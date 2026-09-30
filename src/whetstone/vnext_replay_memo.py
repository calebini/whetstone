"""Invocation-local reuse of pure historical reconstruction, never permission.

Only the private history loaders use ReplayMemo. Every hit repeats observed
D8 reads/listings and confined contract reads, plus the caller's live guard.
No client, publication, durability operation or writer eligibility is cached.
"""
from collections import OrderedDict
from contextvars import ContextVar
from copy import deepcopy
from functools import wraps
import hashlib
import os
from pathlib import Path


_collectors = ContextVar('whetstone_historical_reads', default=())
_contract_roots = ContextVar('whetstone_historical_contract_roots', default=())
_MISSING = ('missing',)


def _fingerprint(value):
    return ('bytes', hashlib.sha256(value).digest()) if isinstance(value, bytes) else ('value', value)


def _record(key, replay, fingerprint):
    for collector in _collectors.get():
        previous = collector.get(key)
        if previous is not None and previous[1] != fingerprint:
            raise ValueError('source changed during historical reconstruction')
        collector[key] = (replay, fingerprint)


def _observe(key, read, replay):
    try:
        value = read()
    except FileNotFoundError:
        _record(key, replay, _MISSING)
        raise
    _record(key, replay, _fingerprint(value))
    return value


def observed_read(method):
    """Observe D8 physical reads without changing their checks or exceptions."""
    @wraps(method)
    def wrapped(owner, relative):
        if not _collectors.get():
            return method(owner, relative)
        return _observe((owner, method.__name__, relative),
                        lambda: method(owner, relative),
                        lambda: getattr(owner, method.__name__)(relative))
    return wrapped


class _ContractPath(type(Path())):
    def read_bytes(self):
        if not _collectors.get():
            return super().read_bytes()
        from whetstone.vnext_contracts import confined_file
        root, relative = self._replay_source
        return _observe(('contract', root, relative), super().read_bytes,
                        lambda: confined_file(root, relative).read_bytes())


def observe_contract_path(path, root, relative):
    # confined_file also serves disposable replay scratch (for example payload
    # verification). Only explicitly pinned contract roots are source inputs;
    # scratch is reconstructed from separately observed D8 bytes.
    if not _collectors.get() or not any(path.is_relative_to(base) for base in _contract_roots.get()):
        return path
    result = _ContractPath(path)
    result._replay_source = (Path(root), relative)
    return result


class ReplayMemo:
    """Bounded to one proof; entries include its proven-base/creation context."""
    def __init__(self, limit=64, *, contract_roots=()):
        self.entries = OrderedDict()
        self.limit = limit
        self.pid = os.getpid()
        self.contract_roots = tuple(Path(root).resolve() for root in contract_roots)

    @staticmethod
    def _unchanged(observations):
        for key, (read, expected) in observations.items():
            try:
                actual = _fingerprint(read())
            except FileNotFoundError:
                actual = _MISSING
            # Also propagate dependencies when the read was supplied by a
            # wrapper that does not itself participate in observation.
            _record(key, read, actual)
            if actual != expected:
                return False
        return True

    def call(self, key, build, guard):
        if os.getpid() != self.pid:
            raise ValueError('historical replay memo belongs to another process')
        guard()
        cached = self.entries.pop(key, None)
        if cached is not None:
            value, observations = cached
            if self._unchanged(observations):
                guard()
                self.entries[key] = cached
                return deepcopy(value)
        observations = {}
        token = _collectors.set((*_collectors.get(), observations))
        roots_token = _contract_roots.set((*_contract_roots.get(), *self.contract_roots))
        try:
            value = build()
        finally:
            _contract_roots.reset(roots_token)
            _collectors.reset(token)
        # Refuse a result assembled from changing sources; never retain an
        # exception or a partially reconstructed entry. Guard after this readback.
        if not self._unchanged(observations):
            raise ValueError('source changed before historical reconstruction completed')
        guard()
        if observations:
            self.entries[key] = (deepcopy(value), observations)
            while len(self.entries) > self.limit:
                self.entries.popitem(last=False)
        return value

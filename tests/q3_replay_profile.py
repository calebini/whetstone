"""Offline Q3 replay measurement on the shipped, still-disabled consuming suite.

Run under m5_bounded_runner.py with PYTHONPATH=src:tests. This developer driver
reuses the four-promotion acceptance journey, replacing only its test-suite
factory and measurement callback. It never enables a public qualification gate.
"""
import argparse
import cProfile
from dataclasses import asdict, is_dataclass
import hashlib
import json
import os
from pathlib import Path
import platform
import pstats
import sys
import time
import unittest
from unittest.mock import patch

from test_vnext_m5_integration import LongerHistoryTests
import test_vnext_verified_semantics as semantics
from vnext_q2_fixtures import suite
from whetstone.vnext_contracts import CONTRACT_ROOT, validate_contract_suite


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def files(root):
    return {p.relative_to(root).as_posix(): digest(p.read_bytes())
            for p in root.rglob('*') if p.is_file()}


def result_bytes(value):
    return json.dumps(asdict(value) if is_dataclass(value) else value,
                      sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if any((out / name).exists() for name in ('measurement.json', 'samples.jsonl', 'stages.jsonl')):
        parser.error('measurement output already exists; preserve it and select a fresh directory')
    pinned = validate_contract_suite(CONTRACT_ROOT / 'suites/vnext-verified-consumer-1.json')
    metadata = dict(suite=pinned.version, suite_digest=pinned.digest,
                    python=sys.version, platform=platform.platform(),
                    outcome='running', public_activation=False,
                    method='test_vnext_m5_integration.LongerHistoryTests.'
                           'test_four_versioned_promotions_replay_exact_history',
                    scope='existing journey on shipped suite; scripted clients; local disposable D8 root')
    def save():
        (out / 'measurement.json').write_text(json.dumps(metadata, indent=2) + '\n')
    save()
    case = LongerHistoryTests('test_four_versioned_promotions_replay_exact_history')

    def sample(f, name):
        # A factory override must actually reach the admitted persisted job.
        job = json.loads(f.store.read_descriptor())
        case.assertEqual(job['contract_suite_version'], pinned.version)
        case.assertEqual(Path(f.run.suite_path).resolve(),
                         CONTRACT_ROOT / 'suites/vnext-verified-consumer-1.json')
        before = files(f.root)
        for operation, call in [('history', lambda: f.run._history().inspect()),
                                ('phase1_state', f.run.phase1_status)]:
            expected = None
            for profiled in (False, True):
                label = name + '-' + operation + ('-profiled' if profiled else '-plain')
                with case.stage(label):
                    profile = cProfile.Profile()
                    wall, cpu = time.perf_counter(), time.process_time()
                    value = profile.runcall(call) if profiled else call()
                    elapsed, cpu_elapsed = time.perf_counter() - wall, time.process_time() - cpu
                    raw = result_bytes(value)
                    if expected is None:
                        expected = raw
                    else:
                        case.assertEqual(raw, expected)
                    case.assertEqual(files(f.root), before, 'read-only replay changed artifacts')
                    row = dict(sample=name, operation=operation, profiled=profiled,
                               wall_seconds=elapsed, process_seconds=cpu_elapsed,
                               result_sha256=digest(raw), artifacts_unchanged=True)
                    if profiled:
                        profile.dump_stats(str(out / (label + '.prof')))
                        stats = pstats.Stats(profile)
                        row['total_calls'] = stats.total_calls
                        row['functions'] = [dict(file=Path(k[0]).name, function=k[2], calls=v[1],
                                                 own_seconds=v[2], cumulative_seconds=v[3])
                            for k, v in stats.stats.items()
                            if k[2] in ('_material', '_seed_inputs', 'validate_contract_suite',
                                        '_replay_transaction', '_unchanged', 'guard')]
                        with (out / (label + '.txt')).open('w') as stream:
                            pstats.Stats(profile, stream=stream).strip_dirs().sort_stats('cumulative').print_stats(40)
                    with (out / 'samples.jsonl').open('a') as stream:
                        stream.write(json.dumps(row) + '\n')
                    print(json.dumps({k: v for k, v in row.items() if k != 'functions'}), flush=True)

    case.sample = sample
    with patch.object(semantics, 'consuming_suite', suite), \
         patch.dict(os.environ, WHETSTONE_M5_EVIDENCE=str(out)), \
         patch('whetstone.vnext_native_editor._run_codex_exec', side_effect=AssertionError('live provider forbidden')), \
         patch('whetstone.vnext_native_editor._run_claude_print', side_effect=AssertionError('live provider forbidden')):
        result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([case]))
    metadata.update(outcome='passed' if result.wasSuccessful() and not result.skipped else 'not_passed',
                    tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                    skips=[reason for _, reason in result.skipped])
    save()
    return 0 if metadata['outcome'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())

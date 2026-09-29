"""Single-source APFS replacement under a live D8 owner; no public capability.

The operator supplies exclusive external access. This adapter does not claim
that the run-root advisory lock excludes arbitrary external writers.
"""
import ctypes
import errno
import os
from pathlib import Path
import stat

from whetstone.vnext_contracts import require, sha256_bytes
from whetstone.vnext_local_storage import (
    _FORK_GATE, _filesystem, _full_flush, _identity, StorageWriteError, Publication,
)


def _empty_acl(fd):
    libc = ctypes.CDLL(None, use_errno=True)
    libc.acl_get_fd.argtypes = [ctypes.c_int]; libc.acl_get_fd.restype = ctypes.c_void_p
    libc.acl_init.argtypes = [ctypes.c_int]; libc.acl_init.restype = ctypes.c_void_p
    libc.acl_to_text.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ssize_t)]
    libc.acl_to_text.restype = ctypes.c_void_p
    libc.acl_free.argtypes = [ctypes.c_void_p]
    def text(acl):
        require(bool(acl), 'cannot inspect source ACL')
        size = ctypes.c_ssize_t()
        result = libc.acl_to_text(acl, ctypes.byref(size))
        try:
            require(bool(result), 'cannot serialize source ACL')
            return ctypes.string_at(result, size.value)
        finally:
            if result: libc.acl_free(result)
            libc.acl_free(acl)
    acl = libc.acl_get_fd(fd)
    if not acl:
        require(ctypes.get_errno() == errno.ENOENT, 'cannot inspect source ACL')
        return True
    return text(acl) == text(libc.acl_init(0))


def _provenance(fd):
    libc = ctypes.CDLL(None, use_errno=True)
    libc.flistxattr.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
    libc.flistxattr.restype = ctypes.c_ssize_t
    size = libc.flistxattr(fd, None, 0, 0)
    require(0 <= size <= 65536, 'cannot inspect source extended attributes')
    names = ctypes.create_string_buffer(size)
    require(libc.flistxattr(fd, names, size, 0) == size, 'source attributes changed')
    keys = set(names.raw.rstrip(b'\0').split(b'\0')) if size else set()
    require(keys <= {b'com.apple.provenance'}, 'source extended attributes require unsupported metadata preservation')
    if not keys: return None
    libc.fgetxattr.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_int]
    libc.fgetxattr.restype = ctypes.c_ssize_t
    size = libc.fgetxattr(fd, b'com.apple.provenance', None, 0, 0, 0)
    require(0 <= size <= 65536, 'cannot inspect source provenance')
    value = ctypes.create_string_buffer(size)
    require(libc.fgetxattr(fd, b'com.apple.provenance', value, size, 0, 0) == size, 'source provenance changed')
    return value.raw.hex()


def _set_provenance(fd, expected):
    if _provenance(fd) == expected: return
    libc = ctypes.CDLL(None, use_errno=True)
    if expected is None:
        libc.fremovexattr.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
        result = libc.fremovexattr(fd, b'com.apple.provenance', 0)
    else:
        raw = bytes.fromhex(expected)
        libc.fsetxattr.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_int]
        result = libc.fsetxattr(fd, b'com.apple.provenance', raw, len(raw), 0, 0)
    require(result == 0, 'cannot preserve source provenance')


def _metadata(fd):
    info = os.fstat(fd)
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'source must be a single-link regular file')
    require(info.st_uid == os.geteuid() and not (info.st_mode & 0o7000), 'unsupported source ownership or special permissions')
    require(not info.st_flags and _empty_acl(fd),
            'source flags, extended attributes or ACL require unsupported metadata preservation')
    return dict(mode=stat.S_IMODE(info.st_mode), uid=info.st_uid, gid=info.st_gid, provenance=_provenance(fd))


def _read(fd):
    os.lseek(fd, 0, os.SEEK_SET)
    chunks = []
    while True:
        raw = os.read(fd, 65536)
        if not raw: return b''.join(chunks)
        chunks.append(raw)


class SourceFile:
    def __init__(self, store, path):
        self.store = store
        value = Path(path)
        require(value.is_absolute() and str(value) == path and '..' not in value.parts,
                'source requires a canonical absolute path')
        require(not value.is_relative_to(store.root), 'source must be outside the run root')
        self.path, self.parent_path, self.leaf = value, value.parent, value.name
        self.parent = None
        # Walk every component without following links, retaining the parent fd.
        fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            for part in value.parent.parts[1:]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
                os.close(fd); fd = child
            require(_filesystem(fd) == store._tree.filesystem and os.fstat(fd).st_dev == store._tree.device,
                    'source must share the qualified local run filesystem')
            self.parent_identity = _identity(os.fstat(fd))
            self.parent = fd
        finally:
            if self.parent is None: os.close(fd)

    def close(self):
        if self.parent is not None: os.close(self.parent); self.parent = None

    def __enter__(self): return self
    def __exit__(self, *args): self.close()

    def check_parent(self):
        require(self.parent is not None, 'source parent is closed')
        require(str(self.parent_path.resolve(strict=True)) == str(self.parent_path), 'source parent became a symlink')
        require(_identity(os.stat(self.parent_path, follow_symlinks=False)) == self.parent_identity
                and _identity(os.fstat(self.parent)) == self.parent_identity, 'source parent identity changed')
        require(_filesystem(self.parent) == self.store._tree.filesystem, 'source filesystem changed')

    def open(self, name):
        self.check_parent()
        return os.open(name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=self.parent)

    def observe(self):
        fd = self.open(self.leaf)
        try:
            before = os.fstat(fd); metadata = _metadata(fd); raw = _read(fd); after = os.fstat(fd)
            require((before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns) ==
                    (after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns), 'source changed while reading')
            require(_identity(os.stat(self.leaf, dir_fd=self.parent, follow_symlinks=False)) == _identity(after),
                    'source changed while reading')
            self.check_parent()
            return raw, dict(parent_identity=self.parent_identity, file_identity=_identity(after),
                             metadata=metadata, mtime_ns=after.st_mtime_ns, ctime_ns=after.st_ctime_ns)
        finally: os.close(fd)

    def prepare(self, token, name, raw, metadata):
        require(name.startswith('.whetstone-apply-') and Path(name).name == name and '\\' not in name,
                'invalid source staging name')
        with _FORK_GATE, self.store._mutex:
            self.store._check_owner(token); self.check_parent()
            try:
                fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                             0o600, dir_fd=self.parent)
            except FileExistsError:
                fd = self.open(name)
                try:
                    require(_read(fd) == raw and _metadata(fd) == metadata, 'source staging file conflicts')
                    _full_flush(fd); os.fsync(self.parent)
                    return _identity(os.fstat(fd))
                finally: os.close(fd)
            try:
                view = memoryview(raw)
                while view:
                    self.store._check_owner(token)
                    count = os.write(fd, view); require(count > 0, 'short source staging write'); view = view[count:]
                os.fchown(fd, metadata['uid'], metadata['gid']); os.fchmod(fd, metadata['mode'])
                _set_provenance(fd, metadata['provenance'])
                require(_metadata(fd) == metadata, 'source staging metadata differs')
                _full_flush(fd); os.fsync(self.parent)
                self.store._check_owner(token)
                return _identity(os.fstat(fd))
            finally: os.close(fd)

    def replace(self, token, *, name, identity, raw, before, guard):
        require(name.startswith('.whetstone-apply-') and Path(name).name == name and '\\' not in name,
                'invalid source staging name')
        attempted = False
        with _FORK_GATE, self.store._mutex:
            try:
                self.store._check_owner(token); guard()
                observed, current = self.observe()
                require(observed == before[0] and current == before[1], 'source changed before replacement')
                fd = self.open(name)
                try:
                    require(_identity(os.fstat(fd)) == identity and _read(fd) == raw
                            and _metadata(fd) == current['metadata'], 'source staging evidence changed')
                    _full_flush(fd)
                finally: os.close(fd)
                self.store._check_owner(token); self.check_parent()
                attempted = True
                os.replace(name, self.leaf, src_dir_fd=self.parent, dst_dir_fd=self.parent)
                self.synchronize(token, raw=raw, identity=identity, metadata=current['metadata'])
            except BaseException as exc:
                if attempted:
                    self.store._invalidate()
                    raise StorageWriteError(Publication('outcome_requires_reconciliation', str(self.path), sha256_bytes(raw)), exc) from exc
                raise

    def synchronize(self, token, *, raw, identity, metadata):
        with _FORK_GATE, self.store._mutex:
            self.store._check_owner(token); self.check_parent()
            fd = self.open(self.leaf)
            try:
                require(_identity(os.fstat(fd)) == identity and _read(fd) == raw, 'source readback differs')
                require(_metadata(fd) == metadata, 'source metadata changed during durability barrier')
                _full_flush(fd); os.fsync(self.parent); _full_flush(fd)
                self.store._check_owner(token)
                observed, seen = self.observe()
                require(observed == raw and seen['file_identity'] == identity and seen['metadata'] == metadata,
                        'source changed during durability barrier')
            finally: os.close(fd)

"""Local publication primitives for exclusive seed initialization.

Registration/promotion fencing is deliberately not advertised by these helpers.
"""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import tempfile

from whetstone.vnext_contracts import canonical_json_bytes, require, sha256_bytes


def safe_path(root: Path, relative: str) -> Path:
    path = Path(relative)
    require(bool(relative) and not path.is_absolute() and ".." not in path.parts
            and path.as_posix() == relative and "\\" not in relative and "\x00" not in relative,
            "invalid local publication path")
    current = root
    for part in path.parts:
        current /= part
        require(not current.is_symlink(), "publication path contains a symlink")
    return current


def sync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def make_directory(root: Path, relative: str) -> Path:
    path = safe_path(root, relative)
    if not path.exists():
        if path.parent != root:
            make_directory(root, path.parent.relative_to(root).as_posix())
        path.mkdir()
        sync_directory(path.parent)
    require(path.is_dir(), "publication parent is not a directory")
    return path


def publish(root: Path, relative: str, value, *, replace: bool = False) -> dict:
    """Durable same-directory publish; immutable replay must match exact bytes."""
    raw = value if isinstance(value, bytes) else canonical_json_bytes(value)
    path = safe_path(root, relative)
    make_directory(root, path.parent.relative_to(root).as_posix()) if path.parent != root else None
    fd, name = tempfile.mkstemp(prefix=".vnext-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        safe_path(root, relative)
        if replace:
            os.replace(name, path)
        else:
            try:
                os.link(name, path)
            except FileExistsError:
                require(path.read_bytes() == raw, "immutable publication conflict", relative)
        sync_directory(path.parent)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return {"path": relative, "hash": sha256_bytes(raw)}


@contextmanager
def writer(root: Path):
    """Existing-root advisory exclusion; never delete/replace the lock inode."""
    path = safe_path(root, "rounds/.vnext-writer.lock")
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)

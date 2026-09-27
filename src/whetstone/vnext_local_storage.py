"""Proposed D8 single-host storage kernel; not a registered runtime capability.

Only macOS/local APFS is an implementation target here. Process/fault tests do
not establish physical power-loss guarantees. Domain callers must validate
committed lineage under acquisition and every pointer transition.
"""
from contextlib import contextmanager
import ctypes
from dataclasses import dataclass
import fcntl
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import threading

from whetstone.vnext_contracts import VNextSchemaRegistry, canonical_json_bytes, decode_json, require, sha256_bytes


LOCK_PATH='rounds/.vnext-authority.lock'
BINDING_PATH='rounds/authority_storage.json'
_FORK_GATE=threading.RLock()
_STORES=set()  # Open handles stay registered until explicit close.


class StorageBusy(RuntimeError):pass
class OwnershipLost(RuntimeError):pass


@dataclass(frozen=True)
class Publication:
    outcome: str
    path: str
    hash: str


class StorageWriteError(RuntimeError):
    def __init__(self,result,cause):
        self.result=result
        super().__init__(result.outcome+': '+str(cause))


class _StatFS(ctypes.Structure):
    # __DARWIN_STRUCT_STATFS64 from the local SDK's sys/mount.h.
    _fields_=[('bsize',ctypes.c_uint32),('iosize',ctypes.c_int32),
              *[(n,ctypes.c_uint64) for n in ('blocks','bfree','bavail','files','ffree')],
              ('fsid',ctypes.c_int32*2),('owner',ctypes.c_uint32),('type',ctypes.c_uint32),
              ('flags',ctypes.c_uint32),('subtype',ctypes.c_uint32),('name',ctypes.c_char*16),
              ('mount',ctypes.c_char*1024),('source',ctypes.c_char*1024),
              ('extended_flags',ctypes.c_uint32),('reserved',ctypes.c_uint32*7)]


def _filesystem(fd):
    require(sys.platform=='darwin','D8 storage is not qualified for this platform')
    libc=ctypes.CDLL(None,use_errno=True)
    function=getattr(libc,'fstatfs$INODE64',libc.fstatfs)
    function.argtypes=[ctypes.c_int,ctypes.POINTER(_StatFS)];function.restype=ctypes.c_int
    value=_StatFS()
    if function(fd,ctypes.byref(value)):
        error=ctypes.get_errno();raise OSError(error,os.strerror(error))
    name=value.name.decode('ascii')
    require(name=='apfs' and bool(value.flags&0x1000),'D8 storage requires local APFS')
    return {'type':name,'fsid':list(value.fsid)}


def _full_flush(fd):
    os.fsync(fd)
    fcntl.fcntl(fd,getattr(fcntl,'F_FULLFSYNC',51))


def _identity(info):return [info.st_dev,info.st_ino]


def _parts(relative):
    require(isinstance(relative,str),'storage path must be a string')
    path=Path(relative)
    require(bool(path.parts) and not path.is_absolute() and '..' not in path.parts
            and path.as_posix()==relative and '\\' not in relative and '\x00' not in relative,
            'invalid confined storage path')
    require(not any(p.startswith('.vnext-tmp-') for p in path.parts),'temporary names are adapter-owned')
    return path.parts


class _Tree:
    def __init__(self,root):
        self.root=Path(root).resolve(strict=True)
        self.fd=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        self.identity=_identity(os.fstat(self.fd));self.device=self.identity[0]
        try:self.filesystem=_filesystem(self.fd)
        except BaseException:os.close(self.fd);self.fd=None;raise

    def check(self):
        if self.fd is None:raise OwnershipLost('storage root handle is closed')
        info=os.stat(self.root,follow_symlinks=False)
        if not stat.S_ISDIR(info.st_mode) or _identity(info)!=self.identity or _identity(os.fstat(self.fd))!=self.identity:
            raise OwnershipLost('physical storage root changed')
        if _filesystem(self.fd)!=self.filesystem:raise OwnershipLost('storage filesystem changed')

    @contextmanager
    def parent(self,relative,*,create=False,check=None):
        parts=_parts(relative);current=os.dup(self.fd);os.set_inheritable(current,False)
        try:
            for part in parts[:-1]:
                if create:
                    check()
                    try:os.mkdir(part,0o700,dir_fd=current);os.fsync(current)
                    except FileExistsError:pass
                child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=current)
                if os.fstat(child).st_dev!=self.device:
                    os.close(child);raise OwnershipLost('storage directory crosses the root device')
                os.close(current);current=child
            yield current,parts[-1]
        finally:os.close(current)

    def read(self,relative):
        self.check()
        with self.parent(relative) as (parent,leaf):
            fd=os.open(leaf,os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=parent)
            try:
                info=os.fstat(fd)
                require(stat.S_ISREG(info.st_mode) and info.st_dev==self.device,'storage artifact is not a confined regular file')
                chunks=[]
                while True:
                    raw=os.read(fd,65536)
                    if not raw:break
                    chunks.append(raw)
                return b''.join(chunks)
            finally:os.close(fd)

    def list_directory(self,relative):
        self.check()
        with self.parent(relative) as (parent,leaf):
            fd=os.open(leaf,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=parent)
            try:
                require(os.fstat(fd).st_dev==self.device,'storage directory crosses the root device')
                entries=[]
                for name in os.listdir(fd):
                    info=os.stat(name,dir_fd=fd,follow_symlinks=False)
                    require(info.st_dev==self.device and (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)),
                            'storage directory contains an unconfined entry')
                    entries.append((name,'directory' if stat.S_ISDIR(info.st_mode) else 'file'))
                return tuple(sorted(entries))
            finally:os.close(fd)

    def write(self,relative,raw,*,check,replace=False):
        """Return only after the final directory/file ordering barrier."""
        attempted=False;name=None;fd=None;existing_fd=None
        try:
            check()
            with self.parent(relative,create=True,check=check) as (parent,leaf):
                name='.vnext-tmp-'+secrets.token_hex(16)
                check();fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=parent)
                try:
                    remaining=memoryview(raw)
                    while remaining:
                        check();written=os.write(fd,remaining)
                        require(written>0,'zero-byte storage write');remaining=remaining[written:]
                    check();_full_flush(fd)
                    check();attempted=True
                    if replace:
                        os.replace(name,leaf,src_dir_fd=parent,dst_dir_fd=parent);name=None
                    else:
                        try:os.link(name,leaf,src_dir_fd=parent,dst_dir_fd=parent,follow_symlinks=False)
                        except FileExistsError:
                            attempted=False
                            require(self.read(relative)==raw,'immutable storage publication conflict')
                            existing_fd=os.open(leaf,os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=parent)
                            attempted=True  # Existing authority still requires its replay durability barrier.
                    if name is not None:
                        check();os.fsync(parent)
                        check();os.unlink(name,dir_fd=parent);name=None
                    check();os.fsync(parent)
                    check();_full_flush(existing_fd if existing_fd is not None else fd)
                    return Publication('committed',relative,sha256_bytes(raw))
                finally:
                    # Never roll back a final name. Keep interrupted temporaries
                    # as evidence; cleanup is optional under later ownership.
                    if fd is not None:os.close(fd)
                    if existing_fd is not None:os.close(existing_fd)
        except BaseException as exc:
            outcome='outcome_requires_reconciliation' if attempted else 'not_committed'
            raise StorageWriteError(Publication(outcome,relative,sha256_bytes(raw)),exc) from exc

    def close(self):
        if self.fd is not None:
            fd=self.fd;self.fd=None;os.close(fd)


def initialize_storage(root,*,job_id,descriptor_ref,artifacts):
    """Exclusive fresh-root initialization only; never repair or upgrade a root."""
    require(re.fullmatch(r'job_[0-9a-f]{64}',job_id) is not None,'invalid storage job identity')
    require(set(descriptor_ref)=={'path','hash'} and descriptor_ref['path'] in artifacts,'missing initial descriptor')
    require(all(isinstance(raw,bytes) for raw in artifacts.values()),'initial artifacts require exact bytes')
    require(sha256_bytes(artifacts[descriptor_ref['path']])==descriptor_ref['hash'],'initial descriptor hash differs')
    descriptor=decode_json(artifacts[descriptor_ref['path']])
    require(descriptor['job_id']==job_id and canonical_json_bytes(descriptor)==artifacts[descriptor_ref['path']],
            'initial descriptor identity or encoding differs')
    for path in artifacts:
        _parts(path);require(path not in {LOCK_PATH,BINDING_PATH},'initial artifacts use a reserved storage path')
    requested=Path(root).absolute();require(requested.name not in {'.','..',''},'invalid fresh root')
    root=requested.parent.resolve(strict=True)/requested.name
    with _FORK_GATE:
        root.mkdir(mode=0o700)
        tree=_Tree(root)
        try:
            parent=os.open(root.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
            try:os.fsync(parent)
            finally:os.close(parent)
            for path,raw in sorted(artifacts.items()):tree.write(path,raw,check=tree.check)
            lock_raw=canonical_json_bytes({'schema_version':'vnext-authority-lock-v1','job_id':job_id})
            tree.write(LOCK_PATH,lock_raw,check=tree.check)
            with tree.parent(LOCK_PATH) as (parent,leaf):
                info=os.stat(leaf,dir_fd=parent,follow_symlinks=False)
                require(stat.S_ISREG(info.st_mode) and info.st_nlink==1,'initial lock inode is invalid')
            binding={'schema_version':'vnext-local-storage-binding-v1','job_id':job_id,
                'root_path':str(root),'root_identity':tree.identity,'filesystem':tree.filesystem,
                'lock_identity':_identity(info),'lock_hash':sha256_bytes(lock_raw),'descriptor':descriptor_ref}
            tree.write(BINDING_PATH,canonical_json_bytes(binding),check=tree.check)
            return binding
        finally:tree.close()


class _Ownership:
    __slots__=('_store','_nonce','_pid')
    def __init__(self,store,nonce):self._store=store;self._nonce=nonce;self._pid=os.getpid()
    def __copy__(self):raise TypeError('storage ownership cannot be copied')
    def __deepcopy__(self,memo):raise TypeError('storage ownership cannot be copied')
    def __reduce__(self):raise TypeError('storage ownership cannot be serialized')


class LocalAuthorityStore:
    @property
    def root(self):
        """Physical run directory, after checking its retained binding."""
        self._check_binding()
        return self._tree.root

    def __init__(self,root,*,job_id):
        with _FORK_GATE:
            self._mutex=threading.RLock();self._pid=os.getpid();self._lock_fd=None;self._token=None;self._nonce=None
            self._tree=_Tree(root)
            try:
                self._binding_raw=self._tree.read(BINDING_PATH);self._binding=decode_json(self._binding_raw)
                VNextSchemaRegistry().validate(self._binding,'vnext_local_storage_binding_v1')
                require(self._binding_raw==canonical_json_bytes(self._binding),'noncanonical storage binding')
                require(self._binding['schema_version']=='vnext-local-storage-binding-v1' and self._binding['job_id']==job_id,
                        'storage binding belongs to another job or protocol')
                require(self._binding['root_identity']==self._tree.identity and self._binding['root_path']==str(self._tree.root)
                        and self._binding['filesystem']==self._tree.filesystem,'storage binding belongs to another physical root')
                self._check_binding()
            except BaseException:self._tree.close();raise
            _STORES.add(self)

    def _check_binding(self):
        if os.getpid()!=self._pid:raise OwnershipLost('storage object belongs to another process')
        self._tree.check()
        require(self._tree.read(BINDING_PATH)==self._binding_raw,'immutable storage binding changed')
        descriptor=self._binding['descriptor']
        require(sha256_bytes(self._tree.read(descriptor['path']))==descriptor['hash'],'immutable storage descriptor changed')
        with self._tree.parent(LOCK_PATH) as (parent,leaf):
            info=os.stat(leaf,dir_fd=parent,follow_symlinks=False)
            require(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and _identity(info)==self._binding['lock_identity'],
                    'retained authority lock inode changed')
        require(sha256_bytes(self._tree.read(LOCK_PATH))==self._binding['lock_hash'],'retained lock bytes changed')
        if self._lock_fd is not None:
            held=os.fstat(self._lock_fd)
            if _identity(held)!=self._binding['lock_identity'] or held.st_nlink!=1:
                raise OwnershipLost('live lock descriptor changed')

    def _check_token(self,token):
        if token is not self._token or token is None or token._store is not self or token._pid!=os.getpid() or token._nonce!=self._nonce:
            raise OwnershipLost('ownership token is stale, foreign or copied')
        if self._lock_fd is None:raise OwnershipLost('ownership descriptor is closed')

    def _check_owner(self,token):
        self._check_token(token)
        self._check_binding()

    def _invalidate(self):
        self._token=None;self._nonce=None
        if self._lock_fd is not None:
            fd=self._lock_fd;self._lock_fd=None;os.close(fd)  # Never LOCK_UN; fork descriptors share the lock.

    def acquire(self,validate_lineage):
        require(callable(validate_lineage),'locked lineage validator is required')
        with _FORK_GATE,self._mutex:
            self._check_binding()
            if self._lock_fd is not None:raise StorageBusy('this storage object already holds authority')
            with self._tree.parent(LOCK_PATH) as (parent,leaf):
                self._lock_fd=os.open(leaf,os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=parent)
            try:
                try:fcntl.flock(self._lock_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError as exc:raise StorageBusy('another process holds authority') from exc
                self._check_binding();validate_lineage(self._tree.read);self._check_binding()
                self._nonce=secrets.token_hex(32);self._token=_Ownership(self,self._nonce)
                return self._token
            except BaseException:self._invalidate();raise

    def release(self,token):
        with _FORK_GATE,self._mutex:
            # Closing our descriptor must remain possible after path tampering.
            self._check_token(token);self._invalidate()

    @contextmanager
    def locked(self,validate_lineage):
        token=self.acquire(validate_lineage)
        try:yield token
        finally:
            with _FORK_GATE,self._mutex:
                if token is self._token:self._invalidate()

    def read(self,relative):
        with _FORK_GATE,self._mutex:
            self._check_binding();return self._tree.read(relative)

    def list_directory(self,relative):
        with _FORK_GATE,self._mutex:
            self._check_binding();return self._tree.list_directory(relative)

    def read_descriptor(self):
        return self.read(self._binding['descriptor']['path'])

    def publish(self,token,relative,value):
        raw=value if isinstance(value,bytes) else canonical_json_bytes(value)
        require(relative not in {LOCK_PATH,BINDING_PATH,self._binding['descriptor']['path']},'cannot repurpose storage control artifacts')
        with _FORK_GATE,self._mutex:
            self._check_owner(token)
            try:return self._tree.write(relative,raw,check=lambda:self._check_owner(token))
            except StorageWriteError as exc:
                if exc.result.outcome=='outcome_requires_reconciliation':self._invalidate()
                raise

    def replace_pointer(self,token,relative,*,expected,snapshot,validate_transition):
        require(callable(validate_transition),'pointer transition validator is required')
        require(relative not in {LOCK_PATH,BINDING_PATH,self._binding['descriptor']['path']} and relative!=snapshot['path'],
                'invalid pointer destination')
        with _FORK_GATE,self._mutex:
            self._check_owner(token)
            raw=self._tree.read(snapshot['path']);require(sha256_bytes(raw)==snapshot['hash'],'pointer snapshot hash differs')
            require(canonical_json_bytes(decode_json(raw))==raw,'pointer snapshot must be canonical JSON')
            try:old=self._tree.read(relative)
            except FileNotFoundError:old=None
            require(old==expected,'current pointer differs from expected bytes')
            validate_transition(old,raw)
            self._check_owner(token)
            try:current=self._tree.read(relative)
            except FileNotFoundError:current=None
            require(current==expected,'pointer changed during transition validation')
            try:return self._tree.write(relative,raw,check=lambda:self._check_owner(token),replace=True)
            except StorageWriteError as exc:
                if exc.result.outcome=='outcome_requires_reconciliation':self._invalidate()
                raise

    def synchronize_existing(self, token, relative, *, expected):
        """Repeat durability barriers for exact existing bytes; never create."""
        require(isinstance(expected, bytes), 'existing synchronization requires exact bytes')
        require(relative not in {LOCK_PATH, BINDING_PATH, self._binding['descriptor']['path']},
                'cannot synchronize storage control artifacts through a consumer')
        with _FORK_GATE, self._mutex:
            self._check_owner(token)
            require(self._tree.read(relative) == expected, 'existing synchronization bytes changed')
            try:
                with self._tree.parent(relative) as (parent, leaf):
                    fd = os.open(leaf, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
                    try:
                        self._check_owner(token); _full_flush(fd)
                        self._check_owner(token); os.fsync(parent)
                        self._check_owner(token); _full_flush(fd)
                    finally: os.close(fd)
                return Publication('committed', relative, sha256_bytes(expected))
            except BaseException as exc:
                self._invalidate()
                raise StorageWriteError(Publication('outcome_requires_reconciliation', relative,
                                        sha256_bytes(expected)), exc) from exc

    def materialize(self, token, relative, raw, *, validate_target):
        """Fenced replacement of a declared derived mirror, never authority."""
        require(relative in {'spec.md', 'rounds/run_state.json', 'rounds/technical_failure_report.json'}
                or re.fullmatch(r'rounds/round-[1-9][0-9]*/draft_after\.md', relative),
                'unsupported materialization destination')
        require(isinstance(raw, bytes) and callable(validate_target), 'materialization requires bytes and validation')
        with _FORK_GATE, self._mutex:
            self._check_owner(token)
            validate_target(self._tree.read, relative, raw)
            self._check_owner(token)
            try: return self._tree.write(relative, raw, check=lambda: self._check_owner(token), replace=True)
            except StorageWriteError as exc:
                if exc.result.outcome == 'outcome_requires_reconciliation': self._invalidate()
                raise

    def close(self):
        with _FORK_GATE,self._mutex:
            self._invalidate();self._tree.close();_STORES.discard(self)

    def __enter__(self):return self
    def __exit__(self,*exc):self.close()


def _before_fork():_FORK_GATE.acquire()
def _after_parent():_FORK_GATE.release()
def _after_child():
    global _FORK_GATE
    for store in list(_STORES):
        store._invalidate();store._tree.close();store._mutex=threading.RLock()
    _STORES.clear();_FORK_GATE=threading.RLock()


os.register_at_fork(before=_before_fork,after_in_parent=_after_parent,after_in_child=_after_child)

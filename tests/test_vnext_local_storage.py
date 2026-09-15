"""Unactivated D8 kernel probes: real local processes and injected IO failures.

These are not candidate registration or physical power-loss qualification.
"""
import copy
import json
import os
from pathlib import Path
import pickle
import select
import shutil
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch

from whetstone import vnext_local_storage as storage
from whetstone.contracts import SchemaValidationError
from whetstone.vnext_contracts import VNextSchemaRegistry, canonical_json_bytes, sha256_bytes


JOB='job_'+'a'*64
DESCRIPTOR='rounds/job.json'
POINTER='rounds/current.json'


@unittest.skipUnless(sys.platform=='darwin','D8 first target is macOS/local APFS')
class LocalStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve();self.root=self.base/'run'
        raw=canonical_json_bytes({'job_id':JOB})
        self.descriptor={'path':DESCRIPTOR,'hash':sha256_bytes(raw)}
        self.artifacts={DESCRIPTOR:raw,'rounds/seed.md':b'# Seed\n'}
        self.binding=storage.initialize_storage(self.root,job_id=JOB,descriptor_ref=self.descriptor,artifacts=self.artifacts)
        self.store=self.open_store()

    def open_store(self):
        store=storage.LocalAuthorityStore(self.root,job_id=JOB)
        self.addCleanup(store.close);return store

    def lineage(self,read):
        self.assertEqual(read(DESCRIPTOR),self.artifacts[DESCRIPTOR])
        self.assertEqual(read('rounds/seed.md'),b'# Seed\n')

    def snapshot(self,token,ordinal):
        path=f'rounds/history/{ordinal}.json';raw=canonical_json_bytes({'ordinal':ordinal,'body':'x'*65536})
        result=self.store.publish(token,path,raw)
        return {'path':path,'hash':result.hash},raw

    def transition(self,old,new):
        expected=0 if old is None else json.loads(old)['ordinal']+1
        self.assertEqual(json.loads(new)['ordinal'],expected)

    def commit(self,token,ordinal,old):
        ref,raw=self.snapshot(token,ordinal)
        self.store.replace_pointer(token,POINTER,expected=old,snapshot=ref,validate_transition=self.transition)
        return raw

    def process(self,body):
        prefix='''import os,signal,sys,time
from pathlib import Path
from whetstone.vnext_local_storage import LocalAuthorityStore,StorageBusy
root=Path(sys.argv[1]);job=sys.argv[2]
'''
        child=subprocess.Popen([sys.executable,'-u','-c',prefix+body,str(self.root),JOB],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,stdin=subprocess.PIPE)
        def cleanup():
            if child.poll() is None:child.kill()
            child.communicate(timeout=5)
        self.addCleanup(cleanup);return child

    def ready(self,child):
        readable,_,_=select.select([child.stdout],[],[],5)
        self.assertTrue(readable,'child did not signal readiness')
        self.assertEqual(child.stdout.readline(),b'ready\n')

    def test_initialization_is_fresh_only_and_does_not_repair(self):
        with self.assertRaises(FileExistsError):
            storage.initialize_storage(self.root,job_id=JOB,descriptor_ref=self.descriptor,artifacts=self.artifacts)
        self.assertEqual(self.binding['filesystem']['type'],'apfs')
        self.assertEqual((self.root/storage.LOCK_PATH).stat().st_nlink,1)
        empty=self.base/'empty';empty.mkdir()
        with self.assertRaises(FileExistsError):
            storage.initialize_storage(empty,job_id=JOB,descriptor_ref=self.descriptor,artifacts=self.artifacts)

    def test_unsupported_platform_refuses_without_fallback(self):
        with patch.object(storage.sys,'platform','linux'):
            with self.assertRaisesRegex(ValueError,'not qualified'):self.open_store()

    def test_descriptor_and_binding_are_immutable_and_closed(self):
        token=self.store.acquire(self.lineage)
        for name in [DESCRIPTOR,storage.BINDING_PATH,storage.LOCK_PATH]:
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'control artifacts'):
                self.store.publish(token,name,b'changed')
        (self.root/DESCRIPTOR).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'descriptor changed'):
            self.store.publish(token,'rounds/no.json',{})
        self.store.release(token)  # Tampering cannot strand our descriptor.
        self.assertIsNone(self.store._lock_fd)
        (self.root/DESCRIPTOR).write_bytes(self.artifacts[DESCRIPTOR])
        binding=dict(self.binding);binding['unexpected']=1
        (self.root/storage.BINDING_PATH).write_bytes(canonical_json_bytes(binding))
        with self.assertRaises(ValueError):self.open_store()

    def test_binding_schema_requires_normalized_root_relative_descriptor_path(self):
        registry=VNextSchemaRegistry()
        for path in ['job_descriptor.json','rounds/job.json','inputs/nested/job.json']:
            binding=copy.deepcopy(self.binding);binding['descriptor']['path']=path
            with self.subTest(path=path):registry.validate(binding,'vnext_local_storage_binding_v1')
        for path in ['', '/', '/job.json', '../job.json', 'rounds/../job.json',
                     '.', '..', './job.json', 'rounds/./job.json', 'rounds//job.json',
                     'rounds/job.json/', 'rounds\\job.json', 'rounds/\x00job.json',
                     '.vnext-tmp-job', 'rounds/.vnext-tmp-job/descriptor.json']:
            binding=copy.deepcopy(self.binding);binding['descriptor']['path']=path
            with self.subTest(path=path),self.assertRaises(SchemaValidationError):
                registry.validate(binding,'vnext_local_storage_binding_v1')

    def test_descriptor_resolution_is_independent_of_process_working_directory(self):
        misleading=self.base/DESCRIPTOR;misleading.parent.mkdir()
        misleading.write_bytes(b'wrong descriptor in process working directory')
        child=self.process("""os.chdir(root.parent)
with LocalAuthorityStore(root,job_id=job) as store:
    assert store.read_descriptor() == (root/'rounds/job.json').read_bytes()
    token=store.acquire(lambda read: None)
    store.release(token)
print('ready',flush=True)
""")
        self.ready(child)
        _,error=child.communicate(timeout=5)
        self.assertEqual(child.returncode,0,error)
        self.assertEqual(misleading.read_bytes(),b'wrong descriptor in process working directory')

    def test_wrong_job_or_physical_copy_cannot_acquire(self):
        with self.assertRaisesRegex(ValueError,'another job'):
            storage.LocalAuthorityStore(self.root,job_id='job_'+'b'*64)
        copied=self.base/'copied';shutil.copytree(self.root,copied)
        with self.assertRaisesRegex(ValueError,'physical root'):
            storage.LocalAuthorityStore(copied,job_id=JOB)

    def test_missing_lock_is_not_recreated(self):
        (self.root/storage.LOCK_PATH).unlink()
        with self.assertRaises(FileNotFoundError):self.open_store()
        self.assertFalse((self.root/storage.LOCK_PATH).exists())

    def test_replaced_lock_same_bytes_is_rejected(self):
        lock=self.root/storage.LOCK_PATH;raw=lock.read_bytes()
        lock.rename(lock.with_name('old-lock'));lock.write_bytes(raw)
        with self.assertRaisesRegex(ValueError,'lock inode changed'):self.open_store()

    def test_symlink_and_multilink_locks_are_rejected(self):
        lock=self.root/storage.LOCK_PATH;other=self.base/'lock'
        os.link(lock,other)
        with self.assertRaisesRegex(ValueError,'lock inode changed'):self.open_store()
        other.unlink();lock.rename(other);lock.symlink_to(other)
        with self.assertRaisesRegex(ValueError,'lock inode changed'):self.open_store()

    def test_live_root_replacement_fences_publication(self):
        token=self.store.acquire(self.lineage)
        self.root.rename(self.base/'moved');self.root.mkdir()
        with self.assertRaises(storage.OwnershipLost):self.store.publish(token,'rounds/no.json',{})
        self.store.release(token)
        self.assertFalse((self.root/'rounds/no.json').exists())

    def test_changed_filesystem_and_cross_device_directory_refuse(self):
        token=self.store.acquire(self.lineage)
        with patch.object(storage,'_filesystem',return_value={'type':'apfs','fsid':[0,0]}):
            with self.assertRaises(storage.OwnershipLost):self.store.publish(token,'rounds/no',b'x')
        other=self.root/'other';other.mkdir();inode=other.stat().st_ino;original=os.fstat
        def crossed(fd):
            info=original(fd)
            if info.st_ino==inode:
                fields=list(info);fields[2]+=1;return os.stat_result(fields)
            return info
        with patch.object(storage.os,'fstat',side_effect=crossed):
            with self.assertRaises(storage.StorageWriteError) as error:self.store.publish(token,'other/no',b'x')
        self.assertEqual(error.exception.result.outcome,'not_committed')
        self.assertFalse((other/'no').exists())

    def test_lock_bytes_change_is_detected_without_replacing_inode(self):
        token=self.store.acquire(self.lineage)
        (self.root/storage.LOCK_PATH).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'lock bytes changed'):self.store.publish(token,'rounds/no',b'x')
        self.store.release(token)

    def test_failed_lineage_validation_grants_no_token(self):
        def reject(read):raise ValueError('invalid committed chain')
        with self.assertRaisesRegex(ValueError,'invalid committed chain'):self.store.acquire(reject)
        self.assertIsNone(self.store._lock_fd)
        with self.open_store().locked(self.lineage):pass

    def test_contention_and_stale_foreign_copied_tokens(self):
        token=self.store.acquire(self.lineage);other=self.open_store()
        with self.assertRaises(storage.StorageBusy):other.acquire(self.lineage)
        with self.assertRaises(storage.StorageBusy):self.store.acquire(self.lineage)
        with self.assertRaises(storage.OwnershipLost):other.publish(token,'rounds/no.json',{})
        for copier in [copy.copy,copy.deepcopy,pickle.dumps]:
            with self.assertRaises(TypeError):copier(token)
        self.store.release(token)
        with self.store.locked(self.lineage) as current:
            with self.assertRaises(storage.OwnershipLost):self.store.publish(token,'rounds/no.json',{})
            self.assertEqual(self.store.publish(current,'rounds/ok.json',{}).outcome,'committed')

    def test_paused_process_keeps_lock_and_death_releases_it(self):
        child=self.process('''store=LocalAuthorityStore(root,job_id=job)
token=store.acquire(lambda read:read('rounds/seed.md'))
print('ready',flush=True)
sys.stdin.read()
''')
        self.ready(child);os.kill(child.pid,signal.SIGSTOP)
        with self.assertRaises(storage.StorageBusy):self.store.acquire(self.lineage)
        child.kill();child.wait(timeout=5)
        with self.store.locked(self.lineage):pass

    def test_fork_child_cannot_write_or_unlock_parent(self):
        token=self.store.acquire(self.lineage);read_fd,write_fd=os.pipe()
        pid=os.fork()
        if pid==0:
            os.close(read_fd)
            try:
                try:self.store.publish(token,'rounds/child.json',{})
                except storage.OwnershipLost:pass
                else:raise AssertionError('inherited token accepted')
                self.store.close()
                with storage.LocalAuthorityStore(self.root,job_id=JOB) as child_store:
                    try:child_store.acquire(lambda read:None)
                    except storage.StorageBusy:pass
                    else:raise AssertionError('child unlocked parent')
                os.write(write_fd,b'ok')
            except BaseException as exc:os.write(write_fd,repr(exc).encode())
            finally:os.close(write_fd);os._exit(0)
        os.close(write_fd)
        try:
            readable,_,_=select.select([read_fd],[],[],5)
            self.assertTrue(readable,'fork child did not complete')
            self.assertEqual(os.read(read_fd,4096),b'ok')
        finally:
            os.close(read_fd)
            try:os.kill(pid,signal.SIGKILL)
            except ProcessLookupError:pass
            os.waitpid(pid,0)
        self.assertEqual(self.store.publish(token,'rounds/parent.json',{}).outcome,'committed')
        self.assertFalse((self.root/'rounds/child.json').exists())

    def test_executable_client_does_not_inherit_lock(self):
        token=self.store.acquire(self.lineage)
        child=subprocess.Popen([sys.executable,'-u','-c',"import sys;print('ready',flush=True);sys.stdin.read()"],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,stdin=subprocess.PIPE,close_fds=False)
        def cleanup():
            if child.poll() is None:child.kill()
            child.communicate(timeout=5)
        self.addCleanup(cleanup);self.ready(child)
        self.store.release(token)
        with self.open_store().locked(self.lineage):pass
        self.assertIsNone(child.poll())

    def test_immutable_replay_is_exact_and_conflict_preserves_bytes(self):
        with self.store.locked(self.lineage) as token:
            original=self.store.publish(token,'rounds/item.json',{'value':1})
            self.assertEqual(original,self.store.publish(token,'rounds/item.json',{'value':1}))
            with self.assertRaises(storage.StorageWriteError) as error:
                self.store.publish(token,'rounds/item.json',{'value':2})
            self.assertEqual(error.exception.result.outcome,'not_committed')
            self.assertEqual(self.store.read('rounds/item.json'),b'{"value":1}')

    def test_paths_and_symlink_parents_cannot_escape(self):
        with self.store.locked(self.lineage) as token:
            for path in ['../escape','/escape','rounds//bad','rounds/./bad','rounds\\bad','rounds/.vnext-tmp-owned']:
                with self.subTest(path=path),self.assertRaises(storage.StorageWriteError):self.store.publish(token,path,b'x')
            (self.root/'rounds/link').symlink_to(self.base,target_is_directory=True)
            with self.assertRaises(storage.StorageWriteError):self.store.publish(token,'rounds/link/escape',b'x')
            target=self.base/'external';target.write_bytes(b'outside')
            (self.root/'rounds/artifact').symlink_to(target)
            with self.assertRaises(storage.StorageWriteError):self.store.publish(token,'rounds/artifact',b'outside')
            self.assertEqual(target.read_bytes(),b'outside')
            self.assertFalse((self.base/'escape').exists())

    def test_nonregular_artifact_read_refuses_without_waiting_for_a_pipe_writer(self):
        os.mkfifo(self.root/'rounds/pipe')
        with self.assertRaisesRegex(ValueError,'regular file'):self.store.read('rounds/pipe')

    def test_short_writes_are_completed(self):
        original=os.write
        with self.store.locked(self.lineage) as token,patch.object(storage.os,'write',side_effect=lambda fd,raw:original(fd,raw[:3])):
            self.store.publish(token,'rounds/short',b'abcdefghijk')
        self.assertEqual(self.store.read('rounds/short'),b'abcdefghijk')

    def test_failure_before_publication_is_known_uncommitted(self):
        with self.store.locked(self.lineage) as token:
            with patch.object(storage,'_full_flush',side_effect=OSError('flush failed')):
                with self.assertRaises(storage.StorageWriteError) as error:self.store.publish(token,'rounds/failed',b'x')
            self.assertEqual(error.exception.result.outcome,'not_committed')
            self.assertFalse((self.root/'rounds/failed').exists())
            self.store.publish(token,'rounds/after',b'x')

    def test_link_acknowledgement_failure_poisoned_token_and_retains_evidence(self):
        token=self.store.acquire(self.lineage);original=os.link
        def fail(*args,**kwargs):original(*args,**kwargs);raise OSError('lost link acknowledgement')
        with patch.object(storage.os,'link',side_effect=fail):
            with self.assertRaises(storage.StorageWriteError) as error:self.store.publish(token,'rounds/uncertain',b'x')
        self.assertEqual(error.exception.result.outcome,'outcome_requires_reconciliation')
        self.assertEqual((self.root/'rounds/uncertain').read_bytes(),b'x')
        with self.assertRaises(storage.OwnershipLost):self.store.publish(token,'rounds/no',b'x')
        with self.store.locked(lambda read:self.assertEqual(read('rounds/uncertain'),b'x')) as new:
            self.store.publish(new,'rounds/uncertain',b'x')

    def test_post_publication_directory_failure_requires_reconciliation(self):
        token=self.store.acquire(self.lineage);original=os.fsync
        def fail(fd):
            if (self.root/'rounds/uncertain').exists():raise OSError('directory barrier failed')
            return original(fd)
        with patch.object(storage.os,'fsync',side_effect=fail):
            with self.assertRaises(storage.StorageWriteError) as error:self.store.publish(token,'rounds/uncertain',b'x')
        self.assertEqual(error.exception.result.outcome,'outcome_requires_reconciliation')
        self.assertIsNone(self.store._lock_fd)

    def test_pointer_is_conditional_and_requires_exact_snapshot(self):
        with self.store.locked(self.lineage) as token:
            old=self.commit(token,0,None);ref,new=self.snapshot(token,1)
            with self.assertRaisesRegex(ValueError,'expected bytes'):
                self.store.replace_pointer(token,POINTER,expected=None,snapshot=ref,validate_transition=self.transition)
            self.assertEqual(self.store.read(POINTER),old)
            bad=dict(ref);bad['hash']='0'*64
            with self.assertRaisesRegex(ValueError,'snapshot hash'):
                self.store.replace_pointer(token,POINTER,expected=old,snapshot=bad,validate_transition=self.transition)
            self.store.replace_pointer(token,POINTER,expected=old,snapshot=ref,validate_transition=self.transition)
            self.assertEqual(self.store.read(POINTER),new)

    def test_transition_validator_cannot_publish_over_a_changed_expected_pointer(self):
        with self.store.locked(self.lineage) as token:
            old=self.commit(token,0,None);ref,new=self.snapshot(token,1)
            def changed(before,after):
                self.store.replace_pointer(token,POINTER,expected=old,snapshot=ref,validate_transition=self.transition)
            with self.assertRaisesRegex(ValueError,'changed during transition'):
                self.store.replace_pointer(token,POINTER,expected=old,snapshot=ref,validate_transition=changed)
            self.assertEqual(self.store.read(POINTER),new)

    def test_rename_acknowledgement_failure_and_interrupt_are_uncertain(self):
        token=self.store.acquire(self.lineage);old=self.commit(token,0,None)
        for ordinal,failure in [(1,OSError('rename acknowledgement')),(2,KeyboardInterrupt())]:
            if ordinal==2:token=self.store.acquire(lambda read:self.assertEqual(read(POINTER),old))
            ref,new=self.snapshot(token,ordinal);original=os.replace
            def fail(*args,**kwargs):original(*args,**kwargs);raise failure
            with patch.object(storage.os,'replace',side_effect=fail):
                with self.assertRaises(storage.StorageWriteError) as error:
                    self.store.replace_pointer(token,POINTER,expected=old,snapshot=ref,validate_transition=self.transition)
            self.assertEqual(error.exception.result.outcome,'outcome_requires_reconciliation')
            self.assertIsNone(self.store._lock_fd);self.assertEqual(self.store.read(POINTER),new)
            old=new

    def test_post_rename_full_flush_failure_does_not_roll_back(self):
        token=self.store.acquire(self.lineage);old=self.commit(token,0,None);ref,new=self.snapshot(token,1)
        original=storage._full_flush;calls=0
        def fail(fd):
            nonlocal calls
            calls+=1
            if calls==2:raise OSError('drive flush failed')
            return original(fd)
        with patch.object(storage,'_full_flush',side_effect=fail):
            with self.assertRaises(storage.StorageWriteError) as error:
                self.store.replace_pointer(token,POINTER,expected=old,snapshot=ref,validate_transition=self.transition)
        self.assertEqual(error.exception.result.outcome,'outcome_requires_reconciliation')
        self.assertEqual(self.store.read(POINTER),new)
        with self.assertRaises(storage.OwnershipLost):self.store.publish(token,'rounds/no',b'x')

    def test_process_death_before_and_after_pointer_rename_requires_actual_readback(self):
        with self.store.locked(self.lineage) as token:old=self.commit(token,0,None)
        for point in ['before','after']:
            with self.subTest(point=point):
                child=self.process('''from whetstone import vnext_local_storage as kernel
from whetstone.vnext_contracts import canonical_json_bytes,sha256_bytes
store=LocalAuthorityStore(root,job_id=job)
token=store.acquire(lambda read:read('rounds/seed.md'))
old=store.read('rounds/current.json')
raw=canonical_json_bytes({'ordinal':1,'body':'x'*65536})
result=store.publish(token,'rounds/history/1.json',raw)
def pause():
 print('ready',flush=True)
 sys.stdin.read()
''' + ('''original=kernel._full_flush
def interrupt(fd):
 original(fd)
 pause()
kernel._full_flush=interrupt
''' if point=='before' else '''original=kernel.os.replace
def interrupt(*args,**kwargs):
 original(*args,**kwargs)
 pause()
kernel.os.replace=interrupt
''') + '''store.replace_pointer(token,'rounds/current.json',expected=old,
 snapshot={'path':result.path,'hash':result.hash},validate_transition=lambda old,new:None)
''')
                self.ready(child);child.kill();child.wait(timeout=5)
                expected=old if point=='before' else (self.root/'rounds/history/1.json').read_bytes()
                visited=[]
                def readback(read):
                    actual=read(POINTER);self.assertEqual(actual,expected);visited.append(actual)
                    self.assertEqual(read(f"rounds/history/{json.loads(actual)['ordinal']}.json"),actual)
                with self.store.locked(readback):pass
                self.assertEqual(visited,[expected])
                self.assertTrue(list((self.root/'rounds').glob('.vnext-tmp-*')))

    def test_read_only_inspection_does_not_repair_or_change_bytes(self):
        with self.store.locked(self.lineage) as token:self.commit(token,0,None)
        orphan=self.root/'rounds/.vnext-tmp-abandoned';orphan.write_bytes(b'partial')
        def inventory():return {str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        before=inventory()
        with storage.LocalAuthorityStore(self.root,job_id=JOB) as reader:reader.read(POINTER)
        self.assertEqual(inventory(),before)

    def test_release_serializes_with_publication(self):
        token=self.store.acquire(self.lineage);entered=threading.Event();proceed=threading.Event();released=threading.Event();errors=[]
        original=storage._full_flush
        def wait_flush(fd):
            entered.set()
            if not proceed.wait(5):raise TimeoutError('test release gate')
            return original(fd)
        def writer():
            try:self.store.publish(token,'rounds/thread',b'x')
            except BaseException as exc:errors.append(exc)
        def release():
            try:self.store.release(token);released.set()
            except BaseException as exc:errors.append(exc)
        with patch.object(storage,'_full_flush',side_effect=wait_flush):
            writing=threading.Thread(target=writer);writing.start()
            try:
                self.assertTrue(entered.wait(5));releasing=threading.Thread(target=release);releasing.start()
                self.assertFalse(released.wait(.05))
            finally:
                proceed.set();writing.join(5)
                if 'releasing' in locals():releasing.join(5)
        self.assertFalse(writing.is_alive());self.assertTrue(released.is_set());self.assertEqual(errors,[])
        self.assertEqual(self.store.read('rounds/thread'),b'x')

    def test_readers_see_complete_pointer_bytes(self):
        token=self.store.acquire(self.lineage);old=self.commit(token,0,None)
        allowed={sha256_bytes(old)};stop=threading.Event();observed=[];errors=[];started=threading.Event()
        def reader():
            while not stop.is_set():
                try:observed.append(sha256_bytes((self.root/POINTER).read_bytes()));started.set()
                except BaseException as exc:errors.append(exc);break
        thread=threading.Thread(target=reader);thread.start()
        try:
            self.assertTrue(started.wait(5))
            for ordinal in range(1,9):
                old=self.commit(token,ordinal,old);allowed.add(sha256_bytes(old))
        finally:stop.set();thread.join(5)
        self.assertFalse(thread.is_alive());self.assertEqual(errors,[]);self.assertTrue(observed)
        self.assertTrue(set(observed)<=allowed)


if __name__=='__main__':unittest.main()

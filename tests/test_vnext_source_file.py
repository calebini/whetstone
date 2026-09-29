"""External-source primitive faults under a real D8 fence (no power-loss claim)."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import test_vnext_local_storage as storage_tests
from whetstone import vnext_source_file as source_module
from whetstone.vnext_source_file import SourceFile
from whetstone.vnext_local_storage import OwnershipLost, StorageBusy, StorageWriteError


@unittest.skipUnless(sys.platform=='darwin','D8 requires macOS/APFS')
class SourceFileTests(unittest.TestCase):
    open_store = storage_tests.LocalStorageTests.open_store
    lineage = storage_tests.LocalStorageTests.lineage

    def setUp(self):
        storage_tests.LocalStorageTests.setUp(self)
        self.path=self.base/'source.md';self.path.write_bytes(b'original\r\n')
        self.after=b'verified\n'

    def prepared(self,source,token):
        before=source.observe();name='.whetstone-apply-test'
        identity=source.prepare(token,name,self.after,before[1]['metadata'])
        return dict(name=name,identity=identity,raw=self.after,before=before,guard=lambda:None)

    def test_exact_atomic_replacement_preserves_permissions_and_provenance(self):
        self.path.chmod(0o640)
        with SourceFile(self.store,str(self.path)) as source,self.store.locked(self.lineage) as token:
            data=self.prepared(source,token);source.replace(token,**data)
            raw,seen=source.observe()
            self.assertEqual(raw,self.after);self.assertEqual(seen['file_identity'],data['identity'])
            self.assertEqual(seen['metadata'],data['before'][1]['metadata'])
        self.assertFalse((self.base/data['name']).exists())

    def test_busy_owner_and_stale_token_cannot_stage_or_replace(self):
        other=self.open_store()
        with SourceFile(self.store,str(self.path)) as source:
            token=self.store.acquire(self.lineage);data=self.prepared(source,token)
            with self.assertRaises(StorageBusy):other.acquire(self.lineage)
            self.store.release(token)
            with self.assertRaises(OwnershipLost):source.replace(token,**data)
        self.assertEqual(self.path.read_bytes(),b'original\r\n')

    def test_changed_source_and_staging_bytes_refuse_before_replacement(self):
        with SourceFile(self.store,str(self.path)) as source,self.store.locked(self.lineage) as token:
            data=self.prepared(source,token)
            (self.base/data['name']).write_bytes(b'forged')
            with self.assertRaisesRegex(ValueError,'staging evidence'):source.replace(token,**data)
            (self.base/data['name']).write_bytes(self.after)
            self.path.write_bytes(b'external edit')
            with self.assertRaisesRegex(ValueError,'source changed'):source.replace(token,**data)
        self.assertEqual(self.path.read_bytes(),b'external edit')

    def test_symlinks_multilinks_relative_and_in_root_targets_refuse(self):
        link=self.base/'link.md';link.symlink_to(self.path)
        for path in (str(link),str(self.root/'rounds/seed.md'),'relative.md'):
            with self.subTest(path=path),self.assertRaises((ValueError,OSError)):
                with SourceFile(self.store,path) as source:source.observe()
        hard=self.base/'hard.md';os.link(self.path,hard)
        with SourceFile(self.store,str(self.path)) as source:
            with self.assertRaisesRegex(ValueError,'single-link'):source.observe()

    def test_parent_identity_or_filesystem_change_refuses(self):
        parent=self.base/'external';parent.mkdir();target=parent/'source';target.write_bytes(b'original')
        with SourceFile(self.store,str(target)) as source:
            before=source.observe();parent.rename(self.base/'old');parent.mkdir();(parent/'source').write_bytes(b'original')
            with self.assertRaisesRegex(ValueError,'parent identity'):source.observe()
        with patch.object(source_module,'_filesystem',return_value={'type':'nfs','fsid':[1,2]}):
            with self.assertRaisesRegex(ValueError,'qualified local'):SourceFile(self.store,str(self.path))

    def test_metadata_and_preparation_flush_failures_do_not_replace_source(self):
        with SourceFile(self.store,str(self.path)) as source,self.store.locked(self.lineage) as token:
            with patch.object(source_module,'_empty_acl',return_value=False):
                with self.assertRaisesRegex(ValueError,'unsupported metadata'):source.observe()
            before=source.observe()
            with patch.object(source_module,'_full_flush',side_effect=OSError('stage flush failed')):
                with self.assertRaisesRegex(OSError,'stage flush'):source.prepare(token,'.whetstone-apply-failed',self.after,before[1]['metadata'])
        self.assertEqual(self.path.read_bytes(),b'original\r\n')
        self.assertTrue((self.base/'.whetstone-apply-failed').exists())

    def test_rename_acknowledgement_and_postrename_barrier_are_uncertain(self):
        for failure in ('ack','file_flush','directory_flush'):
            with self.subTest(failure=failure):
                self.path.write_bytes(b'original\r\n')
                with SourceFile(self.store,str(self.path)) as source:
                    token=self.store.acquire(self.lineage);data=self.prepared(source,token)
                    replace=os.replace
                    def lose(*args,**kwargs):
                        replace(*args,**kwargs)
                        if failure=='ack':raise OSError('lost rename ack')
                    if failure=='file_flush':
                        original=source.synchronize
                        def fail(*args,**kwargs):
                            with patch.object(source_module,'_full_flush',side_effect=OSError('postrename file flush')):return original(*args,**kwargs)
                        context=patch.object(source,'synchronize',side_effect=fail)
                    elif failure=='directory_flush':
                        original=source.synchronize;fsync=os.fsync
                        def fail_directory(fd):
                            if fd==source.parent:raise OSError('postrename directory flush')
                            return fsync(fd)
                        def fail(*args,**kwargs):
                            with patch.object(source_module.os,'fsync',side_effect=fail_directory):return original(*args,**kwargs)
                        context=patch.object(source,'synchronize',side_effect=fail)
                    else:context=patch.object(source_module.os,'replace',side_effect=lose)
                    with context,self.assertRaises(StorageWriteError) as raised:source.replace(token,**data)
                    self.assertEqual(raised.exception.result.outcome,'outcome_requires_reconciliation')
                    self.assertIsNone(self.store._token)
                    self.assertEqual(self.path.read_bytes(),self.after)

    def test_failure_before_replace_keeps_old_source_and_does_not_claim_commit(self):
        with SourceFile(self.store,str(self.path)) as source,self.store.locked(self.lineage) as token:
            data=self.prepared(source,token)
            def refuse():raise ValueError('fresh authority refused')
            data['guard']=refuse
            with patch.object(source_module.os,'replace',side_effect=AssertionError('must not replace')):
                with self.assertRaisesRegex(ValueError,'fresh authority refused'):source.replace(token,**data)
            self.assertIs(self.store._token,token)
        self.assertEqual(self.path.read_bytes(),b'original\r\n')

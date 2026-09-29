"""Internal M4 journeys with genuine convergence and disposable bound sources."""
from copy import deepcopy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone import vnext_apply_back as module
from whetstone.vnext_local_storage import StorageWriteError
import test_vnext_verified_phase2_closeout as closeout
import test_vnext_verified_review as runtime
import test_vnext_verified_semantics as semantic


class Fixture:
    setUpClass = closeout.Phase2CloseoutTests.setUpClass
    start = closeout.Phase2CloseoutTests.start
    files = closeout.Phase2CloseoutTests.files
    reopen = closeout.Phase2CloseoutTests.reopen
    ready = closeout.Phase2CloseoutTests.ready
    review = closeout.Phase2CloseoutTests.review
    promote = closeout.Phase2CloseoutTests.promote
    config = closeout.Phase2CloseoutTests.config
    next_client = closeout.Phase2CloseoutTests.next_client
    advance = closeout.Phase2CloseoutTests.advance
    clean_start = closeout.Phase2CloseoutTests.clean_start
    final_ready = closeout.Phase2CloseoutTests.final_ready

    def fixture(self, **options):
        temp = TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.source = Path(temp.name).resolve()/'source.md'
        original = runtime.unit.UnitPreflightTests.setUp
        def setup(owner):
            original(owner)
            f = owner.c.f
            if getattr(self,'versioned',False):
                f.base = f.base.replace(b'# Queue\n',b'# Queue 0.17\nStatus: Accepted v0.17\n')
            raw = f.base if getattr(self,'unchanged',False) else f.base.replace(b'\n',b'\r\n')
            self.source.write_bytes(raw)
            f.job['source_spec'] = dict(path=str(self.source),expected_hash=sha256_bytes(raw))
            f.rebind()
        original_suite = semantic.consuming_suite
        def suite(*args,**kwargs):
            if not getattr(self,'unpinned',False):
                kwargs['additional_algorithms'] = (*kwargs.get('additional_algorithms',()),'vnext_apply_back_v1')
                kwargs['additional_schemas'] = set(kwargs.get('additional_schemas',())) | set(module.SCHEMAS)
            if getattr(self,'versioned',False):
                kwargs['additional_algorithms'] = (*kwargs['additional_algorithms'],'vnext_version_operations_v1','vnext_version_entry_v1')
                kwargs['additional_schemas'] |= {'mutation_plan_v4','vnext_version_operation_v1','vnext_version_admission_v1','vnext_phase2_entry_v2','vnext_system_entry_request_v1'}
                kwargs['algorithm_overrides'] = {**kwargs.get('algorithm_overrides',{}),'assembler_version':'patch-assembler-v3'}
            return original_suite(*args,**kwargs)
        with patch.object(runtime.unit.UnitPreflightTests,'setUp',setup),patch.object(semantic,'consuming_suite',side_effect=suite):
            return runtime.VerifiedReviewTests.fixture(self,**options)

    def converged(self):
        f,reviewer,client,_ = self.final_ready()
        self.advance(f,client);f.run.finish_phase2();f.run.reconcile_phase2_state()
        return f,reviewer,client

    def approval(self,f):
        before = self.files(f);source = self.source.read_bytes()
        with patch.object(f.store,'locked',side_effect=AssertionError('read-only review took fence')):
            result = f.run.review_apply_back()
        self.assertTrue(result['eligible'],result)
        self.assertFalse(result['apply_back_permitted'])
        self.assertEqual(self.files(f),before);self.assertEqual(self.source.read_bytes(),source)
        return result['assessment']

    def apply(self,f,packet,**options):
        return f.run.apply_back(assessment=packet,approve=True,exclusive_source_access=True,**options)


@unittest.skipUnless(sys.platform=='darwin','D8 requires macOS/APFS')
class ApplyBackTests(Fixture,unittest.TestCase):
    def test_converged_seed_exact_apply_reopen_and_later_source_drift(self):
        f,reviewer,client = self.converged();packet = self.approval(f)
        authority = f.store.read('rounds/current_verified.json');declaration = f.store.read('convergence_declaration.md')
        self.assertTrue(packet['changed']);self.assertIn(b'\r\n',self.source.read_bytes())
        with patch('whetstone.apply_back.apply_back',side_effect=AssertionError('legacy executor')):
            result = self.apply(f,packet)
        self.assertEqual(result['outcome'],'completed');self.assertTrue(result['applied'])
        self.assertEqual(self.source.read_bytes(),f.store.read('spec.md'))
        self.assertEqual(self.source.stat().st_mode & 0o777,packet['source']['metadata']['mode'])
        inode = self.source.stat().st_ino;self.reopen(f)
        self.assertEqual(self.apply(f,packet)['outcome'],'completed')
        self.assertEqual(f.run.recover_apply_back(exclusive_source_access=True)['outcome'],'completed')
        self.assertEqual(self.source.stat().st_ino,inode)
        self.source.write_bytes(b'# External edit\n')
        state = f.run.apply_back_status()
        self.assertTrue(state['historical_completion']);self.assertFalse(state['source_matches_result'])
        self.assertEqual(state['outcome'],'source_drift')
        self.assertEqual(self.apply(f,packet)['outcome'],'source_drift')
        self.assertEqual(self.source.read_bytes(),b'# External edit\n')
        self.assertEqual(f.store.read('rounds/current_verified.json'),authority)
        self.assertEqual(f.store.read('convergence_declaration.md'),declaration)
        self.assertEqual((reviewer.calls,client.calls,f.editor.calls),(1,2,0))

    def test_registered_unverified_and_rejected_candidates_never_grant_apply_back(self):
        from whetstone.vnext_semantic_admission import load_registered_semantic_context
        from vnext_fixtures import STAMP
        f,reviewer=self.start(phase2_closeout_contract=True)
        self.review(f,reviewer);f.run.request(round_number=1,client=f.editor)
        creation=f.run.register(round_number=1,created_at=STAMP).value
        before=self.files(f);source=self.source.read_bytes()
        self.assertFalse(f.run.review_apply_back()['eligible'])
        self.assertEqual(self.files(f),before)
        context=load_registered_semantic_context(f.store,admission=f.run._history(),candidate_id=creation['candidate_id'])
        verifier=runtime.history.verified.semantic.Client(context)
        response=json.loads(verifier.valid);response.update(verdict='reject',unrelated_semantic_change='detected')
        verifier.responses=[canonical_json_bytes(response)]
        self.assertEqual(f.run.verify(client=verifier,decided_at=STAMP).value.decision['candidate_disposition'],'CANDIDATE_REJECTED')
        before=self.files(f)
        self.assertFalse(f.run.review_apply_back()['eligible'])
        self.assertEqual(self.files(f),before);self.assertEqual(self.source.read_bytes(),source)
        self.assertFalse((f.root/module.INTENT).exists())

    def test_noop_never_replaces_and_approval_cannot_be_implicitly_supplied(self):
        self.unchanged = True
        f,_,_ = self.converged();packet = self.approval(f)
        self.assertFalse(packet['changed']);inode = self.source.stat().st_ino
        before = self.files(f)
        for options in ({},{'approve':True},{'exclusive_source_access':True}):
            with self.assertRaisesRegex(ValueError,'explicit approval'):
                f.run.apply_back(assessment=packet,**options)
        self.assertEqual(self.files(f),before)
        with patch.object(module.SourceFile,'replace',side_effect=AssertionError('no-op replaced')):
            result = self.apply(f,packet)
        self.assertEqual(result['outcome'],'completed');self.assertFalse(result['applied'])
        self.assertEqual(self.source.stat().st_ino,inode)
        self.assertFalse((f.root/module.PREPARED).exists())

    def test_unpinned_and_unfinished_runs_cannot_review_or_write(self):
        self.unpinned = True
        f,_ = self.start(phase2_closeout_contract=True)
        before=self.files(f)
        self.assertIn('contract is absent',f.run.review_apply_back()['blockers'][0])
        self.assertEqual(self.files(f),before)
        self.unpinned=False
        f,_=self.start(phase2_closeout_contract=True);before=self.files(f)
        self.assertFalse(f.run.review_apply_back()['eligible'])
        self.assertEqual(self.files(f),before)

    def test_stale_source_approval_and_corrupt_lineage_refuse_before_intent(self):
        f,_,_=self.converged();packet=self.approval(f);before=self.files(f)
        for field in ('verified_map','current_verified_pointer','closeout'):
            tampered=deepcopy(packet);tampered[field]['hash']='0'*64
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'approval is stale'):self.apply(f,tampered)
        self.source.write_bytes(b'# Drift\n')
        with self.assertRaisesRegex(ValueError,'source hash mismatch'):self.apply(f,packet)
        self.assertFalse(f.run.review_apply_back()['eligible'])
        self.assertEqual(self.files(f),before)
        source=f.store.read('spec.md');(f.root/'spec.md').write_bytes(b'# Unverified\n')
        self.assertFalse(f.run.review_apply_back()['eligible'])
        (f.root/'spec.md').write_bytes(source)
        map_path=f.root/packet['verified_map']['path'];map_bytes=map_path.read_bytes();map_path.write_bytes(b'{}')
        self.assertFalse(f.run.review_apply_back()['eligible']);map_path.write_bytes(map_bytes)
        self.assertEqual(self.files(f),before)

    def test_precommit_and_lost_receipt_recovery_never_rewrite_automatically(self):
        f,reviewer,client=self.converged();packet=self.approval(f);original=self.source.read_bytes()
        publish=f.store.publish
        def lose_preimage(token,path,value):
            result=publish(token,path,value)
            if path==module.PREIMAGE:raise OSError('lost preimage acknowledgement')
            return result
        with patch.object(f.store,'publish',side_effect=lose_preimage):
            with self.assertRaisesRegex(OSError,'lost preimage'):self.apply(f,packet)
        self.assertEqual(f.run.apply_back_status()['outcome'],'not_started')
        self.assertEqual(self.source.read_bytes(),original)
        publish=f.store.publish
        def lose_intent(token,path,value):
            result=publish(token,path,value)
            if path==module.INTENT:raise OSError('lost intent acknowledgement')
            return result
        with patch.object(f.store,'publish',side_effect=lose_intent):
            with self.assertRaisesRegex(OSError,'lost intent'):self.apply(f,packet)
        self.reopen(f)
        with patch.object(module.SourceFile,'replace',side_effect=AssertionError('recovery wrote source')):
            self.assertEqual(f.run.recover_apply_back(exclusive_source_access=True)['outcome'],'apply_required')
            self.assertEqual(self.apply(f,packet)['outcome'],'apply_required')
        self.assertEqual(self.source.read_bytes(),original)
        publish=f.store.publish
        def lose_prepared(token,path,value):
            result=publish(token,path,value)
            if path==module.PREPARED:raise OSError('lost preparation acknowledgement')
            return result
        with patch.object(f.store,'publish',side_effect=lose_prepared):
            with self.assertRaisesRegex(OSError,'lost preparation'):self.apply(f,packet,retry=True)
        self.assertEqual(self.source.read_bytes(),original)
        self.assertEqual(f.run.recover_apply_back(exclusive_source_access=True)['outcome'],'apply_required')
        publish=f.store.publish
        def lose_receipt(token,path,value):
            if path==module.RECEIPT:raise OSError('receipt not published')
            return publish(token,path,value)
        with patch.object(f.store,'publish',side_effect=lose_receipt):
            with self.assertRaises(StorageWriteError):self.apply(f,packet,retry=True)
        inode=self.source.stat().st_ino;self.assertIsNone(f.store._token);self.reopen(f)
        self.assertEqual(f.run.apply_back_status()['outcome'],'receipt_recovery_required')
        publish=f.store.publish
        def lose_receipt_ack(token,path,value):
            result=publish(token,path,value)
            if path==module.RECEIPT:raise OSError('lost receipt acknowledgement')
            return result
        with patch.object(f.store,'publish',side_effect=lose_receipt_ack):
            with self.assertRaises(StorageWriteError):f.run.recover_apply_back(exclusive_source_access=True)
        self.reopen(f)
        with patch.object(module.SourceFile,'replace',side_effect=AssertionError('recovery wrote source')):
            self.assertEqual(f.run.recover_apply_back(exclusive_source_access=True)['outcome'],'completed')
        self.assertEqual(self.source.stat().st_ino,inode)
        self.assertEqual((reviewer.calls,client.calls,f.editor.calls),(1,2,0))


class ApprovalIdentityTests(unittest.TestCase):
    def test_identity_binds_values_and_survives_canonical_key_order(self):
        packet={'source':{'expected_hash':'a'*64},'verified_draft':{'hash':'b'*64}}
        identity=module.make_intent(packet)['request_id']
        self.assertEqual(identity,module.make_intent(json.loads(canonical_json_bytes(packet)))['request_id'])
        packet['verified_draft']['hash']='c'*64
        self.assertNotEqual(identity,module.make_intent(packet)['request_id'])


@unittest.skipUnless(sys.platform=='darwin','D8 requires macOS/APFS')
class ApplyBackProcessTests(Fixture,unittest.TestCase):
    def test_process_death_before_and_after_replace_recovers_without_second_write(self):
        import subprocess
        f,reviewer,client=self.converged();packet=self.approval(f)
        original=self.source.read_bytes();approval=self.source.parent/'approval.json';approval.write_bytes(canonical_json_bytes(packet))
        script='''import json,os,sys
from pathlib import Path
from unittest.mock import patch
from whetstone import vnext_registry
from whetstone.vnext_contracts import ALGORITHM_VERSIONS
from whetstone.vnext_verified_run import open_verified_run
from whetstone import vnext_source_file
root,suite_path,approval,stage=sys.argv[1:]
manifest=json.loads(Path(suite_path).read_bytes());job=json.loads((Path(root)/'job_descriptor.json').read_bytes())
vnext_registry.SUPPORTED_SUITES[manifest['suite_version']]=manifest['suite_digest']
vnext_registry.SUITE_ALGORITHM_VERSIONS[manifest['suite_version']]={k:job[k] for k in ALGORITHM_VERSIONS}
replace=os.replace
source=json.loads(Path(approval).read_bytes())['source']['path']
def interrupt(src,dst,**kwargs):
    if dst==Path(source).name:
        if stage=='before':os._exit(74)
        replace(src,dst,**kwargs);os._exit(75)
    return replace(src,dst,**kwargs)
with open_verified_run(root,suite_path=suite_path) as run:
    with patch.object(vnext_source_file.os,'replace',side_effect=interrupt):
        run.apply_back(assessment=json.loads(Path(approval).read_bytes()),approve=True,exclusive_source_access=True,retry=stage=='after')
'''
        f.store.close()
        child=subprocess.run([sys.executable,'-c',script,str(f.root),str(f.admission.suite_path),str(approval),'before'],capture_output=True,timeout=180)
        self.assertEqual(child.returncode,74,child.stderr.decode())
        self.reopen(f)
        self.assertEqual(self.source.read_bytes(),original)
        self.assertEqual(f.run.recover_apply_back(exclusive_source_access=True)['outcome'],'apply_required')
        f.store.close()
        child=subprocess.run([sys.executable,'-c',script,str(f.root),str(f.admission.suite_path),str(approval),'after'],capture_output=True,timeout=180)
        self.assertEqual(child.returncode,75,child.stderr.decode())
        self.reopen(f);inode=self.source.stat().st_ino
        self.assertEqual(self.source.read_bytes(),f.store.read('spec.md'))
        with patch.object(module.SourceFile,'replace',side_effect=AssertionError('recovery repeated write')):
            self.assertEqual(f.run.recover_apply_back(exclusive_source_access=True)['outcome'],'completed')
        self.assertEqual(self.source.stat().st_ino,inode)
        self.assertEqual((reviewer.calls,client.calls,f.editor.calls),(1,2,0))

    def test_uncertain_third_bytes_and_missing_source_require_attention(self):
        f,_,_=self.converged();packet=self.approval(f)
        with patch.object(module.SourceFile,'replace',side_effect=OSError('stop before replacement')):
            with self.assertRaisesRegex(OSError,'stop before replacement'):self.apply(f,packet)
        self.source.write_bytes(b'# Independent source edit\n')
        with patch.object(module.SourceFile,'replace',side_effect=AssertionError('recovery wrote')):
            self.assertEqual(f.run.recover_apply_back(exclusive_source_access=True)['outcome'],'operator_attention_required')
        self.assertEqual(self.source.read_bytes(),b'# Independent source edit\n')
        self.source.unlink()
        self.assertEqual(f.run.recover_apply_back(exclusive_source_access=True)['outcome'],'operator_attention_required')


@unittest.skipUnless(sys.platform=='darwin','D8 requires macOS/APFS')
class ApplyBackVersionTests(Fixture,unittest.TestCase):
    import test_vnext_verified_versions as versions
    start=runtime.VerifiedReviewTests.start
    ready=versions.VersionPhase2Tests.ready
    config=versions.VersionPhase2Tests.config
    advance=versions.VersionPhase2Tests.advance
    response=versions.VersionPhase2Tests.response

    def test_promoted_version_convergence_apply_preserves_history_and_closeout(self):
        self.versioned=True
        f,client,_=self.ready();client.callback=self.response(gaps=False)
        f.run.run_phase2_review(client=client);f.run.consume_phase2_result();self.advance(f,client)
        f.run.prepare_phase2_declaration();self.advance(f,client);f.run.reconcile_phase2_findings()
        f.run.finish_phase2();f.run.reconcile_phase2_state()
        history=f.store.read('spec.history.md');head=f.store.read('rounds/current_verified.json')
        self.assertEqual(json.loads(head)['promotion_ordinal'],1)
        self.assertIn(b'# Queue 1.0',f.store.read('spec.md'))
        packet=self.approval(f)
        result=self.apply(f,packet)
        self.assertEqual(result['outcome'],'completed')
        self.assertEqual(self.source.read_bytes(),f.store.read('spec.md'))
        self.assertEqual(f.store.read('spec.history.md'),history)
        self.assertEqual(f.store.read('rounds/current_verified.json'),head)
        close=json.loads(f.store.read(packet['closeout']['path']))
        self.assertFalse(close['apply_back_permitted'])
        self.assertEqual((client.calls,f.editor.calls),(3,0))

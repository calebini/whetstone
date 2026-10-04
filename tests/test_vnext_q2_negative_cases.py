"""Joined Q2 P0 negative transactions and positive simplification; scripted clients."""
import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_verified_history import VerifiedHistoryAdmission
from whetstone.vnext_verified_work import VerifiedWork
from whetstone.vnext_semantic_admission import load_registered_semantic_context
from vnext_fixtures import STAMP
from vnext_q2_fixtures import Editor, fixture
import test_vnext_verified_work as work
import test_vnext_semantic_requests as semantic


@unittest.skipUnless(sys.platform=='darwin','D8 qualification requires local macOS/APFS')
class NegativeCases(unittest.TestCase):
    setUpClass=classmethod(lambda cls:work.VerifiedWorkTests.setUpClass())
    owner=work.VerifiedWorkTests.owner
    service=work.VerifiedWorkTests.service

    def candidate(self,f,edits,number=1):
        f.editor=Editor(edits)
        result=f.work.request(round_number=number,client=f.editor)
        self.assertEqual(result.value.status,'complete',result.value)
        f.creation=f.work.register(round_number=number,created_at=STAMP).value
        f.identifier=f.creation['candidate_id']
        directory=f.creation['candidate_path'].rsplit('/',1)[0]
        f.report=json.loads(f.store.read(directory+'/preservation_report.json'))
        return f.report

    def unchanged(self,f):
        self.assertEqual(f.store.read('rounds/current_verified.json'),f.base_pointer)
        self.assertEqual(f.store.read('spec.md'),f.base_mirror)
        self.assertEqual(self.service(f).promote(prepared_at=STAMP).outcome,'not_eligible')
        self.assertFalse((f.root/'rounds/verified_history/current-verified-1.json').exists())

    def rejected(self,f,code):
        class ForbiddenVerifier:
            calls=0
            def verify(self,prompt):
                self.calls+=1;raise AssertionError('deterministic failure invoked Verifier')
        self.assertEqual(f.report['result'],'fail',f.report)
        client=ForbiddenVerifier()
        result=f.work.verify(client=client,decided_at=STAMP)
        self.assertEqual(result.value.decision['candidate_disposition'],'CANDIDATE_REJECTED')
        self.assertIn(code,result.value.decision['rejection_codes'])
        self.assertEqual(client.calls,0);self.assertEqual(f.editor.calls,1)
        self.unchanged(f)

    def test_p0_01_six_replaced_sections_reject_without_advancing_authority(self):
        base=('# Queue\n'+''.join(f'## Section {i}\nQueue MUST retain rule {i}.\n' for i in range(1,7))).encode()
        f=fixture(self,base,[[f'section-{i}' for i in range(1,7)]])
        report=self.candidate(f,[(f'Section {i}','replace_section_body','[UNCHANGED sections]\n',False) for i in range(1,7)])
        self.assertEqual(report['result'],'fail')
        self.assertEqual(len(json.loads(f.editor.prompts[0].splitlines()[-1])['target_sections']),6)
        self.rejected(f,'placeholder_content')

    def test_p0_02_unrelated_enum_and_table_loss_report_exact_removed_ids(self):
        base=b'# Queue\n## Timing\nQueue MUST wait.\n```json\n{"enum":["ready","waiting","done"]}\n```\n\n| State | Action |\n| --- | --- |\n| ready | start |\n| waiting | wait |\n'
        variants=[base.decode().split('## Timing\n')[1].replace('"waiting",',''),
                  base.decode().split('## Timing\n')[1].replace('| waiting | wait |\n','')]
        for kind,content in zip(('schema_enum_member','table_row'),variants):
            with self.subTest(kind=kind):
                f=fixture(self,base,[['timing']],claims=['Clarify when the queue begins waiting.'])
                report=self.candidate(f,[('Timing','replace_section_body',content,False)])
                inputs=json.loads(f.editor.prompts[0].splitlines()[-1])
                expected={u['unit_id'] for u in inputs['base_inventory']['units'] if u['kind']==kind
                    and b'waiting' in base[u['byte_start']:u['byte_end']]}
                self.assertTrue(expected)
                removed={u for failure in report['failures'] if failure['code']=='unauthorized_remove' for u in failure['unit_ids']}
                self.assertTrue(expected<=removed,(expected,report))
                self.rejected(f,'unauthorized_remove')

    def test_p0_03_prospective_target_rejects_compatibility_from_older_context(self):
        assertion=dict(assertion_id='',assertion_type='identifier_absent',target_scope='document',
            matcher=dict(kind='regex',value=r'(?i)\b(legacy|transition|adapter|migration|dual-model)\b'),
            enforcement='deterministic',severity='blocking',rationale='Compatibility behavior is forbidden.',
            source_authority_binding_ids=[])
        base=b'# Queue\n## Timing\nQueue MUST wait.\n'
        for word in ('legacy','transition','adapter','migration','dual-model'):
            with self.subTest(word=word):
                f=fixture(self,base,[['timing']],assertions=[assertion],prospective=True)
                self.candidate(f,[('Timing','replace_section_body',f'Queue MUST wait.\nUse `{word}` behavior for older queues.\n',False)])
                packet=json.loads(f.editor.prompts[0].splitlines()[-1])
                self.assertTrue(any(b['role']=='implementation_context' for b in packet['authority_map']['bindings']))
        self.rejected(f,'blocking_assertion_failed')

    def test_p0_05_three_fixes_with_regression_reject_then_reduced_patch_is_fully_reverified(self):
        base=b'# Queue\n## Alpha\nQueue waits.\n## Beta\nWorkers wait.\n## Gamma\nJobs wait.\n## Reports\nReports include every failure.\n'
        f=fixture(self,base,[['alpha','reports'],['beta'],['gamma']],claims=[
            'Clarify when Queue waits.', 'Clarify when workers wait.', 'Clarify when jobs wait.'])
        fixes=[(name,'replace_section_body',content,False) for name,content in [
            ('Alpha','Queue waits before starting.\n'),('Beta','Workers wait before starting.\n'),
            ('Gamma','Jobs wait before starting.\n')]]
        self.assertEqual(self.candidate(f,fixes+[
            ('Reports','replace_section_body','Reports omit transient failures.\n',False)])['result'],'pass')
        original=f.creation
        original_editor=f.editor
        context=load_registered_semantic_context(f.store,admission=self.owner(f),candidate_id=f.identifier)
        verifier=semantic.Client(context)
        response=json.loads(verifier.valid)
        self.assertEqual(len(response['finding_results']),3)
        self.assertTrue(all(r['disposition']=='resolved' for r in response['finding_results']))
        response.update(unrelated_semantic_change='detected',verdict='reject',
            rationale='Three wording fixes succeed, but the unrelated report guarantee regresses.')
        verifier.responses=[canonical_json_bytes(response)]
        decision=f.work.verify(client=verifier,decided_at=STAMP).value.decision
        self.assertEqual(decision['candidate_disposition'],'CANDIDATE_REJECTED')
        self.unchanged(f)
        parent_dir=original['candidate_path'].rsplit('/',1)[0]
        retained={p.relative_to(f.root).as_posix():p.read_bytes() for p in (f.root/parent_dir).rglob('*') if p.is_file()}

        # A separately admitted round produces a new transaction; the rejected
        # candidate and its immutable proposal are never edited or reopened.
        owner=self.owner(f)
        source=json.loads(f.store.read(owner._refs['rounds'][1]['path']))
        feedback=json.loads(f.store.read(source['feedback']['path']));feedback['round_number']=2
        def ref(path,packet):return dict(path=path,hash=sha256_bytes(canonical_json_bytes(packet)))
        feedback_ref=ref('inputs/q2-feedback-2.json',feedback)
        advice=json.loads(f.store.read(source['advice']['path']));advice['feedback']=feedback_ref
        advice_ref=ref('inputs/q2-advice-2.json',advice)
        record={**source,'round_number':2,'feedback':feedback_ref,'advice':advice_ref}
        record_ref=ref('inputs/q2-round-2.json',record)
        with f.store.locked(owner.validate_authority) as token:
            for reference,packet in [(feedback_ref,feedback),(advice_ref,advice),(record_ref,record)]:
                f.store.publish(token,reference['path'],packet)
        f.admission=VerifiedHistoryAdmission(f.store,suite_path=owner.suite_path,
            descriptor_ref=owner._refs['descriptor'],review_ref=owner._refs['review'],seed_map_ref=owner._refs['seed_map'],
            round_refs={**owner._refs['rounds'],2:record_ref})
        f.work=VerifiedWork(f.store,history=f.admission)
        self.assertEqual(self.candidate(f,fixes,number=2)['result'],'pass')
        self.assertNotEqual(f.creation['transaction_id'],original['transaction_id'])
        self.assertNotEqual(f.identifier,original['candidate_id'])
        self.assertEqual(f.report['base_draft_hash'],decision['base_draft_hash'])
        self.assertEqual(f.report['base_draft_hash'],sha256_bytes(base))
        self.assertIn(b'Reports include every failure.',f.store.read(f.creation['candidate_path']))
        context=load_registered_semantic_context(f.store,admission=self.owner(f),candidate_id=f.identifier)
        second=semantic.Client(context)
        self.assertEqual(len(json.loads(second.valid)['finding_results']),3)
        self.assertTrue(f.work.verify(client=second,decided_at=STAMP).value.decision['promotion_permitted'])
        self.assertEqual(self.service(f).promote(prepared_at=STAMP).outcome,'promoted')
        self.assertEqual((verifier.calls,second.calls),(1,1))
        self.assertEqual((original_editor.calls,f.editor.calls),(1,1))
        self.assertEqual(json.loads(f.store.read('rounds/current_verified.json'))['promotion_ordinal'],1)
        for path,raw in retained.items():self.assertEqual(f.store.read(path),raw)

    def test_s01_valid_simplification_requires_semantic_verification_before_promotion(self):
        f=fixture(self,b'# Queue\n## Timing\nQueue MUST wait.\nQueue MUST report.\n',[['timing']])
        report=self.candidate(f,[('Timing','replace_section_body','Queue MUST wait and report.\n',True)])
        self.assertEqual(report['result'],'pass',report)
        self.unchanged(f)
        context=load_registered_semantic_context(f.store,admission=self.owner(f),candidate_id=f.identifier)
        verifier=semantic.Client(context)
        result=f.work.verify(client=verifier,decided_at=STAMP)
        self.assertTrue(result.value.decision['promotion_permitted'])
        self.assertEqual(self.service(f).promote(prepared_at=STAMP).outcome,'promoted')
        self.assertEqual((f.editor.calls,verifier.calls),(1,1))
        self.assertLess(len(f.store.read('spec.md')),len(f.base_mirror))

"""Non-promoting patch preparation against concrete toy documents."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from whetstone import vnext_identity as ids
from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes, validate_contract_suite
from whetstone.vnext_proposals import prepare_patch, persist_proposal
from whetstone.vnext_sections import section_spans
from vnext_fixtures import ACTOR, Bundle


class ProposalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.suite = validate_contract_suite()

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bundle = Bundle(self.root / 'fixture', self.suite, mode='proposal_only')
        self.base = (self.bundle.root / 'inputs/seed.md').read_bytes()
        self.mapping = deepcopy(self.bundle.base_map)
        self.mapping['sections'][0]['canonical_section_id'] = section_spans(self.base)[0].canonical_id
        self.plan = deepcopy(self.bundle.plan)
        self.client = deepcopy(self.bundle.patch)
        self.client['proposal_id'] = None
        self.client['operations'][0]['operation_id'] = 'local_a'
        self.payload = b'Wait 30 seconds or longer.\n'
        self.payload_root = self.root / 'transport'
        self.payload_root.mkdir()
        (self.payload_root / 'body.md').write_bytes(self.payload)
        self.client['operations'][0]['payload']['path'] = 'body.md'

    def prepare(self, packet=None):
        return prepare_patch(canonical_json_bytes(packet or self.client), payload_root=self.payload_root,
                             plan=self.plan, base=self.base, section_map=self.mapping,
                             editor=ACTOR, suite=self.suite)

    def rebind(self):
        self.plan['transaction_id'] = ids.transaction_id(self.plan, {})
        self.client['transaction_id'] = self.plan['transaction_id']
        self.client['mutation_plan_hash'] = sha256_bytes(canonical_json_bytes(self.plan))

    def test_correction_has_canonical_identity_and_payload_without_authority(self):
        proposal = self.prepare()
        self.assertEqual(proposal.patch['proposal_id'], ids.proposal_id(proposal.patch))
        op = proposal.patch['operations'][0]
        self.assertEqual(op['operation_id'], ids.operation_id(self.plan['transaction_id'], op))
        self.assertEqual(proposal.payloads[op['payload']['path']], self.payload)
        self.assertEqual(proposal.patch['editor'], ACTOR)
        self.assertFalse((self.root / 'rounds').exists())
        # Transport filename and operation label do not enter a dependency-free identity.
        (self.payload_root / 'relocated.md').write_bytes(self.payload)
        self.client['operations'][0]['payload']['path'] = 'relocated.md'
        self.client['operations'][0]['operation_id'] = 'another_label'
        self.assertEqual(self.prepare().digest, proposal.digest)

    def test_canonical_publication_retains_raw_attempt_and_has_no_candidate(self):
        out = self.root / 'result'
        out.mkdir()
        raw = canonical_json_bytes(self.client)
        kwargs = dict(payload_root=self.payload_root, plan=self.plan, base=self.base,
                      section_map=self.mapping, editor=ACTOR, suite=self.suite)
        prepared, ref = persist_proposal(out, 1, 1, raw, **kwargs)
        self.assertEqual((out / ref['path']).read_bytes(), canonical_json_bytes(prepared.patch))
        self.assertEqual((out / 'rounds/round-1/proposals/attempts/proposal-attempt-1.json').read_bytes(), raw)
        self.assertFalse(list(out.rglob('candidate_unverified.md')))
        self.assertFalse((out / 'rounds/current_verified.json').exists())
        before = {p.relative_to(out):p.read_bytes() for p in out.rglob('*') if p.is_file()}
        self.assertEqual(persist_proposal(out, 1, 1, raw, **kwargs)[1], ref)
        self.assertEqual(before, {p.relative_to(out):p.read_bytes() for p in out.rglob('*') if p.is_file()})
        with self.assertRaises(ValueError):
            persist_proposal(out, 1, 1, b'not JSON', **kwargs)

    def test_bad_raw_attempt_is_inspectable_without_canonical_patch(self):
        out = self.root / 'bad'
        out.mkdir()
        with self.assertRaises(ValueError):
            persist_proposal(out, 1, 1, b'# A whole rewritten draft', payload_root=self.payload_root,
                             plan=self.plan, base=self.base, section_map=self.mapping,
                             editor=ACTOR, suite=self.suite)
        self.assertTrue((out / 'rounds/round-1/proposals/attempts/proposal-attempt-1.json').exists())
        self.assertFalse(list(out.rglob('proposed_patch.json')))

    def test_stale_bindings_and_forged_ids_reject(self):
        for field, value in [('job_id','job_'+'f'*64),('transaction_id','txn_'+'f'*64),
                             ('base_draft_hash','f'*64),('mutation_plan_hash','f'*64),
                             ('proposal_id','pro_'+'f'*64)]:
            packet=deepcopy(self.client);packet[field]=value
            with self.subTest(field=field), self.assertRaises(ValueError):self.prepare(packet)
        for field, value in [('expected_target_hash','f'*64),('target_stable_section_id','sec_'+'f'*64),
                             ('addressed_finding_ids',['unadmitted'])]:
            packet=deepcopy(self.client);packet['operations'][0][field]=value
            with self.subTest(field=field), self.assertRaises(ValueError):self.prepare(packet)

    def test_payload_path_confinement_hash_and_utf8(self):
        for value in ['../outside.md','/tmp/outside.md','a/../body.md','./body.md']:
            packet=deepcopy(self.client);packet['operations'][0]['payload']['path']=value
            with self.subTest(path=value),self.assertRaises(ValueError):self.prepare(packet)
        (self.payload_root/'link.md').symlink_to(self.payload_root/'body.md')
        packet=deepcopy(self.client);packet['operations'][0]['payload']['path']='link.md'
        with self.assertRaises(ValueError):self.prepare(packet)
        (self.payload_root/'body.md').write_bytes(b'changed')
        with self.assertRaises(ValueError):self.prepare()
        (self.payload_root/'body.md').write_bytes(b'\xff')
        self.client['operations'][0]['payload']['hash']=sha256_bytes(b'\xff')
        with self.assertRaises(UnicodeError):self.prepare()

    def test_fenced_heading_allowed_actual_root_heading_rejected(self):
        for raw, accepted in [(b'```markdown\n# Example\n```\n',True),(b'# Replace root\n',False),
                              (b'~~~\n# Example\n~~~\n',True)]:
            (self.payload_root/'body.md').write_bytes(raw)
            self.client['operations'][0]['payload']['hash']=sha256_bytes(raw)
            if accepted:self.prepare()
            else:
                with self.assertRaises(ValueError):self.prepare()

    def test_duplicate_targets_cycles_and_unknown_dependencies(self):
        self.plan['max_operations']=2;self.rebind()
        for mutation in ['duplicate_label','duplicate_target','cycle','missing']:
            packet=deepcopy(self.client);other=deepcopy(packet['operations'][0]);other['operation_id']='local_b'
            if mutation=='duplicate_label':other['operation_id']='local_a'
            if mutation=='cycle':
                other['depends_on_operation_ids']=['local_a'];packet['operations'][0]['depends_on_operation_ids']=['local_b']
            if mutation=='missing':other['depends_on_operation_ids']=['absent']
            packet['operations'].append(other)
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.prepare(packet)

    def test_mixed_correction_and_unauthorized_deletion_rejects_whole_set(self):
        self.plan['max_operations']=2;self.plan['allowed_operation_types'].append('delete_section_subtree');self.rebind()
        packet=deepcopy(self.client)
        deletion=deepcopy(packet['operations'][0]);deletion.update(operation_id='delete',operation_type='delete_section_subtree',payload={'path':None,'hash':None},normative_change='remove')
        packet['operations'].append(deletion)
        with self.assertRaises(ValueError):self.prepare(packet)
        packet=deepcopy(self.client);packet['operations'][0]['normative_change']='weaken'
        with self.assertRaisesRegex(ValueError,'authorize'):self.prepare(packet)

    def test_decline_and_mutation_budget_are_not_silently_ignored(self):
        self.client['declined_findings']=[{'finding_id':self.plan['finding_dispositions'][0]['finding_id'],
            'source_feedback_ids':['fb-1'],'decline_reason':'ambiguous','rationale':'Need a choice.'}]
        with self.assertRaisesRegex(ValueError,'declined'):self.prepare()
        self.client['declined_findings']=[];self.plan['max_operations']=0;self.rebind()
        with self.assertRaisesRegex(ValueError,'budget'):self.prepare()

    def test_hash_valid_but_structurally_forged_map_rejects(self):
        self.mapping['sections'][0]['heading_text']='Forged heading'
        with self.assertRaisesRegex(ValueError,'exact base'):self.prepare()


if __name__ == '__main__':unittest.main()

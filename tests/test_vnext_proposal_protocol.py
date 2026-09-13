"""Transport bytes remain inspectable while only canonical patch artifacts publish."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_proposal_protocol import capture_response, proposal_prompt
import test_vnext_proposals as proposal_tests


class ProposalProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proposal_tests.ProposalTests.setUpClass()

    def setUp(self):
        self.case=proposal_tests.ProposalTests();self.case.setUp();self.addCleanup(self.case.doCleanups)
        self.out=self.case.root/'output';self.out.mkdir()
        self.packet={'schema_version':'vnext-proposal-response-v1','patch':self.case.client,
                     'payloads':[{'path':'body.md','content':self.case.payload.decode()}]}
        self.details=[{'finding_id':self.case.plan['finding_dispositions'][0]['finding_id'],
                       'source_findings':[{'claim':'Clarify the existing minimum.', 'recommended_change':'Keep the same 30 second minimum.'}]}]
        self.kwargs=dict(plan=self.case.plan,base=self.case.base,section_map=self.case.mapping,
                         editor=self.case.bundle.review['editor'],suite=self.case.suite)

    def test_scripted_patch_transport_preserves_exact_raw_bytes_without_candidate(self):
        prompt=proposal_prompt(plan=self.case.plan,base=self.case.base,section_map=self.case.mapping,
                               authority=self.case.bundle.authority,invariants=self.case.bundle.invariants,context={},finding_details=self.details)
        self.assertIn('Do not return a full draft',prompt)
        self.assertIn(self.case.plan['transaction_id'],prompt)
        raw=json.dumps(self.packet,indent=3).encode()+b'\n'
        proposal,ref=capture_response(self.out,1,1,raw,**self.kwargs)
        retained=self.out/'rounds/round-1/proposals/attempts/proposal-attempt-1.json'
        self.assertEqual(retained.read_bytes(),raw)
        self.assertEqual((self.out/ref['path']).read_bytes(),canonical_json_bytes(proposal.patch))
        self.assertFalse(list(self.out.rglob('candidate_unverified.md')))
        self.assertFalse((self.out/'rounds/current_verified.json').exists())

    def test_unrelated_missing_duplicate_or_escaping_payload_refuses_before_canonical_publication(self):
        for number,mutation in enumerate(('extra','missing','duplicate','escape'),1):
            packet=deepcopy(self.packet)
            if mutation=='extra':packet['payloads'].append({'path':'unrelated.md','content':'Drop a different contract.'})
            if mutation=='missing':packet['payloads']=[]
            if mutation=='duplicate':packet['payloads']*=2
            if mutation=='escape':
                packet['payloads'][0]['path']='../outside.md';packet['patch']['operations'][0]['payload']['path']='../outside.md'
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                capture_response(self.out,1,number,canonical_json_bytes(packet),**self.kwargs)
        self.assertEqual(len(list(self.out.rglob('proposal-attempt-*.json'))),4)
        self.assertFalse(list(self.out.rglob('proposed_patch.json')))

    def test_full_draft_or_mismatched_payload_hash_remains_raw_evidence(self):
        with self.assertRaises(ValueError):capture_response(self.out,1,1,b'# A replacement draft',**self.kwargs)
        self.packet['payloads'][0]['content']='Wait no more than 10 seconds.\n'
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            capture_response(self.out,1,2,canonical_json_bytes(self.packet),**self.kwargs)
        self.assertFalse(list(self.out.rglob('proposed_patch.json')))

    def test_undeclared_context_and_changed_bound_contract_refuse(self):
        kwargs=dict(plan=self.case.plan,base=self.case.base,section_map=self.case.mapping,
                    authority=self.case.bundle.authority,invariants=self.case.bundle.invariants,finding_details=self.details)
        with self.assertRaisesRegex(ValueError,'undeclared'):
            proposal_prompt(**kwargs,context={'bind_'+'f'*64:b'PRIVATE EXCLUDED CONTENT'})
        changed=deepcopy(self.case.bundle.invariants);changed['base_draft_hash']='f'*64
        with self.assertRaisesRegex(ValueError,'invariants'):
            proposal_prompt(**{**kwargs,'invariants':changed},context={})
        with self.assertRaisesRegex(ValueError,'stale'):
            proposal_prompt(**{**kwargs,'base':self.case.base+b'Changed.\n'},context={})
        with self.assertRaisesRegex(ValueError,'finding details'):
            proposal_prompt(**{**kwargs,'finding_details':[]},context={})


if __name__=='__main__':unittest.main()

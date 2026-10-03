"""Final disagreement survives interrupted reconciliation and command reentry."""
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_local_storage import LocalAuthorityStore
import test_vnext_verified_first_review_commands as first


@unittest.skipUnless(sys.platform=='darwin','D8 requires local macOS/APFS')
class FindingsCommandTests(unittest.TestCase):
    setUpClass=first.FirstReviewCommandTests.setUpClass
    setUp=first.FirstReviewCommandTests.setUp
    patch=first.FirstReviewCommandTests.patch
    qualify=first.FirstReviewCommandTests.qualify
    save_config=first.FirstReviewCommandTests.save_config
    clean=staticmethod(first.FirstReviewCommandTests.clean)
    invoke=first.FirstReviewCommandTests.invoke
    files=first.FirstReviewCommandTests.files
    stage_phase2=first.FirstReviewCommandTests.stage_phase2
    ready=first.FirstReviewCommandTests.ready
    call=first.FirstReviewCommandTests.call
    entered=first.FirstReviewCommandTests.entered
    inspect_readonly=first.FirstReviewCommandTests.inspect_readonly

    def disagreement(self,client,packet):
        inputs=json.loads(client.prompts[-1].splitlines()[-1])
        packet['draft_hash']=sha256_bytes(inputs['draft'].encode())
        row=packet['feedback'][0]
        row.update(baseline_severity='major',normalized_severity='major',authority_impact=None,
            determinism_impact=None,rubric_impact=None,invariant_violated=None,
            affected_sections=['convergence_declaration.md'],issue_type='declaration_hash_mismatch',
            claim='The declaration hash is wrong.',evidence='An unproven Reviewer assertion.',
            recommended_change='Correct the declaration hash.')
        row['oscillation_key']['section_id']='convergence_declaration.md'
        mutable=next(r for r in inputs['authority']['bindings'] if r['role']=='mutable_target')
        hints=[dict(feedback_id=r['feedback_id'],classification='deferable',
            authority_scope_ids=mutable['authority_scopes'],source_authority_binding_ids=[mutable['binding_id']],
            scope_surface_ids=[],compatibility_change='none',requested_effects=['clarification']) for r in packet['feedback']]
        return canonical_json_bytes(dict(review=packet,rubric_findings=[],classifications=hints))

    def test_interrupted_findings_recover_only_publication_and_preserve_disagreement(self):
        self.entered();self.phase2_reviewer.callback=self.disagreement
        publish=LocalAuthorityStore.publish;faults=[]
        def lose(suffix):
            def interrupted(store,token,path,value):
                result=publish(store,token,path,value)
                if '/finding_reconciliation/' in path and path.endswith(suffix):
                    faults.append(path);raise OSError('fixture finding acknowledgement lost')
                return result
            return interrupted
        with patch.object(LocalAuthorityStore,'publish',lose('/unresolved_issues.json')):
            code,result=self.call('live-phase2')
        self.assertEqual(code,2,result);self.assertEqual(len(faults),1,result)
        self.assertEqual(self.phase2_reviewer.calls,1)
        state=self.inspect_readonly();self.assertEqual(state['recovery'],'findings_publication',state)
        findings=state['findings'];packet=findings['packet']
        self.assertFalse(findings['committed']);self.assertEqual(findings['pending_paths'],[findings['reference']['path']])
        self.assertEqual(packet['route'],'declaration_revision_required')
        self.assertEqual(packet['remaining_step_budget'],1)
        declaration=json.loads((self.root/packet['declaration_binding']['path']).read_bytes())
        original={ref['path']:(self.root/ref['path']).read_bytes() for ref in
                  (packet['review_request'],packet['review_result'],packet['review_consumption'],
                   packet['feedback'],declaration['declaration'],declaration['unresolved_issues'])}
        before=self.files()
        with patch.object(LocalAuthorityStore,'acquire',side_effect=AssertionError('read-only command took fence')):
            code,result=self.call('resume','--dry-run');self.assertEqual(code,0,result)
            code,result=self.call('live-phase2');self.assertEqual(code,2,result)
            self.assertEqual(result['next_action'],'resume')
            code,result=self.call('resume','--continue');self.assertEqual(code,2,result)
        self.assertEqual(self.files(),before)
        # Successful publication with a lost acknowledgement is durable. A new
        # invocation must report that fact, not attempt another review or repair.
        with patch.object(LocalAuthorityStore,'publish',lose('/commit.json')):
            code,result=self.call('resume')
        self.assertEqual(code,2,result);self.assertEqual(len(faults),2,result)
        state=self.inspect_readonly()
        self.assertEqual(state['gate'],'declaration_closeout_required',state)
        self.assertIsNone(state['recovery']);self.assertIsNone(state['continuation'])
        self.assertTrue(state['findings']['committed'])
        report=state['blocked_report']
        self.assertEqual(report['report_kind'],'status_only')
        self.assertEqual(report['route'],'declaration_revision_required')
        self.assertEqual(report['reconciliation'],findings['reference'])
        self.assertEqual(report['budget']['remaining'],1)
        self.assertTrue(all(row['matches'] for row in report['comparisons']['reviewed_inputs']))
        counts={row['field']:row for row in report['comparisons']['current_residuals']}
        self.assertEqual(counts['unresolved_major_issues count'],
                         dict(field='unresolved_major_issues count',observed='0',expected='1',matches=False))
        retained=report['findings'][0]
        self.assertEqual(retained['disposition'],'unresolved')
        self.assertEqual(retained['finding'],json.loads(original[packet['feedback']['path']])['feedback'][0])
        self.assertEqual(retained['sources'],[dict(feedback=packet['feedback'],consumption=packet['review_consumption'])])
        for key in ('automatic_repair_established','findings_resolved','repair_authorized',
                    'candidate_authorized','next_review_authorized','phase_complete'):
            self.assertIs(report[key],False)
        self.assertNotIn('terminal_state',report)
        before=self.files()
        with patch.object(LocalAuthorityStore,'acquire',side_effect=AssertionError('blocked reentry took fence')):
            for args in [('resume',),('resume','--dry-run'),('resume','--continue'),('live-phase2',)]:
                code,result=self.call(*args);self.assertEqual(code,2,result)
        self.assertEqual(result['blocked_report'],report)
        self.assertEqual(self.files(),before);self.assertEqual(self.phase2_reviewer.calls,1)
        self.assertEqual((self.root/'rounds/current_verified.json').read_bytes(),self.head)
        self.assertEqual((self.root/'rounds/phase2/entry.json').read_bytes(),self.entry)
        for path,raw in original.items():self.assertEqual((self.root/path).read_bytes(),raw)
        self.assertFalse((self.root/'rounds/phase2/review_requests/pass-2').exists())
        self.assertFalse(list(self.root.rglob('candidate_unverified.md')))


if __name__=='__main__':unittest.main()

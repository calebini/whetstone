from copy import deepcopy
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_assembly import assemble_bytes
from whetstone.vnext_candidate_validation import assess_candidate
from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_identity import candidate_id
from whetstone.vnext_section_lineage import candidate_section_map
from whetstone.vnext_semantic_answers import SemanticAnswerSource, submit_semantic_answer
from whetstone.vnext_semantic_followup_preflight import read_followup_evidence, validate_followup_contracts
from whetstone.vnext_semantic_context import prepare_semantic_context
from whetstone.vnext_semantic_protocol import decode_semantic_response
from whetstone.vnext_unit_preflight import prepare_unit_preflight
from whetstone.vnext_unit_protocol import decode_unit_response
from vnext_consuming_suite_fixture import consuming_suite
import test_vnext_semantic_answers as answers
import test_vnext_unit_preflight as unit_tests
import test_vnext_semantic_protocol as protocol_tests
from vnext_fixtures import STAMP


def followup_suite(test,directory):
    return consuming_suite(test,directory,
        additional_schemas=answers.SEMANTIC_SCHEMAS | answers.REQUEST_SCHEMAS | answers.ANSWER_SCHEMAS | {'mutation_plan_v3'},
        additional_algorithms=(*answers.SEMANTIC_ALGORITHMS,'vnext_semantic_requests_v1',
            'vnext_semantic_decisions_v1','vnext_semantic_answers_v1','vnext_semantic_followup_preflight_v1'),
        algorithm_overrides={'semantic_verifier_policy_version':answers.POLICY_VERSION})


@unittest.skipUnless(sys.platform=='darwin','Proposed local storage targets macOS/APFS')
class SemanticFollowupPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        answers.requests.SemanticRequestTests.setUpClass()
        owner=unittest.TestCase();cls.addClassCleanup(owner.doCleanups)
        with patch.object(answers,'answer_suite',followup_suite): cls.subject=answers.subject_for(owner)
        s=cls.subject
        cls.source=SemanticAnswerSource(s.store,admission=s.admission,candidate_id=s.identifier)
        packet=answers.input_for(cls.source)
        cls.evidence=[];cls.receipts=[]
        for choice in cls.source.request['choice']['alternatives']:
            packet['selected_authority_binding_id']=choice['authority_binding_id']
            result=submit_semantic_answer(s.store,admission=s.admission,packet=packet)
            cls.receipts.append(result['reference'])
            cls.evidence.append(read_followup_evidence(s.store,admission=s.admission,candidate_id=s.identifier,
                                                       reference=result['reference']))
        packet.update(action='decline',selected_authority_binding_id=None)
        cls.decline=submit_semantic_answer(s.store,admission=s.admission,packet=packet)['reference']
        cls.arguments=s.admission.load_inputs(s.store.read,1)
        cls.baseline=prepare_unit_preflight(**cls.arguments)

    def prepare(self,index=0,**changes):
        return prepare_unit_preflight(**{**self.arguments,'semantic_followup':self.evidence[index],**changes})

    def test_followup_has_distinct_stable_identity_and_exact_original_editing_scope(self):
        before=answers.files(self.subject)
        first=self.prepare();again=self.prepare();second=self.prepare(1)
        self.assertNotEqual(first.plan['transaction_id'],self.baseline.plan['transaction_id'])
        self.assertNotEqual(first.plan['transaction_id'],second.plan['transaction_id'])
        self.assertEqual((first.plan,first.input_hash,first.prompt),(again.plan,again.input_hash,again.prompt))
        for key,value in self.baseline.plan.items():
            if key not in {'schema_version','transaction_id'}: self.assertEqual(first.plan[key],value,key)
        self.assertEqual(first.findings,self.baseline.findings)
        self.assertEqual(first.derived_tasks,self.baseline.derived_tasks)
        self.assertEqual(first.bindings,self.baseline.bindings)
        self.assertEqual(first.plan['semantic_origin']['answer_receipt'],self.receipts[0])
        self.assertEqual(answers.files(self.subject),before)

    def test_editor_receives_interpretation_without_effect_grants_or_reclassified_findings(self):
        preflight=self.prepare();packet=json.loads(preflight.prompt.splitlines()[-1])
        original=json.loads(self.baseline.prompt.splitlines()[-1])
        self.assertEqual(packet['admitted_findings'],original['admitted_findings'])
        self.assertEqual(packet['mutation_plan_hash'],sha256_bytes(canonical_json_bytes(preflight.plan)))
        self.assertEqual(packet['semantic_interpretation']['response']['authorized_effects'],[])
        self.assertEqual(packet['semantic_interpretation']['question'],self.source.request)
        self.assertIn('changes no authority precedence',preflight.prompt)

    def test_new_plan_drives_distinct_patch_candidate_and_independent_deterministic_assessment(self):
        preflight=self.prepare();client=unit_tests.Client()
        proposal=decode_unit_response(client.propose(preflight.prompt),preflight,base=self.arguments['base'],
            section_map=self.arguments['base_map'],editor=self.arguments['review']['editor'])
        self.assertNotEqual(proposal.patch['proposal_id'],self.subject.creation['proposal_id'])
        assembled=assemble_bytes(base=self.arguments['base'],section_map=self.arguments['base_map'],
                                 plan=preflight.plan,proposal=proposal)
        mapping=candidate_section_map(base=self.arguments['base'],base_map=self.arguments['base_map'],
                                       proposal=proposal,assembled=assembled)
        result=assess_candidate(**{key:self.arguments[key] for key in ('job','authority','invariants','seed','seed_map','base','base_map')},
            base_inventory=preflight.inventory,plan=preflight.plan,proposal=proposal,candidate_bytes=assembled.raw,
            candidate_map=mapping,bindings=preflight.bindings,rules=preflight.rules)
        self.assertEqual(result.report['result'],'pass',result.report['failures'])
        self.assertNotEqual(result.report['candidate_id'],self.subject.identifier)
        # This is pure assembly/assessment, not registration or semantic acceptance.
        self.assertEqual(self.source.view.decision['candidate_disposition'],'CANDIDATE_REJECTED')
        self.assertEqual((self.subject.editor.calls,self.subject.client.calls),(1,1))

    def test_altered_scope_or_source_bindings_refuse_before_any_client(self):
        constraints=deepcopy(self.arguments['constraints']);constraints['max_operations']+=1
        with self.assertRaisesRegex(ValueError,'editing scope'): self.prepare(constraints=constraints)
        for field in ('source_verification','receipt','receipt_ref','question','response'):
            with self.subTest(field=field):
                evidence=json.loads(self.evidence[0])
                if field=='source_verification': evidence[field]['decision_final']=False
                elif field=='receipt': evidence[field]['base_pointer']['hash']='f'*64
                elif field=='receipt_ref': evidence[field]['hash']='f'*64
                elif field=='question': evidence[field]['candidate_id']='can_'+'f'*64
                else: evidence[field]['authorized_effects']=['weaken']
                with self.assertRaises(ValueError): self.prepare(semantic_followup=canonical_json_bytes(evidence))

    def test_verifier_context_carries_same_interpretation_and_cannot_reuse_source_response(self):
        before=answers.files(self.subject)
        preflight=self.prepare();client=unit_tests.Client();values=self.arguments
        proposal=decode_unit_response(client.propose(preflight.prompt),preflight,base=values['base'],
            section_map=values['base_map'],editor=values['review']['editor'])
        assembled=assemble_bytes(base=values['base'],section_map=values['base_map'],plan=preflight.plan,proposal=proposal)
        mapping=candidate_section_map(base=values['base'],base_map=values['base_map'],proposal=proposal,assembled=assembled)
        identifier=candidate_id(preflight.plan['transaction_id'],sha256_bytes(values['base']),
            sha256_bytes(canonical_json_bytes(proposal.patch)),values['job']['assembler_version'],values['job']['normalization_version'])
        directory='rounds/round-1/candidates/'+identifier;map_path=directory+'/section_identity_map_candidate.json'
        assessment=assess_candidate(**{key:values[key] for key in ('job','authority','invariants','seed','seed_map','base','base_map')},
            base_inventory=preflight.inventory,plan=preflight.plan,proposal=proposal,candidate_bytes=assembled.raw,
            candidate_map=mapping,candidate_map_path=map_path,bindings=preflight.bindings,rules=preflight.rules)
        artifacts={directory+'/candidate_unverified.md':assembled.raw,map_path:canonical_json_bytes(mapping),
            directory+'/preservation_report.json':canonical_json_bytes(assessment.report),
            directory+'/preservation_inventory_candidate.json':canonical_json_bytes(assessment.inventory)}
        # Exercise the pure context boundary with a prospective creation; this
        # does not publish or claim a second registered candidate.
        preparation,_=self.subject.registry._preparation(1,proposal.patch['proposal_id'],2,
            sha256_bytes(canonical_json_bytes(self.subject.creation)),STAMP,(identifier,directory,proposal.patch,artifacts))
        creation=preparation['creation_event']
        context=prepare_semantic_context(proposal_inputs={**values,'semantic_followup':self.evidence[0]},proposal=proposal,
            creation=creation,creation_ref={'path':'rounds/candidate_index/creation-2.json','hash':sha256_bytes(canonical_json_bytes(creation))},
            candidate_bytes=assembled.raw,candidate_map=mapping,report=assessment.report,inventory=assessment.inventory)
        editor_packet=json.loads(preflight.prompt.splitlines()[-1])
        self.assertEqual(context.packet['semantic_interpretation'],editor_packet['semantic_interpretation'])
        with self.assertRaisesRegex(ValueError,'context'):
            decode_semantic_response(self.subject.client.valid,context)
        verifier=protocol_tests.SemanticProtocolTests();verifier.context=context
        result=verifier.decode(verifier.response())
        self.assertEqual(result.verification['verdict'],'pass')
        self.assertEqual(result.verification['transaction_id'],preflight.plan['transaction_id'])
        self.assertEqual(answers.files(self.subject),before)

    def test_decline_and_stale_receipt_cannot_supply_followup_evidence(self):
        before=answers.files(self.subject)
        for reference in (self.decline,{**self.receipts[0],'hash':'f'*64}):
            with self.subTest(reference=reference),self.assertRaises(ValueError):
                read_followup_evidence(self.subject.store,admission=self.subject.admission,
                                       candidate_id=self.subject.identifier,reference=reference)
        self.assertEqual(answers.files(self.subject),before)

    def test_unextended_preflight_remains_byte_identical_and_contract_support_is_explicit(self):
        explicit=prepare_unit_preflight(**self.arguments,semantic_followup=None)
        self.assertEqual(explicit,self.baseline)
        self.assertEqual(explicit.plan['schema_version'],'mutation-plan-v2')
        # A suite missing the new contract cannot infer it from installed files.
        suite=deepcopy(self.arguments['suite'])
        suite.manifest['algorithms'][:]=[e for e in suite.manifest['algorithms']
                                       if e['path']!='algorithms/vnext_semantic_followup_preflight_v1.md']
        with self.assertRaisesRegex(ValueError,'outside supported suite'): validate_followup_contracts(suite)


if __name__=='__main__': unittest.main()

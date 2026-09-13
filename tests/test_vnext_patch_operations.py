from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from whetstone import vnext_identity as ids
from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes, validate_contract_suite
from whetstone.vnext_decisions import decision_request
from whetstone.vnext_mutation_admission import inspect_admission, prepare_admission
from whetstone.vnext_proposals import prepare_patch
from whetstone.vnext_sections import section_spans
from vnext_fixtures import ACTOR, STAMP
from vnext_mutation_fixtures import MutationFixture


class PatchOperationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.suite=validate_contract_suite()
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.f=MutationFixture(Path(self.tmp.name),self.suite)
        self.f.base=b'# Queue\n\n## Timing\nWait at least 30 seconds.\n### Details\nKeep precision.\n## Reports\nReport the outcome.\n'
        self.f.feedback['feedback'][0]['affected_sections']=['timing'];self.f.rebind()
        self.f.constraints.update(max_operations=2,max_changed_sections=3,max_changed_normative_units=20,
            allowed_operation_types=['replace_section_body','replace_section_subtree','insert_section_before',
                                     'insert_section_after','append_child_section','delete_section_subtree'])
        self.payload_root=Path(self.tmp.name)/'payloads';self.payload_root.mkdir()
        self.responses=[];self.refresh()
    def inputs(self):return dict(descriptor_ref=self.f.job_ref,review_ref=self.f.original.review_ref,
        feedback_ref=self.f.feedback_ref,advice_ref=self.f.advice_ref)
    def refresh(self,decision_refs=()):
        self.a,self.plan,_,responses=prepare_admission(self.f.root,constraints=self.f.constraints,decision_refs=decision_refs,**self.inputs())
        self.responses=[r for r,_ in responses]
        self.target=next(s for s in self.a.mapping['sections'] if s['heading_text']=='Timing')
    def packet(self,kind,raw,*,label='first',target=None):
        target=target or self.target
        if raw is not None:(self.payload_root/(label+'.md')).write_bytes(raw)
        findings=[f['finding_id'] for f in self.plan['finding_dispositions'] if f['admitted_to_editing']]
        operation={'operation_id':label,'operation_type':kind,'target_stable_section_id':target['stable_section_id'],
            'expected_target_hash':target['section_hash'],'payload':{'path':label+'.md','hash':sha256_bytes(raw)} if raw is not None else {'path':None,'hash':None},
            'addressed_finding_ids':findings,'reason':'Exact section-scoped fixture.','normative_change':'remove' if kind=='delete_section_subtree' else 'clarification',
            'preserve_target_identity':True,'depends_on_operation_ids':[]}
        return {'schema_version':'patch-set-v1','job_id':self.a.job['job_id'],'transaction_id':self.plan['transaction_id'],
            'proposal_id':None,'base_draft_hash':sha256_bytes(self.a.base),'mutation_plan_hash':sha256_bytes(canonical_json_bytes(self.plan)),
            'editor':ACTOR,'operations':[operation],'declined_findings':[],'editor_claims':{'addressed_finding_ids':findings,'normative_change_summary':'Fixture claim only.'}}
    def prepare(self,packet):
        return prepare_patch(canonical_json_bytes(packet),payload_root=self.payload_root,plan=self.plan,
            base=self.a.base,section_map=self.a.mapping,editor=ACTOR,suite=self.suite,responses=self.responses,units=self.a.units)

    def test_each_non_destructive_operation_has_an_eligible_non_root_target(self):
        cases={'replace_section_body':b'Wait 30 seconds or longer.\n',
            'replace_section_subtree':b'## Timing\nWait 30 seconds or longer.\n### Details\nKeep precision.\n',
            'insert_section_before':b'## Before\nA timing example.\n',
            'insert_section_after':b'## After\nA timing example.\n',
            'append_child_section':b'### Example\nA timing example.\n'}
        for kind,payload in cases.items():
            with self.subTest(kind=kind):self.assertEqual(self.prepare(self.packet(kind,payload)).patch['operations'][0]['operation_type'],kind)

    def test_payload_shape_is_enforced_for_every_operation_family(self):
        for kind,payload in [('replace_section_body',b'## Wrong sibling\n'),('replace_section_subtree',b'### Wrong level\n'),
                             ('insert_section_before',b'## One\n## Two\n'),('append_child_section',b'#### Wrong child\n')]:
            with self.subTest(kind=kind),self.assertRaises(ValueError):self.prepare(self.packet(kind,payload))

    def test_ordered_insertions_normalize_labels_and_unordered_insertions_refuse(self):
        packet=self.packet('insert_section_before',b'## One\n')
        second=self.packet('insert_section_before',b'## Two\n',label='second')['operations'][0]
        packet['operations'].append(second)
        with self.assertRaisesRegex(ValueError,'dependency'):self.prepare(packet)
        second['depends_on_operation_ids']=['first']
        operations=self.prepare(packet).patch['operations']
        self.assertEqual(operations[1]['depends_on_operation_ids'],[operations[0]['operation_id']])
        packet['operations'].reverse()
        self.assertEqual(self.prepare(packet).patch['operations'],operations)

    def test_overlapping_subtrees_refuse_even_when_dependency_is_present(self):
        child=next(s for s in self.a.mapping['sections'] if s['heading_text']=='Details')
        self.f.feedback['feedback'][0]['affected_sections'].append(child['canonical_section_id']);self.f.rebind();self.refresh()
        child=next(s for s in self.a.mapping['sections'] if s['heading_text']=='Details')
        packet=self.packet('replace_section_subtree',b'## Timing\nWait 30 seconds.\n### Details\nKeep precision.\n')
        second=self.packet('replace_section_body',b'Keep exact precision.\n',label='second',target=child)['operations'][0]
        second['depends_on_operation_ids']=['first'];packet['operations'].append(second)
        with self.assertRaisesRegex(ValueError,'overlapping'):self.prepare(packet)

    def test_insertion_address_aliases_and_child_appends_need_ordering_and_duplicate_checks_are_symmetric(self):
        self.f.feedback['feedback'][0]['affected_sections'].append('reports');self.f.rebind();self.refresh()
        reports=next(s for s in self.a.mapping['sections'] if s['heading_text']=='Reports')
        packet=self.packet('insert_section_after',b'## One\n')
        second=self.packet('insert_section_before',b'## Two\n',label='second',target=reports)['operations'][0]
        packet['operations'].append(second)
        with self.assertRaisesRegex(ValueError,'dependency'):self.prepare(packet)
        second['depends_on_operation_ids']=['first'];self.prepare(packet)
        packet=self.packet('append_child_section',b'### One\n')
        second=self.packet('append_child_section',b'### Two\n',label='second')['operations'][0]
        packet['operations'].append(second)
        with self.assertRaisesRegex(ValueError,'dependency'):self.prepare(packet)
        second['depends_on_operation_ids']=['first'];self.prepare(packet)
        for first_label,second_label in [('a','z'),('z','a')]:
            packet=self.packet('insert_section_before',b'## Example\n',label=first_label)
            packet['operations'].append(self.packet('replace_section_body',b'Wait 30 seconds.\n',label=second_label)['operations'][0])
            with self.subTest(labels=(first_label,second_label)),self.assertRaisesRegex(ValueError,'duplicate mutation target'):
                self.prepare(packet)

    def test_eligible_subtree_deletion_needs_all_protected_units_and_exact_operator_effect(self):
        with self.assertRaisesRegex(ValueError,'unit authorization'):
            self.prepare(self.packet('delete_section_subtree',None))
        self.f.feedback['feedback'][0]['recommended_change']='Delete the Timing subtree and its details.'
        self.f.hint['requested_effects']=['remove'];self.f.rebind()
        a=inspect_admission(self.f.root,**self.inputs());finding=a.findings[0]
        span=next(s for s in section_spans(a.base) if s.heading=='Timing')
        removed=sorted(key for key,u in a.units.items() if span.start<=u['byte_start']<span.end and u['protected'])
        request=decision_request(job=a.job,base_hash=sha256_bytes(a.base),finding=finding,targets=finding['target_section_ids'],
            feedback_refs=[self.f.feedback_ref],options=[{'option_id':'remove_timing','description':'Remove exactly the named timing units.',
                'authorized_effects':['remove'],'authorized_deletion_unit_ids':removed}])
        response={'schema_version':'operator-decision-response-v1','job_id':a.job['job_id'],'response_id':'',
            'decision_id':request['decision_id'],'decision_request_hash':sha256_bytes(canonical_json_bytes(request)),
            'base_draft_hash':sha256_bytes(a.base),'authority_map_hash':a.job['authority_map_hash'],'scope_contract_hash':a.job['scope_contract_hash'],
            'selected_option_id':'remove_timing','authorized_effects':['remove'],'authorized_deletion_unit_ids':removed,
            'rationale':'Fictional explicit cleanup approval.','decided_by':'fixture operator','decided_at':STAMP}
        response['response_id']=ids.response_id(response)
        refs=[{'finding_id':finding['finding_id'],'request':self.f.save('inputs/request.json',request),'response':self.f.save('inputs/response.json',response)}]
        self.refresh(refs);packet=self.packet('delete_section_subtree',None)
        self.prepare(packet)
        mislabeled=deepcopy(packet);mislabeled['operations'][0]['normative_change']='clarification'
        with self.assertRaisesRegex(ValueError,'declare removal'):self.prepare(mislabeled)
        # The union in the plan may contain valid approvals for other findings;
        # the actual operation must cite the response that grants these units.
        responses=self.responses
        self.responses=[{**responses[0],'authorized_deletion_unit_ids':[]}]
        with self.assertRaisesRegex(ValueError,'addressed operator tasks'):self.prepare(packet)
        self.responses=responses
        self.plan['authorized_deletion_unit_ids'].pop()
        packet['mutation_plan_hash']=sha256_bytes(canonical_json_bytes(self.plan))
        with self.assertRaisesRegex(ValueError,'unit authorization'):self.prepare(packet)

if __name__=='__main__':unittest.main()

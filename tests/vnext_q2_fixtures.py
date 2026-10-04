"""Q2 scripted transactions on the exact offline Q1 consumer; no public activation."""
from copy import deepcopy
from contextlib import nullcontext
import json
from unittest.mock import patch

from whetstone.vnext_contracts import ALGORITHM_VERSIONS, CONTRACT_ROOT, canonical_json_bytes, sha256_bytes, validate_contract_suite
from whetstone.vnext_registry import SUITE_ALGORITHM_VERSIONS
from whetstone.vnext_unit_proposals import payload_units
from whetstone.vnext_identity import binding_id
import test_vnext_unit_preflight as unit
import test_vnext_proposal_requests as requests
import test_vnext_verified_semantics as semantics
import test_vnext_verified_work as work


def suite(test, directory, **options):
    path=CONTRACT_ROOT/'suites/vnext-verified-consumer-1.json'
    result=validate_contract_suite(path)
    return result,path,deepcopy(SUITE_ALGORITHM_VERSIONS[result.version])


class Editor(requests.Client):
    def __init__(self, edits):
        self.edits=edits
        super().__init__(self.response)

    def response(self, response):
        inputs=json.loads(self.prompts[-1].splitlines()[-1])
        operations=[];payloads=[]
        template=response['patch']['operations'][0]
        for i,(heading,kind,content,merge) in enumerate(self.edits,1):
            target=next(s for s in inputs['target_sections'] if s['content'].splitlines()[0].lstrip('# ').strip()==heading)
            path=f'edit-{i}.md'
            op={**deepcopy(template),'operation_id':f'edit-{i}','operation_type':kind,
                'target_stable_section_id':target['stable_section_id'],
                'expected_target_hash':target['section_hash'],
                'addressed_finding_ids':next(sl['admitted_finding_ids'] for sl in inputs['mutation_plan']['slices']
                    if target['stable_section_id'] in sl['target_section_ids']),
                'payload':dict(path=path,hash=sha256_bytes(content.encode()))}
            if merge:
                old=[u['unit_id'] for u in inputs['base_inventory']['units']
                     if u['primary'] and u['normative'] and u['owning_section_id']==target['stable_section_id']]
                units=payload_units(content.encode(),job_id=inputs['mutation_plan']['job_id'],
                                    parser_version=ALGORITHM_VERSIONS['parser_contract_version'])
                op['unit_correspondence']=[dict(base_unit_ids=old,payload_units=[
                    dict(kind=u['kind'],ordinal=j+1,content_hash=u['content_hash'])
                    for j,u in enumerate(units) if u['primary'] and u['normative']])]
            operations.append(op);payloads.append(dict(path=path,content=content))
        response['patch']['operations']=operations;response['payloads']=payloads
        return canonical_json_bytes(response)


def fixture(test, base, targets, *, claims=None, assertions=(), prospective=False, legacy_assembly=False,
            source_path=None):
    original=unit.UnitPreflightTests.setUp
    def configure(owner):
        original(owner);f=owner.c.f;f.base=base
        if source_path is not None:
            source_path.write_bytes(base)
            f.job['source_spec']=dict(path=str(source_path.resolve()),expected_hash=sha256_bytes(base))
        f.invariants.update(assertions=deepcopy(list(assertions)),discovery_rules=[])
        f.constraints.update(max_operations=20,max_changed_sections=500,max_changed_normative_units=20000)
        prototype=deepcopy(f.feedback['feedback'][0])
        f.feedback['feedback']=[{**deepcopy(prototype),'feedback_id':f'fb-{i+1}',
            'affected_sections':list(names),'claim':claim}
            for i,(names,claim) in enumerate(zip(targets,claims or [f'Clarify fixture wording {i}.' for i in range(len(targets))]))]
        if prospective:
            target=next(b for b in f.authority['bindings'] if b['role']=='mutable_target')
            target['effective_horizon']='prospective'
            ref=f.save('inputs/older-implementation.md',b'Older implementation uses a legacy queue adapter.\n')
            old=dict(path=ref['path'],content_hash=ref['hash'],role='implementation_context',
                authority_scopes=['queue'],effective_horizon='current',mutable=False,may_introduce_requirements=False)
            old['binding_id']=binding_id(old);f.authority['bindings'].append(old)
        rebind=f.rebind
        def bound():
            rebind()
            f.advice['findings']=[{**deepcopy(f.hint),'feedback_id':row['feedback_id']} for row in f.feedback['feedback']]
            f.advice_ref=f.save('inputs/advice.json',f.advice)
            f.constraints['required_context_binding_ids']=[b['binding_id'] for b in f.authority['bindings']]
        f.rebind=bound;bound()
    # The raw historical document predates M3's numeric-version anchor contract.
    # Its loss-specific replay uses the separately pinned existing v2 assembler;
    # a distinct test preserves the current consumer's metadata refusal.
    selection=nullcontext() if legacy_assembly else patch.object(semantics,'consuming_suite',suite)
    with patch.object(unit.UnitPreflightTests,'setUp',configure),selection:
        result=work.VerifiedWorkTests.fixture(test,register_candidate=False)
    result.work=work.VerifiedWorkTests.work(test,result)
    test.assertEqual(result.work.request(round_number=1,client=result.editor).outcome,'materialization_recovered')
    result.base_pointer=result.store.read('rounds/current_verified.json')
    result.base_mirror=result.store.read('spec.md')
    return result

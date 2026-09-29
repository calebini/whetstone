"""Deterministic assessment of candidate readback, without storage authority.

This isolated v2 consumer does not advertise runtime support. Its caller loads
immutable artifacts and validates admission and the committed base lineage.
Registration identity and descriptor capability checks remain storage/runtime
obligations; an in-memory report cannot certify those checks.
"""
from dataclasses import dataclass
from pathlib import PurePosixPath
import re

from whetstone.text_validation import validate_generated_text
from whetstone.vnext_assembly import ASSEMBLER_VERSION, NORMALIZATION_VERSION, assemble_bytes
from whetstone.vnext_assertions import evaluate_assertions, validate_assertion_program
from whetstone.vnext_contracts import VNextSchemaRegistry, canonical_json_bytes, require, sha256_bytes
from whetstone.vnext_identity import candidate_id
from whetstone.vnext_discovery import discovery_rules
from whetstone.vnext_inventory import INVENTORY_VERSION, validate_seed_inventory
from whetstone.vnext_inventory_diff import compare_inventory
from whetstone.vnext_section_lineage import candidate_section_map
from whetstone.vnext_unit_authorization import unit_effect_failures
from whetstone.vnext_unit_lineage import candidate_inventory, validate_inventory_facts
from whetstone.vnext_validation import validate_plan


@dataclass(frozen=True)
class CandidateAssessment:
    report: dict
    inventory: dict | None


def _text_failures(raw):
    """Closed obvious-marker checks; broad semantic collapse needs a verifier."""
    text=raw.decode('utf-8');failures=[]
    try:validate_generated_text(text,context='candidate')
    except ValueError as exc:failures.append(('corrupt_text',str(exc)))
    for line in text.splitlines():
        stripped=line.strip()
        if (re.fullmatch(r'(?:\.{3}|…|\[\s*(?:\.{3}|…)\s*\])(?:\s*\([^\n]*\))?',stripped)
                or re.search(r'\[(?:\.{3}\s*)?UNCHANGED\b|\[Whetstone editor blocked\]',stripped,re.I)
                or re.fullmatch(r'(?:<!--\s*)?(?:\[)?(?:rest|remainder|remaining sections?|all other sections?|section content)\s+(?:is |are |remain(?:s)? )?unchanged[.!]?(?:\])?(?:\s*-->)?',stripped,re.I)):
            failures.append(('placeholder_content','An abbreviated or unchanged-section placeholder appears in candidate text.'))
        if (re.match(r'^(?:<{7}(?:\s|$)|>{7}(?:\s|$)|\|{7}(?:\s|$))',stripped)
                or re.fullmatch(r'={7}',stripped)
                or re.match(r'^\*\*\* (?:Begin Patch|End Patch|Update File:|Add File:|Delete File:)',stripped)
                or re.match(r'^@@(?:\s|$)',stripped)):
            failures.append(('unresolved_patch_marker','An unresolved conflict or patch marker appears in candidate text.'))
    return sorted(set(failures))


def assess_candidate(*,job,authority,invariants,seed,seed_map,base,base_map,base_inventory,
                     plan,proposal,candidate_bytes,candidate_map,bindings=(),rules=None,candidate_map_path=None):
    """Reproduce immutable inputs and emit a report for assembled readback.

    Invalid admission/base inputs raise before assessment. Failures in candidate
    reproduction, identity, inventory, assertions or observed effects become
    explicit failed reports. Exact operator bindings must be freshly loaded by
    the caller; candidate/report existence cannot establish their authority.
    """
    registry=VNextSchemaRegistry()
    rules=discovery_rules(invariants,rules)
    plan_schema={'mutation-plan-v2':'mutation_plan_v2','mutation-plan-v3':'mutation_plan_v3','mutation-plan-v4':'mutation_plan_v4'}.get(plan.get('schema_version'))
    require(plan_schema is not None
            and proposal.patch.get('schema_version')=='patch-set-v2',
            'candidate assessment requires inventory-bound v2 inputs')
    registry.validate(plan,plan_schema);registry.validate(authority,'authority_map_v1')
    require(sha256_bytes(seed)==job['seed_draft']['hash'] and seed_map['job_id']==job['job_id'],
            'candidate assessment seed bindings changed')
    require(sha256_bytes(canonical_json_bytes(authority))==job['authority_map_hash']
            and sha256_bytes(canonical_json_bytes(invariants))==job['protected_invariants_hash'],
            'candidate assessment authority or invariants changed')
    require(base_inventory['seed_draft_hash']==job['seed_draft']['hash'], 'candidate inventory belongs to a different seed')
    validate_inventory_facts(base_inventory,base,base_map,rules=rules)
    if base_inventory['base_inventory_hash'] is None:
        validate_seed_inventory(base_inventory,base,base_map,job,rules=rules)
    require(plan['base_inventory_hash']==sha256_bytes(canonical_json_bytes(base_inventory))
            and plan['base_section_identity_map_hash']==sha256_bytes(canonical_json_bytes(base_map)),
            'candidate assessment plan inventory bindings changed')
    validate_assertion_program(invariants,seed,seed_map)
    responses=[(b.response,b.response_hash) for b in bindings if b.response['authorized_effects']]
    validate_plan(plan,job,authority,base_map,responses)
    patch_hash=sha256_bytes(canonical_json_bytes(proposal.patch))
    assembler = ASSEMBLER_VERSION
    if plan_schema=='mutation_plan_v4':
        from whetstone.vnext_version_operations import ASSEMBLER, validate_context
        validate_context(plan)
        assembler=ASSEMBLER
    if plan_schema=='mutation_plan_v4' or job['assembler_version']=='patch-assembler-v3':
        require(job['assembler_version']==assembler, 'candidate plan differs from descriptor assembler')
    identifier=candidate_id(plan['transaction_id'],sha256_bytes(base),patch_hash,assembler,NORMALIZATION_VERSION)
    expected_tail=('candidates',identifier,'section_identity_map_candidate.json')
    map_path=candidate_map_path or '/'.join(expected_tail)
    require(tuple(PurePosixPath(map_path).parts[-3:])==expected_tail, 'candidate map path belongs to another candidate')
    report={'schema_version':'preservation-report-v2','job_id':job['job_id'],'transaction_id':plan['transaction_id'],
        'candidate_id':identifier,'base_draft_hash':sha256_bytes(base),'candidate_hash':sha256_bytes(candidate_bytes),
        'candidate_section_identity_map_path':map_path,
        'candidate_section_identity_map_hash':sha256_bytes(canonical_json_bytes(candidate_map)) if candidate_map is not None else None,
        'patch_set_hash':patch_hash,'parser_contract_version':base_map['parser_contract_version'],
        'assembler_version':assembler,'inventory_version':INVENTORY_VERSION,'normalization_version':NORMALIZATION_VERSION,
        'reproduced_candidate_hash':None,'result':'fail','metrics_complete':False,
        'base_inventory_hash':plan['base_inventory_hash'],'candidate_inventory_hash':None,
        'protected_invariants_hash':job['protected_invariants_hash'],'rules_hash':base_inventory['rules_hash'],
        'mutation_budget':{'operations_allowed':plan['max_operations'],'operations_observed':None,
                           'sections_allowed':plan['max_changed_sections'],'sections_observed':None,
                           'normative_units_allowed':plan['max_changed_normative_units'],'normative_units_observed':None},
        'unit_changes':[],'assertion_results':[],'failures':[],
        'semantic_assertion_ids':sorted(a['assertion_id'] for a in invariants['assertions'] if a['enforcement']=='semantic'),
        'baseline_diagnostics':base_inventory['diagnostics']}
    def fail(code,message,operations=(),sections=(),units=()):
        report['failures'].append({'code':code,'message':message,'operation_ids':sorted(set(operations)),
                                   'section_ids':sorted(set(sections)),'unit_ids':sorted(set(units))})
    def row(unit,change='ambiguous',*,authorized=False,operation=None,successors=(),ordinals=(),group=None,semantic=True,findings=()):
        return {'unit_id':unit.get('unit_id'),'unit_type':unit['kind'],'owning_section_id':unit['owning_section_id'],
                'change':change,'source_finding_ids':sorted(set(findings)),'authorized':authorized,
                'operation_id':operation,'candidate_unit_ids':list(successors),'candidate_unit_ordinals':list(ordinals),
                'correspondence_group_id':group,'semantic_required':semantic}
    report['unit_changes']=[row(u) for u in base_inventory['units']]
    def finish(inventory=None):
        report['failures']=sorted({canonical_json_bytes(f):f for f in report['failures']}.values(),key=canonical_json_bytes)
        report['result']='fail' if report['failures'] else 'pass'
        registry.validate(report,'preservation_report_v2')
        return CandidateAssessment(report,inventory)
    try:
        for code,message in _text_failures(candidate_bytes):fail(code,message)
    except UnicodeDecodeError as exc:fail('invalid_utf8',str(exc))
    try:
        assembled=assemble_bytes(base=base,section_map=base_map,plan=plan,proposal=proposal)
        report['reproduced_candidate_hash']=sha256_bytes(assembled.raw)
        report['mutation_budget']['operations_observed']=len(proposal.patch['operations'])
    except ValueError as exc:
        fail('candidate_reproduction_failed',str(exc));return finish()
    if assembled.raw!=candidate_bytes:
        fail('candidate_bytes_mismatch','Persisted candidate bytes differ from independent patch replay.')
        return finish()
    try:
        expected_map=candidate_section_map(base=base,base_map=base_map,proposal=proposal,assembled=assembled)
    except ValueError as exc:
        fail('candidate_section_lineage_failed',str(exc));return finish()
    if candidate_map!=expected_map:
        fail('candidate_map_mismatch','Persisted candidate map differs from independent section lineage replay.')
        return finish()
    try:
        diff=compare_inventory(base=base,base_map=base_map,base_inventory=base_inventory,plan=plan,
            proposal=proposal,assembled=assembled,candidate_map=candidate_map,rules=rules)
    except ValueError as exc:
        fail('candidate_inventory_comparison_failed',str(exc));return finish()
    for code in diff.failures:fail(code,'Inventory comparison is incomplete or ambiguous.')
    report['baseline_diagnostics']=list(diff.baseline_diagnostics)
    inventory=None
    if not diff.failures:
        try:inventory=candidate_inventory(base=base,base_map=base_map,base_inventory=base_inventory,plan=plan,proposal=proposal,rules=rules)
        except ValueError as exc:fail('candidate_unit_lineage_failed',str(exc))
    report['candidate_inventory_hash']=sha256_bytes(canonical_json_bytes(inventory)) if inventory is not None else None
    report['metrics_complete']=inventory is not None
    if report['metrics_complete']:
        metrics=diff.editor_metrics or diff.metrics
        budget=report['mutation_budget'];budget['sections_observed']=len(metrics.changed_section_ids)
        budget['normative_units_observed']=len(metrics.normative_unit_sections)
        for prefix in ('operations','sections','normative_units'):
            if budget[prefix+'_observed']>budget[prefix+'_allowed']:
                fail('mutation_budget_exceeded',prefix+' exceeds the admitted hard mutation budget.')
    try:
        effect_failures=unit_effect_failures(diff=diff,base_inventory=base_inventory,proposal=proposal,plan=plan,bindings=bindings)
        for failure in effect_failures:
            fail(failure['code'],'Observed unit effect lacks its exact addressed operator grant.',
                 [failure['operation_id']] if failure['operation_id'] else [],units=failure['unit_ids'])
    except ValueError as exc:
        effect_failures=None;fail('operator_binding_invalid',str(exc))
    operations={o['operation_id']:o for o in proposal.patch['operations']}
    invalid_operations=set()
    for op in operations.values():
        if not any(op['target_stable_section_id'] in sl['target_section_ids']
                   and bool(op['addressed_finding_ids']) and set(op['addressed_finding_ids'])<=set(sl['admitted_finding_ids'])
                   for sl in plan['slices']):
            invalid_operations.add(op['operation_id'])
            fail('attribution_outside_slice','Operation findings do not belong to its admitted section slice.',
                 [op['operation_id']],[op['target_stable_section_id']])
    old={u['unit_id']:u for u in base_inventory['units']}
    denied={key for failure in effect_failures or () for key in failure['unit_ids']}
    rows=[]
    for delta in diff.deltas:
        op=operations.get(delta.operation_id)
        normalization_only=(op is None and not delta.semantic_obligation
            and not any(old[key]['protected'] for key in delta.base_unit_ids)
            and not any(diff.candidate_scan[j-1]['protected'] for j in delta.candidate_unit_ordinals))
        authorized=(delta.change=='unchanged' or normalization_only
                    or (delta.operation_id is None and delta.system_operation_id is not None)
                    or (op is not None and op['operation_id'] not in invalid_operations))
        authorized=authorized and inventory is not None and effect_failures is not None and not set(delta.base_unit_ids)&denied
        successors=[inventory['units'][j-1]['unit_id'] for j in delta.candidate_unit_ordinals] if inventory else []
        detail=dict(authorized=authorized,operation=delta.operation_id or delta.system_operation_id,successors=successors,ordinals=delta.candidate_unit_ordinals,
                    group=delta.correspondence_group_id,semantic=delta.semantic_obligation,findings=op['addressed_finding_ids'] if op else [])
        for key in delta.base_unit_ids:rows.append(row(old[key],delta.change,**detail))
        # New identities from split/merge groups are recorded as additions as
        # well as successors; their predecessors retain their own report rows.
        for j in delta.candidate_unit_ordinals:
            unit=inventory['units'][j-1] if inventory else diff.candidate_scan[j-1]
            if not inventory or unit['unit_id'] not in old:
                rows.append(row(unit,'added',**detail))
    report['unit_changes']=rows
    report['assertion_results']=evaluate_assertions(invariants=invariants,seed=seed,seed_map=seed_map,
        candidate=candidate_bytes,candidate_map=candidate_map,frontmatter_id=base_inventory['frontmatter_section_id'],
        rules=rules,metrics=diff.metrics if report['metrics_complete'] else None)
    severity={a['assertion_id']:a['severity'] for a in invariants['assertions']}
    for result in report['assertion_results']:
        if result['result']=='fail' and severity[result['assertion_id']]=='blocking':
            fail('blocking_assertion_failed',result['assertion_id']+': '+result['evidence'])
    return finish(inventory)


def validate_assessment_readback(report,inventory,**inputs):
    """A persisted pass must reproduce; neither caller flags nor hashes suffice."""
    VNextSchemaRegistry().validate(report,'preservation_report_v2')
    expected=assess_candidate(**inputs)
    require(report==expected.report and inventory==expected.inventory,
            'candidate assessment does not reproduce from its exact inputs')

"""Finding admission from bound Reviewer evidence and advisory classifications.

Advice does not grant authority. Deterministic scope, role, invariant and policy
triggers override it, and missing/ambiguous advice fails closed. Semantic truth
and hidden effects remain independent candidate-verification obligations.
"""
from copy import deepcopy
import re

from whetstone.clients import canonicalize_reviewer_input
from whetstone.contracts import validate_artifact
from whetstone.vnext_contracts import VNextSchemaRegistry, canonical_json_bytes, require, sha256_bytes
from whetstone.vnext_proposals import _targets

SENSITIVE = re.compile(r'\b(compatibility|migration|legacy|alias(?:es)?|dual[- ]model|'
                       r'weaken\w*|delet\w*|remov\w*|supersed\w*|choose|decide|whether|'
                       r'operator decision|authority precedence|expand scope|reduce scope)\b', re.I)
PRIORITY = {'editor_fixable':0,'deferable':1,'operator_decision_required':2,'scope_change':3,'authority_conflict':4}


def classify_feedback(*, feedback, feedback_ref, advice, job, authority, invariants,
                      base, section_map, scope=None, review=None):
    """Return deterministic records and their exact evidence, with no writes.

    feedback_ref must have been read/hash-checked by the caller. The hash is
    recomputed here too, and advisory entries refer to source feedback IDs,
    never model-minted canonical issue IDs or model-selected stable targets.
    """
    require(set(feedback_ref)=={'path','hash'}, 'invalid feedback reference')
    validate_artifact(feedback,'reviewer_feedback')
    require(sha256_bytes(canonical_json_bytes(feedback))==feedback_ref['hash'], 'feedback reference changed')
    require(canonicalize_reviewer_input(deepcopy(feedback))==feedback, 'Reviewer identities/severities are not canonical')
    require(feedback['draft_hash']==sha256_bytes(base)==section_map['draft_hash'], 'finding evidence has a stale base')
    require(section_map['job_id']==job['job_id'], 'section map belongs to another job')
    require(sha256_bytes(canonical_json_bytes(authority))==job['authority_map_hash'], 'classification authority changed')
    require(sha256_bytes(canonical_json_bytes(invariants))==job['protected_invariants_hash'], 'classification invariants changed')
    require((sha256_bytes(canonical_json_bytes(scope)) if scope is not None else None)==job['scope_contract_hash'], 'classification scope changed')
    targets=_targets(base,section_map)
    anchors={item['canonical_section_id']:key for key,(item,_) in targets.items()}
    require(len(anchors)==len(targets), 'ambiguous canonical section anchors')
    bindings={b['binding_id']:b for b in authority['bindings']}
    mutable=[b for b in bindings.values() if b['role']=='mutable_target']
    require(len(mutable)==1, 'classification requires one mutable target')
    scopes=set(mutable[0]['authority_scopes'])
    surfaces={s['id']:s for s in scope['scope_surfaces']} if scope else {}
    source_ids=[f['feedback_id'] for f in feedback['feedback']]
    require(len(source_ids)==len(set(source_ids)), 'duplicate feedback identity')
    hints={}
    if advice is not None:
        VNextSchemaRegistry().validate(advice,'vnext_finding_advice_v1')
        expected={'job_id':job['job_id'],'base_draft_hash':sha256_bytes(base),'feedback':feedback_ref,
                  'authority_map_hash':job['authority_map_hash'],'scope_contract_hash':job['scope_contract_hash'],
                  'protected_invariants_hash':job['protected_invariants_hash']}
        require(all(advice[k]==v for k,v in expected.items()), 'classification advice has stale bindings')
        hints={entry['feedback_id']:entry for entry in advice['findings']}
        require(len(hints)==len(advice['findings']) and hints.keys()==set(source_ids), 'advice coverage differs from Reviewer feedback')
    records={}
    evidence={}
    for item in feedback['feedback']:
        key=item['issue_id'];hint=hints.get(item['feedback_id'])
        known=bool(item['affected_sections']) and set(item['affected_sections'])<=anchors.keys()
        section_ids=sorted({anchors[a] for a in item['affected_sections'] if a in anchors})
        classification='operator_decision_required';reasons=[];new_job=False;deferred_by_scope=False
        if hint is None:
            reasons.append('missing_advice')
        else:
            classification=hint['classification']
            require(set(hint['source_authority_binding_ids'])<=bindings.keys(), 'advice cites an unknown authority binding')
            if not known:
                classification=max((classification,'scope_change'),key=PRIORITY.get);reasons.append('unknown_target_anchor')
            if not hint['authority_scope_ids'] or not set(hint['authority_scope_ids'])<=scopes:
                classification=max((classification,'scope_change'),key=PRIORITY.get);reasons.append('authority_scope_outside_target')
            cited=[bindings[b] for b in hint['source_authority_binding_ids']]
            if any(b['role'] not in {'mutable_target','normative_authority'} for b in cited):
                classification='authority_conflict';reasons.append('non_normative_requirement_source')
            if any(not set(hint['authority_scope_ids'])<=set(b['authority_scopes']) for b in cited):
                classification='authority_conflict';reasons.append('source_outside_declared_authority_scope')
            if scope is None:
                require(not hint['scope_surface_ids'], 'scope surfaces supplied without a scope contract')
            elif not hint['scope_surface_ids'] or not set(hint['scope_surface_ids'])<=surfaces.keys():
                classification=max((classification,'scope_change'),key=PRIORITY.get);reasons.append('unresolved_scope_surface')
            else:
                states={surfaces[s]['status'] for s in hint['scope_surface_ids']} if scope else set()
                if 'out_of_scope' in states:
                    classification=max((classification,'scope_change'),key=PRIORITY.get);reasons.append('out_of_scope_surface');new_job=True
                elif 'deferred' in states:
                    classification='deferable';deferred_by_scope=True;reasons.append('deferred_scope_surface')
            effects=set(hint['requested_effects'])
            if not effects and classification=='editor_fixable':
                classification='operator_decision_required';reasons.append('missing_effect_advice')
            if not deferred_by_scope and effects & {'remove','weaken','authority_change','scope_change'}:
                if PRIORITY[classification]<PRIORITY['operator_decision_required']:
                    classification='operator_decision_required'
                reasons.append('sensitive_effect')
            if not deferred_by_scope and 'add' in effects and not any(b['role'] in {'mutable_target','normative_authority'} and b['may_introduce_requirements'] for b in cited):
                if PRIORITY[classification]<PRIORITY['operator_decision_required']:
                    classification='operator_decision_required'
                reasons.append('new_requirement_needs_authority_or_decision')
            if not item['in_scope'] and classification=='editor_fixable':
                classification='operator_decision_required';reasons.append('reviewer_scope_disagrees')
        if not known:
            classification=max((classification,'scope_change'),key=PRIORITY.get);reasons.append('unknown_target_anchor')
        text=item['claim']+' '+item['recommended_change']
        if not deferred_by_scope and SENSITIVE.search(text) and PRIORITY[classification]<PRIORITY['operator_decision_required']:
            classification='operator_decision_required';reasons.append('visible_policy_or_destructive_trigger')
        if not deferred_by_scope and hint and hint['compatibility_change']=='introduce' and authority['prospective_rules']['introduce_compatibility_policy']=='forbid':
            classification='authority_conflict';reasons.append('compatibility_policy_forbidden');new_job=True
        protected_targets=set(section_ids)|set(item['affected_sections'])
        for target_id in section_ids:
            parent=targets[target_id][0]['parent_stable_section_id']
            while parent is not None:
                protected_targets.add(parent)
                protected_targets.add(targets[parent][0]['canonical_section_id'])
                parent=targets[parent][0]['parent_stable_section_id']
        for assertion in invariants['assertions']:
            if deferred_by_scope and item['invariant_violated']==assertion['assertion_id'] and assertion['severity']=='blocking':
                classification='authority_conflict';reasons.append('blocking_invariant_conflicts_with_deferral');new_job=True
            if not deferred_by_scope and assertion['assertion_type']=='section_unchanged' and assertion['severity']=='blocking':
                if assertion['target_scope'] in protected_targets:
                    classification='authority_conflict';reasons.append('immutable_section_invariant');new_job=True
        record={'finding_id':key,'source_feedback_ids':[item['feedback_id']],
                'classification':classification,'target_section_ids':section_ids}
        detail={'issue_fingerprint':item['issue_fingerprint'],'feedback_refs':[deepcopy(feedback_ref)],
                'source_items':[deepcopy(item)],'reasons':sorted(set(reasons)), 'requires_new_job':new_job,
                'advice_hash':sha256_bytes(canonical_json_bytes(advice)) if advice is not None else None}
        if key in records:
            require(evidence[key]['issue_fingerprint']==item['issue_fingerprint'], 'canonical issue identity collision')
            old=records[key]
            old['source_feedback_ids']=sorted(set(old['source_feedback_ids'])|{item['feedback_id']})
            old['target_section_ids']=sorted(set(old['target_section_ids'])|set(section_ids))
            old['classification']=max((old['classification'],classification),key=PRIORITY.get)
            prior=evidence[key]
            if any(s['recommended_change']!=item['recommended_change'] for s in prior['source_items']):
                old['classification']=max((old['classification'],'operator_decision_required'),key=PRIORITY.get)
                prior['reasons'].append('conflicting_repeated_recommendations')
            prior['source_items'].append(deepcopy(item));prior['reasons']=sorted(set(prior['reasons'])|set(reasons))
            prior['requires_new_job'] |= new_job
        else:
            records[key]=record;evidence[key]=detail
    from whetstone.vnext_phase1_policy import enabled, classify_obligations
    if review is not None and enabled(review):
        classify_obligations(feedback, advice, list(records.values()), evidence, scope, invariants)
    return [records[k] for k in sorted(records)],evidence

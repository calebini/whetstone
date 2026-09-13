"""Read-only cross-artifact checks for the offline vNext contract foundation.

These check claimed evidence bindings, not assembly correctness or prose truth.
They do not create a candidate, verify semantics, or authorize promotion.
"""
from pathlib import Path
import re

from whetstone.vnext_contracts import (
    ValidatedSuite, canonical_json_bytes, confined_file, decode_json, require,
    sha256_bytes, validate_contract_suite, validate_job_descriptor,
)
from whetstone import vnext_identity as ids


class ArtifactReader:
    def __init__(self, root, suite):
        self.root = Path(root).resolve()
        self.suite = suite

    def raw(self, reference):
        require(isinstance(reference, dict) and set(reference) == {'path', 'hash'}, 'invalid artifact reference')
        path = reference['path']
        # Descriptor locators may be absolute, but local artifacts remain inside the selected root.
        if isinstance(path, str) and Path(path).is_absolute():
            require(Path(path).is_relative_to(self.root), 'artifact locator is outside the run root')
            path = str(Path(path).relative_to(self.root))
        raw = confined_file(self.root, path).read_bytes()
        require(sha256_bytes(raw) == reference['hash'], 'artifact hash mismatch', path)
        return raw

    def json(self, reference, schema=None):
        raw = self.raw(reference)
        packet = decode_json(raw)
        require(raw == canonical_json_bytes(packet), 'artifact must have exact canonical JSON bytes', reference['path'])
        require(isinstance(packet, dict), 'artifact must be an object')
        name = schema or packet.get('schema_version', '').replace('-', '_')
        require(name + '.schema.json' in {Path(e['path']).name for e in self.suite.manifest['schemas']}, 'schema is outside supported suite')
        self.suite.registry.validate(packet, name)
        return packet


def _unique(values, label):
    require(len(values) == len(set(values)), 'duplicate ' + label)
    return set(values)


def _binding(packet, **expected):
    for key, value in expected.items(): require(packet.get(key) == value, 'conflicting artifact binding', key)


def validate_bootstrap(root, descriptor_ref, suite, *, review_configuration_ref):
    # Re-read pins: a mutable Python object is not a trust capability.
    suite = validate_contract_suite(suite.root / 'suites' / (suite.version + '.json'))
    reader = ArtifactReader(root, suite)
    job = reader.json(descriptor_ref, 'job_descriptor_v2')
    validate_job_descriptor(job, suite)
    require(review_configuration_ref['hash'] == job['review_configuration_hash'], 'review configuration hash mismatch')
    reader.json(review_configuration_ref, 'review_configuration_v1')
    seed = reader.raw(job['seed_draft'])
    require(seed.decode('utf-8').encode('utf-8') == seed, 'invalid UTF-8 seed')
    authority = reader.json({'path': job['authority_map_path'], 'hash': job['authority_map_hash']}, 'authority_map_v1')
    invariants = reader.json({'path': job['protected_invariants_path'], 'hash': job['protected_invariants_hash']}, 'protected_invariants_v1')
    if job['scope_contract_path'] is not None:
        scope = reader.json({'path': job['scope_contract_path'], 'hash': job['scope_contract_hash']}, 'scope_contract')
        require(scope['status'] == 'approved' and scope['approval']['approved'], 'scope must be approved')
    _binding(invariants, base_draft_hash=job['seed_draft']['hash'])
    binding_ids = _unique([b['binding_id'] for b in authority['bindings']], 'authority binding')
    mutable = [b for b in authority['bindings'] if b['role'] == 'mutable_target']
    require(len(mutable) == 1 and mutable[0]['mutable'], 'P0 requires exactly one mutable target')
    require(mutable[0]['content_hash'] == job['seed_draft']['hash'], 'mutable target must match seed')
    scopes = {}
    paths = {}
    for binding in authority['bindings']:
        require(binding['binding_id'] == ids.binding_id(binding), 'binding identity mismatch')
        own = _unique(binding['authority_scopes'], 'authority scope')
        require(bool(own), 'authority binding needs a scope')
        require(not (paths.get(binding['path'], set()) & own), 'overlapping roles for one file')
        paths.setdefault(binding['path'], set()).update(own)
        require(binding['role'] == 'mutable_target' or not binding['mutable'], 'non-target binding is mutable')
        require(binding['role'] in {'mutable_target', 'normative_authority'} or not binding['may_introduce_requirements'], 'role cannot introduce requirements')
        if binding['role'] != 'excluded': reader.raw({'path': binding['path'], 'hash': binding['content_hash']})
        if binding['role'] in {'mutable_target', 'normative_authority'}:
            for scope in own: scopes.setdefault(scope, set()).add(binding['binding_id'])
    precedence = {p['authority_scope']: p for p in authority['precedence']}
    require(len(precedence) == len(authority['precedence']), 'duplicate precedence scope')
    for scope, rule in precedence.items():
        require(scope in scopes and _unique(rule['ordered_binding_ids'], 'precedence binding') == scopes[scope], 'precedence must name exactly its normative bindings')
    require(all(len(bindings) < 2 or scope in precedence for scope, bindings in scopes.items()), 'missing authority precedence')
    _unique([a['assertion_id'] for a in invariants['assertions']], 'assertion')
    for assertion in invariants['assertions']:
        require(assertion['assertion_id'] == ids.assertion_id(invariants['base_draft_hash'], assertion), 'assertion identity mismatch')
        require(set(assertion['source_authority_binding_ids']) <= binding_ids, 'unknown assertion authority')
        require((assertion['matcher']['kind'] == 'semantic') == (assertion['enforcement'] == 'semantic'), 'matcher/enforcement mismatch')
        if assertion['matcher']['kind'] == 'regex':
            require(isinstance(assertion['matcher']['value'], str), 'regex matcher requires a string')
            try: re.compile(assertion['matcher']['value'])
            except re.error as exc: raise ValueError('invalid assertion regex') from exc
    return reader, job, authority, invariants


def validate_section_map(packet, job, *, expected_hash, seed_binding=None):
    _binding(packet, job_id=job['job_id'], draft_hash=expected_hash, parser_contract_version=job['parser_contract_version'])
    sections = packet['sections']
    indexed = {s['stable_section_id']: s for s in sections}
    require(len(indexed) == len(sections), 'duplicate stable section identity')
    _unique([s['canonical_section_id'] for s in sections if s['status'] == 'active'], 'active canonical section')
    require([s['preorder_ordinal'] for s in sections] == list(range(1, len(sections)+1)), 'section preorder must be contiguous')
    seen = set()
    for section in sections:
        require(1 <= section['heading_level'] <= 6, 'invalid ATX heading level')
        parent = section['parent_stable_section_id']
        require(parent is None or parent in seen, 'section parent missing or not earlier in preorder')
        if parent is not None: require(indexed[parent]['heading_level'] < section['heading_level'], 'invalid parent heading level')
        if seed_binding is not None:
            require(section['stable_section_id'] == ids.seed_section_id(job['job_id'], expected_hash, seed_binding, section['preorder_ordinal']), 'seed section identity mismatch')
            require(section['created_by_operation_id'] is None and section['previous_stable_section_id'] is None, 'seed map cannot claim mutation lineage')
        seen.add(section['stable_section_id'])
    return indexed


def validate_plan(plan, job, authority, base_sections, responses):
    _binding(plan, job_id=job['job_id'], base_draft_hash=base_sections['draft_hash'], authority_map_hash=job['authority_map_hash'],
             scope_contract_hash=job['scope_contract_hash'], protected_invariants_hash=job['protected_invariants_hash'])
    response_hashes = {}
    for response, digest in responses:
        _binding(response, job_id=job['job_id'], base_draft_hash=plan['base_draft_hash'], authority_map_hash=job['authority_map_hash'], scope_contract_hash=job['scope_contract_hash'])
        require(response['response_id'] == ids.response_id(response), 'response identity mismatch')
        require(response['response_id'] not in response_hashes, 'duplicate operator response')
        require(digest == sha256_bytes(canonical_json_bytes(response)), 'response content hash mismatch')
        response_hashes[response['response_id']] = digest
    available_sections = {s['stable_section_id'] for s in base_sections['sections'] if s['status'] == 'active'}
    require(set(plan['allowed_section_ids']) <= available_sections, 'unknown allowed section')
    require(set(plan['required_context_binding_ids']) <= {b['binding_id'] for b in authority['bindings'] if b['role'] != 'excluded'}, 'unknown or excluded required context')
    findings = plan['finding_dispositions']
    _unique([f['finding_id'] for f in findings], 'finding')
    admitted = {f['finding_id'] for f in findings if f['admitted_to_editing']}
    used_responses = {f['decision_response_id'] for f in findings if f['decision_response_id'] is not None}
    require(used_responses == response_hashes.keys(), 'missing or unrelated decision-response binding')
    for finding in findings:
        require(not finding['admitted_to_editing'] or finding['classification'] == 'editor_fixable', 'non-editor-fixable finding admitted')
    approved_deletions = {u for r, _ in responses for u in r['authorized_deletion_unit_ids']}
    require(set(plan['authorized_deletion_unit_ids']) <= approved_deletions, 'deletion lacks operator response')
    covered = set()
    for item in ids.topological(plan['slices'], 'slice_id', 'dependency_slice_ids'):
        require(item['slice_id'] == ids.slice_id(item), 'slice identity mismatch')
        require(set(item['target_section_ids']) <= set(plan['allowed_section_ids']), 'slice target outside plan')
        require(set(item['admitted_finding_ids']) <= admitted, 'slice contains unadmitted finding')
        covered.update(item['admitted_finding_ids'])
    require(covered == admitted, 'slices do not cover exactly the admitted findings')
    require(plan['transaction_id'] == ids.transaction_id(plan, response_hashes), 'transaction identity mismatch')
    return admitted


def validate_patch(patch, plan, sections, reader, *, proposal_directory):
    _binding(patch, job_id=plan['job_id'], transaction_id=plan['transaction_id'], base_draft_hash=plan['base_draft_hash'], mutation_plan_hash=sha256_bytes(canonical_json_bytes(plan)))
    require(patch['proposal_id'] == ids.proposal_id(patch), 'proposal identity mismatch')
    require(Path(proposal_directory).name == patch['proposal_id'], 'proposal directory identity mismatch')
    operations = ids.topological(patch['operations'], 'operation_id', 'depends_on_operation_ids')
    require(len(operations) <= plan['max_operations'], 'operation budget exceeded')
    admitted = {f['finding_id'] for f in plan['finding_dispositions'] if f['admitted_to_editing']}
    require(not any(f['finding_id'] in admitted for f in patch['declined_findings']), 'admitted finding declined; new plan required')
    touched = set()
    for operation in operations:
        require(operation['operation_id'] == ids.operation_id(plan['transaction_id'], operation), 'operation identity mismatch')
        require(operation['operation_type'] in plan['allowed_operation_types'], 'operation type outside plan')
        target = operation['target_stable_section_id']; touched.add(target)
        require(target in plan['allowed_section_ids'] and target in sections, 'operation target outside plan')
        require(operation['expected_target_hash'] == sections[target]['section_hash'], 'stale target preimage')
        require(bool(operation['addressed_finding_ids']) and set(operation['addressed_finding_ids']) <= admitted, 'operation lacks admitted attribution')
        payload = operation['payload']
        if operation['operation_type'] == 'delete_section_subtree':
            require(payload == {'path': None, 'hash': None}, 'deletion requires null payload')
            require(bool(plan['authorized_deletion_unit_ids']), 'deletion has no unit authorization')
        else:
            require(payload['path'] is not None and payload['hash'] is not None, 'operation requires payload')
            require(payload['path'] == 'payloads/' + payload['hash'] + '.md', 'payload path is not content addressed')
            reader.raw({'path': (Path(proposal_directory) / payload['path']).as_posix(), 'hash': payload['hash']})
        if operation['normative_change'] in {'remove', 'weaken', 'authority_change', 'scope_change'}:
            derived = {f['finding_id'] for f in plan['finding_dispositions'] if f['decision_response_id'] is not None}
            require(set(operation['addressed_finding_ids']) <= derived, 'sensitive effect lacks derived operator task')
    require(len(touched) <= plan['max_changed_sections'], 'section budget exceeded')
    # Shape and dependency checks do not implement patch assembly (slice 18.5).
    return operations


def validate_reports(preservation, semantic, plan, job, candidate, candidate_map_ref, patch_hash, admitted, invariants, *, operations):
    common = dict(job_id=job['job_id'], transaction_id=plan['transaction_id'], candidate_id=candidate['id'],
                  base_draft_hash=plan['base_draft_hash'], candidate_hash=candidate['hash'],
                  candidate_section_identity_map_path=candidate_map_ref['path'], candidate_section_identity_map_hash=candidate_map_ref['hash'], patch_set_hash=patch_hash)
    _binding(preservation, **common)
    for key in ('parser_contract_version','assembler_version','inventory_version','normalization_version'): _binding(preservation, **{key:job[key]})
    _binding(preservation, reproduced_candidate_hash=candidate['hash'])
    deterministic={a['assertion_id']:a for a in invariants['assertions'] if a['enforcement']=='deterministic'}
    require(_unique([a['assertion_id'] for a in preservation['assertion_results']], 'deterministic assertion') == deterministic.keys(), 'deterministic assertion coverage differs')
    budget=preservation['mutation_budget']
    require(budget['operations_observed'] == len(operations), 'reported operation count differs from patch')
    for stem,limit in [('operations','max_operations'),('sections','max_changed_sections'),('normative_units','max_changed_normative_units')]:
        require(budget[stem+'_allowed']==plan[limit], 'report budget differs from plan')
        if preservation['result']=='pass':require(budget[stem+'_observed']<=plan[limit], 'passing report exceeds budget')
    if preservation['result']=='pass':
        require(not preservation['failures'], 'passing report has failures')
        require(all(c['authorized'] and c['change']!='ambiguous' for c in preservation['unit_changes']), 'passing report has unauthorized or ambiguous change')
        require(all(a['result']=='pass' for a in preservation['assertion_results'] if deterministic[a['assertion_id']]['severity']=='blocking'), 'passing report has failed blocking assertion')
    if semantic is None:return
    _binding(semantic, **common, preservation_report_hash=sha256_bytes(canonical_json_bytes(preservation)), semantic_verifier_policy_version=job['semantic_verifier_policy_version'])
    require(_unique([a['operation_id'] for a in semantic['normative_change_assessment']], 'normative operation') == {op['operation_id'] for op in operations}, 'normative operation assessment coverage differs')
    require(_unique([f['finding_id'] for f in semantic['finding_results']], 'semantic finding') == admitted, 'semantic finding coverage differs from admitted set')
    assertions={a['assertion_id']:a for a in invariants['assertions'] if a['enforcement']=='semantic'}
    require(_unique([a['assertion_id'] for a in semantic['semantic_assertions']], 'semantic assertion')==assertions.keys(), 'semantic assertion coverage differs')
    uncertain={key for key in ('unrelated_semantic_change','lost_or_weakened_semantics','authority_compliance') if semantic[key]=='uncertain'}
    uncertain.update('semantic_assertions/'+a['assertion_id'] for a in semantic['semantic_assertions'] if a['result']=='uncertain')
    resolutions={r['field_path']:r for r in semantic['uncertainty_resolutions']}
    require(len(resolutions)==len(semantic['uncertainty_resolutions']) and resolutions.keys()==uncertain, 'uncertainty mapping is incomplete or unrelated')
    if uncertain:
        for name,r in resolutions.items():
            if name in {'unrelated_semantic_change','lost_or_weakened_semantics'}:require(r['disposition']=='reject','unsafe uncertainty mapping')
            if r['disposition']=='operator_decision_required':require(r['decision_id'] is not None,'uncertainty decision missing')
        expected='reject' if any(r['disposition']=='reject' for r in resolutions.values()) else 'operator_decision_required'
        require(semantic['verdict']==expected,'uncertainty verdict mismatch')
    if semantic['verdict']=='pass':
        require(preservation['result']=='pass' and not semantic['operator_decision_required'], 'semantic pass contradicts deterministic/decision gate')
        require(all(f['disposition']=='resolved' for f in semantic['finding_results']), 'unresolved admitted finding in passing semantic report')
        _binding(semantic, unrelated_semantic_change='none', lost_or_weakened_semantics='none', authority_compliance='pass')
        require(all(a['result']=='pass' for a in semantic['semantic_assertions'] if assertions[a['assertion_id']]['severity']=='blocking'), 'blocking semantic assertion did not pass')


def validate_decision(decision, preservation, semantic, job):
    for key in ('job_id','transaction_id','candidate_id','base_draft_hash','candidate_hash','candidate_section_identity_map_path','candidate_section_identity_map_hash','patch_set_hash'):
        _binding(decision, **{key:preservation[key]})
    _binding(decision, preservation_report_hash=sha256_bytes(canonical_json_bytes(preservation)), deterministic_result=preservation['result'],
             semantic_verification_hash=sha256_bytes(canonical_json_bytes(semantic)) if semantic else None, semantic_result=semantic['verdict'] if semantic else 'not_run')
    require((decision['decision_ordinal']==1)==(decision['previous_decision_hash'] is None), 'decision predecessor/ordinal mismatch')
    if decision['candidate_disposition']=='CANDIDATE_VERIFIED':
        require(preservation['result']=='pass' and semantic is not None and semantic['verdict']=='pass', 'verification lacks passing evidence')
        require(decision['decision_final'] and not decision['outstanding_decision_ids'] and not decision['rejection_codes'], 'verified decision is incomplete')
    elif decision['candidate_disposition']=='CANDIDATE_REJECTED':
        require(decision['decision_final'] and bool(decision['rejection_codes']), 'rejection must be final with reasons')
    else:require(not decision['decision_final'], 'unverified decision cannot be final')
    require(decision['promotion_permitted']==(job['editing_mode']=='verified_promotion' and decision['candidate_disposition']=='CANDIDATE_VERIFIED' and decision['decision_final']), 'promotion permission contradicts mode or disposition')


def validate_creation_chain(reader, index, job):
    _binding(index,job_id=job['job_id'])
    previous=None;seen=set();events=[]
    for ordinal,ref in enumerate(index['entries'],1):
        require(ref['candidate_creation_ordinal']==ordinal,'candidate index gap or duplicate ordinal')
        require(ref['path']==f'rounds/candidate_index/creation-{ordinal}.json','creation event path/ordinal mismatch')
        event=reader.json({'path':ref['path'],'hash':ref['hash']},'candidate_creation_event_v1')
        _binding(event,job_id=job['job_id'],candidate_creation_ordinal=ordinal,previous_creation_event_hash=previous)
        require(event['creation_event_id']==ids.creation_id(event),'creation identity mismatch')
        require(event['candidate_id'] not in seen,'duplicate candidate registration');seen.add(event['candidate_id'])
        proposal_dir=f"rounds/round-{event['round_number']}/proposals/{event['proposal_id']}"
        patch_path=proposal_dir+'/proposed_patch.json'
        patch_hash=sha256_bytes(confined_file(reader.root,patch_path).read_bytes())
        patch=reader.json({'path':patch_path,'hash':patch_hash},'patch_set_v1')
        _binding(patch,job_id=job['job_id'],transaction_id=event['transaction_id'],proposal_id=event['proposal_id'])
        require(patch['proposal_id']==ids.proposal_id(patch),'registered proposal identity mismatch')
        require(event['candidate_id']==ids.candidate_id(event['transaction_id'],patch['base_draft_hash'],patch_hash,job['assembler_version'],job['normalization_version']),'registered candidate identity mismatch')

        reader.raw({'path':event['candidate_path'],'hash':event['candidate_hash']})
        mapping=reader.json({'path':event['candidate_section_identity_map_path'],'hash':event['candidate_section_identity_map_hash']},'section_identity_map_v1')
        validate_section_map(mapping,job,expected_hash=event['candidate_hash'])
        initial=reader.json({'path':event['initial_disposition_event_path'],'hash':event['initial_disposition_event_hash']},'candidate_disposition_event_v1')
        _binding(initial,job_id=job['job_id'],candidate_id=event['candidate_id'],candidate_creation_ordinal=ordinal,event_ordinal=1,event_kind='candidate_created',previous_event_hash=None,previous_disposition=None,new_disposition='CANDIDATE_UNVERIFIED',source_artifact_path=event['candidate_path'],source_artifact_hash=event['candidate_hash'])
        require(initial['event_id']==ids.disposition_id(initial),'initial disposition identity mismatch')
        previous=ref['hash'];events.append(event)
    return events


def validate_disposition_chain(reader, references, creation):
    previous=None;state=None;events=[];decision_ordinal=0;previous_decision=None
    for ordinal,ref in enumerate(references,1):
        event=reader.json(ref,'candidate_disposition_event_v1')
        _binding(event,job_id=creation['job_id'],candidate_id=creation['candidate_id'],candidate_creation_ordinal=creation['candidate_creation_ordinal'],event_ordinal=ordinal,previous_event_hash=previous,previous_disposition=state)
        require(event['event_id']==ids.disposition_id(event),'disposition identity mismatch')
        if ordinal==1:
            require(ref=={'path':creation['initial_disposition_event_path'],'hash':creation['initial_disposition_event_hash']},'initial event is not registration bound')
        elif event['event_kind']=='verification_decision':
            require(state!='CANDIDATE_PROMOTED','promoted candidate cannot be reverified')
            source=reader.json({'path':event['source_artifact_path'],'hash':event['source_artifact_hash']},'candidate_verification_v1')
            decision_ordinal += 1
            _binding(source,job_id=event['job_id'],candidate_id=event['candidate_id'],candidate_creation_ordinal=creation['candidate_creation_ordinal'],candidate_disposition=event['new_disposition'],decision_ordinal=decision_ordinal,previous_decision_hash=previous_decision)
            previous_decision=event['source_artifact_hash']
        elif event['event_kind']=='promotion_committed':
            require(state=='CANDIDATE_VERIFIED' and event['new_disposition']=='CANDIDATE_PROMOTED','invalid promotion transition')
            source=reader.json({'path':event['source_artifact_path'],'hash':event['source_artifact_hash']},'promotion_intent_v1')
            _binding(source,job_id=event['job_id'],candidate_id=event['candidate_id'],candidate_creation_ordinal=creation['candidate_creation_ordinal'])
        else:require(False,'invalid later disposition event')
        state=event['new_disposition'];previous=ref['hash'];events.append(event)
    return events


def validate_verification_pointer(pointer, decision, decision_ref, event, event_ref, creation):
    _binding(pointer, **{k:decision[k] for k in ('job_id','transaction_id','candidate_id','candidate_creation_ordinal','candidate_section_identity_map_path','candidate_section_identity_map_hash','candidate_disposition','decision_final')},
             current_decision_ordinal=decision['decision_ordinal'],current_decision_path=decision_ref['path'],current_decision_hash=decision_ref['hash'],current_disposition_event_path=event_ref['path'],current_disposition_event_hash=event_ref['hash'])
    _binding(event,event_kind='verification_decision',source_artifact_path=decision_ref['path'],source_artifact_hash=decision_ref['hash'],new_disposition=decision['candidate_disposition'])
    _binding(creation, candidate_id=decision['candidate_id'],transaction_id=decision['transaction_id'],candidate_hash=decision['candidate_hash'],candidate_creation_ordinal=decision['candidate_creation_ordinal'],candidate_section_identity_map_path=decision['candidate_section_identity_map_path'],candidate_section_identity_map_hash=decision['candidate_section_identity_map_hash'])
    require(Path(decision_ref['path']).parent == Path(event_ref['path']).parent.parent == Path(creation['candidate_path']).parent, 'verification artifacts must remain in registered candidate directory')


def validate_promotion(pointer, intent, intent_ref, previous, previous_ref, creation, creation_ref, decision, decision_ref, event, event_ref, job):
    require(job['editing_mode']=='verified_promotion','promotion is forbidden by job mode')
    require(decision['candidate_disposition']=='CANDIDATE_VERIFIED' and decision['decision_final'] and decision['promotion_permitted'],'promotion lacks final verified decision')
    require(intent['intent_id']==ids.intent_id(intent),'intent identity mismatch')
    _binding(intent,job_id=job['job_id'],transaction_id=creation['transaction_id'],candidate_id=creation['candidate_id'],candidate_creation_ordinal=creation['candidate_creation_ordinal'],
             candidate_creation_event_path=creation_ref['path'],candidate_creation_event_hash=creation_ref['hash'],
             candidate_section_identity_map_path=creation['candidate_section_identity_map_path'],candidate_section_identity_map_hash=creation['candidate_section_identity_map_hash'],
             base_draft_hash=previous['verified_draft_hash'],candidate_hash=creation['candidate_hash'],candidate_verification_path=decision_ref['path'],candidate_verification_hash=decision_ref['hash'],
             expected_current_verified_hash=previous['verified_draft_hash'],expected_current_verified_pointer_hash=previous_ref['hash'],expected_current_promotion_ordinal=previous['promotion_ordinal'],next_promotion_ordinal=previous['promotion_ordinal']+1,status='prepared')
    _binding(decision,base_draft_hash=previous['verified_draft_hash'])
    _binding(event,event_kind='promotion_committed',source_artifact_path=intent_ref['path'],source_artifact_hash=intent_ref['hash'],new_disposition='CANDIDATE_PROMOTED',previous_disposition='CANDIDATE_VERIFIED',candidate_id=creation['candidate_id'])
    _binding(pointer,job_id=job['job_id'],promotion_ordinal=intent['next_promotion_ordinal'],verified_draft_path=creation['candidate_path'],verified_draft_hash=creation['candidate_hash'],
             verified_section_identity_map_path=creation['candidate_section_identity_map_path'],verified_section_identity_map_hash=creation['candidate_section_identity_map_hash'],
             source_transaction_id=creation['transaction_id'],source_candidate_id=creation['candidate_id'],source_candidate_creation_ordinal=creation['candidate_creation_ordinal'],
             source_candidate_creation_event_path=creation_ref['path'],source_candidate_creation_event_hash=creation_ref['hash'],candidate_verification_path=decision_ref['path'],candidate_verification_hash=decision_ref['hash'],
             promotion_intent_path=intent_ref['path'],promotion_intent_hash=intent_ref['hash'],promotion_disposition_event_path=event_ref['path'],promotion_disposition_event_hash=event_ref['hash'],
             previous_verified_draft_hash=previous['verified_draft_hash'],previous_verified_pointer_path=previous_ref['path'],previous_verified_pointer_hash=previous_ref['hash'])
    require(previous_ref['path']==f"rounds/verified_pointer_history/pointer-{previous['promotion_ordinal']}.json",'previous pointer must use its ordinal snapshot path')


def validate_seed_pointer(pointer, job, seed_map_ref):
    _binding(pointer,job_id=job['job_id'],promotion_ordinal=0,verified_draft_path=job['seed_draft']['path'],verified_draft_hash=job['seed_draft']['hash'],verified_section_identity_map_path=seed_map_ref['path'],verified_section_identity_map_hash=seed_map_ref['hash'])
    for key,value in pointer.items():
        if key.startswith(('source_','candidate_verification_','promotion_intent_','promotion_disposition_','previous_verified_')):
            require(value is None,'seed pointer has candidate/promotion lineage',key)


def validate_terminal(report, pointer, creation, creation_ref, effective_event, event_ref, decision=None, decision_ref=None):
    _binding(report,current_verified_draft_path=pointer['verified_draft_path'],current_verified_draft_hash=pointer['verified_draft_hash'])
    latest=report['latest_candidate']
    if creation is None:
        require(all(value is None for value in latest.values()),'empty candidate chain requires null latest fields')
    else:
        _binding(latest,candidate_id=creation['candidate_id'],candidate_creation_ordinal=creation['candidate_creation_ordinal'],candidate_creation_event_path=creation_ref['path'],candidate_creation_event_hash=creation_ref['hash'],path=creation['candidate_path'],hash=creation['candidate_hash'],
                 disposition=effective_event['new_disposition'],disposition_event_path=event_ref['path'],disposition_event_hash=event_ref['hash'],verification_decision_path=decision_ref['path'] if decision_ref else None,verification_decision_hash=decision_ref['hash'] if decision_ref else None,verification_decision_final=decision['decision_final'] if decision else None)
        if report['apply_back_permitted']:
            require(effective_event['new_disposition']=='CANDIDATE_PROMOTED' and pointer['source_candidate_id']==creation['candidate_id'],'unpromoted latest candidate cannot claim apply-back')
    if report['apply_back_permitted']:require(not report['outstanding_decision_ids'],'outstanding decision blocks apply-back')
    # Scheduler readiness, external-source checks and lock ownership are runtime gates.


def validate_ratification_delta(delta, job, authority, target_hash, responses):
    bindings={b['binding_id']:b for b in authority['bindings']}
    target=next(b['binding_id'] for b in authority['bindings'] if b['role']=='mutable_target')
    _binding(delta,job_id=job['job_id'],mutable_target_binding_id=target,target_draft_hash=target_hash)
    compared=_unique(delta['compared_binding_ids'],'compared binding')
    require(compared <= {key for key,b in bindings.items() if b['role'] not in {'excluded','mutable_target'}},'delta compares unknown or excluded binding')
    for item in delta['deltas']:
        require(item['reference_binding_id'] in compared,'delta reference is not in compared set')
        require(item['authority_scope'] in bindings[item['reference_binding_id']]['authority_scopes'],'delta scope differs from binding')
    policy=delta['compatibility_policy']
    if policy['status']=='authorized':
        require(policy['decision_response_id'] in responses,'compatibility authorization lacks operator response')
        response=responses[policy['decision_response_id']]
        _binding(response,job_id=job['job_id'],base_draft_hash=target_hash,authority_map_hash=job['authority_map_hash'],scope_contract_hash=job['scope_contract_hash'])
        require(response['response_id']==ids.response_id(response),'compatibility response identity mismatch')
    else:require(policy['decision_response_id'] is None,'unrelated compatibility decision reference')


def validate_pointer_snapshot(reader, pointer_ref):
    pointer=reader.json(pointer_ref,'current_verified_pointer_v1')
    path=f"rounds/verified_pointer_history/pointer-{pointer['promotion_ordinal']}.json"
    snapshot=confined_file(reader.root,path).read_bytes()
    require(snapshot==reader.raw(pointer_ref),'current pointer differs from its same-ordinal snapshot')
    return pointer

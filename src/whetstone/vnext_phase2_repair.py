"""Explicit narrower repair scope; final rejected bytes never become a base."""
from copy import deepcopy
from dataclasses import replace

from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, decode_json, require, sha256_bytes
from whetstone.vnext_identity import slice_id, transaction_id

ALGORITHM = 'algorithms/vnext_verified_phase2_repair_v1.md'
SCHEMA = 'vnext_phase2_repair_input_v1'
REQUEST_SCHEMA = 'vnext_phase2_repair_request_v1'


def supported(suite):
    return any(r['path'] == ALGORITHM for r in suite.manifest['algorithms'])


def pins(suite):
    from whetstone.vnext_phase2_operator import pins as operator_pins
    operator_pins(suite)
    entries = {r['path']: r['sha256'] for family in ('algorithms', 'schemas') for r in suite.manifest[family]}
    for path in (ALGORITHM, *('schemas/'+s+'.schema.json' for s in (SCHEMA, REQUEST_SCHEMA))):
        require(path in entries and entries[path] == sha256_bytes(confined_file(CONTRACT_ROOT, path).read_bytes()),
                'Phase 2 repair contract is absent or changed', path)


def prepare(arguments, evidence):
    from whetstone.vnext_unit_preflight import prepare_unit_preflight
    from whetstone.vnext_validation import validate_plan
    pins(arguments['suite'])
    require(isinstance(evidence, bytes), 'repair evidence requires canonical bytes')
    packet = decode_json(evidence)
    require(evidence == canonical_json_bytes(packet) and set(packet) == {'context','decision','decision_ref','request','semantic'},
            'invalid repair evidence envelope')
    source = packet['context']; request = packet['request']; decision = packet['decision']
    arguments['suite'].registry.validate(request, REQUEST_SCHEMA)
    arguments['suite'].registry.validate(decision, 'candidate_verification_v1')
    arguments['suite'].registry.validate(packet['semantic'], 'semantic_verification_v2')
    require(arguments.get('phase2') is not None and source.get('phase2') == arguments['phase2'],
            'repair requires unchanged Phase 2 configuration and request')
    for source_key, key in [('job','job'),('authority_map','authority'),('scope_contract','scope'),
                            ('protected_invariants','invariants'),('review_configuration','review'),
                            ('base_pointer','base_pointer_ref'),('base_map','base_map'),('seed_map','seed_map')]:
        require(source[source_key] == arguments.get(key), 'repair source binding changed: '+key)
    require(source['base'].encode() == arguments['base'] and source['seed'].encode() == arguments['seed'],
            'repair source draft changed')
    require(request['job_id'] == arguments['job']['job_id'] and request['base_pointer'] == arguments['base_pointer_ref']
            and request['round_number'] == arguments['feedback']['round_number']
            and request['source_creation'] == source['creation_ref'] and request['source_verification'] == packet['decision_ref'],
            'repair request has stale source bindings')
    require(all(request[k].strip() for k in ('decided_by','rationale','decided_at')), 'repair requires explicit operator attribution')
    require(decision['candidate_id'] == source['creation']['candidate_id'] and decision['decision_final']
            and decision['candidate_disposition'] == 'CANDIDATE_REJECTED' and decision['semantic_result'] == 'reject'
            and not decision['outstanding_decision_ids'], 'repair requires final semantic rejection without an outstanding choice')
    require(decision['job_id'] == source['job']['job_id']
            and decision['transaction_id'] == source['mutation_plan']['transaction_id']
            and packet['decision_ref'] == dict(
                path=source['creation']['candidate_path'].rsplit('/',1)[0]
                     +'/candidate_verification-attempt-'+str(decision['decision_ordinal'])+'.json',
                hash=sha256_bytes(canonical_json_bytes(decision))), 'repair verification identity changed')
    semantic = packet['semantic']
    require(sha256_bytes(canonical_json_bytes(semantic)) == decision['semantic_verification_hash'],
            'repair semantic evidence changed')
    unresolved = {r['finding_id'] for r in semantic['finding_results'] if r['disposition'] != 'resolved'}
    selected = set(request['finding_ids'])
    require(selected <= unresolved, 'repair cannot select resolved or unknown findings')
    operations = {op['operation_id']:op for op in source['editor_proposal']['patch']['operations']}
    require(set(request['operation_ids']) <= operations.keys(), 'repair selects unknown source operation')
    chosen = [operations[key] for key in request['operation_ids']]
    require(all(set(op['depends_on_operation_ids']) <= set(request['operation_ids']) for op in chosen),
            'repair operations must include their dependencies')
    require(all(set(op['addressed_finding_ids']) & selected for op in chosen)
            and selected <= {key for op in chosen for key in op['addressed_finding_ids']},
            'repair operation attribution does not cover selected rejected findings')
    types = {op['operation_type'] for op in chosen}
    require(len(types) == 1, 'repair requires one operation type to preserve exact target/type bounds')
    baseline = prepare_unit_preflight(**arguments)
    parent = source['mutation_plan']; plan = deepcopy(baseline.plan)
    parent_admitted = {r['finding_id'] for r in parent['finding_dispositions'] if r['admitted_to_editing']}
    require(selected <= parent_admitted, 'repair expands parent finding scope')
    targets = {op['target_stable_section_id'] for op in chosen}
    require(targets <= set(parent['allowed_section_ids']) and types <= set(parent['allowed_operation_types']),
            'repair expands parent operation scope')
    for key, limit in request['limits'].items():
        require(limit <= parent[key], 'repair expands parent mutation budget')
        plan[key] = limit
    require(plan['max_operations'] <= len(chosen), 'repair operation budget exceeds selected failed operations')
    require(plan['max_changed_sections'] >= len(targets), 'repair targets exceed selected section budget')
    plan['allowed_operation_types'] = sorted(types); plan['allowed_section_ids'] = sorted(targets)
    for row in plan['finding_dispositions']: row['admitted_to_editing'] = row['finding_id'] in selected
    part = dict(target_section_ids=sorted(targets), dependency_slice_ids=[], admitted_finding_ids=sorted(selected))
    plan['slices'] = [dict(slice_id=slice_id(part), **part)]
    # A fresh caller stamp or rationale never turns identical scope into a new retry.
    require(selected < parent_admitted or targets < set(parent['allowed_section_ids'])
            or types < set(parent['allowed_operation_types'])
            or any(plan[key] < parent[key] for key in request['limits']),
            'unchanged rejected plan cannot be resubmitted')
    responses = [(b.response,b.response_hash) for b in baseline.bindings if b.response['authorized_effects']]
    plan['transaction_id'] = transaction_id(plan, {r['response_id']:h for r,h in responses})
    require(plan['transaction_id'] != parent['transaction_id'], 'repair must have a distinct transaction')
    arguments['suite'].registry.validate(plan,plan['schema_version'].replace('-','_'))
    validate_plan(plan, arguments['job'], arguments['authority'], arguments['base_map'], responses)
    intro, raw = baseline.prompt.rsplit('\n',1)
    prompt = decode_json(raw.encode())
    prompt.update(mutation_plan=plan, mutation_plan_hash=sha256_bytes(canonical_json_bytes(plan)),
                  repair=dict(request=request, source_context=source, source_verification=decision, semantic=semantic))
    digest = sha256_bytes(canonical_json_bytes(dict(baseline=baseline.input_hash,repair=sha256_bytes(evidence))))
    return replace(baseline, input_hash=digest, plan=plan,
        prompt=intro+'\nRepair only the selected failed operations/findings against the verified base. '
        'The rejected candidate remains immutable and grants no authority.\n'+canonical_json_bytes(prompt).decode())

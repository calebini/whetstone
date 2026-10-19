"""Read-only explanation of decisions used by a proven promoted transaction."""
from copy import deepcopy

from whetstone.vnext_contracts import canonical_json_bytes, require, sha256_bytes


GUIDANCE = (
    'Historical operator decisions explain only the linked changes already promoted into this base. '
    'They are not current mutation authority or reusable approval. The supplied seed is the admitted '
    'starting baseline, not a reconstruction from later findings. Continue to report contradictory '
    'authority, effects beyond approval, missing evidence, regressions and new product choices. '
    'Do not presume a pass from earlier verification or promotion.\n'
)


def promoted_decisions(proof, router, creation, pointer, arguments):
    """Called only after original-transaction and final semantic replay succeed."""
    if not arguments.get('decisions'):
        return []
    journal = router.load_inputs.request_journal(
        proof.store, creation['round_number'], creation['proposal_id'])
    plan = journal.preflight.plan
    used = {row['decision_response_id'] for row in plan['finding_dispositions']
            if row['admitted_to_editing'] and row['decision_response_id'] is not None}
    record_ref = proof.owner._refs['rounds'][creation['round_number']]
    record = proof.reader.json(record_ref, 'vnext_proposal_round_input_v1')
    references = {row['finding_id']: row for row in record['decision_refs']}
    entries = []
    for decision in arguments['decisions']:
        response = decision['response']
        if response['response_id'] not in used:
            continue
        refs = references.get(decision['finding_id'])
        require(refs is not None, 'promoted decision lacks original source references')
        for name, schema in (('request', 'vnext_mutation_decision_request_v2'),
                             ('response', 'operator_decision_response_v1')):
            require(proof.reader.json(refs[name], schema) == decision[name],
                    'promoted decision source differs from original transaction')
        entries.append(dict(source_base=deepcopy(arguments['base_pointer_ref']),
            round_number=creation['round_number'], round_input=deepcopy(record_ref),
            finding_id=decision['finding_id'], feedback_refs=deepcopy(decision['feedback_refs']),
            admitted_findings=[deepcopy(row) for row in plan['finding_dispositions']
                               if row['decision_response_id'] == response['response_id']],
            plan_hash=sha256_bytes(canonical_json_bytes(plan)), transaction_id=plan['transaction_id'],
            request_ref=deepcopy(refs['request']), response_ref=deepcopy(refs['response']),
            request=deepcopy(decision['request']), response=deepcopy(response),
            selected_effects=deepcopy(response['authorized_effects']),
            promotion=dict(path=f"rounds/verified_history/current-verified-{pointer['promotion_ordinal']}.json",
                           hash=sha256_bytes(canonical_json_bytes(pointer))),
            candidate_id=creation['candidate_id']))
    require({entry['response']['response_id'] for entry in entries} == used,
            'promoted decision history is incomplete')
    return entries


def history_sources(history):
    """Exact source barriers for a detached, already validated history packet."""
    sources = {}
    for entry in history:
        for reference in [entry['source_base'], entry['round_input'], entry['request_ref'],
                          entry['response_ref'], entry['promotion'], *entry['feedback_refs']]:
            old = sources.setdefault(reference['path'], reference)
            require(old == reference, 'historical decision source has conflicting hashes')
    return [deepcopy(sources[path]) for path in sorted(sources)]


def phase2_history(proof, inputs, prompt):
    """New Phase 2 presentation, with history covered by input and prompt hashes."""
    history = proof.decision_history(proof.latest)
    inputs = deepcopy(inputs)
    inputs['historical_operator_decisions'] = history
    for reference in history_sources(history):
        if reference not in inputs['sources']:
            inputs['sources'].append(reference)
    return inputs, prompt + GUIDANCE

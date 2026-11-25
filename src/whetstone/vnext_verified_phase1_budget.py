"""Explicit grant journal over immutable baseline budgets; no client invocation."""
from whetstone.vnext_phase1_policy import closeout_schema
from copy import deepcopy
from datetime import datetime, timezone
import re

from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, require, sha256_bytes, decode_json

ALGORITHM = 'algorithms/vnext_verified_phase1_budget_v1.md'
DIRECTORY = 'rounds/phase1_budget_extensions'
SCHEMA = 'vnext_phase1_budget_extension_v1'
DEFAULT_REASON = 'operator_requested_resume_budget_extension'


def supported(suite):
    return any(r['path'] == ALGORITHM for r in suite.manifest['algorithms'])


def pins(suite):
    entries = {r['path']: r['sha256'] for family in ('algorithms', 'schemas') for r in suite.manifest[family]}
    for path in (ALGORITHM, 'schemas/'+SCHEMA+'.schema.json', 'schemas/vnext_verified_phase1_closeout_v4.schema.json',
                 'schemas/vnext_review_request_v3.schema.json', 'schemas/editor_summary.schema.json'):
        require(path in entries and entries[path] == sha256_bytes(confined_file(CONTRACT_ROOT, path).read_bytes()),
                'Phase 1 budget contract is absent or changed', path)


def ref(path, value):
    return dict(path=path, hash=sha256_bytes(canonical_json_bytes(value)))


def event_id(event, ordinal):
    fields = {k: v for k, v in event.items() if k not in {'event_id', 'generated_at'}}
    fields['extension_ordinal'] = ordinal
    return 'bxe_' + sha256_bytes(canonical_json_bytes(fields))[:16]


def records(proof, *, through_round=None):
    try: entries = proof.store.list_directory(DIRECTORY)
    except FileNotFoundError: entries = ()
    if not supported(proof.reader.suite):
        require(not entries, 'budget extension is outside supported suite')
        return []
    pins(proof.reader.suite)
    numbers = []
    for name, kind in entries:
        if name.startswith('.vnext-tmp-'): continue
        match = re.fullmatch(r'extension-([1-9][0-9]*)\.json', name)
        require(match is not None and kind == 'file', 'invalid budget extension journal')
        numbers.append(int(match[1]))
    require(sorted(numbers) == list(range(1, len(numbers)+1)), 'budget extension ordinal gap')
    result, previous, boundary = [], None, 0
    for n in sorted(numbers):
        path = f'{DIRECTORY}/extension-{n}.json'
        raw = proof.store.read(path)
        value = proof.reader.json(dict(path=path, hash=sha256_bytes(raw)), SCHEMA)
        event = value['event']
        require(raw == canonical_json_bytes(value) and value['extension_ordinal'] == n
                and value['previous'] == previous and value['job_id'] == proof.seed_values['job']['job_id']
                and value['review_configuration'] == proof.owner.run._record['review_configuration']
                and event['event_id'] == event_id(event, n)
                and event['previous_current_round'] > boundary, 'budget extension bindings or event identity changed')
        if through_round is not None and event['previous_current_round'] >= through_round: break
        previous = ref(path, value)
        result.append((previous, value))
        boundary = event['previous_current_round']
    return result


class Timeline:
    """Apply each grant at its original exhausted boundary during scheduler replay."""
    def __init__(self, proof, profiles, *, through_round=None):
        self.proof, self.profiles = proof, deepcopy(profiles)
        self.records = records(proof, through_round=through_round)
        self.index = 0

    def advance(self, number, counts, clean, base, frames, merges=()):
        if self.index == len(self.records): return
        _, value = self.records[self.index]
        event = value['event']
        boundary = event['previous_current_round']
        require(number <= boundary+1, 'budget extension skipped its original boundary')
        if number != boundary+1: return
        from whetstone.vnext_verified_review import _gate
        vertical = self.proof.seed_values['review']['review_mode'] == 'vertical'
        exhausted = (not any(counts[p['name']] < p['budget'] for p in self.profiles)
                     if vertical else _gate(self.profiles, counts, clean)[0] == 'budget_exhausted')
        require(exhausted and not all(clean.values()), 'budget extension requires exhausted Phase 1')
        require(base == value['base_pointer'], 'budget extension base differs from replay')
        pointer = self.proof.reader.json(base, 'current_verified_pointer_v1')
        closeout = self.proof.reader.json(value['closeout'], closeout_schema(self.proof.seed_values['review'], self.proof.reader.suite))
        terminal = self.proof.reader.json(closeout['terminal_report'], 'terminal_report_v2')
        receipts = [dict(round_number=f.request.number, profile=f.request.profile,
            base_pointer=f.header['base_pointer'], receipt=ref(f.request.directory+'/result.json', f.receipt)) for f in frames]
        expected_merges = [ref(f"rounds/round-{m[0]['round_number']}/vertical_merge.json", m[0]) for m in merges]
        require(closeout['job_id'] == value['job_id'] and closeout['review_configuration'] == value['review_configuration']
                and closeout['current_verified_pointer'] == base and closeout['round_number'] == boundary
                and closeout['review_receipts'] == receipts and closeout['vertical_merges'] == expected_merges
                and closeout['budget_extensions'] == [r[0] for r in self.records[:self.index]]
                and terminal['terminal_state'] == event['previous_terminal_state']
                and terminal['current_verified_draft_hash'] == pointer['verified_draft_hash']
                == event['previous_current_draft_hash'], 'budget extension exhausted evidence differs from replay')
        old = {p['name']: p['budget'] for p in self.profiles}
        new = {name: max(budget, counts[name])+event['added_rounds_per_profile'] for name, budget in old.items()}
        require(event['previous_review_profile_budgets'] == old and event['new_review_profile_budgets'] == new,
                'budget extension effective counts differ from replay')
        for profile in self.profiles: profile['budget'] = new[profile['name']]
        self.index += 1

    def finish(self):
        require(self.index == len(self.records), 'budget extension is beyond the completed scheduler boundary')


def effective_profiles(proof, profiles):
    result = deepcopy(profiles)
    grants = records(proof)
    if grants:
        budgets = grants[-1][1]['event']['new_review_profile_budgets']
        for p in result: p['budget'] = budgets[p['name']]
    return result


def recovery_record(proof, *, last_completed=None, grants=None):
    """The exact committed grant still eligible for idempotent operator reentry."""
    from whetstone.vnext_verified_review import _sequence
    from whetstone.vnext_verified_vertical_phase1 import enabled, sequence, completed_round
    if grants is None: grants = records(proof)
    if not grants: return None
    if last_completed is None:
        frames, _, _ = _sequence(proof)
        last_completed = (completed_round(sequence(proof)) if enabled(proof.seed_values['review'])
                          else max([f.request.number for f in frames if f.receipt is not None], default=0))
    return grants[-1] if last_completed == grants[-1][1]['event']['previous_current_round'] else None


def synchronize(store, proof):
    """Immutable grant dependencies must be durable before any appended work."""
    for reference, value in records(proof):
        closeout = proof.reader.json(value['closeout'], closeout_schema(proof.seed_values['review'], proof.reader.suite))
        refs = [value['review_configuration'], value['base_pointer'], value['closeout'], closeout['terminal_report']]
        if closeout['technical_failure']: refs.append(closeout['technical_failure'])
        refs += [row['receipt'] for row in closeout['review_receipts']] + closeout['vertical_merges']
        for source in refs: proof.owner.run.store.synchronize_existing(store._token, source['path'], expected=proof.reader.raw(source))
        store.publish(store._token, reference['path'], value)
    proof.guard(store.read)


def require_projected(proof):
    grants = records(proof)
    if grants:
        state = decode_json(proof.store.read('rounds/run_state.json'))
        require(state.get('budget_extensions') == [v['event'] for _, v in grants],
                'budget extension state recovery required before appended work')
        from whetstone.vnext_verified_review import _sequence
        from whetstone.vnext_verified_vertical_phase1 import enabled, sequence, completed_round
        frames, _, _ = _sequence(proof)
        number = completed_round(sequence(proof)) if enabled(proof.seed_values['review']) else max(
            [f.request.number for f in frames if f.receipt is not None], default=0)
        require(state.get('current_round') == number, 'Phase 1 round state recovery required before appended work')


def project_review_state(run, store, proof):
    """Complete the derived round checkpoint inside its existing Reviewer fence."""
    if not supported(proof.reader.suite): return
    from whetstone.vnext_verified_phase1_operator import _OperatorStatus
    owner = _OperatorStatus(run)
    before, target, _ = owner._state_target(owner.evaluate(proof), proof)
    def validate(read, path, raw):
        proof.guard(read); run._guard(read)
        require(path == 'rounds/run_state.json' and raw == target and read(path) == before,
                'Phase 1 round state changed during projection')
    if target != before:
        run.store.materialize(store._token, 'rounds/run_state.json', target, validate_target=validate)
    else:
        run.store.synchronize_existing(store._token, 'rounds/run_state.json', expected=target)


def extend(run, *, added_rounds_per_profile, reason=DEFAULT_REASON, generated_at=None):
    from whetstone.vnext_verified_phase1_operator import _OperatorStatus
    from whetstone.vnext_verified_review import _sequence, _contract
    from whetstone.vnext_verified_vertical_phase1 import enabled, sequence, completed_round
    require(type(added_rounds_per_profile) is int and added_rounds_per_profile > 0,
            'budget extension requires an explicit positive integer')
    require(isinstance(reason, str) and reason.strip(), 'budget extension requires a reason')
    owner = _OperatorStatus(run)

    def guard_mirrors():
        pointer = decode_json(run.store.read('rounds/current_verified.json'))
        state = decode_json(run.store.read('rounds/run_state.json'))
        require(sha256_bytes(run.store.read('spec.md')) == pointer['verified_draft_hash'] == state.get('current_draft_hash'),
                'budget extension current draft/state hash mismatch')
    guard_mirrors()

    def publish(store, proof):
        pins(proof.reader.suite)
        guard_mirrors()
        require(owner._optional('rounds/phase2/entry_request.json') is None,
                'Phase 1 budget cannot change after Phase 2 binding')
        frames, gate, _ = _sequence(proof)
        grants = records(proof)
        last_completed = (completed_round(sequence(proof)) if enabled(proof.seed_values['review'])
                          else max([f.request.number for f in frames if f.receipt is not None], default=0))
        # A committed grant with no appended completed round is recovery, never a second grant.
        recovery = recovery_record(proof, last_completed=last_completed, grants=grants) is not None
        if recovery:
            reference, value = grants[-1]
            require(value['event']['added_rounds_per_profile'] == added_rounds_per_profile
                    and value['event']['reason'] == reason, 'pending extension has different explicit parameters')
        else:
            closeout = owner.evaluate(proof)
            status = owner._status(proof, closeout)
            require(gate == 'budget_exhausted' and closeout.materialized and status.state_current,
                    'budget extension requires committed exhausted closeout and current state')
            checked = owner._synchronize_sources(store, proof, closeout)
            require(checked == closeout, 'budget extension closeout changed during barriers')
            profiles = effective_profiles(proof, _contract(proof))
            counts = {p['name']: sum(f.receipt is not None and f.request.profile == p['name'] for f in frames) for p in profiles}
            previous = {p['name']: p['budget'] for p in profiles}
            event = dict(generated_at=generated_at or datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'),
                phase='phase_1', previous_terminal_state=closeout.report['terminal_state'], previous_current_round=last_completed,
                previous_current_draft_hash=proof.pointers[-1]['verified_draft_hash'], previous_review_profile_budgets=previous,
                new_review_profile_budgets={k: max(v, counts[k])+added_rounds_per_profile for k,v in previous.items()},
                added_rounds_per_profile=added_rounds_per_profile, reason=reason)
            event['event_id'] = event_id(event, len(grants)+1)
            value = dict(schema_version='vnext-phase1-budget-extension-v1', job_id=proof.seed_values['job']['job_id'],
                review_configuration=deepcopy(run._record['review_configuration']), base_pointer=deepcopy(proof.latest),
                closeout=deepcopy(closeout.evidence_ref), previous=grants[-1][0] if grants else None,
                extension_ordinal=len(grants)+1, event=event)
            proof.reader.suite.registry.validate(value, SCHEMA)
            reference = ref(f'{DIRECTORY}/extension-{len(grants)+1}.json', value)
            for source in (closeout.evidence_ref, closeout.report_ref):
                proof.owner.run.store.synchronize_existing(store._token, source['path'], expected=proof.reader.raw(source))
        synchronize(store, proof)
        require(records(proof) == grants, 'budget extension history changed during source barriers')
        if not recovery:
            require(owner.evaluate(proof) == closeout, 'budget extension sources changed before commit')
        else:
            _sequence(proof)
        guard_mirrors()
        proof.guard(store.read)
        run._guard(store.read)
        store.publish(store._token, reference['path'], value)
        # Re-evaluate from the committed journal before writing the derived state.
        closeout = owner.evaluate(proof)
        before, target, _ = owner._state_target(closeout, proof)
        def validate(read, path, raw):
            proof.guard(read); run._guard(read)
            require(path == 'rounds/run_state.json' and raw == target and read(path) == before,
                    'budget extension state changed during recovery')
        if before != target: run.store.materialize(store._token, 'rounds/run_state.json', target, validate_target=validate)
        else: proof.owner.run.store.synchronize_existing(store._token, 'rounds/run_state.json', expected=target)
        require_projected(proof)
        return dict(outcome='budget_extension_recovered' if recovery else 'budget_extended',
                    extension=deepcopy(value), reference=reference, next_gate=closeout.review_gate)
    return owner._execute(publish)

"""Explicit, opt-in Phase 2 correction reports over existing immutable journals."""
from copy import copy, deepcopy
from datetime import datetime, timezone

from whetstone.hashing import draft_hash
from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, confined_file, decode_json, require, sha256_bytes
from whetstone.vnext_candidate_registry import CandidateAssemblyFailure
from whetstone.vnext_validation import validate_terminal
from whetstone.vnext_verified_history import _HistoricalJournal
from whetstone.vnext_verified_materialization import STATE_PATH
from whetstone.vnext_verified_phase2_binding import _ref
from whetstone.vnext_verified_phase2_closeout import _Declaration, _latest_issues
from whetstone.vnext_verified_phase2_sequence import _Evidence, sequence
from whetstone.vnext_verified_semantics import VerifiedSemanticDecisionJournal, VerifiedSemanticRequestJournal

ALGORITHM = 'algorithms/vnext_verified_phase2_correction_failure_v1.md'
SCHEMA = 'vnext_phase2_correction_failure_v1'
ROOT = 'rounds/phase2/correction_failures'
STATE_FIELD = 'vnext_phase2_correction_failure'
STAGES = ('editor', 'assembly', 'verifier', 'candidate')


def supported(proof):
    return any(r['path'] == ALGORITHM for r in proof.reader.suite.manifest['algorithms'])


class _CorrectionFailure(_Declaration):
    def __init__(self, run):
        tracked = copy(run)
        tracked.store = _Evidence(run.store)
        super().__init__(tracked)

    def _proof(self, read):
        # Track the same physical owner reads even when the kernel supplies its
        # direct reader to the fence validator; no virtualized bytes or cache.
        from whetstone.vnext_verified_phase2_failure import _Failure
        proof = _Failure(self.run)._proof(self.store.read)
        pins = {r['path']: r['sha256'] for family in ('algorithms', 'schemas')
                for r in proof.reader.suite.manifest[family]}
        for path in (ALGORITHM, 'schemas/'+SCHEMA+'.schema.json',
                     'schemas/vnext_correction_artifact_error_v1.schema.json',
                     'schemas/convergence_failure_report.schema.json'):
            require(path in pins and pins[path] == sha256_bytes(confined_file(CONTRACT_ROOT, path).read_bytes()),
                    'Phase 2 correction failure contract is absent or changed', path)
        return proof

    def _terminal(self, proof, frame, stage, candidate, terminal, reason, predecessor=None):
        """Render original failure-time disposition, never a later intended state."""
        number = frame['owner'].number
        creations = [c for c in proof.view.creations if c['round_number'] < number]
        if candidate is not None:
            creations.append(candidate)
        from whetstone.vnext_phase2_operator import supported as operator_supported
        if operator_supported(proof.reader.suite) and (candidate is not None or predecessor is not None):
            last = candidate or predecessor
            creations = [c for c in proof.view.creations
                         if c['candidate_creation_ordinal'] <= last['candidate_creation_ordinal']]
        views = []
        for c in creations:
            router = proof.transactions(c['candidate_creation_ordinal'])
            view = VerifiedSemanticDecisionJournal(router.registry(), admission=router)._state(c)[0]
            views.append(view)
        latest = views[-1] if views else None
        pointer = frame['owner'].proof.pointers[-1]
        fields = proof.reader.suite.registry.load('terminal_report_v2')['properties']['latest_candidate']['properties']
        projection = dict.fromkeys(fields)
        creation = creation_ref = event = event_ref = decision = decision_ref = None
        if latest:
            creation = latest.creation
            creation_ref = _ref(f"rounds/candidate_index/creation-{creation['candidate_creation_ordinal']}.json", creation)
            decision = latest.decision
            event, event_ref = latest.effective_event, latest.effective_event_ref
            if candidate is not None and stage == 'verifier':
                directory = candidate['candidate_path'].rsplit('/', 1)[0]
                # The full current journal above proves this committed predecessor.
                path = directory+'/candidate_verification-attempt-1.json'
                decision = decode_json(self.store.read(path));decision_ref = _ref(path, decision)
                path = directory+'/disposition_events/event-2.json'
                event = decode_json(self.store.read(path));event_ref = _ref(path, event)
                require(not decision['decision_final'] and decision['deterministic_result'] == 'pass',
                        'Verifier failure lacks committed deterministic predecessor')
            else:
                require(not latest.prepared, 'recover candidate decision before failure reporting')
                if latest.pointer:
                    decision_ref = dict(path=latest.pointer['current_decision_path'], hash=latest.pointer['current_decision_hash'])
                promoted = next((p for p in frame['owner'].proof.pointers if p['source_candidate_id'] == creation['candidate_id']), None)
                if promoted:
                    event_ref = dict(path=promoted['promotion_disposition_event_path'], hash=promoted['promotion_disposition_event_hash'])
                    event = proof.reader.json(event_ref, 'candidate_disposition_event_v1')
            projection.update(candidate_id=creation['candidate_id'], candidate_creation_ordinal=creation['candidate_creation_ordinal'],
                candidate_creation_event_path=creation_ref['path'], candidate_creation_event_hash=creation_ref['hash'],
                path=creation['candidate_path'], hash=creation['candidate_hash'], disposition=event['new_disposition'],
                disposition_event_path=event_ref['path'], disposition_event_hash=event_ref['hash'],
                verification_decision_path=decision_ref['path'] if decision_ref else None,
                verification_decision_hash=decision_ref['hash'] if decision_ref else None,
                verification_decision_final=decision['decision_final'] if decision else None)
        report = dict(schema_version='terminal-report-v2', terminal_state=terminal,
            current_verified_draft_path=pointer['verified_draft_path'], current_verified_draft_hash=pointer['verified_draft_hash'],
            latest_candidate=projection,
            rejected_candidate_ids=[v.creation['candidate_id'] for v in views
                if v.effective_event['new_disposition'] == 'CANDIDATE_REJECTED'
                and not (stage == 'verifier' and v.creation == candidate)],
            outstanding_decision_ids=deepcopy(decision['outstanding_decision_ids']) if decision else [],
            apply_back_permitted=False, resume=dict(permitted=False, next_gate=None, reason=reason))
        proof.reader.suite.registry.validate(report, 'terminal_report_v2')
        validate_terminal(report, pointer, creation, creation_ref, event, event_ref, decision, decision_ref)
        return report

    def _record(self, proof, frames, index, stage, attempt, cause, candidate, active, stamp,
                *, suffix='', predecessor=None, transaction_order=None):
        frame = frames[index]; owner = frame['owner']; config = owner.binding.configuration
        directory = ROOT+f'/round-{owner.number}/{suffix}{stage}-{attempt}'
        order = ((owner.ordinal, STAGES.index(stage)+1, attempt) if transaction_order is None else
                 (owner.ordinal, 1, transaction_order, STAGES.index(stage)+1, attempt))
        existing = self._optional(directory+'/failure.json')
        committed = self._optional(directory+'/commit.json')
        if existing is not None:
            retained = decode_json(existing)
            proof.reader.suite.registry.validate(retained, 'convergence_failure_report')
            stamp = retained['generated_at']
        classification = cause['classification']
        terminal = 'HALTED_CLIENT_TIMEOUT' if classification == 'timeout' else 'HALTED_ARTIFACT_INVALID'
        reason = 'vnext_phase2_'+stage+'_'+classification
        if stage == 'candidate':
            reason = 'vnext_preservation_failed' if cause['deterministic_result'] == 'fail' else (
                'vnext_operator_decision_required' if cause['semantic_result'] == 'operator_decision_required' else 'vnext_semantic_rejected')
            terminal = {'vnext_preservation_failed':'HALTED_ARTIFACT_INVALID',
                        'vnext_operator_decision_required':'PAUSED_DECISION', 'vnext_semantic_rejected':'TARGET_NOT_REACHED'}[reason]
        if stamp is None:
            require(committed is None, 'committed correction failure lacks report')
            return dict(directory=directory, active=active, pending=True, committed=False,
                        reference=None, terminal_state=terminal, order=order)
        base = owner.proof; pointer = base.pointers[-1]
        normalized = draft_hash(base.values(base.latest)['base'].decode())
        prior = frames[:index+1]; rows = _latest_issues(prior, base.latest)
        require(not any(r['rubric_impact'] is not None or 'rubric_gaps.json' in r['affected_sections']
                        for f in prior if f.get('consumed') for r in f['review']['feedback']['feedback']),
                'correction failure cannot invent rubric-gap resolution')
        manifest = dict(schema_version='vnext-bound-rubric-v1', configuration=owner.binding.configuration_ref,
            workflow=config['workflow'], rubric_profile=config['rubric']['profile'], rubric_source=config['rubric']['source'],
            rubric_label=None, rubric_path=config['rubric']['artifact']['path'], rubric_content_hash=config['rubric']['artifact']['hash'],
            target_phase=config['target_phase'], target_mode=config['target_mode'])
        manifest_ref = _ref(directory+'/rubric_manifest.json', manifest)
        scheduler = deepcopy(owner.scheduler)
        feedback = frame['review']['feedback']['feedback']
        serious = [r for r in feedback if r['in_scope'] and r['normalized_severity'] in {'major','blocker'}]
        scheduler.record_result(frame['bound'].request['step']['profile'], blocker_count=len(serious), major_count=0)
        profiles = scheduler.status()
        latest = {f['bound'].request['step']['profile']: f for f in prior
                  if f.get('consumed') and f['bound'].request['base_pointer'] == base.latest}
        clean = {name for name, f in latest.items() if not any(r['in_scope'] and r['normalized_severity'] in {'major','blocker'}
                                                             for r in f['review']['feedback']['feedback'])}
        profiles['unverified_profiles'] = sorted({r['name'] for r in config['profiles']}-clean)
        def issues(severity):
            return [{k:deepcopy(r[k]) for k in ('issue_id','issue_fingerprint','normalized_severity','affected_sections','claim')}
                    for r in rows if r['normalized_severity'] == severity]
        failure = dict(terminal_state=terminal, generated_at=stamp, round_number=owner.number, draft_hash=normalized,
            final_draft_path=pointer['verified_draft_path'], final_declaration_path=None,
            target_phase=config['target_phase'], target_mode=config['target_mode'], workflow=config['workflow'],
            rubric_profile=config['rubric']['profile'], rubric_source=config['rubric']['source'], rubric_label=None,
            rubric_manifest_path=manifest_ref['path'], unresolved_blockers=issues('blocker'), unresolved_major_issues=issues('major'),
            unresolved_rubric_gaps=[], reviewer_final_status='not_run',
            last_accepted_draft_hash=draft_hash(proof.reader.raw(owner.entry.entry['current_verified_draft']).decode()),
            last_draft_hash=normalized, exit_reason=reason, recommendation='manual_review_required', profile_status=profiles,
            last_reviewer_findings=dict(round_number=owner.number, profile=frame['bound'].request['step']['profile'],
                blocker_count=sum(r['normalized_severity']=='blocker' for r in serious),
                major_count=sum(r['normalized_severity']=='major' for r in serious), feedback_ids=[r['feedback_id'] for r in serious]))
        job = proof.seed_values['job']; descriptor = self.run._record['descriptor']
        failure['run_artifact_pointers'] = dict(job_descriptor=dict(path=descriptor['path'], exists=True, sha256=descriptor['hash']),
            scope_contract=dict(path=job['scope_contract_path'], exists=job['scope_contract_path'] is not None, sha256=job['scope_contract_hash']))
        report = self._terminal(proof, frame, stage, candidate, terminal, reason, predecessor)
        assets = {directory+'/failure.json':canonical_json_bytes(failure), directory+'/terminal.json':canonical_json_bytes(report),
                  manifest_ref['path']:canonical_json_bytes(manifest)}
        error_ref = None
        if terminal in {'HALTED_CLIENT_TIMEOUT','HALTED_ARTIFACT_INVALID'}:
            role = stage if stage in {'editor','verifier'} else None
            outcomes = cause.get('outcomes', [])
            error = dict(terminal_state=terminal, generated_at=stamp, round_number=owner.number, phase='phase_2',
                profile=frame['bound'].request['step']['profile'], client_role=role,
                client=deepcopy(proof.seed_values['review'][role]) if role else None,
                failure_type='client_timeout' if classification=='timeout' else
                    'client_error' if classification in {'transport_failure','interrupted'} else 'artifact_validation',
                attempts=[dict(attempt_number=o['attempt'], artifact_name='proposed_patch.json' if role=='editor' else 'semantic_verification.json',
                    validation_errors=[o['error']], raw_response_path=cause['directory']+f"/attempts/{o['attempt']}/response.json" if o['response_hash'] else None)
                    for o in outcomes], retry_exhausted=len(outcomes)==2 or classification in {'invalid_proposal','invalid_semantic','assembly_invalid','rejected'},
                last_valid_draft_hash=normalized, last_valid_draft_path=pointer['verified_draft_path'], recommendation='manual_review_required')
            proof.reader.suite.registry.validate(error, 'vnext_correction_artifact_error_v1')
            error_ref = _ref(directory+'/error.json', error); assets[error_ref['path']] = canonical_json_bytes(error)
        proof.reader.suite.registry.validate(failure, 'convergence_failure_report')
        round_path = f'rounds/round-{owner.number}/proposal_input.json'
        packet = dict(schema_version='vnext-phase2-correction-failure-v1', round_number=owner.number, stage=stage, attempt=attempt,
            current_verified_pointer=base.latest, configuration=owner.binding.configuration_ref, entry=frame['bound'].request['entry'],
            review_request=frame['bound'].request_ref, round_input=dict(path=round_path, hash=sha256_bytes(self.store.read(round_path))),
            cause_hash=sha256_bytes(canonical_json_bytes(cause)),
            client_request=_ref(cause['directory']+'/request.json', cause['request']) if 'request' in cause else None,
            failure=_ref(directory+'/failure.json', failure), error=error_ref,
            terminal=_ref(directory+'/terminal.json', report), rubric_manifest=manifest_ref)
        proof.reader.suite.registry.validate(packet, SCHEMA)
        reference = _ref(directory+'/commit.json', packet); pending = False
        for path, value in [*assets.items(), (reference['path'], canonical_json_bytes(packet))]:
            observed = self._optional(path)
            require(observed is None or observed == value, 'correction failure differs from exact evidence replay', path)
            pending = pending or observed is None
        require(committed is None or not pending, 'committed correction failure lacks dependencies')
        return dict(directory=directory, packet=packet, assets=assets, reference=reference, committed=committed is not None,
                    pending=pending, active=active, terminal_state=terminal, order=order)

    def _transactions(self, proof, frame):
        """Follow explicit selected children; never infer a transaction from order."""
        number = frame['owner'].number
        journal = _HistoricalJournal(proof, lambda read: proof.admission.load_inputs(read, number))
        candidates = [c for c in proof.view.creations if c['round_number'] == number]
        from whetstone.vnext_phase2_operator import supported as operator_supported, pins as operator_pins
        if not operator_supported(proof.reader.suite):
            require(len(candidates) <= 1, 'Phase 2 correction followup reporting requires separate admission support')
            return [(journal, candidates[0] if candidates else None, None, '', None)]
        operator_pins(proof.reader.suite)
        from whetstone.vnext_verified_history import _VerifiedTransactions
        tasks = []; seen = set(); predecessor = None
        while True:
            transaction = journal.preflight.plan['transaction_id']
            require(transaction not in seen, 'cyclic Phase 2 correction transaction chain')
            seen.add(transaction)
            matches = [c for c in candidates if c['transaction_id'] == transaction]
            require(len(matches) <= 1, 'ambiguous Phase 2 transaction candidate')
            candidate = matches[0] if matches else None
            suffix = '' if not tasks else transaction+'--'
            tasks.append((journal, candidate, predecessor, suffix, len(tasks)))
            if candidate is None: break
            path = candidate['candidate_path'].rsplit('/', 1)[0]+'/followup_transaction.json'
            raw = self._optional(path)
            if raw is None: break
            selection = proof.reader.json(dict(path=path, hash=sha256_bytes(raw)), 'vnext_semantic_followup_selection_v1')
            require(selection['candidate_id'] == candidate['candidate_id'] and selection['job_id'] == candidate['job_id'],
                    'Phase 2 child selection belongs to another parent')
            router = _VerifiedTransactions(proof.store, original=proof.admission, selected_ref=selection['transaction_input'])
            record = router.selected_record(proof.store.read)
            require(record['source_creation'] == _ref(f"rounds/candidate_index/creation-{candidate['candidate_creation_ordinal']}.json", candidate),
                    'Phase 2 child selects another source creation')
            journal = _HistoricalJournal(proof, lambda read, r=router: r.load_inputs(read, number))
            predecessor = candidate
        require({c['candidate_id'] for _, c, _, _, _ in tasks if c} == {c['candidate_id'] for c in candidates},
                'Phase 2 candidate lacks its explicit predecessor selection')
        return tasks

    def _view_failures(self, proof, stamp=None):
        state = sequence(proof); records = []; expected = set(); recovery = None
        for index, frame in enumerate(state['frames']):
            owner = frame['owner']; number = owner.number
            if not frame.get('consumed') or self._optional(f'rounds/round-{number}/proposal_input.json') is None:
                continue
            tasks = self._transactions(proof, frame)
            for task_index, (journal, candidate, predecessor, suffix, transaction_order) in enumerate(tasks):
                header, outcomes, proposal, receipt = journal.inspect()
                current = (task_index == len(tasks)-1 and index == len(state['frames'])-1
                           and owner.proof.latest == proof.latest and state['gate'] == 'correction_required')
                def add(stage, attempt, cause, creation, active):
                    directory = ROOT+f'/round-{number}/{suffix}{stage}-{attempt}'
                    expected.add(directory)
                    present = self._optional(directory+'/failure.json') is not None or self._optional(directory+'/commit.json') is not None
                    # Partial directory publication is also a recovery claim.
                    try: present = present or bool(self.store.list_directory(directory))
                    except FileNotFoundError: pass
                    if present or active:
                        records.append(self._record(proof, state['frames'], index, stage, attempt, cause, creation, active, stamp,
                            suffix=suffix, predecessor=predecessor, transaction_order=transaction_order))
                def technical(stage, js, os, result, creation):
                    for count, outcome in enumerate(os, 1):
                        kind = outcome['classification']
                        if kind.startswith('valid_') or (kind=='shape_invalid' and count<2): continue
                        add(stage, count, dict(classification=kind, directory=js.directory, outcomes=os[:count],
                            request=decode_json(js.read('request.json')),
                            invocations=[decode_json(js.read(f"attempts/{o['attempt']}/invocation.json")) for o in os[:count]]), creation,
                            current and result is None and count==len(os))
                technical('editor', journal, outcomes, proposal, None)
                if receipt is not None:
                    path = f"rounds/round-{number}/proposals/{proposal.patch['proposal_id']}/assembly_failure.json"
                    raw = self._optional(path)
                    if raw is not None:
                        registry = proof.router.registry()
                        try: registry._material(number, proposal.patch['proposal_id'])
                        except CandidateAssemblyFailure as exc: expected_failure = exc.evidence
                        else: raise ValueError('assembly failure no longer reproduces')
                        require(raw == canonical_json_bytes(expected_failure) and candidate is None,
                                'assembly failure differs from evidence or fabricated registration')
                        add('assembly', 0, dict(classification='assembly_invalid', evidence=expected_failure), None, current)
                if candidate is not None:
                    router = proof.transactions(candidate['candidate_creation_ordinal'])
                    decision_owner = VerifiedSemanticDecisionJournal(router.registry(), admission=router)
                    view = decision_owner._state(candidate)[0]
                    if view.prepared and current: recovery = 'verification_commit_recovery_required'
                    if view.decision is not None and view.decision['deterministic_result']=='pass':
                        js = VerifiedSemanticRequestJournal(router.store, admission=router, candidate_id=candidate['candidate_id'])
                        _, os, result, _ = js.inspect()
                        technical('verifier', js, os, result, candidate)
                    if view.decision is not None and view.decision['decision_final'] and view.decision['candidate_disposition']=='CANDIDATE_REJECTED':
                        add('candidate', 0, dict(classification='rejected', **view.decision), candidate, current)
        try: rounds = self.store.list_directory(ROOT)
        except FileNotFoundError: rounds = ()
        for name, kind in rounds:
            if name.startswith('.vnext-tmp-'): continue
            require(kind=='directory' and any(p.startswith(ROOT+'/'+name+'/') for p in expected), 'unknown correction failure round')
            for leaf, leaf_kind in self.store.list_directory(ROOT+'/'+name):
                if leaf.startswith('.vnext-tmp-'): continue
                require(leaf_kind=='directory' and ROOT+'/'+name+'/'+leaf in expected, 'unknown correction failure claim')
        proof.guard(self.store.read); self.run._guard(self.store.read)
        return dict(state=state, records=records, active=next((r for r in reversed(records) if r['active']), None), recovery=recovery)

    def _sources(self):
        return {p:r for p,r in self.store.reads.items() if not p.startswith(ROOT+'/')
                and p not in {STATE_PATH,'rounds/artifact_validation_error.json','rounds/convergence_failure_report.json'}}

    def _barrier(self, token, snapshot):
        self.store.synchronize(token, snapshot, self.run._record['descriptor']['path'])

    def _projection(self, view):
        return dict(active=view['active']['reference'] if view['active'] and view['active']['committed'] else None,
                    history=[r['reference'] for r in view['records'] if r['committed']])

    def _public_failure(self, proof, view):
        from whetstone.vnext_phase2_report_projection import projections
        plan = projections(self, proof, correction=view)
        state = decode_json(self.store.read(STATE_PATH)); projection = self._projection(view)
        active = view['active']
        return dict(gate=view['recovery'] or ('correction_failure' if active else 'no_active_correction_failure'),
            terminal_state=active['terminal_state'] if active else None,
            committed=bool(active and active['committed']), active=projection['active'], history=projection['history'],
            publication_required=any(r['pending'] for r in view['records']), resume_permitted=False,
            state_current=state.get(STATE_FIELD)==projection if view['records'] else STATE_FIELD not in state,
            mirrors_current=all(self._optional(path)==target['raw'] for path,target in plan.items()), phase_complete=False)

    def status(self):
        proof=self._proof(self.store.read);work=self._observe(proof)
        if work.outcome!='work_available':return work
        view=self._view_failures(proof);result=self._public_failure(proof,view)
        self.store.check(self._sources());return result

    def publish(self):
        def perform(store,proof):
            stamp=datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
            view=self._view_failures(proof,stamp);snapshot=self._sources()
            self._barrier(store._token,snapshot)
            check=self._view_failures(proof,stamp)
            require([r['packet'] for r in check['records']]==[r['packet'] for r in view['records']], 'correction failure changed at barrier')
            for record in view['records']:
                for path,raw in record['assets'].items():store.publish(store._token,path,raw)
                self.store.check(snapshot)
                store.publish(store._token,record['reference']['path'],record['packet'])
            self.store.check(snapshot)
            return self._public_failure(proof,self._view_failures(proof))
        return self._execute(perform)

    def recover(self):
        def perform(store,proof):
            from whetstone.vnext_phase2_report_projection import recover_projections
            view=self._view_failures(proof)
            require(not any(r['pending'] for r in view['records']), 'publish correction failure before state recovery')
            self._barrier(store._token,self._sources())
            recover_projections(self,store,proof,correction=view)
            before=self.store.read(STATE_PATH);state=decode_json(before)
            if view['records']:state[STATE_FIELD]=self._projection(view)
            else:state.pop(STATE_FIELD,None)
            target=canonical_json_bytes(state) if state!=decode_json(before) else before
            snapshot=self._sources()
            def validate(read,path,raw):
                self.store.check(snapshot);proof.guard(read);self.run._guard(read)
                require(path==STATE_PATH and read(path)==before and raw==target,'correction state changed')
                require(self._projection(self._view_failures(proof))==self._projection(view),'correction evidence changed')
            if target!=before:self.store.materialize(store._token,STATE_PATH,target,validate_target=validate)
            else:self.store.synchronize_existing(store._token,STATE_PATH,expected=target)
            result=self._public_failure(proof,self._view_failures(proof))
            require(result['state_current'] and result['mirrors_current'],'correction failure recovery incomplete')
            return dict(result,gate='correction_failure_state_recovered')
        return self._execute(perform)

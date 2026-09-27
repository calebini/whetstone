"""Actual Phase 2 decisions and distinct child transactions under D8."""
from copy import deepcopy
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_vnext_verified_phase2_resolution as resolution
import test_vnext_verified_phase2_client as clients
import test_vnext_verified_history as history
from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_identity import binding_id
from whetstone.vnext_semantic_admission import load_registered_semantic_context
from whetstone.vnext_semantic_protocol import RULES
from whetstone.vnext_verified_history import _VerifiedAnswerSource
from vnext_fixtures import STAMP


@unittest.skipUnless(sys.platform == 'darwin', 'D8 targets local macOS/APFS')
class Phase2OperatorTests(unittest.TestCase):
    setUpClass = resolution.ResolutionRuntimeTests.setUpClass
    fixture = resolution.ResolutionRuntimeTests.fixture
    ready = resolution.ResolutionRuntimeTests.ready
    config = resolution.ResolutionRuntimeTests.config
    files = resolution.ResolutionRuntimeTests.files
    reopen = resolution.ResolutionRuntimeTests.reopen
    review = resolution.ResolutionRuntimeTests.review
    promote = resolution.ResolutionRuntimeTests.promote
    next_client = resolution.ResolutionRuntimeTests.next_client
    advance = resolution.ResolutionRuntimeTests.advance
    advice = resolution.ResolutionRuntimeTests.advice
    candidate = resolution.ResolutionRuntimeTests.candidate
    response = resolution.ResolutionRuntimeTests.response
    corrected = resolution.ResolutionRuntimeTests.corrected

    def start(self, **kwargs):
        return clients.VerifiedPhase2ClientTests.start(self, phase2_operator_contract=True, **kwargs)

    def question(self):
        unit = history.verified.fixtures.fixtures.UnitPreflightTests
        setup = unit.setUp
        def with_authority(test):
            setup(test)
            fixture = test.c.f
            reference = fixture.save('inputs/waiting-authority.md', b'Queue waiting applies to each work start.\n')
            target = next(r for r in fixture.authority['bindings'] if r['role'] == 'mutable_target')
            authority = dict(path=reference['path'], content_hash=reference['hash'], role='normative_authority',
                authority_scopes=target['authority_scopes'], effective_horizon='current', mutable=False,
                may_introduce_requirements=True)
            authority['binding_id'] = binding_id(authority)
            fixture.authority['bindings'].append(authority)
            fixture.authority['precedence'] = [dict(authority_scope=scope,
                ordered_binding_ids=[authority['binding_id'], target['binding_id']], conflict_policy='pause')
                for scope in target['authority_scopes']]
            fixture.rebind()
        with patch.object(unit, 'setUp', with_authority):
            f, reviewer, _ = self.ready()
        result = f.run.run_phase2_review(client=reviewer); f.run.consume_phase2_result()
        from types import SimpleNamespace
        from whetstone.vnext_verified_phase2_review import INPUT_PATH
        bound = SimpleNamespace(inputs=json.loads(f.store.read(INPUT_PATH)))
        f.run.bind_phase2_advice(self.advice(bound, result))
        reference = f.run.admit_phase2_round()
        number = json.loads(f.store.read(reference['path']))['round_number']
        creation, verifier = self.candidate(f, number)
        context = load_registered_semantic_context(f.store, admission=f.run._history(), candidate_id=creation['candidate_id'])
        packet = context.packet
        target = next(r for r in packet['authority_map']['bindings'] if r['role'] == 'mutable_target')
        authority = next(r for r in packet['dependency_context'] if r['binding']['role'] == 'normative_authority')
        def alternative(identifier, text, interpretation):
            return dict(authority_binding_id=identifier, interpretation=interpretation,
                evidence=dict(byte_start=0, byte_end=len(text.encode()), content_hash=sha256_bytes(text.encode()), text=text))
        response = json.loads(verifier.valid)
        response.update(authority_compliance='uncertain', operator_decision_required=True,
            verdict='operator_decision_required', authority_choice=dict(question='Which interpretation should a new transaction address?',
                authority_scope=target['authority_scopes'][0], alternatives=[
                    alternative(target['binding_id'], packet['seed'], 'Waiting is scoped to queue startup.'),
                    alternative(authority['binding']['binding_id'], authority['content'], 'Waiting is scoped to each work start.')]),
            uncertainty_resolutions=[dict(field_path='authority_compliance', policy_rule_id=RULES['authority_choice'],
                disposition='operator_decision_required', decision_id=None)])
        verifier.responses = [canonical_json_bytes(response)]
        final = f.run.verify(client=verifier, decided_at=STAMP)
        self.assertEqual(final.value.decision['semantic_result'], 'operator_decision_required')
        source = _VerifiedAnswerSource(f.store, admission=f.run._history(), candidate_id=creation['candidate_id'], require_current=True)
        return f, reviewer, verifier, creation, number, history.answers.input_for(source)

    def test_phase2_answer_selects_distinct_child_and_resolves_only_after_promotion(self):
        f, reviewer, verifier, parent, number, answer = self.question()
        parent_report = f.run.publish_phase2_correction_failure()
        self.assertEqual(parent_report['terminal_state'], 'PAUSED_DECISION')
        f.run.reconcile_phase2_correction_failure_state()
        head = f.store.read('rounds/current_verified.json')
        before = self.files(f)
        preview = f.run.submit_answer(packet=answer, dry_run=True)
        self.assertEqual(self.files(f), before)
        recorded = f.run.submit_answer(packet=answer)
        self.assertEqual(recorded.value, preview.value)
        selected = f.run.select_followup(candidate_id=parent['candidate_id'], answer_reference=recorded.value['reference']).value
        self.assertEqual(f.store.read('rounds/current_verified.json'), head)
        self.reopen(f)
        saved = self.files(f)
        child_editor = history.verified.fixtures.Client()
        self.assertEqual(f.run.request(round_number=number, client=child_editor, selected_ref=selected).value.status, 'complete')
        child = f.run.register(round_number=number, created_at=STAMP, selected_ref=selected).value
        self.assertNotEqual(child['transaction_id'], parent['transaction_id'])
        context = load_registered_semantic_context(f.store, admission=f.run._history(), candidate_id=child['candidate_id'])
        self.assertIn('phase2', context.packet)
        child_verifier = history.verified.semantic.Client(context)
        self.assertTrue(f.run.verify(client=child_verifier, decided_at=STAMP).value.decision['promotion_permitted'])
        self.assertEqual(f.run.promote(prepared_at=STAMP).outcome, 'promoted')
        f.run.publish_phase2_resolutions(); f.run.reconcile_phase2_resolution_state()
        self.reopen(f)
        self.assertEqual(f.run.phase2_sequence_status()['gate'], 'review')
        self.advance(f, self.next_client(reviewer))
        status = f.run.phase2_correction_failure_status()
        self.assertIsNone(status['terminal_state'])
        self.assertIn(parent_report['active'], status['history'])
        for path, raw in saved.items():
            if path not in {'spec.md', 'rounds/current_verified.json', 'rounds/run_state.json'}:
                self.assertEqual(f.store.read(path), raw, path)
        self.assertEqual((reviewer.calls, f.editor.calls, verifier.calls, child_editor.calls, child_verifier.calls), (1,1,1,1,1))

    def choice(self):
        f, reviewer, _ = self.ready()
        result = f.run.run_phase2_review(client=reviewer); f.run.consume_phase2_result()
        from types import SimpleNamespace
        from whetstone.vnext_verified_phase2_review import INPUT_PATH
        advice = self.advice(SimpleNamespace(inputs=json.loads(f.store.read(INPUT_PATH))), result)
        advice['findings'][0]['requested_effects'] = ['weaken']
        f.run.bind_phase2_advice(advice)
        context = f.run.phase2_operator_context()
        self.assertEqual(context['findings'][0]['classification'], 'operator_decision_required')
        options = dict(schema_version='vnext-operator-options-v1',
            **{k:context[k] for k in ('job_id', 'round_number', 'review_result')},
            choices=[dict(finding_id=context['findings'][0]['finding_id'], options=[
                dict(option_id='clarify', description='Clarify the existing requirement without weakening it.',
                    authorized_effects=['clarification'], authorized_deletion_unit_ids=[], authorized_unit_effects=[]),
                dict(option_id='defer', description='Keep the choice unresolved.',
                    authorized_effects=[], authorized_deletion_unit_ids=[], authorized_unit_effects=[])])])
        return f, reviewer, context, options

    def selection(self, f, context, request, option='clarify'):
        return dict(schema_version='vnext-operator-response-input-v1',
            **{k:context[k] for k in ('job_id','round_number','review_result')}, selections=[dict(request=request,
                selected_option_id=option, rationale='Fictional explicit operator choice.', decided_by='fixture operator', decided_at=STAMP)])

    def test_explicit_choice_admits_derived_work_but_retains_original_debt(self):
        f, reviewer, context, options = self.choice()
        before = self.files(f)
        preview = f.run.prepare_phase2_operator_requests(options, dry_run=True)
        self.assertEqual(self.files(f), before)
        requests = f.run.prepare_phase2_operator_requests(options)
        self.assertEqual(requests, preview)
        packet = self.selection(f, context, requests[0]['request'])
        before = self.files(f)
        preview = f.run.submit_phase2_operator_responses(packet, dry_run=True)
        self.assertEqual(self.files(f), before)
        selected = f.run.submit_phase2_operator_responses(packet)
        self.assertEqual(selected, preview)
        self.assertEqual(f.run.phase2_sequence_status()['gate'], 'operator_or_advice_required')
        reference = f.run.admit_phase2_operator_round(selected['selection'])
        self.assertEqual(f.run.admit_phase2_operator_round(selected['selection']), reference)
        self.assertEqual((reviewer.calls, f.editor.calls), (1,0))
        self.reopen(f)
        creation, verifier = self.candidate(f, context['round_number'])
        packet = load_registered_semantic_context(f.store, admission=f.run._history(), candidate_id=creation['candidate_id']).packet
        self.assertNotEqual(packet['admitted_findings'][0]['finding_id'], context['findings'][0]['finding_id'])
        self.assertEqual(packet['admitted_findings'][0]['original_finding']['classification'], 'operator_decision_required')
        f.run.verify(client=verifier, decided_at=STAMP); f.run.promote(prepared_at=STAMP)
        status = f.run.publish_phase2_resolutions()
        record = status['records'][0]
        summary = json.loads(f.store.read(record['packet']['summary']['path']))
        self.assertEqual(summary['resolved_issue_ids'], [])
        self.assertEqual(summary['unresolved_issue_ids'], [context['findings'][0]['finding_id']])
        self.assertEqual(record['packet']['reset_opposition_keys'], [])
        self.assertEqual(f.run.phase2_sequence_status()['gate'], 'review')
        self.assertEqual((reviewer.calls, f.editor.calls, verifier.calls), (1,1,1))
        self.advance(f, self.next_client(reviewer))
        self.advance(f, self.next_client(reviewer))
        package = f.run.prepare_phase2_declaration()
        self.assertEqual(package['declaration']['counts']['major_issues'], 1)
        with self.assertRaisesRegex(ValueError, 'unresolved serious debt'):
            f.run.bind_phase2_next_review(reviewer.transport_binding)

    def test_decline_stale_sources_and_unselected_response_cannot_admit(self):
        f, reviewer, context, options = self.choice()
        bad = deepcopy(options); bad['review_result']['hash'] = 'f'*64
        before = self.files(f)
        with self.assertRaises(ValueError): f.run.prepare_phase2_operator_requests(bad)
        self.assertEqual(self.files(f), before)
        request = f.run.prepare_phase2_operator_requests(options)[0]['request']
        selected = f.run.submit_phase2_operator_responses(self.selection(f, context, request, 'defer'))
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'deferred blocking choice'):
            f.run.admit_phase2_operator_round(selected['selection'])
        with self.assertRaises(ValueError): f.run.admit_phase2_round()
        self.assertEqual(self.files(f), before)
        self.assertEqual(f.run.phase2_sequence_status()['gate'], 'operator_or_advice_required')
        self.assertEqual((reviewer.calls, f.editor.calls), (1,0))

    def test_request_response_selection_and_admission_lost_ack_recover_without_clients(self):
        f, reviewer, context, options = self.choice()
        def interrupted(suffix, action):
            publish = f.store.publish
            fired = False
            def stop(token, path, value):
                nonlocal fired
                result = publish(token, path, value)
                if not fired and suffix in path:
                    fired = True
                    raise OSError('operator lost acknowledgement')
                return result
            with patch.object(f.store, 'publish', side_effect=stop):
                with self.assertRaisesRegex(OSError, 'operator lost acknowledgement'): action()
            self.assertTrue(fired)
            self.reopen(f)
            return action()
        request = interrupted('/operator_decisions/', lambda:f.run.prepare_phase2_operator_requests(options))[0]['request']
        packet = self.selection(f, context, request)
        selected = interrupted('/responses/', lambda:f.run.submit_phase2_operator_responses(packet))
        selected = interrupted('/selections/', lambda:f.run.submit_phase2_operator_responses(packet))
        reference = interrupted('/proposal_input.json', lambda:f.run.admit_phase2_operator_round(selected['selection']))
        before = self.files(f)
        self.assertEqual(f.run.admit_phase2_operator_round(selected['selection']), reference)
        self.assertEqual(self.files(f), before)
        self.assertEqual((reviewer.calls, f.editor.calls), (1,0))

    def test_later_review_operator_admission_is_bound_to_its_exact_request(self):
        f, reviewer, _ = self.ready()
        reviewer.callback = lambda client, packet: canonical_json_bytes({**packet, 'feedback':[]})
        f.run.run_phase2_review(client=reviewer); f.run.consume_phase2_result()
        later = self.next_client(reviewer, clean=False)
        bound, result, _ = self.advance(f, later)
        advice = self.advice(bound, result)
        advice['findings'][0]['requested_effects'] = ['weaken']
        f.run.continue_phase2_pass(2, action='advice', advice=advice)
        context = f.run.phase2_operator_context()
        options = dict(schema_version='vnext-operator-options-v1',
            **{k:context[k] for k in ('job_id', 'round_number', 'review_result')},
            choices=[dict(finding_id=context['findings'][0]['finding_id'], options=[dict(option_id='clarify',
                description='Clarify without weakening.', authorized_effects=['clarification'],
                authorized_deletion_unit_ids=[], authorized_unit_effects=[])])])
        request = f.run.prepare_phase2_operator_requests(options)[0]['request']
        selected = f.run.submit_phase2_operator_responses(self.selection(f, context, request))
        reference = f.run.admit_phase2_operator_round(selected['selection'])
        self.reopen(f)
        inputs = f.run._history().load_inputs(f.store.read, context['round_number'])
        self.assertEqual(inputs['phase2']['request'], bound.request)
        self.assertEqual(inputs['feedback_ref'], result.receipt['feedback'])
        self.assertEqual(json.loads(f.store.read(reference['path']))['decision_refs'], selected['content']['decision_refs'])
        self.assertEqual((reviewer.calls, later.calls, f.editor.calls), (1,1,0))

    def test_choice_source_drift_and_ownership_loss_leave_no_authorized_round(self):
        from whetstone.vnext_local_storage import OwnershipLost
        f, reviewer, context, options = self.choice()
        sync = f.store.synchronize_existing
        request_path = 'rounds/phase2/review_requests/first/request.json'
        original = f.store.read(request_path)
        def drift(token, path, *, expected):
            result = sync(token, path, expected=expected)
            if path == request_path:
                (f.root/path).write_bytes(original+b' ')
            return result
        with patch.object(f.store, 'synchronize_existing', side_effect=drift):
            with self.assertRaises(ValueError): f.run.prepare_phase2_operator_requests(options)
        self.assertFalse(list(f.root.glob('rounds/round-*/operator_decisions')))
        (f.root/request_path).write_bytes(original)
        publish = f.store.publish
        def lose(token, path, value):
            result = publish(token, path, value)
            if '/operator_decisions/' in path: f.store._invalidate()
            return result
        with patch.object(f.store, 'publish', side_effect=lose):
            with self.assertRaises(OwnershipLost): f.run.prepare_phase2_operator_requests(options)
        self.reopen(f)
        requests = f.run.prepare_phase2_operator_requests(options)
        self.assertEqual(len(requests),1)
        self.assertFalse(f.run.phase2_operator_context()['admitted'])
        self.assertEqual((reviewer.calls, f.editor.calls), (1,0))

    def test_unpinned_operator_surface_refuses_without_writes(self):
        with patch.object(self, 'start', side_effect=lambda **kwargs: clients.VerifiedPhase2ClientTests.start(
                self, phase2_resolution_contract=True, **kwargs)):
            f, _, _ = self.ready()
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'operator integration is outside supported suite'):
            f.run.phase2_operator_context()
        self.assertEqual(self.files(f), before)

    def test_fresh_process_replays_selected_decisions_without_writes(self):
        f, reviewer, context, options = self.choice()
        request = f.run.prepare_phase2_operator_requests(options)[0]['request']
        selection = f.run.submit_phase2_operator_responses(self.selection(f, context, request))
        f.run.admit_phase2_operator_round(selection['selection'])
        script = """import json,sys
from pathlib import Path
from whetstone import vnext_registry
from whetstone.vnext_contracts import ALGORITHM_VERSIONS
from whetstone.vnext_verified_run import open_verified_run
root,suite,number=sys.argv[1:]
manifest=json.loads(Path(suite).read_bytes());job=json.loads((Path(root)/'job_descriptor.json').read_bytes())
vnext_registry.SUPPORTED_SUITES[manifest['suite_version']]=manifest['suite_digest']
vnext_registry.SUITE_ALGORITHM_VERSIONS[manifest['suite_version']]={k:job[k] for k in ALGORITHM_VERSIONS}
with open_verified_run(root,suite_path=suite) as run:
    inputs=run._history().load_inputs(run.store.read,int(number))
    print(json.dumps(dict(gate=run.phase2_sequence_status()['gate'],decisions=len(inputs['decisions']),
        round_number=inputs['phase2']['request']['round_number'])))
"""
        before = self.files(f)
        child = subprocess.run([sys.executable, '-c', script, str(f.root), str(f.admission.suite_path), str(context['round_number'])],
            capture_output=True, timeout=120)
        self.assertEqual(child.returncode, 0, child.stderr.decode())
        self.assertEqual(json.loads(child.stdout), dict(gate='correction_required', decisions=1, round_number=context['round_number']))
        self.assertEqual(self.files(f), before)
        self.assertEqual((reviewer.calls, f.editor.calls), (1,0))

    def test_status_lists_exact_retained_choices_without_selecting_or_repairing(self):
        f, reviewer, context, options = self.choice()
        request = f.run.prepare_phase2_operator_requests(options)[0]['request']
        declined = f.run.submit_phase2_operator_responses(self.selection(f, context, request, 'defer'))
        selected = f.run.submit_phase2_operator_responses(self.selection(f, context, request))
        before = self.files(f)
        with patch.object(f.store, 'locked', side_effect=AssertionError('read-only status took a fence')):
            status = f.run.phase2_operator_context()
        self.assertEqual(status['requests'][0]['request'], request)
        self.assertEqual(status['selections'], sorted([declined['selection'], selected['selection']], key=lambda r:r['path']))
        self.assertFalse(status['admitted']); self.assertFalse(status['resume']['permitted'])
        self.assertEqual(status['gate'], 'operator_or_advice_required')
        self.assertEqual(self.files(f), before)
        foreign = f.root/request['path']; raw = foreign.read_bytes(); foreign.write_bytes(raw+b' ')
        before = self.files(f)
        with self.assertRaises(ValueError): f.run.phase2_operator_context()
        self.assertEqual(self.files(f), before)
        self.assertEqual((reviewer.calls, f.editor.calls), (1,0))

    def test_original_resolution_cannot_rewrite_pre_promotion_issue_history(self):
        from whetstone.vnext_verified_phase2_sequence import _Continuation, sequence
        from whetstone.vnext_verified_phase2_closeout import _latest_issues
        f, _, _, _, _, _ = self.corrected()
        f.run.publish_phase2_resolutions()
        owner = _Continuation(f.run); proof = owner._proof(f.store.read)
        proof.inspect_registry()
        state = sequence(proof)
        frame = state['frames'][0]
        prior = _latest_issues(state['frames'], frame['bound'].request['base_pointer'])
        current = _latest_issues(state['frames'], state['reference'])
        self.assertEqual(len(prior), 2)
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0]['normalized_severity'], 'minor')
        self.assertEqual(prior, sorted(frame['review']['feedback']['feedback'], key=lambda r:r['issue_id']))

    def test_selected_child_timeout_reports_separately_and_recovers_publication(self):
        f, reviewer, verifier, parent, number, answer = self.question()
        old = f.run.publish_phase2_correction_failure()
        old_path = old['active']['path']; old_raw = f.store.read(old_path)
        receipt = f.run.submit_answer(packet=answer).value['reference']
        selected = f.run.select_followup(candidate_id=parent['candidate_id'], answer_reference=receipt).value
        def timeout(packet): raise TimeoutError('selected child timeout')
        child = history.verified.fixtures.Client(timeout)
        self.assertEqual(f.run.request(round_number=number, client=child, selected_ref=selected).value.status, 'timeout')
        before = self.files(f)
        status = f.run.phase2_correction_failure_status()
        self.assertEqual(status['terminal_state'], 'HALTED_CLIENT_TIMEOUT')
        self.assertEqual(self.files(f), before)
        publish = f.store.publish
        fired = False
        def lose(token, path, value):
            nonlocal fired
            result = publish(token, path, value)
            if '--editor-1/commit.json' in path and not fired:
                fired = True
                raise OSError('child report lost acknowledgement')
            return result
        with patch.object(f.store, 'publish', side_effect=lose):
            with self.assertRaisesRegex(OSError, 'child report lost acknowledgement'):
                f.run.publish_phase2_correction_failure()
        self.assertTrue(fired)
        self.reopen(f)
        current = f.run.publish_phase2_correction_failure()
        self.assertNotEqual(current['active'], old['active'])
        self.assertEqual(len(current['history']), 2)
        self.assertEqual(f.store.read(old_path), old_raw)
        f.run.reconcile_phase2_correction_failure_state()
        self.assertEqual((reviewer.calls, f.editor.calls, verifier.calls, child.calls), (1,1,1,1))


if __name__ == '__main__': unittest.main()

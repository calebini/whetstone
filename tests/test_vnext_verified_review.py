"""Production V sequence/admission with fictional clients and test-only suites."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_proposal_run import RUN_INPUT_PATH, run_input_record
from whetstone.vnext_semantic_admission import load_registered_semantic_context
from whetstone.vnext_verified_run import VerifiedRun, open_verified_run
from vnext_fixtures import STAMP
import test_vnext_verified_history as history
import test_vnext_verified_review_requests as journal
import test_vnext_unit_preflight as unit


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class VerifiedReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): history.VerifiedHistoryTests.setUpClass()
    files = history.VerifiedHistoryTests.files

    def fixture(self, *, budget=3, profiles=None, mode='horizontal', focused_profile=None, focused_contract=False, sequence_contract=True, status_contract=False,
                closeout_contract=False, operator_status_contract=False, phase2_eligibility_contract=False,
                phase2_binding_contract=False, phase2_entry_contract=False, phase2_review_contract=False, phase2_client_contract=False, phase2_consumption_contract=False, phase2_advice_contract=False, phase2_round_contract=False, phase2_sequence_contract=False, phase2_closeout_contract=False, phase2_findings_contract=False, phase2_blocked_contract=False, phase2_termination_contract=False, phase2_failure_contract=False, phase2_correction_failure_contract=False, phase2_signals_contract=False, phase2_resolution_contract=False, phase2_operator_contract=False, phase2_repair_contract=False, phase2_source_correction_contract=False, phase2_review_only_contract=False, phase2_rubric_contract=False, phase2_targets_contract=False, phase2_gap_acceptance_contract=False):
        phase2_targets_contract = phase2_targets_contract or phase2_gap_acceptance_contract
        phase2_rubric_contract = phase2_rubric_contract or phase2_targets_contract
        phase2_source_correction_contract = phase2_source_correction_contract or phase2_review_only_contract or phase2_rubric_contract
        phase2_operator_contract = phase2_operator_contract or phase2_repair_contract or phase2_source_correction_contract
        phase2_resolution_contract = phase2_resolution_contract or phase2_operator_contract
        phase2_signals_contract = phase2_signals_contract or phase2_resolution_contract
        phase2_correction_failure_contract = phase2_correction_failure_contract or phase2_signals_contract
        phase2_failure_contract = phase2_failure_contract or phase2_correction_failure_contract
        phase2_termination_contract = phase2_termination_contract or phase2_failure_contract
        phase2_findings_contract = phase2_findings_contract or phase2_blocked_contract or phase2_termination_contract
        phase2_closeout_contract = phase2_closeout_contract or phase2_findings_contract
        phase2_sequence_contract = phase2_sequence_contract or phase2_closeout_contract
        phase2_round_contract = phase2_round_contract or phase2_sequence_contract
        phase2_advice_contract = phase2_advice_contract or phase2_round_contract
        phase2_consumption_contract = phase2_consumption_contract or phase2_advice_contract
        phase2_client_contract = phase2_client_contract or phase2_consumption_contract
        phase2_review_contract = phase2_review_contract or phase2_client_contract
        phase2_entry_contract = phase2_entry_contract or phase2_review_contract
        phase2_binding_contract = phase2_binding_contract or phase2_entry_contract
        phase2_eligibility_contract = phase2_eligibility_contract or phase2_binding_contract
        operator_status_contract = operator_status_contract or phase2_eligibility_contract
        closeout_contract = closeout_contract or operator_status_contract
        original = unit.UnitPreflightTests.setUp
        def setup(owner):
            original(owner)
            source = owner.c.f
            source.original.review['profiles'] = profiles or [{'name': 'structural_integrity', 'budget': budget}]
            source.original.review['review_mode'] = mode
            if focused_profile is not None:
                source.original.review.update(schema_version='review-configuration-v2',
                    phase1_selection=dict(kind='focused', profile=focused_profile))
            source.original.review_ref = source.save('inputs/review.json', source.original.review)
            source.job['review_configuration_hash'] = source.original.review_ref['hash']
            source.rebind()
        algorithms = ('vnext_verified_materialization_v1', 'vnext_verified_promotion_v1',
            'vnext_verified_work_v1', 'vnext_verified_operator_v1', 'vnext_verified_run_v1',
            'vnext_verified_review_requests_v1')
        if focused_contract: algorithms += ('vnext_verified_focused_phase1_v1',)
        if sequence_contract: algorithms += ('vnext_verified_review_sequence_v1',)
        if status_contract: algorithms += ('vnext_verified_phase1_status_v1',)
        if closeout_contract: algorithms += ('vnext_verified_phase1_closeout_v1',)
        if operator_status_contract: algorithms += ('vnext_verified_phase1_operator_v1',)
        if phase2_eligibility_contract: algorithms += ('vnext_verified_phase2_eligibility_v1',)
        if phase2_binding_contract: algorithms += ('vnext_verified_phase2_binding_v1',)
        if phase2_entry_contract: algorithms += ('vnext_verified_phase2_entry_v1',)
        if phase2_review_contract: algorithms += ('vnext_verified_phase2_review_v1',)
        if phase2_client_contract: algorithms += ('vnext_verified_phase2_client_v1',)
        if phase2_consumption_contract: algorithms += ('vnext_verified_phase2_consumption_v1',)
        if phase2_closeout_contract: algorithms += ('vnext_verified_phase2_closeout_v1',)
        if phase2_findings_contract: algorithms += ('vnext_verified_phase2_findings_v1',)
        if phase2_blocked_contract: algorithms += ('vnext_verified_phase2_blocked_v1',)
        if phase2_operator_contract: algorithms += ('vnext_verified_phase2_operator_v1',)
        if phase2_repair_contract: algorithms += ('vnext_verified_phase2_repair_v1',)
        if phase2_source_correction_contract: algorithms += ('vnext_verified_phase2_source_correction_v1',)
        if phase2_review_only_contract: algorithms += ('vnext_verified_phase2_review_only_v1',)
        if phase2_rubric_contract: algorithms += ('vnext_verified_phase2_rubric_v1',)
        if phase2_targets_contract: algorithms += ('vnext_verified_phase2_targets_v1',)
        if phase2_gap_acceptance_contract: algorithms += ('vnext_verified_phase2_gap_acceptance_v1',)
        if phase2_resolution_contract: algorithms += ('vnext_verified_phase2_resolution_v1',)
        if phase2_signals_contract: algorithms += ('vnext_verified_phase2_signals_v1',)
        if phase2_correction_failure_contract: algorithms += ('vnext_verified_phase2_correction_failure_v1',)
        if phase2_failure_contract: algorithms += ('vnext_verified_phase2_failure_v1',)
        if phase2_termination_contract: algorithms += ('vnext_verified_phase2_termination_v1',)
        if phase2_sequence_contract: algorithms += ('vnext_verified_phase2_sequence_v1',)
        if phase2_round_contract: algorithms += ('vnext_verified_phase2_round_v1',)
        if phase2_advice_contract: algorithms += ('vnext_verified_phase2_advice_v1', 'vnext_mutation_preparation_v1')
        with patch.object(unit.UnitPreflightTests, 'setUp', setup):
            f = history.VerifiedHistoryTests.fixture(self, extra_algorithms=algorithms,
                extra_schemas={'vnext_review_request_v2'} | ({'review_configuration_v2','vnext_verified_phase1_closeout_v2','technical_failure_report','editor_summary'} if focused_profile is not None else set()) | ({'vnext_phase2_gap_acceptance_v1','vnext_phase2_declaration_v3','vnext_phase2_finding_reconciliation_v2'} if phase2_gap_acceptance_contract else set()) | ({'vnext_phase2_configuration_v2','vnext_phase2_declaration_v2','vnext_phase2_review_request_v6','vnext_phase2_consumption_v6','vnext_phase2_halt_evidence_v1','vnext_phase2_failure_closeout_v2'} if phase2_targets_contract else set()) | ({'vnext_phase2_rubric_response_v1'} if phase2_rubric_contract else set()) | ({'vnext_phase2_review_request_v5','vnext_phase2_consumption_v5'} if phase2_review_only_contract else set()) | ({'vnext_phase2_review_request_v4','vnext_phase2_consumption_v4'} if phase2_source_correction_contract else set()) | ({'vnext_phase2_repair_request_v1','vnext_phase2_repair_input_v1'} if phase2_repair_contract else set()) | ({'vnext_operator_options_v1','vnext_operator_response_input_v1','vnext_operator_selection_v1'} if phase2_operator_contract else set()) | ({'vnext_phase2_resolution_v1','vnext_phase2_resolution_summary_v1'} if phase2_resolution_contract else set()) | ({'vnext_phase2_signals_v1','oscillation_report','conflict_report','conflict_state'} if phase2_signals_contract else set()) | ({'vnext_phase2_correction_failure_v1','vnext_correction_artifact_error_v1'} if phase2_correction_failure_contract else set()) | ({'vnext_phase2_reviewer_failure_v1','artifact_validation_error'} if phase2_failure_contract else set()) | ({'vnext_phase2_failure_closeout_v1','convergence_failure_report'} if phase2_termination_contract else set()) | ({'vnext_phase2_blocked_report_v1'} if phase2_blocked_contract else set()) | ({'vnext_phase2_finding_reconciliation_v1','vnext_phase2_closeout_v2'} if phase2_findings_contract else set()) | ({'vnext_phase2_declaration_v1','vnext_phase2_closeout_v1',
                    'vnext_phase2_review_request_v3','vnext_phase2_consumption_v3','unresolved_issues','rubric_gaps'} if phase2_closeout_contract else set()) | ({'vnext_phase2_review_request_v2','vnext_phase2_consumption_v2'} if phase2_sequence_contract else set()) | ({'vnext_verified_phase1_closeout_v1'} if closeout_contract else set())
                    | ({'vnext_phase2_configuration_v1', 'vnext_phase2_entry_request_v1'} if phase2_binding_contract else set())
                    | ({'vnext_phase2_entry_v1'} if phase2_entry_contract else set())
                    | ({'vnext_phase2_review_request_v1', 'phase2_reviewer_feedback_input', 'controlled_vocabulary'} if phase2_review_contract else set())
                    | ({'vnext_phase2_review_result_v1','phase2_reviewer_feedback'} if phase2_client_contract else set())
                    | ({'vnext_phase2_consumption_v1'} if phase2_consumption_contract else set())
                    | ({'vnext_phase2_advice_binding_v1'} if phase2_advice_contract else set()),
                register_candidate=False)
        refs = f.admission._refs
        constraints = json.loads(f.store.read(refs['rounds'][1]['path']))['constraints']
        def save(token, path, value):
            raw = canonical_json_bytes(value); f.store.publish(token, path, raw)
            return dict(path=path, hash=sha256_bytes(raw))
        with f.store.locked(f.admission.validate_authority) as token:
            limits = save(token, 'inputs/mutation_constraints.json', dict(schema_version='vnext-mutation-constraints-v1', constraints=constraints))
            package = save(token, 'inputs/proposal_package.json', dict(schema_version='vnext-proposal-package-v1',
                job_descriptor=refs['descriptor'], review_configuration=refs['review'], mutation_constraints=limits))
            record = run_input_record(json.loads(f.store.read_descriptor()), dict(descriptor_ref=refs['descriptor'],
                review_ref=refs['review'], seed_map_ref=refs['seed_map'], round_refs={}, launch_package_ref=package))
            f.store.publish(token, RUN_INPUT_PATH, record)
        f.run = VerifiedRun(f.store, suite_path=f.admission.suite_path)
        return f

    def start(self, **options):
        f = self.fixture(**options)
        reviewer = journal.Reviewer(f)
        self.assertEqual(f.run.review_next(client=reviewer).outcome, 'materialization_recovered')
        self.assertEqual(reviewer.calls, 0)
        return f, reviewer

    def review(self, f, reviewer):
        self.assertEqual(f.run.review_next(client=reviewer).status, 'complete')
        self.assertEqual(f.run.review_status().status, 'finding_admission')
        return f.run.admit_reviewed_round()

    def promote(self, f):
        self.assertEqual(f.run.request(round_number=1, client=f.editor).value.status, 'complete')
        f.creation = f.run.register(round_number=1, created_at=STAMP).value
        f.identifier = f.creation['candidate_id']
        context = load_registered_semantic_context(f.store, admission=f.run._history(), candidate_id=f.identifier)
        verifier = history.verified.semantic.Client(context)
        self.assertTrue(f.run.verify(client=verifier, decided_at=STAMP).value.decision['promotion_permitted'])
        self.assertEqual(f.run.review_next().outcome, 'promotion_required')
        self.assertEqual(f.run.promote(prepared_at=STAMP).current_pointer['promotion_ordinal'], 1)
        return verifier

    def reopen(self, f):
        f.store.close()
        f.run = open_verified_run(f.root, suite_path=f.admission.suite_path)
        f.store = f.run.store
        self.addCleanup(f.run.close)

    def test_production_round_admission_promotion_and_new_base_review_reopen(self):
        f, reviewer = self.start()
        root_record = f.store.read(RUN_INPUT_PATH)
        first = self.review(f, reviewer)
        self.assertEqual(first['path'], 'rounds/round-1/proposal_input.json')
        verifier = self.promote(f)
        self.reopen(f)
        self.assertEqual(f.run.review_status().round_number, 2)
        second = self.review(f, reviewer)
        self.assertEqual(second['path'], 'rounds/round-2/proposal_input.json')
        record = json.loads(f.store.read(second['path']))
        current = json.loads(f.store.read('rounds/current_verified.json'))
        self.assertEqual(record['base_pointer']['path'], 'rounds/verified_history/current-verified-1.json')
        self.assertEqual(json.loads(reviewer.prompts[-1].splitlines()[-1])['base_draft_hash'], current['verified_draft_hash'])
        self.assertEqual((reviewer.calls, f.editor.calls, verifier.calls), (2, 1, 1))
        self.assertEqual(f.store.read(RUN_INPUT_PATH), root_record)
        before = self.files(f)
        self.reopen(f)
        self.assertEqual(f.run.admit_reviewed_round(), second)
        self.assertEqual(self.files(f), before)
        # Original candidate replay continues to use round 1 and its seed base.
        self.assertEqual(f.run._history().load_inputs(f.store.read, 1)['base_pointer_ref']['path'],
                         'rounds/verified_history/current-verified-0.json')

    def test_original_reviewer_raw_missing_refuses_promoted_history_before_writes(self):
        f, reviewer = self.start(); self.review(f, reviewer); self.promote(f)
        header = json.loads(f.store.read('rounds/review_index/request-1.json'))
        (f.root / f"rounds/client_requests/{header['request_id']}/attempts/1/response.json").unlink()
        before = self.files(f)
        with self.assertRaises((ValueError, FileNotFoundError)): f.run.review_next(client=reviewer)
        self.assertEqual(self.files(f), before)
        self.assertEqual(reviewer.calls, 1)

    def test_pending_review_and_round_publication_recover_without_duplicate_calls(self):
        for suffix in ('/response.json', '/result.json', '/proposal_input.json'):
            with self.subTest(suffix=suffix):
                f, reviewer = self.start()
                publish = f.store.publish
                def stop(token, path, value):
                    result = publish(token, path, value)
                    if path.endswith(suffix): raise OSError('bounded interruption')
                    return result
                with patch.object(f.store, 'publish', side_effect=stop):
                    with self.assertRaisesRegex(OSError, 'bounded interruption'): self.review(f, reviewer)
                self.reopen(f)
                if f.run.review_status().status == 'valid_response':
                    self.assertEqual(f.run.review_next().status, 'continuation_required')
                    self.assertEqual(f.run.review_next(continuation=True).status, 'complete')
                self.assertEqual(f.run.admit_reviewed_round()['path'], 'rounds/round-1/proposal_input.json')
                self.assertEqual(reviewer.calls, 1)

    def test_round_constraints_and_feedback_cannot_be_substituted(self):
        for field in ('constraints', 'feedback'):
            with self.subTest(field=field):
                f, reviewer = self.start(); ref = self.review(f, reviewer)
                record = json.loads(f.store.read(ref['path']))
                if field == 'constraints': record['constraints']['max_operations'] += 1
                else: record['feedback'] = json.loads(f.store.read(f.admission._refs['rounds'][1]['path']))['feedback']
                (f.root / ref['path']).write_bytes(canonical_json_bytes(record))
                before = self.files(f)
                with self.assertRaises(ValueError): f.run.request(round_number=1, client=f.editor)
                self.assertEqual(f.editor.calls, 0)
                self.assertEqual(self.files(f), before)

    def test_budget_survives_promotion_and_clean_review_does_not_admit_editing(self):
        f, reviewer = self.start(budget=1); self.review(f, reviewer); self.promote(f)
        self.assertEqual(f.run.review_next(client=reviewer).status, 'budget_exhausted')
        self.assertEqual(reviewer.calls, 1)
        g, clean = self.start(profiles=[{'name':'structural_integrity','budget':1}, {'name':'determinism','budget':1}])
        def response(value):
            value['feedback']['feedback'] = []; value['classifications'] = []
            return canonical_json_bytes(value)
        clean.callback = response
        self.assertEqual(g.run.review_next(client=clean).status, 'complete')
        self.assertEqual(g.run.review_status().profile, 'determinism')
        self.assertEqual(g.run.review_next(client=clean).status, 'complete')
        self.assertEqual(g.run.review_next(client=clean).status, 'review_complete')
        before = self.files(g)
        with self.assertRaisesRegex(ValueError, 'no completed V review'): g.run.admit_reviewed_round()
        self.assertEqual(self.files(g), before)
        self.assertEqual(clean.calls, 2)

    def test_unsupported_sequence_and_missing_pin_refuse_before_reviewer(self):
        for options in ({'mode':'vertical'}, {'sequence_contract':False}):
            f, reviewer = self.start(**options)
            before = self.files(f)
            with self.assertRaises(ValueError): f.run.review_next(client=reviewer)
            self.assertEqual(self.files(f), before)
            self.assertEqual(reviewer.calls, 0)

    def test_findings_and_technical_interruption_cannot_allocate_another_round(self):
        f, reviewer = self.start()
        def timeout(value): raise TimeoutError('fictional timeout')
        reviewer.callback = timeout
        self.assertEqual(f.run.review_next(client=reviewer).status, 'timeout')
        reviewer.callback = None
        self.assertEqual(f.run.review_next(client=reviewer).status, 'continuation_required')
        self.assertEqual(reviewer.calls, 1)
        self.assertEqual(f.run.review_next(client=reviewer, continuation=True).status, 'complete')
        for _ in range(2): self.assertEqual(f.run.review_next(client=reviewer).status, 'finding_admission')
        self.assertEqual(reviewer.calls, 2)
        self.assertFalse((f.root / 'rounds/review_index/request-2.json').exists())

    def test_valid_journal_with_wrong_profile_is_not_sequence_authority(self):
        from whetstone.vnext_verified_review_requests import _ReviewInputs, _VerifiedReviewRequest, _run_bound_review
        from whetstone.vnext_verified_work import _BorrowedFence
        f, reviewer = self.start(profiles=[{'name':'structural_integrity','budget':2}, {'name':'determinism','budget':2}])
        with f.store.locked(f.run._history().validate_authority) as token:
            proof = f.run._history()._prove(f.store.read)
            request = _VerifiedReviewRequest(_ReviewInputs(_BorrowedFence(f.store, token), proof, proof.latest), 1, 'determinism')
            self.assertEqual(_run_bound_review(request, token, previous=None, client=reviewer).status, 'complete')
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'eligible profile or budget'): f.run.admit_reviewed_round()
        self.assertEqual(self.files(f), before)
        self.assertEqual(reviewer.calls, 1)

    def test_same_bytes_promotion_still_selects_new_pointer_and_consumes_budget(self):
        f, reviewer = self.start(budget=2); self.review(f, reviewer)
        def unchanged(packet):
            content = 'Queue always waits.\n'
            packet['payloads'][0]['content'] = content
            packet['patch']['operations'][0]['payload']['hash'] = sha256_bytes(content.encode())
            return canonical_json_bytes(packet)
        f.editor = history.verified.fixtures.Client(unchanged)
        self.promote(f)
        self.review(f, reviewer)
        first, second = [json.loads(prompt.splitlines()[-1]) for prompt in reviewer.prompts]
        self.assertEqual(first['base'], second['base'])
        self.assertNotEqual(first['base_pointer_ref'], second['base_pointer_ref'])
        self.assertEqual(second['base_pointer_ref']['path'], 'rounds/verified_history/current-verified-1.json')

    def test_committed_mirror_repair_precedes_malformed_future_review(self):
        f, reviewer = self.start(); self.review(f, reviewer); self.promote(f)
        (f.root / 'spec.md').unlink()
        (f.root / 'rounds/review_index/request-2.json').write_bytes(b'not json')
        self.assertEqual(f.run.review_next(client=reviewer).outcome, 'materialization_recovered')
        self.assertEqual(reviewer.calls, 1)
        before = self.files(f)
        with self.assertRaises(ValueError): f.run.review_next(client=reviewer)
        self.assertEqual(self.files(f), before)

    def test_clean_result_lost_ack_repeats_barriers_before_next_claim(self):
        f, reviewer = self.start(profiles=[{'name':'structural_integrity','budget':1}, {'name':'determinism','budget':1}])
        def clean(value):
            value['feedback']['feedback'] = []; value['classifications'] = []
            return canonical_json_bytes(value)
        reviewer.callback = clean
        publish = f.store.publish
        def stop(token, path, value):
            result = publish(token, path, value)
            if path.endswith('/result.json'): raise OSError('lost result acknowledgement')
            return result
        with patch.object(f.store, 'publish', side_effect=stop):
            with self.assertRaisesRegex(OSError, 'lost result'): f.run.review_next(client=reviewer)
        header = json.loads(f.store.read('rounds/review_index/request-1.json'))
        receipt_path = f"rounds/client_requests/{header['request_id']}/result.json"
        seen = []
        def trace(token, path, value):
            seen.append(path)
            return publish(token, path, value)
        with patch.object(f.store, 'publish', side_effect=trace):
            self.assertEqual(f.run.review_next(client=reviewer).status, 'complete')
        self.assertLess(seen.index(receipt_path), seen.index('rounds/review_index/request-2.json'))
        self.assertEqual(reviewer.calls, 2)

    def test_fresh_process_reopens_genuine_runtime_review_history(self):
        f, reviewer = self.start(); self.review(f, reviewer); self.promote(f)
        self.review(f, reviewer)
        before = self.files(f)
        script = '''import json,sys
from pathlib import Path
from whetstone import vnext_registry
from whetstone.vnext_contracts import ALGORITHM_VERSIONS
from whetstone.vnext_verified_run import open_verified_run
root,suite_path=sys.argv[1:]; manifest=json.loads(Path(suite_path).read_bytes())
job=json.loads((Path(root)/'job_descriptor.json').read_bytes())
vnext_registry.SUPPORTED_SUITES[manifest['suite_version']]=manifest['suite_digest']
vnext_registry.SUITE_ALGORITHM_VERSIONS[manifest['suite_version']]={k:job[k] for k in ALGORITHM_VERSIONS}
with open_verified_run(root,suite_path=suite_path) as run:
    print(json.dumps(dict(status=run.review_status().status,round=run.review_status().round_number)))
'''
        result = subprocess.run([sys.executable, '-c', script, str(f.root), str(f.admission.suite_path)],
                                capture_output=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(json.loads(result.stdout), dict(status='finding_admission', round=2))
        self.assertEqual(self.files(f), before)


if __name__ == '__main__': unittest.main()

"""Runtime Reviewer rounds, explicit operator child, and two real promotions."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_identity import binding_id
from whetstone.vnext_proposal_run import RUN_INPUT_PATH
from whetstone.vnext_semantic_admission import load_registered_semantic_context
from whetstone.vnext_semantic_protocol import RULES
from whetstone.vnext_verified_history import _VerifiedAnswerSource
from vnext_fixtures import STAMP
import test_vnext_verified_review as runtime
import test_vnext_verified_history as history
import test_vnext_unit_preflight as unit


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class RuntimeFollowupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): runtime.VerifiedReviewTests.setUpClass()
    files = runtime.VerifiedReviewTests.files
    start = runtime.VerifiedReviewTests.start
    review = runtime.VerifiedReviewTests.review
    reopen = runtime.VerifiedReviewTests.reopen

    def fixture(self, **options):
        setup = unit.UnitPreflightTests.setUp
        def with_authority(owner):
            setup(owner)
            f = owner.c.f
            reference = f.save('inputs/waiting-authority.md', b'Queue waiting applies to each work start.\n')
            target = next(row for row in f.authority['bindings'] if row['role'] == 'mutable_target')
            authority = dict(path=reference['path'], content_hash=reference['hash'], role='normative_authority',
                authority_scopes=target['authority_scopes'], effective_horizon='current', mutable=False,
                may_introduce_requirements=True)
            authority['binding_id'] = binding_id(authority)
            f.authority['bindings'].append(authority)
            f.authority['precedence'] = [dict(authority_scope=scope,
                ordered_binding_ids=[authority['binding_id'], target['binding_id']], conflict_policy='pause')
                for scope in target['authority_scopes']]
            f.rebind()
        with patch.object(unit.UnitPreflightTests, 'setUp', with_authority):
            f = runtime.VerifiedReviewTests.fixture(self, **options)
        f.editors, f.verifiers = [], []
        return f

    def candidate(self, f, *, number, selected=None, content=None):
        def change(packet):
            packet['payloads'][0]['content'] = content
            packet['patch']['operations'][0]['payload']['hash'] = sha256_bytes(content.encode())
            return canonical_json_bytes(packet)
        editor = history.verified.fixtures.Client(change if content else None)
        f.editors.append(editor)
        self.assertEqual(f.run.request(round_number=number, client=editor, selected_ref=selected).value.status, 'complete')
        creation = f.run.register(round_number=number, created_at=STAMP, selected_ref=selected).value
        self.assertEqual(editor.calls, 1)
        f.creation, f.identifier = creation, creation['candidate_id']
        return creation

    def verify(self, f, *, question=False):
        context = load_registered_semantic_context(f.store, admission=f.run._history(), candidate_id=f.identifier)
        verifier = history.verified.semantic.Client(context)
        if question:
            packet = context.packet
            target = next(row for row in packet['authority_map']['bindings'] if row['role'] == 'mutable_target')
            authority = packet['dependency_context'][0]
            def alternative(identifier, text, interpretation):
                return dict(authority_binding_id=identifier, interpretation=interpretation,
                    evidence=dict(byte_start=0, byte_end=len(text.encode()), content_hash=sha256_bytes(text.encode()), text=text))
            response = json.loads(verifier.valid)
            response.update(authority_compliance='uncertain', operator_decision_required=True,
                verdict='operator_decision_required', authority_choice=dict(
                    question='Which interpretation should a new transaction address?',
                    authority_scope=target['authority_scopes'][0], alternatives=[
                        alternative(target['binding_id'], packet['seed'], 'Waiting is scoped to queue startup.'),
                        alternative(authority['binding']['binding_id'], authority['content'], 'Waiting is scoped to every work start.')]),
                uncertainty_resolutions=[dict(field_path='authority_compliance', policy_rule_id=RULES['authority_choice'],
                    disposition='operator_decision_required', decision_id=None)])
            verifier.responses = [canonical_json_bytes(response)]
        f.verifiers.append(verifier)
        result = f.run.verify(client=verifier, decided_at=STAMP)
        self.assertEqual(verifier.calls, 1)
        self.assertEqual(result.value.decision['semantic_result'], 'operator_decision_required' if question else 'pass')
        return result.value

    def question(self):
        f, reviewer = self.start()
        self.review(f, reviewer)
        parent = self.candidate(f, number=1)
        decision = self.verify(f, question=True)
        self.assertEqual(decision.decision['candidate_disposition'], 'CANDIDATE_REJECTED')
        self.assertTrue(decision.decision['outstanding_decision_ids'])
        source = _VerifiedAnswerSource(f.store, admission=f.run._history(), candidate_id=f.identifier, require_current=True)
        answer = history.answers.input_for(source)
        return f, reviewer, parent, answer

    def select(self, f, parent, answer):
        before = self.files(f)
        preview = f.run.submit_answer(packet=answer, dry_run=True)
        self.assertEqual(preview.outcome, 'answer_preview')
        self.assertEqual(self.files(f), before)
        result = f.run.submit_answer(packet=answer)
        self.assertEqual(result.value, preview.value)
        self.assertEqual(result.value['response']['authorized_effects'], [])
        self.reopen(f)
        selected = f.run.select_followup(candidate_id=parent['candidate_id'], answer_reference=result.value['reference'])
        self.assertEqual(selected.outcome, 'followup_selected')
        self.reopen(f)
        return result.value['reference'], selected.value

    def second(self, f, reviewer):
        self.review(f, reviewer)
        second = self.candidate(f, number=2, content='Queue always waits before processing begins.\n')
        self.verify(f)
        return second

    def assert_counts(self, f, reviewer, *, reviews, editors, verifiers):
        self.assertEqual((reviewer.calls, sum(c.calls for c in f.editors), sum(c.calls for c in f.verifiers)),
                         (reviews, editors, verifiers))

    def test_runtime_operator_child_second_promotion_and_fresh_process_readback(self):
        f, reviewer, parent, answer = self.question()
        selectors = f.store.read(RUN_INPUT_PATH)
        original_round = f.store.read('rounds/round-1/proposal_input.json')
        parent_directory = parent['candidate_path'].rsplit('/', 1)[0] + '/'
        parent_evidence = {path: raw for path, raw in self.files(f).items() if path.startswith(parent_directory)}
        receipt, selected = self.select(f, parent, answer)
        self.assert_counts(f, reviewer, reviews=1, editors=1, verifiers=1)
        # Neither answering nor selecting advances authority or adds a review.
        self.assertEqual(f.run.review_next(client=reviewer).status, 'finding_admission')
        self.assertEqual(json.loads(f.store.read('rounds/current_verified.json'))['promotion_ordinal'], 0)
        child = self.candidate(f, number=1, selected=selected)
        self.assertNotEqual(child['candidate_id'], parent['candidate_id'])
        parent_plan_raw = f.store.read('rounds/round-1/mutation_plan.json')
        parent_plan = json.loads(parent_plan_raw)
        child_plan = json.loads(f.store.read(f"rounds/round-1/transactions/{child['transaction_id']}/mutation_plan.json"))
        self.assertEqual(child_plan['semantic_origin']['editing_plan_hash'], sha256_bytes(parent_plan_raw))
        for key, value in parent_plan.items():
            if key not in {'schema_version', 'transaction_id'}: self.assertEqual(child_plan[key], value, key)
        self.verify(f)
        editor_packet = json.loads(f.editors[-1].prompts[-1].splitlines()[-1])
        verifier_context = load_registered_semantic_context(f.store, admission=f.run._history(), candidate_id=child['candidate_id'])
        self.assertEqual(verifier_context.packet['semantic_interpretation'], editor_packet['semantic_interpretation'])
        self.assertEqual(f.run.promote(prepared_at=STAMP).current_pointer['promotion_ordinal'], 1)
        self.reopen(f)
        second = self.second(f, reviewer)
        self.assertEqual(f.run.promote(prepared_at=STAMP).current_pointer['promotion_ordinal'], 2)
        self.reopen(f)
        self.assertFalse(f.run.answers(candidate_id=parent['candidate_id']).value['submission_permitted'])
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'latest candidate and exact current base'):
            f.run.submit_answer(packet=answer)
        self.assertEqual(self.files(f), before)
        for path, raw in parent_evidence.items(): self.assertEqual(f.store.read(path), raw, path)
        self.assertEqual(f.store.read(RUN_INPUT_PATH), selectors)
        self.assertEqual(f.store.read('rounds/round-1/proposal_input.json'), original_round)
        self.assertEqual(json.loads(f.store.read(selected['path']))['answer_receipt'], receipt)
        def clean(response):
            response['feedback']['feedback'] = []; response['classifications'] = []
            return canonical_json_bytes(response)
        reviewer.callback = clean
        self.assertEqual(f.run.review_next(client=reviewer).status, 'complete')
        self.assertEqual(f.run.review_status().status, 'review_complete')
        pointers = [json.loads(prompt.splitlines()[-1])['base_pointer_ref']['path'] for prompt in reviewer.prompts]
        self.assertEqual(pointers, [f'rounds/verified_history/current-verified-{n}.json' for n in range(3)])
        self.assert_counts(f, reviewer, reviews=3, editors=3, verifiers=3)
        proof = f.run._history()._prove(f.store.read)
        self.assertEqual([p['source_candidate_id'] for p in proof.pointers[1:]], [child['candidate_id'], second['candidate_id']])
        self.assertEqual([c['candidate_id'] for c in proof.view.creations],
                         [parent['candidate_id'], child['candidate_id'], second['candidate_id']])
        self.fresh_process(f)

    def test_runtime_answer_and_selection_prefixes_reopen_without_clients(self):
        for boundary in ('/responses/', '/admission.json'):
            with self.subTest(boundary=boundary):
                f, reviewer, parent, answer = self.question()
                answer_reference = None
                if boundary == '/admission.json':
                    answer_reference = f.run.submit_answer(packet=answer).value['reference']
                publish = f.store.publish
                def stop(token, path, value):
                    result = publish(token, path, value)
                    if boundary in path: raise OSError('runtime operator interruption')
                    return result
                with patch.object(f.store, 'publish', side_effect=stop):
                    with self.assertRaisesRegex(OSError, 'runtime operator interruption'):
                        if answer_reference is None: f.run.submit_answer(packet=answer)
                        else: f.run.select_followup(candidate_id=parent['candidate_id'], answer_reference=answer_reference)
                self.reopen(f)
                if answer_reference is None:
                    answer_reference = f.run.submit_answer(packet=answer).value['reference']
                selected = f.run.select_followup(candidate_id=parent['candidate_id'], answer_reference=answer_reference).value
                self.reopen(f)
                before = self.files(f)
                self.assertEqual(f.run.select_followup(candidate_id=parent['candidate_id'], answer_reference=answer_reference).value, selected)
                self.assertEqual(self.files(f), before)
                self.assert_counts(f, reviewer, reviews=1, editors=1, verifiers=1)
                child = self.candidate(f, number=1, selected=selected)
                self.assertNotEqual(child['candidate_id'], parent['candidate_id'])
                self.verify(f)
                self.assertEqual(f.run.promote(prepared_at=STAMP).current_pointer['promotion_ordinal'], 1)
                self.assert_counts(f, reviewer, reviews=1, editors=2, verifiers=2)

    def test_second_promotion_lost_ack_repairs_before_new_review_and_replays_original_raw(self):
        f, reviewer = self.start()
        self.review(f, reviewer); self.candidate(f, number=1); self.verify(f)
        self.assertEqual(f.run.promote(prepared_at=STAMP).current_pointer['promotion_ordinal'], 1)
        self.reopen(f)
        self.second(f, reviewer)
        replace = f.store.replace_pointer
        def stop(token, path, **options):
            result = replace(token, path, **options)
            if path == 'rounds/current_verified.json': raise OSError('lost second promotion acknowledgement')
            return result
        with patch.object(f.store, 'replace_pointer', side_effect=stop):
            with self.assertRaisesRegex(OSError, 'lost second promotion'): f.run.promote(prepared_at=STAMP)
        committed = f.store.read('rounds/current_verified.json')
        self.assertEqual(json.loads(committed)['promotion_ordinal'], 2)
        self.reopen(f)
        self.assertEqual(f.run.review_next(client=reviewer).outcome, 'materialization_recovered')
        self.assert_counts(f, reviewer, reviews=2, editors=2, verifiers=2)
        self.assertEqual(f.store.read('rounds/current_verified.json'), committed)
        self.assertEqual(f.run.promote(prepared_at=STAMP).outcome, 'not_eligible')
        self.assertFalse((f.root / 'rounds/verified_history/current-verified-3.json').exists())
        self.assertEqual(f.run.review_status().round_number, 3)
        self.assertEqual(f.run.review_next(client=reviewer).status, 'complete')
        self.assert_counts(f, reviewer, reviews=3, editors=2, verifiers=2)
        # Even after two promotions, the original Reviewer raw result is required.
        header = json.loads(f.store.read('rounds/review_index/request-1.json'))
        raw = f.root / f"rounds/client_requests/{header['request_id']}/attempts/1/response.json"
        raw.write_bytes(raw.read_bytes() + b' ')
        before = self.files(f)
        with self.assertRaises(ValueError): f.run.admit_reviewed_round()
        self.assertEqual(self.files(f), before)
        self.assert_counts(f, reviewer, reviews=3, editors=2, verifiers=2)

    def test_declined_or_stale_answer_cannot_select_runtime_child(self):
        f, reviewer, parent, answer = self.question()
        before = self.files(f)
        stale = deepcopy(answer); stale['request']['hash'] = 'f' * 64
        with self.assertRaises(ValueError): f.run.submit_answer(packet=stale)
        self.assertEqual(self.files(f), before)
        declined = {**answer, 'action':'decline', 'selected_authority_binding_id':None}
        reference = f.run.submit_answer(packet=declined).value['reference']
        self.reopen(f)
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'declined semantic answer'):
            f.run.select_followup(candidate_id=parent['candidate_id'], answer_reference=reference)
        self.assertEqual(self.files(f), before)
        self.assertFalse(list(f.root.rglob('followup_transaction.json')))
        self.assertEqual(f.run.review_next(client=reviewer).status, 'finding_admission')
        self.assert_counts(f, reviewer, reviews=1, editors=1, verifiers=1)
        self.assertEqual(json.loads(f.store.read('rounds/current_verified.json'))['promotion_ordinal'], 0)

    def fresh_process(self, f):
        before = self.files(f)
        script = '''import json,sys
from pathlib import Path
from whetstone import vnext_registry
from whetstone.vnext_contracts import ALGORITHM_VERSIONS
from whetstone.vnext_verified_run import open_verified_run
root,suite=sys.argv[1:]; manifest=json.loads(Path(suite).read_bytes()); job=json.loads((Path(root)/'job_descriptor.json').read_bytes())
vnext_registry.SUPPORTED_SUITES[manifest['suite_version']]=manifest['suite_digest']
vnext_registry.SUITE_ALGORITHM_VERSIONS[manifest['suite_version']]={k:job[k] for k in ALGORITHM_VERSIONS}
with open_verified_run(root,suite_path=suite) as run:
    proof=run._history()._prove(run.store.read)
    print(json.dumps(dict(ordinal=proof.pointers[-1]['promotion_ordinal'],creations=len(proof.view.creations),review=run.review_status().status)))
'''
        result = subprocess.run([sys.executable, '-c', script, str(f.root), str(f.admission.suite_path)],
                                capture_output=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(json.loads(result.stdout), dict(ordinal=2, creations=3, review='review_complete'))
        self.assertEqual(self.files(f), before)


if __name__ == '__main__': unittest.main()

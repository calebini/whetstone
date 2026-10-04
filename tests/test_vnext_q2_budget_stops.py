"""P0-07 caller-owned budget stops; no public token/time accounting policy.

A deterministic caller ledger/fake clock cancels at durable storage boundaries.
This is cooperative cancellation, not process-kill or provider metering coverage.
"""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes
from whetstone.vnext_proposal_handoff import registry_for_proposal_requests
from whetstone.vnext_semantic_admission import load_registered_semantic_context
from whetstone.vnext_verified_semantics import VerifiedSemanticDecisionJournal
from vnext_fixtures import STAMP
from vnext_q2_fixtures import Editor, fixture
import test_vnext_semantic_requests as semantic
import test_vnext_verified_run as stored
import test_vnext_verified_work as work


class BudgetStop(BaseException):
    """Caller cancellation must not become a retryable provider exception."""


class CallerBudget:
    def __init__(self, kind):
        self.kind = kind
        self.tokens = 0
        self.now = 0
        self.token_limit = 10
        self.deadline = 10

    def exhaust(self):
        if self.kind == 'tokens': self.tokens = self.token_limit
        else: self.now = self.deadline

    def check(self):
        if self.tokens >= self.token_limit or self.now >= self.deadline:
            raise BudgetStop(self.kind)


@unittest.skipUnless(sys.platform == 'darwin', 'D8 requires local macOS/APFS')
class BudgetStopTests(unittest.TestCase):
    setUpClass = work.VerifiedWorkTests.setUpClass
    owner = work.VerifiedWorkTests.owner
    service = work.VerifiedWorkTests.service
    files = work.VerifiedWorkTests.files
    later_candidate = work.VerifiedWorkTests.later_candidate

    def prepare(self):
        temp = TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.source = Path(temp.name)/'source.md'
        f = fixture(self, b'# Queue\n## Timing\nQueue waits.\n', [['timing']], source_path=self.source)
        stored.VerifiedRunTests.persist(self, f)
        f.editor = Editor([('Timing', 'replace_section_body', 'Queue waits before starting.\n', False)])
        self.assertEqual(f.work.request(round_number=1, client=f.editor).value.status, 'complete')
        return f

    def reopen(self, f):
        # All assertions after a stop use a newly opened store and persisted selectors.
        run = stored.VerifiedRunTests.reopen(self, f)
        f.work = run
        return run

    def journal(self, f):
        admission = self.owner(f)
        registry = registry_for_proposal_requests(f.store, load_inputs=admission.load_inputs,
                                                  validate_authority=admission.validate_authority)
        return VerifiedSemanticDecisionJournal(registry, admission=admission)

    def unverified(self, f, creation, *, decision=False):
        view = self.journal(f).inspect(creation['candidate_id'])
        self.assertEqual(view.effective_event['new_disposition'], 'CANDIDATE_UNVERIFIED')
        self.assertEqual(view.prepared, False)
        if decision:
            self.assertFalse(view.decision['decision_final'])
            self.assertFalse(view.decision['promotion_permitted'])
            self.assertEqual(view.decision['semantic_result'], 'not_run')
        else:
            self.assertIsNone(view.decision); self.assertIsNone(view.pointer)
        return view

    def safe(self, f, run, outcome):
        before = self.files(f)
        self.assertEqual(run.inspect().outcome, outcome)
        self.assertEqual(f.store.read('rounds/current_verified.json'), f.base_pointer)
        self.assertEqual(f.store.read('spec.md'), f.base_mirror)
        self.assertEqual(self.source.read_bytes(), f.base_mirror)
        review = run.review_apply_back()
        self.assertFalse(review['eligible'])
        self.assertFalse(review['apply_back_permitted'])
        self.assertFalse(any('source binding absent' in r or 'contract is absent' in r for r in review['blockers']))
        self.assertEqual(self.files(f), before)
        if outcome == 'registration_recovery_required':
            with self.assertRaisesRegex(ValueError, 'registration recovery is required before promotion'):
                run.promote(prepared_at=STAMP)
        else:
            self.assertEqual(run.promote(prepared_at=STAMP).outcome, 'not_eligible')
        self.assertEqual(self.files(f), before)
        self.assertFalse(list(f.root.rglob('promotion-intent-*.json')))
        self.assertFalse((f.root/'rounds/apply_back').exists())

    def cancel_publication(self, f, kind, predicate, *, after):
        budget = CallerBudget(kind); budget.check()
        publish = f.store.publish
        hits = []
        def bounded(token, path, value):
            if predicate(path):
                if after: publish(token, path, value)
                hits.append(path); budget.exhaust(); budget.check()
            return publish(token, path, value)
        with patch.object(f.store, 'publish', side_effect=bounded):
            with self.assertRaisesRegex(BudgetStop, kind):
                f.work.register(round_number=getattr(f, 'round_number', 1), created_at=STAMP)
        self.assertEqual(len(hits), 1)
        self.assertIsNone(f.store._token)
        return budget

    def complete_orphan(self, kind, *, previous=False):
        f = self.prepare()
        prior = None
        if previous:
            prior = f.work.register(round_number=1, created_at=STAMP).value
            context = load_registered_semantic_context(f.store, admission=self.owner(f), candidate_id=prior['candidate_id'])
            verifier = semantic.Client(context)
            response = json.loads(verifier.valid)
            response.update(verdict='reject', unrelated_semantic_change='detected')
            verifier.responses = [canonical_json_bytes(response)]
            self.assertEqual(f.work.verify(client=verifier, decided_at=STAMP).value.decision['candidate_disposition'],
                             'CANDIDATE_REJECTED')
            self.later_candidate(f, prepare_only=True)
            # Persist the separately admitted same-base round for fresh-store reentry.
            from whetstone.vnext_proposal_run import round_input_path
            record = f.store.read(f.admission._refs['rounds'][2]['path'])
            with f.store.locked(self.owner(f).validate_authority) as token:
                f.store.publish(token, round_input_path(2), record)
            self.reopen(f)
            self.assertEqual(f.work.request(round_number=2, client=f.editor).value.status, 'complete')
            f.round_number = 2
        ordinal = 2 if previous else 1
        self.cancel_publication(f, kind, lambda p: p == f'rounds/candidate_index/creation-{ordinal}.json', after=False)
        run = self.reopen(f)
        view = self.owner(f).inspect()
        self.assertEqual(view.creations, (prior,) if prior else ())
        self.assertEqual(len(view.orphans), 1)
        before = self.files(f)
        self.safe(f, run, 'registration_recovery_required')
        self.assertEqual(run.verify(decided_at=STAMP).outcome, 'registration_recovery_required')
        self.assertEqual(self.files(f), before)
        result = run.recover_registration()
        self.assertEqual(result.outcome, 'registration_recovered')
        creation = result.latest_candidate
        self.assertEqual(creation['candidate_creation_ordinal'], ordinal)
        self.unverified(f, creation)
        # Recovery only publishes the missing commit and preserves the entire orphan.
        self.assertEqual(set(self.files(f))-set(before), {f'rounds/candidate_index/creation-{ordinal}.json'})
        for path, raw in before.items(): self.assertEqual(f.store.read(path), raw)
        self.assertEqual(run.recover_registration().outcome, 'no_registration_recovery')
        self.assertEqual(f.editor.calls, 1)
        self.safe(f, run, 'work_available')

    def test_token_stop_before_registration_preserves_prior_latest_and_recovers_once(self):
        self.complete_orphan('tokens', previous=True)

    def test_time_stop_before_registration_leaves_no_latest_and_recovers_once(self):
        self.complete_orphan('time')

    def test_partial_orphan_is_preserved_and_cannot_be_recovered_as_registered(self):
        for kind in ('tokens', 'time'):
            with self.subTest(kind=kind):
                f = self.prepare()
                self.cancel_publication(f, kind, lambda p: p.endswith('/candidate_unverified.md'), after=True)
                run = self.reopen(f)
                view = self.owner(f).inspect()
                self.assertFalse(view.creations); self.assertEqual(len(view.orphans), 1)
                before = self.files(f)
                self.safe(f, run, 'registration_recovery_required')
                with self.assertRaises(FileNotFoundError): run.recover_registration()
                self.assertEqual(self.files(f), before)
                self.assertEqual(f.editor.calls, 1)

    def test_token_and_time_stop_after_registration_prevent_verifier_and_promotion(self):
        for kind in ('tokens', 'time'):
            with self.subTest(kind=kind):
                f = self.prepare()
                creation = f.work.register(round_number=1, created_at=STAMP).value
                context = load_registered_semantic_context(f.store, admission=self.owner(f), candidate_id=creation['candidate_id'])
                verifier = semantic.Client(context)
                budget = CallerBudget(kind); budget.check(); budget.exhaust()
                with self.assertRaisesRegex(BudgetStop, kind):
                    budget.check()
                    f.work.verify(client=verifier, decided_at=STAMP)
                self.assertEqual(verifier.calls, 0)
                run = self.reopen(f)
                self.assertEqual(run.inspect().latest_candidate, creation)
                self.unverified(f, creation)
                self.safe(f, run, 'work_available')
                # A later caller explicitly supplies a fresh budget; no automatic retry.
                CallerBudget(kind).check()
                result = run.verify(client=verifier, decided_at=STAMP)
                self.assertTrue(result.value.decision['promotion_permitted'])
                self.assertEqual((f.editor.calls, verifier.calls), (1, 1))
                self.assertEqual(f.store.read('rounds/current_verified.json'), f.base_pointer)

    def test_stop_at_semantic_invocation_retains_nonfinal_decision_until_explicit_continuation(self):
        for kind in ('tokens', 'time'):
            with self.subTest(kind=kind):
                f = self.prepare()
                creation = f.work.register(round_number=1, created_at=STAMP).value
                context = load_registered_semantic_context(f.store, admission=self.owner(f), candidate_id=creation['candidate_id'])
                verifier = semantic.Client(context)
                budget = CallerBudget(kind)
                def stop_before_provider(prompt):
                    budget.exhaust(); budget.check()
                with patch.object(verifier, 'verify', side_effect=stop_before_provider):
                    with self.assertRaisesRegex(BudgetStop, kind):
                        f.work.verify(client=verifier, decided_at=STAMP)
                self.assertIsNone(f.store._token)
                run = self.reopen(f)
                initial = self.unverified(f, creation, decision=True)
                self.safe(f, run, 'work_available')
                before = self.files(f)
                self.assertEqual(run.verify(client=verifier, decided_at=STAMP).outcome, 'continuation_required')
                self.assertEqual(self.files(f), before); self.assertEqual(verifier.calls, 0)
                self.assertTrue(run.verify(client=verifier, decided_at=STAMP, continuation=True).value.decision['promotion_permitted'])
                self.assertEqual((f.editor.calls, verifier.calls), (1, 1))
                self.assertEqual(json.loads(f.store.read(initial.pointer['current_decision_path'])), initial.decision)
                self.assertEqual(f.store.read('rounds/current_verified.json'), f.base_pointer)


if __name__ == '__main__': unittest.main()

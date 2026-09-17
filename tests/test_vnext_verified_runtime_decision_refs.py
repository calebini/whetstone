"""Canonical round admission with explicit named-unit decision dependencies."""
import json
import sys
import unittest
from unittest.mock import patch

from whetstone import vnext_local_storage as storage
from whetstone.vnext_classification import classify_feedback
from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_discovery import discovery_rules
from whetstone.vnext_identity import response_id
from whetstone.vnext_inventory import seed_inventory
from whetstone.vnext_unit_authorization import unit_decision_request
from whetstone.vnext_unit_preflight import prepare_unit_preflight
from vnext_fixtures import STAMP
import test_vnext_verified_review as runtime


ROUND = 'rounds/round-1/proposal_input.json'
POINTER = 'rounds/current_verified.json'


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class RuntimeDecisionReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): runtime.VerifiedReviewTests.setUpClass()
    fixture = runtime.VerifiedReviewTests.fixture
    start = runtime.VerifiedReviewTests.start
    reopen = runtime.VerifiedReviewTests.reopen
    files = runtime.VerifiedReviewTests.files

    def decision(self):
        f, reviewer = self.start()
        reviewer.hints[0]['requested_effects'] = ['weaken']
        result = f.run.review_next(client=reviewer)
        self.assertEqual(result.status, 'complete')
        self.assertEqual(f.run.review_status().status, 'finding_admission')
        reader, values = f.admission._base(f.store.read)
        feedback = reader.json(result.receipt['feedback'], 'reviewer_feedback')
        advice = reader.json(result.receipt['advice'], 'vnext_finding_advice_v1')
        findings, evidence = classify_feedback(feedback=feedback, feedback_ref=result.receipt['feedback'],
            advice=advice, **{key: values[key] for key in ('job', 'authority', 'invariants', 'base', 'scope')},
            section_map=values['base_map'])
        finding = findings[0]
        self.assertEqual(finding['classification'], 'operator_decision_required')
        inventory = seed_inventory(values['base'], values['base_map'], values['job'],
            rules=discovery_rules(values['invariants']))
        unit = next(row for row in inventory['units'] if row['normative']
                    and row['owning_section_id'] in finding['target_section_ids'])
        request = unit_decision_request(job=values['job'], base_hash=sha256_bytes(values['base']),
            finding=finding, targets=finding['target_section_ids'],
            feedback_refs=evidence[finding['finding_id']]['feedback_refs'], inventory=inventory,
            section_map=values['base_map'], options=[dict(option_id='named_weaken',
                description='Fictional named-unit approval.', authorized_effects=['weaken'],
                authorized_deletion_unit_ids=[],
                authorized_unit_effects=[dict(unit_id=unit['unit_id'], effects=['weaken'])])])
        request_ref = dict(path='inputs/runtime-unit-request.json', hash=sha256_bytes(canonical_json_bytes(request)))
        response = dict(schema_version='operator-decision-response-v1', job_id=values['job']['job_id'],
            response_id='', decision_id=request['decision_id'], decision_request_hash=request_ref['hash'],
            base_draft_hash=sha256_bytes(values['base']), authority_map_hash=values['job']['authority_map_hash'],
            scope_contract_hash=values['job']['scope_contract_hash'], selected_option_id='named_weaken',
            authorized_effects=['weaken'], authorized_deletion_unit_ids=[],
            rationale='Fixture approval of this unit only.', decided_by='fixture operator', decided_at=STAMP)
        response['response_id'] = response_id(response)
        response_ref = dict(path='inputs/runtime-unit-response.json', hash=sha256_bytes(canonical_json_bytes(response)))
        # Explicit fictional operator inputs; the runtime must replay their
        # barriers itself before exposing a round that grants their effects.
        with f.store.locked(f.admission.validate_authority) as token:
            f.store.publish(token, request_ref['path'], request)
            f.store.publish(token, response_ref['path'], response)
        choice = dict(finding_id=finding['finding_id'], request=request_ref, response=response_ref)
        self.assertFalse((f.root / ROUND).exists())
        self.assertEqual(f.run._record['staged_rounds'], [])
        return f, reviewer, result, choice, response, unit

    def assert_no_later_work(self, f, reviewer, current):
        self.assertEqual(f.store.read(POINTER), current)
        self.assertEqual((reviewer.calls, f.editor.calls), (1, 0))
        for path in ('rounds/candidate_index/creation-1.json', 'rounds/review_index/request-2.json',
                     'rounds/verified_history/current-verified-1.json'):
            self.assertFalse((f.root / path).exists(), path)

    def test_request_and_response_replay_failures_recover_exact_round_without_clients(self):
        for source in ('request', 'response'):
            with self.subTest(source=source):
                f, reviewer, result, choice, response, unit = self.decision()
                current = f.store.read(POINTER)
                before = self.files(f)
                target = choice[source]['path']
                publish, flush = f.store.publish, storage._full_flush
                active, seen, full_flushes = [], [], []
                def interrupt(fd):
                    if active == [target]:
                        full_flushes.append(fd)
                        if len(full_flushes) == 2:
                            raise OSError('decision existing-inode replay flush failed')
                    return flush(fd)
                def observe(token, path, value):
                    active[:] = [path]
                    seen.append(path)
                    try: return publish(token, path, value)
                    except storage.StorageWriteError:
                        self.assertIsNone(f.store._token)
                        self.assertIsNone(f.store._lock_fd)
                        with self.assertRaises(storage.OwnershipLost):
                            publish(token, 'rounds/stale-decision-owner', b'forbidden')
                        raise
                    finally: active.clear()
                with patch.object(storage, '_full_flush', side_effect=interrupt), \
                        patch.object(f.store, 'publish', side_effect=observe):
                    with self.assertRaises(storage.StorageWriteError) as error:
                        f.run.admit_reviewed_round(decision_refs=[choice])
                self.assertEqual(error.exception.result.outcome, 'outcome_requires_reconciliation')
                self.assertEqual(error.exception.result.path, target)
                self.assertEqual(error.exception.result.hash, choice[source]['hash'])
                self.assertEqual(len(full_flushes), 2)
                receipt_path = f"rounds/client_requests/{result.request_id}/result.json"
                self.assertLess(seen.index(receipt_path), seen.index(target))
                self.assertNotIn(ROUND, seen)
                if source == 'request': self.assertNotIn(choice['response']['path'], seen)
                self.assertEqual(self.files(f), before)
                self.reopen(f)
                self.assertEqual(f.run.review_status().status, 'finding_admission')
                self.assertEqual(self.files(f), before)
                self.assert_no_later_work(f, reviewer, current)

                seen = []
                publish = f.store.publish
                def trace(token, path, value):
                    seen.append(path)
                    return publish(token, path, value)
                with patch.object(f.store, 'publish', side_effect=trace):
                    reference = f.run.admit_reviewed_round(decision_refs=[choice])
                expected = [choice['request']['path'], choice['response']['path'], ROUND]
                self.assertEqual([path for path in seen if path in expected], expected)
                self.assertLess(seen.index(receipt_path), seen.index(expected[0]))
                record = json.loads(f.store.read(ROUND))
                self.assertEqual(reference, dict(path=ROUND, hash=sha256_bytes(f.store.read(ROUND))))
                self.assertEqual(record['decision_refs'], [choice])
                self.assertEqual(record['feedback'], result.receipt['feedback'])
                self.assertEqual(record['advice'], result.receipt['advice'])
                self.assertEqual(record['base_pointer']['hash'], sha256_bytes(current))
                self.assertEqual(set(self.files(f)) - set(before), {ROUND})
                for path, raw in before.items(): self.assertEqual(f.store.read(path), raw, path)
                self.reopen(f)
                inputs = f.run._history().load_inputs(f.store.read, 1)
                preflight = prepare_unit_preflight(**inputs)
                self.assertEqual(len(preflight.bindings), 1)
                self.assertEqual(preflight.bindings[0].response, response)
                self.assertEqual(preflight.bindings[0].units_for('weaken'), {unit['unit_id']})
                self.assertEqual(preflight.bindings[0].units_for('remove'), set())
                self.assertEqual(len(preflight.derived_tasks), 1)
                after = self.files(f)
                self.assertEqual(f.run.admit_reviewed_round(decision_refs=[choice]), reference)
                self.assertEqual(self.files(f), after)
                self.assertFalse((f.root / 'rounds/stale-decision-owner').exists())
                self.assert_no_later_work(f, reviewer, current)

    def test_missing_altered_and_mid_replay_changed_decisions_refuse_round_publication(self):
        f, reviewer, _, choice, _, _ = self.decision()
        current = f.store.read(POINTER)
        pristine = self.files(f)
        for source in ('request', 'response'):
            for fault in ('missing', 'altered'):
                with self.subTest(source=source, fault=fault):
                    path = f.root / choice[source]['path']
                    raw = path.read_bytes()
                    try:
                        if fault == 'missing': path.unlink()
                        else: path.write_bytes(raw + b' ')
                        before = self.files(f)
                        self.reopen(f)
                        with patch.object(f.store, 'publish', side_effect=AssertionError('publication before valid decisions')):
                            with self.assertRaises((ValueError, FileNotFoundError)):
                                f.run.admit_reviewed_round(decision_refs=[choice])
                        self.assertEqual(self.files(f), before)
                        self.assertFalse((f.root / ROUND).exists())
                    finally: path.write_bytes(raw)
                    self.assertEqual(self.files(f), pristine)
                    self.assert_no_later_work(f, reviewer, current)

        publish = f.store.publish
        response_path = f.root / choice['response']['path']
        raw = response_path.read_bytes()
        changed = []
        def drift(token, path, value):
            result = publish(token, path, value)
            if path == choice['request']['path']:
                response_path.write_bytes(raw + b' ')
                changed.append(self.files(f))
            return result
        try:
            with patch.object(f.store, 'publish', side_effect=drift):
                with self.assertRaisesRegex(ValueError, 'decision source changed'):
                    f.run.admit_reviewed_round(decision_refs=[choice])
            self.assertEqual(len(changed), 1)
            self.assertEqual(self.files(f), changed[0])
            self.assertFalse((f.root / ROUND).exists())
        finally: response_path.write_bytes(raw)
        self.assertEqual(self.files(f), pristine)
        self.assert_no_later_work(f, reviewer, current)


if __name__ == '__main__': unittest.main()

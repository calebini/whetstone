from copy import deepcopy
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_local_storage import Publication, StorageWriteError
from whetstone.vnext_semantic_admission import SEMANTIC_ALGORITHMS, SEMANTIC_SCHEMAS
from whetstone.vnext_semantic_protocol import POLICY_VERSION
from whetstone.vnext_semantic_requests import REQUEST_SCHEMAS
from whetstone.vnext_semantic_decisions import SemanticDecisionJournal
from vnext_consuming_suite_fixture import consuming_suite
from vnext_fixtures import STAMP
import test_vnext_semantic_requests as requests


def decision_suite(test, directory):
    return consuming_suite(test, directory, additional_schemas=SEMANTIC_SCHEMAS | REQUEST_SCHEMAS,
        additional_algorithms=(*SEMANTIC_ALGORITHMS, 'vnext_semantic_requests_v1', 'vnext_semantic_decisions_v1'),
        algorithm_overrides={'semantic_verifier_policy_version': POLICY_VERSION})


@unittest.skipUnless(sys.platform == 'darwin', 'Proposed local storage targets macOS/APFS')
class SemanticDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        requests.SemanticRequestTests.setUpClass()

    def setUp(self):
        self.subject = requests.SemanticRequestTests()
        self.addCleanup(self.subject.doCleanups)
        with patch.object(requests, 'request_suite', decision_suite):
            self.subject.setUp()
        self.store = self.subject.store
        self.creation = self.subject.creation
        self.identifier = self.subject.identifier
        self.journal = SemanticDecisionJournal(self.subject.registry, admission=self.subject.admission)

    def commit(self, stamp=STAMP):
        return self.journal.commit_semantic(self.identifier, decided_at=stamp)

    def test_pass_appends_linked_final_decision_and_preserves_seed_and_initial_evidence(self):
        first = self.journal.inspect(self.identifier)
        seed = self.store.read('rounds/current_verified.json')
        d1 = self.store.read(first.pointer['current_decision_path'])
        self.subject.run_request()
        final = self.commit()
        self.assertEqual((final.decision['decision_ordinal'], final.decision['candidate_disposition'], final.decision['decision_final']),
                         (2, 'CANDIDATE_VERIFIED', True))
        self.assertEqual(final.decision['previous_decision_hash'], sha256_bytes(d1))
        self.assertEqual(final.effective_event['event_ordinal'], 3)
        self.assertEqual(final.effective_event['previous_event_hash'], first.effective_event_ref['hash'])
        self.assertFalse(final.decision['promotion_permitted'])
        self.assertEqual(self.store.read('rounds/current_verified.json'), seed)
        self.assertEqual(self.store.read(first.pointer['current_decision_path']), d1)
        self.assertEqual(self.commit('2031-01-01T00:00:00Z').decision, final.decision)
        self.assertEqual(self.journal.commit(self.identifier, decided_at='2032-01-01T00:00:00Z').decision, final.decision)
        report = self.journal.terminal()
        self.assertEqual((report['terminal_state'], report['resume']['reason']), ('TARGET_NOT_REACHED', 'vnext_proposal_only_complete'))
        self.assertEqual(report['latest_candidate']['disposition'], 'CANDIDATE_VERIFIED')
        self.assertFalse(report['apply_back_permitted']);self.assertFalse(report['resume']['permitted'])
        self.assertEqual((self.subject.client.calls, self.subject.editor.calls), (1, 1))

    def test_reject_is_final_with_semantic_reason_and_cannot_reopen(self):
        response = json.loads(self.subject.client.valid)
        response.update(verdict='reject', unrelated_semantic_change='detected')
        self.subject.client.responses = [canonical_json_bytes(response)]
        self.subject.run_request()
        final = self.commit()
        self.assertEqual(final.decision['candidate_disposition'], 'CANDIDATE_REJECTED')
        self.assertEqual(final.decision['rejection_codes'], ['vnext_semantic_rejected'])
        self.assertEqual(self.journal.terminal()['resume']['reason'], 'vnext_semantic_rejected')
        self.assertEqual(self.journal.terminal()['terminal_state'], 'TARGET_NOT_REACHED')
        self.assertEqual(self.journal.commit(self.identifier, decided_at=STAMP).decision, final.decision)
        self.assertEqual(self.subject.client.calls, 1)

    def test_technical_failure_leaves_nonfinal_initial_decision_without_an_append(self):
        self.subject.client.responses = [TimeoutError('scripted deadline')]
        self.subject.run_request()
        with self.assertRaisesRegex(ValueError, 'completed durable Verifier receipt'): self.commit()
        view = self.journal.inspect(self.identifier)
        self.assertEqual((view.decision['decision_ordinal'], view.decision['semantic_result'], view.decision['decision_final']), (1, 'not_run', False))
        self.assertFalse(self.subject.fixture.root.joinpath(self.journal.paths(self.creation, 2)[1]).exists())
        self.assertEqual(self.subject.client.calls, 1)

    def test_every_pre_pointer_prefix_is_ineffective_and_recovery_reuses_timestamp(self):
        self.subject.run_request()
        original = self.store.publish
        _, decision_path, event_path, snapshot_path, _ = self.journal.paths(self.creation, 2)
        for target in (decision_path, event_path, snapshot_path):
            def stop(token, path, value):
                result = original(token, path, value)
                if path == target: raise OSError('scripted semantic prefix interruption')
                return result
            with patch.object(self.store, 'publish', side_effect=stop):
                with self.assertRaisesRegex(OSError, 'prefix interruption'): self.commit()
            view = self.journal.inspect(self.identifier)
            self.assertTrue(view.prepared)
            self.assertEqual(view.decision['decision_ordinal'], 1)
            self.assertEqual(view.effective_event['new_disposition'], 'CANDIDATE_UNVERIFIED')
            report = self.journal.terminal()
            self.assertEqual(report['resume']['next_gate'], 'verification_commit')
            self.assertTrue(report['resume']['permitted'])
        final = self.commit('2031-01-01T00:00:00Z')
        self.assertEqual(final.decision['decided_at'], STAMP)
        self.assertFalse(final.prepared)
        self.assertEqual(self.subject.client.calls, 1)

    def test_lost_pointer_acknowledgement_reads_the_committed_final_disposition(self):
        self.subject.run_request()
        original = self.store._tree.write
        target = self.journal.paths(self.creation, 2)[-1]
        def lost(path, raw, **kwargs):
            result = original(path, raw, **kwargs)
            if path == target: raise StorageWriteError(Publication('outcome_requires_reconciliation', path, result.hash), 'scripted lost semantic pointer acknowledgement')
            return result
        with patch.object(self.store._tree, 'write', side_effect=lost):
            with self.assertRaises(StorageWriteError): self.commit()
        self.assertIsNone(self.store._token)
        view = self.journal.inspect(self.identifier)
        self.assertEqual(view.decision['candidate_disposition'], 'CANDIDATE_VERIFIED')
        self.assertFalse(view.prepared)
        self.assertEqual(self.commit().decision, view.decision)

    def test_changed_predecessor_and_unknown_next_ordinal_refuse_without_downgrade(self):
        self.subject.run_request()
        final = self.commit()
        pointer_path = self.journal.paths(self.creation, 2)[-1]
        pointer = self.store.read(pointer_path)
        decision_path = self.subject.fixture.root / final.pointer['current_decision_path']
        original = decision_path.read_bytes()
        value = json.loads(original);value['previous_decision_hash'] = 'f' * 64
        decision_path.write_bytes(canonical_json_bytes(value))
        with self.assertRaisesRegex(ValueError, 'receipt or predecessor'): self.commit()
        self.assertEqual(self.store.read(pointer_path), pointer)
        decision_path.write_bytes(original)
        extra = decision_path.parent / 'candidate_verification-attempt-3.json';extra.write_bytes(original)
        with self.assertRaisesRegex(ValueError, 'unsupported or duplicate'): self.journal.inspect(self.identifier)
        self.assertEqual(self.store.read(pointer_path), pointer)

    def test_final_pointer_cannot_hide_missing_raw_receipt_or_predecessor_snapshot(self):
        self.subject.run_request()
        final = self.commit()
        paths = [self.subject.path('attempts/1/response.json'), self.subject.path('result.json'),
                 self.subject.fixture.root / self.journal.paths(self.creation, 1)[3]]
        for path in paths:
            raw = path.read_bytes();path.unlink()
            with self.subTest(path=path.name), self.assertRaises(ValueError): self.journal.inspect(self.identifier)
            path.write_bytes(raw)
        self.assertEqual(self.journal.inspect(self.identifier).decision, final.decision)
        self.assertEqual(self.subject.client.calls, 1)


if __name__ == '__main__':
    unittest.main()

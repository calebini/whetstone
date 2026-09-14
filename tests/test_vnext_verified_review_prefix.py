import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_verified_history import _Proof
from whetstone.vnext_verified_review_requests import _read_review_prefix
from vnext_fixtures import STAMP
import test_vnext_verified_review_requests as journal


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class VerifiedReviewPrefixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): journal.VerifiedReviewRequestTests.setUpClass()
    files = journal.VerifiedReviewRequestTests.files
    owner = journal.VerifiedReviewRequestTests.owner
    ready = journal.VerifiedReviewRequestTests.ready
    run_request = journal.VerifiedReviewRequestTests.run_request
    verified = journal.VerifiedReviewRequestTests.verified
    service = journal.VerifiedReviewRequestTests.service
    materialize_seed = journal.VerifiedReviewRequestTests.materialize_seed
    fixture = journal.VerifiedReviewRequestTests.fixture
    seed = journal.VerifiedReviewRequestTests.seed
    request = journal.VerifiedReviewRequestTests.request

    def test_original_base_prefix_replays_across_promotion_without_self_support(self):
        f = self.verified()
        self.materialize_seed(f)
        first = self.request(f, client=journal.Reviewer(f))
        previous = sha256_bytes(f.store.read('rounds/review_index/request-1.json'))
        self.service(f).promote(prepared_at=STAMP)
        second = self.request(f, number=2, previous=previous, client=journal.Reviewer(f))
        before = self.files(f)
        proof = self.owner(f)._prove(f.store.read)
        frames = _read_review_prefix(proof, require_complete=True)
        self.assertEqual([frame.receipt for frame in frames], [first.receipt, second.receipt])
        self.assertNotEqual(frames[0].header['base_pointer'], frames[1].header['base_pointer'])
        with self.assertRaisesRegex(ValueError, 'read-only'):
            frames[0].request.synchronize(None, frames[0].header, frames[0].outcomes)
        # While proving the first promotion, only its seed predecessor has
        # entered the acyclic base set. Its own Reviewer prefix is available;
        # the subsequent review cannot justify that same promotion.
        partial = _Proof(self.owner(f), f.store.read)
        self.assertEqual(len(_read_review_prefix(partial, through_round=1, require_complete=True)), 1)
        with self.assertRaisesRegex(ValueError, 'has not been proven'):
            _read_review_prefix(partial, through_round=2, require_complete=True)
        self.assertEqual(self.files(f), before)

    def test_bounded_prefix_never_enumerates_or_consumes_future_claims(self):
        f = self.seed()
        self.request(f, client=journal.Reviewer(f))
        (f.root / 'rounds/review_index/request-2.json').write_bytes(b'not json')
        before = self.files(f)
        proof = self.owner(f)._prove(f.store.read)
        listing = proof.store.list_directory
        def exact_only(path):
            if path == 'rounds/review_index': raise AssertionError('enumerated future claims')
            return listing(path)
        with patch.object(proof.store, 'list_directory', side_effect=exact_only):
            self.assertEqual(len(_read_review_prefix(proof, through_round=1, require_complete=True)), 1)
        with self.assertRaises(ValueError): _read_review_prefix(proof)
        self.assertEqual(self.files(f), before)

    def test_pending_last_request_cannot_become_complete_source_or_be_skipped(self):
        f = self.seed()
        def timeout(packet): raise TimeoutError('prefix fixture timeout')
        self.assertEqual(self.request(f, client=journal.Reviewer(f, timeout)).status, 'timeout')
        proof = self.owner(f)._prove(f.store.read)
        before = self.files(f)
        self.assertIsNone(_read_review_prefix(proof)[0].receipt)
        with self.assertRaisesRegex(ValueError, 'incomplete source'):
            _read_review_prefix(proof, through_round=1, require_complete=True)
        self.assertEqual(self.files(f), before)
        raw = f.store.read('rounds/review_index/request-1.json')
        (f.root / 'rounds/review_index/request-2.json').write_bytes(raw)
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'incomplete source'): _read_review_prefix(proof)
        self.assertEqual(self.files(f), before)

    def test_missing_raw_or_rehashed_original_bindings_refuse_without_repair(self):
        for damage in ('response', 'predecessor', 'input', 'base'):
            with self.subTest(damage=damage):
                f = self.seed()
                result = self.request(f, client=journal.Reviewer(f))
                path = f.root / 'rounds/review_index/request-1.json'
                header = json.loads(path.read_bytes())
                if damage == 'response':
                    (f.root / 'rounds/client_requests' / result.request_id / 'attempts/1/response.json').unlink()
                elif damage == 'predecessor': header['previous_request_hash'] = 'f' * 64
                elif damage == 'input': header['input_hash'] = 'f' * 64
                else: header['base_pointer']['path'] = 'rounds/verified_history/current-verified-7.json'
                path.write_bytes(canonical_json_bytes(header))
                before = self.files(f)
                proof = self.owner(f)._prove(f.store.read)
                with self.assertRaises(ValueError): _read_review_prefix(proof, through_round=1, require_complete=True)
                self.assertEqual(self.files(f), before)


if __name__ == '__main__': unittest.main()

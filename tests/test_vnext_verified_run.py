import json
import sys
import subprocess
import unittest

from whetstone.vnext_contracts import canonical_json_bytes
from whetstone.vnext_proposal_run import RUN_INPUT_PATH, round_input_path, run_input_record
from whetstone.vnext_semantic_admission import load_registered_semantic_context
from whetstone.vnext_verified_run import VerifiedRun, open_verified_run
from vnext_fixtures import STAMP
import test_vnext_verified_history as history
import test_vnext_verified_work as work


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class VerifiedRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): history.VerifiedHistoryTests.setUpClass()
    files = work.VerifiedWorkTests.files
    owner = work.VerifiedWorkTests.owner
    later_candidate = work.VerifiedWorkTests.later_candidate

    def fixture(self, *, run_contract=True):
        algorithms = ('vnext_verified_materialization_v1', 'vnext_verified_promotion_v1',
                      'vnext_verified_work_v1', 'vnext_verified_operator_v1')
        if run_contract: algorithms += ('vnext_verified_run_v1',)
        f = history.VerifiedHistoryTests.fixture(self, extra_algorithms=algorithms, register_candidate=False)
        self.persist(f)
        return f

    def persist(self, f):
        refs = f.admission._refs
        packet = run_input_record(json.loads(f.store.read_descriptor()), dict(
            descriptor_ref=refs['descriptor'], review_ref=refs['review'], seed_map_ref=refs['seed_map'], round_refs=refs['rounds']))
        with f.store.locked(f.admission.validate_authority) as token: f.store.publish(token, RUN_INPUT_PATH, packet)

    def reopen(self, f):
        f.store.close()
        run = open_verified_run(f.root, suite_path=f.admission.suite_path)
        self.addCleanup(run.close)
        f.store = run.store
        return run

    def verify(self, f, run):
        context = load_registered_semantic_context(run.store, admission=run._history(), candidate_id=f.identifier)
        verifier = history.verified.semantic.Client(context)
        self.assertTrue(run.verify(client=verifier, decided_at=STAMP).value.decision['promotion_permitted'])
        self.assertEqual(verifier.calls, 1)

    def test_reopen_seed_and_promoted_runs_resolves_later_round_without_in_memory_selectors(self):
        f = self.fixture()
        before = self.files(f)
        run = self.reopen(f)
        self.assertEqual(run.inspect().outcome, 'materialization_required')
        self.assertEqual(self.files(f), before)
        self.assertEqual(run.request(round_number=1, client=f.editor).outcome, 'materialization_recovered')
        self.assertEqual(run.request(round_number=1, client=f.editor).value.status, 'complete')
        f.creation = run.register(round_number=1, created_at=STAMP).value
        f.identifier = f.creation['candidate_id']
        self.verify(f, run)
        self.assertEqual(run.promote(prepared_at=STAMP).current_pointer['promotion_ordinal'], 1)
        self.later_candidate(f, prepare_only=True)
        # The input producer is still fixture setup. Its exact canonical
        # record, not a changed root manifest or caller history map, persists.
        record = f.store.read(f.admission._refs['rounds'][2]['path'])
        with f.store.locked(run._history().validate_authority) as token:
            f.store.publish(token, round_input_path(2), record)
        run = self.reopen(f)
        self.assertEqual(list(run._staged), [1])
        self.assertEqual(run.request(round_number=2, client=f.editor).value.status, 'complete')
        f.creation = run.register(round_number=2, created_at=STAMP).value
        f.identifier = f.creation['candidate_id']
        run = self.reopen(f)
        self.verify(f, run)
        self.assertEqual(run.promote(prepared_at=STAMP).current_pointer['promotion_ordinal'], 2)
        before = self.files(f)
        run = self.reopen(f)
        self.assertEqual(run.inspect().current_pointer['promotion_ordinal'], 2)
        self.assertEqual(self.files(f), before)
        self.assertEqual(f.editor.calls, 1)

    def test_unrelated_future_input_and_review_claim_do_not_prevent_seed_mirror_recovery(self):
        f = self.fixture()
        path = f.root / round_input_path(99)
        path.parent.mkdir(parents=True)
        path.write_bytes(b'not json')
        index = f.root / 'rounds/review_index'
        index.mkdir()
        (index / 'request-99.json').write_bytes(b'not json')
        before = self.files(f)
        run = self.reopen(f)
        self.assertEqual(run.inspect().outcome, 'materialization_required')
        self.assertEqual(self.files(f), before)
        self.assertEqual(run.request(round_number=1, client=f.editor).outcome, 'materialization_recovered')
        self.assertEqual(f.editor.calls, 0)
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'Reviewer sequence cannot be bypassed'):
            run.request(round_number=1, client=f.editor)
        self.assertEqual(self.files(f), before)

    def test_promoted_staged_mirror_repair_precedes_unrelated_runtime_claim(self):
        f = self.fixture()
        run = VerifiedRun(f.store, suite_path=f.admission.suite_path)
        run.request(round_number=1, client=f.editor)
        self.assertEqual(run.request(round_number=1, client=f.editor).value.status, 'complete')
        f.creation = run.register(round_number=1, created_at=STAMP).value
        f.identifier = f.creation['candidate_id']
        self.verify(f, run)
        run.promote(prepared_at=STAMP)
        (f.root / 'spec.md').unlink()
        index = f.root / 'rounds/review_index'; index.mkdir()
        (index / 'request-99.json').write_bytes(b'not json')
        run = self.reopen(f)
        self.assertEqual(run.inspect().outcome, 'materialization_required')
        self.assertEqual(run.request(round_number=1, client=f.editor).outcome, 'materialization_recovered')
        self.assertEqual(f.editor.calls, 1)
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'Reviewer sequence cannot be bypassed'):
            run.request(round_number=1, client=f.editor)
        self.assertEqual(self.files(f), before)

    def test_changed_manifest_or_resolved_input_cannot_refresh_existing_owner(self):
        f = self.fixture()
        run = VerifiedRun(f.store, suite_path=f.admission.suite_path)
        owner = run._history()
        owner.load_inputs(f.store.read, 1)
        source = f.root / f.admission._refs['rounds'][1]['path']
        original = source.read_bytes()
        source.write_bytes(original + b' ')
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'staged V round selector changed'):
            owner.load_inputs(f.store.read, 1)
        self.assertEqual(self.files(f), before)
        source.write_bytes(original)
        manifest = f.root / RUN_INPUT_PATH
        packet = json.loads(manifest.read_bytes())
        packet['staged_rounds'] = []
        manifest.write_bytes(canonical_json_bytes(packet))
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'retained V run selectors changed'): run.inspect()
        self.assertEqual(self.files(f), before)

    def test_canonical_round_must_match_exact_staged_bytes_before_work(self):
        f = self.fixture()
        run = VerifiedRun(f.store, suite_path=f.admission.suite_path)
        run.request(round_number=1, client=f.editor)
        source = f.store.read(f.admission._refs['rounds'][1]['path'])
        destination = f.root / round_input_path(1)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source + b' ')
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'canonical V round differs'):
            run.request(round_number=1, client=f.editor)
        self.assertEqual(self.files(f), before)
        self.assertEqual(f.editor.calls, 0)

    def test_missing_run_pin_refuses_before_repair(self):
        f = self.fixture(run_contract=False)
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'verified run algorithm is outside supported suite'):
            open_verified_run(f.root, suite_path=f.admission.suite_path)
        self.assertEqual(self.files(f), before)

    def test_proposal_mode_cannot_reopen_as_verified_mode(self):
        f = history.verified.VerifiedSemanticTests.fixture(self, mode='proposal_only',
            extra_algorithms=('vnext_verified_run_v1',))
        self.persist(f)
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'requires verified_promotion mode'):
            open_verified_run(f.root, suite_path=f.admission.suite_path)
        self.assertEqual(self.files(f), before)

    def test_fresh_process_reopens_promoted_root_without_clients_or_writes(self):
        f = self.fixture()
        run = VerifiedRun(f.store, suite_path=f.admission.suite_path)
        run.request(round_number=1, client=f.editor)
        self.assertEqual(run.request(round_number=1, client=f.editor).value.status, 'complete')
        f.creation = run.register(round_number=1, created_at=STAMP).value
        f.identifier = f.creation['candidate_id']
        self.verify(f, run)
        run.promote(prepared_at=STAMP)
        before = self.files(f)
        packet = dict(root=str(f.root), suite_path=str(f.admission.suite_path))
        script = '''import json,sys
from pathlib import Path
from whetstone import vnext_registry
from whetstone.vnext_contracts import ALGORITHM_VERSIONS
from whetstone.vnext_verified_run import open_verified_run
packet=json.loads(sys.argv[1]);root=Path(packet['root'])
manifest=json.loads(Path(packet['suite_path']).read_bytes())
job=json.loads((root/'job_descriptor.json').read_bytes())
vnext_registry.SUPPORTED_SUITES[manifest['suite_version']]=manifest['suite_digest']
vnext_registry.SUITE_ALGORITHM_VERSIONS[manifest['suite_version']]={key:job[key] for key in ALGORITHM_VERSIONS}
with open_verified_run(root,suite_path=packet['suite_path']) as run:
    result=run.inspect()
    print(json.dumps(dict(outcome=result.outcome,ordinal=result.current_pointer['promotion_ordinal'])))
'''
        result = subprocess.run([sys.executable, '-c', script, json.dumps(packet)],
                                capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(json.loads(result.stdout), dict(outcome='work_available', ordinal=1))
        self.assertEqual(self.files(f), before)


if __name__ == '__main__': unittest.main()

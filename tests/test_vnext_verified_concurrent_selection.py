"""P0 latest-candidate selection with two actual competing promotion callers.

Two candidates are prepared through component fixtures on the same seed base.
This does not weaken the normal runtime's promotion-before-new-work gate.
"""
import json
import select
import subprocess
import sys
import unittest

from whetstone.vnext_verified_materialization import STATE_FIELD, STATE_PATH
from vnext_fixtures import STAMP
import test_vnext_verified_promotion as promotion


POINTER = 'rounds/current_verified.json'
SNAPSHOT = 'rounds/verified_history/current-verified-1.json'

CALLER = '''import json,sys
from pathlib import Path
from whetstone import vnext_registry
from whetstone.vnext_contracts import ALGORITHM_VERSIONS
from whetstone.vnext_local_storage import LocalAuthorityStore, StorageBusy
from whetstone.vnext_verified_history import VerifiedHistoryAdmission
from whetstone.vnext_verified_promotion import VerifiedPromotion
packet=json.loads(sys.argv[1])
manifest=json.loads(Path(packet['suite']).read_bytes())
job=json.loads((Path(packet['root'])/'job_descriptor.json').read_bytes())
vnext_registry.SUPPORTED_SUITES[manifest['suite_version']]=manifest['suite_digest']
vnext_registry.SUITE_ALGORITHM_VERSIONS[manifest['suite_version']]={k:job[k] for k in ALGORITHM_VERSIONS}
selectors=packet['selectors']
selectors['round_refs']={int(k):v for k,v in selectors['round_refs'].items()}
def emit(**value):print(json.dumps(dict(caller=packet['caller'],**value)),flush=True)
emit(outcome='ready')
for line in sys.stdin:
    command=line.strip()
    assert command in ('hold','promote'),command
    # Each attempt opens a fresh owner with the same complete selector set.
    with LocalAuthorityStore(packet['root'],job_id=job['job_id']) as store:
        owner=VerifiedHistoryAdmission(store,suite_path=packet['suite'],**selectors)
        acquire=store.acquire
        pause=command=='hold'
        def controlled_acquire(validate):
            global pause
            token=acquire(validate)
            if pause:
                pause=False
                emit(outcome='locked')
                assert sys.stdin.readline().strip()=='continue'
            return token
        store.acquire=controlled_acquire
        try:
            result=VerifiedPromotion(store,history=owner).promote(prepared_at=packet['stamp'])
        except StorageBusy:
            emit(outcome='busy')
        else:
            emit(outcome=result.outcome,candidate_id=result.candidate_id,
                 pointer=result.current_pointer,committed=result.committed_pointer)
'''


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class ConcurrentSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): promotion.VerifiedPromotionTests.setUpClass()

    fixture = promotion.VerifiedPromotionTests.fixture
    ready = promotion.VerifiedPromotionTests.ready
    verified = promotion.VerifiedPromotionTests.verified
    files = promotion.VerifiedPromotionTests.files
    owner = promotion.VerifiedPromotionTests.owner
    run_request = promotion.VerifiedPromotionTests.run_request
    materialize_seed = promotion.VerifiedPromotionTests.materialize_seed
    later_candidate = promotion.VerifiedPromotionTests.later_candidate
    service = promotion.VerifiedPromotionTests.service

    def spawn(self, f, label, stamp):
        refs = f.admission._refs
        packet = dict(root=str(f.root), suite=str(f.admission.suite_path), caller=label, stamp=stamp,
            selectors=dict(descriptor_ref=refs['descriptor'], review_ref=refs['review'],
                           seed_map_ref=refs['seed_map'], round_refs=refs['rounds']))
        child = subprocess.Popen([sys.executable, '-u', '-c', CALLER, json.dumps(packet)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def cleanup():
            if child.poll() is None: child.kill()
            child.communicate(timeout=10)
        self.addCleanup(cleanup)
        self.assertEqual(self.receive(child), dict(caller=label, outcome='ready'))
        return child

    def receive(self, child):
        ready, _, _ = select.select([child.stdout], [], [], 180)
        self.assertTrue(ready, 'promotion caller did not reach the controlled boundary')
        line = child.stdout.readline()
        self.assertTrue(line, child.stderr.read().decode() if child.poll() is not None else 'caller closed stdout')
        return json.loads(line)

    def send(self, child, command):
        child.stdin.write((command + '\n').encode())
        child.stdin.flush()

    def test_two_verified_candidates_select_latest_with_either_process_holding_first(self):
        stamps = {'A': STAMP, 'B': '2031-01-01T00:00:00Z'}
        for first in ('A', 'B'):
            with self.subTest(first=first):
                f = self.verified()
                older = f.creation
                older_decision = f.final.decision
                clients = [f.editor, f.client]
                self.materialize_seed(f)
                self.later_candidate(f)
                newer = f.creation
                clients.extend([f.editor, f.client])
                self.assertEqual([c.calls for c in clients], [1, 1, 1, 1])
                self.assertNotEqual(older['candidate_id'], newer['candidate_id'])
                self.assertEqual([older['candidate_creation_ordinal'], newer['candidate_creation_ordinal']], [1, 2])
                for decision in (older_decision, f.final.decision):
                    self.assertEqual(decision['candidate_disposition'], 'CANDIDATE_VERIFIED')
                    self.assertTrue(decision['decision_final'])
                    self.assertTrue(decision['promotion_permitted'])
                owner = self.owner(f)
                bases = [owner.load_inputs(f.store.read, n)['base_pointer_ref'] for n in (1, 2)]
                self.assertEqual(bases[0], bases[1])
                self.assertEqual(bases[0]['path'], 'rounds/verified_history/current-verified-0.json')
                self.assertEqual(json.loads(f.store.read(POINTER))['promotion_ordinal'], 0)
                self.assertFalse(list(f.root.rglob('promotion-intent-*.json')))
                before = self.files(f)
                children = {label: self.spawn(f, label, stamps[label]) for label in ('A', 'B')}
                second = 'B' if first == 'A' else 'A'
                self.send(children[first], 'hold')
                self.assertEqual(self.receive(children[first]), dict(caller=first, outcome='locked'))
                self.assertEqual(self.files(f), before)
                self.send(children[second], 'promote')
                self.assertEqual(self.receive(children[second]), dict(caller=second, outcome='busy'))
                self.assertEqual(self.files(f), before)
                self.assertEqual([c.calls for c in clients], [1, 1, 1, 1])
                self.send(children[first], 'continue')
                result = self.receive(children[first])
                self.assertEqual(result['caller'], first)
                self.assertEqual(result['outcome'], 'promoted')
                self.assertEqual(result['candidate_id'], newer['candidate_id'])
                self.assertEqual(result['committed'], result['pointer'])
                pointer = result['pointer']
                self.assertEqual(pointer['promotion_ordinal'], 1)
                self.assertEqual(pointer['source_candidate_creation_ordinal'], 2)
                self.assertEqual(pointer['promoted_at'], stamps[first])
                self.assertEqual(json.loads(f.store.read(POINTER)), pointer)
                self.assertEqual(f.store.read(POINTER), f.store.read(SNAPSHOT))
                intent_path = pointer['promotion_intent_path']
                event_path = pointer['promotion_disposition_event_path']
                for path in (intent_path, event_path):
                    self.assertEqual(json.loads(f.store.read(path))['candidate_id'], newer['candidate_id'])
                self.assertEqual(json.loads(f.store.read(intent_path))['prepared_at'], stamps[first])
                draft = f.store.read(newer['candidate_path'])
                self.assertEqual(f.store.read('spec.md'), draft)
                self.assertEqual(f.store.read('rounds/round-2/draft_after.md'), draft)
                self.assertEqual(json.loads(f.store.read(STATE_PATH))[STATE_FIELD], pointer)
                after = self.files(f)
                self.assertEqual(set(after) - set(before), {intent_path, event_path, SNAPSHOT, 'rounds/round-2/draft_after.md'})
                for path, raw in before.items():
                    if path not in {POINTER, 'spec.md', STATE_PATH}:
                        self.assertEqual(after[path], raw, path)
                self.send(children[second], 'promote')
                repeated = self.receive(children[second])
                self.assertEqual(repeated['caller'], second)
                self.assertEqual(repeated['outcome'], 'not_eligible')
                self.assertIsNone(repeated['candidate_id'])
                self.assertIsNone(repeated['committed'])
                self.assertEqual(repeated['pointer'], pointer)
                self.assertEqual(self.service(f).inspect().outcome, 'not_eligible')
                self.assertEqual(self.files(f), after)
                self.assertEqual([c.calls for c in clients], [1, 1, 1, 1])
                self.assertEqual(len(list(f.root.rglob('promotion-intent-*.json'))), 1)
                self.assertFalse((f.root / 'rounds/verified_history/current-verified-2.json').exists())
                self.assertFalse((f.root / 'rounds/candidate_index/creation-3.json').exists())
                for child in children.values():
                    child.stdin.close()
                    child.stdin = None
                    output, errors = child.communicate(timeout=10)
                    self.assertEqual(child.returncode, 0, errors.decode())
                    self.assertEqual(output, b'')
                    self.assertEqual(errors, b'')


if __name__ == '__main__': unittest.main()

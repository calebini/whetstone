"""Immutable bootstrap is distinct from permission to use a current base."""
from pathlib import Path
import sys
import unittest

from whetstone.vnext_proposal_admission import ProposalAdmission
from vnext_consuming_suite_fixture import consuming_suite
import test_vnext_proposal_admission as fixtures


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class SeedInputBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.ProposalAdmissionTests.setUpClass()

    def test_seed_read_does_not_turn_a_changed_current_pointer_into_proposal_authority(self):
        owner = fixtures.ProposalAdmissionTests()
        owner.setUp()
        self.addCleanup(owner.doCleanups)
        admission = owner.admission
        reader, original = admission._seed_inputs(owner.store.read, expected_mode='proposal_only')
        current = owner.root / 'rounds/current_verified.json'
        current.write_bytes(b'changed authority')
        _, retained = admission._seed_inputs(owner.store.read, expected_mode='proposal_only')
        self.assertEqual(retained['base_pointer_ref'], original['base_pointer_ref'])
        self.assertEqual(retained['base'], original['seed'])
        with self.assertRaisesRegex(ValueError, 'current committed seed pointer'):
            admission._base(owner.store.read)
        snapshot = owner.root / original['base_pointer_ref']['path']
        snapshot.write_bytes(snapshot.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'canonical JSON'):
            admission._seed_inputs(owner.store.read, expected_mode='proposal_only')

    def test_fresh_verified_mode_bootstrap_does_not_enable_the_proposal_only_consumer(self):
        fixture = fixtures.fixtures.UnitPreflightTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        f = fixture.c.f
        suite, suite_path, algorithms = consuming_suite(self, Path(fixture.c.tmp.name) / 'consumer')
        # These are fresh staged inputs. No existing storage descriptor or
        # admitted run is converted from one mode into another.
        f.suite = suite
        f.job.update(editing_mode='verified_promotion', contract_suite_version=suite.version, **algorithms)
        f.rebind()
        artifacts = {p.relative_to(f.root).as_posix(): p.read_bytes() for p in f.root.rglob('*') if p.is_file()}
        class Inputs:
            def read(self, path):
                try: return artifacts[path]
                except KeyError as exc: raise FileNotFoundError(path) from exc
            def read_descriptor(self): return self.read('job_descriptor.json')
        store = Inputs()
        admission = ProposalAdmission(store, suite_path=suite_path, descriptor_ref=f.job_ref,
            review_ref=f.original.review_ref, seed_map_ref=f.map_ref, round_refs={})
        _, values = admission._seed_inputs(store.read, expected_mode='verified_promotion')
        self.assertEqual(values['job'], f.job)
        self.assertEqual(values['seed'], f.base)
        self.assertEqual(values['base_pointer_ref'], f.pointer_ref)
        with self.assertRaisesRegex(ValueError, 'requires proposal_only mode'):
            admission._base(store.read)
        for mode in ('reviewer_only', 'automatic', None):
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, 'unsupported mutable admission mode'):
                admission._seed_inputs(store.read, expected_mode=mode)


if __name__ == '__main__':
    unittest.main()

import sys
import unittest

from whetstone.vnext_contracts import canonical_json_bytes
import test_vnext_proposal_admission as fixtures


@unittest.skipUnless(sys.platform=='darwin','Local storage targets macOS/APFS')
class FreshValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.ProposalAdmissionTests.setUpClass()

    def test_reusing_admission_does_not_cache_suite_pins_or_authority_bytes(self):
        fixture=fixtures.ProposalAdmissionTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        admission=fixture.admission;store=fixture.store
        _,first=admission._base(store.read)
        for relative in ('schemas/mutation_plan_v2.schema.json','algorithms/vnext_candidate_assembly_v2.md'):
            path=fixture.suite.root/relative;raw=path.read_bytes()
            try:
                path.write_bytes(raw+b' ')
                with self.subTest(path=relative),self.assertRaisesRegex(ValueError,'pinned file digest'):
                    admission._base(store.read)
            finally:path.write_bytes(raw)
        authority=fixture.root/first['job']['authority_map_path'];raw=authority.read_bytes()
        try:
            authority.write_bytes(raw+b' ')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):admission._base(store.read)
        finally:authority.write_bytes(raw)
        _,again=admission._base(store.read)
        self.assertEqual(canonical_json_bytes(again['job']),canonical_json_bytes(first['job']))
        self.assertEqual(again['seed'],first['seed'])


if __name__=='__main__':unittest.main()

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from whetstone.vnext_contracts import canonical_json_bytes,validate_contract_suite
from whetstone.vnext_validation import ArtifactReader,validate_pointer_snapshot
from vnext_fixtures import Bundle


class PointerReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.suite=validate_contract_suite()

    def test_seed_and_promoted_snapshot_reads_use_the_store_callback(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);bundle=Bundle(root,self.suite)
            for pointer in (bundle.seed_pointer,bundle.pointer):
                with self.subTest(ordinal=pointer['promotion_ordinal']):
                    reference=bundle.save('rounds/current_verified.json',pointer)
                    bundle.save(f"rounds/verified_history/current-verified-{pointer['promotion_ordinal']}.json",pointer)
                    files={p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}
                    reads=[]
                    def read(path):
                        reads.append(path)
                        if path not in files:raise FileNotFoundError(path)
                        return files[path]
                    reader=ArtifactReader(None,self.suite,read=read)
                    before=dict(files)
                    self.assertEqual(validate_pointer_snapshot(reader,reference),pointer)
                    snapshot=f"rounds/verified_history/current-verified-{pointer['promotion_ordinal']}.json"
                    self.assertIn(snapshot,reads)
                    self.assertEqual(files,before)
                    files[snapshot]=canonical_json_bytes({**pointer,'promoted_at':'2030-01-01T00:00:00Z'})
                    with self.assertRaisesRegex(ValueError,'same-ordinal'):
                        validate_pointer_snapshot(reader,reference)
                    del files[snapshot]
                    with self.assertRaises(FileNotFoundError):validate_pointer_snapshot(reader,reference)


if __name__=='__main__':unittest.main()

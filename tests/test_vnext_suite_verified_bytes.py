from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import shutil
import unittest

from whetstone.vnext_contracts import CONTRACT_ROOT,canonical_json_bytes,validate_contract_suite


class SuiteVerifiedBytesTests(unittest.TestCase):
    def check_replacement_after_pin_read(self,kind):
        with TemporaryDirectory() as directory:
            root=Path(directory)/'contracts';shutil.copytree(CONTRACT_ROOT,root)
            manifest_path=root/'suites/vnext-contracts-1.json'
            manifest=json.loads(manifest_path.read_bytes())
            relative='schemas/job_descriptor_v2.schema.json' if kind=='schema' else manifest['fixtures'][0]['path']
            target=(root/relative).resolve();original=target.read_bytes();replacement=json.loads(original)
            if kind=='schema':replacement['required']=[]
            else:replacement['expected_result']='fail' if replacement['expected_result']=='pass' else 'pass'
            replacement=canonical_json_bytes(replacement)
            read_bytes=Path.read_bytes;changed=False
            def changing(path):
                nonlocal changed
                raw=read_bytes(path)
                if path==target and not changed:
                    changed=True;target.write_bytes(replacement)
                return raw
            with patch.object(Path,'read_bytes',new=changing):
                suite=validate_contract_suite(manifest_path)
            self.assertTrue(changed)
            if kind=='schema':self.assertIn('job_id',suite.registry.load('job_descriptor_v2')['required'])
            self.assertEqual(target.read_bytes(),replacement)
            # The next public validation must see the changed file. Reuse is
            # local to one call, never an authority cache across calls.
            with self.assertRaisesRegex(ValueError,'pinned file digest'):
                validate_contract_suite(manifest_path)

    def test_schema_parsing_uses_the_exact_hash_checked_bytes(self):
        self.check_replacement_after_pin_read('schema')

    def test_fixture_evaluation_uses_the_exact_hash_checked_bytes(self):
        self.check_replacement_after_pin_read('fixture')


if __name__=='__main__':unittest.main()

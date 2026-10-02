"""Approval parsing never upgrades an envelope or recovery into a source write."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import json
import unittest
from unittest.mock import Mock

from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_verified_source_cli import execute_source


class SourceCommandTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve(); root=self.base/'run';root.mkdir()
        self.source = self.base/'source.md';self.source.write_bytes(b'fixture')
        descriptor = dict(source_spec=dict(path=str(self.source),expected_hash=sha256_bytes(b'fixture')))
        self.run = Mock(store=SimpleNamespace(root=root, read_descriptor=lambda:canonical_json_bytes(descriptor)))
        self.run.review_apply_back.return_value = dict(eligible=False,blockers=['fixture'],assessment=None)
        self.run.recover_apply_back.return_value = dict(outcome='not_started')
        self.run.apply_back.return_value = dict(outcome='completed')
        reference = dict(path='rounds/fixture.json',hash='a'*64)
        self.assessment = dict(schema_version='vnext-apply-back-review-v1',job_id='job_'+'a'*64,
            current_verified_pointer=reference,verified_draft=reference,verified_map=reference,closeout=reference,
            source=dict(path=str(self.source),expected_hash='a'*64,parent_identity=[1,2],file_identity=[1,3],
                        metadata=dict(mode=420,uid=1,gid=1,provenance=None),mtime_ns=1,ctime_ns=1),changed=True)

    def args(self, **kwargs):
        return SimpleNamespace(**dict(dict(source=str(self.source),expected_source_hash=None,
            recover=False,apply=False,approve=False,retry_apply=False,approval=None,approval_hash=None,
            exclusive_source_access=False,dry_run=False),**kwargs))

    def approval(self,raw):
        path=self.base/'approval.json';path.write_bytes(raw)
        return self.args(apply=True,approve=True,exclusive_source_access=True,
                         approval=str(path),approval_hash=sha256_bytes(raw))

    def test_blocked_review_and_historical_recovery_do_not_require_fresh_eligibility(self):
        self.assertIsNone(execute_source(self.run,self.args())['assessment'])
        self.run.review_apply_back.side_effect=AssertionError('recovery used fresh eligibility')
        result=execute_source(self.run,self.args(recover=True,exclusive_source_access=True))
        self.assertEqual(result['outcome'],'not_started')
        self.run.apply_back.assert_not_called()
        self.assertEqual(self.source.read_bytes(),b'fixture')

    def test_only_exact_canonical_assessment_reaches_apply_owner(self):
        args=self.approval(canonical_json_bytes(self.assessment))
        execute_source(self.run,args)
        self.run.apply_back.assert_called_once_with(assessment=self.assessment,approve=True,
                                                   exclusive_source_access=True,retry=False)
        invalid=[canonical_json_bytes(dict(eligible=True,assessment=self.assessment)),b'null',
                 json.dumps(self.assessment,indent=2).encode(),canonical_json_bytes(self.assessment)+b'\n',
                 b'{"schema_version":"x","schema_version":"y"}']
        for raw in invalid:
            self.run.apply_back.reset_mock()
            with self.subTest(raw=raw[:40]),self.assertRaises(ValueError):execute_source(self.run,self.approval(raw))
            self.run.apply_back.assert_not_called()
        args=self.approval(canonical_json_bytes(self.assessment));args.approval_hash='b'*64
        with self.assertRaises(ValueError):execute_source(self.run,args)
        self.run.apply_back.assert_not_called()

    def test_recovery_write_combinations_and_source_redirection_refuse(self):
        for change in [dict(apply=True),dict(approve=True),dict(retry_apply=True),dict(approval='x'),dict(approval_hash='a'*64)]:
            with self.subTest(change=change),self.assertRaises(ValueError):
                execute_source(self.run,self.args(recover=True,exclusive_source_access=True,**change))
        with self.assertRaises(ValueError):execute_source(self.run,self.args(source=str(self.base/'other.md')))
        self.run.apply_back.assert_not_called();self.run.recover_apply_back.assert_not_called()

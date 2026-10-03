"""Answer and child-selection publication recover without clients or authority drift."""
import json
import sys
from types import SimpleNamespace
from unittest.mock import patch

from whetstone.vnext_contracts import canonical_json_bytes
from whetstone.vnext_local_storage import LocalAuthorityStore
from whetstone.vnext_verified_run import open_verified_run
from whetstone.vnext_verified_history import _VerifiedAnswerSource
from test_vnext_proposal_requests import Client as Editor
from test_vnext_semantic_answers import input_for
import test_vnext_verified_runtime_followup as runtime
import test_vnext_verified_semantic_commands as semantic
from vnext_fixtures import STAMP
from vnext_q1_command_fixtures import CommandCase


class SemanticBoundaryCommands(CommandCase):
    setUp=semantic.SemanticCommandTests.setUp

    def test_response_receipt_admission_and_marker_recover_without_reopening_parent(self):
        if sys.platform!='darwin':self.skipTest('D8 requires macOS/APFS')
        self.qualify();code,result=self.call('vnext-admit');self.assertEqual(code,0,result)
        self.reviewer.callback=canonical_json_bytes;editor=Editor();verifiers=[]
        with open_verified_run(self.root) as run:
            run.review_next(client=self.reviewer);run.admit_reviewed_round();run.request(round_number=1,client=editor)
            parent=run.register(round_number=1,created_at=STAMP).value
            f=SimpleNamespace(run=run,store=run.store,identifier=parent['candidate_id'],verifiers=verifiers)
            runtime.RuntimeFollowupTests.verify(self,f,question=True)
            source=_VerifiedAnswerSource(run.store,admission=run._history(),candidate_id=f.identifier,require_current=True)
            answer=input_for(source)
        baseline=self.files();path=self.config_path.parent/'answer.json';path.write_bytes(canonical_json_bytes(answer))
        args=('--candidate',parent['candidate_id'],'--input',str(path))
        for family in ('/responses/','/receipts/'):
            with self.lost_publication(lambda p:family in p):code,result=self.call('vnext-semantic-answer',*args)
            self.assertEqual(code,2,result)
            before=self.files()
            with patch.object(LocalAuthorityStore,'acquire',side_effect=AssertionError('preview took fence')):
                code,result=self.call('vnext-semantic-answer',*args,'--dry-run')
            self.assertEqual(code,0,result);self.assertEqual(self.files(),before)
        code,result=self.call('vnext-semantic-answer',*args);self.assertEqual(code,0,result)
        receipt=result['value']['reference']
        args=('--candidate',parent['candidate_id'],'--answer-receipt',receipt['path'],'--answer-hash',receipt['hash'])
        for suffix in ('/admission.json','/followup_transaction.json'):
            with self.lost_publication(lambda p:p.endswith(suffix)):code,result=self.call('vnext-semantic-followup',*args)
            self.assertEqual(code,2,result)
            state=self.inspect_readonly()
            self.assertEqual(state['gate'],'candidate_final' if suffix=='/admission.json' else 'proposal')
        code,result=self.call('vnext-semantic-followup',*args);self.assertEqual(code,0,result)
        selected=result['value'];self.assertEqual(self.inspect_readonly()['selected_ref'],selected)
        source=self.root/selected['path'];raw=source.read_bytes();source.write_bytes(raw+b' ')
        self.refuses('status','--format','json');self.refuses('live-phase1');source.write_bytes(raw)
        self.assertEqual((self.reviewer.calls,editor.calls,sum(v.calls for v in verifiers)),(1,1,1))
        for name,raw in baseline.items():self.assertEqual((self.root/name).read_bytes(),raw,name)
        self.assertFalse((self.root/'rounds/candidate_index/creation-2.json').exists())

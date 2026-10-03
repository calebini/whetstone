"""Finding reconciliation stays bound to one selected outcome at the D8 fence."""
from copy import deepcopy
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import Mock, call, patch

import test_vnext_local_storage as storage
from whetstone.vnext_verified_commands import resume, SelectionChanged
from whetstone.vnext_verified_run import VerifiedRun


@unittest.skipUnless(sys.platform=='darwin','D8 requires local macOS/APFS')
class FindingsGuardTests(unittest.TestCase):
    setUp=storage.LocalStorageTests.setUp
    open_store=storage.LocalStorageTests.open_store

    def scenario(self, *, changed=False):
        initial=dict(gate='findings_publication',phase='phase_2',recovery='findings_publication',
            continuation=None,findings=dict(reference=dict(path='findings/commit.json',hash='a'*64)))
        run=Mock(spec=VerifiedRun);run.store=self.store;run.state=deepcopy(initial)
        result=dict(committed=True,phase_complete=False)
        def reconcile():
            if changed:run.state['findings']['reference']['hash']='b'*64
            with self.store.locked(lambda read:None) as token:
                self.store.publish(token,'findings/commit.json',result)
                run.state=dict(gate='closeout_publication',phase='phase_2',
                               recovery='closeout_publication',continuation=None)
            return result
        run.reconcile_phase2_findings.side_effect=reconcile
        return run,initial,result

    def test_resume_stops_after_findings_even_when_closeout_is_now_ready(self):
        run,state,result=self.scenario()
        with patch('whetstone.vnext_verified_commands.inspect_command',side_effect=lambda run:deepcopy(run.state)):
            self.assertEqual(resume(run,SimpleNamespace(dry_run=False),{}, {},state),result)
        self.assertEqual(run.mock_calls,[call.reconcile_phase2_findings()])
        self.assertEqual(run.state['recovery'],'closeout_publication')

    def test_changed_reconciliation_refuses_inside_fence_before_write(self):
        run,state,_=self.scenario(changed=True)
        with patch('whetstone.vnext_verified_commands.inspect_command',side_effect=lambda run:deepcopy(run.state)):
            with self.assertRaises(SelectionChanged):resume(run,SimpleNamespace(dry_run=False),{}, {},state)
        with self.assertRaises(FileNotFoundError):self.store.read('findings/commit.json')
        self.assertIsNone(self.store._lock_fd)

    def test_dry_run_never_enters_reconciliation_owner(self):
        run,state,_=self.scenario()
        with patch.object(self.store,'acquire',side_effect=AssertionError('dry run took fence')):
            self.assertEqual(resume(run,SimpleNamespace(dry_run=True),{}, {},state),state)
        self.assertEqual(run.mock_calls,[])


if __name__=='__main__':unittest.main()

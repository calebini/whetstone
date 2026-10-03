"""Declaration maintenance must retain its selected package at its writer fence."""
from copy import deepcopy
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

import test_vnext_local_storage as storage
from whetstone.vnext_verified_commands import SelectionChanged
from whetstone.vnext_verified_phase2_commands import execute_phase2


@unittest.skipUnless(sys.platform=='darwin','D8 requires local macOS/APFS')
class TerminalGuardTests(unittest.TestCase):
    setUp=storage.LocalStorageTests.setUp
    open_store=storage.LocalStorageTests.open_store

    def invoke(self, *, changed):
        state=dict(gate='declaration_maintenance_required',recovery=None,continuation=None,
                   declaration=dict(reference={'path':'halt/declaration.json','hash':'a'*64},committed=False))
        run=SimpleNamespace(store=self.store,state=deepcopy(state),calls=[])
        def prepare():
            if changed:run.state['declaration']['committed']=True
            with self.store.locked(lambda read:None) as token:
                run.calls.append('prepare')
                self.store.publish(token,'halt/declaration.json',{'retained':'selected package'})
                run.state=dict(gate='phase2_stopped',recovery=None,continuation=None)
        run.prepare_phase2_declaration=prepare
        with (patch('whetstone.vnext_verified_phase2_commands.optional',return_value=b'entry'),
              patch('whetstone.vnext_verified_phase2_commands.inspect_command',side_effect=lambda run:deepcopy(run.state)),
              patch('whetstone.vnext_verified_commands.inspect_command',side_effect=lambda run:deepcopy(run.state))):
            if changed:
                with self.assertRaises(SelectionChanged):execute_phase2(run,SimpleNamespace(),{}, {})
                self.assertEqual(run.calls,[])
                with self.assertRaises(FileNotFoundError):self.store.read('halt/declaration.json')
            else:
                result=execute_phase2(run,SimpleNamespace(),{}, {})
                self.assertEqual(result['gate'],'phase2_stopped')
                self.assertEqual(run.calls,['prepare'])

    def test_exact_maintenance_selection_enters_the_owner_fence(self):self.invoke(changed=False)

    def test_peer_preparation_ends_stale_invocation_before_publication(self):self.invoke(changed=True)


if __name__=='__main__':unittest.main()

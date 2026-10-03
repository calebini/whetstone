"""A selected publication repairs only its own outcome under fresh fences."""
from copy import deepcopy
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

import test_vnext_local_storage as storage
from whetstone.vnext_verified_commands import repair, resume, SelectionChanged


@unittest.skipUnless(sys.platform == 'darwin', 'D8 requires local macOS/APFS')
class PublicationCommandTests(unittest.TestCase):
    setUp = storage.LocalStorageTests.setUp
    open_store = storage.LocalStorageTests.open_store

    def scenario(self, family):
        field = 'closeout' if family == 'closeout' else 'report'
        ref = dict(path='outcomes/commit.json', hash='a'*64)
        result = dict(reference=ref, state_current=False, committed=True)
        initial = dict(gate=family+'_publication', recovery=family+'_publication', phase='phase_2',
            continuation=None, sequence=dict(current_pointer=dict(path='head',hash='b'*64)))
        projected = dict(initial, gate=family+'_projection', recovery=family+'_projection', **{field:result})
        run = SimpleNamespace(store=self.store, state=initial, calls=[])
        def publish():
            with self.store.locked(lambda read: None) as token:
                run.calls.append('publish')
                self.store.publish(token, 'outcomes/commit.json', result)
                run.state = deepcopy(projected)
            return deepcopy(result)
        def project():
            with self.store.locked(lambda read: None) as token:
                run.calls.append('project')
                self.store.publish(token, 'outcomes/projection.json', ref)
            return dict(result,state_current=True)
        if family == 'resolution':
            run.publish_phase2_resolutions=publish;run.reconcile_phase2_resolution_state=project
        elif family == 'failure':
            run.publish_phase2_failure=publish;run.reconcile_phase2_failure_state=project
        else:
            run.finish_phase2=publish;run.reconcile_phase2_state=project
        return run, initial

    def test_resume_completes_one_outcome_and_stops_with_two_real_fences(self):
        run,state=self.scenario('resolution')
        with patch('whetstone.vnext_verified_commands.inspect_command',side_effect=lambda run: deepcopy(run.state)):
            result=resume(run,SimpleNamespace(dry_run=False),{}, {},state)
        self.assertTrue(result['state_current'])
        self.assertEqual(run.calls,['publish','project'])

    def test_dry_run_never_enters_publication_or_projection(self):
        run,state=self.scenario('closeout')
        self.assertEqual(resume(run,SimpleNamespace(dry_run=True),{}, {},state),state)
        self.assertEqual(run.calls,[])

    def test_reviewer_failure_publication_projects_and_stops_without_continuation(self):
        run,state=self.scenario('failure')
        with patch('whetstone.vnext_verified_commands.inspect_command',side_effect=lambda run: deepcopy(run.state)):
            result=resume(run,SimpleNamespace(dry_run=False),{}, {},state)
        self.assertTrue(result['state_current'])
        self.assertEqual(run.calls,['publish','project'])

    def test_other_outcome_cannot_replace_the_just_published_closeout(self):
        run,state=self.scenario('closeout')
        original=run.finish_phase2
        def changed():
            result=original()
            run.state['closeout']['reference']['hash']='c'*64
            return result
        run.finish_phase2=changed
        with patch('whetstone.vnext_verified_commands.inspect_command',side_effect=lambda run: deepcopy(run.state)):
            with self.assertRaisesRegex(ValueError,'published outcome changed'):
                repair(run,state,SimpleNamespace())
        self.assertEqual(run.calls,['publish'])

    def test_selection_is_rechecked_inside_projection_fence(self):
        run,state=self.scenario('resolution')
        project=run.reconcile_phase2_resolution_state
        def raced():
            run.state=dict(run.state,recovery=None,gate='review')
            return project()
        run.reconcile_phase2_resolution_state=raced
        with patch('whetstone.vnext_verified_commands.inspect_command',side_effect=lambda run: deepcopy(run.state)):
            with self.assertRaises(SelectionChanged):repair(run,state,SimpleNamespace())
        self.assertEqual(run.calls,['publish'])

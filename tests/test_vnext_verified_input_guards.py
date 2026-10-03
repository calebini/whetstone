"""Operator operands and command selection are checked at actual D8 fences."""
from copy import deepcopy
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import Mock, patch

import test_vnext_local_storage as storage
from whetstone.vnext_contracts import canonical_json_bytes
from whetstone.vnext_verified_commands import execute, SelectionChanged
from whetstone.vnext_verified_run import VerifiedRun


@unittest.skipUnless(sys.platform=='darwin','D8 requires local macOS/APFS')
class InputGuardTests(unittest.TestCase):
    setUp=storage.LocalStorageTests.setUp
    open_store=storage.LocalStorageTests.open_store
    routes=('phase1_options','phase1_selections','phase2_options','phase2_selections',
            'first_advice','later_advice','repair','gaps','answer','followup')

    def scenario(self, route, *, dry_run=False, race=None):
        phase='phase_1' if route.startswith('phase1') or route in {'answer','followup'} else 'phase_2'
        state=dict(phase=phase,gate='operator_or_advice_required',recovery=None,continuation=None,
                   sequence=dict(pass_number=2 if route=='later_advice' else 1))
        run=Mock(spec=VerifiedRun);run.store=self.store;run.state=deepcopy(state)
        packet=dict(candidate_id='candidate',selected='original')
        source=self.store.root/(route+'.json');source.write_bytes(canonical_json_bytes(packet))
        args=SimpleNamespace(command='vnext-decisions',dry_run=dry_run,options=None,advice=None,
            selections=None,repair_request=None,gap_acceptance=None,candidate='candidate',
            input=str(source),answer_receipt='answers/receipt.json',answer_hash='a'*64)
        operator=Mock();events=[]
        def perform(value, **kwargs):
            if race=='input':source.write_bytes(source.read_bytes()+b' ')
            if race=='state':run.state['gate']='peer_advanced'
            if kwargs.get('dry_run') or dry_run:
                events.append('preview');return value
            with self.store.locked(lambda read:events.append('owner')) as token:
                self.store.publish(token,'results/'+route+'.json',value)
                events.append('write')
            return value
        operator.publish.side_effect=perform
        if route.endswith('options'):args.options=str(source)
        elif route.endswith('selections'):args.command='vnext-decide';args.selections=str(source)
        elif route in {'first_advice','later_advice'}:
            args.advice=str(source)
            run.prepare_phase2_advice.side_effect=perform;run.bind_phase2_advice.side_effect=perform
            run.prepare_phase2_continuation_advice.side_effect=lambda ordinal,value:perform(value)
            run.continue_phase2_pass.side_effect=lambda ordinal,**kw:perform(kw['advice'])
        elif route in {'repair','gaps'}:
            args.command='vnext-decide'
            setattr(args,'repair_request' if route=='repair' else 'gap_acceptance',str(source))
            getattr(run,'admit_phase2_repair' if route=='repair' else 'accept_phase2_gaps').side_effect=perform
        elif route=='answer':args.command='vnext-semantic-answer';run.submit_answer.side_effect=lambda **kw:perform(kw['packet'],dry_run=kw['dry_run'])
        else:
            args.command='vnext-semantic-followup'
            run.select_followup.side_effect=lambda **kw:perform(kw)
        patches=(patch('whetstone.vnext_verified_commands.inspect_command',side_effect=lambda run:deepcopy(run.state)),
            patch('whetstone.vnext_verified_phase1_decisions.Phase1Decisions',return_value=operator),
            patch('whetstone.vnext_verified_phase2_operator.Phase2Operator',return_value=operator))
        return run,args,source,events,patches

    def invoke(self, scenario):
        run,args,_,_,patches=scenario
        with patches[0],patches[1],patches[2]:return execute(run,args,{}, {})

    def test_each_mutating_route_enters_its_selected_owner_fence(self):
        for route in self.routes:
            with self.subTest(route=route):
                case=self.scenario(route);self.invoke(case)
                self.assertEqual(case[3],['owner','write'])
                self.assertIsNone(self.store._lock_fd)

    def test_each_route_refuses_peer_advancement_before_owner_validation(self):
        for route in self.routes:
            with self.subTest(route=route):
                case=self.scenario(route,race='state')
                with self.assertRaises(SelectionChanged):self.invoke(case)
                self.assertEqual(case[3],[])
                self.assertFalse((self.store.root/'results'/f'{route}.json').exists())
                self.assertIsNone(self.store._lock_fd)

    def test_each_file_operand_rejects_even_json_equivalent_byte_replacement(self):
        for route in self.routes[:-1]:
            with self.subTest(route=route):
                case=self.scenario(route,race='input')
                with self.assertRaisesRegex(ValueError,'selected operator input changed'):self.invoke(case)
                self.assertEqual(case[3],[])
                self.assertFalse((self.store.root/'results'/f'{route}.json').exists())

    def test_all_supported_previews_take_no_writer_fence(self):
        for route in self.routes[:-1]:
            with self.subTest(route=route):
                case=self.scenario(route,dry_run=True)
                with patch.object(self.store,'acquire',side_effect=AssertionError('preview took fence')):self.invoke(case)
                self.assertEqual(case[3],['preview'])
                self.assertFalse((self.store.root/'results'/f'{route}.json').exists())

    def test_preview_detects_operand_replacement_without_publishing(self):
        case=self.scenario('answer',dry_run=True,race='input')
        with self.assertRaisesRegex(ValueError,'selected operator input changed'):self.invoke(case)
        self.assertEqual(case[3],['preview'])

    def test_mismatched_candidate_and_duplicate_input_keys_never_reach_owner(self):
        case=self.scenario('answer');case[1].candidate='other'
        with self.assertRaisesRegex(ValueError,'answer differs'):self.invoke(case)
        self.assertEqual(case[3],[])
        case=self.scenario('phase1_options');case[2].write_bytes(b'{"x":1,"x":2}')
        with self.assertRaises(ValueError):self.invoke(case)
        self.assertEqual(case[3],[])

    def test_readonly_context_and_answers_do_not_install_writer_guards(self):
        for command in ('vnext-decisions','vnext-semantic-answers'):
            case=self.scenario('answer');case[1].command=command
            with patch.object(self.store,'guard_invocation',side_effect=AssertionError('inspection guarded write')):
                self.invoke(case)
            self.assertEqual(case[3],[])


if __name__=='__main__':unittest.main()

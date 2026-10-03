"""An unrelated shared mirror must not take a report family's own repair."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from whetstone.vnext_verified_command_state import phase2_state


class ReportSelectionTests(unittest.TestCase):
    def select(self, reports):
        run=SimpleNamespace(store=SimpleNamespace(read=lambda path:b'present'),
            phase2_state=lambda:dict(state_current=True))
        for family,method in [('failure','phase2_failure_status'),
                              ('correction_failure','phase2_correction_failure_status'),
                              ('resolution','phase2_resolution_status'),('signal','phase2_signal_status')]:
            value=dict(state_current=True,mirrors_current=True)
            value.update(reports.get(family,{}))
            setattr(run,method,lambda value=value:value)
        with (patch('whetstone.vnext_verified_phase2_sequence._Continuation'),
              patch('whetstone.vnext_verified_phase2_sequence.sequence',return_value=dict(frames=[])),
              patch('whetstone.vnext_verified_phase2_sequence._status',return_value=dict(gate='review',current_pointer={'hash':'a'*64}))):
            return phase2_state(run)

    def test_own_publication_or_state_repair_precedes_unrelated_shared_mirror(self):
        for family in ('correction_failure','signal'):
            for condition,expected in [('publication_required','publication'),('state_current','projection')]:
                with self.subTest(family=family,condition=condition):
                    report=dict(state_current=True,mirrors_current=False)
                    report[condition]=condition=='publication_required'
                    result=self.select(dict(failure=dict(state_current=True,mirrors_current=False),**{family:report}))
                    self.assertEqual(result['recovery'],family+'_'+expected)
                    self.assertEqual(result['report'],report)

    def test_earlier_own_state_repair_keeps_precedence(self):
        result=self.select(dict(failure=dict(state_current=False,mirrors_current=False),
                                signal=dict(publication_required=True)))
        self.assertEqual(result['recovery'],'failure_projection')

    def test_shared_mirror_only_repair_remains_available(self):
        result=self.select(dict(failure=dict(state_current=True,mirrors_current=False)))
        self.assertEqual(result['recovery'],'failure_projection')


if __name__=='__main__':unittest.main()

"""Acceptance cannot survive a changed draft/gap or override verified resolution."""
from copy import deepcopy
import unittest

import test_vnext_phase2_rubric as rubric_rules
from whetstone.vnext_phase2_rubric import attribute
from whetstone.vnext_phase2_gap_acceptance import apply, selection


class GapAcceptanceRulesTests(unittest.TestCase):
    def test_exact_draft_gap_and_requirement_are_required_and_resolution_wins(self):
        source=rubric_rules.RubricRulesTests()
        row=attribute(source.annotations(),source.feedback(),source.raw,['first','second'])[0]
        ref={'path':'pointer','hash':'a'*64};chosen=selection(row)
        record=(dict(base_pointer=ref,gaps=[chosen]),{'path':'acceptance','hash':'b'*64})
        for change in ('none','pointer','claim','evidence','severity','requirement','resolved'):
            with self.subTest(change=change):
                current=deepcopy(row);pointer=deepcopy(ref)
                if change=='pointer':pointer['hash']='c'*64
                if change in {'claim','evidence'}:current['gap'][change]+=' Changed.'
                if change=='severity':current['gap']['normalized_severity']='blocker'
                if change=='requirement':current['requirement']['requirement_hash']='d'*64
                if change=='resolved':current['gap'].update(status='resolved',blocking_convergence=False)
                rows={row['gap']['gap_id']:current};apply(rows,[record],pointer)
                self.assertEqual(current['gap']['status'],'accepted' if change=='none' else 'resolved' if change=='resolved' else 'unresolved')
                self.assertEqual(current['gap']['blocking_convergence'],change not in {'none','resolved'})

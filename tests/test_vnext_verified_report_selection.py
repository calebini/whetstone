"""An unrelated shared mirror must not take a report family's own repair."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from whetstone.vnext_verified_command_state import phase2_state


class ReportSelectionTests(unittest.TestCase):
    def select(self, reports, *, gate='review', closeout=None, package=None, findings=None, blocked=None):
        run=SimpleNamespace(store=SimpleNamespace(read=lambda path:b'present'),
            phase2_state=lambda:dict(state_current=True),
            phase2_closeout=lambda:closeout if closeout is not None else dict(committed=False),
            phase2_final_findings=lambda:findings)
        def report():
            if blocked is None:raise AssertionError('unexpected blocked report')
            return blocked
        run.phase2_blocked_report=report
        for family,method in [('failure','phase2_failure_status'),
                              ('correction_failure','phase2_correction_failure_status'),
                              ('resolution','phase2_resolution_status'),('signal','phase2_signal_status')]:
            value=dict(state_current=True,mirrors_current=True)
            value.update(reports.get(family,{}))
            setattr(run,method,lambda value=value:value)
        with (patch('whetstone.vnext_verified_phase2_sequence._Continuation'),
              patch('whetstone.vnext_verified_phase2_sequence.sequence',return_value=dict(frames=[],clean=[])),
              patch('whetstone.vnext_verified_phase2_sequence._status',return_value=dict(gate=gate,current_pointer={'hash':'a'*64})),
              patch('whetstone.vnext_verified_phase2_halt.maintenance_owner'),
              patch('whetstone.vnext_verified_phase2_closeout._bundle',return_value=package)):
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

    def test_exhaustion_selects_exact_declaration_preparation_without_resume(self):
        package=dict(reference=dict(path='halt/declaration/commit.json',hash='b'*64),
                     pending_paths=['halt/declaration/commit.json'],committed=False,assets={'excluded':b'bytes'})
        for gate in ('budget_exhausted','closeout_required'):
            with self.subTest(gate=gate):
                result=self.select({},gate=gate,closeout=dict(gate='declaration_maintenance_required'),package=package)
                self.assertEqual(result['gate'],'declaration_maintenance_required')
                self.assertIsNone(result['recovery']);self.assertIsNone(result['continuation'])
                self.assertEqual(result['declaration'],{k:v for k,v in package.items() if k!='assets'})

    def test_exhaustion_report_readiness_selects_bounded_closeout_publication(self):
        closeout=dict(gate='failure_report_publication_required',committed=False,
                      proposed_terminal_state='TARGET_NOT_REACHED')
        result=self.select({},gate='budget_exhausted',closeout=closeout)
        self.assertEqual(result['recovery'],'closeout_publication')
        self.assertEqual(result['closeout'],closeout)

    def test_closeout_projection_precedes_its_shared_failure_mirror(self):
        closeout=dict(committed=True,state_current=False,mirror_current=False,phase_complete=False)
        result=self.select(dict(failure=dict(state_current=True,mirrors_current=False)),closeout=closeout)
        self.assertEqual(result['recovery'],'closeout_projection')

    def test_completed_halt_is_stopped_without_continuation(self):
        result=self.select({},closeout=dict(committed=True,state_current=True,mirror_current=True,
                                           halt_complete=True,phase_complete=False))
        self.assertEqual(result['gate'],'phase2_stopped')
        self.assertIsNone(result['recovery']);self.assertIsNone(result['continuation'])

    def test_completed_closeout_does_not_hide_other_shared_mirror_repair(self):
        result=self.select(dict(failure=dict(state_current=True,mirrors_current=False)),
                           closeout=dict(committed=True,state_current=True,mirror_current=True,phase_complete=False))
        self.assertEqual(result['recovery'],'failure_projection')

    def test_pending_findings_select_reconciliation_before_blocked_inspection(self):
        findings=dict(committed=False,pending_paths=['findings/commit.json'])
        result=self.select({},gate='declaration_closeout_required',findings=findings)
        self.assertEqual(result['recovery'],'findings_publication')
        self.assertEqual(result['findings'],findings)
        self.assertNotIn('blocked_report',result)

    def test_committed_disagreement_exposes_report_without_resume_permission(self):
        findings=dict(committed=True,packet=dict(blocking_reasons=['declaration_revision_required']))
        blocked=dict(report_kind='status_only',route='declaration_revision_required',repair_authorized=False)
        result=self.select({},gate='declaration_closeout_required',findings=findings,blocked=blocked)
        self.assertEqual(result['gate'],'declaration_closeout_required')
        self.assertEqual(result['findings'],findings);self.assertEqual(result['blocked_report'],blocked)
        self.assertIsNone(result['recovery']);self.assertIsNone(result['continuation'])

    def test_unblocked_findings_do_not_invoke_blocked_owner(self):
        findings=dict(committed=True,packet=dict(blocking_reasons=[]))
        result=self.select({},gate='declaration_closeout_required',findings=findings)
        self.assertEqual(result['findings'],findings);self.assertNotIn('blocked_report',result)

    def test_ready_closeout_keeps_precedence_over_blocked_inspection(self):
        result=self.select({},gate='declaration_closeout_required',
                           closeout=dict(gate='failure_report_publication_required',committed=False))
        self.assertEqual(result['recovery'],'closeout_publication')
        self.assertNotIn('blocked_report',result)


if __name__=='__main__':unittest.main()

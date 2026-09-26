"""Blocked status preserves findings and explains evidence without granting work."""
from copy import deepcopy
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_vnext_verified_phase2_findings as findings
from whetstone import vnext_verified_phase2_blocked as blocked
from whetstone.vnext_contracts import canonical_json_bytes
from whetstone.vnext_verified_materialization import STATE_PATH


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class BlockedReportTests(unittest.TestCase):
    setUpClass = findings.FinalFindingsTests.setUpClass
    fixture = findings.FinalFindingsTests.fixture
    files = findings.FinalFindingsTests.files
    reopen = findings.FinalFindingsTests.reopen
    ready = findings.FinalFindingsTests.ready
    review = findings.FinalFindingsTests.review
    config = findings.FinalFindingsTests.config
    next_client = findings.FinalFindingsTests.next_client
    advance = findings.FinalFindingsTests.advance
    clean_start = findings.FinalFindingsTests.clean_start
    final_ready = findings.FinalFindingsTests.final_ready
    consumed = findings.FinalFindingsTests.consumed
    residuals = staticmethod(findings.FinalFindingsTests.residuals)

    def start(self, **kwargs):
        return findings.FinalFindingsTests.start(self, phase2_blocked_contract=True, **kwargs)

    @staticmethod
    def serious(client, packet):
        packet = json.loads(findings.FinalFindingsTests.residuals(client, packet))
        packet['feedback'][0].update(normalized_severity='major', baseline_severity='major',
            issue_type='declaration_hash_mismatch', claim='The declaration hash is wrong.',
            evidence='Reviewer claim, not a deterministic repair certificate.',
            recommended_change='Correct the declaration hash.')
        return canonical_json_bytes(packet)

    def test_exact_evidence_and_counts_stay_unresolved_without_writes_or_extra_work(self):
        f, reviewer, client, package, bound, _, _ = self.consumed(self.serious)
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'committed finding reconciliation'):
            f.run.phase2_blocked_report()
        self.assertEqual(self.files(f), before)
        receipt = f.run.reconcile_phase2_findings()
        before = self.files(f)
        with patch.object(f.store, 'locked', side_effect=AssertionError('report took fence')):
            report = f.run.phase2_blocked_report()
        self.assertEqual(report['route'], 'declaration_revision_required')
        self.assertEqual(report['reconciliation'], receipt['reference'])
        self.assertEqual(report['declaration'], package['declaration']['declaration'])
        self.assertEqual(report['sources']['review_request'], bound.request_ref)
        self.assertEqual(report['budget'], dict(step_index=3, profile='convergence_strict_check',
                                               round_budget=3, rounds_used=1, remaining=2))
        self.assertTrue(all(r['matches'] for r in report['comparisons']['reviewed_inputs']))
        current = {r['field']: r for r in report['comparisons']['current_residuals']}
        self.assertEqual(current['unresolved_major_issues count'], dict(
            field='unresolved_major_issues count', observed='0', expected='1', matches=False))
        row = report['findings'][0]
        self.assertEqual(row['disposition'], 'unresolved')
        source = json.loads(f.store.read(row['sources'][0]['feedback']['path']))
        self.assertEqual(row['finding'], source['feedback'][0])
        self.assertEqual(row['sources'][0]['consumption'], receipt['packet']['review_consumption'])
        for key in ('automatic_repair_established', 'findings_resolved', 'repair_authorized',
                    'candidate_authorized', 'next_review_authorized', 'phase_complete'):
            self.assertIs(report[key], False)
        self.assertNotIn('terminal_state', report)
        self.assertEqual(f.run.bind_phase2_next_review(client.transport_binding)['gate'], 'declaration_closeout_required')
        with self.assertRaisesRegex(ValueError, 'no terminal'):
            f.run.finish_phase2()
        self.assertEqual(self.files(f), before)
        self.reopen(f)
        self.assertEqual(f.run.phase2_blocked_report(), report)
        script = """import json,sys
from pathlib import Path
from whetstone import vnext_registry
from whetstone.vnext_contracts import ALGORITHM_VERSIONS
from whetstone.vnext_verified_run import open_verified_run
root,suite_path=sys.argv[1:];manifest=json.loads(Path(suite_path).read_bytes())
job=json.loads((Path(root)/'job_descriptor.json').read_bytes())
vnext_registry.SUPPORTED_SUITES[manifest['suite_version']]=manifest['suite_digest']
vnext_registry.SUITE_ALGORITHM_VERSIONS[manifest['suite_version']]={k:job[k] for k in ALGORITHM_VERSIONS}
with open_verified_run(root,suite_path=suite_path) as run:
    print(json.dumps(run.phase2_blocked_report()))
"""
        child = subprocess.run([sys.executable, '-c', script, str(f.root), str(f.admission.suite_path)],
                               capture_output=True, timeout=180)
        self.assertEqual(child.returncode, 0, child.stderr.decode())
        self.assertEqual(json.loads(child.stdout), report)
        self.assertEqual(self.files(f), before)
        self.assertEqual((reviewer.calls, client.calls, f.editor.calls), (1, 2, 0))

    def test_mixed_findings_keep_authority_rubric_and_source_reasons(self):
        def response(client, packet):
            packet = json.loads(self.serious(client, packet))
            row = deepcopy(packet['feedback'][0])
            row.update(feedback_id='fb_source', affected_sections=['spec.md'], in_scope=False,
                       claim='A source requirement is missing.')
            signal = deepcopy(row)
            signal.update(feedback_id='fb_signal', normalized_severity='minor', baseline_severity='minor',
                          authority_impact='minor', rubric_impact='minor', claim='Clarify authority and rubric.')
            packet['feedback'].extend([row, signal])
            return canonical_json_bytes(packet)
        f, _, _, _, _, _, _ = self.consumed(response)
        receipt = f.run.reconcile_phase2_findings()
        before = self.files(f)
        report = f.run.phase2_blocked_report()
        self.assertEqual(report['route'], 'authority_resolution_required')
        self.assertEqual(report['blocking_reasons'], receipt['packet']['blocking_reasons'])
        self.assertIn('rubric_resolution_required', report['blocking_reasons'])
        self.assertIn('source_revision_required', report['blocking_reasons'])
        self.assertEqual(len(report['findings']), 3)
        self.assertEqual([r['field'] for r in report['comparisons']['current_residuals']],
                         ['unresolved_blockers count', 'unresolved_major_issues count'])
        self.assertEqual(self.files(f), before)

    def test_corrupt_missing_and_changed_evidence_refuse_and_cache_cannot_resolve(self):
        f, _, _, package, _, _, _ = self.consumed(self.serious)
        receipt = f.run.reconcile_phase2_findings()
        report = f.run.phase2_blocked_report()
        references = [receipt['reference'], package['declaration']['declaration'],
                      *report['sources'].values(), receipt['packet']['feedback']]
        for ref in references:
            with self.subTest(path=ref['path']):
                path = f.root / ref['path']; raw = path.read_bytes()
                path.write_bytes(raw + b' ')
                before = self.files(f)
                with self.assertRaises(ValueError): f.run.phase2_blocked_report()
                self.assertEqual(self.files(f), before)
                path.write_bytes(raw)
        path = f.root / receipt['packet']['unresolved_issues']['path']; raw = path.read_bytes(); path.unlink()
        with self.assertRaisesRegex(ValueError, 'lacks dependencies'): f.run.phase2_blocked_report()
        path.write_bytes(raw)
        feedback = f.root / receipt['packet']['feedback']['path']; raw = feedback.read_bytes()
        original = blocked._comparisons
        def drift(*args):
            result = original(*args)
            feedback.write_bytes(raw + b' ')
            return result
        with patch.object(blocked, '_comparisons', side_effect=drift):
            with self.assertRaisesRegex(ValueError, 'changed'): f.run.phase2_blocked_report()
        feedback.write_bytes(raw)
        state = json.loads(f.store.read(STATE_PATH)); state['vnext_phase2_closeout'] = {'path': 'fake', 'hash': '0'*64}
        (f.root / STATE_PATH).write_bytes(canonical_json_bytes(state))
        before = self.files(f)
        self.assertEqual(f.run.phase2_blocked_report(), report)
        self.assertEqual(self.files(f), before)

    def test_clean_and_unpinned_reviews_do_not_become_blocked_reports(self):
        f, _, _, _, _, _, _ = self.consumed(lambda c, p: canonical_json_bytes({**p, 'feedback': []}))
        f.run.reconcile_phase2_findings()
        before = self.files(f)
        with self.assertRaisesRegex(ValueError, 'requires a blocked final review'): f.run.phase2_blocked_report()
        self.assertEqual(self.files(f), before)
        with patch.object(self, 'start', side_effect=lambda **kw: findings.FinalFindingsTests.start(self, **kw)):
            old, _, _, _ = self.final_ready()
        before = self.files(old)
        with self.assertRaisesRegex(ValueError, 'outside supported suite'): old.run.phase2_blocked_report()
        self.assertEqual(self.files(old), before)

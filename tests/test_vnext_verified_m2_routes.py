"""Cross-route acceptance through unchanged entry and real Phase 2 consumers."""
from copy import deepcopy
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, sha256_bytes
import test_vnext_verified_phase1_budget as budget
import test_vnext_verified_phase2_client as clients
import test_vnext_verified_phase2_targets as targets
from test_vnext_verified_phase1_status import clean_response
import test_vnext_verified_vertical_phase1 as vertical_tests


@unittest.skipUnless(sys.platform == 'darwin', 'Local storage targets macOS/APFS')
class M2RoutesTests(unittest.TestCase):
    setUpClass = budget.BudgetTests.setUpClass
    fixture = budget.BudgetTests.fixture
    start = budget.BudgetTests.start
    review = budget.BudgetTests.review
    promote = budget.BudgetTests.promote
    reopen = budget.BudgetTests.reopen
    files = budget.BudgetTests.files
    exhausted = budget.BudgetTests.exhausted
    response = targets.TargetRuntimeTests.response
    advance = targets.TargetRuntimeTests.advance
    target = ('final','strict')

    def phase2(self, f, prior):
        config = targets.TargetRuntimeTests.config(self,f)
        mode=json.loads(f.store.read(f.run._record['review_configuration']['path']))['review_mode']
        config.update(schema_version='vnext-phase2-configuration-v3',review_mode=mode)
        f.run.bind_phase2_entry(config)
        f.run.enter_phase2()
        transport=deepcopy(prior.transport_binding)
        transport['output_schema_hash']=sha256_bytes((CONTRACT_ROOT/'schemas/vnext_phase2_rubric_response_v1.schema.json').read_bytes())
        client=clients.Client(transport,prior.feedback,callback=self.response(gaps=False))
        f.run.prepare_phase2_declaration()
        bound=f.run.bind_phase2_review(transport)
        return client,bound

    def complete(self, f, client):
        self.assertEqual(f.run.run_phase2_review(client=client).status,'complete')
        f.run.consume_phase2_result()
        self.advance(f,client)
        self.assertEqual(f.run.phase2_sequence_status()['gate'],'declaration_closeout_required')
        f.run.reconcile_phase2_findings()
        self.assertEqual(f.run.finish_phase2()['packet']['terminal_state'],'CONVERGED')
        self.assertTrue(f.run.reconcile_phase2_state()['phase_complete'])
        self.reopen(f)
        self.assertTrue(f.run.phase2_closeout()['committed'])
        before=self.files(f)
        with self.assertRaisesRegex(ValueError,'cannot supersede bound Phase 2'):
            f.run.reconcile_phase1_state()
        self.assertEqual(self.files(f),before)

    def test_extended_horizontal_and_vertical_finish_phase2_with_preserved_phase1_history(self):
        for vertical in (False,True):
            with self.subTest(vertical=vertical):
                f, prior, old=self.exhausted(vertical=vertical,routes_contract=True)
                f.run.extend_phase1_budget(added_rounds_per_profile=1)
                prior.callback=clean_response
                for _ in range(2 if vertical else 1):f.run.review_next(client=prior)
                f.run.finish_phase1();f.run.reconcile_phase1_state()
                self.reopen(f)
                with patch('whetstone.live_phase2.LivePhase2Runner',side_effect=AssertionError('legacy executor')):
                    client,bound=self.phase2(f,prior)
                    self.assertEqual(bound.request['round_number'],6 if vertical else 3)
                    self.complete(f,client)
                self.assertEqual(f.store.read(old.evidence_ref['path']),canonical_json_bytes(old.evidence))
                self.assertEqual(len(json.loads(f.store.read('rounds/run_state.json'))['budget_extensions']),1)

    def test_final_synthetic_noop_is_counted_before_entry_and_recovery(self):
        f,prior=self.start(mode='vertical',vertical_contract=True,routes_contract=True,
            profiles=[{'name':'structural_integrity','budget':1},{'name':'determinism','budget':1}])
        def minor(packet):
            for row in packet['feedback']['feedback']:
                row.update(baseline_severity='minor',normalized_severity='minor',in_scope=False)
            for row in packet['classifications']:row['classification']='deferable'
            return canonical_json_bytes(packet)
        prior.callback=minor
        vertical_tests.VerticalPhase1Tests.cycle(self,f,prior)
        self.assertEqual(f.run.review_next().status,'merge_complete')
        closeout=f.run.finish_phase1();self.assertEqual(closeout.evidence['round_number'],3)
        f.run.reconcile_phase1_state();self.reopen(f)
        client,bound=self.phase2(f,prior)
        self.assertEqual(bound.request['round_number'],4)
        self.complete(f,client)
        self.assertEqual(f.editor.calls,0)


if __name__ == '__main__':unittest.main()

"""Offline command qualification of system-only versioned Phase 2 entry."""
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_contracts import sha256_bytes
from whetstone.vnext_local_storage import LocalAuthorityStore
from whetstone.vnext_verified_phase2_entry import ENTRY_PATH
from whetstone.vnext_verified_run import open_verified_run
import test_vnext_verified_cli as cli


@unittest.skipUnless(sys.platform == 'darwin', 'D8 requires local macOS/APFS')
class VersionEntryCommandTests(unittest.TestCase):
    setUpClass = cli.VerifiedCLITests.setUpClass
    patch = cli.VerifiedCLITests.patch
    qualify = cli.VerifiedCLITests.qualify
    save_config = cli.VerifiedCLITests.save_config
    clean = staticmethod(cli.VerifiedCLITests.clean)
    invoke = cli.VerifiedCLITests.invoke
    files = cli.VerifiedCLITests.files
    stage_phase2 = cli.VerifiedCLITests.stage_phase2

    def setUp(self):
        cli.VerifiedCLITests.setUp(self)
        self.f.base = self.f.base.replace(b'# Queue\n', b'# Queue 0.17\nStatus: Accepted v0.17\n')
        self.f.rebind()
        self.fixture.package['job_descriptor'] = self.f.job_ref
        self.fixture.constraint_ref = self.f.save('inputs/mutation-constraints.json',
            dict(schema_version='vnext-mutation-constraints-v1', constraints=self.f.constraints))
        self.fixture.package['mutation_constraints'] = self.fixture.constraint_ref
        self.fixture.save_package()
        self.config['vnext_input_package']['hash'] = sha256_bytes(
            (self.fixture.source/'proposal_package.json').read_bytes())
        self.save_config()
        self.patch('whetstone.live_phase2.LivePhase2Runner', side_effect=AssertionError('legacy executor'))

    def call(self, command, *args):
        print('  command: '+command+' '+' '.join(args), file=sys.stderr, flush=True)
        code, result = self.invoke(command, *args)
        print('  result: '+str(code)+' '+str(result.get('gate', result.get('reason', result.get('outcome')))),
              file=sys.stderr, flush=True)
        return code, result

    def test_configuration_change_at_binding_and_version_fences_refuses_before_writes(self):
        from whetstone.vnext_verified_phase2_binding import REQUEST_PATH
        self.qualify()
        code, result = self.call('live-phase1'); self.assertEqual(code, 0, result)
        self.stage_phase2()
        path = self.root/self.config['vnext_phase2_configuration']['path']
        raw = path.read_bytes()
        acquire = LocalAuthorityStore.acquire
        for bound in (False, True):
            if bound:
                with open_verified_run(self.root) as run:
                    run.bind_phase2_entry(json.loads(raw))
            before = self.files()
            races = []
            def raced(store, validate):
                path.write_bytes(raw+b' ')
                races.append(True)
                return acquire(store, validate)
            try:
                with patch.object(LocalAuthorityStore, 'acquire', raced):
                    code, result = self.call('promote-phase2')
                self.assertEqual(code, 2, result)
                self.assertIn('configuration hash differs', result['reason'])
                self.assertEqual(races, [True])
            finally:
                path.write_bytes(raw)
            self.assertEqual(self.files(), before)
            self.assertEqual((self.root/REQUEST_PATH).exists(), bound)
            self.assertFalse((self.root/ENTRY_PATH).exists())
        self.assertEqual(self.phase2_reviewer.calls, 0)

    def test_version_candidate_promotes_before_distinct_entry_and_recovery_stops(self):
        from test_vnext_semantic_requests import Client
        from whetstone.vnext_semantic_admission import load_registered_semantic_context
        self.qualify()
        code, result = self.call('live-phase1'); self.assertEqual(code, 0, result)
        self.stage_phase2()
        phase1_calls = self.reviewer.calls
        verifiers = []
        def verifier(**kwargs):
            with open_verified_run(self.root) as run:
                history = run._history(); creation = history.inspect().creations[-1]
                context = load_registered_semantic_context(run.store, admission=history,
                    candidate_id=creation['candidate_id'])
                self.assertEqual(context.packet['admitted_findings'], [])
                self.assertIn('system_entry', context.packet)
            client = Client(context); verifiers.append(client); return client
        self.patch('whetstone.vnext_proposal_cli.NativeSemanticVerifierClient', side_effect=verifier)
        before = self.files()
        code, result = self.call('status', '--format', 'json'); self.assertEqual(code, 0, result)
        self.assertEqual(self.files(), before)
        publish = LocalAuthorityStore.publish
        faults = []
        def before_entry(store, token, path, packet):
            if path == ENTRY_PATH:
                faults.append(path)
                raise OSError('fixture stopped before entry commit')
            return publish(store, token, path, packet)
        with patch.object(LocalAuthorityStore, 'publish', before_entry):
            code, result = self.call('promote-phase2')
        self.assertEqual(code, 2, result); self.assertEqual(faults, [ENTRY_PATH], result)
        self.assertFalse((self.root/ENTRY_PATH).exists())
        head = (self.root/'rounds/current_verified.json').read_bytes()
        self.assertEqual(json.loads(head)['promotion_ordinal'], 1)
        self.assertIn(b'# Queue 1.0', (self.root/'spec.md').read_bytes())
        self.assertEqual(sum(c.calls for c in verifiers), 1)
        before = self.files()
        code, state = self.call('status', '--format', 'json'); self.assertEqual(code, 0, state)
        self.assertEqual(state['gate'], 'entry_required')
        code, result = self.call('resume'); self.assertEqual(code, 2, result)
        self.assertEqual(self.files(), before)

        def after_entry(store, token, path, packet):
            result = publish(store, token, path, packet)
            if path == ENTRY_PATH: raise OSError('fixture lost entry commit acknowledgement')
            return result
        with patch.object(LocalAuthorityStore, 'publish', after_entry):
            code, result = self.call('promote-phase2')
        self.assertEqual(code, 2, result)
        entry = (self.root/ENTRY_PATH).read_bytes()
        self.assertEqual(json.loads(entry)['version'], dict(before='0.17', after='1.0', changed=True))
        before = self.files()
        code, state = self.call('status', '--format', 'json'); self.assertEqual(code, 0, state)
        self.assertEqual(state['recovery'], 'entry')
        code, result = self.call('resume', '--dry-run'); self.assertEqual(code, 0, result)
        code, result = self.call('promote-phase2'); self.assertEqual(code, 2, result)
        self.assertEqual(self.files(), before)
        code, result = self.call('resume'); self.assertEqual(code, 0, result)
        self.assertEqual(result['outcome'], 'phase2_entry_recovered')
        self.assertTrue(result['committed'] and result['state_current'])
        before = self.files()
        code, state = self.call('status', '--format', 'json'); self.assertEqual(code, 0, state)
        self.assertEqual(state['gate'], 'first_review_binding')
        code, result = self.call('promote-phase2'); self.assertEqual(code, 0, result)
        code, result = self.call('resume'); self.assertEqual(code, 2, result)
        self.assertEqual(self.files(), before)
        self.assertEqual((self.root/ENTRY_PATH).read_bytes(), entry)
        self.assertEqual((self.root/'rounds/current_verified.json').read_bytes(), head)
        self.assertEqual((self.reviewer.calls, self.phase2_reviewer.calls), (phase1_calls, 0))
        self.assertEqual(sum(c.calls for c in verifiers), 1)
        self.assertFalse((self.root/'rounds/proposal_requests').exists())
        history = (self.root/'spec.history.md').read_bytes()
        self.assertEqual(history.count(b'`0.17` -> `1.0`'), 1)


if __name__ == '__main__': unittest.main()

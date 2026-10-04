"""Q1 source-command journeys write only descriptor-bound disposable fixtures."""
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
import sys
import unittest
from unittest.mock import patch

from whetstone.cli import main
from whetstone import vnext_apply_back as apply_owner
from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_local_storage import LocalAuthorityStore
from whetstone.vnext_verified_run import open_verified_run
from vnext_q1_command_fixtures import CommandCase


@unittest.skipUnless(sys.platform == 'darwin', 'D8 requires local macOS/APFS')
class SourceCommands(CommandCase):
    def configure_source(self, *, unchanged=False):
        self.source = self.root.parent.resolve()/'external-source.md'
        self.source.write_bytes(self.f.base if unchanged else self.f.base.replace(b'\n', b'\r\n'))
        self.f.job['source_spec'] = dict(path=str(self.source), expected_hash=sha256_bytes(self.source.read_bytes()))
        self.f.rebind()
        self.fixture.package.update(job_descriptor=self.f.job_ref, review_configuration=self.f.original.review_ref)
        self.fixture.save_package()
        self.config['vnext_input_package']['hash'] = sha256_bytes((self.fixture.source/'proposal_package.json').read_bytes())
        self.save_config(); self.qualify()
        self.patch('whetstone.cli.apply_back', side_effect=AssertionError('legacy source executor'))
        self.patch('whetstone.cli.LivePhase2Runner', side_effect=AssertionError('legacy Phase 2 executor'))

    def converge(self):
        code, result = self.call('live-phase1'); self.assertEqual(code, 0, result)
        self.stage_phase2()
        # Source policy accepts current CONVERGED evidence for every supported
        # target. Use one ordinary mid/permissive review; target matrix is pass 2.
        with open_verified_run(self.root) as run:
            packet = json.loads(run.store.read(self.config['vnext_phase2_configuration']['path']))
            packet.update(target_phase='mid', target_mode='permissive')
            raw = canonical_json_bytes(packet); path = 'inputs/phase2/source-test-configuration.json'
            with run.store.locked(run._history().validate_authority) as token: run.store.publish(token, path, raw)
        self.config['vnext_phase2_configuration'] = dict(path=path, hash=sha256_bytes(raw)); self.save_config()
        code, result = self.call('live-phase2'); self.assertEqual(code, 0, result)
        self.assertTrue(result.get('phase_complete') or result.get('gate') == 'phase2_complete', result)
        self.client_counts = (self.reviewer.calls, self.phase2_reviewer.calls)
        self.assertEqual(self.phase2_reviewer.calls, 1)

    def source_call(self, command='strop', *args, code=0):
        print('  source command: '+command+' '+' '.join(args), file=sys.stderr, flush=True)
        output = StringIO()
        with redirect_stdout(output):
            actual = main([command, '--run-root', str(self.root), '--source', str(self.source),
                           '--config', str(self.config_path), *args])
        result = json.loads(output.getvalue())
        print('  source result: '+str(actual)+' '+str(result.get('outcome', result.get('reason', result.get('blockers', result.get('eligible'))))),
              file=sys.stderr, flush=True)
        self.assertEqual(actual, code, result)
        return result

    def readonly(self, command='strop', *args, code=0):
        before = self.files(); source = self.source.read_bytes() if self.source.exists() else None
        with patch.object(LocalAuthorityStore, 'acquire', side_effect=AssertionError('read-only source command took fence')):
            result = self.source_call(command, *args, code=code)
        self.assertEqual(self.files(), before)
        self.assertEqual(self.source.read_bytes() if self.source.exists() else None, source)
        return result

    def approval(self):
        result = self.readonly()
        self.assertTrue(result['eligible'], result); self.assertFalse(result['apply_back_permitted'])
        raw = canonical_json_bytes(result['assessment'])
        path = self.source.parent/'approval.json'; path.write_bytes(raw)
        return result['assessment'], ['--apply', '--approve', '--exclusive-source-access',
            '--approval', str(path), '--approval-hash', sha256_bytes(raw)]

    def clients_unchanged(self):
        self.assertEqual((self.reviewer.calls, self.phase2_reviewer.calls), self.client_counts)

    def test_exact_approval_alias_replay_and_historical_source_drift(self):
        self.configure_source(); self.converge(); packet, args = self.approval()
        self.assertTrue(packet['changed']); original = self.source.read_bytes(); before = self.files()
        for omitted in ('--approve', '--exclusive-source-access'):
            self.source_call('strop', *[a for a in args if a != omitted], code=2)
        self.readonly('apply-back', '--allow-source-hash-mismatch', code=2)
        self.assertEqual(self.files(), before); self.assertEqual(self.source.read_bytes(), original)
        # A validly shaped but stale approval must reach and fail the real owner.
        stale = deepcopy(packet); stale['verified_map']['hash'] = '0'*64
        path = self.source.parent/'stale.json'; raw = canonical_json_bytes(stale); path.write_bytes(raw)
        self.source_call('strop', *args[:3], '--approval', str(path), '--approval-hash', sha256_bytes(raw), code=2)
        self.assertEqual(self.files(), before)
        result = self.source_call('apply-back', *args); self.assertEqual(result['outcome'], 'completed')
        self.assertTrue(result['applied']); self.assertEqual(self.source.read_bytes(), (self.root/'spec.md').read_bytes())
        inode = self.source.stat().st_ino; applied = self.files()
        with patch.object(apply_owner.SourceFile, 'replace', side_effect=AssertionError('replay replaced source')):
            self.assertEqual(self.source_call('strop', *args)['outcome'], 'completed')
            self.assertEqual(self.source_call('apply-back', '--recover', '--exclusive-source-access')['outcome'], 'completed')
        self.assertEqual(self.files(), applied); self.assertEqual(self.source.stat().st_ino, inode)
        self.source.write_bytes(b'# Independent fixture edit\n')
        review = self.readonly('apply-back'); self.assertFalse(review['eligible']); self.assertIsNone(review['assessment'])
        self.assertTrue(review['recovery']['historical_completion']); self.assertEqual(review['recovery']['outcome'], 'source_drift')
        with patch.object(apply_owner.SourceFile, 'replace', side_effect=AssertionError('drift overwritten')):
            result = self.source_call('strop', '--recover', '--exclusive-source-access')
        self.assertEqual(result['outcome'], 'source_drift'); self.assertFalse(result['source_matches_result'])
        self.assertEqual(self.files(), applied); self.assertEqual(self.source.read_bytes(), b'# Independent fixture edit\n')
        for name in ('rounds/current_verified.json', 'convergence_declaration.md'):
            self.assertEqual(self.files()[name], before[name])
        self.clients_unchanged()

    def test_precommit_recovery_requires_explicit_exact_retry(self):
        self.configure_source(); self.converge(); packet, args = self.approval(); original = self.source.read_bytes()
        with self.lost_publication(lambda p: p == apply_owner.INTENT):
            self.source_call('strop', *args, code=2)
        intent = (self.root/apply_owner.INTENT).read_bytes(); before = self.files()
        with patch.object(apply_owner.SourceFile, 'replace', side_effect=AssertionError('implicit source retry')):
            self.assertEqual(self.source_call('strop', '--recover', '--exclusive-source-access')['outcome'], 'apply_required')
            self.assertEqual(self.source_call('apply-back', *args)['outcome'], 'apply_required')
        self.assertEqual(self.files(), before); self.assertEqual(self.source.read_bytes(), original)
        result = self.source_call('apply-back', *args, '--retry-apply')
        self.assertEqual(result['outcome'], 'completed'); self.assertEqual((self.root/apply_owner.INTENT).read_bytes(), intent)
        self.assertEqual(self.source.read_bytes(), (self.root/'spec.md').read_bytes()); self.clients_unchanged()

    def test_uncertain_write_and_receipt_ack_recover_without_replacement(self):
        self.configure_source(); self.converge(); packet, args = self.approval()
        with self.lost_publication(lambda p: p == apply_owner.RECEIPT, after=False):
            self.source_call('strop', *args, code=2)
        self.assertEqual(self.source.read_bytes(), (self.root/'spec.md').read_bytes()); inode = self.source.stat().st_ino
        review = self.readonly(); self.assertEqual(review['recovery']['outcome'], 'receipt_recovery_required')
        with patch.object(apply_owner.SourceFile, 'replace', side_effect=AssertionError('recovery replaced source')):
            with self.lost_publication(lambda p: p == apply_owner.RECEIPT):
                self.source_call('apply-back', '--recover', '--exclusive-source-access', code=2)
            result = self.source_call('strop', '--recover', '--exclusive-source-access')
        self.assertEqual(result['outcome'], 'completed'); self.assertEqual(self.source.stat().st_ino, inode)
        self.clients_unchanged()

    def test_unfinished_diagnostics_no_intent_recovery_and_noop(self):
        self.configure_source(unchanged=True)
        code, result = self.call('vnext-admit'); self.assertEqual(code, 0, result)
        result = self.readonly(); self.assertFalse(result['eligible']); self.assertIsNone(result['assessment'])
        before = self.files()
        result = self.source_call('apply-back', '--recover', '--exclusive-source-access')
        self.assertEqual(result['outcome'], 'not_started'); self.assertEqual(self.files(), before)
        self.converge(); packet, args = self.approval(); self.assertFalse(packet['changed'])
        inode = self.source.stat().st_ino
        with patch.object(apply_owner.SourceFile, 'replace', side_effect=AssertionError('no-op replaced')):
            result = self.source_call('strop', *args)
        self.assertEqual(result['outcome'], 'completed'); self.assertFalse(result['applied'])
        self.assertEqual(self.source.stat().st_ino, inode); self.assertFalse((self.root/apply_owner.PREPARED).exists())
        self.clients_unchanged()


if __name__ == '__main__': unittest.main()

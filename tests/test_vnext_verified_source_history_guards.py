"""Historical source approval selection, independent of a scheduler restart route.

Proof/readback doubles isolate a later proven current pointer. These are owner
composition guards, not an end-to-end post-convergence promotion campaign.
"""
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from whetstone import vnext_apply_back as module
from whetstone.vnext_contracts import sha256_bytes


class HistoricalSourceGuards(unittest.TestCase):
    def setUp(self):
        self.before, self.after = b'before\r\n', b'verified\n'
        ref = lambda path: dict(path=path, hash='a'*64)
        self.packet = dict(schema_version='vnext-apply-back-review-v1', job_id='job_'+'a'*64,
            current_verified_pointer=ref('rounds/verified_history/current-verified-0.json'),
            verified_draft=dict(path='rounds/seed.md', hash=sha256_bytes(self.after)),
            verified_map=ref('rounds/seed-map.json'), closeout=ref('rounds/closeout.json'), changed=True,
            source=dict(path='/fixture/source.md', expected_hash=sha256_bytes(self.before),
                parent_identity=[1,2], file_identity=[1,3], metadata=dict(mode=420,uid=1,gid=1,provenance=None),
                mtime_ns=1, ctime_ns=1))
        self.intent = module.make_intent(self.packet)
        self.prepared = dict(intent=module._ref(module.INTENT,self.intent), request_id=self.intent['request_id'],
            stage_name='.whetstone-apply-'+self.intent['request_id']+'-fixture', file_identity=[1,4])
        self.proof = Mock()
        self.proof.latest = ref('rounds/verified_history/current-verified-1.json')
        self.proof.seed_values = dict(job=dict(job_id=self.packet['job_id'], editing_mode='verified_promotion',
            source_spec={k:self.packet['source'][k] for k in ('path','expected_hash')}))
        pointer = dict(verified_draft_path=self.packet['verified_draft']['path'],
            verified_draft_hash=self.packet['verified_draft']['hash'],
            verified_section_identity_map_path=self.packet['verified_map']['path'],
            verified_section_identity_map_hash=self.packet['verified_map']['hash'])
        closeout = dict(current_verified_pointer=self.packet['current_verified_pointer'], accepted=True,
            terminal_state='CONVERGED', **{k:ref('rounds/'+k) for k in ('final_declaration','terminal_report',
            'review_result','review_consumption','configuration','entry','declaration_binding')})
        def values(reference):
            if reference != self.packet['current_verified_pointer']: raise ValueError('unproven historical base')
            return dict(base=self.after)
        self.proof.values.side_effect = values
        self.proof.reader.raw.side_effect = lambda reference: self.before if reference == self.intent['preimage'] else self.after
        def read_json(reference, *args):
            if reference == self.packet['current_verified_pointer']: return pointer
            if reference == self.packet['closeout']: return closeout
            raise AssertionError('unexpected reference')
        self.proof.reader.json.side_effect = read_json
        self.store = Mock(); self.run = SimpleNamespace(store=self.store, _history=Mock(return_value=SimpleNamespace(store=self.store)))
        self.owner = module.ApplyBack(self.run)
        self.owner.proof = Mock(return_value=self.proof)
        self.token = object()
        @contextmanager
        def locked(validate):
            validate(self.store.read); yield self.token
        self.store.locked.side_effect = locked
        self.records = {module.INTENT:self.intent, module.PREPARED:self.prepared}
        p = patch.object(module,'_read',side_effect=lambda store,path,schema:self.records.get(path))
        p.start(); self.addCleanup(p.stop)

    def test_retained_approval_uses_proven_ancestor_and_rejects_unproven_retarget(self):
        result = self.owner.intent(self.proof)
        self.assertEqual(result,(self.intent,self.before,self.after,self.prepared))
        self.proof.values.assert_called_once_with(self.packet['current_verified_pointer'])
        changed = deepcopy(self.packet); changed['current_verified_pointer'] = self.proof.latest
        self.records[module.INTENT] = module.make_intent(changed)
        with self.assertRaisesRegex(ValueError,'unproven historical base'): self.owner.intent(self.proof)
        self.store.publish.assert_not_called()

    def test_historical_recovery_ignores_current_eligibility_but_retry_rechecks_it(self):
        self.owner.status = Mock(side_effect=[dict(outcome='receipt_recovery_required'), dict(outcome='completed')])
        self.owner.assess = Mock(side_effect=ValueError('current pointer no longer has eligible convergence'))
        with patch.object(module,'SourceFile') as factory:
            source = factory.return_value.__enter__.return_value
            source.parent_identity = self.packet['source']['parent_identity']
            self.assertEqual(self.owner.recover(exclusive_source_access=True)['outcome'],'completed')
            source.synchronize.assert_called_once_with(self.token,raw=self.after,
                identity=self.prepared['file_identity'],metadata=self.packet['source']['metadata'])
            source.prepare.assert_not_called(); source.replace.assert_not_called()
        self.owner.assess.assert_not_called()
        self.store.publish.assert_called_once_with(self.token,module.RECEIPT,module.make_receipt(self.intent,self.prepared))
        self.store.publish.reset_mock()
        self.owner.status = Mock(return_value=dict(outcome='apply_required',historical_completion=False))
        with patch.object(module,'SourceFile') as factory:
            with self.assertRaisesRegex(ValueError,'current pointer'):
                self.owner.apply(assessment=self.packet,approve=True,exclusive_source_access=True,retry=True)
            source = factory.return_value.__enter__.return_value
            source.prepare.assert_not_called(); source.replace.assert_not_called()
        self.owner.assess.assert_called_once(); self.store.publish.assert_not_called()


if __name__ == '__main__': unittest.main()

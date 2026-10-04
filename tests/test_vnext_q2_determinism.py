"""P0-13 differential corpus: a separate stdlib-only executable vs production."""
import ast
import base64
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_assembly import assemble_bytes
from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_identity import candidate_id
from whetstone.vnext_section_lineage import candidate_section_map
from whetstone.vnext_semantic_admission import load_registered_semantic_context
from whetstone.vnext_verified_semantics import VerifiedSemanticDecisionJournal
from vnext_fixtures import STAMP
from vnext_q2_fixtures import Editor, fixture
import test_vnext_patch_operations as operations
import test_vnext_version_operations as versions
import test_vnext_verified_work as work
import test_vnext_semantic_requests as semantic

REFERENCE = Path(__file__).with_name('vnext_q2_reference.py')


def reference(packet):
    # Isolated interpreter has no src/tests search path and uses only stdlib.
    result = subprocess.run([sys.executable, '-I', str(REFERENCE)], input=json.dumps(packet).encode(),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
    if result.returncode: raise ValueError(result.stderr.decode())
    return json.loads(result.stdout)


def assembly_packet(base, mapping, plan, proposal):
    return dict(task='assemble',base=base64.b64encode(base).decode(),mapping=mapping,plan=plan,patch=proposal.patch,
                payloads={k:base64.b64encode(v).decode() for k,v in proposal.payloads.items()})


class IndependentAssemblyTests(unittest.TestCase):
    setUpClass = operations.PatchOperationTests.setUpClass

    def setUp(self):
        self.c = operations.PatchOperationTests(); self.c.setUp(); self.addCleanup(self.c.doCleanups)

    def compare(self, packet):
        c=self.c;proposal=c.prepare(packet)
        return self.compare_inputs(c.a.base,c.a.mapping,c.plan,proposal)

    def compare_inputs(self, base, mapping, plan, proposal):
        packet=assembly_packet(base,mapping,plan,proposal)
        before=deepcopy(packet)
        # Reference runs first; no production candidate/map is supplied to it.
        expected=reference(packet)
        assembled=assemble_bytes(base=base,section_map=mapping,plan=plan,proposal=proposal)
        actual_map=candidate_section_map(base=base,base_map=mapping,proposal=proposal,assembled=assembled)
        actual=dict(candidate=base64.b64encode(assembled.raw).decode(),candidate_hash=sha256_bytes(assembled.raw),
            section_map=actual_map,map_hash=sha256_bytes(canonical_json_bytes(actual_map)),version_operation=assembled.version_operation,
            candidate_id=candidate_id(plan['transaction_id'],sha256_bytes(base),sha256_bytes(canonical_json_bytes(proposal.patch)),
                                      assembled.assembler_version,assembled.normalization_version))
        self.assertEqual(canonical_json_bytes(expected),canonical_json_bytes(actual))
        self.assertEqual(packet,before)
        return packet,expected

    def test_reference_is_stdlib_only_and_receives_no_expected_outputs(self):
        imports=set()
        for node in ast.walk(ast.parse(REFERENCE.read_text())):
            if isinstance(node,ast.Import):imports.update(n.name.split('.')[0] for n in node.names)
            if isinstance(node,ast.ImportFrom):imports.add(node.module.split('.')[0])
        self.assertLessEqual(imports,{'base64','copy','hashlib','json','re','sys'})
        self.assertNotIn('whetstone',imports)
        packet,result=self.compare(self.c.packet('replace_section_body',b'Wait more precisely.\n'))
        self.assertEqual(set(packet),{'task','base','mapping','plan','patch','payloads'})
        # A changed payload must not produce the former answer by golden lookup.
        altered=deepcopy(packet);key=next(iter(altered['payloads']));altered['payloads'][key]=base64.b64encode(b'Changed.\n').decode()
        with self.assertRaisesRegex(ValueError,'payload hash mismatch'):reference(altered)
        self.assertNotEqual(result['candidate_hash'],sha256_bytes(self.c.a.base))

    def test_all_six_operations_and_identity_replacement(self):
        for kind,raw in [('replace_section_body',b'Wait precisely.\n'),
            ('replace_section_subtree',b'## Timing renamed\nWait.\n### Details\nKeep exact precision.\n'),
            ('insert_section_before',b'## Before\nExample.\n'),('insert_section_after',b'## After\nExample.\n'),
            ('append_child_section',b'### Examples\n#### First\nOne.\n#### Second\nTwo.\n')]:
            with self.subTest(kind=kind):self.compare(self.c.packet(kind,raw))
        packet=self.c.packet('replace_section_subtree',b'## Different\nBody.\n')
        packet['operations'][0]['preserve_target_identity']=False
        _,result=self.compare(packet);self.assertTrue(any(r['status']=='retired' for r in result['section_map']['sections']))
        self.c.authorize_timing_deletion();self.compare(self.c.packet('delete_section_subtree',None))

    def test_shared_anchor_topology_order_and_array_permutation(self):
        c=self.c; packet=c.packet('insert_section_after',b'## Later\n')
        child=c.packet('append_child_section',b'### Child\n',label='child')['operations'][0]
        packet['operations'][0]['depends_on_operation_ids']=['child'];packet['operations'].append(child)
        _,first=self.compare(packet);packet['operations'].reverse()
        _,second=self.compare(packet);self.assertEqual(first,second)
        packet=c.packet('insert_section_after',b'## One\n')
        second=c.packet('insert_section_after',b'## Two\n',label='second')['operations'][0]
        second['depends_on_operation_ids']=['first'];packet['operations'].append(second)
        self.compare(packet)

    def test_unicode_fences_normalization_and_duplicate_heading_lineage(self):
        c=self.c;c.f.base=b'# Queue\r\n\r\n## Timing\r\n### Detail\r\nSame.\r\n### Detail\r\nSame.\r\n## Reports\r\nReport.\r\n'
        c.f.rebind();c.refresh()
        self.compare(c.packet('replace_section_body','Café waits.  \r\n```md\r\n## not a heading\r\n```\r\n'.encode()))
        self.compare(c.packet('replace_section_subtree',b'## Timing renamed\n### Detail\nSame.\n### Detail\nSame.\n'))
        self.compare(c.packet('append_child_section','### Résumé!\nBody.\n'.encode()))

    def test_reordered_renamed_and_moved_descendants(self):
        c=self.c
        c.f.base=b'# Queue\n## Timing\n### One\nA.\n### Two\nB.\n### Parent\n#### Moved\nBody.\n##### Detail\nSame.\n##### Detail\nSame.\n## Reports\nReport.\n'
        c.f.rebind();c.refresh()
        self.compare(c.packet('replace_section_subtree',b'## Timing renamed\n### Two\nB.\n### Renamed one\nA.\n### Parent\n### Moved\nBody.\n#### Detail\nSame.\n#### Detail\nSame.\n'))

    def test_global_join_and_ambiguous_lineage_refuse_in_both(self):
        c=self.c
        for payload in (b'No trailing newline.',b'```\nUnclosed fence\n'):
            proposal=c.prepare(c.packet('replace_section_body',payload))
            with self.assertRaises(ValueError):reference(assembly_packet(c.a.base,c.a.mapping,c.plan,proposal))
            with self.assertRaises(ValueError):assemble_bytes(base=c.a.base,section_map=c.a.mapping,plan=c.plan,proposal=proposal)
        c.f.base=b'# Queue\n## Timing\n### Detail\nOld A.\n### Detail\nOld B.\n## Reports\nReport.\n'
        c.f.rebind();c.refresh()
        proposal=c.prepare(c.packet('replace_section_subtree',b'## Timing\n### Detail\nNew A.\n### Detail\nNew B.\n'))
        with self.assertRaisesRegex(ValueError,'ambiguous'):reference(assembly_packet(c.a.base,c.a.mapping,c.plan,proposal))
        assembled=assemble_bytes(base=c.a.base,section_map=c.a.mapping,plan=c.plan,proposal=proposal)
        with self.assertRaisesRegex(ValueError,'ambiguous'):candidate_section_map(base=c.a.base,base_map=c.a.mapping,proposal=proposal,assembled=assembled)
        # Identical siblings at unequal depths are not an unchanged ordered
        # stream when only one depth changes; ordinal zipping would guess IDs.
        c.f.base=b'# Queue\n## Timing\n#### Detail\nSame.\n### Detail\nSame.\n## Reports\nReport.\n'
        c.f.rebind();c.refresh()
        proposal=c.prepare(c.packet('replace_section_subtree',b'## Timing\n### Detail\nSame.\n### Detail\nSame.\n'))
        with self.assertRaisesRegex(ValueError,'ambiguous'):reference(assembly_packet(c.a.base,c.a.mapping,c.plan,proposal))
        assembled=assemble_bytes(base=c.a.base,section_map=c.a.mapping,plan=c.plan,proposal=proposal)
        with self.assertRaisesRegex(ValueError,'ambiguous'):candidate_section_map(base=c.a.base,base_map=c.a.mapping,proposal=proposal,assembled=assembled)

    def test_v3_metadata_candidates_match_all_anchors_and_phase_arithmetic(self):
        helper=versions.VersionCandidateTests();helper.setUpClass();self.addCleanup(helper.doCleanups)
        for label in ('0.17','0.99','1','2.03.004'):
            with self.subTest(label=label):
                f=helper.fixture()
                f.c.f.base=f.c.f.base.replace(b'0.17',label.encode())
                f.c.f.base=b'---\nVersion: '+label.encode()+b'\n---\nVersion: '+label.encode()+b'\n'+f.c.f.base
                f.c.f.rebind();_,inputs=helper.candidate(f)
                self.compare_inputs(inputs['base'],inputs['base_map'],inputs['plan'],inputs['proposal'])
        # The same validated metadata algorithm also owns Phase 2 arithmetic.
        from whetstone.vnext_version_operations import project
        import vnext_q2_reference as ref
        for phase,transition in [('phase_1','round'),('phase_2','round'),('phase_2','phase2_entry')]:
            for label in ('0.99','1','2.03.004'):
                base=f'# Queue {label}\nStatus: Accepted v{label}\n## Body\nKeep.\n'.encode()
                proposed=base if transition=='phase2_entry' else base+b'More.\n'
                plan=dict(job_id='fixture',transaction_id='fixture',system_metadata=dict(phase=phase,transition=transition))
                self.assertEqual(ref.metadata(base,proposed,plan)[0],project(base,proposed,phase=phase,transition=transition)[0])
                if transition=='round':
                    for unchanged in (base,base.replace(b'Keep.\n',b'Keep.  \r\n')):
                        result=ref.metadata(base,unchanged,plan)
                        self.assertEqual(result[0],project(base,unchanged,phase=phase,transition=transition)[0])
                        self.assertEqual(result[1]['edits'],[])


@unittest.skipUnless(sys.platform=='darwin','D8 requires local macOS/APFS')
class IndependentSelectionTests(unittest.TestCase):
    setUpClass=work.VerifiedWorkTests.setUpClass
    owner=work.VerifiedWorkTests.owner
    service=work.VerifiedWorkTests.service
    files=work.VerifiedWorkTests.files
    later_candidate=work.VerifiedWorkTests.later_candidate
    stop_after_intent=work.VerifiedWorkTests.stop_after_intent

    def fresh(self):
        f=fixture(self,b'# Queue\n## Timing\nQueue waits.\n',[['timing']])
        f.editor=Editor([('Timing','replace_section_body','Queue waits before starting.\n',False)])
        self.assertEqual(f.work.request(round_number=1,client=f.editor).value.status,'complete')
        return f

    def register(self,f):
        f.creation=f.work.register(round_number=1,created_at=STAMP).value;f.identifier=f.creation['candidate_id']
        return f.creation

    def verify(self,f):
        context=load_registered_semantic_context(f.store,admission=self.owner(f),candidate_id=f.identifier)
        client=semantic.Client(context)
        self.assertTrue(f.work.verify(client=client,decided_at=STAMP).value.decision['promotion_permitted'])
        self.assertEqual(client.calls,1)

    def later_rejected(self,f):
        # Timestamp order deliberately disagrees with creation-ordinal order.
        with patch('test_vnext_verified_promotion.STAMP','2020-01-01T00:00:00Z'):
            self.later_candidate(f,reject=True)
        # This unmarked prose needs a semantic rejection, not an invented
        # deterministic weakening judgment based on the helper's name.
        from whetstone.vnext_verified_semantics import run_verified_semantic_request
        context=load_registered_semantic_context(f.store,admission=f.admission,candidate_id=f.identifier)
        client=semantic.Client(context);response=json.loads(client.valid)
        response.update(verdict='reject',unrelated_semantic_change='detected')
        client.responses=[canonical_json_bytes(response)]
        self.assertEqual(run_verified_semantic_request(f.store,admission=f.admission,
            candidate_id=f.identifier,client=client).status,'complete')
        self.assertEqual(f.decisions.commit_semantic(f.identifier,decided_at=STAMP).decision['candidate_disposition'],
                         'CANDIDATE_REJECTED')

    def compare(self,f):
        raw=self.files(f)
        expected=reference(dict(task='select',artifacts={p:base64.b64encode(v).decode() for p,v in raw.items()}))
        self.assertEqual(expected,reference(dict(task='select',artifacts={p:base64.b64encode(raw[p]).decode() for p in reversed(list(raw))})))
        proof=self.service(f)._proof(f.store.read);proof.inspect_registry()
        latest=proof.view.creations[-1] if proof.view.creations else None
        journal=VerifiedSemanticDecisionJournal(proof.router.registry(),admission=proof.router)
        state=journal._state(latest)[0] if latest else None
        promoted=next((p for p in proof.pointers if latest and p['source_candidate_id']==latest['candidate_id']),None)
        event_ref=(dict(path=promoted['promotion_disposition_event_path'],hash=promoted['promotion_disposition_event_hash']) if promoted else state.effective_event_ref if state else None)
        selection=None if proof.view.orphans else self.service(f)._select(proof)
        actual=dict(latest_candidate=latest['candidate_id'] if latest else None,creation_ordinal=latest['candidate_creation_ordinal'] if latest else None,
            disposition='CANDIDATE_PROMOTED' if promoted else state.effective_event['new_disposition'] if state else None,
            effective_event=event_ref,decision=dict(path=state.pointer['current_decision_path'],hash=state.pointer['current_decision_hash']) if state and state.pointer else None,
            promotion_candidate=selection.creation['candidate_id'] if selection else None,orphans=list(proof.view.orphans))
        self.assertEqual(expected,actual);self.assertEqual(self.files(f),raw)
        return expected,raw

    def test_current_suite_candidate_and_every_commit_boundary_agree(self):
        f=self.fresh();self.compare(f)
        publish=f.store.publish
        def stop(token,path,value):
            if path=='rounds/candidate_index/creation-1.json':raise OSError('before creation')
            return publish(token,path,value)
        with patch.object(f.store,'publish',side_effect=stop):
            with self.assertRaises(OSError):self.register(f)
        state,_=self.compare(f);self.assertIsNone(state['latest_candidate']);self.assertEqual(len(state['orphans']),1)
        creation=f.work.recover_registration().latest_candidate;f.creation=creation;f.identifier=creation['candidate_id']
        state,_=self.compare(f);self.assertEqual(state['disposition'],'CANDIDATE_UNVERIFIED')
        # Same admitted current-suite inputs, independent candidate/map/hash output.
        proof=self.owner(f)._prove(f.store.read);inputs=proof.router.load_inputs.for_proposal(f.store.read,1,creation['proposal_id'])
        from whetstone.vnext_unit_preflight import prepare_unit_preflight
        from whetstone.vnext_proposals import PreparedProposal
        plan=prepare_unit_preflight(**inputs).plan
        prefix=f"rounds/round-1/proposals/{creation['proposal_id']}"
        proposal=json.loads(f.store.read(prefix+'/proposed_patch.json'))
        payloads={op['payload']['path']:f.store.read(prefix+'/'+op['payload']['path']) for op in proposal['operations']}
        packet=assembly_packet(inputs['base'],inputs['base_map'],plan,PreparedProposal(proposal,payloads))
        independent=reference(packet)
        self.assertEqual(base64.b64decode(independent['candidate']),f.store.read(creation['candidate_path']))
        self.assertEqual(canonical_json_bytes(independent['section_map']),f.store.read(creation['candidate_section_identity_map_path']))
        self.assertEqual(independent['candidate_hash'],creation['candidate_hash']);self.assertEqual(independent['candidate_id'],creation['candidate_id'])
        # Effective event is the committed nonfinal decision, not merely the
        # candidate-created event, even though both say UNVERIFIED.
        from whetstone.vnext_proposal_handoff import registry_for_proposal_requests
        registry=registry_for_proposal_requests(f.store,load_inputs=f.admission.load_inputs,
                                               validate_authority=f.admission.validate_authority)
        VerifiedSemanticDecisionJournal(registry,admission=f.admission).commit(f.identifier,decided_at=STAMP)
        state,_=self.compare(f);self.assertEqual(state['disposition'],'CANDIDATE_UNVERIFIED')
        self.assertIsNotNone(state['decision'])
        self.verify(f);self.compare(f)
        self.stop_after_intent(f);state,_=self.compare(f);self.assertEqual(state['disposition'],'CANDIDATE_VERIFIED')
        # An uncommitted event/snapshot must not confer promoted disposition.
        publish=f.store.publish
        def stop_snapshot(token,path,value):
            result=publish(token,path,value)
            if path=='rounds/verified_history/current-verified-1.json':raise OSError('before pointer')
            return result
        with patch.object(f.store,'publish',side_effect=stop_snapshot):
            with self.assertRaises(OSError):self.service(f).promote(prepared_at=STAMP)
        state,_=self.compare(f);self.assertEqual(state['disposition'],'CANDIDATE_VERIFIED')
        self.assertEqual(self.service(f).promote(prepared_at=STAMP).outcome,'promoted')
        state,raw=self.compare(f);self.assertEqual(state['disposition'],'CANDIDATE_PROMOTED')
        # The independent reader refuses a changed bound map and creation chain.
        for path in (creation['candidate_section_identity_map_path'],'rounds/candidate_index/creation-1.json'):
            bad={**raw,path:raw[path]+b' '}
            with self.subTest(path=path),self.assertRaises(ValueError):reference(dict(task='select',artifacts={p:base64.b64encode(v).decode() for p,v in bad.items()}))
        self.assertEqual(f.editor.calls,1)

    def test_later_rejection_cannot_displace_reserved_older_promotion(self):
        f=self.fresh();first=self.register(f);self.verify(f);self.stop_after_intent(f)
        self.later_rejected(f)
        state,_=self.compare(f)
        self.assertEqual(state['latest_candidate'],f.identifier)
        self.assertEqual(state['disposition'],'CANDIDATE_REJECTED')
        self.assertEqual(state['promotion_candidate'],first['candidate_id'])
        self.assertEqual(self.service(f).promote(prepared_at=STAMP).candidate_id,first['candidate_id'])
        state,_=self.compare(f);self.assertEqual(state['disposition'],'CANDIDATE_REJECTED');self.assertIsNone(state['promotion_candidate'])

    def test_latest_rejection_prevents_fallback_without_claimant(self):
        f=self.fresh();self.register(f);self.verify(f)
        self.later_rejected(f)
        state,_=self.compare(f)
        self.assertEqual(state['creation_ordinal'],2);self.assertEqual(state['disposition'],'CANDIDATE_REJECTED')
        self.assertIsNone(state['promotion_candidate'])
        self.assertEqual(self.service(f).promote(prepared_at=STAMP).outcome,'not_eligible')


if __name__=='__main__':unittest.main()

"""Exact historical first-round output translated losslessly to forbidden patch intent."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

from whetstone.vnext_contracts import canonical_json_bytes, sha256_bytes
from whetstone.vnext_sections import section_spans
from vnext_q2_fixtures import fixture
import test_vnext_proposal_requests as requests
import test_vnext_verified_work as work

GOLDEN=Path(__file__).parent/'fixtures/vnext_q2/recurrence_first_round'


def historical_edits(base,after):
    """Only encode exact existing top-level subtrees, without synthesizing text."""
    old=section_spans(base);new=section_spans(after)
    assert old[0].heading==new[0].heading
    before={s.heading:s for s in old if s.level==2}
    following={s.heading:s for s in new if s.level==2}
    assert set(following)<=set(before)
    assert [s for s in before if s in following]==list(following)
    assert base[:old[0].heading_end]==after[:new[0].heading_end]
    body=after[new[0].heading_end:new[0].direct_end]
    edits=[]
    if body!=base[old[0].heading_end:old[0].direct_end]:
        edits.append((old[0].heading,'replace_section_body',body))
    reconstructed=base[:old[0].heading_end]+body
    for name,span in before.items():
        if name not in following:
            edits.append((name,'delete_section_subtree',None));continue
        successor=following[name];raw=after[successor.start:successor.end]
        reconstructed+=raw
        if raw!=base[span.start:span.end]:edits.append((name,'replace_section_subtree',raw))
    assert reconstructed==after,'historical translation must preserve the exact golden output'
    return edits,[s.canonical_id for s in old if s.level<=2]


class HistoricalEditor(requests.Client):
    def __init__(self,edits):self.edits=edits;super().__init__(self.response)
    def response(self,response):
        inputs=json.loads(self.prompts[-1].splitlines()[-1]);operations=[];payloads=[]
        prototype=response['patch']['operations'][0]
        for i,(heading,kind,raw) in enumerate(self.edits,1):
            target=next(s for s in inputs['target_sections'] if s['content'].splitlines()[0].lstrip('# ').strip()==heading)
            path=f'historical-{i}.md'
            op={**deepcopy(prototype),'operation_id':f'historical-{i}','operation_type':kind,
                'target_stable_section_id':target['stable_section_id'],'expected_target_hash':target['section_hash'],
                'normative_change':'remove' if raw is None else 'clarification',
                'payload':dict(path=None,hash=None) if raw is None else dict(path=path,hash=sha256_bytes(raw))}
            operations.append(op)
            if raw is not None:payloads.append(dict(path=path,content=raw.decode()))
        response['patch']['operations']=operations;response['payloads']=payloads
        return canonical_json_bytes(response)


@unittest.skipUnless(sys.platform=='darwin','D8 qualification requires local macOS/APFS')
class RecurrenceGoldenTests(unittest.TestCase):
    setUpClass=classmethod(lambda cls:work.VerifiedWorkTests.setUpClass())
    owner=work.VerifiedWorkTests.owner

    def test_historical_body_loss_refuses_current_consumer_with_m3_metadata(self):
        originals=[(GOLDEN/name).read_bytes() for name in ('draft_before.md','draft_after.md')]
        adapted=[]
        for raw in originals:
            lines=raw.splitlines(keepends=True)
            self.assertTrue(lines[2].startswith(b'Status: Draft v0.3.'))
            # Explicit derived fixture, never represented as original bytes:
            # strip the numeric run suffix and leave version stamping to M3.
            lines[2]=b'Status: Draft v0.3.1\n'
            derived=b''.join(lines)
            self.assertEqual(derived.split(b'\n',3)[3],raw.split(b'\n',3)[3])
            adapted.append(derived)
        base,after=adapted;edits,targets=historical_edits(base,after)
        f=fixture(self,base,[targets],claims=['Clarify recurrence wording while preserving every existing requirement.'])
        job=json.loads(f.store.read('job_descriptor.json'))
        self.assertEqual((job['contract_suite_version'],job['assembler_version']),
                         ('vnext-verified-consumer-1','patch-assembler-v3'))
        editor=HistoricalEditor(edits)
        result=f.work.request(round_number=1,client=editor)
        self.assertEqual(result.value.status,'invalid_proposal',result.value)
        self.assertRegex(result.value.last_outcome['error'],r'delet|remov')
        self.assertEqual(editor.calls,1)
        self.assertEqual(f.store.read('rounds/current_verified.json'),f.base_pointer)
        self.assertEqual(f.store.read('spec.md'),base)
        self.assertFalse((f.root/'rounds/candidate_index/creation-1.json').exists())
        self.assertFalse((f.root/'rounds/verified_history/current-verified-1.json').exists())

    def test_original_metadata_refuses_current_consumer_before_editor(self):
        base=(GOLDEN/'draft_before.md').read_bytes();after=(GOLDEN/'draft_after.md').read_bytes()
        edits,targets=historical_edits(base,after)
        f=fixture(self,base,[targets],claims=['Clarify recurrence wording while preserving every existing requirement.'])
        editor=HistoricalEditor(edits)
        before={p.relative_to(f.root):p.read_bytes() for p in f.root.rglob('*') if p.is_file()}
        with self.assertRaisesRegex(ValueError,'ambiguous numeric version anchor'):
            f.work.request(round_number=1,client=editor)
        self.assertEqual(editor.calls,0)
        self.assertEqual(before,{p.relative_to(f.root):p.read_bytes() for p in f.root.rglob('*') if p.is_file()})

    def test_p0_12_original_loss_replays_under_pinned_v2_before_registration_or_promotion(self):
        provenance=json.loads((GOLDEN/'provenance.json').read_text())
        base=(GOLDEN/'draft_before.md').read_bytes();after=(GOLDEN/'draft_after.md').read_bytes()
        for name,raw in [('draft_before.md',base),('draft_after.md',after)]:
            self.assertEqual(sha256_bytes(raw),provenance['source_files'][name]['sha256'])
            self.assertEqual(len(raw),provenance['source_files'][name]['bytes'])
        self.assertEqual(len(provenance['resolved_issue_ids']),3)
        edits,targets=historical_edits(base,after)
        self.assertEqual([heading for heading,kind,_ in edits if kind=='delete_section_subtree'],
                         provenance['removed_top_level_sections'])
        f=fixture(self,base,[targets],claims=['Clarify recurrence wording while preserving every existing requirement.'],
                  legacy_assembly=True)
        self.assertEqual(json.loads(f.store.read('job_descriptor.json'))['assembler_version'],'patch-assembler-v2')
        editor=HistoricalEditor(edits)
        result=f.work.request(round_number=1,client=editor)
        self.assertEqual(result.value.status,'invalid_proposal',result.value)
        self.assertRegex(result.value.last_outcome['error'],r'delet|remov')
        self.assertEqual(editor.calls,1)
        self.assertEqual(f.store.read('rounds/current_verified.json'),f.base_pointer)
        self.assertEqual(f.store.read('spec.md'),base)
        self.assertIsNone(f.work.inspect().latest_candidate)
        self.assertFalse((f.root/'rounds/candidate_index/creation-1.json').exists())
        self.assertFalse((f.root/'rounds/verified_history/current-verified-1.json').exists())
        self.assertFalse(list(f.root.glob('rounds/client_requests/*/semantic_result.json')))
        # The raw rejected response remains evidence and cannot be retried implicitly.
        before={p.relative_to(f.root):p.read_bytes() for p in f.root.rglob('*') if p.is_file()}
        again=f.work.request(round_number=1,client=editor)
        self.assertEqual(again.value.status,'invalid_proposal')
        self.assertEqual(editor.calls,1)
        self.assertEqual(before,{p.relative_to(f.root):p.read_bytes() for p in f.root.rglob('*') if p.is_file()})

"""Ratified internal M4 review, explicit source replacement and recovery.

No public dispatch, automatic source repair, client calls or lineage mutation.
A single immutable intent binds one source operation for this isolated run.
"""
from copy import deepcopy
import difflib
import secrets

from whetstone.vnext_contracts import (
    CONTRACT_ROOT, VNextSchemaRegistry, canonical_json_bytes, confined_file,
    content_identifier, decode_json, require, sha256_bytes,
)
from whetstone.vnext_local_storage import _FORK_GATE, StorageWriteError, Publication
from whetstone.vnext_source_file import SourceFile
from whetstone.vnext_verified_phase2_closeout import _Declaration

ALGORITHM = 'algorithms/vnext_apply_back_v1.md'
SCHEMAS = ('vnext_apply_back_review_v1', 'vnext_apply_back_intent_v1',
           'vnext_apply_back_prepared_v1', 'vnext_apply_back_receipt_v1')
DIRECTORY = 'rounds/apply_back'
INTENT = DIRECTORY + '/intent.json'
PREPARED = DIRECTORY + '/prepared.json'
RECEIPT = DIRECTORY + '/receipt.json'
PREIMAGE = DIRECTORY + '/source_before.md'


def _ref(path, value):
    return dict(path=path, hash=sha256_bytes(value if isinstance(value,bytes) else canonical_json_bytes(value)))


def _pins(proof):
    entries = {r['path']:r['sha256'] for k in ('algorithms','schemas') for r in proof.reader.suite.manifest[k]}
    for path in [ALGORITHM] + ['schemas/'+name+'.schema.json' for name in SCHEMAS]:
        require(path in entries and entries[path] == sha256_bytes(confined_file(CONTRACT_ROOT,path).read_bytes()),
                'apply-back contract is absent or changed', path)


def _read(store, path, schema):
    try: raw = store.read(path)
    except FileNotFoundError: return None
    packet = decode_json(raw)
    VNextSchemaRegistry().validate(packet, schema)
    require(raw == canonical_json_bytes(packet), 'noncanonical apply-back record', path)
    return packet


def _source(proof):
    job = proof.seed_values['job']; source = job['source_spec']
    require(job['editing_mode'] == 'verified_promotion', 'apply-back requires verified promotion mode')
    require(source['path'] is not None and source['expected_hash'] is not None,
            'source binding absent; inspection only')
    return source


class ApplyBack:
    def __init__(self, run):
        self.run, self.store = run, run.store
        self.owner = _Declaration(run)

    def proof(self, read):
        proof = self.owner._proof(read); _pins(proof); return proof

    def assess(self, proof, source):
        work = self.owner._observe(proof)
        require(work.outcome == 'work_available', 'apply-back blocked by '+work.outcome)
        view = self.owner._closeout(proof)
        public = self.owner._public(proof,view)
        require(public.get('phase_complete') and view['packet']['terminal_state'] == 'CONVERGED',
                'apply-back requires complete current convergence')
        report = proof.reader.json(view['packet']['terminal_report'], 'terminal_report_v2')
        require(not report['outstanding_decision_ids'], 'apply-back has outstanding decisions')
        require(view['packet']['current_verified_pointer'] == proof.latest, 'apply-back closeout is stale')
        expected = _source(proof)
        raw, observation = source.observe()
        require(str(source.path) == expected['path'] and sha256_bytes(raw) == expected['expected_hash'],
                'external source hash mismatch')
        head = proof.pointers[-1]
        draft = dict(path=head['verified_draft_path'],hash=head['verified_draft_hash'])
        selected = proof.reader.raw(draft)
        from whetstone.text_validation import validate_generated_text
        validate_generated_text(selected.decode('utf-8'), context='verified apply-back')
        packet = dict(schema_version='vnext-apply-back-review-v1',job_id=expected_job(proof),
            current_verified_pointer=deepcopy(proof.latest),verified_draft=draft,
            verified_map=dict(path=head['verified_section_identity_map_path'],hash=head['verified_section_identity_map_hash']),
            closeout=deepcopy(view['reference']),source=dict(path=expected['path'],expected_hash=expected['expected_hash'],
                **observation),changed=raw != selected)
        VNextSchemaRegistry().validate(packet, SCHEMAS[0])
        proof.guard(self.store.read); self.run._guard(self.store.read)
        return packet, raw, selected, view

    def review(self):
        try:
            proof = self.proof(self.store.read)
            if _read(self.store,INTENT,SCHEMAS[1]) is not None:
                return dict(eligible=False,apply_back_permitted=False,blockers=['existing_apply_back_intent'],
                            recovery=self.status(proof=proof),assessment=None)
            with SourceFile(self.store,_source(proof)['path']) as source:
                packet, before, after, _ = self.assess(proof, source)
            return dict(eligible=True,apply_back_permitted=False,blockers=[],assessment=packet,
                diff=''.join(difflib.unified_diff(before.decode('utf-8').splitlines(True),after.decode('utf-8').splitlines(True),
                    fromfile=packet['source']['path'],tofile=packet['verified_draft']['path'])))
        except (ValueError, OSError) as exc:
            return dict(eligible=False,apply_back_permitted=False,blockers=[str(exc)],assessment=None)

    def intent(self, proof):
        intent = _read(self.store,INTENT,SCHEMAS[1])
        if intent is None: return None
        packet = intent['assessment']; expected = _source(proof)
        require(packet['job_id'] == expected_job(proof) and packet['source']['path'] == expected['path']
                and packet['source']['expected_hash'] == expected['expected_hash'], 'apply-back intent source/job changed')
        require(intent == make_intent(packet), 'apply-back intent differs from approval')
        before = proof.reader.raw(intent['preimage'])
        require(sha256_bytes(before) == expected['expected_hash'], 'apply-back preimage differs from descriptor')
        # A later pointer cannot retarget the historical source-write approval.
        values = proof.values(packet['current_verified_pointer'])
        pointer = proof.reader.json(packet['current_verified_pointer'],'current_verified_pointer_v1')
        require(packet['verified_draft'] == dict(path=pointer['verified_draft_path'],hash=pointer['verified_draft_hash'])
                and packet['verified_map'] == dict(path=pointer['verified_section_identity_map_path'],hash=pointer['verified_section_identity_map_hash']),
                'apply-back approved lineage differs')
        after = proof.reader.raw(packet['verified_draft']); proof.reader.raw(packet['verified_map'])
        require(values['base'] == after and packet['changed'] == (before != after), 'apply-back approved bytes differ')
        closeout = proof.reader.json(packet['closeout'])
        require(closeout['current_verified_pointer'] == packet['current_verified_pointer']
                and closeout['accepted'] and closeout['terminal_state'] == 'CONVERGED', 'apply-back approved closeout differs')
        for name in ('final_declaration','terminal_report','review_result','review_consumption','configuration','entry','declaration_binding'):
            proof.reader.raw(closeout[name])
        prepared = _read(self.store,PREPARED,SCHEMAS[2])
        if prepared is not None:
            require(prepared['intent'] == _ref(INTENT,intent) and prepared['request_id'] == intent['request_id']
                    and prepared['stage_name'].startswith('.whetstone-apply-'+intent['request_id']+'-'),
                    'apply-back preparation differs from intent')
        return intent, before, after, prepared

    def status(self, *, proof=None):
        proof = proof or self.proof(self.store.read)
        retained = self.intent(proof)
        if retained is None: return dict(outcome='not_started',applied=False,source_write_permitted=False)
        intent, before, after, prepared = retained
        packet = intent['assessment']; receipt = _read(self.store,RECEIPT,SCHEMAS[3])
        if receipt is not None:
            require(receipt == make_receipt(intent,prepared), 'apply-back receipt differs from intent/preparation')
        try:
            with SourceFile(self.store,packet['source']['path']) as source:
                raw, seen = source.observe()
                parent_ok = seen['parent_identity'] == packet['source']['parent_identity']
                expected_identity = prepared['file_identity'] if prepared else packet['source']['file_identity']
                is_after = parent_ok and raw == after and seen['file_identity'] == expected_identity and seen['metadata'] == packet['source']['metadata']
                is_before = raw == before and seen == observation(packet)
                if receipt:
                    outcome = 'completed' if is_after else 'source_drift'
                elif is_after and (prepared is not None or not packet['changed']): outcome = 'receipt_recovery_required'
                elif is_before: outcome = 'apply_required'
                else: outcome = 'operator_attention_required'
                result = dict(outcome=outcome,applied=receipt is not None and packet['changed'],
                    historical_completion=receipt is not None,source_matches_result=is_after,
                    observed_source_hash=sha256_bytes(raw),source_write_permitted=False)
        except (OSError,ValueError) as exc:
            result = dict(outcome='operator_attention_required',applied=receipt is not None and packet['changed'],
                historical_completion=receipt is not None,source_matches_result=False,source_write_permitted=False,reason=str(exc))
        proof.guard(self.store.read); self.run._guard(self.store.read)
        return {**result,'intent':_ref(INTENT,intent),'receipt':_ref(RECEIPT,receipt) if receipt else None}

    def apply(self, *, assessment, approve=False, exclusive_source_access=False, retry=False):
        require(approve is True and exclusive_source_access is True, 'explicit approval and exclusive source access are required')
        require(type(retry) is bool, 'retry must be an explicit boolean')
        packet = deepcopy(assessment); VNextSchemaRegistry().validate(packet, SCHEMAS[0])
        captured = {}
        def validate(read): captured['proof'] = self.proof(read)
        with self.store.locked(validate) as token:
            proof = captured['proof']; old = self.intent(proof)
            if old is not None:
                require(old[0] == make_intent(packet), 'a different source-write approval already exists')
                state = self.status(proof=proof)
                if state['historical_completion'] or not retry or state['outcome'] != 'apply_required': return state
            with SourceFile(self.store,_source(proof)['path']) as source:
                current, before, after, view = self.assess(proof,source)
                require(current == packet, 'apply-back approval is stale')
                self.owner._synchronize(self.store,proof,view)
                for path,raw in view['assets']+((view['reference']['path'],canonical_json_bytes(view['packet'])),):
                    self.store.synchronize_existing(token,path,expected=raw)
                intent = make_intent(packet)
                self.store.publish(token,PREIMAGE,before)
                self.store.publish(token,INTENT,intent)
                prepared = old[3] if old else None
                attempted = False
                try:
                    if packet['changed']:
                        name = prepared['stage_name'] if prepared else '.whetstone-apply-'+intent['request_id']+'-'+secrets.token_hex(16)
                        identity = source.prepare(token,name,after,packet['source']['metadata'])
                        expected = dict(schema_version='vnext-apply-back-prepared-v1',request_id=intent['request_id'],
                            intent=_ref(INTENT,intent),stage_name=name,file_identity=identity)
                        require(prepared is None or prepared == expected, 'prepared source identity changed')
                        prepared = expected
                        self.store.publish(token,PREPARED,prepared)
                        def guard():
                            fresh = self.proof(self.store.read)
                            require(self.assess(fresh,source)[0] == packet, 'apply-back evidence changed before replacement')
                            require(self.intent(fresh)[0] == intent, 'apply-back intent changed before replacement')
                        source.replace(token,name=name,identity=identity,raw=after,before=(before,observation(packet)),guard=guard)
                        attempted = True
                    else:
                        require(self.assess(self.proof(self.store.read),source)[0] == packet, 'no-op approval changed')
                        source.synchronize(token,raw=after,identity=packet['source']['file_identity'],metadata=packet['source']['metadata'])
                    self.store.publish(token,RECEIPT,make_receipt(intent,prepared))
                except BaseException as exc:
                    # Even a receipt acknowledgement can be lost after a known
                    # source commit. Never infer noncommit or retry the write.
                    if attempted or isinstance(exc,StorageWriteError):
                        with _FORK_GATE,self.store._mutex: self.store._invalidate()
                        if isinstance(exc,StorageWriteError): raise
                        raise StorageWriteError(Publication('outcome_requires_reconciliation',packet['source']['path'],sha256_bytes(after)),exc) from exc
                    raise
            return self.status(proof=proof)

    def recover(self, *, exclusive_source_access=False):
        require(exclusive_source_access is True, 'source recovery requires exclusive access')
        captured = {}
        def validate(read): captured['proof'] = self.proof(read)
        with self.store.locked(validate) as token:
            proof = captured['proof']; state = self.status(proof=proof)
            if state['outcome'] != 'receipt_recovery_required': return state
            intent,before,after,prepared = self.intent(proof)
            packet = intent['assessment']
            # Recovery has no path to source.prepare/replace, regardless of
            # current scheduler state or approval's historical pointer.
            with SourceFile(self.store,packet['source']['path']) as source:
                identity = prepared['file_identity'] if prepared else packet['source']['file_identity']
                try:
                    require(source.parent_identity == packet['source']['parent_identity'], 'source parent identity changed')
                    source.synchronize(token,raw=after,identity=identity,metadata=packet['source']['metadata'])
                    for path,value in ((PREIMAGE,before),(INTENT,intent),(PREPARED,prepared)):
                        if value is not None:self.store.synchronize_existing(token,path,expected=value if isinstance(value,bytes) else canonical_json_bytes(value))
                    self.store.publish(token,RECEIPT,make_receipt(intent,prepared))
                except BaseException as exc:
                    with _FORK_GATE,self.store._mutex:self.store._invalidate()
                    if isinstance(exc,StorageWriteError):raise
                    raise StorageWriteError(Publication('outcome_requires_reconciliation',packet['source']['path'],sha256_bytes(after)),exc) from exc
            return self.status(proof=proof)


def expected_job(proof): return proof.seed_values['job']['job_id']


def observation(packet):
    return {k:deepcopy(packet['source'][k]) for k in ('parent_identity','file_identity','metadata','mtime_ns','ctime_ns')}


def make_intent(packet):
    return dict(schema_version='vnext-apply-back-intent-v1',
        request_id=content_identifier('apply','whetstone-apply-back-v1',[packet]),
        assessment=deepcopy(packet),approved=True,exclusive_source_access=True,
        preimage=dict(path=PREIMAGE,hash=packet['source']['expected_hash']))


def make_receipt(intent, prepared):
    packet = intent['assessment']
    require(not packet['changed'] or prepared is not None, 'source-write receipt lacks preparation')
    return dict(schema_version='vnext-apply-back-receipt-v1',request_id=intent['request_id'],intent=_ref(INTENT,intent),
        outcome='source_updated' if packet['changed'] else 'no_change',source_hash=packet['verified_draft']['hash'],
        file_identity=prepared['file_identity'] if prepared else packet['source']['file_identity'])

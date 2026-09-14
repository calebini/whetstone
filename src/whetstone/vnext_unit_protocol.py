"""Injected v2 proposal transport with preflight and retained attempt evidence.

This exercise is not a public proposal job or D8 registration path. The future
storage adapter supplies load_inputs by rereading admitted immutable artifacts
and current committed authority. No candidate or pointer is written here.
"""
from copy import deepcopy
import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory

from whetstone.vnext_contracts import VNextSchemaRegistry, canonical_json_bytes, decode_json, require, sha256_bytes
from whetstone.vnext_storage import publish, safe_path
from whetstone.vnext_unit_preflight import prepare_unit_preflight
from whetstone.vnext_unit_proposals import prepare_unit_patch


class ProposalShapeError(ValueError):
    """Malformed response JSON/schema only; eligible for D7's bounded retry."""


def decode_unit_response(raw,preflight,*,base,section_map,editor):
    registry=VNextSchemaRegistry()
    registry.load('vnext_proposal_response_v2')  # Local contract failures are not client shape failures.
    try:
        packet=decode_json(raw)
    except ValueError as exc:
        raise ProposalShapeError(str(exc)) from exc
    # A supplied contradictory identity is a binding failure even when its
    # string also violates the schema's lexical format. Do not repair scope or
    # authority through a supposedly structural retry.
    if isinstance(packet,dict) and isinstance(packet.get('patch'),dict):
        supplied=packet['patch']
        expected={key:preflight.plan[key] for key in ('job_id','transaction_id','base_draft_hash')}
        expected.update(mutation_plan_hash=sha256_bytes(canonical_json_bytes(preflight.plan)),editor=editor)
        for key,value in expected.items():
            if key in supplied:require(supplied[key]==value,'unit response contradicts frozen '+key)
        def check_path(value):
            if not isinstance(value,str):return
            path=Path(value)
            require(bool(path.parts) and not path.is_absolute() and '..' not in path.parts
                    and path.as_posix()==value and '\\' not in value and '\x00' not in value,
                    'unit payload path violates confinement')
        if isinstance(supplied.get('operations'),list):
            for operation in supplied['operations']:
                payload=operation.get('payload') if isinstance(operation,dict) else None
                if not isinstance(payload,dict):continue
                check_path(payload.get('path'))
                if isinstance(payload.get('hash'),str):
                    require(re.fullmatch(r'[0-9a-f]{64}',payload['hash']) is not None,'unit payload hash binding is malformed')
        if isinstance(packet.get('payloads'),list):
            for payload in packet['payloads']:
                if isinstance(payload,dict):check_path(payload.get('path'))
    try:registry.validate(packet,'vnext_proposal_response_v2')
    except ValueError as exc:raise ProposalShapeError(str(exc)) from exc
    paths=[item['path'] for item in packet['payloads']]
    require(len(paths)==len(set(paths)),'duplicate unit transport payload path')
    referenced={op['payload']['path'] for op in packet['patch']['operations'] if op['payload']['path'] is not None}
    require(set(paths)==referenced,'unit transport payloads differ from patch references')
    with TemporaryDirectory(prefix='whetstone-unit-proposal-') as temporary:
        root=Path(temporary)
        for item in packet['payloads']:
            path=safe_path(root,item['path']);path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(item['content'].encode('utf-8'))
        return prepare_unit_patch(canonical_json_bytes(packet['patch']),payload_root=root,plan=preflight.plan,
            base=base,section_map=section_map,inventory=preflight.inventory,editor=editor,
            responses=[b.response for b in preflight.bindings if b.response['authorized_effects']],rules=preflight.rules)


def exercise_unit_proposal(directory,*,load_inputs,client):
    """A fresh isolated request with at most one automatic shape-only retry.

    load_inputs must reread and validate storage-owned authority each time.
    It returns prepare_unit_preflight arguments. This boundary permits later
    current-base/registration integration without reseeding a promoted draft.
    """
    def load():
        values=load_inputs()
        return {**deepcopy({k:v for k,v in values.items() if k!='suite'}),'suite':values['suite']}
    arguments=load();preflight=prepare_unit_preflight(**arguments)
    transport=deepcopy(getattr(client,'transport_binding',None))
    if hasattr(client,'identity'):
        require(client.identity==arguments['review']['editor'],'native Editor differs from pinned preflight role')
    directory=Path(directory)
    directory.mkdir()  # Atomic fresh exercise claim; never replay a client call.
    publish(directory,'mutation_plan.json',preflight.plan)
    publish(directory,'base_inventory.json',preflight.inventory)
    publish(directory,'attempts/prompt-1.txt',preflight.prompt.encode('utf-8'))
    publish(directory,'preflight.json',{'input_hash':preflight.input_hash,
        'mutation_plan_hash':sha256_bytes(canonical_json_bytes(preflight.plan)),
        'base_inventory_hash':sha256_bytes(canonical_json_bytes(preflight.inventory)),
        'prompt_hash':sha256_bytes(preflight.prompt.encode()),'base_pointer':arguments['base_pointer_ref'],
        'findings':preflight.findings,'evidence':preflight.evidence,'derived_tasks':preflight.derived_tasks,
        'candidate_registered':False,'transport_binding':transport,'maximum_attempts':2})
    attempt=1
    try:
        errors=None
        for attempt in (1,2):
            prompt=preflight.prompt if errors is None else (
                'Correct only the response JSON/schema shape under the unchanged frozen authorization.\n'
                'Previous shape validation errors:\n'+errors+'\n\n'+preflight.prompt)
            publish(directory,f'attempts/prompt-{attempt}.txt',prompt.encode('utf-8'))
            before=load();rechecked=prepare_unit_preflight(**before)
            require(rechecked.input_hash==preflight.input_hash and rechecked.prompt==preflight.prompt,
                    'unit proposal inputs changed before the client call')
            require(getattr(client,'transport_binding',None)==transport,'unit proposal transport changed')
            publish(directory,f'attempts/invocation-{attempt}.json',{
                'attempt':attempt,'input_hash':preflight.input_hash,'transport_binding':transport,
                'original_prompt_hash':sha256_bytes(preflight.prompt.encode()),'attempt_prompt_hash':sha256_bytes(prompt.encode())})
            try:
                raw=client.propose(prompt)
            finally:
                telemetry=getattr(client,'last_telemetry',None)
                if telemetry is not None:
                    publish(directory,f'attempts/telemetry-{attempt}.json',json.dumps(telemetry,sort_keys=True).encode('utf-8'))
            require(isinstance(raw,bytes),'unit proposal client must return exact bytes')
            publish(directory,f'attempts/proposal-attempt-{attempt}.json',raw)
            current=load();rechecked=prepare_unit_preflight(**current)
            require(rechecked.input_hash==preflight.input_hash and rechecked.prompt==preflight.prompt,
                    'unit proposal inputs changed during the client call')
            require(getattr(client,'transport_binding',None)==transport,'unit proposal transport changed')
            try:
                proposal=decode_unit_response(raw,rechecked,base=current['base'],section_map=current['base_map'],editor=current['review']['editor'])
            except ProposalShapeError as exc:
                errors=str(exc)
                publish(directory,f'attempts/validation-error-{attempt}.txt',errors.encode('utf-8'))
                publish(directory,f'attempts/outcome-{attempt}.json',{'attempt':attempt,'classification':'shape_invalid',
                    'automatic_retry_permitted':attempt==1,'response_hash':sha256_bytes(raw)})
                if attempt==2:raise
                continue
            publish(directory,f'attempts/outcome-{attempt}.json',{'attempt':attempt,'classification':'valid_proposal',
                'automatic_retry_permitted':False,'response_hash':sha256_bytes(raw),'proposal_hash':proposal.digest})
            break
        relative='proposals/'+proposal.patch['proposal_id']
        for path,payload in sorted(proposal.payloads.items()):publish(directory,relative+'/'+path,payload)
        reference=publish(directory,relative+'/proposed_patch.json',proposal.patch)
        result={'schema_version':'vnext-proposal-result-v1','proposal':reference,
                'mutation_plan_hash':sha256_bytes(canonical_json_bytes(preflight.plan)),
                'base_pointer':arguments['base_pointer_ref'],'candidate_registered':False,'verified':False,'promoted':False}
        VNextSchemaRegistry().validate(result,'vnext_proposal_result_v1');publish(directory,'proposal_result.json',result)
        return preflight,proposal,reference
    except Exception as exc:
        publish(directory,f'attempts/failure-{attempt}.txt',(type(exc).__name__+': '+str(exc)).encode('utf-8'))
        raise

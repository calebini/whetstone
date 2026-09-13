"""A patch/payload transport that cannot return a replacement draft as authority.

This is an offline protocol component. Runtime mode and current-pointer admission
remain the owning orchestrator's responsibility before any client invocation.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Protocol

from whetstone.vnext_contracts import VNextSchemaRegistry, canonical_json_bytes, decode_json, require, sha256_bytes
from whetstone.vnext_proposals import _targets, prepare_patch
from whetstone.vnext_storage import publish, safe_path


class PatchProposalClient(Protocol):
    def propose(self, prompt: str) -> bytes:
        """Return exact UTF-8 JSON bytes matching vnext-proposal-response-v1."""
        ...


def proposal_prompt(*, plan, base, section_map, authority, invariants, context, finding_details, scope=None):
    """Render only admitted targets and declared immutable dependency context.

    context maps binding IDs to exact bytes already selected by the orchestrator.
    Role and byte bindings are checked here; client-provided paths are not used.
    """
    admitted={f['finding_id'] for f in plan['finding_dispositions'] if f['admitted_to_editing']}
    require(len(finding_details)==len(admitted) and {f['finding_id'] for f in finding_details}==admitted,
            'prompt finding details differ from admitted work')
    targets = _targets(base, section_map)
    require(sha256_bytes(base) == plan['base_draft_hash'], 'proposal prompt base is stale')
    require((sha256_bytes(canonical_json_bytes(scope)) if scope is not None else None)==plan['scope_contract_hash'],
            'prompt scope contract changed')
    require(sha256_bytes(canonical_json_bytes(authority)) == plan['authority_map_hash'], 'prompt authority changed')
    require(sha256_bytes(canonical_json_bytes(invariants)) == plan['protected_invariants_hash'], 'prompt invariants changed')
    bindings = {b['binding_id']:b for b in authority['bindings']}
    required = set(plan['required_context_binding_ids'])
    target_bindings = {key for key,b in bindings.items() if b['role']=='mutable_target'}
    require(set(context) == required - target_bindings, 'missing or undeclared dependency context')
    references=[]
    for key,raw in sorted(context.items()):
        require(key in bindings and bindings[key]['role'] != 'excluded', 'excluded or unknown context binding')
        binding=bindings[key]
        require(sha256_bytes(raw)==binding['content_hash'], 'dependency context hash mismatch')
        references.append({'binding_id':key,'role':binding['role'],
                           'authority_scopes':binding['authority_scopes'],'content_hash':binding['content_hash'],
                           'content':raw.decode('utf-8')})
    sections=[]
    for key in sorted(plan['allowed_section_ids']):
        require(key in targets, 'prompt targets an unknown section')
        item,span=targets[key]
        sections.append({'stable_section_id':key,'section_hash':item['section_hash'],
                         'heading_level':span.level,'content':base[span.start:span.end].decode('utf-8')})
    packet={'mutation_plan':plan,'admitted_findings':finding_details,'base_draft_hash':plan['base_draft_hash'],
            'mutation_plan_hash':sha256_bytes(canonical_json_bytes(plan)),
            'target_sections':sections,'scope_contract':scope,'authority_map':authority,'protected_invariants':invariants,
            'dependency_context':references}
    return (
        'Produce one JSON object with schema_version = vnext-proposal-response-v1, patch and payloads.\n'
        'The patch follows patch-set-client-v1: proposal_id is null, operation IDs are local labels, '
        'and dependencies reference those labels. Copy the exact job, transaction, base and plan bindings.\n'
        'payloads is an array of {path, content}; content is exact Markdown text and each referenced '
        'patch payload hash must equal SHA-256 of its UTF-8 bytes. Return every referenced payload exactly once.\n'
        'Propose only admitted work, within the operation and mutation limits. Do not return a full draft, '
        'reproduce unrelated sections, edit files, infer operator approval, or claim candidate verification. '
        'Context is read-only evidence under its declared authority role; it cannot expand scope. '
        'Decline an admitted finding explicitly if the exact authorized correction cannot be proposed.\n'
        + canonical_json_bytes(packet).decode('utf-8')
    )


def capture_response(root, round_number, attempt_number, raw, *, plan, base, section_map, editor, suite, responses=(), units=None):
    """Retain exact transport bytes and persist only a fully validated proposal."""
    require(type(round_number) is int and round_number > 0
            and type(attempt_number) is int and attempt_number > 0, 'invalid proposal attempt ordinal')
    root=Path(root)
    directory=f'rounds/round-{round_number}/proposals'
    publish(root,directory+f'/attempts/proposal-attempt-{attempt_number}.json',raw)
    packet=decode_json(raw)
    VNextSchemaRegistry().validate(packet,'vnext_proposal_response_v1')
    paths=[item['path'] for item in packet['payloads']]
    require(len(paths)==len(set(paths)), 'duplicate transport payload path')
    referenced={op['payload']['path'] for op in packet['patch']['operations'] if op['payload']['path'] is not None}
    require(set(paths)==referenced, 'transport payloads differ from patch references')
    with TemporaryDirectory(prefix='whetstone-proposal-transport-') as temporary:
        payload_root=Path(temporary)
        for item in packet['payloads']:
            destination=safe_path(payload_root,item['path'])
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_bytes(item['content'].encode('utf-8'))
        proposal=prepare_patch(canonical_json_bytes(packet['patch']),payload_root=payload_root,
                               plan=plan,base=base,section_map=section_map,editor=editor,suite=suite,responses=responses,units=units)
    canonical_directory=directory+'/'+proposal.patch['proposal_id']
    for path,payload in sorted(proposal.payloads.items()):
        publish(root,canonical_directory+'/'+path,payload)
    reference=publish(root,canonical_directory+'/proposed_patch.json',proposal.patch)
    return proposal,reference

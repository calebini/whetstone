"""Derive human version history solely from reproduced committed promotions."""
from whetstone.vnext_contracts import decode_json, require
from whetstone.vnext_version_operations import ASSEMBLER, pins


def projection(proof):
    if proof.seed_values['job']['assembler_version'] != ASSEMBLER:
        return None
    pins(proof.reader.suite)
    lines=['# Verified version history', '',
           'Derived from committed verified-pointer history; labels are not authority.', '']
    latest=None
    for pointer in proof.pointers[1:]:
        router=proof.transactions(pointer['source_candidate_creation_ordinal'])
        registry=router.registry()
        creation=registry._chain(pointer['source_candidate_creation_ordinal'])[-1]
        directory=creation['candidate_path'].rsplit('/',1)[0]
        material=registry._material(creation['round_number'],creation['proposal_id'],persisted_directory=directory)
        raw=material[-1][directory+'/version_operation.json']
        require(proof.store.read(directory+'/version_operation.json')==raw, 'committed version operation changed')
        operation=decode_json(raw)
        latest=operation
        if not operation['edits']: continue
        phase=operation['authority']['phase'];transition=operation['authority']['transition']
        label=f"round {creation['round_number']}" if transition=='round' else transition
        lines.append(f"- {phase} {label}: `{operation['before']}` -> `{operation['after']}`; "
                     f"before stamp `{operation['canonical_input_hash']}`, after stamp `{operation['candidate_hash']}`, "
                     f"verified candidate `{pointer['verified_draft_hash']}`; "
                     f"promotion {pointer['promotion_ordinal']}, operation `{operation['operation_id']}`.")
    return ('\n'.join(lines)+'\n').encode(),latest

"""Test-only registered consuming suite. Never modifies the shipping registry."""
from copy import deepcopy
from pathlib import Path
import shutil
from unittest.mock import patch

from whetstone.vnext_contracts import (CONTRACT_ROOT, ALGORITHM_VERSIONS, _refs,
    canonical_json_bytes, decode_json, sha256_bytes, validate_contract_suite)
from whetstone.vnext_proposal_admission import PROPOSAL_SCHEMAS
from whetstone.vnext_assembly import ASSEMBLER_VERSION, NORMALIZATION_VERSION
from whetstone.vnext_inventory import INVENTORY_VERSION
from whetstone import vnext_registry


def consuming_suite(test, directory, *, additional_schemas=(), additional_algorithms=(), algorithm_overrides=None):
    root=Path(directory)/'contracts'
    shutil.copytree(CONTRACT_ROOT,root)
    manifest=decode_json((root/'suites/vnext-contracts-1.json').read_bytes())
    manifest['suite_version']='test-proposal-consumer-v1'
    entries={entry['path']:entry for entry in manifest['schemas']}
    pending=['schemas/'+name+'.schema.json' for name in set(PROPOSAL_SCHEMAS)|set(additional_schemas)]
    seen=set()
    while pending:
        path=pending.pop()
        if path in seen:continue
        seen.add(path);raw=(root/path).read_bytes();schema=decode_json(raw)
        if path not in entries:
            name=Path(path).name.removesuffix('.schema.json')
            entries[path]=dict(name=name,version=name.replace('_','-'),path=path,sha256=sha256_bytes(raw))
        pending.extend('schemas/'+name for name in _refs(schema) if name)
    manifest['schemas']=sorted(entries.values(),key=lambda e:e['name'])
    # Pin the proposed implementation algorithms too, without publishing a suite.
    for name in ('vnext_candidate_assembly_v2','vnext_local_storage_kernel_v1',
                 'vnext_candidate_registration_v1','vnext_proposal_requests_v1','vnext_proposal_handoff_v1',
                 'vnext_proposal_admission_v1','vnext_proposal_closeout_v1','vnext_proposal_run_v1',
                 'vnext_seed_review_requests_v1','vnext_seed_review_closeout_v1','vnext_proposal_package_v1',
                 'vnext_proposal_cli_v1','vnext_operator_decisions_v1', *additional_algorithms):
        path='algorithms/'+name+'.md'
        manifest['algorithms'].append(dict(name=name,version=name.replace('_','-'),path=path,
            sha256=sha256_bytes((root/path).read_bytes())))
    manifest['algorithms'].sort(key=lambda e:e['name'])
    manifest['suite_digest']=sha256_bytes(canonical_json_bytes({k:v for k,v in manifest.items() if k!='suite_digest'}))
    path=root/'suites'/f"{manifest['suite_version']}.json"
    path.write_bytes(canonical_json_bytes(manifest))
    algorithms={**deepcopy(ALGORITHM_VERSIONS),'assembler_version':ASSEMBLER_VERSION,
                'normalization_version':NORMALIZATION_VERSION,'inventory_version':INVENTORY_VERSION,
                **(algorithm_overrides or {})}
    for mapping,value in [(vnext_registry.SUPPORTED_SUITES,manifest['suite_digest']),
                          (vnext_registry.SUITE_ALGORITHM_VERSIONS,algorithms)]:
        patcher=patch.dict(mapping,{manifest['suite_version']:value});patcher.start();test.addCleanup(patcher.stop)
    return validate_contract_suite(path),path,algorithms

"""Offline suite registry; no vNext runtime mode is enabled by this registry."""
SUPPORTED_SUITES = {
    "vnext-verified-consumer-3": "46a7d73362aa8c1463e20978f2dc9803a588dae6e043c461321492d33c42313c",
    "vnext-verified-consumer-2": "bc6657ad4a098f2f6a9a2652b0d4be412e5ca452be4723c8d3c8ba82443c9820",
    "vnext-contracts-1": "69dbe84ce740ccae19126a39514f9bca5bcc036c3152d7a0a623e29bd9214548",
    "vnext-verified-consumer-1": "7d636c3cb2da3b687dccd31b17050d8786fc0db256c8e35581739264d002fd58",
}

# Implementation-owned dispatch, paired with the registered manifest digest.
# Adding files or changing a descriptor cannot select a different algorithm.
SUITE_ALGORITHM_VERSIONS = {
    "vnext-verified-consumer-1": {
        'normalization_version': 'whetstone-markdown-normalization-v1',
        'parser_contract_version': 'markdown-atx-v1',
        'assembler_version': 'patch-assembler-v3',
        'inventory_version': 'preservation-inventory-v2',
        'semantic_verifier_policy_version': 'semantic-policy-v2',
    },
    "vnext-contracts-1": {
        'normalization_version': 'whetstone-canonical-json-v1',
        'parser_contract_version': 'markdown-atx-v1',
        'assembler_version': 'patch-assembler-v1',
        'inventory_version': 'preservation-inventory-v1',
        'semantic_verifier_policy_version': 'semantic-policy-v1',
    },
}

# Phase 1 policy changes; candidate/semantic algorithm versions are unchanged.
SUITE_ALGORITHM_VERSIONS["vnext-verified-consumer-2"] = dict(SUITE_ALGORITHM_VERSIONS["vnext-verified-consumer-1"])
SUITE_ALGORITHM_VERSIONS["vnext-verified-consumer-3"] = dict(SUITE_ALGORITHM_VERSIONS["vnext-verified-consumer-2"])

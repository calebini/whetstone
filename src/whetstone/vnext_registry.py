"""Offline suite registry; no vNext runtime mode is enabled by this registry."""
SUPPORTED_SUITES = {
    "vnext-contracts-1": "69dbe84ce740ccae19126a39514f9bca5bcc036c3152d7a0a623e29bd9214548",
}

# Implementation-owned dispatch, paired with the registered manifest digest.
# Adding files or changing a descriptor cannot select a different algorithm.
SUITE_ALGORITHM_VERSIONS = {
    "vnext-contracts-1": {
        'normalization_version': 'whetstone-canonical-json-v1',
        'parser_contract_version': 'markdown-atx-v1',
        'assembler_version': 'patch-assembler-v1',
        'inventory_version': 'preservation-inventory-v1',
        'semantic_verifier_policy_version': 'semantic-policy-v1',
    },
}

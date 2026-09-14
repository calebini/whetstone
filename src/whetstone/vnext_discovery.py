"""Job-bound discovery rules from the protected-invariants artifact."""
from copy import deepcopy

from whetstone.vnext_contracts import VNextSchemaRegistry, require
from whetstone.vnext_inventory import _rules


def discovery_rules(invariants,expected=None):
    version=invariants.get('schema_version')
    schemas={'protected-invariants-v1':'protected_invariants_v1','protected-invariants-v2':'protected_invariants_v2'}
    require(version in schemas,'unsupported invariant/discovery version')
    VNextSchemaRegistry().validate(invariants,schemas[version])
    rules=deepcopy(invariants.get('discovery_rules',[]))
    _rules(rules)
    if expected is not None:
        require(list(expected)==rules,'discovery rules differ from the job-bound invariant artifact')
    return rules

"""Fixed, non-extensible evaluator for the pinned offline conformance vectors."""
from whetstone.vnext_contracts import ContractSuiteError, canonical_json_bytes, require
from whetstone.contracts import SchemaValidationError
from whetstone import vnext_identity as identity


def check_fixture(packet, registry):
    require(isinstance(packet,dict) and set(packet)=={'name','operation','input','expected_result','expected'},'invalid conformance vector envelope')
    require(packet['expected_result'] in {'pass','reject'},'unknown fixture result')
    operation=packet['operation'];data=packet['input']
    require(operation in {'schema','canonical','candidate_identity','decision','topology'},'unsupported conformance operation')
    try:
        if operation=='schema':
            require(set(data)=={'schema','value'},'invalid schema vector')
            registry.validate(data['value'],data['schema']);actual=None
        elif operation=='canonical':actual=canonical_json_bytes(data).hex()
        elif operation=='candidate_identity':actual=identity.candidate_id(*data)
        elif operation=='decision':
            from whetstone.vnext_validation import validate_decision
            require(set(data)=={'decision','preservation','semantic','job'},'invalid decision vector')
            registry.validate(data['decision'],'candidate_verification_v1')
            registry.validate(data['preservation'],'preservation_report_v1')
            if data['semantic'] is not None:registry.validate(data['semantic'],'semantic_verification_v1')
            validate_decision(**data);actual=None
        else:
            require(set(data)=={'items','key','dependencies'},'invalid topology vector')
            actual=[item[data['key']] for item in identity.topological(data['items'],data['key'],data['dependencies'])]
    except (ContractSuiteError,SchemaValidationError,UnicodeError,ValueError):
        require(packet['expected_result']=='reject','positive conformance vector was rejected',packet['name'])
    else:
        require(packet['expected_result']=='pass','negative conformance vector was accepted',packet['name'])
        require(actual==packet['expected'],'conformance output mismatch',packet['name'])

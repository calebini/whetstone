"""Separate read-only native Semantic Verifier transport, with no retries.

The orchestration consumer owns admitted-context binding, durable invocation
claims and result validation. This adapter alone does not grant a verdict.
"""
from whetstone.vnext_native_editor import NativePatchProposalClient


class NativeSemanticVerifierClient(NativePatchProposalClient):
    role = 'verifier'
    provider_schema = 'semantic_verification_client_v2.codex.schema.json'
    canonical_schema = 'semantic_verification_client_v2'
    schema_title = 'Whetstone Independent Semantic Verification'

    def verify(self, prompt):
        return super().propose(prompt)

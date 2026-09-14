"""Raw read-only Reviewer transport for the proposal consumer."""
from whetstone.vnext_native_editor import NativePatchProposalClient


class NativeProposalReviewerClient(NativePatchProposalClient):
    role='reviewer'
    provider_schema='vnext_review_response_v1.codex.schema.json'
    canonical_schema='vnext_review_response_v1'
    schema_title='Whetstone Proposal Review And Classification Advice'

    def review(self,prompt):return super().propose(prompt)

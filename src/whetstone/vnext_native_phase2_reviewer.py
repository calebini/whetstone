"""Read-only Phase 2 rubric transport; journals own retries and validation."""
from whetstone.vnext_contracts import CONTRACT_ROOT, sha256_bytes
from whetstone.vnext_native_editor import structural_output_schema
from whetstone.vnext_native_reviewer import NativeProposalReviewerClient
import json


def phase2_output_schema():
    result = structural_output_schema('vnext_phase2_rubric_response_v2', 'Whetstone Verified Phase 2 Rubric Review')
    # The canonical Phase 2 review uses allOf to specialize oscillation keys.
    # Reuse its explicit provider projection rather than dropping that shape.
    review = json.loads((CONTRACT_ROOT/'schemas/phase2_reviewer_feedback_input.codex.schema.json').read_bytes())
    result['properties']['review'] = {k:v for k,v in review.items() if k not in {'$schema', '$id'}}
    return result


class NativePhase2ReviewerClient(NativeProposalReviewerClient):
    provider_schema = 'vnext_phase2_rubric_response_v2.codex.schema.json'
    canonical_schema = 'vnext_phase2_rubric_response_v2'
    schema_title = 'Whetstone Verified Phase 2 Rubric Review'

    def output_schema(self): return phase2_output_schema()

    @property
    def transport_binding(self):
        # Phase 2 binds the canonical response contract, not its provider projection.
        binding = super().transport_binding
        binding['output_schema_hash'] = sha256_bytes(
            (CONTRACT_ROOT/'schemas'/f'{self.canonical_schema}.schema.json').read_bytes())
        return binding

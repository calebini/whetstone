"""Config-selected V bootstrap; no proposal-only owner or mode conversion."""
from whetstone.vnext_contracts import require
from whetstone.vnext_proposal_admission import ProposalAdmission
from whetstone.vnext_proposal_package import prepare_proposal_package


class VerifiedSeedAdmission(ProposalAdmission):
    def _base(self, read):
        reader, values = self._seed_inputs(read, expected_mode='verified_promotion')
        require(read('rounds/current_verified.json') == reader.raw(values['base_pointer_ref']),
                'V initialization requires the exact committed seed pointer')
        return reader, values


def prepare_verified_package(root, *, manifest_path, suite_path=None):
    return prepare_proposal_package(root, manifest_path=manifest_path,
                                    suite_path=suite_path, _admission_type=VerifiedSeedAdmission)

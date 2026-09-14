"""Explicit full semantic proposal workflow; public use requires qualification."""
from whetstone.vnext_contracts import CONTRACT_ROOT, confined_file, require, sha256_bytes
from whetstone.vnext_proposal_run import ProposalRun
from whetstone.vnext_semantic_decisions import SemanticDecisionJournal
from whetstone.vnext_semantic_protocol import POLICY_VERSION
from whetstone.vnext_semantic_admission import SEMANTIC_ALGORITHMS, SEMANTIC_SCHEMAS
from whetstone.vnext_semantic_requests import REQUEST_SCHEMAS


ALGORITHM = 'algorithms/vnext_semantic_workflow_v1.md'


def validate_semantic_workflow(job, suite):
    require(job['semantic_verifier_policy_version'] == POLICY_VERSION, 'unsupported semantic workflow policy')
    algorithms = {entry['path']: entry for entry in suite.manifest['algorithms']}
    required = {ALGORITHM, 'algorithms/vnext_semantic_run_v1.md', 'algorithms/vnext_semantic_decisions_v1.md',
                'algorithms/vnext_semantic_requests_v1.md'} | {'algorithms/' + name + '.md' for name in SEMANTIC_ALGORITHMS}
    require(required <= algorithms.keys(), 'semantic workflow algorithms are outside supported suite')
    schemas = {entry['path']: entry for entry in suite.manifest['schemas']}
    required_schemas = {'schemas/' + name + '.schema.json' for name in SEMANTIC_SCHEMAS | REQUEST_SCHEMAS}
    require(required_schemas <= schemas.keys(), 'semantic workflow schemas are outside supported suite')
    for path in required | required_schemas:
        entry = (algorithms if path.startswith('algorithms/') else schemas)[path]
        require(sha256_bytes(confined_file(CONTRACT_ROOT, path).read_bytes()) == entry['sha256'],
                'installed semantic workflow contract differs from pinned suite')


class _WorkflowDecisions(SemanticDecisionJournal):
    def terminal(self, **options):
        if not options:
            registered = self.registry.inspect()
            if registered.events and not registered.orphans:
                view = self._state(registered.events[-1])[0]
                if view.decision is not None and not view.prepared and not view.decision['decision_final']:
                    options = dict(terminal_state='TARGET_NOT_REACHED', reason='vnext_semantic_not_started')
        return super().terminal(**options)


class SemanticProposalRun(ProposalRun):
    """Use semantic-aware readers for all candidates, including earlier rounds."""
    def __init__(self, store, *, suite_path):
        super().__init__(store, suite_path=suite_path)
        reader, values = self._base(store.read)
        validate_semantic_workflow(values['job'], reader.suite)

    def decision_journal(self, registry):
        return _WorkflowDecisions(registry, admission=self)

    def candidate_status(self, round_number, journal, creation):
        # The common status reader has already validated all chains and the
        # selected completed Editor request. Avoid deriving its status twice.
        from whetstone.vnext_semantic_run import _inspect
        return _inspect(self, round_number, journal, journal._state(creation)[0])

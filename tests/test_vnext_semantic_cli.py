from copy import deepcopy
from contextlib import contextmanager
import json
import sys
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from whetstone import vnext_proposal_cli as routing
from whetstone.vnext_contracts import CONTRACT_ROOT, canonical_json_bytes, sha256_bytes
from whetstone.vnext_local_storage import LocalAuthorityStore
from whetstone.vnext_semantic_context import SemanticContext
from whetstone.vnext_semantic_admission import SEMANTIC_ALGORITHMS, SEMANTIC_SCHEMAS
from whetstone.vnext_semantic_protocol import POLICY_VERSION
from whetstone.vnext_semantic_requests import REQUEST_SCHEMAS
from vnext_consuming_suite_fixture import consuming_suite
import test_vnext_proposal_cli as cli_tests
import test_vnext_semantic_protocol as protocol_tests
import test_vnext_semantic_run as round_tests


def workflow_suite(test, directory):
    return consuming_suite(test, directory, additional_schemas=SEMANTIC_SCHEMAS | REQUEST_SCHEMAS,
        additional_algorithms=(*SEMANTIC_ALGORITHMS, 'vnext_semantic_requests_v1', 'vnext_semantic_decisions_v1',
                               'vnext_semantic_run_v1', 'vnext_semantic_workflow_v1'),
        algorithm_overrides={'semantic_verifier_policy_version': POLICY_VERSION})


class Verifier:
    def __init__(self):
        self.calls = 0
        self.callback = None
        self.prompts = []
        self.last_telemetry = None

    def configure(self, *, review, command, cwd, timeout_seconds):
        self.identity = deepcopy(review['verifier'])
        self.transport = dict(verifier=self.identity, command=command or 'fictional-semantic-verifier', cwd=str(cwd),
            timeout_seconds=timeout_seconds,
            output_schema_hash=sha256_bytes((CONTRACT_ROOT / 'schemas/semantic_verification_client_v2.codex.schema.json').read_bytes()))
        return self

    @property
    def transport_binding(self):
        return deepcopy(self.transport)

    def verify(self, prompt):
        self.calls += 1
        self.prompts.append(prompt)
        packet = next(json.loads(line) for line in prompt.splitlines() if line.startswith('{') and '"context":' in line)
        helper = protocol_tests.SemanticProtocolTests()
        helper.context = SemanticContext(canonical_json_bytes(packet['context']))
        response = helper.response()
        return self.callback(response) if self.callback else canonical_json_bytes(response)


def fixture(test, factory=workflow_suite):
    subject = cli_tests.ProposalCLITests()
    test.addCleanup(subject.doCleanups)
    with patch.object(cli_tests.package_tests.fixtures, 'consuming_suite', factory):
        subject.setUp()
    qualifier = patch.dict(routing.QUALIFIED_SEMANTIC_SUITES, {subject.suite.version:subject.suite.digest})
    qualifier.start();test.addCleanup(qualifier.stop)
    return subject


@contextmanager
def native_clients(subject):
    from whetstone.vnext_native_editor import NativePatchProposalClient
    from whetstone.vnext_native_reviewer import NativeProposalReviewerClient
    from whetstone.vnext_native_verifier import NativeSemanticVerifierClient
    f = subject.f
    for role in ('reviewer', 'editor', 'verifier'):
        f.original.review[role] = dict(name='codex', version='scripted-1', model='semantic-cli-' + role)
    f.original.review_ref = f.save(f.original.review_ref['path'], f.original.review)
    f.job['review_configuration_hash'] = f.original.review_ref['hash'];f.rebind()
    subject.fixture.package.update(job_descriptor=f.job_ref, review_configuration=f.original.review_ref)
    subject.fixture.package['mutation_constraints'] = f.save(subject.fixture.constraint_ref['path'],
        dict(schema_version='vnext-mutation-constraints-v1', constraints=f.constraints))
    subject.fixture.save_package()
    template = json.dumps(dict(feedback=f.feedback, hint=f.hint))
    commands = {}
    for role in ('reviewer', 'editor', 'verifier'):
        command = subject.root.parent / ('semantic-cli-native-' + role)
        counter = command.with_suffix('.count')
        command.write_text(f'''#!{sys.executable}
import json, sys
from pathlib import Path
sys.path[:0] = [{str(Path('src').resolve())!r}, {str(Path('tests').resolve())!r}]
prompt = sys.stdin.read()
packet = json.loads(prompt.splitlines()[-1])
counter = Path({str(counter)!r})
counter.write_text(str(int(counter.read_text()) + 1 if counter.exists() else 1))
if {role!r} == 'reviewer':
    template = json.loads({template!r})
    feedback = template['feedback']
    feedback.update(round_number=packet['round_number'], profile=packet['profile'], reviewer=packet['review']['reviewer'])
    response = dict(schema_version='vnext-review-response-v1', feedback=feedback, classifications=[template['hint']])
elif {role!r} == 'editor':
    from test_vnext_unit_preflight import Client
    response = json.loads(Client().propose(prompt))
    response['patch']['editor'] = packet['editor']
else:
    from whetstone.vnext_semantic_context import SemanticContext
    from whetstone.vnext_contracts import canonical_json_bytes
    from test_vnext_semantic_protocol import SemanticProtocolTests
    helper = SemanticProtocolTests()
    helper.context = SemanticContext(canonical_json_bytes(packet['context']))
    response = helper.response()
Path(sys.argv[sys.argv.index('--output-last-message') + 1]).write_bytes(json.dumps(response).encode())
print('tokens used\\n29')
''')
        command.chmod(0o700)
        commands[role] = {'command':str(command)}
    subject.config.write_text(json.dumps(dict(clients=commands,
        timeouts=dict(reviewer_seconds=10, editor_seconds=10, verifier_seconds=10))))
    with patch.object(routing, 'NativeProposalReviewerClient', NativeProposalReviewerClient), \
            patch.object(routing, 'NativePatchProposalClient', NativePatchProposalClient), \
            patch.object(routing, 'NativeSemanticVerifierClient', NativeSemanticVerifierClient):
        yield


def assert_native_reentry(test, command, expected, actual):
    """Retain a failed readback before the fixture's registered cleanup runs.

    The archive is inert forensic evidence, not a relocatable D8 run root.
    Successful reentry creates no diagnostic directory.
    """
    if actual == expected:
        return
    output = Path(tempfile.mkdtemp(prefix='whetstone-semantic-cli-failure-'))
    packets = dict(test=test.id(), command=command, expected=expected, actual=actual,
                   fixture_root=str(test.subject.root))
    (output / 'packets.json').write_text(json.dumps(packets, indent=2) + '\n')
    try:
        with tarfile.open(output / 'fixture.tar.gz', 'w:gz') as archive:
            archive.add(test.subject.root.parent, arcname='forensic-fixture')
    except OSError as exc:
        # Preserve the original assertion and packets even if archival fails.
        (output / 'archive-error.txt').write_text(str(exc) + '\n')
    test.maxDiff = None
    test.assertEqual(actual, expected, f'{command} readback evidence retained at {output}')


@unittest.skipUnless(sys.platform == 'darwin', 'Proposed local storage targets macOS/APFS')
class SemanticCLITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cli_tests.ProposalCLITests.setUpClass()

    def setUp(self):
        self.subject = fixture(self)
        self.verifier = Verifier()
        self.factory = self.subject.patch('whetstone.vnext_proposal_cli.NativeSemanticVerifierClient', side_effect=self.verifier.configure)

    def invoke(self, *args, **kwargs):
        return self.subject.invoke(*args, **kwargs)

    def reset_factories(self):
        for factory in (self.factory, self.subject.review_factory, self.subject.editor_factory): factory.reset_mock()

    def no_factories(self):
        for factory in (self.factory, self.subject.review_factory, self.subject.editor_factory): factory.assert_not_called()

    def test_live_command_reaches_independent_verification_and_reentry_is_read_only(self):
        code, packet = self.invoke('live-phase1', package=True)
        self.assertEqual(code, 2, packet)
        self.assertEqual(packet['vnext']['reason_code'], 'vnext_proposal_only_complete', packet)
        self.assertEqual(packet['terminal_report']['latest_candidate']['disposition'], 'CANDIDATE_VERIFIED')
        self.assertIn('semantic_verification', packet['vnext']['available_gates'])
        self.assertNotIn('promotion', packet['vnext']['available_gates'])
        self.assertEqual((self.subject.reviewer.calls, self.subject.editor.calls, self.verifier.calls), (1, 1, 1))
        self.assertEqual(packet['proposal_status']['request_attempts'], 1)
        root = self.subject.root
        self.assertEqual((root/'rounds/current_verified.json').read_bytes(), (root/'rounds/verified_history/current-verified-0.json').read_bytes())
        before = self.subject.files();self.reset_factories()
        self.assertEqual(self.invoke('status')[1], packet)
        self.assertEqual(self.invoke('live-phase1')[1], packet)
        self.assertEqual(self.invoke('resume', '--continue')[0], 2)
        self.assertEqual(self.subject.files(), before);self.no_factories()

    def test_separate_qualification_gate_does_not_infer_semantics_from_installed_contracts(self):
        with patch.dict(routing.QUALIFIED_SEMANTIC_SUITES, {}, clear=True):
            code, packet = self.invoke('live-phase1', package=True)
        self.assertEqual(packet['vnext']['reason_code'], 'vnext_gate_unavailable', packet)
        self.assertNotIn('semantic_verification', packet['vnext']['available_gates'])
        self.assertEqual(packet['terminal_report']['latest_candidate']['disposition'], 'CANDIDATE_UNVERIFIED')
        self.factory.assert_not_called();self.assertEqual(self.verifier.calls, 0)
        code, packet = self.invoke('live-phase1')
        self.assertEqual(packet['vnext']['reason_code'], 'vnext_proposal_only_complete', packet)
        self.assertEqual((self.subject.reviewer.calls, self.subject.editor.calls, self.verifier.calls), (1, 1, 1))

    def test_semantic_rejection_is_final_without_editor_repair_or_continuation(self):
        def reject(response):
            response.update(verdict='reject', unrelated_semantic_change='detected')
            return canonical_json_bytes(response)
        self.verifier.callback = reject
        _, packet = self.invoke('live-phase1', package=True)
        self.assertEqual(packet['terminal_state'], 'TARGET_NOT_REACHED', packet)
        self.assertEqual(packet['vnext']['reason_code'], 'vnext_semantic_rejected')
        self.assertEqual(packet['terminal_report']['latest_candidate']['disposition'], 'CANDIDATE_REJECTED')
        before = self.subject.files();self.reset_factories()
        self.assertEqual(self.invoke('live-phase1')[1], packet)
        self.assertEqual(self.invoke('resume', '--continue')[0], 2)
        self.assertEqual(before, self.subject.files());self.no_factories()

    def test_timeout_uses_explicit_verifier_continuation_and_preserves_exhausted_cause(self):
        def timeout(response): raise TimeoutError('fictional CLI semantic deadline')
        self.verifier.callback = timeout
        _, packet = self.invoke('live-phase1', '--verifier-timeout-seconds', '2', package=True)
        self.assertEqual(packet['terminal_state'], 'HALTED_CLIENT_TIMEOUT', packet)
        self.assertEqual(packet['proposal_status']['resume']['next_gate'], 'semantic_verification')
        before = self.subject.files();self.reset_factories()
        self.assertEqual(self.invoke('resume', '--dry-run')[0], 0)
        self.assertEqual(self.invoke('live-phase1')[0], 2)
        self.assertEqual(self.subject.files(), before);self.no_factories()
        _, packet = self.invoke('resume', '--continue', '--verifier-timeout-seconds', '3')
        self.assertEqual(packet['terminal_state'], 'HALTED_CLIENT_TIMEOUT', packet)
        self.assertIn('fictional CLI semantic deadline', packet['vnext']['reason'])
        self.assertFalse(packet['proposal_status']['resume']['permitted'])
        self.assertEqual((self.subject.reviewer.calls, self.subject.editor.calls, self.verifier.calls), (1, 1, 2))
        self.reset_factories();before = self.subject.files()
        self.assertEqual(self.invoke('live-phase1')[1], packet)
        self.assertEqual(self.invoke('resume', '--continue')[0], 2)
        self.no_factories();self.assertEqual(before, self.subject.files())

    def test_prepared_semantic_decision_and_terminal_recovery_construct_no_adapters(self):
        original = LocalAuthorityStore.publish
        def stop(store, token, path, value):
            result = original(store, token, path, value)
            if path.endswith('/candidate_verification-attempt-2.json'):
                raise OSError('fictional semantic decision interruption')
            return result
        with patch.object(LocalAuthorityStore, 'publish', stop):
            _, packet = self.invoke('live-phase1', package=True)
        self.assertEqual(packet['terminal_state'], 'HALTED_ARTIFACT_INVALID', packet)
        self.reset_factories();before = self.subject.files()
        _, status = self.invoke('status')
        self.assertEqual(status['proposal_status']['processing_gate'], 'verification_commit', status)
        self.assertEqual(status['terminal_report']['latest_candidate']['disposition'], 'CANDIDATE_UNVERIFIED')
        self.assertEqual(self.subject.files(), before)
        _, complete = self.invoke('resume', '--continue')
        self.assertEqual(complete['vnext']['reason_code'], 'vnext_proposal_only_complete', complete)
        self.no_factories()
        report = complete['terminal_report']
        path = self.subject.root/'rounds/terminal_reports'/('terminal-'+sha256_bytes(canonical_json_bytes(report))+'.json')
        path.unlink();before = self.subject.files()
        _, status = self.invoke('resume', '--dry-run')
        self.assertEqual(status['proposal_status']['processing_gate'], 'materialization')
        self.assertEqual(self.subject.files(), before)
        self.assertEqual(self.invoke('resume', '--continue')[1], complete)
        self.no_factories();self.assertEqual(self.verifier.calls, 1)

    def test_deterministic_failure_stops_before_verifier_invocation(self):
        def fail(packet):
            content = 'Queue sometimes waits.\n'
            packet['payloads'][0]['content'] = content
            packet['patch']['operations'][0]['payload']['hash'] = sha256_bytes(content.encode())
            return canonical_json_bytes(packet)
        self.subject.editor.callback = fail
        _, packet = self.invoke('live-phase1', package=True)
        self.assertEqual(packet['vnext']['reason_code'], 'vnext_preservation_failed', packet)
        self.assertEqual(packet['terminal_report']['latest_candidate']['disposition'], 'CANDIDATE_REJECTED')
        self.assertEqual(self.verifier.calls, 0)
        self.reset_factories();before = self.subject.files()
        self.assertEqual(self.invoke('live-phase1')[1], packet)
        self.no_factories();self.assertEqual(self.subject.files(), before)

    def test_clean_seed_never_invokes_editor_or_verifier(self):
        self.subject.reviewer.callback = self.subject.clean
        code, packet = self.invoke('live-phase1', package=True)
        self.assertEqual((code, packet['terminal_state']), (0, 'PHASE_1_STABLE'), packet)
        self.assertEqual((self.subject.reviewer.calls, self.subject.editor.calls, self.verifier.calls), (1, 0, 0))
        before = self.subject.files();self.reset_factories()
        self.assertEqual(self.invoke('live-phase1')[1], packet)
        self.no_factories();self.assertEqual(self.subject.files(), before)

    def test_three_native_roles_complete_the_normal_command_and_reentry_without_more_calls(self):
        with native_clients(self.subject):
            code, packet = self.invoke('live-phase1', package=True)
            self.assertEqual(code, 2, packet)
            self.assertEqual(packet['vnext']['reason_code'], 'vnext_proposal_only_complete', packet)
            self.assertEqual(packet['terminal_report']['latest_candidate']['disposition'], 'CANDIDATE_VERIFIED')
            before = self.subject.files()
            assert_native_reentry(self, 'status', (0, packet), self.invoke('status'))
            assert_native_reentry(self, 'live-phase1', (2, packet), self.invoke('live-phase1'))
            self.assertEqual(self.subject.files(), before)
        for role in ('reviewer', 'editor', 'verifier'):
            self.assertEqual((self.subject.root.parent / ('semantic-cli-native-' + role + '.count')).read_text(), '1')
        self.assertEqual((self.subject.root/'rounds/current_verified.json').read_bytes(),
                         (self.subject.root/'rounds/verified_history/current-verified-0.json').read_bytes())


@unittest.skipUnless(sys.platform == 'darwin', 'Proposed local storage targets macOS/APFS')
class SemanticCLIAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cli_tests.ProposalCLITests.setUpClass()

    def test_round_support_without_workflow_pin_refuses_before_root_or_adapter_creation(self):
        subject = fixture(self, round_tests.run_suite)
        with patch.object(routing, 'NativeSemanticVerifierClient') as factory:
            code, packet = subject.invoke('vnext-admit', package=True)
        self.assertEqual(code, 2)
        self.assertIn('semantic workflow algorithms', packet['vnext']['reason'])
        self.assertFalse(subject.root.exists());factory.assert_not_called()
        subject.review_factory.assert_not_called();subject.editor_factory.assert_not_called()

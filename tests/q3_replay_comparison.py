"""Compare only historical seed reuse, in ABBA order on one live D8 fixture.

Run under m5_bounded_runner.py with PYTHONPATH=src:tests. Both arms use the
current implementation; control substitutes the original fresh seed-validation
callback. Fixture construction and final acceptance use the changed path.
"""
import argparse
from contextlib import ExitStack, nullcontext
import json
import os
from pathlib import Path
import platform
import sys
import time
import unittest
from unittest.mock import patch

from q3_replay_profile import digest, files, result_bytes
from test_vnext_m5_integration import LongerHistoryTests
import test_vnext_verified_semantics as semantics
from vnext_q2_fixtures import suite
from whetstone.vnext_contracts import CONTRACT_ROOT, validate_contract_suite
from whetstone.vnext_verified_history import _Proof, VerifiedHistoryAdmission
from whetstone.vnext_verified_run import _RunHistory, _RoundSelectors, VerifiedRun


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if any((out / name).exists() for name in ('comparison.json', 'samples.jsonl', 'stages.jsonl')):
        parser.error('comparison output exists; preserve it and select a fresh directory')
    pinned = validate_contract_suite(CONTRACT_ROOT / 'suites/vnext-verified-consumer-1.json')
    metadata = dict(suite=pinned.version, suite_digest=pinned.digest, python=sys.version,
                    platform=platform.platform(), outcome='running',
                    control='Inherited _recheck_review_seed calls _seed_inputs fresh each time.',
                    order=['control_1', 'reuse_1', 'reuse_2', 'control_2'],
                    scope='one/four promotions on the same current-suite fixture; scripted clients; no activation')
    def save():
        (out / 'comparison.json').write_text(json.dumps(metadata, indent=2) + '\n')
    save()
    case = LongerHistoryTests('test_four_versioned_promotions_replay_exact_history')

    def sample(f, name):
        case.assertEqual(json.loads(f.store.read_descriptor())['contract_suite_version'], pinned.version)
        case.assertEqual(Path(f.run.suite_path).resolve(), CONTRACT_ROOT / 'suites/vnext-verified-consumer-1.json')
        before = files(f.root)
        expected = {}; control_counts = {}
        for label in metadata['order']:
            context = patch.object(_RunHistory, '_recheck_review_seed', VerifiedHistoryAdmission._recheck_review_seed) \
                if label.startswith('control') else nullcontext()
            with context:
                for operation, call in [('history', lambda: f.run._history().inspect()),
                                        ('phase1_state', f.run.phase1_status)]:
                    counts = {}
                    def count(owner, method, key):
                        original = getattr(owner, method)
                        counts[key] = 0
                        def counted(*args, **kwargs):
                            counts[key] += 1
                            return original(*args, **kwargs)
                        return patch.object(owner, method, counted)
                    with case.stage(name + '-' + label + '-' + operation), ExitStack() as stack:
                        for owner, method, key in [(_RunHistory, '_seed_inputs', 'seed_validations'),
                            (_Proof, 'guard', 'proof_guards'), (_RoundSelectors, 'guard', 'round_guards'),
                            (VerifiedRun, '_guard', 'run_guards')]:
                            stack.enter_context(count(owner, method, key))
                        wall, cpu = time.perf_counter(), time.process_time()
                        value = call()
                        seconds, cpu_seconds = time.perf_counter() - wall, time.process_time() - cpu
                    raw = result_bytes(value)
                    if label == 'control_1':
                        expected[operation] = raw
                        control_counts[operation] = counts.copy()
                    case.assertEqual(raw, expected[operation])
                    case.assertEqual(files(f.root), before)
                    if label.startswith('reuse'):
                        for key in ('proof_guards', 'round_guards', 'run_guards'):
                            case.assertGreaterEqual(counts[key], control_counts[operation][key], key)
                    row = dict(sample=name, variant=label, operation=operation, wall_seconds=seconds,
                               process_seconds=cpu_seconds, counts=counts,
                               result_sha256=digest(raw), artifacts_unchanged=True)
                    with (out / 'samples.jsonl').open('a') as stream:
                        stream.write(json.dumps(row) + '\n')
                    print(json.dumps(row), flush=True)

    case.sample = sample
    with patch.object(semantics, 'consuming_suite', suite), \
         patch.dict(os.environ, WHETSTONE_M5_EVIDENCE=str(out)), \
         patch('whetstone.vnext_native_editor._run_codex_exec', side_effect=AssertionError('live provider forbidden')), \
         patch('whetstone.vnext_native_editor._run_claude_print', side_effect=AssertionError('live provider forbidden')):
        result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([case]))
    metadata.update(outcome='passed' if result.wasSuccessful() and not result.skipped else 'not_passed',
                    tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                    skips=[reason for _, reason in result.skipped])
    save()
    return 0 if metadata['outcome'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())

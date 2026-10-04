"""Collect Q3's finite regression inventory without executing product tests.

Use PYTHONPATH=src:tests python tests/q3_qualification_inventory.py --output DIR.
Collection is not qualification. Preserve each snapshot; final sources require
a fresh inventory and verdicts recording passes, skips, failures and errors.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def collect():
    # Legacy helpers also use the repository's tests.* namespace. Direct script
    # execution otherwise exposes only the script directory, unlike python -m.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    loader = unittest.TestLoader()
    cases = list(flatten(loader.discover(str(ROOT / 'tests'))))
    if loader.errors:
        raise ValueError('collection errors: ' + '\n'.join(loader.errors))
    counts = Counter(case.id() for case in cases)
    unique = {}
    for case in cases:
        previous = unique.setdefault(case.id(), case)
        if type(previous) is not type(case) or previous.__dict__ != case.__dict__:
            raise ValueError('same identity has different test instances: ' + case.id())
    methods = sorted(unique)
    original = json.loads((ROOT / 'docs/audits/VNEXT_18_9_INVENTORY.json').read_text())
    p0 = {row['id']: [t['id'] for t in row['tests']] for row in original['p0']}
    for number in ('01', '02', '03', '05'):
        p0['P0-' + number] += [i for i in methods if i.startswith('test_vnext_q2_negative_cases.')
                              and 'test_p0_' + number + '_' in i]
    for number, module in [('07', 'test_vnext_q2_budget_stops'),
                           ('12', 'test_vnext_q2_recurrence'), ('13', 'test_vnext_q2_determinism')]:
        p0['P0-' + number] += [i for i in methods if i.startswith(module + '.')]
    p0 = {key: sorted(set(values)) for key, values in p0.items()}
    missing = {key: [i for i in values if i not in unique] for key, values in p0.items()}
    missing = {key: values for key, values in missing.items() if values}
    if missing:
        raise ValueError('unresolved P0 method links: ' + repr(missing))
    simplification = [t['id'] for row in original['supplemental'] for t in row['tests']]
    simplification += [i for i in methods if i.startswith('test_vnext_q2_') and 'simplif' in i]
    if not set(simplification) <= set(methods):
        raise ValueError('unresolved simplification method links')
    groups = {'p0': sorted({i for values in p0.values() for i in values}),
              'simplification': sorted(set(simplification)),
              'd8': [i for i in methods if i.startswith('test_vnext_local_storage.')],
              'process_prefix_faults': [i for i in methods
                                        if i.split('.')[0] in original['D8']['additional_modules']],
              'q1_commands': [i for i in methods if i.startswith('test_vnext_verified_')
                              and ('commands.' in i or 'command_guards.' in i or 'cli.' in i)]}
    for name, category in original['compatibility_inventory'].items():
        modules = {Path(p).stem for p in category['modules']}
        groups[name] = [i for i in methods if i.split('.')[0] in modules]
    paths = sorted(p for directory in ('src', 'tests', 'contracts', 'rubrics')
                   for p in (ROOT / directory).rglob('*')
                   if p.is_file() and '__pycache__' not in p.parts and p.name != '.DS_Store')
    sources = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    return dict(status='collected, not executed; final campaign awaits performance disposition and source freeze',
                commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                python=sys.version, platform=platform.platform(), discovery_occurrences=len(cases),
                distinct_methods=len(methods), modules=len({i.split('.')[0] for i in methods}),
                duplicate_occurrences={key: count for key, count in counts.items() if count > 1},
                duplicate_policy='Execute identical class/method/instance-state identities once; retain occurrence counts.',
                methods=methods, p0=p0, groups=groups, source_sha256=sources,
                declared_skips=[dict(id=key, reason=getattr(type(case), '__unittest_skip_why__', '') or
                                    getattr(getattr(case, case._testMethodName), '__unittest_skip_why__', ''))
                    for key, case in sorted(unique.items()) if getattr(type(case), '__unittest_skip__', False) or
                    getattr(getattr(case, case._testMethodName), '__unittest_skip__', False)],
                limits=['Group labels are indexes, not disjoint execution cohorts or coverage verdicts.',
                        'P0 links join the historical map and Q2; component/test-generated suites retain their scope.',
                        'Runtime skips and outcomes must be recorded by the eventual runner.',
                        'No public gate, provider call or external source write is authorized by collection.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    result = collect()
    with (args.output / 'inventory.json').open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('discovery_occurrences', 'distinct_methods', 'modules', 'declared_skips')}, indent=2))


if __name__ == '__main__':
    main()

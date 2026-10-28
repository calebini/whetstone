"""Config-selected verified command adapter with exact release qualification.

No config/CLI/environment setting can populate QUALIFIED_VERIFIED_SUITES.
Only release-qualified suite digests admit public verified-promotion jobs.
"""
from dataclasses import asdict, is_dataclass
import json
from pathlib import Path
import re

from whetstone import vnext_admission as common
from whetstone.vnext_contracts import (
    CONTRACT_ROOT, canonical_json_bytes, confined_file, decode_json, require,
    sha256_bytes, validate_contract_suite, validate_job_descriptor,
)
from whetstone.vnext_proposal_cli import _package_selector, _settings
from whetstone.vnext_proposal_run import RUN_INPUT_PATH
from whetstone.vnext_verified_bootstrap import prepare_verified_package
from whetstone.vnext_verified_run import open_verified_run

# Controlled opt-in release, 2026-10-28. See VNEXT_VERIFIED_PROMOTION_RELEASE.md.
QUALIFIED_VERIFIED_SUITES = {
    'vnext-verified-consumer-1': '7d636c3cb2da3b687dccd31b17050d8786fc0db256c8e35581739264d002fd58',
}
COMMANDS = frozenset({'vnext-admit', 'live-phase1', 'live-focused-phase1',
    'promote-phase2', 'live-phase2', 'status', 'resume', 'vnext-decisions',
    'vnext-decide', 'vnext-semantic-answers', 'vnext-semantic-answer',
    'vnext-semantic-followup', 'strop', 'apply-back'})


def public(value):
    if is_dataclass(value): return public(asdict(value))
    if isinstance(value, dict): return {k: public(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [public(v) for v in value]
    return value


def read_input(path):
    path = Path(path)
    return decode_json(confined_file(path.parent, path.name).read_bytes())


def emit(args, value):
    packet = public(value)
    if getattr(args, 'format', None) == 'text':
        print('Protocol: vnext\nMode: verified_promotion')
        print(json.dumps(packet, indent=2, ensure_ascii=False))
    else: print(json.dumps(packet, ensure_ascii=False))


def _requested(args, path, root):
    if (root / RUN_INPUT_PATH).is_file():
        job = decode_json(confined_file(root, 'job_descriptor.json').read_bytes())
        require(isinstance(job, dict), 'retained descriptor must be an object')
        if job.get('editing_mode') == 'verified_promotion': return True
    text = path.read_text() if path.is_file() else ''
    # Presence selects validation, not permission. Invalid or incomplete V
    # selectors must not fall through to a legacy writer. Package-only R/P
    # interfaces retain their existing dispatch below this adapter.
    names = ('editing_mode', 'contract_suite_version', 'vnext_phase2_configuration')
    if any(re.search(r'(?m)^\s*'+name+r'\s*:|"'+name+r'"\s*:', text) for name in names):
        return any(name in common.config_packet(path) for name in names)
    return False


def _controls(args, config, *, fresh):
    common.check(args.command in COMMANDS, 'vnext_gate_unavailable', 'unsupported verified command')
    for name in ('overwrite', 'draft_after', 'allow_source_hash_mismatch', 'allow_non_converged',
                 'output_dir', 'closeout_existing', 'rubric_label'):
        common.check(not getattr(args, name, None), 'vnext_selection_conflict', 'unsupported V control: '+name)
    grant = getattr(args, 'extend_review_budget', None)
    require(grant is None or (type(grant) is int and grant > 0),
            'budget extension requires an explicit positive integer')
    require(not getattr(args, 'continue_run', False) or
            (args.command == 'resume' and grant is None),
            'continue and budget grant cannot be combined')
    number = getattr(args, 'vnext_round', None)
    require(number is None or (type(number) is int and number > 0), 'round must be a positive integer')
    require(not fresh or number in (None, 1), 'fresh admission starts at round 1')
    require(getattr(args, 'vnext_decisions', None) is None or args.command in
            {'live-phase1', 'live-focused-phase1', 'live-phase2', 'status'},
            'decision selection is separate from technical recovery')
    require('vnext_input_package' not in config or config['vnext_input_package'] is not None,
            'package selector cannot be null')
    if fresh or args.command not in {'status', 'resume', 'strop', 'apply-back'}:
        common.check(config.get('editing_mode') == 'verified_promotion',
                     'vnext_mode_mismatch', 'V work requires config-selected verified_promotion')
        common.check(isinstance(config.get('contract_suite_version'), str) and bool(config['contract_suite_version']),
                     'vnext_config_invalid', 'V work requires an explicit contract suite version')


def _bound_settings(args, config, *, root, job, review, authority, selectors):
    for name, expected in (('workflow', review['workflow']), ('rubric', 'standard-v1')):
        value = getattr(args, name, None)
        common.check(value is None or value == expected, 'vnext_selection_conflict',
                     'CLI '+name+' differs from the supported immutable V selection')
    for name in ('editing_mode', 'contract_suite_version'):
        if name in config:
            common.check(config[name] == job[name], 'vnext_mode_mismatch', 'config differs from immutable '+name)
    shared = {k:v for k,v in config.items() if k not in
              {'editing_mode', 'contract_suite_version', 'vnext_input_package', 'vnext_phase2_configuration'}}
    _settings(args, shared, root=root, job=job, review=review, authority=authority,
              descriptor_ref=selectors['descriptor_ref'], review_ref=selectors['review_ref'])
    if args.command == 'live-focused-phase1':
        from whetstone.vnext_review_configuration import focused_profile
        selected = focused_profile(review)
        require(selected == args.profile, 'focused profile differs from immutable selection')
        if getattr(args, '_budget_explicit', False):
            require(args.budget == next(p['budget'] for p in review['profiles'] if p['name'] == selected),
                    'focused budget differs from immutable selection')
    require(review['workflow'] == 'standard' and review['profile_set'] == 'stateful_system',
            'unsupported verified workflow/profile set')


def _phase2_selector(config, root, job, selectors):
    if 'vnext_phase2_configuration' not in config: return
    reference = config['vnext_phase2_configuration']
    require(isinstance(reference, dict) and set(reference) == {'path', 'hash'},
            'Phase 2 selector requires exactly path and hash')
    raw = confined_file(root, reference['path']).read_bytes()
    require(sha256_bytes(raw) == reference['hash'], 'Phase 2 configuration hash differs')
    packet = decode_json(raw)
    require(raw == canonical_json_bytes(packet), 'Phase 2 configuration must be canonical')
    require(isinstance(packet, dict), 'Phase 2 configuration must be an object')
    from whetstone.vnext_contracts import VNextSchemaRegistry
    require(packet.get('schema_version') == 'vnext-phase2-configuration-v3',
            'verified command suite requires the Phase 2 v3 configuration')
    VNextSchemaRegistry().validate(packet, 'vnext_phase2_configuration_v3')
    require(packet['job_id'] == job['job_id'] and packet['review_configuration'] == selectors['review_ref'],
            'Phase 2 selector differs from immutable job/review inputs')
    from whetstone.vnext_verified_phase2_binding import REQUEST_PATH
    if (root / REQUEST_PATH).exists():
        request = decode_json(confined_file(root, REQUEST_PATH).read_bytes())
        require(request['configuration']['hash'] == reference['hash'],
                'Phase 2 configuration differs from committed binding')


def command_succeeded(command, packet):
    if command == 'promote-phase2':
        return bool(packet.get('committed') and packet.get('state_current'))
    if packet.get('gate') in {'phase1_complete', 'phase2_complete'} or packet.get('phase_complete'):
        return True
    # Focused stability completes the selected command without accepting Phase 1.
    # Only a reconciled terminal owner result can supply that narrower success.
    operator = packet.get('operator') or {}
    return bool(command == 'live-focused-phase1' and packet.get('phase') == 'phase_1'
        and packet.get('gate') == 'phase1_stopped' and not packet.get('recovery')
        and not packet.get('continuation') and operator.get('state_current')
        and (operator.get('terminal_report') or {}).get('terminal_state') == 'FOCUSED_PROFILE_STABLE')


def dispatch_verified(args):
    root = Path(getattr(args, 'run_root', None) or getattr(args, 'root', '.'))
    path = root / getattr(args, 'config', 'orchestrator_config.yaml')
    run = None
    try:
        if not _requested(args, path, root): return None
        config = common.config_packet(path)
        existing = (root / RUN_INPUT_PATH).is_file()
        _controls(args, config, fresh=not existing)
        selected = _package_selector(args, dict(config), path)
        if existing:
            job = decode_json(confined_file(root, 'job_descriptor.json').read_bytes())
            suite = validate_contract_suite(CONTRACT_ROOT/'suites'/(job['contract_suite_version']+'.json'))
            validate_job_descriptor(job, suite)
            common.check(QUALIFIED_VERIFIED_SUITES.get(suite.version) == suite.digest,
                         'vnext_mode_unavailable', 'verified promotion is not release-qualified')
            run = open_verified_run(root, suite_path=CONTRACT_ROOT/'suites'/(suite.version+'.json'))
            record = run._record
            proof = run._operator()._proof(run.store.read)
            values = proof.seed_values
            selectors = dict(descriptor_ref=record['descriptor'], review_ref=record['review_configuration'])
            if selected:
                require(selected[1] == run.store.read(record['launch_package']['path']), 'package differs from retained inputs')
            require(args.command != 'vnext-admit', 'admission cannot reuse an existing root')
        else:
            common.check(not root.exists(), 'vnext_root_incompatible', 'V destination must not exist')
            common.check(selected is not None and 'vnext_input_package' in config,
                         'vnext_config_invalid', 'fresh V admission requires a config input package')
            require(args.command in {'vnext-admit', 'live-phase1', 'live-focused-phase1'}, 'command requires an existing V root')
            prepared = prepare_verified_package(selected[0].parent, manifest_path=selected[0].name)
            selectors = decode_json(prepared.selectors_json)
            job = decode_json(prepared.artifacts['job_descriptor.json'])
            suite = validate_contract_suite(prepared.suite_path)
            common.check(QUALIFIED_VERIFIED_SUITES.get(suite.version) == suite.digest,
                         'vnext_mode_unavailable', 'verified promotion is not release-qualified')
            values = dict(review=decode_json(prepared.artifacts[selectors['review_ref']['path']]),
                          authority=decode_json(prepared.artifacts[job['authority_map_path']]))
        _bound_settings(args, config, root=root if existing else prepared.source_root, job=job, review=values['review'],
                        authority=values['authority'], selectors=selectors)
        _phase2_selector(config, root, job, selectors)
        if not existing:
            # Construction validates transport settings without invoking providers.
            from whetstone.vnext_proposal_cli import _client
            for role in ('reviewer', 'editor', 'verifier'):
                _client(role, values['review'], config, args, prepared.source_root)
            if getattr(args, 'dry_run', False):
                emit(args, dict(protocol='vnext', mode='verified_promotion', admitted=False, gate='admission'))
                return 0
            run = prepared.create(root)
            # A just-created seed has no candidate or client request. Complete
            # its initial projections through the normal fenced recovery owner.
            run.recover_registration()
            if args.command == 'vnext-admit':
                emit(args, dict(protocol='vnext', mode='verified_promotion', admitted=True, gate='materialization'))
                return 0
        from whetstone.vnext_verified_commands import execute
        result = execute(run, args, config, values['review'])
        emit(args, result)
        if args.command in {'live-phase1', 'live-focused-phase1', 'live-phase2', 'promote-phase2'}:
            return 0 if command_succeeded(args.command, public(result)) else 2
        return 0
    except (ValueError, OSError, KeyError, TypeError, RuntimeError) as exc:
        emit(args, dict(protocol='vnext', mode='verified_promotion', admitted=False,
                        reason_code=getattr(exc, 'code', 'vnext_input_invalid'), reason=str(exc)))
        return 2
    finally:
        if run is not None: run.close()

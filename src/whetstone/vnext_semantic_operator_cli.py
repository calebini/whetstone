"""Explicit interpretation commands; no model invocation or effect grants."""
from pathlib import Path

from whetstone.vnext_contracts import CONTRACT_ROOT, confined_file, decode_json, require, sha256_bytes
from whetstone.vnext_semantic_answers import inspect_semantic_answers, submit_semantic_answer


ALGORITHM = 'algorithms/vnext_semantic_operator_cli_v1.md'
COMMANDS = frozenset({'vnext-semantic-answers', 'vnext-semantic-answer', 'vnext-semantic-followup'})


def validate_operator_cli(suite):
    from whetstone.vnext_semantic_followup_preflight import validate_followup_contracts
    from whetstone.vnext_semantic_followup_admission import ALGORITHM as admission_algorithm, SCHEMAS
    from whetstone.vnext_semantic_followup_workflow import ALGORITHM as workflow_algorithm
    # This also runs before fresh-root creation. A qualification entry cannot
    # defer missing follow-up consumer contracts until after initialization.
    validate_followup_contracts(suite)
    entries = {row['path']: row for family in ('algorithms', 'schemas') for row in suite.manifest[family]}
    paths = {ALGORITHM, admission_algorithm, workflow_algorithm} | {'schemas/'+name+'.schema.json' for name in SCHEMAS}
    require(paths <= entries.keys(), 'semantic operator CLI contracts are outside supported suite')
    for path in paths:
        require(sha256_bytes(confined_file(CONTRACT_ROOT, path).read_bytes()) == entries[path]['sha256'],
                'installed semantic operator CLI contract differs from pinned suite', path)


def execute_operator_command(run, args, *, round_number):
    """The dispatcher has qualified this consumer and bound its configuration."""
    require(args.command in COMMANDS, 'unknown semantic operator command')
    registered = run.router.registry().inspect()
    creation = next((event for event in registered.events if event['candidate_id'] == args.candidate), None)
    require(creation is not None and creation['round_number'] == round_number,
            'semantic operator candidate differs from the selected round')
    if args.command == 'vnext-semantic-answers':
        return {'semantic_answers': inspect_semantic_answers(run.store, admission=run.router,
                                                            candidate_id=args.candidate)}
    if args.command == 'vnext-semantic-answer':
        path = Path(args.input)
        packet = decode_json(confined_file(path.parent, path.name).read_bytes())
        require(isinstance(packet, dict) and packet.get('candidate_id') == args.candidate,
                'semantic answer input differs from the selected candidate')
        return {'semantic_answer': submit_semantic_answer(run.store, admission=run.router,
                                                         packet=packet, dry_run=args.dry_run)}
    reference = {'path': args.answer_receipt, 'hash': args.answer_hash}
    return {'semantic_followup': run.admit_followup(candidate_id=args.candidate, answer_reference=reference)}

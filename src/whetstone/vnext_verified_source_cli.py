"""Separate read-only review, exact approval, retry and historical source recovery."""
from pathlib import Path

from whetstone.vnext_contracts import canonical_json_bytes, confined_file, decode_json, require, sha256_bytes


def execute_source(run, args):
    recover = args.recover
    apply = args.apply
    require(not recover or not any((apply, args.approve, args.retry_apply, args.approval, args.approval_hash)),
            'recovery cannot select a new source approval or write')
    require(apply or not any((args.approve, args.retry_apply, args.approval, args.approval_hash)),
            'approval and retry operands require --apply')
    job = decode_json(run.store.read_descriptor())
    # Source spelling cannot redirect the descriptor's authority.
    source = job.get('source_spec')
    if source is not None and source['path'] is not None:
        require(str(Path(args.source).absolute()) == source['path'], 'source differs from descriptor binding')
        if args.expected_source_hash:
            require(args.expected_source_hash == source['expected_hash'], 'source hash override differs from descriptor')
    if recover:
        require(args.exclusive_source_access, 'historical recovery requires exclusive source access')
        if getattr(args, 'dry_run', False): return run.apply_back_status()
        return run.recover_apply_back(exclusive_source_access=True)
    if not apply: return run.review_apply_back()
    require(args.approve and args.exclusive_source_access and args.approval and args.approval_hash,
            'apply requires explicit approval, exact assessment/hash and exclusive source access')
    path = Path(args.approval).absolute()
    require(not path.is_relative_to(run.store.root), 'assessment file must be outside the run root')
    raw = confined_file(path.parent, path.name).read_bytes()
    require(sha256_bytes(raw) == args.approval_hash, 'assessment file hash differs')
    packet = decode_json(raw)
    require(raw == canonical_json_bytes(packet), 'assessment file must contain exact canonical JSON')
    from whetstone.vnext_contracts import VNextSchemaRegistry
    VNextSchemaRegistry().validate(packet, 'vnext_apply_back_review_v1')
    if getattr(args, 'dry_run', False): return dict(approval_valid=True, review=run.review_apply_back())
    return run.apply_back(assessment=packet, approve=True, exclusive_source_access=True, retry=args.retry_apply)

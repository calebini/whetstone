"""Read-only evidence for blocked final reviews; never a repair or retry grant."""
from copy import deepcopy

from whetstone.declaration import _parse_fields
from whetstone.hashing import draft_hash
from whetstone.vnext_contracts import CONTRACT_ROOT, confined_file, require, sha256_bytes
from whetstone.vnext_verified_phase2_binding import _ref
from whetstone.vnext_verified_phase2_closeout import _bundle, _latest_issues
from whetstone.vnext_verified_phase2_findings import _Findings

ALGORITHM = 'algorithms/vnext_verified_phase2_blocked_v1.md'
SCHEMA = 'vnext_phase2_blocked_report_v1'


def _comparisons(package, configuration, pointer, draft, residual):
    """Compare reviewed counts and post-review residual counts separately."""
    packet = package['packet']
    observed = _parse_fields(package['assets']['declaration'][1].decode())
    expected = {key: configuration[key] for key in ('target_phase', 'target_mode', 'workflow')}
    expected.update(rubric_profile=configuration['rubric']['profile'],
        rubric_source=configuration['rubric']['source'], rubric_label='null',
        rubric_manifest_path=packet['rubric_manifest']['path'],
        rubric_content_hash=configuration['rubric']['artifact']['hash'],
        final_draft_hash=draft_hash(draft.decode()), final_draft_sha256=sha256_bytes(draft),
        current_verified_pointer_path=pointer['path'], current_verified_pointer_hash=pointer['hash'],
        reviewer_final_status='not_run', declaration_status='rejected')
    for field, count in (('unresolved_blockers count', 'blockers'),
                         ('unresolved_major_issues count', 'major_issues'),
                         ('unresolved_rubric_gaps count', 'rubric_gaps')):
        expected[field] = str(packet['counts'][count])
    def compare(values):
        return [dict(field=key, observed=observed.get(key), expected=value,
                     matches=observed.get(key) == value) for key, value in sorted(values.items())]
    # Rubric impact is not a computed gap count: that resolution owner is absent.
    current = {'unresolved_blockers count': str(sum(r['normalized_severity'] == 'blocker' for r in residual)),
               'unresolved_major_issues count': str(sum(r['normalized_severity'] == 'major' for r in residual))}
    return dict(reviewed_inputs=compare(expected), current_residuals=compare(current))


class _BlockedReport(_Findings):
    def _proof(self, read):
        proof = super()._proof(read)
        pins = {r['path']: r['sha256'] for family in ('algorithms', 'schemas')
                for r in proof.reader.suite.manifest[family]}
        for path in (ALGORITHM, 'schemas/' + SCHEMA + '.schema.json'):
            require(path in pins and pins[path] == sha256_bytes(confined_file(CONTRACT_ROOT, path).read_bytes()),
                    'Phase 2 blocked report is outside supported suite or changed', path)
        return proof

    def inspect_report(self):
        proof = self._proof(self.store.read)
        work = self._observe(proof)
        if work.outcome != 'work_available':
            return work
        state, view = self._finding_view(proof)
        require(view['committed'], 'blocked report requires committed finding reconciliation')
        receipt = view['packet']
        require(receipt['blocking_reasons'], 'blocked report requires a blocked final review')
        final = state['frames'][-1]
        owner = final['owner']
        from whetstone.vnext_verified_phase2_review_only import package_for
        package = package_for(owner)
        rows = _latest_issues(state['frames'], proof.latest)
        latest = {f['bound'].request['step']['profile']: f for f in state['frames']
                  if f.get('consumed') and f['bound'].request['base_pointer'] == proof.latest}
        findings = []
        for row in rows:
            sources = [dict(feedback=deepcopy(f['receipt']['feedback']),
                            consumption=_ref(f['owner'].consumption_path, f['consumption']))
                       for _, f in sorted(latest.items())
                       if row in f['review']['feedback']['feedback']]
            require(sources, 'blocked finding lacks current source feedback')
            findings.append(dict(finding=deepcopy(row), sources=sources, disposition='unresolved'))
        profile = final['consumption']['profiles'][final['bound'].request['step']['index'] - 1]
        report = dict(schema_version='vnext-phase2-blocked-report-v1', report_kind='status_only',
            job_id=receipt['job_id'], reconciliation=deepcopy(view['reference']),
            sources={key: deepcopy(receipt[key]) for key in ('current_verified_pointer', 'configuration',
                'declaration_binding', 'review_request', 'review_result', 'review_consumption', 'unresolved_issues')},
            declaration=deepcopy(package['packet']['declaration']),
            reviewed_issues=deepcopy(package['packet']['unresolved_issues']),
            reviewed_gaps=deepcopy(package['packet']['rubric_gaps']),
            route=receipt['route'], blocking_reasons=deepcopy(receipt['blocking_reasons']), findings=findings,
            comparisons=_comparisons(package, owner.binding.configuration, proof.latest,
                                     proof.values(proof.latest)['base'], rows),
            budget=dict(step_index=final['bound'].request['step']['index'], profile=profile['profile'],
                round_budget=profile['round_budget'], rounds_used=profile['rounds_used'],
                remaining=receipt['remaining_step_budget']),
            automatic_repair_established=False, findings_resolved=False, repair_authorized=False,
            candidate_authorized=False, next_review_authorized=False, phase_complete=False)
        proof.reader.suite.registry.validate(report, SCHEMA)
        # Recheck observed immutable bytes without acquiring a writer fence or repairing.
        owner.store.check(dict(owner.store.reads))
        for reference in (view['reference'], receipt['unresolved_issues']):
            proof.reader.raw(reference)
        proof.guard(self.store.read)
        self.run._guard(self.store.read)
        return report

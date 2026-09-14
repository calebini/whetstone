"""Bounded seed review execution and evidence-derived phase terminal reports.

Finding admission remains a separate explicit action. This consumer never
constructs an Editor plan, selects an operator option or enters Phase 2.
"""
from dataclasses import dataclass

from whetstone.vnext_contracts import canonical_json_bytes,require,sha256_bytes
from whetstone.vnext_proposal_closeout import proposal_terminal_report
from whetstone.vnext_proposal_handoff import registry_for_proposal_requests
from whetstone.vnext_review_requests import ReviewStep,_sequence,inspect_seed_review,run_next_seed_review


FINAL_REVIEW_STATES=frozenset({'phase_1_stable','budget_exhausted','invalid_review','attempts_exhausted'})


@dataclass(frozen=True)
class SeedReviewCloseout:
    report: dict
    reference: dict
    materialized: bool
    final: bool


@dataclass(frozen=True)
class SeedReviewPhaseResult:
    review: ReviewStep
    terminal_report: dict | None=None
    terminal_report_ref: dict | None=None


def inspect_seed_review_closeout(run,review=None):
    """Reproduce a terminal from live evidence, never from report filenames."""
    current=inspect_seed_review(run)
    require(review is None or review==current,'seed review selection changed before closeout')
    review=current
    if review.status in {'not_started','prepared','valid_response','finding_admission'}:return None
    if review.status=='phase_1_stable':
        terminal='PHASE_1_STABLE';reason='vnext_seed_review_complete';eligible=False
    elif review.status=='budget_exhausted':
        terminal='TARGET_NOT_REACHED';reason='vnext_review_budget_exhausted';eligible=False
    else:
        last=review.last_outcome or {};cause=last.get('classification','interrupted')
        terminal='HALTED_CLIENT_TIMEOUT' if cause=='timeout' else 'HALTED_ARTIFACT_INVALID'
        reason='vnext_review_'+cause
        if last.get('error'):reason+=': '+last['error']
        eligible=review.status not in FINAL_REVIEW_STATES and review.attempts<2
    registry=registry_for_proposal_requests(run.store,load_inputs=run.load_inputs,validate_authority=run.validate_authority)
    registered=registry.inspect()
    require(not registered.events and not registered.orphans,'seed review closeout cannot bypass candidate processing')
    report=proposal_terminal_report(registry,terminal_state=terminal,reason=reason,
                                   next_gate='review' if eligible else None,resume_permitted=eligible)
    raw=canonical_json_bytes(report);path='rounds/terminal_reports/terminal-'+sha256_bytes(raw)+'.json'
    try:stored=run.store.read(path)
    except FileNotFoundError:run.store.read_descriptor();stored=None
    require(stored is None or stored==raw,'seed review terminal materialization conflicts with evidence')
    return SeedReviewCloseout(report,{'path':path,'hash':sha256_bytes(raw)},stored is not None,
                             review.status in FINAL_REVIEW_STATES)


def finish_seed_review(run):
    """Repeat source barriers, then publish the exactly reproduced terminal."""
    with run.store.locked(run.validate_authority) as token:
        completed,pending,gate,profile,previous=_sequence(run)
        for request,header,outcomes,review,receipt in completed:
            request.synchronize(token,header,outcomes);request.finish(token,review)
        if pending:
            request,header,outcomes,review,receipt=pending
            request.synchronize(token,header,outcomes)
        step=inspect_seed_review(run);closeout=inspect_seed_review_closeout(run,step)
        require(closeout is not None,'seed review has no terminal outcome to materialize')
        run.store.publish(token,closeout.reference['path'],closeout.report)
        checked=inspect_seed_review_closeout(run)
        require(checked is not None and checked.materialized and checked.report==closeout.report,
                'seed review terminal changed during publication')
        return SeedReviewPhaseResult(step,checked.report,checked.reference)


def run_seed_review_phase(run,*,client,continuation=False):
    """Run configured seed reviews up to findings, terminal outcome or failure."""
    require(type(continuation) is bool,'Reviewer continuation must be an explicit boolean')
    review=inspect_seed_review(run)
    status=run.status(round_number=review.round_number)
    if review.status=='finding_admission':
        require(not continuation,'finding admission is not technical continuation')
        return SeedReviewPhaseResult(review)
    require(not continuation or status['resume']['permitted'],'seed review gate is not technically resumable')
    require(continuation or not status['resume']['permitted'],
            'interrupted seed review requires explicit continuation')
    if status['processing_gate']=='materialization' or review.status in FINAL_REVIEW_STATES:
        # Recovery ends here, without another request or a new ordinal.
        return finish_seed_review(run)
    while True:
        result=run_next_seed_review(run,client=client,continuation=continuation)
        continuation=False
        if result.status!='complete':
            if result.status=='finding_admission':return SeedReviewPhaseResult(result)
            return finish_seed_review(run)
        review=inspect_seed_review(run)
        if review.status=='finding_admission':return SeedReviewPhaseResult(review)
        if review.status in FINAL_REVIEW_STATES:return finish_seed_review(run)
        require(review.status=='not_started','seed review did not advance to its selected next request')

"""Retained proposal selectors, root reopening and round admission.

This is a private integration boundary until the shipping suite and D8 release
qualify. It never treats a locator record as capability or candidate authority.
"""
from copy import deepcopy
from pathlib import Path

from whetstone.vnext_contracts import (CONTRACT_ROOT,VNextSchemaRegistry,canonical_json_bytes,
    confined_file,decode_json,require,sha256_bytes)
from whetstone.vnext_local_storage import LocalAuthorityStore
from whetstone.vnext_proposal_admission import ProposalAdmission

RUN_INPUT_PATH='inputs/proposal_run.json'


def round_input_path(number):
    require(type(number) is int and number>0,'invalid proposal round selector')
    return f'rounds/round-{number}/proposal_input.json'


def run_input_record(job,selectors):
    value={'schema_version':'vnext-proposal-run-input-v1','job_id':job['job_id'],
        'descriptor':deepcopy(selectors['descriptor_ref']),'review_configuration':deepcopy(selectors['review_ref']),
        'seed_section_map':deepcopy(selectors['seed_map_ref']),
        'staged_rounds':[{'round_number':number,'input':deepcopy(reference)}
                         for number,reference in sorted(selectors['round_refs'].items())]}
    if selectors.get('launch_package_ref') is not None:value['launch_package']=deepcopy(selectors['launch_package_ref'])
    VNextSchemaRegistry().validate(value,'vnext_proposal_run_input_v1')
    return value


class ProposalRun:
    def __init__(self,store,*,suite_path):
        self.store=store;self.suite_path=Path(suite_path)
        self._raw=store.read(RUN_INPUT_PATH);self._record=decode_json(self._raw)
        VNextSchemaRegistry().validate(self._record,'vnext_proposal_run_input_v1')
        require(self._raw==canonical_json_bytes(self._record),'noncanonical proposal run input record')
        numbers=[entry['round_number'] for entry in self._record['staged_rounds']]
        require(numbers==sorted(set(numbers)),'staged round selectors must be sorted and unique')
        self._staged={entry['round_number']:entry['input'] for entry in self._record['staged_rounds']}
        self.validate_authority(store.read)

    def _admission(self,read,round_refs=None):
        require(read(RUN_INPUT_PATH)==self._raw,'retained proposal run selectors changed')
        admission=ProposalAdmission(self.store,suite_path=self.suite_path,
            descriptor_ref=self._record['descriptor'],review_ref=self._record['review_configuration'],
            seed_map_ref=self._record['seed_section_map'],round_refs=round_refs or {},
            launch_package_ref=self._record.get('launch_package'))
        return admission

    def validate_authority(self,read):
        self._base(read)

    def _base(self,read):
        """Expose the same pinned base to downstream admitted consumers."""
        reader,values=self._admission(read)._base(read)
        require(values['job']['job_id']==self._record['job_id'],'proposal run record belongs to another job')
        return reader,values

    def selected_round(self,read,number):
        path=round_input_path(number)
        try:raw=read(path)
        except FileNotFoundError:
            self.validate_authority(read);raw=None
        staged=self._staged.get(number)
        if staged is not None:
            staged_raw=read(staged['path'])
            require(sha256_bytes(staged_raw)==staged['hash'],'staged proposal round reference changed')
            require(raw is None or raw==staged_raw,'committed round differs from its staged input')
            if raw is None:return deepcopy(staged)
        require(raw is not None,'proposal round has no admitted input record')
        return {'path':path,'hash':sha256_bytes(raw)}

    def load_inputs(self,read,number):
        reference=self.selected_round(read,number)
        from whetstone.vnext_review_requests import validate_review_binding
        validate_review_binding(self,number,decode_json(read(reference['path'])))
        return self._admission(read,{number:reference}).load_inputs(read,number)

    def admit_round(self,record):
        """Validate source evidence, then publish the canonical round input.

        All Reviewer/decision inputs must already exist by their exact hashes.
        No choice, finding, grant or plan is invented by this publication.
        """
        frozen=deepcopy(record);raw=canonical_json_bytes(frozen)
        VNextSchemaRegistry().validate(frozen,'vnext_proposal_round_input_v1')
        number=frozen['round_number'];path=round_input_path(number);reference={'path':path,'hash':sha256_bytes(raw)}
        def staged_read(relative):return raw if relative==path else self.store.read(relative)
        with self.store.locked(self.validate_authority) as token:
            from whetstone.vnext_review_requests import validate_review_binding
            validate_review_binding(self,number,frozen)
            if number in self._staged:
                staged=self._staged[number]
                require(self.store.read(staged['path'])==raw and staged['hash']==reference['hash'],
                        'round admission contradicts its staged selector')
            admission=self._admission(staged_read,{number:reference})
            admission.load_inputs(staged_read,number)
            sources=[frozen['feedback']]
            if frozen['advice'] is not None:sources.append(frozen['advice'])
            for choice in frozen['decision_refs']:sources.extend([choice['request'],choice['response']])
            for source in sources:
                content=self.store.read(source['path'])
                require(sha256_bytes(content)==source['hash'],'round source changed before admission')
                self.store.publish(token,source['path'],content)
            # Repeat full preflight after dependency barriers and before commit.
            admission.load_inputs(staged_read,number)
            self.store.publish(token,path,raw)
            self.load_inputs(self.store.read,number)
            return reference

    def run_round(self,*,round_number,client,decided_at,continuation=False):
        from whetstone.vnext_proposal_closeout import run_proposal_round
        reference=self.selected_round(self.store.read,round_number)
        record=decode_json(self.store.read(reference['path']))
        status=self.status(round_number=round_number)
        require(not continuation or status['resume']['permitted'],'selected proposal gate is not technically resumable')
        require(continuation or not status['resume']['permitted'],
                'interrupted proposal work requires explicit continuation')
        require(status['resume']['reason']!='vnext_registration_recovery_required' or (
            continuation and status['resume']['permitted']), 'registration recovery must complete before new work')
        self.admit_round(record)
        return run_proposal_round(self.store,admission=self,round_number=round_number,
            client=client,decided_at=decided_at,continuation=continuation)

    def status(self,*,round_number):
        from whetstone.vnext_proposal_status import inspect_proposal_run
        return inspect_proposal_run(self,round_number=round_number)

    def semantic_status(self,*,round_number):
        from whetstone.vnext_semantic_run import inspect_semantic_round
        return inspect_semantic_round(self,round_number=round_number)

    def verify_round(self,*,round_number,client=None,decided_at,continuation=False):
        from whetstone.vnext_semantic_run import run_semantic_round
        return run_semantic_round(self,round_number=round_number,client=client,
                                  decided_at=decided_at,continuation=continuation)

    def review_status(self):
        from whetstone.vnext_review_requests import inspect_seed_review
        return inspect_seed_review(self)

    def review_next(self,*,client,continuation=False):
        from whetstone.vnext_review_requests import run_next_seed_review
        return run_next_seed_review(self,client=client,continuation=continuation)

    def review_phase(self,*,client,continuation=False):
        from whetstone.vnext_seed_review_closeout import run_seed_review_phase
        return run_seed_review_phase(self,client=client,continuation=continuation)

    def admit_reviewed_round(self,*,decision_refs=()):
        """Use packaged limits and exact live review; decisions stay explicit."""
        from whetstone.vnext_proposal_package import validate_launch_package
        reader,values=self._admission(self.store.read)._base(self.store.read)
        reference=self._record.get('launch_package')
        require(reference is not None,'reviewed round requires explicit packaged mutation constraints')
        constraints=validate_launch_package(reader,reference,descriptor_ref=self._record['descriptor'],
            review_ref=self._record['review_configuration'],authority=values['authority'])
        review=self.review_status()
        require(review.status=='finding_admission' and review.receipt is not None,'no completed review awaits finding admission')
        record={'schema_version':'vnext-proposal-round-input-v1','job_id':values['job']['job_id'],
            'round_number':review.round_number,'base_pointer':values['base_pointer_ref'],
            'feedback':review.receipt['feedback'],'advice':review.receipt['advice'],
            'decision_refs':deepcopy(list(decision_refs)),'constraints':constraints}
        return self.admit_round(record)

    def close(self):self.store.close()
    def __enter__(self):return self
    def __exit__(self,*exc):self.close()


def open_proposal_run(root,*,suite_path=None):
    # Initial filesystem reads select only locators; the opened kernel then
    # verifies physical binding and every consumed descriptor/input hash.
    raw=confined_file(Path(root),RUN_INPUT_PATH).read_bytes();record=decode_json(raw)
    VNextSchemaRegistry().validate(record,'vnext_proposal_run_input_v1')
    require(raw==canonical_json_bytes(record),'noncanonical proposal run input record')
    store=LocalAuthorityStore(root,job_id=record['job_id'])
    try:
        require(store.read(RUN_INPUT_PATH)==raw,'proposal run selectors changed while opening')
        job=decode_json(store.read_descriptor())
        from whetstone.vnext_registry import SUPPORTED_SUITES
        require(job['contract_suite_version'] in SUPPORTED_SUITES,'unknown proposal contract suite')
        path=suite_path if suite_path is not None else CONTRACT_ROOT/'suites'/(job['contract_suite_version']+'.json')
        return ProposalRun(store,suite_path=path)
    except BaseException:
        store.close()
        raise

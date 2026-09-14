"""Package-based CLI routing, guarded by exact release qualification.

The qualification map is intentionally empty until 18.5 and D8 pass. Fixture
tests may register a test suite explicitly; configuration cannot populate it.
"""
import json,re
from pathlib import Path

from whetstone import vnext_admission as common
from whetstone.vnext_contracts import VNextSchemaRegistry,canonical_json_bytes,confined_file,decode_json,sha256_bytes,validate_contract_suite
from whetstone.vnext_native_editor import NativePatchProposalClient
from whetstone.vnext_native_reviewer import NativeProposalReviewerClient
from whetstone.vnext_native_verifier import NativeSemanticVerifierClient
from whetstone.vnext_proposal_package import prepare_proposal_package
from whetstone.vnext_proposal_run import RUN_INPUT_PATH,open_proposal_run,round_input_path

QUALIFIED_PROPOSAL_SUITES={}
QUALIFIED_SEMANTIC_SUITES={}
QUALIFIED_SEMANTIC_FOLLOWUP_SUITES={}
PROPOSAL_GATES=('admission','seed_initialization','review','finding_admission','proposal','assembly',
                'deterministic_validation','verification_commit','materialization','complete')


def _qualified(job,suite):
    return job is not None and suite is not None and QUALIFIED_PROPOSAL_SUITES.get(suite.version)==suite.digest


def _qualified_semantic(job,suite):
    return _qualified(job,suite) and QUALIFIED_SEMANTIC_SUITES.get(suite.version)==suite.digest


def _qualified_followup(job,suite):
    return _qualified_semantic(job,suite) and QUALIFIED_SEMANTIC_FOLLOWUP_SUITES.get(suite.version)==suite.digest


def _diagnostic(job,suite,*,gate,admitted=False,error=None,status=None):
    packet=common.diagnostic(job,suite,gate,admitted=admitted,error=error)
    capability=packet['vnext']
    if _qualified(job,suite):
        capability['available_modes']=sorted(set(capability['available_modes'])|{'proposal_only'})
        if job['editing_mode']=='proposal_only':
            capability['available_gates']=sorted(set(PROPOSAL_GATES)|({'semantic_verification'} if _qualified_semantic(job,suite) else set()))
    if status is not None:
        packet['proposal_status']=status;packet['terminal_report']=status['terminal_report']
        if error is None:
            packet['terminal_state']=(status['terminal_report'] or {}).get('terminal_state')
            capability.update(requested_gate=status['processing_gate'],reason=status['resume']['reason'],
                reason_code=status['resume']['reason'].split(':',1)[0],
                next_action='resume' if status['resume']['permitted'] else
                    'inspect_findings' if status['processing_gate']=='finding_admission' else
                    'run_requested_gate' if status['request_status']=='not_started' else 'inspect_evidence')
            work=status.get('operator_work')
            if work and work['requires_new_job']:capability['next_action']='new_isolated_root'
            elif work and work['requests']:
                capability['next_action']='select_decision_receipt' if work['selections'] else 'review_decisions'
    # Validate the capability envelope before adding the detailed projection.
    VNextSchemaRegistry().validate({k:packet[k] for k in ('protocol','terminal_state','vnext')},'vnext_capability_v1')
    return packet


def _emit(args,packet):
    if getattr(args,'format','json')=='text':
        capability=packet['vnext'];status=packet.get('proposal_status') or {}
        print('Protocol: vnext\nMode: '+str(capability['requested_mode']))
        print('State: '+str(packet['terminal_state'] or ('ADMITTED' if capability['admitted'] else 'NOT_ADMITTED')))
        print('Next action: '+capability['next_action']);print(capability['reason'])
        if status:print('Processing gate: '+status['processing_gate'])
        if packet.get('terminal_report'):print('Verified draft: '+packet['terminal_report']['current_verified_draft_path'])
    else:print(json.dumps(packet))


def _package_selector(args,config,config_path):
    configured=config.pop('vnext_input_package',None)
    explicit=getattr(args,'vnext_input_package',None)
    def raw(path):
        path=Path(path)
        value=confined_file(path.parent,path.name).read_bytes();packet=decode_json(value)
        common.check(value==canonical_json_bytes(packet),'vnext_config_invalid','package selector must name canonical JSON')
        VNextSchemaRegistry().validate(packet,'vnext_proposal_package_v1')
        return path.resolve(),value
    common.check(explicit is None or bool(explicit),'vnext_config_invalid','package locator cannot be empty')
    selected=raw(explicit) if explicit is not None else None
    if configured is not None:
        common.check(isinstance(configured,dict) and set(configured)=={'path','hash'},
                     'vnext_config_invalid','vnext_input_package requires exactly path and hash')
        common.check(isinstance(configured['path'],str) and bool(configured['path']),
                     'vnext_config_invalid','package locator must be a nonempty path')
        other=raw(config_path.parent/configured['path'])
        common.check(sha256_bytes(other[1])==configured['hash'],'vnext_config_invalid','configured package hash differs')
        common.check(selected is None or selected[1]==other[1],'vnext_selection_conflict','CLI and configuration select different packages')
        if selected is None:selected=other
    return selected


def _settings(args,config,*,root,job,review,authority,descriptor_ref,review_ref):
    common._settings(config,review,job,authority)
    explicit=bool(getattr(args,'vnext_job_descriptor',None) or getattr(args,'vnext_review_configuration',None))
    if explicit or 'vnext' in config:
        selection=common.select(root,config,descriptor_path=getattr(args,'vnext_job_descriptor',None),
                                review_path=getattr(args,'vnext_review_configuration',None))
        common.check(selection['job_descriptor']['hash']==descriptor_ref['hash']
                     and selection['review_configuration']['hash']==review_ref['hash'],
                     'vnext_selection_conflict','descriptor/review selectors differ from the admitted package')
    for name in ('timeout_seconds','reviewer_timeout_seconds','editor_timeout_seconds','verifier_timeout_seconds'):
        value=getattr(args,name,None)
        common.check(value is None or (type(value) is int and value>0),'vnext_config_invalid','timeouts must be positive integers')


def _client(role,review,config,args,root):
    cls={'reviewer':NativeProposalReviewerClient,'editor':NativePatchProposalClient,'verifier':NativeSemanticVerifierClient}[role]
    timeout=getattr(args,role+'_timeout_seconds',None) or getattr(args,'timeout_seconds',None) or \
        config.get('timeouts',{}).get(role+'_seconds',360)
    return cls(review=review,command=config.get('clients',{}).get(role,{}).get('command'),cwd=root,timeout_seconds=timeout)


def _number(run,args):
    selected=getattr(args,'vnext_round',None)
    if selected is not None:
        common.check(type(selected) is int and selected>0,'vnext_config_invalid','round selector must be a positive integer')
        return selected
    if run._staged:
        common.check(len(run._staged)==1,'vnext_config_invalid','multiple staged rounds require --vnext-round')
        return next(iter(run._staged))
    return run.review_status().round_number


def _has_round(run,number):
    if number in run._staged:return True
    try:run.store.read(round_input_path(number));return True
    except FileNotFoundError:return False


def _semantic_candidate_gate(run,status):
    from whetstone.vnext_semantic_workflow import SemanticProposalRun
    if not isinstance(run,SemanticProposalRun):return False
    if status['processing_gate']=='semantic_verification':return True
    report=status['terminal_report']
    return bool(report and report['latest_candidate']['candidate_id'] is not None
                and status['processing_gate'] in {'verification_commit','materialization','complete'}
                and status['resume']['reason']!='vnext_historical_proposal_complete')


def _execute_semantic(run,args,config,review,number,status,continuation):
    if status['processing_gate']=='complete':return status
    if status['request_status'] in {'invalid_semantic','attempts_exhausted'} and not status['resume']['permitted']:return status
    client=None
    if status['processing_gate']=='semantic_verification':
        client=_client('verifier',review,config,args,run.store.root)
    run.verify_round(round_number=number,client=client,decided_at=common.stamp(),continuation=continuation)
    return run.status(round_number=number)


def _execute(run,args,config,review,number,decisions=None):
    status=run.status(round_number=number);continuation=args.command=='resume'
    common.check(not continuation or status['resume']['permitted'],'vnext_gate_unavailable',
                 'selected gate is not technically resumable',terminal=None,action='inspect_evidence')
    common.check(continuation or not status['resume']['permitted'],'vnext_selection_conflict',
                 'interrupted work requires explicit resume --continue',terminal=None,action='resume')
    if _semantic_candidate_gate(run,status):return _execute_semantic(run,args,config,review,number,status,continuation)
    if status['processing_gate'] in {'complete','semantic_verification'} and not status['resume']['permitted']:return status
    if continuation and status['processing_gate']=='materialization':
        if _has_round(run,number):
            from whetstone.vnext_proposal_closeout import finish_proposal_round
            finish_proposal_round(run.store,admission=run,round_number=number,decided_at=common.stamp())
        else:run.review_phase(client=None,continuation=True)
        return run.status(round_number=number)
    if not _has_round(run,number):
        current=run.review_status()
        common.check(current.round_number==number,'vnext_selection_conflict','selected round is not active',terminal=None)
        if current.status!='finding_admission':
            result=run.review_phase(client=_client('reviewer',review,config,args,run.store.root),continuation=continuation)
            number=result.review.round_number
            if result.terminal_report is not None:return run.status(round_number=number)
        current=run.review_status()
        if decisions is None and any(f['classification'] not in {'editor_fixable','deferable'} for f in current.review['findings']):
            if status.get('operator_work',{}).get('requests'):
                from whetstone.vnext_operator_decisions import finish_operator_pause
                finish_operator_pause(run,round_number=number)
            return run.status(round_number=number)
        run.admit_reviewed_round(decision_refs=decisions or ());continuation=False
    status=run.status(round_number=number)
    if _semantic_candidate_gate(run,status):return _execute_semantic(run,args,config,review,number,status,continuation)
    if status['processing_gate'] in {'complete','semantic_verification'} and not status['resume']['permitted']:return status
    editor=None if status['request_status'] in {'complete','valid_response','invalid_proposal','attempts_exhausted'} else _client('editor',review,config,args,run.store.root)
    run.run_round(round_number=number,client=editor,
                  decided_at=common.stamp(),continuation=continuation)
    status=run.status(round_number=number)
    if _semantic_candidate_gate(run,status) and status['processing_gate']=='semantic_verification' and status['request_status']=='not_started':
        return _execute_semantic(run,args,config,review,number,status,False)
    return status


def dispatch_proposal(args):
    root=Path(getattr(args,'run_root',None) or getattr(args,'root','.'))
    config_path=root/getattr(args,'config','orchestrator_config.yaml')
    flag=getattr(args,'vnext_input_package',None)
    decision_selector=getattr(args,'vnext_decisions',None)
    operator_command=args.command in {'vnext-decisions','vnext-decide'}
    from whetstone.vnext_semantic_operator_cli import COMMANDS as semantic_commands
    semantic_operator_command=args.command in semantic_commands
    marker=root/RUN_INPUT_PATH;existing=marker.exists() or marker.is_symlink()
    declared=existing
    if not declared and (root/'rounds').exists() and (root/'job_descriptor.json').is_file():
        try:
            packet=decode_json(confined_file(root,'job_descriptor.json').read_bytes())
            declared=packet.get('schema_version')=='job-descriptor-v2' and packet.get('editing_mode')=='proposal_only'
        except (ValueError,OSError,AttributeError):pass
    try:text=config_path.read_text() if config_path.is_file() else ''
    except (OSError,ValueError):
        if flag is None and not declared:return None
        text=''
    configured=bool(re.search(r'(?m)^\s*vnext_input_package\s*:|"vnext_input_package"\s*:',text))
    if not (flag is not None or declared or configured or operator_command or semantic_operator_command or decision_selector is not None):
        if getattr(args,'vnext_round',None) is None:return None
        _emit(args,_diagnostic(None,None,gate='admission',error=common.AdmissionError(
            'vnext_selection_conflict','--vnext-round requires a stored proposal run')));return 2
    job=None;suite=None;run=None;status=None;gate='admission'
    try:
        common.check(args.command in {'vnext-admit','live-phase1','status','resume','vnext-decisions','vnext-decide'}|semantic_commands,'vnext_gate_unavailable',
                     'command is unavailable for proposal runs',action='inspect_available_work')
        common.check(not (operator_command or semantic_operator_command or decision_selector is not None) or declared,'vnext_root_incompatible',
                     'operator work requires an already admitted proposal run')
        common.check(decision_selector is None or args.command in {'live-phase1','status'},'vnext_selection_conflict',
                     'new operator authorization is distinct from technical continuation')
        common.check(not (getattr(args,'overwrite',False) or getattr(args,'apply',False)
                         or getattr(args,'draft_after',None) or getattr(args,'extend_review_budget',None) is not None),
                     'vnext_selection_conflict','legacy overwrite/apply/budget controls cannot alter a proposal run')
        number=getattr(args,'vnext_round',None)
        common.check(number is None or (type(number) is int and number>0),'vnext_config_invalid',
                     'round selector must be a positive integer')
        common.check(declared or number in (None,1),'vnext_selection_conflict','a fresh package starts at round 1')
        config=common.config_packet(config_path)
        common.check('vnext_input_package' not in config or config['vnext_input_package'] is not None,
                     'vnext_config_invalid','package selector cannot be null')
        try:selected=_package_selector(args,config,config_path)
        except (ValueError,OSError,KeyError,TypeError) as exc:
            if isinstance(exc,common.AdmissionError):raise
            raise common.AdmissionError('vnext_config_invalid',str(exc)) from exc
        common.check(args.command!='vnext-admit' or not declared,'vnext_root_incompatible',
                     'proposal admission requires a genuinely fresh destination',action='new_isolated_root')
        if declared:
            run=open_proposal_run(root)
            reader,values=run._admission(run.store.read)._base(run.store.read)
            job=values['job'];suite=reader.suite;review=values['review'];authority=values['authority']
            descriptor_ref=run._record['descriptor'];review_ref=run._record['review_configuration']
            if selected:
                reference=run._record.get('launch_package')
                common.check(reference is not None and reference['hash']==sha256_bytes(selected[1]),
                             'vnext_selection_conflict','selected package differs from the retained launch package')
            settings_root=root
        else:
            common.check(selected is not None,'vnext_config_invalid','new proposal admission requires an input package')
            common.check(not root.exists() and not root.is_symlink(),'vnext_root_incompatible',
                         'proposal destination must not exist',action='new_isolated_root')
            package_path=selected[0]
            prepared=prepare_proposal_package(package_path.parent,manifest_path=package_path.name)
            selectors=decode_json(prepared.selectors_json);job=decode_json(prepared.artifacts['job_descriptor.json'])
            suite=validate_contract_suite(prepared.suite_path)
            review_ref=selectors['review_ref'];descriptor_ref=decode_json(selected[1])['job_descriptor']
            review=decode_json(prepared.artifacts[review_ref['path']]);authority=decode_json(prepared.artifacts[job['authority_map_path']])
            settings_root=prepared.source_root
        _settings(args,config,root=settings_root,job=job,review=review,authority=authority,
                  descriptor_ref=descriptor_ref,review_ref=review_ref)
        common.check(_qualified(job,suite),'vnext_gate_unavailable',
                     'proposal execution awaits exact suite and D8 release qualification',action='use_supported_implementation')
        semantic=_qualified_semantic(job,suite)
        followup=_qualified_followup(job,suite)
        common.check(not semantic_operator_command or followup,'vnext_gate_unavailable',
                     'semantic operator commands await exact follow-up suite qualification',action='use_supported_implementation')
        if followup:
            from whetstone.vnext_semantic_operator_cli import validate_operator_cli
            validate_operator_cli(suite)
        if semantic:
            from whetstone.vnext_semantic_workflow import SemanticProposalRun,validate_semantic_workflow
            validate_semantic_workflow(job,suite)
        if args.command=='resume':
            common.check(run is not None,'vnext_root_incompatible','resume requires an admitted run')
            common.check(getattr(args,'dry_run',False) or getattr(args,'continue_run',False),
                         'vnext_selection_conflict','proposal continuation requires --continue')
        if run is None:
            # Validate both required transports before creating authority; no process is invoked.
            for role in (('reviewer','editor','verifier') if semantic else ('reviewer','editor')):
                _client(role,review,config,args,prepared.source_root)
            if args.command=='status' or getattr(args,'dry_run',False):
                _emit(args,_diagnostic(job,suite,gate='admission'));return 0
            run=prepared.create(root)
        if followup:
            from whetstone.vnext_semantic_followup_workflow import SemanticFollowupRun
            run=SemanticFollowupRun(run.store,suite_path=run.suite_path)
        elif semantic:run=SemanticProposalRun(run.store,suite_path=run.suite_path)
        if args.command=='vnext-admit':
            _emit(args,_diagnostic(job,suite,gate='seed_initialization',admitted=True));return 0
        number=_number(run,args)
        if semantic_operator_command:
            from whetstone.vnext_semantic_operator_cli import execute_operator_command
            gate='semantic_verification'
            detail=execute_operator_command(run,args,round_number=number)
            status=run.status(round_number=number)
            _emit(args,{**_diagnostic(job,suite,gate=status['processing_gate'],admitted=True,status=status),**detail});return 0
        if operator_command:
            # Exact explicit inputs may complete an interrupted request write.
            # The producer validates seed/review/candidate preconditions before
            # writes; full status follows publication, including operator files.
            gate='finding_admission'
            from whetstone.vnext_operator_decisions import decision_context,prepare_operator_requests,submit_operator_responses
            locator=getattr(args,'options',None) if args.command=='vnext-decisions' else args.selections
            if locator is None:detail={'decision_context':decision_context(run,round_number=number)}
            else:
                path=Path(locator);packet=decode_json(confined_file(path.parent,path.name).read_bytes())
                common.check(isinstance(packet,dict) and packet.get('round_number')==number,'vnext_selection_conflict',
                             'operator command input differs from the selected round')
                if args.command=='vnext-decisions':
                    detail={'operator_requests':prepare_operator_requests(run,packet,dry_run=args.dry_run)}
                else:detail={'operator_selection':submit_operator_responses(run,packet,dry_run=args.dry_run)}
            status=run.status(round_number=number)
            _emit(args,{**_diagnostic(job,suite,gate=status['processing_gate'],admitted=True,status=status),**detail});return 0
        status=run.status(round_number=number);gate=status['processing_gate']
        decisions=None
        if decision_selector is not None:
            from whetstone.vnext_operator_decisions import selected_operator_decisions
            reference=common.local_ref(root,decision_selector)
            decisions=selected_operator_decisions(run,round_number=number,reference=reference)
            if _has_round(run,number):
                record=decode_json(run.store.read(run.selected_round(run.store.read,number)['path']))
                common.check(record['decision_refs']==decisions,'vnext_selection_conflict',
                             'selected decisions cannot replace the immutable admitted round')
        if args.command=='status' or getattr(args,'dry_run',False):
            _emit(args,_diagnostic(job,suite,gate=gate,admitted=True,status=status))
            return 0 if args.command=='status' or status['resume']['permitted'] else 2
        status=_execute(run,args,config,review,number,decisions)
        _emit(args,_diagnostic(job,suite,gate=status['processing_gate'],admitted=True,status=status))
        return 0 if (status['terminal_report'] or {}).get('terminal_state')=='PHASE_1_STABLE' else 2
    except (ValueError,OSError,KeyError,TypeError,RuntimeError) as exc:
        admitted_root=declared or run is not None
        error=exc if isinstance(exc,common.AdmissionError) else common.AdmissionError(
            'vnext_lineage_invalid' if admitted_root else getattr(exc,'code','vnext_input_invalid'),str(exc),
            terminal='HALTED_ARTIFACT_INVALID' if admitted_root else 'CONFIG_INVALID',
            action='inspect_evidence' if admitted_root else 'repair_configuration')
        # A failed writer/readback may have changed or invalidated the prior
        # projection. Do not report cached evidence as the current run state.
        _emit(args,_diagnostic(job,suite,gate=gate,admitted=run is not None,error=error));return 2
    finally:
        if run is not None:run.close()

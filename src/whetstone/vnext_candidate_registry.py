"""Unactivated candidate creation journal over the proposed D8 storage kernel.

The caller must supply descriptor/suite and committed-authority validation plus
immutable assessment inputs. No public mode, semantic verdict or promotion is
enabled here. Creation events, not preparation records, commit registration.
"""
from copy import deepcopy
from dataclasses import dataclass
import re

from whetstone import vnext_identity as ids
from whetstone.vnext_assembly import ASSEMBLER_VERSION, NORMALIZATION_VERSION, assemble_bytes
from whetstone.vnext_candidate_validation import assess_candidate
from whetstone.vnext_contracts import VNextSchemaRegistry, canonical_json_bytes, decode_json, require, sha256_bytes
from whetstone.vnext_inventory import INVENTORY_VERSION
from whetstone.vnext_proposals import PreparedProposal
from whetstone.vnext_section_lineage import candidate_section_map


@dataclass(frozen=True)
class RegistrationView:
    events: tuple
    orphans: tuple

    @property
    def latest(self):return deepcopy(self.events[-1]) if self.events else None


class CandidateAssemblyFailure(ValueError):
    """Deterministic failure before a candidate/map package exists."""
    def __init__(self, evidence):
        self.evidence = deepcopy(evidence)
        super().__init__(evidence['message'])


def _directory(round_number,candidate_id):
    return f'rounds/round-{round_number}/candidates/{candidate_id}'


def _creation_path(ordinal):return f'rounds/candidate_index/creation-{ordinal}.json'
def _ref(path,raw):return {'path':path,'hash':sha256_bytes(raw)}


class CandidateRegistry:
    """All writer methods reacquire exclusion and validate before allocating.

    validate_authority(read) must validate the admitted descriptor/suite and the
    current committed pointer/seed history. load_inputs(read, round, proposal)
    must load immutable authority, invariants, seed/map, committed base/map/unit
    inventory and exact operator bindings for that transaction. Both callbacks
    are required, read-only, and may not invoke clients or mutate authority.
    """
    def __init__(self,store,*,job,validate_authority,load_inputs):
        require(callable(validate_authority) and callable(load_inputs),'registration requires authority and input validators')
        VNextSchemaRegistry().validate(job,'job_descriptor_v2')
        require(canonical_json_bytes(job)==store.read_descriptor(),'registration descriptor differs from storage binding')
        require(job['editing_mode'] in {'proposal_only','verified_promotion'},'job mode prohibits candidate registration')
        require(job['contract_suite_version']!='vnext-contracts-1','frozen suite does not support candidate registration')
        for key,value in [('assembler_version',ASSEMBLER_VERSION),('normalization_version',NORMALIZATION_VERSION),
                          ('inventory_version',INVENTORY_VERSION),('parser_contract_version','markdown-atx-v1')]:
            require(job[key]==value,'registration descriptor algorithm differs: '+key)
        self.store=store;self.job=deepcopy(job);self.validate_authority=validate_authority;self.load_inputs=load_inputs
        self.schemas=VNextSchemaRegistry()

    def _json(self,path,schema):
        raw=self.store.read(path);value=decode_json(raw)
        require(raw==canonical_json_bytes(value),'noncanonical registration artifact',path)
        self.schemas.validate(value,schema)
        return value,raw

    def _listing(self,path):
        try:return self.store.list_directory(path)
        except FileNotFoundError:
            self.store.read_descriptor()  # Missing control state is not an empty journal.
            return ()

    def _material(self,round_number,proposal_id,*,persisted_directory=None):
        require(type(round_number) is int and round_number>=1,'invalid registration round')
        require(isinstance(proposal_id,str) and re.fullmatch(r'pro_[0-9a-f]{64}',proposal_id),'invalid registration proposal')
        inputs=self.load_inputs(self.store.read,round_number,proposal_id)
        required={'authority','invariants','seed','seed_map','base','base_map','base_inventory','review'}
        require(required<=inputs.keys() and inputs.keys()<=required|{'bindings','rules','plan_reference'},'invalid registration assessment inputs')
        inputs=dict(inputs);review=inputs.pop('review');plan_reference=inputs.pop('plan_reference',None)
        require(inputs['base_map']['job_id']==inputs['base_inventory']['job_id']==self.job['job_id'],
                'registration base lineage belongs to another job')
        require(inputs['base_map']['parser_contract_version']==self.job['parser_contract_version'],
                'registration base parser differs from descriptor')
        self.schemas.validate(review,'review_configuration_v1')
        require(sha256_bytes(canonical_json_bytes(review))==self.job['review_configuration_hash'],'registration role configuration changed')
        if plan_reference is None:
            plan,_=self._json(f'rounds/round-{round_number}/mutation_plan.json','mutation_plan_v2')
        else:
            require(isinstance(plan_reference,dict) and set(plan_reference)=={'path','hash'},'invalid transaction plan reference')
            plan,raw=self._json(plan_reference['path'],'mutation_plan_v3')
            require(sha256_bytes(raw)==plan_reference['hash'],'transaction plan reference changed')
            require(plan_reference['path']==f"rounds/round-{round_number}/transactions/{plan['transaction_id']}/mutation_plan.json",
                    'transaction plan path differs from its identity')
        prefix=f'rounds/round-{round_number}/proposals/{proposal_id}'
        patch,patch_raw=self._json(prefix+'/proposed_patch.json','patch_set_v2')
        require(patch['proposal_id']==proposal_id and ids.proposal_id(patch)==proposal_id,'registration proposal identity changed')
        require(plan['job_id']==patch['job_id']==self.job['job_id'],'registration inputs belong to another job')
        require(patch['editor']==review['editor'],'registered proposal differs from pinned Editor')
        payloads={}
        for operation in patch['operations']:
            reference=operation['payload']
            if reference['path'] is None:continue
            raw=self.store.read(prefix+'/'+reference['path'])
            require(sha256_bytes(raw)==reference['hash'],'registration payload hash differs')
            payloads[reference['path']]=raw
        proposal=PreparedProposal(patch,payloads)
        stage='assembly'
        try:
            assembled=assemble_bytes(base=inputs['base'],section_map=inputs['base_map'],plan=plan,proposal=proposal)
            stage='section_map'
            mapping=candidate_section_map(base=inputs['base'],base_map=inputs['base_map'],proposal=proposal,assembled=assembled)
        except ValueError as exc:
            evidence={'schema_version':'vnext-candidate-assembly-failure-v1','job_id':self.job['job_id'],
                'transaction_id':plan['transaction_id'],'proposal_id':proposal_id,'round_number':round_number,
                'base_draft_hash':sha256_bytes(inputs['base']),'mutation_plan_hash':sha256_bytes(canonical_json_bytes(plan)),
                'patch_set_hash':sha256_bytes(patch_raw),'stage':stage,'error_type':type(exc).__name__,'message':str(exc)}
            self.schemas.validate(evidence,'vnext_candidate_assembly_failure_v1')
            raise CandidateAssemblyFailure(evidence) from exc
        require(mapping['job_id']==self.job['job_id'] and mapping['draft_hash']==sha256_bytes(assembled.raw),
                'candidate section map differs from registered job/bytes')
        identifier=ids.candidate_id(plan['transaction_id'],sha256_bytes(inputs['base']),sha256_bytes(patch_raw),
                                    self.job['assembler_version'],self.job['normalization_version'])
        directory=_directory(round_number,identifier)
        map_path=directory+'/section_identity_map_candidate.json'
        candidate_raw=assembled.raw
        if persisted_directory is not None:
            require(directory==persisted_directory,'registration preparation is in a different candidate directory')
            candidate_raw=self.store.read(directory+'/candidate_unverified.md')
            persisted_map,_=self._json(map_path,'section_identity_map_v2')
            require(candidate_raw==assembled.raw and persisted_map==mapping,
                    'persisted candidate or section map differs from independent replay')
            mapping=persisted_map
        assessment=assess_candidate(job=self.job,plan=plan,proposal=proposal,candidate_bytes=candidate_raw,
            candidate_map=mapping,candidate_map_path=map_path,**inputs)
        require(assessment.report['candidate_id']==identifier,'assessment candidate identity differs')
        artifacts={directory+'/candidate_unverified.md':candidate_raw,map_path:canonical_json_bytes(mapping),
                   directory+'/preservation_report.json':canonical_json_bytes(assessment.report)}
        if assessment.inventory is not None:
            artifacts[directory+'/preservation_inventory_candidate.json']=canonical_json_bytes(assessment.inventory)
        return identifier,directory,patch,artifacts

    def _preparation(self,round_number,proposal_id,ordinal,previous,stamp,material):
        identifier,directory,patch,artifacts=material
        candidate=directory+'/candidate_unverified.md';mapping=directory+'/section_identity_map_candidate.json'
        initial_path=directory+'/disposition_events/event-1.json'
        initial={'schema_version':'candidate-disposition-event-v1','event_id':'','job_id':self.job['job_id'],
            'candidate_id':identifier,'candidate_creation_ordinal':ordinal,'event_ordinal':1,
            'event_kind':'candidate_created','previous_event_hash':None,'previous_disposition':None,
            'new_disposition':'CANDIDATE_UNVERIFIED','source_artifact_path':candidate,
            'source_artifact_hash':sha256_bytes(artifacts[candidate]),'recorded_at':stamp}
        initial['event_id']=ids.disposition_id(initial);self.schemas.validate(initial,'candidate_disposition_event_v1')
        artifacts={**artifacts,initial_path:canonical_json_bytes(initial)}
        event={'schema_version':'candidate-creation-event-v1','job_id':self.job['job_id'],'creation_event_id':'',
            'candidate_creation_ordinal':ordinal,'round_number':round_number,'transaction_id':patch['transaction_id'],
            'proposal_id':proposal_id,'candidate_id':identifier,'candidate_path':candidate,
            'candidate_hash':sha256_bytes(artifacts[candidate]),'candidate_section_identity_map_path':mapping,
            'candidate_section_identity_map_hash':sha256_bytes(artifacts[mapping]),
            'initial_disposition_event_path':initial_path,'initial_disposition_event_hash':sha256_bytes(artifacts[initial_path]),
            'previous_creation_event_hash':previous,'created_at':stamp}
        event['creation_event_id']=ids.creation_id(event)
        preparation={'schema_version':'candidate-registration-preparation-v1','creation_event':event,
                     'artifacts':[_ref(path,raw) for path,raw in sorted(artifacts.items())]}
        self.schemas.validate(preparation,'candidate_registration_preparation_v1')
        return preparation,artifacts

    def _validate_preparation(self,directory,*,ordinal,previous,event=None):
        preparation,_=self._json(directory+'/registration_preparation.json','candidate_registration_preparation_v1')
        pending=preparation['creation_event']
        require(event is None or pending==event,'preparation contradicts committed creation event')
        require(pending['candidate_creation_ordinal']==ordinal and pending['previous_creation_event_hash']==previous,
                'orphan or creation event claims a different ordinal/predecessor')
        material=self._material(pending['round_number'],pending['proposal_id'],persisted_directory=directory)
        require(material[1]==directory,'registration preparation is in a different candidate directory')
        expected,artifacts=self._preparation(pending['round_number'],pending['proposal_id'],ordinal,previous,pending['created_at'],material)
        require(preparation==expected,'registration preparation does not reproduce from immutable inputs')
        for path,raw in artifacts.items():
            require(self.store.read(path)==raw,'candidate registration artifact differs from independent replay',path)
        return pending,artifacts

    def _chain(self,through_ordinal=None):
        files={}
        for name,kind in self._listing('rounds/candidate_index'):
            if name.startswith('.vnext-tmp-'):continue
            match=re.fullmatch(r'creation-([1-9][0-9]*)\.json',name)
            require(match is not None and kind=='file','invalid creation journal entry')
            files[int(match[1])]=name
        require(sorted(files)==list(range(1,len(files)+1)),'creation journal has a gap or duplicate ordinal')
        if through_ordinal is not None:
            require(type(through_ordinal) is int and 1<=through_ordinal<=len(files),'invalid historical creation boundary')
            files={ordinal:name for ordinal,name in files.items() if ordinal<=through_ordinal}
        events=[];previous=None;seen=set()
        for ordinal in sorted(files):
            event,raw=self._json(_creation_path(ordinal),'candidate_creation_event_v1')
            require(event['job_id']==self.job['job_id'] and event['creation_event_id']==ids.creation_id(event),
                    'creation event job or identity differs')
            require(event['candidate_id'] not in seen,'duplicate candidate registration')
            directory=_directory(event['round_number'],event['candidate_id'])
            self._validate_preparation(directory,ordinal=ordinal,previous=previous,event=event)
            previous=sha256_bytes(raw);seen.add(event['candidate_id']);events.append(event)
        return events

    def _orphans(self,events):
        registered={_directory(e['round_number'],e['candidate_id']) for e in events};orphans=[]
        for name,kind in self._listing('rounds'):
            if not name.startswith('round-'):continue
            require(re.fullmatch(r'round-[1-9][0-9]*',name) and kind=='directory','invalid round directory')
            for identifier,candidate_kind in self._listing('rounds/'+name+'/candidates'):
                if identifier.startswith('.vnext-tmp-'):continue
                require(re.fullmatch(r'can_[0-9a-f]{64}',identifier) and candidate_kind=='directory','invalid candidate directory')
                directory='rounds/'+name+'/candidates/'+identifier
                if directory not in registered:orphans.append(directory)
        return tuple(sorted(orphans))  # Enumeration diagnoses; it never selects among claimants.

    def inspect(self):
        self.validate_authority(self.store.read)
        events=self._chain()
        return RegistrationView(tuple(events),self._orphans(events))

    def _reconcile(self,token,events):
        # A complete visible event may have lost its previous acknowledgement
        # before the directory/drive barrier. Locked readback plus exact replay
        # establishes durability before another ordinal or successful replay.
        for event in events:
            self.store.publish(token,_creation_path(event['candidate_creation_ordinal']),event)
        orphans=self._orphans(events)
        require(len(orphans)<=1,'multiple unresolved candidate orphans; cannot choose a registration')
        if not orphans:return events
        ordinal=len(events)+1;previous=sha256_bytes(canonical_json_bytes(events[-1])) if events else None
        pending,artifacts=self._validate_preparation(orphans[0],ordinal=ordinal,previous=previous)
        require(pending['candidate_id'] not in {e['candidate_id'] for e in events},'orphan duplicates a registered candidate')
        # Re-establish dependency durability before acknowledging recovery.
        for path,raw in artifacts.items():self.store.publish(token,path,raw)
        self.store.publish(token,_creation_path(ordinal),pending)
        return self._chain()

    def reconcile(self):
        with self.store.locked(self.validate_authority) as token:
            events=self._reconcile(token,self._chain())
            return RegistrationView(tuple(events),self._orphans(events))

    def register(self,*,round_number,proposal_id,created_at):
        with self.store.locked(self.validate_authority) as token:
            events=self._reconcile(token,self._chain())
            try:material=self._material(round_number,proposal_id)
            except CandidateAssemblyFailure as exc:
                # No candidate identity/disposition is fabricated when its map
                # cannot be built. Persistence errors remain storage failures.
                self.store.publish(token,f'rounds/round-{round_number}/proposals/{proposal_id}/assembly_failure.json',exc.evidence)
                raise
            existing=next((e for e in events if e['candidate_id']==material[0]),None)
            if existing is not None:
                require(self.store.read(existing['candidate_path'])==material[3][material[1]+'/candidate_unverified.md']
                    and self.store.read(existing['candidate_section_identity_map_path'])==material[3][material[1]+'/section_identity_map_candidate.json'],
                    'candidate identity collision across registration replay')
                return deepcopy(existing)
            ordinal=len(events)+1;previous=sha256_bytes(canonical_json_bytes(events[-1])) if events else None
            preparation,artifacts=self._preparation(round_number,proposal_id,ordinal,previous,created_at,material)
            self.store.publish(token,material[1]+'/registration_preparation.json',preparation)
            # Candidate bytes and map precede their initial disposition event.
            initial=preparation['creation_event']['initial_disposition_event_path']
            ordered=[path for path in artifacts if path!=initial]+[initial]
            for path in ordered:self.store.publish(token,path,artifacts[path])
            self._validate_preparation(material[1],ordinal=ordinal,previous=previous)
            self.store.publish(token,_creation_path(ordinal),preparation['creation_event'])
            return deepcopy(self._chain()[-1])

"""Synthetic inputs for a non-promoting proposal journey; no live admission."""
from copy import deepcopy
from pathlib import Path
import shutil

from whetstone.clients import canonicalize_reviewer_input
from whetstone import vnext_identity as ids
from whetstone.vnext_contracts import canonical_json_bytes, derive_job_id, sha256_bytes
from whetstone.vnext_sections import seed_section_map
from vnext_fixtures import Bundle, ACTOR


class MutationFixture:
    def __init__(self,root,suite):
        self.suite=suite;self.root=Path(root)/'run';self.root.mkdir()
        self.original=Bundle(Path(root)/'source',suite,mode='proposal_only')
        shutil.copytree(self.original.root/'inputs',self.root/'inputs')
        self.job=deepcopy(self.original.job);self.authority=deepcopy(self.original.authority)
        self.invariants=deepcopy(self.original.invariants);self.scope=None
        self.base=(self.root/'inputs/seed.md').read_bytes()
        self.feedback={'round_number':1,'profile':'structural_integrity','reviewer':ACTOR,
            'draft_hash':sha256_bytes(self.base),'feedback':[{'feedback_id':'fb-1','issue_id':'iss_'+'0'*16,
                'issue_fingerprint':'0'*64,'issue_type':'precision_gap','affected_sections':['queue'],
                'baseline_severity':'major','authority_impact':None,'determinism_impact':None,'rubric_impact':None,
                'normalized_severity':'major','invariant_violated':None,'claim':'The minimum interval needs clearer wording.',
                'evidence':'The target states at least 30 seconds.','recommended_change':'Clarify the same minimum interval.',
                'in_scope':True,'severity_rationale':None,'oscillation_key':None}]}
        self.hint={'feedback_id':'fb-1','classification':'editor_fixable','authority_scope_ids':['queue'],
                   'source_authority_binding_ids':[],'scope_surface_ids':[],'compatibility_change':'none','requested_effects':['clarification']}
        self.constraints={k:deepcopy(self.original.plan[k]) for k in ('allowed_operation_types','max_operations',
            'max_changed_sections','max_changed_normative_units','required_context_binding_ids')}
        self.rebind()

    def save(self,name,value):
        raw=value if isinstance(value,bytes) else canonical_json_bytes(value)
        p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
        return {'path':name,'hash':sha256_bytes(raw)}

    def rebind(self):
        digest=sha256_bytes(self.base)
        self.save('inputs/seed.md',self.base)
        self.job['seed_draft']['hash']=digest
        self.invariants['base_draft_hash']=digest
        self.feedback['draft_hash']=digest
        for binding in self.authority['bindings']:
            if binding['role']=='mutable_target':binding['content_hash']=digest
        for b in self.authority['bindings']:b['binding_id']=ids.binding_id(b)
        for a in self.invariants['assertions']:a['assertion_id']=ids.assertion_id(self.invariants['base_draft_hash'],a)
        ar=self.save('inputs/authority.json',self.authority);ir=self.save('inputs/invariants.json',self.invariants)
        self.job.update(authority_map_hash=ar['hash'],protected_invariants_hash=ir['hash'])
        if self.scope is not None:
            sr=self.save('inputs/scope.json',self.scope);self.job.update(scope_contract_path=sr['path'],scope_contract_hash=sr['hash'])
        self.job['job_id']=derive_job_id(self.job,self.suite.digest);self.job_ref=self.save('job_descriptor.json',self.job)
        mutable=next(b for b in self.authority['bindings'] if b['role']=='mutable_target')
        self.mapping=seed_section_map(self.base,self.job,mutable['binding_id'])
        self.map_ref=self.save('inputs/seed_sections.json',self.mapping)
        pointer=deepcopy(self.original.seed_pointer);pointer.update(job_id=self.job['job_id'],verified_draft_hash=digest,
            verified_section_identity_map_path=self.map_ref['path'],verified_section_identity_map_hash=self.map_ref['hash'])
        self.pointer_ref=self.save('rounds/verified_history/current-verified-0.json',pointer)
        self.save('rounds/current_verified.json',pointer)
        self.feedback=canonicalize_reviewer_input(self.feedback);self.feedback_ref=self.save('inputs/feedback.json',self.feedback)
        self.hint['source_authority_binding_ids']=[mutable['binding_id']]
        self.constraints['required_context_binding_ids']=[mutable['binding_id']]
        self.advice={'schema_version':'vnext-finding-advice-v1','job_id':self.job['job_id'],
            'base_draft_hash':sha256_bytes(self.base),'feedback':self.feedback_ref,
            'authority_map_hash':self.job['authority_map_hash'],'scope_contract_hash':self.job['scope_contract_hash'],
            'protected_invariants_hash':self.job['protected_invariants_hash'],'findings':[deepcopy(self.hint)]}
        self.advice_ref=self.save('inputs/advice.json',self.advice)

    def classification_arguments(self):
        return dict(feedback=self.feedback,feedback_ref=self.feedback_ref,advice=self.advice,job=self.job,
                    authority=self.authority,invariants=self.invariants,base=self.base,section_map=self.mapping,scope=self.scope)

"""Exact staged proposal inputs and explicit default mutation constraints.

The source package is read-only and never becomes the destination run. Public
capability routing remains separately gated by suite and D8 qualification.
"""
from copy import deepcopy
from dataclasses import dataclass
import os,stat,unicodedata
from pathlib import Path,PurePosixPath
from types import MappingProxyType

from whetstone.vnext_review_configuration import read as read_review_configuration
from whetstone.vnext_contracts import (CONTRACT_ROOT,VNextSchemaRegistry,canonical_json_bytes,decode_json,
    require,sha256_bytes,validate_contract_suite,validate_job_descriptor)
from whetstone.vnext_proposal_admission import initialize_proposal_storage,prepare_proposal_storage_inputs
from whetstone.vnext_sections import seed_section_map
from whetstone.vnext_validation import ArtifactReader,validate_bootstrap_reader

PACKAGE_PATH='inputs/proposal_package.json'
SEED_MAP_PATH='inputs/section_identity_map_seed.json'
RESERVED_INPUTS=frozenset({PACKAGE_PATH,SEED_MAP_PATH,'inputs/proposal_run.json'})
RESERVED_ROOTS=frozenset({'rounds','.git','.agents','.codex','.vnext-initializing','spec.md',
                         'draft_before.md','draft_after.md','run_state.json','orchestrator_config.yaml'})


class ProposalPackageError(ValueError):
    def __init__(self,code,message):
        super().__init__(message);self.code=code


def input_artifact_path(path):
    require(isinstance(path,str) and bool(path) and '\\' not in path and '\x00' not in path,'invalid package input path')
    parsed=PurePosixPath(path)
    require(bool(parsed.parts) and not parsed.is_absolute() and '..' not in parsed.parts
            and parsed.as_posix()==path,'package input path must be normalized and relative')
    folded=unicodedata.normalize('NFD',path).casefold()
    require(folded.split('/')[0] not in RESERVED_ROOTS and folded not in RESERVED_INPUTS
            and not any(p.casefold().startswith('.vnext-tmp-') for p in parsed.parts),'package input collides with runtime storage')
    return parsed.parts


class _Source:
    """Open-relative regular-file reads, with no symlink or FIFO traversal."""
    def __init__(self,root):
        root=Path(root)
        require(root.is_dir() and not root.is_symlink(),'package root must be a real directory')
        self.root=root.resolve();self.fd=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        info=os.fstat(self.fd);self.identity=(info.st_dev,info.st_ino);self.reads={}
    def read(self,path):
        parts=input_artifact_path(path);current=os.dup(self.fd)
        try:
            for part in parts[:-1]:
                child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=current)
                os.close(current);current=child
            fd=os.open(parts[-1],os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=current)
            try:
                require(stat.S_ISREG(os.fstat(fd).st_mode),'package input is not a regular file')
                chunks=[]
                while raw:=os.read(fd,65536):chunks.append(raw)
                raw=b''.join(chunks)
            finally:os.close(fd)
        finally:os.close(current)
        info=os.stat(self.root,follow_symlinks=False)
        require(stat.S_ISDIR(info.st_mode) and (info.st_dev,info.st_ino)==self.identity,'package root changed during reading')
        require(path not in self.reads or self.reads[path]==raw,'package input changed during preflight')
        self.reads[path]=raw;return raw
    def close(self):os.close(self.fd)


def validate_launch_package(reader,reference,*,descriptor_ref,review_ref,authority):
    package=reader.json(reference,'vnext_proposal_package_v1')
    require(package['job_descriptor']['hash']==descriptor_ref['hash'],'package selects a different descriptor')
    require(package['review_configuration']['hash']==review_ref['hash'],'package selects a different review configuration')
    reader.json(package['job_descriptor'],'job_descriptor_v2')
    read_review_configuration(reader, package['review_configuration'])
    packet=reader.json(package['mutation_constraints'],'vnext_mutation_constraints_v1')
    constraints=packet['constraints']
    allowed={b['binding_id'] for b in authority['bindings'] if b['role']!='excluded'}
    require(set(constraints['required_context_binding_ids'])<=allowed,'mutation constraints require unknown or excluded context')
    return deepcopy(constraints)


@dataclass(frozen=True)
class PreparedProposalPackage:
    source_root: Path
    manifest_path: str
    suite_path: Path
    suite_digest: str
    artifacts: object
    selectors_json: bytes
    input_paths: tuple

    def create(self,destination):
        """Revalidate exact source bytes and suite before creating any root."""
        require(not Path(destination).resolve().is_relative_to(self.source_root),
                'destination must be outside the read-only source package')
        current=prepare_proposal_package(self.source_root,manifest_path=self.manifest_path,suite_path=self.suite_path)
        require(current.suite_digest==self.suite_digest and current.artifacts==self.artifacts
                and current.selectors_json==self.selectors_json,'staged package changed after preflight')
        store,_=initialize_proposal_storage(destination,artifacts=dict(self.artifacts),suite_path=self.suite_path,
            input_paths=self.input_paths,**decode_json(self.selectors_json))
        from whetstone.vnext_proposal_run import ProposalRun
        try:return ProposalRun(store,suite_path=self.suite_path)
        except BaseException:store.close();raise


def prepare_proposal_package(root,*,manifest_path='proposal_package.json',suite_path=None):
    """Read only referenced inputs, derive seed authority, and validate all bytes."""
    source=_Source(root)
    stage='vnext_config_invalid'
    try:
        raw=source.read(manifest_path);package=decode_json(raw)
        require(raw==canonical_json_bytes(package),'package manifest must have exact canonical JSON bytes')
        schemas=VNextSchemaRegistry();schemas.validate(package,'vnext_proposal_package_v1')
        stage='vnext_descriptor_invalid'
        descriptor_raw=source.read(package['job_descriptor']['path']);job=decode_json(descriptor_raw)
        require(sha256_bytes(descriptor_raw)==package['job_descriptor']['hash'],'descriptor reference hash mismatch')
        require(descriptor_raw==canonical_json_bytes(job),'descriptor must have exact canonical JSON bytes')
        schemas.validate(job,'job_descriptor_v2')
        stage='vnext_suite_unsupported'
        from whetstone.vnext_registry import SUPPORTED_SUITES
        require(job['contract_suite_version'] in SUPPORTED_SUITES,'unknown proposal contract suite')
        path=Path(suite_path) if suite_path is not None else CONTRACT_ROOT/'suites'/(job['contract_suite_version']+'.json')
        suite=validate_contract_suite(path)
        stage='vnext_descriptor_invalid'
        validate_job_descriptor(job,suite)
        stage='vnext_input_invalid'
        reader,job,authority,invariants=validate_bootstrap_reader(ArtifactReader(None,suite,read=source.read),
            package['job_descriptor'],review_configuration_ref=package['review_configuration'])
        # Validate the manifest through the same pinned reader as stored runs.
        validate_launch_package(reader,{'path':manifest_path,'hash':sha256_bytes(raw)},
            descriptor_ref=package['job_descriptor'],review_ref=package['review_configuration'],authority=authority)
        mutable=next(b for b in authority['bindings'] if b['role']=='mutable_target')
        seed=reader.raw(job['seed_draft']);mapping=seed_section_map(seed,job,mutable['binding_id'])
        map_raw=canonical_json_bytes(mapping);map_ref={'path':SEED_MAP_PATH,'hash':sha256_bytes(map_raw)}
        pointer={'schema_version':'current-verified-pointer-v1','job_id':job['job_id'],'promotion_ordinal':0,
            'verified_draft_path':job['seed_draft']['path'],'verified_draft_hash':job['seed_draft']['hash'],
            'verified_section_identity_map_path':map_ref['path'],'verified_section_identity_map_hash':map_ref['hash'],
            'promoted_at':job['created_at']}
        for key in suite.registry.load('current_verified_pointer_v1')['required']:pointer.setdefault(key,None)
        pointer_raw=canonical_json_bytes(pointer)
        artifacts={p:content for p,content in source.reads.items() if p!=manifest_path}
        input_paths=tuple(sorted(artifacts))
        require(all(content==descriptor_raw for name,content in artifacts.items()
                    if unicodedata.normalize('NFD',name).casefold()=='job_descriptor.json'),
                'canonical descriptor path conflicts with another input')
        artifacts.update({'job_descriptor.json':descriptor_raw,PACKAGE_PATH:raw,SEED_MAP_PATH:map_raw,
            'rounds/current_verified.json':pointer_raw,'rounds/verified_history/current-verified-0.json':pointer_raw})
        selectors=dict(descriptor_ref={'path':'job_descriptor.json','hash':sha256_bytes(descriptor_raw)},
            review_ref=package['review_configuration'],seed_map_ref=map_ref,round_refs={},
            launch_package_ref={'path':PACKAGE_PATH,'hash':sha256_bytes(raw)})
        frozen,selectors,job=prepare_proposal_storage_inputs(artifacts=artifacts,suite_path=path,
                                                          input_paths=input_paths,**selectors)
        # Re-read all source inputs after constructing the complete snapshot.
        for name,content in tuple(source.reads.items()):require(source.read(name)==content,'package input changed during preflight')
        return PreparedProposalPackage(source.root,manifest_path,path.resolve(),suite.digest,
            MappingProxyType(frozen),canonical_json_bytes(selectors),input_paths)
    except (ValueError,OSError,KeyError,TypeError) as exc:
        raise ProposalPackageError(stage,str(exc)) from exc
    finally:source.close()

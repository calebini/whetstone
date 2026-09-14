"""Native read-only Editor transport for v2 patches, without automatic retries.

Descriptor capability admission belongs to the orchestrator. These adapters
reuse the repository's existing Codex/Claude process runners and never use the
legacy whole-draft Editor normalizer or artifact acceptance path.
"""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from whetstone.clients import _run_codex_exec, _run_claude_print
from whetstone.contracts import SCHEMA_DIR
from whetstone.vnext_contracts import VNextSchemaRegistry, require, sha256_bytes


PROVIDER_SCHEMA='vnext_proposal_response_v2.codex.schema.json'


def native_output_schema():
    return structural_output_schema('vnext_proposal_response_v2','Whetstone vNext Unit Proposal Response For Native Clients')


def structural_output_schema(schema_name,title):
    """Self-contained structural hint; canonical validation owns value rules."""
    registry=VNextSchemaRegistry()
    def project(node):
        if '$ref' in node:node={**registry._resolve_ref(node['$ref']),**{k:v for k,v in node.items() if k!='$ref'}}
        result={k:deepcopy(v) for k,v in node.items() if k in {'type','title','description','required','enum','additionalProperties'}}
        if 'const' in node:result['enum']=[node['const']]
        if 'enum' in result and all(isinstance(v,str) for v in result['enum']):result.setdefault('type','string')
        if 'properties' in node:result['properties']={key:project(value) for key,value in node['properties'].items()}
        if 'items' in node:result['items']=project(node['items'])
        if 'anyOf' in node:result['anyOf']=[project(value) for value in node['anyOf']]
        return result
    result=project(registry.load(schema_name))
    result['title']=title
    return result


class NativePatchProposalClient:
    role='editor'
    provider_schema=PROVIDER_SCHEMA
    canonical_schema='vnext_proposal_response_v2'
    schema_title='Whetstone vNext Unit Proposal Response For Native Clients'
    def __init__(self,*,review,command=None,cwd='.',timeout_seconds=360):
        VNextSchemaRegistry().validate(review,'review_configuration_v1')
        self.identity=deepcopy(review[self.role])
        require(self.identity['name'] in {'codex','claude-code'},'unsupported native patch Editor')
        require(type(timeout_seconds) is int and timeout_seconds>0,'patch Editor timeout must be a positive integer')
        self.command=command or {'codex':'codex','claude-code':'claude'}[self.identity['name']]
        require(isinstance(self.command,str) and bool(self.command.strip()),'patch Editor command is empty')
        self.cwd=Path(cwd).resolve();require(self.cwd.is_dir(),'patch Editor working directory is missing')
        self.timeout_seconds=timeout_seconds
        self._schema_bytes=(SCHEMA_DIR/self.provider_schema).read_bytes()
        require(json.loads(self._schema_bytes)==structural_output_schema(self.canonical_schema,self.schema_title),'native output schema does not reproduce from the transport contract')
        self.schema_hash=sha256_bytes(self._schema_bytes)
        self.last_telemetry=None

    @property
    def transport_binding(self):
        return {self.role:deepcopy(self.identity),'command':self.command,'cwd':str(self.cwd),
                'timeout_seconds':self.timeout_seconds,'output_schema_hash':self.schema_hash}

    def propose(self,prompt):
        self.last_telemetry=None
        require((SCHEMA_DIR/self.provider_schema).read_bytes()==self._schema_bytes,'native output schema changed after client configuration')
        runner={'codex':_run_codex_exec,'claude-code':_run_claude_print}[self.identity['name']]
        try:
            # Freeze the provider schema during the process invocation. Both
            # transports receive exact output shape, never mutable schema refs.
            with TemporaryDirectory(prefix='whetstone-native-patch-') as temporary:
                schema=Path(temporary)/self.provider_schema;schema.write_bytes(self._schema_bytes)
                result=runner(command=self.command,prompt=prompt,cwd=self.cwd,schema_path=schema,
                              model=self.identity['model'],timeout_seconds=self.timeout_seconds,raw=True)
            self.last_telemetry=result.telemetry
            envelope=result.telemetry.get('raw_envelope')
            if self.identity['name']=='claude-code' and isinstance(envelope,dict):
                require_error=(envelope.get('is_error') is True or envelope.get('error') is not None
                               or str(envelope.get('subtype','')).startswith('error'))
                if require_error:
                    error=RuntimeError('Claude returned a provider/process error envelope')
                    error.telemetry=result.telemetry
                    raise error
            require(isinstance(result.raw_response,bytes),'native patch transport did not retain response bytes')
            return result.raw_response
        except Exception as exc:
            self.last_telemetry=getattr(exc,'telemetry',self.last_telemetry)
            raise

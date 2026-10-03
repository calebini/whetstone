"""Shared real-CLI fixtures for the bounded Q1 recovery/operator pass."""
from contextlib import contextmanager
import sys
import unittest
from unittest.mock import patch

from whetstone.vnext_local_storage import LocalAuthorityStore
import test_vnext_verified_cli as cli
import test_vnext_verified_first_review_commands as first


class CommandCase(unittest.TestCase):
    setUpClass=cli.VerifiedCLITests.setUpClass
    setUp=cli.VerifiedCLITests.setUp
    patch=cli.VerifiedCLITests.patch
    qualify=cli.VerifiedCLITests.qualify
    save_config=cli.VerifiedCLITests.save_config
    clean=staticmethod(cli.VerifiedCLITests.clean)
    invoke=cli.VerifiedCLITests.invoke
    files=cli.VerifiedCLITests.files
    stage_phase2=cli.VerifiedCLITests.stage_phase2
    call=first.FirstReviewCommandTests.call
    inspect_readonly=first.FirstReviewCommandTests.inspect_readonly

    @contextmanager
    def lost_publication(self, predicate, *, after=True):
        publish=LocalAuthorityStore.publish;hits=[]
        def lost(store,token,path,value):
            if predicate(path) and not hits:
                if after:publish(store,token,path,value)
                hits.append(path);raise OSError('Q1 fixture publication interruption')
            return publish(store,token,path,value)
        with patch.object(LocalAuthorityStore,'publish',lost):yield hits
        self.assertEqual(len(hits),1)

    def readonly_resume(self,*args):
        before=self.files()
        with patch.object(LocalAuthorityStore,'acquire',side_effect=AssertionError('preview took fence')):
            code,result=self.call('resume',*args,'--dry-run')
        self.assertEqual(code,0,result);self.assertEqual(self.files(),before)
        return result

    def refuses(self,command,*args):
        before=self.files();code,result=self.call(command,*args)
        self.assertEqual(code,2,result);self.assertEqual(self.files(),before)
        return result

    def refuses_drift_at_fence(self, path, *args):
        target=self.root/path;raw=target.read_bytes();before=self.files()
        acquire=LocalAuthorityStore.acquire;hits=[]
        def changed(store,validate):
            if store.root==self.root.resolve() and not hits:
                target.write_bytes(raw+b' ');hits.append(path)
            return acquire(store,validate)
        try:
            with patch.object(LocalAuthorityStore,'acquire',changed):code,result=self.call('resume',*args)
            self.assertEqual(code,2,result);self.assertEqual(hits,[path])
        finally:target.write_bytes(raw)
        self.assertEqual(self.files(),before)


class Phase2CommandCase(CommandCase):
    def consumed_review(self, *, gap=False, mixed=False):
        import json
        from copy import deepcopy
        from whetstone.vnext_contracts import canonical_json_bytes,sha256_bytes
        from whetstone.vnext_verified_run import open_verified_run
        self.qualify()
        code,result=self.call('live-phase1');self.assertEqual(code,0,result)
        self.stage_phase2()
        if gap:
            with open_verified_run(self.root) as run:
                config=json.loads(run.store.read(self.config['vnext_phase2_configuration']['path']))
                config['target_mode']='permissive';raw=canonical_json_bytes(config)
                path='inputs/phase2/permissive-configuration.json'
                with run.store.locked(run._history().validate_authority) as token:run.store.publish(token,path,raw)
            self.config['vnext_phase2_configuration']=dict(path=path,hash=sha256_bytes(raw));self.save_config()
        def response(client,packet):
            inputs=json.loads(client.prompts[-1].splitlines()[-1])
            packet['draft_hash']=sha256_bytes(inputs['draft'].encode())
            for row in packet['feedback']:
                row.update(baseline_severity='minor' if gap else 'major',normalized_severity='minor' if gap else 'major',
                    authority_impact=None,determinism_impact=None,rubric_impact='minor' if gap else None,
                    invariant_violated=None,claim='Clarify the waiting description.',recommended_change='Clarify the wording.')
            if mixed:
                extra=deepcopy(packet['feedback'][0]);extra.update(feedback_id='fb_retained',
                    claim='Clarify the separate descriptive example.',baseline_severity='minor',normalized_severity='minor')
                extra['oscillation_key']['concern_type']='clarity_gap';packet['feedback'].append(extra)
            mutable=next(r for r in inputs['authority']['bindings'] if r['role']=='mutable_target')
            hints=[dict(feedback_id=r['feedback_id'],classification='deferable' if gap or i else 'editor_fixable',
                authority_scope_ids=mutable['authority_scopes'],source_authority_binding_ids=[mutable['binding_id']],
                scope_surface_ids=[],compatibility_change='none',requested_effects=['clarification'])
                for i,r in enumerate(packet['feedback'])]
            annotations=[]
            if gap:
                requirement=inputs['rubric_catalogue'][0]
                annotations=[dict(feedback_id=packet['feedback'][0]['feedback_id'],rubric_anchor=requirement['rubric_anchor'],
                    requirement_hash=requirement['requirement_hash'])]
            return canonical_json_bytes(dict(review=packet,rubric_findings=annotations,classifications=hints))
        self.phase2_reviewer.callback=response
        with open_verified_run(self.root) as run:
            config=json.loads(run.store.read(self.config['vnext_phase2_configuration']['path']))
            run.bind_phase2_entry(config);run.enter_phase2();run.prepare_phase2_declaration()
            run.bind_phase2_review(self.phase2_reviewer.transport_binding)
            result=run.run_phase2_review(client=self.phase2_reviewer);self.assertEqual(result.status,'complete')
            run.consume_phase2_result()
        self.patch('whetstone.live_phase2.LivePhase2Runner',side_effect=AssertionError('legacy executor'))
        return result

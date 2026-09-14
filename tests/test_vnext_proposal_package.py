from copy import deepcopy
import json,os,sys
import unittest

from whetstone.vnext_contracts import canonical_json_bytes,sha256_bytes
from whetstone.vnext_proposal_package import PACKAGE_PATH,prepare_proposal_package
from whetstone.vnext_proposal_run import open_proposal_run
import test_vnext_proposal_admission as fixtures
from test_vnext_review_requests import Reviewer
from test_vnext_proposal_requests import Client as Editor
from vnext_fixtures import STAMP


@unittest.skipUnless(sys.platform=='darwin','D8 first target is macOS/local APFS')
class ProposalPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.ProposalAdmissionTests.setUpClass()
    def setUp(self):
        self.f=fixtures.ProposalAdmissionTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        f=self.f.f;self.source=f.root;self.destination=self.f.root.with_name('packaged-run')
        self.constraint_ref=f.save('inputs/mutation-constraints.json',
            {'schema_version':'vnext-mutation-constraints-v1','constraints':f.constraints})
        self.package={'schema_version':'vnext-proposal-package-v1','job_descriptor':f.job_ref,
            'review_configuration':f.original.review_ref,'mutation_constraints':self.constraint_ref}
        self.save_package()
    def save_package(self):self.f.f.save('proposal_package.json',self.package)
    def prepare(self):return prepare_proposal_package(self.source,suite_path=self.f.path)
    def files(self,root):return {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}
    def create(self):
        run=self.prepare().create(self.destination);self.addCleanup(run.close);return run

    def test_preflight_is_read_only_and_copies_only_referenced_inputs(self):
        unrelated=self.source/'unrelated.txt';unrelated.write_text('Not part of the admitted package.')
        before=self.files(self.source);prepared=self.prepare()
        self.assertEqual(self.files(self.source),before);self.assertFalse(self.destination.exists())
        self.assertNotIn('unrelated.txt',prepared.artifacts)
        self.assertNotIn(self.f.f.feedback_ref['path'],prepared.artifacts)
        self.assertFalse(any('/candidates/' in path for path in prepared.artifacts))
        run=prepared.create(self.destination);self.addCleanup(run.close)
        self.assertEqual(self.files(self.source),before)
        self.assertEqual(run.store.read('job_descriptor.json'),(self.source/self.f.f.job_ref['path']).read_bytes())
        self.assertEqual(run.store.read(PACKAGE_PATH),canonical_json_bytes(self.package))
        self.assertEqual(run.store.read('rounds/current_verified.json'),run.store.read('rounds/verified_history/current-verified-0.json'))

    def test_packaged_limits_feed_live_reviewer_to_editor_without_implicit_grants(self):
        run=self.create();reviewer=Reviewer(self.f.f);result=run.review_phase(client=reviewer)
        self.assertEqual(result.review.status,'finding_admission')
        reference=run.admit_reviewed_round();record=json.loads(run.store.read(reference['path']))
        self.assertEqual(record['constraints'],self.f.f.constraints);self.assertEqual(record['decision_refs'],[])
        editor=Editor();report,_=run.run_round(round_number=1,client=editor,decided_at=STAMP)
        self.assertEqual((reviewer.calls,editor.calls),(1,1))
        self.assertEqual(report['latest_candidate']['disposition'],'CANDIDATE_UNVERIFIED')
        self.assertEqual(report['resume']['reason'],'vnext_gate_unavailable')
        self.assertEqual(run.store.read('rounds/current_verified.json'),run.store.read('rounds/verified_history/current-verified-0.json'))

    def test_sensitive_advice_still_requires_an_operator_response(self):
        run=self.create()
        def unsafe(packet):packet['classifications'][0]['requested_effects']=['weaken'];return canonical_json_bytes(packet)
        result=run.review_phase(client=Reviewer(self.f.f,unsafe))
        self.assertEqual(result.review.review['findings'][0]['classification'],'operator_decision_required')
        before=self.files(self.destination)
        with self.assertRaisesRegex(ValueError,'unresolved operator decisions'):run.admit_reviewed_round()
        self.assertEqual(self.files(self.destination),before)

    def test_no_limits_or_unknown_fields_fail_before_any_destination(self):
        original=deepcopy(self.package)
        for update in ('missing','unknown','null'):
            self.package=deepcopy(original)
            if update=='missing':del self.package['mutation_constraints']
            elif update=='unknown':self.package['editing_mode']='proposal_only'
            else:self.package['mutation_constraints']=None
            self.save_package()
            with self.subTest(update=update),self.assertRaises(ValueError):self.prepare()
            self.assertFalse(self.destination.exists())

    def test_changed_source_after_preflight_cannot_create_a_root(self):
        prepared=self.prepare();path=self.source/self.constraint_ref['path'];path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):prepared.create(self.destination)
        self.assertFalse(self.destination.exists())

    def test_existing_destination_or_child_of_source_cannot_be_upgraded(self):
        prepared=self.prepare();self.destination.mkdir();marker=self.destination/'legacy.txt';marker.write_text('Preserve.')
        before=self.files(self.destination)
        with self.assertRaises((FileExistsError,ValueError)):prepared.create(self.destination)
        self.assertEqual(self.files(self.destination),before)
        child=self.source/'child-run'
        with self.assertRaisesRegex(ValueError,'outside the read-only source package'):prepared.create(child)
        self.assertFalse(child.exists())

    def test_non_input_namespace_paths_and_descriptor_locators_are_preserved(self):
        f=self.f.f
        reference=f.save('metadata/descriptor.json',f.job);self.package['job_descriptor']=reference
        constraints=f.save('settings/mutation-limits.json',{'schema_version':'vnext-mutation-constraints-v1','constraints':f.constraints})
        self.package['mutation_constraints']=constraints;self.save_package()
        run=self.create()
        self.assertEqual(run.store.read(reference['path']),run.store.read('job_descriptor.json'))
        self.assertEqual(run.store.read(constraints['path']),(self.source/constraints['path']).read_bytes())

    def test_reserved_runtime_paths_symlinks_and_special_files_refuse(self):
        original=deepcopy(self.package)
        variants=[('rounds/imported-limits.json','runtime'),('Rounds/imported-limits.json','runtime'),
                  ('.VNEXT-TMP-limits.json','runtime'),
                  ('symlink-limits.json','symlink'),('fifo-limits.json','fifo')]
        for relative,kind in variants:
            target=self.source/relative;target.parent.mkdir(parents=True,exist_ok=True)
            if kind=='runtime':target.write_bytes((self.source/self.constraint_ref['path']).read_bytes())
            elif kind=='symlink':target.symlink_to(self.source/self.constraint_ref['path'])
            else:os.mkfifo(target)
            self.package=deepcopy(original);self.package['mutation_constraints']['path']=relative;self.save_package()
            with self.subTest(kind=kind),self.assertRaises((ValueError,OSError)):self.prepare()
            self.assertFalse(self.destination.exists())

    def test_unknown_or_excluded_required_context_cannot_be_packaged(self):
        packet={'schema_version':'vnext-mutation-constraints-v1','constraints':deepcopy(self.f.f.constraints)}
        packet['constraints']['required_context_binding_ids']=['bind_'+'f'*64]
        self.package['mutation_constraints']=self.f.f.save(self.constraint_ref['path'],packet);self.save_package()
        with self.assertRaisesRegex(ValueError,'unknown or excluded context'):self.prepare()
        self.assertFalse(self.destination.exists())

    def test_bound_context_is_copied_but_excluded_special_file_is_never_opened(self):
        f=self.f.f;context=f.save('references/context.md',b'Fictional background, not normative authority.\n')
        excluded='excluded-context.fifo';os.mkfifo(self.source/excluded)
        for reference,role in [(context,'informational_reference'),({'path':excluded,'hash':'f'*64},'excluded')]:
            f.authority['bindings'].append({'binding_id':'','path':reference['path'],'content_hash':reference['hash'],
                'role':role,'authority_scopes':['background'],'effective_horizon':'current','mutable':False,
                'may_introduce_requirements':False})
        f.rebind();self.package['job_descriptor']=f.job_ref;self.save_package()
        prepared=self.prepare();self.assertIn(context['path'],prepared.artifacts);self.assertNotIn(excluded,prepared.artifacts)
        packet={'schema_version':'vnext-mutation-constraints-v1','constraints':deepcopy(f.constraints)}
        packet['constraints']['required_context_binding_ids']=[f.authority['bindings'][-1]['binding_id']]
        self.package['mutation_constraints']=f.save(self.constraint_ref['path'],packet);self.save_package()
        with self.assertRaisesRegex(ValueError,'unknown or excluded context'):self.prepare()

    def test_non_normalized_seed_refuses_in_package_preflight(self):
        f=self.f.f;f.base+=b'\n\n';f.rebind();self.package['job_descriptor']=f.job_ref
        self.package['mutation_constraints']=f.save(self.constraint_ref['path'],
            {'schema_version':'vnext-mutation-constraints-v1','constraints':f.constraints})
        self.save_package()
        with self.assertRaisesRegex(ValueError,'seed must be normalized'):self.prepare()
        self.assertFalse(self.destination.exists())

    def test_reopening_cannot_rehash_limits_past_the_committed_reviewer_binding(self):
        run=self.create();run.review_phase(client=Reviewer(self.f.f));run.close()
        constraints=json.loads((self.destination/self.constraint_ref['path']).read_bytes())
        constraints['constraints']['max_operations']+=1
        raw=canonical_json_bytes(constraints);(self.destination/self.constraint_ref['path']).write_bytes(raw)
        package=deepcopy(self.package);package['mutation_constraints']['hash']=sha256_bytes(raw)
        raw_package=canonical_json_bytes(package);(self.destination/PACKAGE_PATH).write_bytes(raw_package)
        path=self.destination/'inputs/proposal_run.json';record=json.loads(path.read_bytes())
        record['launch_package']['hash']=sha256_bytes(raw_package);path.write_bytes(canonical_json_bytes(record))
        with open_proposal_run(self.destination,suite_path=self.f.path) as reopened:
            with self.assertRaisesRegex(ValueError,'claim differs'):reopened.admit_reviewed_round()

    def test_corrupt_package_or_limits_is_detected_on_every_read(self):
        run=self.create();path=self.destination/self.constraint_ref['path'];path.write_bytes(path.read_bytes()+b' ')
        reviewer=Reviewer(self.f.f)
        with self.assertRaisesRegex(ValueError,'hash mismatch'):run.review_phase(client=reviewer)
        self.assertEqual(reviewer.calls,0)

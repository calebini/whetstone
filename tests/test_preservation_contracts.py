from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from whetstone.contracts import SchemaRegistry, SchemaValidationError, validate_artifact
from whetstone.hashing import canonical_json_dumps, canonical_json_hash, draft_hash
from whetstone.preservation_contracts import (
    BRIDGE_SCHEMAS, BridgeContractError, complete_correspondence, decode_json, read_ref,
    validate_change_surface, validate_evidence_bindings, validate_evidence_kind,
    validate_proposal_bindings, validate_reference_graph, validate_surface_bindings, validate_untransformed_change,
)
from whetstone.preservation_inventory import build_inventory, match_inventory_units, sha256_bytes
from whetstone.scope import scope_contract_from_notes

CORPUS = Path(__file__).resolve().parents[1] / "examples/fixtures/preservation_bridge"
CATALOG = json.loads((CORPUS / "cases.json").read_text())
APPROVAL = {"approved": True, "approved_by": "fixture-operator", "approved_at": "2026-09-06T00:00:00Z"}
ISSUE = "iss_" + "a" * 16


class Packet:
    """Explicit scripted operator inputs, never live approval or production helpers."""
    def __init__(self, root, case=0, variant="clarified", **surface_changes):
        self.root = root
        self.case = CATALOG["cases"][case]
        self.raw = (CORPUS / self.case["base"]["path"]).read_bytes()
        self.after = (CORPUS / self.case["variants"][variant]["path"]).read_bytes()
        self.base_ref = self.save("seed.md", self.raw)
        self.inventory = build_inventory(self.raw, path="seed.md")
        self.inventory_ref = self.save("inventory.json", self.inventory)
        self.output_ref = self.save("output.md", self.after)
        self.output = build_inventory(self.after, path="output.md")
        self.output_inventory_ref = self.save("output-inventory.json", self.output)
        scope = scope_contract_from_notes("# Core Outcome\nPreserve test contracts.\n", approved=True)
        scope["approval"] = dict(APPROVAL)
        self.scope_ref = self.save("scope.json", scope)
        self.feedback = {"round_number":1,"profile":"consistency","draft_hash":draft_hash(self.raw.decode()),
            "reviewer":{"name":"fixture","version":"1","model":"fixture"},"feedback":[{
            "feedback_id":"fb-1","issue_id":ISSUE,"issue_fingerprint":"a"*64,"issue_type":"clarification",
            "affected_sections":["test"],"baseline_severity":"minor","authority_impact":None,
            "determinism_impact":None,"rubric_impact":None,"normalized_severity":"minor","invariant_violated":None,
            "claim":"Apply the stated fixture change.","evidence":"Exact toy scenario.","recommended_change":"Use the controlled proposal.",
            "in_scope":True,"severity_rationale":None,"oscillation_key":None}]}
        self.feedback_ref = self.save("feedback.json", self.feedback)
        self.surface = {"schema_version":"bounded-change-surface-v1","base_draft":self.base_ref,"inventory":self.inventory_ref,
            "scope_contract":self.scope_ref,"finding_sources":[{"artifact":self.feedback_ref,"feedback_ids":["fb-1"]}],
            "allowed_sections":[s["section_id"] for s in self.inventory["sections"]],
            "allowed_unit_ids":[u["unit_id"] for u in self.inventory["units"]],"frozen_sections":[],"frozen_unit_ids":[],
            "allowed_change_types":["clarify","reword"],"relocations":[],"deletion_allowed":False,"weakening_allowed":False,
            "authorized_deletion_unit_ids":[],"authorized_supersession_unit_ids":[],"max_changed_sections":None,
            "max_changed_normative_units":None,"approval":dict(APPROVAL),**surface_changes}
        self.surface_ref = self.save("surface.json", self.surface)
        self.admission = {"schema_version":"preservation-bridge-proposal-admission-v1","capability_version":"preservation-bridge-v1",
            "round_number":1,"attempt_number":1,"phase":"phase_1","profile":"consistency","origin":"editor","client_attempt_number":1,
            "base_draft":self.base_ref,"inventory":self.inventory_ref,"scope_contract":self.scope_ref,"allowed_change_surface":self.surface_ref,
            "finding_sources":self.surface["finding_sources"],"predecessor_report":None,"transform_policy_version":"bridge-version-transform-v1"}
        admission_ref = self.save("admission.json", self.admission)
        summary={"round_number":1,"draft_before_hash":draft_hash(self.raw.decode()),"draft_after_hash":draft_hash(self.after.decode()),
            "accepted_feedback_ids":["fb-1"],"modified_feedback_ids":[],"declined_feedback":[],"created_conflict_ids":[],
            "resolved_issue_ids":[ISSUE],"unresolved_issue_ids":[],"draft_after_content":self.after.decode()}
        summary_ref=self.save("summary.json",summary)
        self.proposal={"schema_version":"preservation-bridge-proposal-v1","admission":admission_ref,
            "raw_response":self.save("response.json",summary),"raw_proposal":self.output_ref,"materialized_draft":self.output_ref,
            "materialized_inventory":self.output_inventory_ref,"materialized_draft_hash":draft_hash(self.after.decode()),
            "transformations":[],"normal_round_evidence":{"effective_config":self.save("config.json",{"phase":"phase_1","profile":"consistency"}),
            "reviewer_feedback":[self.feedback_ref],"editor_summary":summary_ref}}
        self.proposal_ref=self.save("proposal.json",self.proposal)

    def save(self, name, value):
        raw=value if isinstance(value,bytes) else (canonical_json_dumps(value)+"\n").encode()
        (self.root/name).write_bytes(raw)
        return {"path":name,"sha256":sha256_bytes(raw)}

    def relation(self, scenario):
        check=next(c for c in self.case["checks"] if c["id"]==scenario)
        return [{"base_unit_id":self.inventory["units"][r["base_line"]-1]["unit_id"],
                 "successor_unit_ids":[self.output["units"][n-1]["unit_id"] for n in r["successor_lines"]],
                 "disposition":r["disposition"]} for r in check["relation"]]

    def evidence(self, relation, kind="attest_equivalence", types=None, additions=None):
        return {"schema_version":"bridge-operator-evidence-v2","kind":kind,"proposal":self.proposal_ref,
            "base_draft_sha256":self.base_ref["sha256"],"base_inventory_sha256":self.inventory_ref["sha256"],
            "scope_contract_sha256":self.scope_ref["sha256"],"allowed_change_surface_sha256":self.surface_ref["sha256"],
            "raw_proposal_sha256":self.output_ref["sha256"],"materialized_draft_sha256":self.output_ref["sha256"],
            "transformations_sha256":canonical_json_hash([]),"correspondence":relation,"added_unit_ids":additions or [],
            "change_types":types if types is not None else ["reword"],
            "finding_refs":[{"artifact_sha256":self.feedback_ref["sha256"],"feedback_id":"fb-1"}],
            "effect":"The exact controlled fixture effect.","rationale":"Explicit scripted operator adoption.","approval":dict(APPROVAL)}

    def context(self):
        return validate_surface_bindings(self.root,self.surface_ref)


class BridgeBindingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)

    def test_clarification_requires_evidence_then_preserves_total_coverage(self):
        p=Packet(self.root)
        with self.assertRaisesRegex(BridgeContractError,"incomplete"):
            complete_correspondence(p.inventory,p.output,evidence=[])
        e=p.evidence(p.relation("C01"));ref=p.save("evidence.json",e)
        self.assertEqual(validate_evidence_bindings(self.root,ref,proposal_ref=p.proposal_ref,surface_ref=p.surface_ref),e)
        relation,added=complete_correspondence(p.inventory,p.output,evidence=[e])
        self.assertEqual(len(relation),len(p.inventory["units"]))
        self.assertEqual(added,[])
        self.assertEqual(validate_change_surface(p.context(),p.output,correspondence=relation,additions=added,evidence=[e]),
                         {"changed_sections":1,"changed_normative_units":1})
        validate_reference_graph(self.root,p.proposal_ref,"preservation_bridge_proposal")
        self.assertEqual((self.root/"seed.md").read_bytes(),p.raw)

    def test_composed_contract_check_is_read_only_and_not_an_acceptance_marker(self):
        p=Packet(self.root);e=p.evidence(p.relation("C01"));ref=p.save("adopted.json",e)
        snapshot={f.name:f.read_bytes() for f in self.root.iterdir()}
        result=validate_untransformed_change(self.root,proposal_ref=p.proposal_ref,surface_ref=p.surface_ref,evidence_refs=[ref])
        self.assertEqual(result.changed_normative_units,1)
        self.assertEqual({f.name:f.read_bytes() for f in self.root.iterdir()},snapshot)
        self.assertFalse((self.root/"acceptance.json").exists())

    def test_frozen_schema_table_and_enum_losses_fail_despite_claimed_resolution(self):
        for variant in ("missing_field","missing_state","missing_enum"):
            with self.subTest(variant=variant), TemporaryDirectory() as tmp:
                p=Packet(Path(tmp),1,variant)
                matched=match_inventory_units(p.inventory,p.output)
                before={u["unit_id"]:u for u in p.inventory["units"]}
                after={u["unit_id"]:u for u in p.output["units"]}
                removed=[uid for uid in matched.unmatched_base if before[uid]["section_id"].endswith(
                    ('["Record Schema",1]]','["States",1]]','["Failure Codes",1]]'))]
                self.assertEqual(len(removed),1)
                old=next(uid for uid in matched.unmatched_base if before[uid]["section_id"].endswith('["Delivery",1]]'))
                new=next(uid for uid in matched.unmatched_output if after[uid]["section_id"].endswith('["Delivery",1]]'))
                p.surface.update(allowed_sections=[before[old]["section_id"]],allowed_unit_ids=[old],
                                 frozen_sections=[before[removed[0]]["section_id"]])
                surface_ref=p.save("bounded.json",p.surface);p.surface_ref=surface_ref
                equivalent=p.evidence([{"base_unit_id":old,"successor_unit_ids":[new],"disposition":"reworded_equivalent"}])
                unauthorized=p.evidence([{"base_unit_id":removed[0],"successor_unit_ids":[],"disposition":"authorized_deleted"}],
                                        "authorize_deletion",["delete"])
                refs=[p.save("equivalent.json",equivalent),p.save("deletion.json",unauthorized)]
                with self.assertRaisesRegex(BridgeContractError,"outside allowed surface|not permitted by acceptance surface"):
                    validate_untransformed_change(p.root,proposal_ref=p.proposal_ref,surface_ref=surface_ref,evidence_refs=refs)
                self.assertEqual((p.root/"seed.md").read_bytes(),p.raw)

    def test_ref_rejects_stale_bytes_absolute_escape_symlink_and_non_file(self):
        p=Packet(self.root)
        (self.root/"escape").symlink_to(self.root.parent)
        for path in (str(self.root/"seed.md"),"../anything","escape/anything","."):
            with self.subTest(path=path), self.assertRaises(BridgeContractError):
                read_ref(self.root,{"path":path,"sha256":p.base_ref["sha256"]})
        (self.root/"seed.md").write_bytes(p.raw.replace(b"\n",b"\r\n"))
        with self.assertRaisesRegex(BridgeContractError,"hash mismatch"): read_ref(self.root,p.base_ref)

    def test_duplicate_json_keys_nonfinite_overflow_and_surrogates_reject(self):
        for raw in (b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":1e999}',b'{"x":"\\ud800"}',b'\xff'):
            with self.subTest(raw=raw), self.assertRaises(BridgeContractError):decode_json(raw)

    def test_surface_rejects_stale_finding_and_frozen_descendant_and_orphan_permission(self):
        p=Packet(self.root)
        mutations=[{"frozen_sections":[p.inventory["sections"][1]["section_id"]]},
                   {"deletion_allowed":True}, {"weakening_allowed":True}, {"allowed_sections":["[]"]},
                   {"allowed_unit_ids":["u_"+"f"*64]}]
        for n,mutation in enumerate(mutations):
            bad={**p.surface,**mutation}
            with self.subTest(mutation=mutation), self.assertRaises(BridgeContractError):
                validate_surface_bindings(self.root,p.save(f"bad-{n}.json",bad))
        feedback={**p.feedback,"draft_hash":"0"*64};ref=p.save("stale-feedback.json",feedback)
        bad={**p.surface,"finding_sources":[{"artifact":ref,"feedback_ids":["fb-1"]}]}
        with self.assertRaisesRegex(BridgeContractError,"stale base"):
            validate_surface_bindings(self.root,p.save("bad-findings.json",bad))

    def test_evidence_binds_all_effect_inputs_and_unknown_fields_reject(self):
        p=Packet(self.root);e=p.evidence(p.relation("C01"))
        for field in ("base_draft_sha256","base_inventory_sha256","scope_contract_sha256","allowed_change_surface_sha256",
                      "raw_proposal_sha256","materialized_draft_sha256","transformations_sha256"):
            with self.subTest(field=field),self.assertRaises(BridgeContractError):
                validate_evidence_bindings(self.root,p.save("bad-evidence.json",{**e,field:"0"*64}),
                                           proposal_ref=p.proposal_ref,surface_ref=p.surface_ref)
        for mutation in ({"schema_version":"bridge-operator-evidence-v1"},{"base_unit_ids":[]},{"successor_unit_ids":[]}):
            with self.subTest(mutation=mutation),self.assertRaises(SchemaValidationError):
                validate_evidence_kind({**e,**mutation})

    def test_output_and_retained_round_evidence_cannot_be_substituted(self):
        p=Packet(self.root)
        for field in ("effective_config","editor_summary"):
            ref=p.proposal["normal_round_evidence"][field];path=self.root/ref["path"];original=path.read_bytes()
            path.write_bytes(original+b" ")
            with self.subTest(field=field),self.assertRaisesRegex(BridgeContractError,"hash mismatch"):
                validate_proposal_bindings(self.root,p.proposal_ref)
            path.write_bytes(original)
        raw=p.save("new-raw.md",p.after+b"Extra text.\n")
        with self.assertRaisesRegex(BridgeContractError,"unrecorded materialization"):
            validate_proposal_bindings(self.root,p.save("altered-proposal.json",{**p.proposal,"raw_proposal":raw}))

    def test_reflow_counts_one_base_unit_not_two_successors(self):
        p=Packet(self.root,2,"reflowed",max_changed_normative_units=1)
        e=p.evidence(p.relation("C07"));relation,added=complete_correspondence(p.inventory,p.output,evidence=[e])
        self.assertEqual(validate_change_surface(p.context(),p.output,correspondence=relation,additions=added,evidence=[e])["changed_normative_units"],1)
        wrong=deepcopy(e);wrong["correspondence"][0]["successor_unit_ids"].reverse()
        with self.assertRaisesRegex(BridgeContractError,"byte order"):complete_correspondence(p.inventory,p.output,evidence=[wrong])

    def test_duplicate_choice_can_be_adopted_but_conflicting_evidence_rejects(self):
        p=Packet(self.root,2,"one_duplicate_removed")
        self.assertTrue(match_inventory_units(p.inventory,p.output).ambiguous_base)
        entries=p.relation("C08")
        preserve=p.evidence(entries[:1],types=[])
        deletion=p.evidence(entries[1:],"authorize_deletion",["delete"])
        relation,_=complete_correspondence(p.inventory,p.output,evidence=[preserve,deletion])
        self.assertEqual(len(relation),len(p.inventory["units"]))
        conflicting=p.evidence([{**entries[0],"base_unit_id":entries[1]["base_unit_id"]}],types=[])
        with self.assertRaisesRegex(BridgeContractError,"conflicting"):
            complete_correspondence(p.inventory,p.output,evidence=[preserve,deletion,conflicting])

    def test_complete_supersession_group_passes_without_deletion_permission(self):
        p=Packet(self.root,6,"consolidated")
        entries=p.relation("C21")
        p.surface.update(allowed_change_types=["supersede"],authorized_supersession_unit_ids=[e["base_unit_id"] for e in entries],max_changed_normative_units=2)
        p.surface_ref=p.save("supersession-surface.json",p.surface)
        e=p.evidence(entries,"attest_supersession",["supersede"])
        relation,added=complete_correspondence(p.inventory,p.output,evidence=[e])
        counts=validate_change_surface(p.context(),p.output,correspondence=relation,additions=added,evidence=[e])
        self.assertEqual(counts["changed_normative_units"],2)
        with self.assertRaisesRegex(BridgeContractError,"connected supersession"):
            complete_correspondence(p.inventory,p.output,evidence=[{**e,"correspondence":entries[:1]},{**e,"correspondence":entries[1:]}])
        with self.assertRaisesRegex(BridgeContractError,"both successor and addition"):
            complete_correspondence(p.inventory,p.output,evidence=[e,p.evidence([],"attest_addition",["add"],entries[0]["successor_unit_ids"])])

    def test_supersession_connected_group_is_transitive(self):
        # Relation-only check: all three predecessors belong to one group via B.
        p=Packet(self.root)
        base=build_inventory(b"A MUST hold.\nB MUST hold.\nC MUST hold.\n",path="group-base.md")
        out=build_inventory(b"A and B MUST hold.\nB and C MUST hold.\n",path="group-output.md")
        a,b,c=[u["unit_id"] for u in base["units"]];x,y=[u["unit_id"] for u in out["units"]]
        entries=[{"base_unit_id":uid,"successor_unit_ids":successors,"disposition":"superseded"}
                 for uid,successors in [(a,[x]),(b,[x,y]),(c,[y])]]
        whole=p.evidence(entries,"attest_supersession",["supersede"])
        self.assertEqual(len(complete_correspondence(base,out,evidence=[whole])[0]),3)
        with self.assertRaisesRegex(BridgeContractError,"connected supersession"):
            complete_correspondence(base,out,evidence=[{**whole,"correspondence":entries[:2]},
                                                       {**whole,"correspondence":entries[1:]}])

    def test_relocation_requires_exact_authority_and_counts_both_sections(self):
        p=Packet(self.root,4,"moved");entry=p.relation("C15")[0];e=p.evidence([entry],types=["move"])
        relation,added=complete_correspondence(p.inventory,p.output,evidence=[e])
        destination=next(u for u in p.output["units"] if u["unit_id"]==entry["successor_unit_ids"][0])["section_id"]
        p.surface.update(allowed_change_types=["move"],max_changed_normative_units=1,max_changed_sections=2)
        p.surface_ref=p.save("move-no-map.json",p.surface)
        with self.assertRaisesRegex(BridgeContractError,"relocation"):
            validate_change_surface(p.context(),p.output,correspondence=relation,additions=added,evidence=[e])
        p.surface["relocations"]=[{"source_unit_ids":[entry["base_unit_id"]],"destination_section":destination,"change_type":"move"}]
        p.surface_ref=p.save("move-map.json",p.surface)
        self.assertEqual(validate_change_surface(p.context(),p.output,correspondence=relation,additions=added,evidence=[e]),
                         {"changed_sections":2,"changed_normative_units":1})
        p.surface["max_changed_sections"]=1;p.surface_ref=p.save("capped.json",p.surface)
        with self.assertRaisesRegex(BridgeContractError,"max_changed_sections"):
            validate_change_surface(p.context(),p.output,correspondence=relation,additions=added,evidence=[e])

    def test_semantic_weakening_of_verbatim_unit_needs_specific_evidence(self):
        p=Packet(self.root,3,"maintenance_exception")
        entry=p.relation("C12")[0]
        new_uid=p.output["units"][-1]["unit_id"]
        addition=p.evidence([],"attest_addition",["add"],[new_uid])
        weakening=p.evidence([entry],"authorize_weakening",["weaken"])
        relation,added=complete_correspondence(p.inventory,p.output,evidence=[addition,weakening])
        p.surface.update(allowed_change_types=["add"]);p.surface_ref=p.save("add-only.json",p.surface)
        with self.assertRaisesRegex(BridgeContractError,"change type"):
            validate_change_surface(p.context(),p.output,correspondence=relation,additions=added,evidence=[addition,weakening])
        p.surface.update(allowed_change_types=["add","weaken"],weakening_allowed=True);p.surface_ref=p.save("weakening.json",p.surface)
        self.assertEqual(validate_change_surface(p.context(),p.output,correspondence=relation,additions=added,evidence=[addition,weakening])["changed_normative_units"],2)
        wrong={**weakening,"kind":"attest_equivalence","change_types":["reword"]}
        with self.assertRaisesRegex(BridgeContractError,"contradicts"):validate_evidence_kind(wrong)


class BridgeSchemaTests(unittest.TestCase):
    def test_closed_schema_family_rejects_unknown_fields(self):
        registry=SchemaRegistry()
        def sample(schema):
            if "$ref" in schema: return sample(registry._resolve_ref(schema["$ref"]))
            if "const" in schema:return schema["const"]
            if "enum" in schema:return schema["enum"][0]
            if "anyOf" in schema:return sample(schema["anyOf"][0])
            kind=schema.get("type")
            if kind=="object":return {key:sample(value) for key,value in schema["properties"].items()}
            if kind=="array":return [sample(schema["items"]) for _ in range(schema.get("minItems",0))]
            if kind=="integer":return schema.get("minimum",0)
            if kind=="boolean":return False
            if kind=="null":return None
            if schema.get("format")=="date-time":return APPROVAL["approved_at"]
            if "pattern" in schema and "64" in schema["pattern"]:return ("u_" if schema["pattern"].startswith("u_") else "")+"a"*64
            return "example"
        for name in BRIDGE_SCHEMAS.values():
            with self.subTest(name=name):
                valid=sample(registry.load(name));registry.validate(valid,name)
                with self.assertRaises(SchemaValidationError):registry.validate({**valid,"unexpected":True},name)
                with self.assertRaises(SchemaValidationError):registry.validate({**valid,"schema_version":"unsupported-v0"},name)

    def test_array_constraints_distinguish_booleans_and_duplicate_objects(self):
        registry=SchemaRegistry()
        registry._validate([True,1],{"type":"array","uniqueItems":True},"$")
        for value,schema in [([],{"minItems":1}),([1,2],{"maxItems":1}),([1,1.0],{"uniqueItems":True}),
                             ([{"a":1,"b":2},{"b":2,"a":1}],{"uniqueItems":True})]:
            with self.subTest(value=value),self.assertRaises(SchemaValidationError):registry._validate(value,{"type":"array",**schema},"$")

    def test_admission_origin_nullability_and_integer_boolean_rules(self):
        with TemporaryDirectory() as tmp:
            p=Packet(Path(tmp));validate_artifact(p.admission,"preservation_bridge_proposal_admission")
            for change in ({"round_number":True},{"attempt_number":True},{"client_attempt_number":None},{"origin":"phase2_entry"},{"operator_evidence":[]}):
                with self.subTest(change=change),self.assertRaises(SchemaValidationError):
                    validate_artifact({**p.admission,**change},"preservation_bridge_proposal_admission")
            entry={**p.admission,"origin":"phase2_entry","phase":"phase_2","round_number":None,"profile":None,"client_attempt_number":None}
            validate_artifact(entry,"preservation_bridge_proposal_admission")
            with self.assertRaises(SchemaValidationError):validate_artifact({**entry,"phase":"phase_1"},"preservation_bridge_proposal_admission")


if __name__ == "__main__":unittest.main()

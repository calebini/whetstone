/* Explanatory documentation. The promoted spec family, contracts and runtime retain authority. */
(() => {
  const e=window.WhetstoneDiagrams.escape;
  const code=(label,value)=>`<div class="code-block"><div class="code-header"><span>${e(label)}</span><button class="copy-button" type="button">Copy ↗</button></div><pre><code>${e(value)}</code></pre></div>`;
  const table=(heads,rows)=>`<div class="table-scroll" tabindex="0" role="region" aria-label="Scrollable reference table"><table><thead><tr>${heads.map(h=>`<th scope="col">${h}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map(v=>`<td>${v}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  const sources=paths=>`<div class="source-list">${paths.map(p=>`<a class="source-pill" href="../../${p}">${e(p)} ↗</a>`).join('')}</div>`;
  const callout=(title,body,kind='')=>`<div class="callout ${kind}"><b>${title}</b><p>${body}</p></div>`;
  const section=(id,title,body)=>({id,title,body});
  const cli='PYTHONPATH=src python3 -m whetstone.cli';
  const next=(route,title)=>`<a class="chapter-next" href="#${route}"><div><small>CONTINUE THE FIELD GUIDE</small><b>${title}</b></div><span>→</span></a>`;
  const S='docs/specs/';
  const liveConfig=`spec_path: ./spec.md
history_path: ./spec.history.md
rounds_dir: ./rounds
declaration_path: ./convergence_declaration.md
workflow: standard
clients:
  reviewer:
    name: codex
    command: codex
    version: "REPLACE_WITH_INSTALLED_VERSION"
    model: "REPLACE_WITH_AVAILABLE_MODEL"
  editor:
    name: codex
    command: codex
    version: "REPLACE_WITH_INSTALLED_VERSION"
    model: "REPLACE_WITH_AVAILABLE_MODEL"
review:
  mode: horizontal
  profile_set: stateful_system
  budget_exhaustion_policy: hard
  profile_budgets:
    structural_integrity: 4
    determinism: 4
    operability: 4
convergence:
  enabled: true
  target_phase: final
  target_mode: strict
  rubric_profile: standard-v1
  rubric_source: builtin
  profile_budgets:
    convergence_strict_check: 4
    adversarial: 4
decision_points:
  enabled: true
  mode: end_of_cycle
timeouts:
  reviewer_seconds: 360
  editor_seconds: 900`;
  const pages={
    'getting-started':{number:'01',label:'Getting started',title:'Your first complete trail.',lead:'Start with a deterministic fixture to learn the artifacts. Then prepare an isolated live job with explicit scope and client access.',time:'8 MIN READ',sections:[
      section('prerequisites','What you need',`<p>Use a Whetstone checkout and <strong>Python 3.11 or later</strong>. The Python package declares no runtime dependencies. Run these examples from the repository root; <code>PYTHONPATH=src</code> uses that checkout directly. A virtual environment and editable installation are optional.</p>${code('OPTIONAL · LOCAL INSTALL',`python3 -m venv .venv\n. .venv/bin/activate\npip install -e .\n${cli} --help`)}<p>The fixture below calls no model. Live runs additionally require a supported, installed, authenticated Codex or Claude CLI, a model available to that client, and access to the selected inputs.</p>${sources(['pyproject.toml','src/whetstone/cli.py','src/whetstone/clients.py'])}`),
      section('first-run','Run the deterministic example',`<p>This fixture supplies scripted clean feedback. It demonstrates artifact plumbing and terminal evidence; it does not assess the quality of the sample specification.</p>${code('SHELL · FROM THE WHETSTONE REPOSITORY ROOT',`DEMO_ROOT="$(mktemp -d /tmp/whetstone-demo.XXXXXX)"
cat > "$DEMO_ROOT/spec.md" <<'SPEC'
# Demonstration Spec v0.1

## Purpose
A local demonstration of Whetstone fixture artifacts.

## Behavior
The tool returns the supplied message unchanged.
SPEC
printf '# History\\n' > "$DEMO_ROOT/spec.history.md"
${cli} fixture-script \\
  --root "$DEMO_ROOT" \\
  --script examples/fixtures/clean_convergence_script.json
ls "$DEMO_ROOT/rounds"
cat "$DEMO_ROOT/convergence_declaration.md"`)}${callout('Expected result','The CLI prints <code>terminal_state: CONVERGED</code> in its JSON response. Inspect the numbered round folders and declaration. Fixture mode is a deterministic demonstration; live run status and readiness should be read through <code>status</code>.','success')}${sources(['examples/fixtures/clean_convergence_script.json','src/whetstone/engine.py','src/whetstone/runner.py'])}`),
      section('isolated-root','Prepare an isolated live root',`<p>Choose a new directory for this attempt. Keep the source and run draft separate. A live Editor can replace the entire run draft, so retain the original and inspect the complete resulting diff.</p>${code('SHELL · REPLACE THE TWO PATHS',`SOURCE_SPEC="/absolute/path/to/MY_SPEC.md"
RUN_ROOT="/absolute/path/to/whetstone_runs/my-spec-001"
WORKFLOW="standard"
mkdir "$RUN_ROOT"
cp "$SOURCE_SPEC" "$RUN_ROOT/spec.md"
printf '# History\\n' > "$RUN_ROOT/spec.history.md"`)}<p>Create the parent directory first if needed. Using a new directory prevents accidental reuse of an existing run. Save the following as <code>$RUN_ROOT/orchestrator_config.yaml</code> and replace both client version and model placeholders with your installed client’s actual identity. The budgets are a bounded starting example, not a promise of convergence.</p>${code('YAML · LIVE CONFIGURATION TEMPLATE',liveConfig)}${callout('Public preservation is not active','The current public workflow uses full-draft editing. An approved scope contract and bounded instructions do not enforce non-destructive changes. The preservation bridge is under development; its public configuration remains unavailable. Use assessment-only workflows when rewriting is unacceptable.','warning')}${sources(['docs/OPERATOR_QUICKSTART.md','src/whetstone/config.py'])}`),
      section('live-run','Start a live review deliberately',`<p>Before an agent invokes nested clients, authorize the exact source copy, reference documents, rubric, scope contract, and feedback files that may be passed to the selected client. Confirm client session access and the intended budgets. These are model calls with the configured provider; the documentation site itself makes none.</p>${code('SHELL · AFTER CONFIGURATION AND CLIENT AUTHORIZATION',`${cli} live-phase1 --root "$RUN_ROOT"
${cli} status --root "$RUN_ROOT" --format text`)}<p>Proceed only when status reports <code>PHASE_1_STABLE</code> and <code>next_action: run_live_phase2</code>. Continue with the <a href="#sharpening">sharpening chapter</a> for Phase 2 and verification closeout.</p>${sources(['docs/OPERATOR_QUICKSTART.md','src/whetstone/status.py'])}${next('workflows','Choose the right workflow')}`)
    ]},
    workflows:{number:'02',label:'Choose a workflow',title:'Use the right amount of pressure.',lead:'Start with the question you need answered. A bounded assessment, technical stabilization, and a convergence declaration serve different purposes.',time:'5 MIN READ',sections:[
      section('choose','Choose by intended outcome',table(['QUESTION','WORKFLOW','WHAT IT CAN CONCLUDE'],[
        ['Do these changed or seed specs agree?','<code>audit-change</code>','Reviewer-only bounded audit; no source mutation or convergence verdict.'],
        ['Where will this spec need work?','<code>diagnostic-sweep</code>','One review per Phase 1 profile on the same draft; no Editor or Phase 2 admission.'],
        ['Can one client produce valid output?','<code>reviewer-smoke</code>','Reviewer output and plumbing check.'],
        ['Can this draft become technically stable?','<code>live-phase1</code>','Reviewer/Editor iteration across the configured profile set.'],
        ['Is this one concern now clean?','<code>live-focused-phase1</code>','Selected-profile stability only; not full readiness.'],
        ['Does the stable draft meet the target bar?','<code>live-phase2</code>','Rubric review, declaration and terminal outcome.'],
        ['Should the result replace the source?','<code>strop</code>','Review eligibility and diff; source write only with explicit apply and approval.'],
        ['Does one spec own too many boundaries?','<code>decompose</code>','Lossless extraction and governed ownership; not convergence.']
      ])+sources(['docs/OPERATOR_QUICKSTART.md','src/whetstone/cli.py'])),
      section('presets','Select a quality target',`<p>A <strong>workflow</strong> names the intended review bar. A <strong>rubric</strong> states the criteria. A <strong>profile set</strong> chooses review lenses and default budgets. A <strong>review mode</strong> decides how review and editing are ordered.</p>${table(['WORKFLOW','BUILT-IN RUBRIC','INTENDED USE'],[['exploratory','exploratory-v1','Early technical shaping.'],['mvp','mvp-v1','First useful build; requires approved scope.'],['standard','standard-v1','Normal spec sharpening.'],['governance','governance-v6','Deliberately heavier governance pressure.'],['custom','Explicit path and label','Named domain-specific criteria.']])}${callout('Workflow names are not automatic configuration presets','Changing only <code>workflow</code> or <code>--workflow</code> does not replace the configured rubric, target phase/mode, profile set, or budgets. Configure these together. The conventional targets are exploratory: <code>mid / permissive</code>; MVP: <code>mid / strict</code>; standard and governance: <code>final / strict</code>. A builtin rubric mismatch produces a manifest warning, not automatic correction. Inspect <code>rubric_manifest.json</code> for the actual rubric, target and profile settings.')}<p>Confirmed profile sets include <code>stateful_system</code>, <code>utility_mvp</code>, and <code>governance</code>. Read the configuration and rubric sources before customizing names.</p>${sources(['src/whetstone/rubrics.py','src/whetstone/vocabulary.py',S+'RUBRICS_PROFILES_AND_FEEDBACK_SPEC.md'])}`),
      section('diagnostic','Assess before editing',`${code('SHELL · REVIEWER-ONLY PROFILE SWEEP',`${cli} diagnostic-sweep \\
  --root "$RUN_ROOT" --reviewer-timeout-seconds 420`)}<p>Read <code>rounds/profile_sweep_report.md</code> and the per-round Reviewer feedback. Recommendations such as <code>start_phase_1</code>, <code>run_bounded_synthesis</code>, <code>run_vertical_phase_1</code>, or <code>manual_scope_review</code> guide your next job; they do not execute it.</p>${callout('Keep the conclusion narrow','A diagnostic sweep does not mark Phase 1 stable. An audit pass does not declare convergence. A focused recheck does not replace the full required profile set.')}${sources(['src/whetstone/diagnostic_sweep.py'])}${next('preparation','Scope and seed preparation')}`)
    ]},
    preparation:{number:'03',label:'Scope & seed specs',title:'Define the edge you want.',lead:'Make the source of authority, editable surface, and first useful outcome explicit before inviting more review pressure.',time:'7 MIN READ',sections:[
      section('intake','Turn scope notes into an approved contract',`<p>For MVP work, identify one core outcome, the in-scope surfaces, deferred work, and the depth needed for validation, schemas, reports, failures, and operations. Scope should express what is sufficient for this run.</p>${code('SHELL · GENERATE NOTES, THEN EDIT THEM',`${cli} intake --root "$RUN_ROOT" \\
  --template mvp --output "$RUN_ROOT/scope-notes.md"`)}<p>Read and edit the notes before the separate approval command:</p>${code('SHELL · AFTER REVIEWING THE SCOPE',`${cli} intake --root "$RUN_ROOT" \\
  --from-notes "$RUN_ROOT/scope-notes.md" --approve`)}<p>The contract is written to <code>rounds/intake/scope_contract.json</code>. Omitting <code>--approve</code> generates a draft that does not satisfy MVP preflight.</p>${sources(['docs/SCOPE_NOTES_GUIDE.md','src/whetstone/scope.py','contracts/schemas/scope_contract.schema.json'])}`),
      section('seed-bundles','Assess a family of seed specifications',`<p>A seed bundle is a <strong>job-design pattern</strong>: pass several small authority documents to <code>audit-change</code>. Ask whether they define one coherent, implementable boundary. Keep each document’s ownership visible; avoid flattening their authority into an unexplained combined draft.</p><p>Write a notes file with the headings below, then fill them with the specific shared boundary and exclusions. Paths in the command are examples to replace.</p>${code('MARKDOWN · audit-notes.md',`# Change Intent
Check whether the seed specifications define one implementable MVP.

# Expected Boundary
Describe ownership, shared contracts, and the first useful outcome.

# Specs To Check
List each document and its authority.

# Out Of Scope
List deferred capabilities and unrelated polish.`)}${code('SHELL · RUN FROM THE WHETSTONE CHECKOUT',`AUDIT_ROOT="/absolute/path/to/audits/seed-family-001"
${cli} audit-change \\
  --root "$AUDIT_ROOT" \\
  --notes /absolute/path/to/audit-notes.md \\
  --spec /absolute/path/to/POLICY_SPEC.md \\
  --spec /absolute/path/to/EVIDENCE_SPEC.md \\
  --profile consistency`)}<p>This is a live Reviewer call. Configure its client using the options from <code>audit-change --help</code> and authorize the listed inputs. The audit writes a brief, manifest, structured feedback, and JSON/Markdown report under <code>change_audit/</code>. The manifest records the source paths and hashes.</p>${table(['VERDICT','INTERPRETATION'],[['pass / pass_with_minor_clarification','The stated boundary passed the bounded audit.'],['needs_revision / blocked','Review findings; revise manually or design an isolated sharpening job.'],['audit_failed','The audit did not complete successfully; inspect the report before drawing conclusions.']])}<p>Audit artifacts are not Phase 1 or Phase 2 scheduler state. Do not feed an audit verdict directly into convergence admission.</p>${sources(['src/whetstone/change_audit.py','src/whetstone/cli.py','contracts/schemas/change_audit_report.schema.json'])}`),
      section('references','Preserve reference authority',`<p>For one editable spec that depends on an HLD, policy, or domain contract, configure file-backed reference context. Reference documents inform review while <code>spec_path</code> identifies the mutable draft.</p>${code('YAML · OPTIONAL CONFIGURATION FRAGMENT',`reference_context:
  files:
    architecture_hld:
      path: /absolute/path/to/hld-architecture.md
      role: architecture_authority
      required: true`)}<p>The context-pressure report measures draft, rubric, scope, and references. It is advisory: it does not trim context, alter scheduling, or accept or reject a run.</p>${sources(['src/whetstone/config.py','src/whetstone/context_pressure.py','docs/OPERATOR_QUICKSTART.md'])}${next('sharpening','Sharpen and converge')}`)
    ]},
    sharpening:{number:'04',label:'Sharpen & converge',title:'Make clarity repeatable.',lead:'Use profile review to stabilize the draft, then test the stable result against its chosen convergence target.',time:'7 MIN READ',sections:[
      section('phase1','Phase 1: technical stabilization',`${code('SHELL · BEGIN AND INSPECT',`${cli} live-phase1 --root "$RUN_ROOT"
${cli} status --root "$RUN_ROOT" --format text`)}<p>The <code>stateful_system</code> set uses structural integrity, determinism, and operability lenses. The orchestrator validates feedback, records Editor dispositions and changed drafts, tracks issues and churn, and applies profile stability and budget rules.</p>${table(['MODE','ROUND SHAPE','TRADEOFF'],[['horizontal','Profile-by-profile Reviewer/Editor loop.','Careful sequential sharpening; edits can require repeat review.'],['vertical','Separate profile reviews on one draft, then merged feedback and one consolidated Editor round.','Fewer Editor turns; still needs verification after editing.']])}<p>In <code>profile_used.yaml</code>, vertical profile rounds are <code>review_only</code>; merged Editor rounds are <code>consolidated_editor</code>. The diagrams show ordering, not concurrent model calls.</p>${sources(['src/whetstone/live_phase1.py','src/whetstone/live.py',S+'SCHEDULER_STATE_AND_RESUME_SPEC.md'])}`),
      section('budgets','Budget for verification, not just edits',`<p>Budgets are <strong>per profile</strong>. Three profiles with a budget of ten can create far more than ten round directories. A late edit may resolve known issues while leaving the draft unverified; a clean review of an older hash does not verify that edit.</p><p><code>hard</code> budget policy stops on failure to reach the target. <code>soft</code> can continue a Phase 1 sweep to collect residuals; <code>PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS</code> requires manual review and blocks Phase 2. Eligible verification-only closeout passes invoke Reviewers without changing the draft.</p>${callout('Readiness is explicit','Proceed when status reports <code>terminal_state: PHASE_1_STABLE</code> and <code>next_action: run_live_phase2</code>. “Accepted but unverified” is additional review work, not readiness.')}${sources(['docs/OPERATOR_QUICKSTART.md','src/whetstone/scheduler.py'])}`),
      section('focused','Recheck one profile',`<p>For an independent comparison, seed a new isolated root with the latest valid draft from the earlier run. Copy or recreate its configuration and applicable approved scope, then select a confirmed profile.</p>${code('SHELL · FOCUSED COMPARISON ROOT',`${cli} live-focused-phase1 \\
  --root "$FOCUSED_RUN_ROOT" \\
  --profile structural_integrity --budget 3`)}<p>The run writes ordinary round artifacts. <code>FOCUSED_PROFILE_STABLE</code> means that lens is clean for this draft; <code>ready_for_phase_2</code> remains false. This command can invoke an Editor. For assessment only, use a reviewer-only workflow.</p>${sources(['docs/OPERATOR_QUICKSTART.md','src/whetstone/live_phase1.py'])}`),
      section('phase2','Phase 2: the convergence decision',`${code('SHELL · AFTER FULL PHASE 1 STABILITY',`${cli} live-phase2 --root "$RUN_ROOT" --workflow "$WORKFLOW"
${cli} status --root "$RUN_ROOT" --format text`)}<p>Phase 2 uses the selected rubric identity, target phase and mode, required profiles, gap state, and declaration acceptance. Read <code>rounds/rubric_manifest.json</code> to confirm which rubric was used. For a custom rubric, provide an explicit path and label.</p>${code('SHELL · CUSTOM RUBRIC EXAMPLE',`${cli} live-phase2 --root "$RUN_ROOT" \\
  --workflow custom --rubric /absolute/path/to/domain-rubric.md \\
  --rubric-label "domain-readiness-v1"`)}<p>Successful live status reports <code>CONVERGED</code>, <code>next_action: review_or_apply_back</code>, and apply-back availability. Convergence is relative to this draft, target, rubric, and retained evidence.</p>${sources(['src/whetstone/live_phase2.py','src/whetstone/declaration.py',S+'PHASE2_CONVERGENCE_AND_DECLARATION_SPEC.md'])}`),
      section('closeout','Close remaining verification debt',`<p>If an existing Phase 2 run stopped as <code>TARGET_NOT_REACHED</code> with zero unresolved blockers, majors, and rubric gaps, the explicit closeout path may be eligible. It verifies the current draft across remaining required profiles without an Editor.</p>${code('SHELL · ELIGIBLE EXISTING PHASE 2 RUN ONLY',`${cli} live-phase2 --root "$RUN_ROOT" \\
  --workflow "$WORKFLOW" --closeout-existing`)}<p>It appends review-only rounds and preserves earlier terminal reports; when a previous failure state is replaced, <code>rounds/superseded_terminal_reports.json</code> records that relationship. This is not a general resume command for Phase 2 timeouts.</p>${sources(['src/whetstone/live_phase2.py','docs/OPERATOR_QUICKSTART.md'])}${next('evidence','Read the evidence')}`)
    ]},
    evidence:{number:'05',label:'Read the evidence',title:'The trail is part of the product.',lead:'A final draft answers “what.” The run record lets you ask “why,” “verified against what,” and “what remains unresolved.”',time:'6 MIN READ',sections:[
      section('reading-order','Start with status',`${code('SHELL · ROUTINE READBACK',`${cli} status --root "$RUN_ROOT" --format text`)}<ol><li>Read terminal state, next action, readiness and resume eligibility.</li><li>Inspect <code>rounds/run_state.json</code> for current lineage and profile state.</li><li>Read the applicable technical, convergence, validation, oscillation, or conflict report.</li><li>Read the latest valid Reviewer feedback and Editor summary alongside their before/after draft snapshots.</li><li>Review decisions, checkpoints, and any strop review before source mutation.</li></ol><p>Partial rounds can have missing files. Use <code>missing_round_artifacts</code> and the terminal report to identify what was actually persisted.</p>${sources(['src/whetstone/status.py','docs/OPERATOR_QUICKSTART.md'])}`),
      section('artifact-map','Map files to questions',table(['ARTIFACT','QUESTION IT ANSWERS'],[
        ['<code>rounds/run_state.json</code>','Which draft hash and phase does the controller recognize?'],
        ['<code>rounds/round-N/draft_before.md</code><br><code>draft_after.md</code>','What exact text entered and left this round?'],
        ['<code>reviewer_feedback.json</code>','Which claims, affected sections, severities, and issue identities were recorded?'],
        ['<code>editor_summary.json</code>','Which feedback IDs did the Editor accept, modify, decline, or claim to resolve?'],
        ['<code>unresolved_issues.json</code>','What remains open, and what blocks acceptance?'],
        ['<code>profile_used.yaml</code><br><code>prompt_snapshot.json</code>','Which lens, round kind, prompt, and client identity explain the round?'],
        ['<code>rounds/rubric_manifest.json</code>','Which builtin or custom rubric and hash were selected?'],
        ['<code>rounds/decision_register.json</code><br><code>rounds/decision_summary.md</code>','What product, scope, authority, or contract decisions emerged?'],
        ['<code>rounds/round-N/operator_decision_checkpoint.json</code>','Which decision checkpoint belongs to this round?'],
        ['<code>convergence_declaration.md</code>','What convergence was declared for the selected target and evidence?'],
        ['<code>rounds/apply_back_review.md</code>','Is the final draft eligible, and what would change in the source?']
      ])+sources([S+'ARTIFACTS_VALIDATION_AND_TELEMETRY_SPEC.md','src/whetstone/artifacts.py'])),
      section('identity','Follow identity and hashes',`<p>Whetstone computes issue fingerprints and IDs, severity normalization, and other deterministic primitives. It validates artifacts against repository contracts instead of treating prose or process exit codes as proof.</p><p>Compare <code>run_state.current_draft_hash</code> with the current root draft. The latest folder can be partial or rejected. An Editor’s resolution list does not prove that the new text passes required review profiles.</p>${callout('When hashes disagree','A <code>root_draft_hash_mismatch</code> warning means the root draft is outside the accepted chain. Preserve the evidence; restore the accepted snapshot, seed a new job, or perform explicit reconciliation before continuation.','warning')}${sources(['src/whetstone/identity.py','src/whetstone/hashing.py','src/whetstone/evaluation.py','src/whetstone/status.py'])}`),
      section('decisions','Decisions and observability',`<p>Decision summaries highlight requirement strength, authority boundaries, scope, enums, and error-code changes. With <code>end_of_cycle</code> mode, decisions are collected for review; their presence is not automatic permission to apply them.</p><p>Use root and per-round <code>context_pressure_report.md</code> to understand input size and referenced context. Read available client telemetry for actual usage. Rough token estimates are advisory and cannot substitute for provider usage data.</p>${sources(['src/whetstone/decisions.py','src/whetstone/context_pressure.py','contracts/schemas/client_telemetry.schema.json'])}${next('operations','Recover and apply back')}`)
    ]},
    operations:{number:'06',label:'Recover & apply back',title:'Stop clearly. Continue deliberately.',lead:'Preserve the run, diagnose the failing boundary, and choose only a continuation supported by its state and hashes.',time:'8 MIN READ',sections:[
      section('states','Interpret terminal states',table(['STATE','NEXT STEP'],[
        ['PHASE_1_STABLE','Proceed to Phase 2 using the configured target.'],['FOCUSED_PROFILE_STABLE','Use as evidence for this profile only; no full Phase 2 readiness.'],['CONVERGED','Review the draft, declaration, decisions and strop diff.'],['TARGET_NOT_REACHED','Read the phase failure report; distinguish remaining issues from verification debt.'],['PHASE_1_SWEEP_COMPLETE_WITH_RESIDUALS','Read residual profile status; manual review, not Phase 2.'],['HALTED_CLIENT_TIMEOUT','Read status for a supported resume command.'],['HALTED_ARTIFACT_INVALID','Inspect role, report and validation errors; only certain Editor failures can resume.'],['HALTED_OSCILLATION / HALTED_CONFLICT','Read the corresponding report; resolve the cause before a new attempt.'],['PAUSED_DECISION','Operator decision is required; technical retry cannot supply approval.'],['CONFIG_INVALID','Correct the configuration before model execution.']
      ])+sources(['docs/OPERATOR_QUICKSTART.md','src/whetstone/termination.py','src/whetstone/status.py'])),
      section('resume','Preview a supported recovery',`${code('SHELL · INSPECT, PREVIEW, THEN CONTINUE',`${cli} status --root "$RUN_ROOT" --format text
${cli} resume --root "$RUN_ROOT" --dry-run --continue
# Continue only when the dry run reports resumable.
${cli} resume --root "$RUN_ROOT" --continue`)}<p>Public resume supports Phase 1 Reviewer timeouts, Editor timeouts after validated Reviewer feedback, certain Editor artifact failures after valid feedback, and explicit Phase 1 budget extension. It does not support Reviewer artifact-validation failures, arbitrary malformed roots, changed source hashes, manually edited run drafts, or generic Phase 2 timeouts.</p>${code('SHELL · PREVIEW ADDITIONAL PHASE 1 BUDGET',`${cli} resume --root "$RUN_ROOT" \\
  --extend-review-budget 3 --dry-run
# If eligible, append rounds without --dry-run.
${cli} resume --root "$RUN_ROOT" --extend-review-budget 3`)}<p>Extension preserves earlier artifacts, appends round directories, and records <code>budget_extensions</code>. In vertical mode it adds review cycles with consolidated editing as needed.</p>${sources(['src/whetstone/resume.py','docs/OPERATOR_QUICKSTART.md'])}`),
      section('troubleshooting','Troubleshoot by evidence',`<details><summary>The nested client cannot access its session files</summary><p>This is infrastructure failure before semantic review. Correct client session access and execution authorization. Preserve the failed root and start a clean isolated attempt; do not interpret the access failure as spec feedback.</p></details><details><summary>The Editor timed out while writing a large draft</summary><p>Read status and preview resume. If supported and hashes match, increase <code>--editor-timeout-seconds</code> on the resume command. Do not treat partial output as the accepted result.</p></details><details><summary>The root draft no longer matches run state</summary><p>Inspect the latest accepted draft snapshot and current_draft_hash. Preserve both versions. Restore the accepted snapshot, seed a new root, or explicitly reconcile the change before continuing. Do not casually override hash guards.</p></details><details><summary>The run seems to converge too quickly</summary><p>Inspect rubric identity, target, profile budgets, clean profile hashes, latest Reviewer feedback, and declaration. Fixture success and a thin audit are not live convergence evidence.</p></details><details><summary>Strop refuses to write</summary><p>Read <code>rounds/apply_back_review.json</code> if present and the command diagnostic. Check terminal eligibility, source hash, final hash against run state, and text hygiene. Do not use override flags as routine recovery.</p></details>${sources(['docs/OPERATOR_QUICKSTART.md','src/whetstone/resume.py','src/whetstone/apply_back.py'])}`),
      section('apply-back','Review and apply back',`<p>Read the final draft, history, declaration, decision summary, and run state. Generate a source diff without writing the source:</p>${code('SHELL · DRY-RUN STROP',`${cli} strop --source "$SOURCE_SPEC" --run-root "$RUN_ROOT"`)}<p>Read <code>$RUN_ROOT/rounds/apply_back_review.md</code>. Verify eligibility and inspect the entire diff, including removals. The source-baseline guard is optional: copy <code>source_before_hash</code> from the reviewed JSON report into <code>REVIEWED_SOURCE_HASH</code> and pass it explicitly. Without <code>--expected-source-hash</code>, strop does not compare the source to a supplied baseline. Keep the source unchanged during the run. After human review:</p>${code('SHELL · EXPLICIT SOURCE WRITE',`${cli} strop --source "$SOURCE_SPEC" \\
  --run-root "$RUN_ROOT" --expected-source-hash "$REVIEWED_SOURCE_HASH" \\
  --apply --approve
${cli} status --root "$RUN_ROOT" --format text`)}<p><code>apply-back</code> is the legacy alias. Strop writes the selected source file; the source repository owner reviews and commits that change separately. A converged run is not a blanket preservation guarantee.</p>${sources(['src/whetstone/apply_back.py','docs/OPERATOR_QUICKSTART.md'])}${next('decomposition','Decompose an authority-dense spec')}`)
    ]},
    decomposition:{number:'07',label:'Decompose a spec',title:'Give each boundary a home.',lead:'Split an overloaded source into a coordinating spec and owned leaves, preserving normative content and provenance.',time:'5 MIN READ',sections:[
      section('when','When decomposition fits',`<p>Use decomposition when one spec owns several independent subsystems, interfaces, or artifact families, or when people repeatedly ask which section owns a decision. This is a copy-first extraction workflow. It reorganizes authority; it does not rewrite requirements or declare convergence.</p>${callout('Whetstone’s own spec family','The promoted entry point is <code>docs/specs/WHETSTONE_COORDINATING_SPEC.md</code>. Each leaf owns its surface. The original <code>spec.md</code> remains the pre-decomposition source snapshot.')}${sources(['docs/decomposition/decomposition_manifest.json',S+'WHETSTONE_COORDINATING_SPEC.md'])}`),
      section('plan','Inventory and map ownership',`${code('SHELL · INVENTORY A SOURCE',`${cli} decompose plan --source "$SOURCE_SPEC" \\
  --output-dir /absolute/path/to/decomposition/inventory`)}<p>Inspect <code>decomposition_map_template.json</code>: it contains the source hash, valid enum values, and exact extractable units. Copy it to a map file and fill target ownership using that inventory.</p>${code('SHELL · VALIDATE THE FILLED MAP',`${cli} decompose plan --source "$SOURCE_SPEC" \\
  --map /absolute/path/to/decomposition/map.json \\
  --output-dir /absolute/path/to/decomposition`)}${sources(['src/whetstone/decomposition.py','docs/OPERATOR_QUICKSTART.md'])}`),
      section('promote','Approve, extract, audit, promote',`<p>Replace these paths with one consistent plan and target tree. Approval binds the source and plan hashes. Inspect the generated plan before approving it, and inspect the coverage report before promotion.</p>${code('SHELL · REVIEWED DECOMPOSITION PLAN',`DECOMP_DIR="/absolute/path/to/decomposition"
TARGET_TREE="/absolute/path/to/target-repository"
${cli} decompose approve \\
  --plan "$DECOMP_DIR/decomposition_plan.json" \\
  --source "$SOURCE_SPEC" --approved-by "$USER"
${cli} decompose extract \\
  --plan "$DECOMP_DIR/decomposition_plan.json" \\
  --source "$SOURCE_SPEC" --output-dir "$TARGET_TREE"`)}<p>Use the actual emitted manifest path reported by extraction. Audit coverage, hashes, provenance headers, unmapped units, and duplicated authority:</p>${code('SHELL · AUDIT BEFORE PROMOTION',`MANIFEST="/absolute/path/to/emitted/decomposition_manifest.json"
${cli} decompose audit --manifest "$MANIFEST" --source "$SOURCE_SPEC"
# After a successful audit and review of the generated family:
${cli} decompose promote --manifest "$MANIFEST" --accepted-by "$USER"`)}<p>Promotion marks the audited family authoritative. It does not delete the original, prove convergence, or authorize unrelated content changes.</p>${sources(['src/whetstone/decomposition.py',S+'SCOPE_INTAKE_AND_DECISIONS_SPEC.md'])}${next('architecture','Explore the ten architecture plates')}`)
    ]}
  };
  const commands=[
    ['fixture-script','Run scripted multi-round fixture artifacts without models.','Fixture','getting-started'],
    ['intake','Generate notes or an approved scope contract.','Prepare','preparation'],
    ['audit-change','Reviewer-only bounded cross-spec or seed-family audit.','Assess','preparation'],
    ['diagnostic-sweep','Review each configured Phase 1 profile without an Editor.','Assess','workflows'],
    ['reviewer-smoke','Check one Reviewer output and client plumbing.','Assess','workflows'],
    ['live-phase1','Stabilize the draft across required technical profiles.','Edit','sharpening'],
    ['live-focused-phase1','Target one profile with ordinary round artifacts.','Edit','sharpening'],
    ['live-phase2','Review the stable draft against its rubric and declaration.','Converge','sharpening'],
    ['status','Read current state, lineage, readiness and next action.','Read','evidence'],
    ['resume','Preview or perform supported Phase 1 recovery or budget extension.','Recover','operations'],
    ['strop / apply-back','Review or explicitly write a converged draft to the source.','Apply','operations'],
    ['decompose','Plan, approve, extract, audit and promote a spec family.','Restructure','decomposition']
  ];
  pages.reference={number:'08',label:'Commands & sources',title:'Know where the truth lives.',lead:'This field guide explains the system. It does not create new contracts, activate proposed capabilities, or replace the implementation’s own admission checks.',time:'REFERENCE',sections:[
    section('commands','Command index',`<p>Commands below are selected operator surfaces, not the exhaustive parser. Use help from the checkout you are executing for accepted flags and defaults.</p>${code('SHELL · INSPECT THE EXECUTING CLI',`${cli} --help\n${cli} audit-change --help\n${cli} resume --help\n${cli} decompose --help`)}${table(['COMMAND','PURPOSE','MODE'],commands.map(([c,t,m,r])=>[`<a href="#${r}"><code>${c}</code></a>`,t,m]))}${sources(['src/whetstone/cli.py'])}`),
    section('glossary','Working vocabulary',table(['TERM','MEANING'],[
      ['Source spec','The normative file owned by its original repository.'],['Run draft','The mutable spec.md inside the isolated job root.'],['Run root','The filesystem boundary containing job inputs and retained evidence.'],['Profile','A named review lens; budgets and stability are tracked per required profile.'],['Rubric','Quality criteria, with identity and content hash retained for the run.'],['Scope contract','The reviewed boundary and expected depth; approval is required for MVP.'],['Accepted draft','A draft accepted under current runtime rules; it can still need verification.'],['Verification debt','Review work needed on the current changed draft after earlier clean evidence became stale.'],['Convergence','An explicit terminal outcome tied to the target, rubric and draft evidence.'],['Strop','Review and optional approved apply-back from an isolated run to the source.']
    ])),
    section('capabilities','Implemented, designed, and future',`${table(['STATUS','SURFACE','READING RULE'],[
      ['<span class="cap implemented">Implemented</span>','Two live phases; intake; audit; sweeps; focused checks; bounded recovery; strop; decomposition.','Use the CLI and current Operator Quickstart for runnable procedures.'],
      ['<span class="cap developer">Local development · unpublished</span>','Preservation inventory, proposal, assessment, local acceptance/repair and scripted runtime integration.','Not part of the published CLI. Local development checkpoints do not establish public availability or live-model qualification.'],
      ['<span class="cap design">Registered design · inactive</span>','Candidate-safe editing and verified promotion.','The coordinating spec registers an activation gate. Registration is not implementation or public availability.'],
      ['<span class="cap design">Exploratory</span>','Critic then Canonicalizer two-stage review.','The subsystem spec is exploratory; current configuration does not implement this pipeline as a supported mode.'],
      ['<span class="cap design">Future notes</span>','Multi-reviewer extension and project-level spec tracking ideas.','Do not turn roadmap prose into commands or capability claims.']
    ])}<p>The guide was researched against package <strong>0.1.0</strong> and the local working tree on <strong>8 September 2026</strong>, with unpublished preservation work explicitly distinguished from the published CLI. The spec’s version milestones describe design changes, not package release numbers. Public links are pinned to the publishing commit by the Pages packager; local links read the surrounding checkout.</p>${sources(['pyproject.toml','src/whetstone/config.py','docs/OPERATOR_QUICKSTART.md',S+'CANDIDATE_EDITING_AND_PROMOTION_SPEC.md','docs/TWO_STAGE_REVIEW_PIPELINE_SPEC.md','notes/future-improvements.md'])}`),
    section('sources','Authority and source map',`<p><strong>The promoted spec family is normative.</strong> Its coordinating document routes ownership to leaves; the owning leaf controls its surface. <code>contracts/schemas/</code> contains machine-readable agreements. Runtime code and tests establish what is implemented. This HTML guide and the Operator Quickstart explain use. The old root <code>spec.md</code> is retained as the pre-decomposition snapshot.</p>${sources([S+'WHETSTONE_COORDINATING_SPEC.md',S+'RUBRICS_PROFILES_AND_FEEDBACK_SPEC.md',S+'SCOPE_INTAKE_AND_DECISIONS_SPEC.md',S+'SCHEDULER_STATE_AND_RESUME_SPEC.md',S+'ARTIFACTS_VALIDATION_AND_TELEMETRY_SPEC.md',S+'IDENTITY_OSCILLATION_AND_CONFLICTS_SPEC.md',S+'PHASE2_CONVERGENCE_AND_DECLARATION_SPEC.md',S+'CANDIDATE_EDITING_AND_PROMOTION_SPEC.md','docs/decomposition/decomposition_manifest.json','contracts/schemas/reviewer_feedback.schema.json','docs/OPERATOR_QUICKSTART.md','tests/test_cli.py'])}`),
    section('using-guide','Explore, trace, and export',`<p>Use <kbd>⌘ K</kbd> or <kbd>Ctrl K</kbd> to search. Every chapter section and architecture plate has a deep link. In a plate, choose <strong>Expand diagram</strong>, then zoom or fit. The title dropdown switches among all ten plates, including in native fullscreen.</p><p>Trace flow is optional and remembered separately for each plate during this page session. Inline and expanded controls share the setting. Traces illustrate direction; they are not execution telemetry. Reduced-motion preference replaces animation with static highlighting.</p><p>SVG export resolves the selected theme and embeds the bundled fonts for portable artwork. The five Cortext1 themes are remembered when browser storage is available. This folder opens directly from disk without a network connection. Source links need the surrounding repository; the public package points to GitHub at its deployment revision.</p>`)
  ]};
  function overview(render){return `<div class="page home-page"><section class="hero"><div class="hero-top"><div class="eyebrow"><span class="line"></span>THE SPEC SHARPENING FIELD GUIDE</div><span class="badge">WHETSTONE 0.1.0 / ACTIVE DEVELOPMENT</span></div><div class="hero-heading"><h1>From rough intent<br>to a <span class="accent">considered edge.</span></h1><span class="edge-index" aria-hidden="true">W / 01</span></div><div class="hero-intro"><p>Whetstone turns uncertain technical specifications into inspectable, implementation-ready drafts. Review with a purpose. Refine within a scope. Keep the evidence.</p><div class="button-row"><a class="button primary" href="#getting-started">Make your first run <span>→</span></a><a class="button" href="#architecture">Explore the atlas <span>↗</span></a></div></div><p class="diagram-scroll-hint">Scroll sideways to explore · Expand for the whole view ↗</p><div class="hero-art"><div class="art-heading"><span>FIELD PLATE 01 / THE SHARPENING SYSTEM</span><span>ILLUSTRATIVE · NOT LIVE</span></div>${render('01')}<div class="art-caption"><span>SCOPE → REVIEW → REFINE → VERIFY → DECIDE</span><a href="#architecture/01">Read the system view ↗</a></div></div></section><div class="stat-strip"><div class="stat"><b>Two phases</b><span>Stabilize, then test convergence</span></div><div class="stat"><b>Every round</b><span>Retained as inspectable evidence</span></div><div class="stat"><b>One boundary</b><span>Your source stays yours</span></div><div class="stat"><b>Ten plates</b><span>See how the system fits together</span></div></div><section><div class="section-heading"><div><div class="eyebrow">FIND YOUR WAY IN</div><h2>Operate it. Understand it.</h2></div><p>A practical guide to the work—and an atlas of the machinery behind it.</p></div><div class="path-grid"><a class="path-card" href="#getting-started"><span class="card-number">01 / THE OPERATOR PATH</span><h3>Make the next pass count.</h3><p>Choose a workflow, prepare your inputs, make a first run, and learn to read the result.</p><span class="text-link">Open the operator guide →</span><span class="card-art" aria-hidden="true">↗</span></a><a class="path-card" href="#architecture"><span class="card-number">02 / THE ARCHITECTURE PATH</span><h3>See what gives it an edge.</h3><p>Ten detailed plates of authority, phases, feedback, artifact lineage, and controlled change.</p><span class="text-link">Enter the architecture atlas →</span><span class="card-art" aria-hidden="true">◇</span></a></div></section><section class="principles" aria-label="Whetstone principles"><div><span>01 / PURPOSEFUL PRESSURE</span><b>Scope before sharpening.</b><p>Set the target bar and deferred work before a Reviewer expands the questions.</p></div><div><span>02 / DURABLE EVIDENCE</span><b>Keep the path to the result.</b><p>Drafts, feedback, decisions, and terminal reports preserve how the spec changed.</p></div><div><span>03 / DELIBERATE OWNERSHIP</span><b>Review before apply-back.</b><p>Convergence reports a result. You decide whether that result should become the source.</p></div></section><div class="home-note"><span class="cap developer">CURRENT BOUNDARY</span><p>Public runs use full-draft editing. Preservation components are under development; public activation remains unavailable. <a href="#reference/capabilities">Read the capability map →</a></p></div></div>`;}
  window.WhetstoneContent={pages,sources,commands,overview};
})();

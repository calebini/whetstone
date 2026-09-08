/* Hand-composed, dependency-free vector diagrams. Specs and runtime remain authoritative. */
(() => {
  const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const palette = {blue:'var(--text-accent)',teal:'var(--diagram-evidence)',purple:'var(--diagram-authority)',amber:'var(--diagram-attention)',muted:'var(--text-secondary)'};
  let serial = 0;
  const text = (x,y,value,cls='s-body',anchor='start',fill='') => `<text x="${x}" y="${y}" class="${cls}" text-anchor="${anchor}"${fill?` fill="${palette[fill]||fill}"`:''}>${esc(value)}</text>`;
  const tag = (x,y,value,color='blue',anchor='middle') => {
    const w = value.length * 6.4 + 18;
    return `<g><rect x="${anchor==='middle'?x-w/2:x-8}" y="${y-13}" width="${w}" height="20" rx="4" fill="var(--bg-surface)"/>${text(x,y,value,'s-label',anchor,color)}</g>`;
  };
  const node = (x,y,w,title,sub='',color='blue',eyebrow='',h=88) => `<g class="s-node"><title>${esc(title+'. '+sub)}</title><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="8" class="s-box"/><path d="M${x+1} ${y+19}v${h-38}" stroke="${palette[color]}" stroke-width="2"/>${eyebrow?text(x+18,y+20,eyebrow.toUpperCase(),'s-micro','start',color):''}${text(x+18,y+(eyebrow?45:32),title,'s-title')}${sub.split('|').map((line,i)=>text(x+18,y+(eyebrow?66:55)+i*18,line,'s-body')).join('')}</g>`;
  const edge = (d,color='blue',dashed=false) => `<path d="${d}" class="s-edge${dashed?' dashed':''}" stroke="${palette[color]}" marker-end="url(#ARROW_${color})"/>`;
  const line = (x1,y1,x2,y2,color='blue',dashed=false) => edge(`M${x1} ${y1} L${x2} ${y2}`,color,dashed);
  const boundary = (x,y,w,h,label,color='blue') => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="12" class="s-boundary" stroke="${palette[color]}"/>${text(x+20,y+26,label,'s-micro','start',color)}`;
  const note = (x,y,value,color='muted') => text(x,y,value,'s-label','start',color);
  const point = (x,y,color='blue',r=4) => `<circle cx="${x}" cy="${y}" r="${r}" fill="${palette[color]}"/>`;
  const marks = (w,h) => `<path d="M20 35V20h15 M${w-35} 20h15v15 M20 ${h-35}v15h15 M${w-35} ${h-20}h15v-15" fill="none" stroke="var(--border-default)"/>`;
  function wrap(content,{w=1120,h=620,title='',desc='',id=''}={}) {
    const uid=`s${++serial}`;
    const defs=Object.entries(palette).map(([key,col])=>`<marker id="ARROW_${key}" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M1 1L7 4L1 7" fill="none" stroke="${col}" stroke-width="1.2"/></marker>`).join('');
    const svg=`<svg xmlns="http://www.w3.org/2000/svg" class="diagram-svg" viewBox="0 0 ${w} ${h}" role="img" aria-labelledby="${uid}-title ${uid}-desc" data-diagram="${id}"><title id="${uid}-title">${esc(title)}</title><desc id="${uid}-desc">${esc(desc)}</desc><defs>${defs}<pattern id="GRID" width="28" height="28" patternUnits="userSpaceOnUse"><path d="M28 0H0V28" fill="none" stroke="var(--border-default)" stroke-width=".5" opacity=".24"/></pattern><radialGradient id="GLOW"><stop stop-color="var(--text-accent)" stop-opacity=".12"/><stop offset="1" stop-color="var(--text-accent)" stop-opacity="0"/></radialGradient><linearGradient id="CHARGE"><stop stop-color="var(--charge-start)"/><stop offset=".5" stop-color="var(--charge-mid)"/><stop offset="1" stop-color="var(--charge-end)"/></linearGradient><filter id="SOFT"><feGaussianBlur stdDeviation="4"/></filter></defs><style>.s-box{fill:var(--bg-surface);stroke:var(--border-default);stroke-width:.7}.s-node:hover .s-box{stroke:var(--text-accent)}.s-title{font:600 16px Syne,Arial,sans-serif;fill:var(--text-primary)}.s-body{font:12px Inter,Arial,sans-serif;fill:var(--text-secondary)}.s-label{font:11px 'JetBrains Mono',monospace}.s-micro{font:9px 'JetBrains Mono',monospace;letter-spacing:1.2px}.s-edge{fill:none;stroke-width:1;opacity:.85}.s-edge.dashed{stroke-dasharray:4 5}.s-boundary{fill:none;stroke-width:.7;stroke-dasharray:4 6;opacity:.55}.s-rule{stroke:var(--border-default);stroke-width:.7}.s-big{font:600 36px Syne,Arial,sans-serif;fill:var(--text-primary)}.s-strong{font:600 13px Inter,Arial,sans-serif;fill:var(--text-primary)}.s-mono{font:12px 'JetBrains Mono',monospace;fill:var(--text-primary)}.s-pulse{stroke-dasharray:2 24;animation:flow 6s linear infinite}@keyframes flow{to{stroke-dashoffset:-104}}@media(prefers-reduced-motion:reduce){.s-pulse{animation:none}}</style><rect width="${w}" height="${h}" fill="var(--bg-base)"/><rect width="${w}" height="${h}" fill="url(#GRID)"/>${marks(w,h)}${content}</svg>`;
    return svg.replaceAll('ARROW_',`${uid}-arrow-`).replaceAll('id="GRID"',`id="${uid}-grid"`).replaceAll('url(#GRID)',`url(#${uid}-grid)`).replaceAll('id="GLOW"',`id="${uid}-glow"`).replaceAll('url(#GLOW)',`url(#${uid}-glow)`).replaceAll('id="CHARGE"',`id="${uid}-charge"`).replaceAll('url(#CHARGE)',`url(#${uid}-charge)`).replaceAll('id="SOFT"',`id="${uid}-soft"`).replaceAll('url(#SOFT)',`url(#${uid}-soft)`).replaceAll('id="BLADE"',`id="${uid}-blade"`).replaceAll('url(#BLADE)',`url(#${uid}-blade)`);
  }
  const plate=(n,t,s)=>text(52,60,n+' / '+t,'s-micro','start','blue')+text(52,84,s,'s-body');
  const stone=(x,y)=>`<g><defs><linearGradient id="BLADE" gradientUnits="userSpaceOnUse" x1="${x+16}" y1="${y+49}" x2="${x+24.63}" y2="${y+67}"><stop offset="0" stop-color="var(--text-accent)" stop-opacity="1"/><stop offset=".45" stop-color="var(--text-accent)" stop-opacity=".3"/><stop offset="1" stop-color="var(--text-accent)" stop-opacity="0"/></linearGradient></defs><ellipse cx="${x+180}" cy="${y+88}" rx="230" ry="155" fill="url(#GLOW)"/><path d="M${x} ${y+92}l234-111 124 73-235 111Z" fill="var(--bg-elevated)" stroke="var(--text-accent)"/><path d="M${x} ${y+92}v25l123 73 235-112v-24" fill="none" stroke="var(--text-accent)" opacity=".35"/>${Array.from({length:13},(_,i)=>`<path d="M${x+30+i*13} ${y+78-i*6}l90 52" stroke="var(--text-accent)" opacity=".12"/>`).join('')}<path d="M${x+16} ${y+49}l244-117 8.63 18-244 117Z" fill="url(#BLADE)"/><path d="M${x+16} ${y+49}l244-117" stroke="var(--text-accent)" stroke-width="2"/><path d="M${x+16} ${y+49}l244-117" stroke="var(--text-accent)" stroke-width="7" opacity=".15" filter="url(#SOFT)"/></g>`;
  function context(){return plate('01','THE SHARPENING BOUNDARY','People own intent. Whetstone owns the loop. Persisted evidence explains the result.')+
    boundary(355,126,420,390,'ISOLATED RUN / LOCAL CONTROL')+
    edge('M295 220H390')+edge('M570 151V109H919V176','purple',true)+edge('M820 220H736','purple')+
    edge('M295 427H336V337L407 303')+edge('M732 337H790V427H820','teal')+
    edge('M820 467H790V552H172V478','amber',true)+
    node(52,176,243,'Operator / agent','Choose scope, clients and budgets','purple','INTENT & AUTHORIZATION')+
    node(52,389,243,'Source specifications','Owned by the source repository','blue','READ / COPY',89)+
    stone(391,254)+text(565,379,'Whetstone','s-big','middle')+text(565,405,'REVIEW → EDIT → VERIFY','s-micro','middle','blue')+
    node(820,176,247,'Model clients','Codex / Claude CLI subprocesses','purple','EXTERNAL INFERENCE')+
    node(820,389,247,'Run artifacts','Drafts, findings, state, declaration','teal','INSPECTABLE OUTPUT')+
    tag(338,208,'control')+tag(778,207,'feedback','purple')+tag(363,370,'copy')+tag(790,363,'persist','teal')+
    tag(558,545,'strop: review + explicit approval before source write','amber')+
    note(52,591,'Solid: information paths. Dashed: authorization / deliberate external source change.');}
  function components(){return plate('02','RUNTIME RESPONSIBILITIES','Logical module groups inside the Python process; these are not separate deployed services.')+
    boundary(35,112,725,442,'WHETSTONE PYTHON PROCESS')+boundary(794,112,290,442,'SUBPROCESS / FILE BOUNDARIES','purple')+
    edge('M327 213H402')+edge('M560 257V318')+edge('M402 215H368V446H327')+edge('M327 448H402','teal')+
    edge('M727 358H784V215H824','purple')+edge('M940 260V344','purple')+edge('M940 432V492H727','teal')+
    node(60,169,267,'CLI & configuration','cli.py · config.py · scope.py','blue','ADMISSION')+
    node(402,169,325,'Phase runners & scheduler','live_phase1.py · live_phase2.py','blue','CONTROL')+
    node(402,318,325,'Round orchestration','live.py · prompts.py · clients.py','blue','REVIEWER / EDITOR HANDOFF')+
    node(60,402,267,'Deterministic checks','identity · evaluation · termination','teal','VALIDATION & DECISIONS')+
    node(402,448,325,'Artifacts & run state','artifacts.py · run_state.py','teal','PERSISTENCE')+
    node(824,172,230,'Model CLI','Identity and role timeouts','purple','EXTERNAL')+
    node(824,344,230,'Context & output files','Snapshots and telemetry','purple','FILE HANDOFF')+
    tag(365,197,'dispatch')+note(52,593,'Public protocols: ReviewerClient.review(prompt) and EditorClient.revise(prompt).');}
  function concepts(){return plate('03','THE EVIDENCE VOCABULARY','A conceptual relationship map of artifacts, not a database schema or exhaustive file inventory.')+
    edge('M312 198H441')+edge('M560 242V325')+edge('M678 198H807','purple')+edge('M807 232H760V369H678','purple')+
    edge('M441 369H312','teal')+edge('M560 413V481','teal')+edge('M807 385H678','teal')+
    node(62,154,250,'Source & run draft','Original bytes → isolated spec.md','blue','CONTENT')+
    node(441,154,237,'Run','Config, state, budgets, hashes','blue','EXECUTION IDENTITY')+
    node(807,154,252,'Scope & rubric','Allowed depth and quality target','purple','BOUND REVIEW PRESSURE')+
    node(441,325,237,'Round','One persisted step in the run','blue','ROUND-N')+
    node(62,325,250,'Finding & issue','Claim, section, identity, severity','teal','REVIEWER FEEDBACK')+
    node(807,325,252,'Editor disposition','Accepted, modified or declined IDs','teal','EDITOR SUMMARY')+
    node(441,481,360,'Declaration & terminal reports','Read alongside the current draft hash','teal','RUN OUTCOME')+
    tag(377,184,'seeds')+tag(584,288,'contains')+tag(375,357,'records','teal')+
    note(52,592,'An Editor resolution claim is evidence to inspect; a clean review of the changed draft verifies it.');}
  function lifecycle(){return plate('04','END-TO-END PROGRESSION','The main sharpening path, with assessment and focused work shown as separate destinations.')+
    boundary(42,135,1035,239,'THE CONVERGENCE PATH')+
    edge('M255 247H321')+edge('M531 247H597')+edge('M807 247H869','teal')+
    node(68,203,187,'Prepare','Config + copied draft','purple','01 / SCOPE')+
    node(321,203,210,'Phase 1','Technical stabilization','blue','02 / SHARPEN')+
    node(597,203,210,'Phase 2','Rubric + declaration','blue','03 / CONVERGE')+
    node(869,203,183,'Strop','Review → approve','teal','04 / APPLY')+
    tag(562,305,'PHASE_1_STABLE','teal')+tag(913,332,'CONVERGED','teal')+
    edge('M426 291V430','amber',true)+edge('M702 291V430','amber',true)+
    node(321,430,486,'Stop with evidence','Budgets · invalid artifacts · timeout · conflict · decision','amber','HALT / PAUSE / RESIDUALS')+
    node(68,430,217,'Assessment only','Audit / diagnostic sweep','purple','NO CONVERGENCE')+
    node(840,430,212,'Focused Phase 1','One selected profile','purple','NO PHASE 2 ADMISSION')+
    note(52,591,'Only a full stable Phase 1 admits Phase 2. A focused result or an audit verdict does not.');}
  function intake(){return plate('05','PREPARE THE RIGHT PRESSURE','Two preparation paths: a single mutable draft, or a read-only audit over a family of seeds.')+
    boundary(40,128,510,400,'A / SHARPEN ONE SPEC')+boundary(573,128,505,400,'B / ASSESS SEVERAL SPECS','purple')+
    edge('M299 231H334')+edge('M432 275V341')+edge('M299 385H334','purple')+
    node(66,187,233,'Source copy','Isolate spec.md + history','blue','RUN ROOT')+
    node(334,187,189,'Configuration','Profiles, clients, budgets','blue','JOB SHAPE')+
    node(66,341,233,'Scope notes','Core outcome + deferred work','purple','MVP: HUMAN REVIEW')+
    node(334,341,189,'Approved scope','scope_contract.json','purple','INTAKE --APPROVE')+
    edge('M707 275V336','purple')+edge('M947 275V336','purple')+edge('M829 424V472','teal')+
    node(600,187,214,'Seed specs','Explicit --spec paths','purple','AUTHORITIES')+
    node(842,187,211,'Audit notes','Intent + expected boundary','purple','BOUNDED QUESTION')+
    node(600,336,453,'audit-change','One reviewer-only brief with per-source hashes','teal','READ-ONLY ASSESSMENT')+
    tag(829,492,'report → manual revision / scoped run','teal')+
    note(52,574,'Seed bundle is an operator pattern over audit-change, not a separate CLI command.')+
    note(52,594,'Reference context informs a mutable run; it does not make reference files editable drafts.');}
  function sequence(){return plate('06','REVIEW, EDIT, VERIFY','Horizontal iteration above; vertical consolidation below. Arrows describe order, not concurrency.')+
    `<path d="M52 322H1068" class="s-rule"/>`+
    edge('M270 218H338')+edge('M562 218H630','teal')+edge('M854 218H903')+edge('M995 262V297H168V262','teal',true)+
    node(52,174,218,'Review profile','Inspect current draft + context','blue','HORIZONTAL')+
    node(338,174,224,'Validate feedback','Schema, identity and severity','teal','ORCHESTRATOR')+
    node(630,174,224,'Editor revision','Full draft + disposition','blue','BOUNDED BY PROMPT')+
    node(903,174,165,'Re-review','Changed draft','teal','VERIFY')+
    tag(558,293,'changed draft returns to review','teal')+
    boundary(40,360,375,182,'VERTICAL / SAME DRAFT HASH','purple')+
    node(63,401,330,'Separate profile reviews','Structural · determinism · operability','purple','REVIEW-ONLY ROUNDS')+
    edge('M393 445H481')+edge('M724 445H800')+edge('M929 489V561H222V489','teal',true)+
    node(481,401,243,'Merged feedback','One cross-profile problem set','blue','CONSOLIDATE')+
    node(800,401,268,'One Editor turn','Then verify required profiles again','teal','CONSOLIDATED_EDITOR')+
    note(52,600,'A full-draft Editor can remove content. Scope instructions do not provide enforced preservation.');}
  function feedback(){return plate('07','FINDINGS BECOME VERIFICATION DEBT','Follow the claim, its disposition, and the evidence on the draft that actually exists now.')+
    edge('M287 230H352')+edge('M605 230H675')+edge('M804 274V385')+
    edge('M675 429H605','teal')+edge('M352 429H287','teal')+edge('M161 385V274','teal',true)+
    node(52,186,235,'Reviewer finding','Claim + affected sections + scope','blue','OBSERVATION')+
    node(352,186,253,'Canonical identity','Fingerprint, ID, severity','blue','DETERMINISTIC')+
    node(675,186,259,'Editor disposition','Resolve, modify, decline; record IDs','purple','CLAIMED RESPONSE')+
    node(675,385,259,'Changed draft','New hash needs verification','blue','ACCEPTED MAY BE UNVERIFIED')+
    node(352,385,253,'Profile re-review','Clean evidence on this hash','teal','VERIFY')+
    node(52,385,235,'Unresolved issues','Remaining blockers and majors','teal','FEEDBACK LOOP')+
    edge('M480 274V327H1012V500','amber',true)+node(812,500,257,'Churn / conflicts','Oscillation and conflict reports','amber','STOP WHEN REQUIRED',79)+
    note(52,552,'Focused rechecks verify one lens. Full readiness needs the complete Phase 1 profile set.')+
    note(52,585,'Disposition and halt precedence are governed by evaluation and termination rules.');}
  function lineage(){return plate('08','A RUN IS A CHAIN OF EVIDENCE','File groups are representative. Run state identifies accepted lineage; folder order alone does not.')+
    boundary(41,122,1038,438,'ISOLATED RUN ROOT')+
    node(66,174,260,'spec.md + config','Current draft and job inputs','blue','ROOT')+
    edge('M326 218H421')+edge('M686 218H791','teal')+
    node(421,174,265,'rounds/run_state.json','Current hash, phase, profile state','blue','CONTROL RECORD')+
    node(791,174,262,'Declaration','convergence_declaration.md','teal','TERMINAL EVIDENCE')+
    edge('M554 262V325H217V358')+edge('M369 402H421')+edge('M686 402H738')+
    node(66,358,303,'round-N / before','draft_before.md|prompt_snapshot.json','purple','INPUT SNAPSHOT',106)+
    node(421,358,265,'round-N / findings','reviewer_feedback.json|editor_summary.json','teal','STRUCTURED HANDOFF',106)+
    node(738,358,315,'round-N / after','draft_after.md|unresolved_issues.json','blue','OUTPUT SNAPSHOT',106)+
    edge('M895 464V510H710V299H610V262','teal',true)+tag(859,507,'accepted hash advances state','teal')+
    note(52,590,'Also: decision registers, profile/rubric manifests, terminal reports and available client telemetry.');}
  function applyback(){return plate('09','THE SOURCE WRITE IS A SEPARATE DECISION','Current strop behavior. Candidate-safe promotion and public bridge activation remain gated.')+
    boundary(42,131,495,410,'WHETSTONE / RUN EVIDENCE')+boundary(580,131,498,410,'OPERATOR / SOURCE OWNERSHIP','purple')+
    edge('M290 228H325')+edge('M423 272V360','teal')+
    node(67,184,223,'Converged run','Draft + declaration + decisions','teal','REVIEW INPUT')+
    node(325,184,185,'Hash checks','Source opt-in + final hash','blue','ELIGIBILITY')+
    node(67,360,443,'Strop dry run','rounds/apply_back_review.md + JSON + diff','teal','NO SOURCE WRITE')+
    edge('M510 404H607','purple')+edge('M823 404H863','amber')+
    node(607,360,216,'Human review','Inspect actual diff and losses','purple','CHANGE AUTHORITY')+
    node(863,360,187,'Source write','--apply --approve','amber','EXPLICIT ACTION')+
    node(608,184,442,'Original source repository','Owns the normative file and subsequent commit','purple','EXTERNAL AUTHORITY')+
    edge('M956 360V272','amber')+
    tag(793,496,'CONVERGED is not permission to publish or commit','purple')+
    note(52,590,'Hash guards detect changed content. They do not prove preservation of every requirement.');}
  function recovery(){return plate('10','EXECUTION & RECOVERY','Local files, a Python invocation, and external model clients. Diagnose the boundary that failed.')+
    boundary(39,119,310,421,'HOST / OPERATOR')+boundary(377,119,333,421,'PYTHON / WHETSTONE')+boundary(737,119,342,421,'CLIENT / PROVIDER','purple')+
    node(61,177,263,'Invocation','CLI, environment, run root','blue','LOCAL HOST')+
    edge('M324 221H402')+node(402,177,283,'Preflight & context','Validate config; snapshot input files','blue','ADMISSION')+
    edge('M685 221H764','purple')+node(764,177,288,'Reviewer / Editor CLI','Session access, model, role timeout','purple','EXTERNAL INFERENCE')+
    edge('M908 265V346','amber')+node(764,346,288,'Output or failure','Artifacts / timeout / invalid output','amber','RETURN BOUNDARY')+
    edge('M764 390H685','teal')+node(402,346,283,'Persist state & reports','Validate, retry or halt as supported','teal','EVIDENCE')+
    edge('M402 390H324','teal')+node(61,346,263,'Status → dry-run resume','Check eligibility and unchanged hash','teal','OPERATOR RECOVERY')+
    edge('M193 434V494H546V434','teal',true)+tag(422,492,'supported continuation only','teal')+
    note(52,576,'Preserve failed roots. Generic resume cannot repair Phase 2 timeouts or a manually changed draft.')+
    note(52,596,'Phase 2 closeout-existing is a bounded review-only path, not generic timeout recovery.');}
  const all=[];
  function add(id,slug,short,type,title,summary,draw,steps,invariant,desc,sources){all.push({id,slug,short,type,title,summary,draw,steps,invariant,desc,sources,boundary:'Explanatory architecture · Illustrative flow tracing, not live telemetry.'});}
  add('01','authority','System & authority','CONTEXT','Pressure, with a boundary.','Where people, source specifications, model clients, and Whetstone meet—and who owns each decision.',context,['Start with the operator: scope, client access and budgets are job inputs.','Follow the source copy into an isolated run and model feedback back into the loop.','The lower return path is deliberate strop apply-back, after review and approval.'],'A run result does not own the source specification. Source changes require a separate apply-back decision.','An operator configures Whetstone in an isolated run root. Source specifications are read or copied. External model CLI clients supply feedback and edits. Whetstone persists evidence. Strop can copy an eligible result to the source after explicit approval.',['README.md','docs/OPERATOR_QUICKSTART.md','src/whetstone/apply_back.py']);
  add('02','components','Runtime responsibilities','COMPONENT MAP','One loop. Distinct responsibilities.','The Python modules that admit a job, run its phases, validate its artifacts, and preserve its state.',components,['Enter through cli.py and config.py.','Phase runners use scheduling and round orchestration; deterministic checks evaluate returned artifacts.','Subprocesses cross the external boundary. Files carry context, output and available telemetry.'],'A successful model subprocess alone is not a valid round. The orchestrator checks its output.','Logical groups cover CLI/configuration, phase scheduling, round execution, validation and storage. They execute inside Python rather than as independent services. Client subprocesses and filesystem artifacts are external boundaries.',['src/whetstone/cli.py','src/whetstone/protocols.py','src/whetstone/live.py','src/whetstone/scheduler.py','src/whetstone/artifacts.py']);
  add('03','concepts','Concepts & artifacts','RELATIONSHIP MAP','Give every claim a place.','A vocabulary for runs, drafts, rounds, findings, dispositions, and terminal evidence.',concepts,['A source seeds one mutable run draft.','A run binds configuration, scope and rubric to a sequence of rounds.','Each round records feedback and disposition; terminal evidence summarizes the outcome.'],'A finding, an Editor disposition, and a verified correction are distinct facts.','The run relates content to scope, rubric and configuration. It contains rounds with Reviewer findings and Editor dispositions. It emits declarations or terminal reports whose meaning depends on the current draft and its lineage.',['docs/specs/ARTIFACTS_VALIDATION_AND_TELEMETRY_SPEC.md','contracts/schemas/reviewer_feedback.schema.json','contracts/schemas/editor_summary.schema.json','src/whetstone/run_state.py']);
  add('04','lifecycle','Workflow & phases','STATE PROGRESSION','Every next step is earned.','The main route from preparation through stabilization and convergence to a reviewed source change.',lifecycle,['Prepare an isolated root and appropriate scope.','Require PHASE_1_STABLE before Phase 2 and CONVERGED before normal strop.','Read assessments, focused checks, and halts according to their own outcome semantics.'],'An audit pass or FOCUSED_PROFILE_STABLE does not admit Phase 2.','The main path is prepare, Phase 1, Phase 2, then reviewed strop. Both phases can halt or pause. Reviewer-only assessments and focused Phase 1 are separate workflows with narrower conclusions.',['docs/OPERATOR_QUICKSTART.md','src/whetstone/live_phase1.py','src/whetstone/live_phase2.py','src/whetstone/status.py']);
  add('05','intake','Scope & seed preparation','TWO PATHS','Choose the surface to sharpen.','Prepare one editable draft or assess a small family of authority documents without rewriting them.',intake,['Use an isolated source copy and explicit configuration for sharpening.','For MVP, review scope notes and approve the generated scope contract.','For a seed bundle, give audit-change explicit spec paths and a bounded question in notes.'],'A draft scope contract does not satisfy MVP preflight; references are not automatically mutable inputs.','Single-spec preparation copies a draft and configures profiles, clients and budgets. MVP intake converts notes to an approved scope contract. Multi-spec assessment combines explicit paths and notes in a reviewer-only brief with a manifest.',['docs/SCOPE_NOTES_GUIDE.md','src/whetstone/scope.py','src/whetstone/change_audit.py','contracts/schemas/change_audit_manifest.schema.json']);
  add('06','refinement','Analysis & refinement','SEQUENCE COMPARISON','A finer edge, one pass at a time.','Two review modes: iterate by profile, or collect independent profile feedback before one edit.',sequence,['Horizontal mode advances through profile review and editing.','Vertical mode reviews the same draft under each profile, then merges feedback for one consolidated Editor round.','Any changed draft needs fresh verification; a clean earlier hash is insufficient.'],'Accepted editing and clean verification are separate checkpoints. Current full-draft editing does not enforce preservation.','Horizontal mode loops review, validation, revision and re-review. Vertical mode has review-only profile rounds over the same hash, merged feedback and a consolidated Editor round. Arrows show order, not concurrent execution.',['docs/OPERATOR_QUICKSTART.md','src/whetstone/live.py','src/whetstone/live_phase1.py','src/whetstone/evaluation.py']);
  add('07','feedback','Findings & rechecks','FEEDBACK LOOP','Close the issue. Verify the draft.','How claims acquire identity, Editor responses are recorded, and changes create verification work.',feedback,['Follow a claim through deterministic identity and severity handling.','Read the Editor disposition and actual changed text together.','Re-review the current hash, inspect unresolved issues, and stop on applicable churn or conflict gates.'],'An Editor resolution claim does not substitute for Reviewer evidence on the current draft.','A finding has sections, scope and identity. An Editor supplies a disposition and possibly a new draft. A profile review verifies the resulting hash. Remaining issues feed iteration; oscillation and conflict detection can halt the loop.',['src/whetstone/identity.py','src/whetstone/evaluation.py','src/whetstone/oscillation.py','src/whetstone/conflicts.py','docs/specs/IDENTITY_OSCILLATION_AND_CONFLICTS_SPEC.md']);
  add('08','lineage','Run lineage & provenance','ARTIFACT TOPOLOGY','Keep the path to the result.','The file structure connecting job inputs, each round’s evidence, and the accepted draft lineage.',lineage,['Read status, then the run-state current draft hash.','Inspect before/after snapshots and structured handoffs in the selected round.','Use declarations, reports and manifests to explain the terminal outcome.'],'The largest round number does not prove its draft is the accepted current draft.','A root contains spec.md, configuration and a declaration. The rounds directory contains run_state.json and numbered round directories. Each round retains text, prompt snapshots and feedback. Accepted lineage updates the hash in run state.',['src/whetstone/artifacts.py','src/whetstone/run_state.py','src/whetstone/status.py','docs/specs/ARTIFACTS_VALIDATION_AND_TELEMETRY_SPEC.md']);
  add('09','apply-back','Apply-back & ownership','AUTHORITY CROSSING','Sharpening ends. Ownership stays.','Eligibility, diff review, and explicit action separate a run from a source repository change.',applyback,['Inspect the draft, declaration and decisions.','Run strop without apply to review eligibility and the source diff.','After review, use --apply --approve; the source owner retains responsibility for committing the change.'],'CONVERGED is a run outcome, not permission to write the source or publish a repository.','Strop evaluates terminal eligibility, draft lineage and text hygiene. Source-baseline comparison requires --expected-source-hash. A dry run produces review artifacts. The operator inspects the actual diff, then explicit apply plus approval permits a source write. Hash guards are not semantic preservation guarantees.',['src/whetstone/apply_back.py','docs/OPERATOR_QUICKSTART.md','docs/specs/SCHEDULER_STATE_AND_RESUME_SPEC.md','docs/specs/CANDIDATE_EDITING_AND_PROMOTION_SPEC.md']);
  add('10','recovery','Execution & recovery','FAILURE TOPOLOGY','Recover from the right boundary.','Locate failures across the host, Python process, and nested model client before choosing a supported continuation.',recovery,['Separate host/session access from semantic model feedback.','Inspect persisted status, terminal reports and missing artifacts.','Use dry-run recovery only for supported states with intact lineage; Phase 2 closeout is separate.'],'A failed run is not automatically resumable. Unchanged inputs and supported state are admission requirements.','The host launches Python with a run root. Whetstone preflights and writes context. Clients return output or fail. Whetstone validates and persists evidence. The operator previews a supported resume. Generic Phase 2 timeout recovery is unavailable.',['src/whetstone/clients.py','src/whetstone/resume.py','src/whetstone/status.py','src/whetstone/termination.py','docs/OPERATOR_QUICKSTART.md']);
  window.WhetstoneDiagrams={all,escape:esc,render(id){const d=all.find(d=>d.id===id);return d?wrap(d.draw(),{id,title:d.title,desc:d.desc}):'';}};
})();

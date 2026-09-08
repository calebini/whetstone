/** Check rendered command syntax, deep-link targets, and source availability without model calls. */
import {readFile,writeFile,mkdtemp} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import vm from 'node:vm';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
import {sourcePaths} from './build-pages.mjs';
const site=path.dirname(fileURLToPath(import.meta.url)),sandbox={window:{}};vm.createContext(sandbox);
for(const name of ['diagrams.js','content.js'])vm.runInContext(await readFile(path.join(site,name),'utf8'),sandbox);
const {pages,overview}=sandbox.window.WhetstoneContent,diagrams=sandbox.window.WhetstoneDiagrams;
const html=[await readFile(path.join(site,'index.html'),'utf8'),overview(diagrams.render),...Object.values(pages).flatMap(p=>p.sections.map(s=>s.body))].join('\n');
const decode=s=>s.replace(/&(#39|quot|lt|gt|amp);/g,(_,k)=>({'#39':"'",quot:'"',lt:'<',gt:'>',amp:'&'}[k]));
const temp=await mkdtemp(path.join(os.tmpdir(),'whetstone-doc-content-'));
let checked=0,configs=0;
for(const match of html.matchAll(/<pre><code>([\s\S]*?)<\/code><\/pre>/g)){
 const code=decode(match[1]);
 if(code.startsWith('spec_path:')){
  const configPath=path.join(temp,'orchestrator_config.yaml');await writeFile(configPath,code);
  execFileSync('python3',['-c','import sys; from whetstone.config import load_config; c=load_config(sys.argv[1]); assert c.workflow == "standard"',configPath],{cwd:path.resolve(site,'../..'),env:{...process.env,PYTHONPATH:'src'}});configs++;
 }
 if(!code.includes('python3')&&!code.includes('pip install'))continue;
 const file=path.join(temp,`snippet-${checked++}.sh`);await writeFile(file,code);execFileSync('bash',['-n',file]);
}
let anchors=0;
for(const [,href] of html.matchAll(/href="#([^\"]+)"/g)){
 const [route,part]=href.split('/');if(['main','overview'].includes(route))continue;
 if(route==='architecture'){if(part)assert.ok(diagrams.all.some(d=>d.id===part),href);}
 else {assert.ok(pages[route],href);if(part)assert.ok(pages[route].sections.some(s=>s.id===part),href);}anchors++;
}
console.log(`PASS: ${configs} live config loads; ${checked} shell snippets parse; ${anchors} internal links resolve; ${(await sourcePaths()).length} source paths inventoried.`);

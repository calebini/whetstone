/** Explicit public-asset allowlist. No run roots, source files or QA artifacts are copied. */
import {copyFile,mkdir,readFile,writeFile,stat,realpath} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import vm from 'node:vm';
const site=path.dirname(fileURLToPath(import.meta.url)),repo=path.resolve(site,'../..');
export const publicFiles=['index.html','styles.css','app.js','content.js','diagrams.js','font-data.js','assets/whetstone.svg','assets/favicon.svg','assets/favicon-32.png','assets/fonts/inter-regular.ttf','assets/fonts/inter-semibold.ttf','assets/fonts/syne-semibold.ttf','assets/fonts/jetbrains-mono.ttf','assets/fonts/Inter-OFL.txt','assets/fonts/Syne-OFL.txt','assets/fonts/JetBrainsMono-OFL.txt'];
export async function sourcePaths(){
  const sandbox={window:{}};vm.createContext(sandbox);
  for(const name of ['diagrams.js','content.js'])vm.runInContext(await readFile(path.join(site,name),'utf8'),sandbox);
  const content=sandbox.window.WhetstoneContent,diagrams=sandbox.window.WhetstoneDiagrams;
  const rendered=[await readFile(path.join(site,'index.html'),'utf8'),content.overview(diagrams.render),...Object.values(content.pages).flatMap(p=>p.sections.map(s=>s.body)),...diagrams.all.map(d=>content.sources(d.sources))].join('\n');
  return [...new Set([...rendered.matchAll(/href="(\.\.\/[^\"]+)"/g)].map(m=>m[1]))].sort();
}
export async function buildPages(output,{repository='calebini/whetstone',revision}={}){
  if(!/^[a-z\d][a-z\d-]*\/[a-z\d][\w.-]*$/i.test(repository))throw new Error('Invalid GitHub repository');
  if(!/^[a-f0-9]{40}$/.test(revision||''))throw new Error('A full commit SHA is required');
  const links=await sourcePaths();
  for(const href of links){
    const absolute=path.resolve(site,href.split('#')[0]);
    const real=await realpath(absolute),relative=path.relative(repo,real);
    if(relative.startsWith('..')||path.isAbsolute(relative))throw new Error('Source outside repository: '+href);
    if(!(await stat(absolute)).isFile())throw new Error('Source must be a file: '+href);
  }
  // Fail before copying if destination already exists; never remove or overwrite it.
  await mkdir(output);
  const base=`https://github.com/${repository}/blob/${revision}/`;
  for(const file of publicFiles){
    const target=path.join(output,file);await mkdir(path.dirname(target),{recursive:true});
    if(!['index.html','content.js'].includes(file)){await copyFile(path.join(site,file),target);continue;}
    let text=await readFile(path.join(site,file),'utf8');
    text=text.replace('href="../../${p}"',`href="${base}\${p}"`);
    text=text.replace(/href="(\.\.\/[^\"]+)"/g,(_,href)=>{
      const [file,fragment]=href.split('#');const relative=path.relative(repo,path.resolve(site,file));
      return `href="${base}${relative.split(path.sep).map(encodeURIComponent).join('/')}${fragment?'#'+fragment:''}"`;
    });
    if(file==='index.html')text=text.replace('</head>',`<meta name="whetstone-source-revision" content="${revision}">\n</head>`);
    await writeFile(target,text);
  }
  await writeFile(path.join(output,'.nojekyll'),'');
  console.log(`Packaged ${publicFiles.length} public assets and ${links.length} revision-pinned source targets (${repository}@${revision}).`);
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  if(!process.argv[2])throw new Error('Usage: node docs/site/build-pages.mjs NEW_OUTPUT_DIRECTORY');
  await buildPages(path.resolve(process.argv[2]),{repository:process.env.GITHUB_REPOSITORY||'calebini/whetstone',revision:process.env.GITHUB_SHA||execFileSync('git',['rev-parse','HEAD'],{cwd:repo,encoding:'utf8'}).trim()});
}

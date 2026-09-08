import assert from 'node:assert/strict';
import {mkdtemp,readFile,readdir} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import {buildPages,publicFiles,sourcePaths} from './build-pages.mjs';
test('Only public assets; every source is checked locally and pinned at deployment',async()=>{
 const root=await mkdtemp(path.join(os.tmpdir(),'whetstone-pages-test-')),out=path.join(root,'site'),revision='a'.repeat(40);
 await buildPages(out,{revision});
 const files=(await readdir(out,{recursive:true,withFileTypes:true})).filter(e=>e.isFile()).map(e=>path.relative(out,path.join(e.parentPath||e.path,e.name))).sort();
 assert.deepEqual(files,[...publicFiles,'.nojekyll'].sort());
 const html=await readFile(path.join(out,'index.html'),'utf8'),content=await readFile(path.join(out,'content.js'),'utf8');
 assert.ok(html.includes(`/blob/${revision}/docs/OPERATOR_QUICKSTART.md`));
 assert.ok(html.includes(`/blob/${revision}/README.md`));
 assert.ok(content.includes(`/blob/${revision}/\${p}`));
 assert.doesNotMatch(html+content,/href="\.\.\//);
 assert.ok(html.includes('src="app.js"'));
 assert.ok((await sourcePaths()).length>=50);
 await assert.rejects(buildPages(out,{revision}),{code:'EEXIST'});
 assert.ok((await readFile(new URL('content.js',import.meta.url),'utf8')).includes('href="../../${p}"'));
});
test('Publishing requires safe repository metadata and an immutable revision',async()=>{
 const root=await mkdtemp(path.join(os.tmpdir(),'whetstone-pages-invalid-'));
 await assert.rejects(buildPages(path.join(root,'site'),{repository:'../private',revision:'a'.repeat(40)}),/Invalid GitHub/);
 for(const revision of [undefined,'main','../../secret','abc'])await assert.rejects(buildPages(path.join(root,'site'),{revision}),/full commit SHA/);
});

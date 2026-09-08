/** Export portability, local source navigation, theme persistence, and visual proof sheets. */
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const require=createRequire(import.meta.url),{chromium}=require(process.env.WHETSTONE_PLAYWRIGHT_PATH||'playwright-core');
const site=path.dirname(fileURLToPath(import.meta.url)),out=path.join(site,'qa-output');await mkdir(out,{recursive:true});
const url=process.env.WHETSTONE_DOCS_URL||'http://127.0.0.1:8766/';
const browser=await chromium.launch({headless:true,...(process.env.WHETSTONE_CHROME_PATH?{executablePath:process.env.WHETSTONE_CHROME_PATH}:{channel:'chrome'})});
const page=await browser.newPage({viewport:{width:1512,height:1000},acceptDownloads:true});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
const themes=['cortex-dark','voltage-blue','cortex-purple','signal-live','inverted'];
let exported=0;
try{
 await page.goto(url+'#architecture/01');
 for(const theme of themes){
  await page.selectOption('#theme-select',theme);await page.reload();
  assert.equal(await page.locator('html').getAttribute('class'),'theme-'+theme,'Theme survives reload');
  for(let n=1;n<=10;n++){
   const id=String(n).padStart(2,'0');await page.goto(url+'#architecture/'+id);
   const downloading=page.waitForEvent('download');await page.locator('.diagram-tools [data-download]').click();
   const download=await downloading,svg=await readFile(await download.path(),'utf8');
   assert.match(download.suggestedFilename(),new RegExp('whetstone-'+id+'-'));
   assert.match(svg,/data:font\/ttf;base64,/);assert.doesNotMatch(svg,/var\(--/);
   assert.ok(svg.includes(`data-diagram="${id}"`));
   const background=await page.evaluate(()=>getComputedStyle(document.documentElement).getPropertyValue('--bg-base').trim());assert.ok(svg.includes(background));exported++;
   if(n===1){
    const exportedPath=path.join(out,'export-'+theme+'.svg');await writeFile(exportedPath,svg);
    const standalone=await browser.newPage({viewport:{width:1120,height:620}});await standalone.goto('file://'+exportedPath);await standalone.evaluate(()=>document.fonts.ready);
    assert.ok(await standalone.locator('svg').count());
    await standalone.screenshot({path:path.join(out,'export-'+theme+'.jpg'),type:'jpeg',quality:75});await standalone.close();
   }
  }
 }
 // Expanded export must follow the picker, not the page beneath the modal.
 await page.goto(url+'#architecture/01');await page.locator('[data-expand="01"]').click();await page.selectOption('#diagram-picker','09');
 const downloading=page.waitForEvent('download');await page.locator('#expanded-export').click();assert.match((await downloading).suggestedFilename(),/^whetstone-09-/);
 await page.locator('[aria-label="Close expanded diagram"]').click();
 // Real inline motion, not merely the presence of path clones.
 await page.emulateMedia({reducedMotion:'no-preference'});await page.locator('.diagram-tools [data-trace]').click();
 const before=await page.locator('.diagram-canvas .s-trace').first().evaluate(p=>getComputedStyle(p).strokeDashoffset);
 await page.waitForFunction(previous=>getComputedStyle(document.querySelector('.diagram-canvas .s-trace')).strokeDashoffset!==previous,before);
 // Direct file opening, fonts, export and actual source-link navigation work without a server.
 const disk=await browser.newPage({acceptDownloads:true});await disk.goto('file://'+path.join(site,'index.html')+'#getting-started');await disk.evaluate(()=>document.fonts.ready);
 assert.equal(await disk.locator('h1').textContent(),'Your first complete trail.');
 const source=disk.locator('a.source-pill[href="../../pyproject.toml"]').first();await source.click();
 assert.ok(disk.url().endsWith('/pyproject.toml'));assert.ok((await disk.locator('body').innerText()).includes('requires-python'));
 await disk.goto('file://'+path.join(site,'index.html')+'#architecture/03');
 const offlineDownload=disk.waitForEvent('download');await disk.locator('.diagram-tools [data-download]').click();assert.match((await offlineDownload).suggestedFilename(),/^whetstone-03-/);await disk.close();
 // Proof sheets: all ten SVGs, at legible scale; never shipped as public assets.
 for(const [start,end,name] of [[0,5,'plates-01-05'],[5,10,'plates-06-10']]){
  await page.goto(url+'?theme=cortex-dark#architecture');await page.reload();
  await page.evaluate(({start,end})=>{
    document.querySelector('.sidebar').remove();document.querySelector('.topbar').remove();document.querySelector('.site-footer').remove();document.querySelector('.workspace').style.margin='0';
    document.querySelector('#main').innerHTML='<div id="proof" style="display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:12px">'+window.WhetstoneDiagrams.all.slice(start,end).map(d=>'<div>'+window.WhetstoneDiagrams.render(d.id)+'</div>').join('')+'</div>';
    document.querySelectorAll('#proof svg').forEach(s=>{s.style.width='100%';s.style.display='block';});
  },{start,end});
  await page.setViewportSize({width:1900,height:1650});await page.evaluate(()=>document.fonts.ready);
  await page.locator('#proof').screenshot({path:path.join(out,name+'.jpg'),type:'jpeg',quality:82});
 }
 assert.deepEqual(errors,[]);console.log(`PASS: ${exported} themed exports, embedded fonts, standalone SVG rendering, picker export, remembered themes, inline motion, offline source navigation and export. Proof sheets saved.`);
}finally{await browser.close();}

/** Regenerate the lazy offline SVG-export font bundle from the licensed source fonts. */
import {readFile,writeFile} from 'node:fs/promises';
const fonts=[['Syne','syne-semibold.ttf',600],['Inter','inter-regular.ttf',400],['JetBrains Mono','jetbrains-mono.ttf',400]];
const rules=await Promise.all(fonts.map(async([family,file,weight])=>`@font-face{font-family:'${family}';font-weight:${weight};src:url(data:font/ttf;base64,${(await readFile(new URL('assets/fonts/'+file,import.meta.url))).toString('base64')}) format('truetype')}`));
await writeFile(new URL('font-data.js',import.meta.url),'// Generated from bundled OFL fonts for offline SVG export.\nwindow.WhetstoneFontCSS='+JSON.stringify(rules.join(''))+';\n');

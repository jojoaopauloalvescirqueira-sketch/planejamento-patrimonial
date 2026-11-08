'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),read=p=>fs.readFileSync(path.join(root,p),'utf8');
const source=JSON.parse(read('docs/source-provenance.json'));
for(const p of source.files.filter(x=>x.modification==='none'))assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(root,p.target))).digest('hex'),p.sha256,'Immutable source '+p.target);
for(const p of source.files.filter(x=>x.targetSha256))assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(root,p.target))).digest('hex'),p.targetSha256,'Declared adapted source '+p.target);
for(const f of fs.readdirSync(path.join(root,'dist/assets')).filter(p=>p.endsWith('.js')))new vm.Script(read('dist/assets/'+f),{filename:f});
const index=read('dist/index.html'),build=read('dist/assets/version.js').match(/PP_BUILD="([^"]+)"/)[1];for(const [,url] of index.matchAll(/(?:src|href)="((?:assets\/|favicon)[^"]+)"/g))assert.ok(url.endsWith('?v='+build),'Versioned asset '+url);assert.ok(!/<iframe|serviceWorker|analytics|gtag|googletagmanager/i.test(index));
for(const [,p] of index.matchAll(/(?:src|href)="((?:assets\/|favicon)[^"]+)"/g))assert.ok(fs.existsSync(path.join(root,'dist',p.split('?')[0])),'Asset exists: '+p);
assert.equal([...index.matchAll(/id="planning"/g)].length,1,'One planning host');
assert.ok(!/JP WEALTH|JP Wealth|STOIKUS|Stoikus/.test(read('dist/assets/planning-ui.js')),'Public identity fully separated');
// OOXML identifiers are namespaces, not runtime network destinations.
const allowed=['http://schemas.openxmlformats.org/spreadsheetml/2006/main','http://schemas.openxmlformats.org/officeDocument/2006/relationships','http://schemas.openxmlformats.org/package/2006','http://schemas.openxmlformats.org/drawingml/2006/chart','http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing','http://schemas.openxmlformats.org/drawingml/2006/main','https://api.frankfurter.dev/v2/rate/USD/BRL','http://www.w3.org/2000/svg','https://www.investor.gov/introduction-investing','https://www.investor.gov/additional-resources/information/youth/teachers-classroom-resources/risk-and-return'];
for(const f of fs.readdirSync(path.join(root,'dist/assets')).filter(p=>p.endsWith('.js'))){for(const rawUrl of read('dist/assets/'+f).match(/https?:\/\/[^'"\s<>]+/g)||[]){const url=rawUrl.replace(/\\+$/,'');assert.ok(allowed.includes(url)||url.startsWith('http://www.w3.org/'),'Allowed URL '+url)};}
assert.ok(read('dist/assets/storage.js').includes('planejamento_patrimonial_state_v1'));
assert.ok(!read('dist/assets/storage.js').includes('localStorage.clear('));
console.log('PASS source provenance, syntax, asset closure, independent branding/network, storage scope');

assert.ok(index.indexOf('annual-review.js')>index.indexOf('planning-engine.js')&&index.indexOf('annual-review.js')<index.indexOf('storage.js'),'Annual validation loads before persistence');

// The published tree is generated solely from canonical, versioned sources.
function siteFiles(dir){return fs.readdirSync(dir,{withFileTypes:true}).filter(e=>e.name!=='.DS_Store'&&!e.name.startsWith('._')).flatMap(e=>e.isDirectory()?siteFiles(path.join(dir,e.name)):[path.join(dir,e.name)]);}
const sourceDir=path.join(root,'src/site'),publicDir=path.join(root,'dist');
const canonicalHTML=s=>s.replace(/((?:src|href)="(?:assets\/[^"?]+|favicon\.svg))(?:\?v=[a-f0-9]{16})?("\s*\/?>|"\s)/g,'$1$2');
for(const file of siteFiles(sourceDir)){const relative=path.relative(sourceDir,file),target=path.join(publicDir,relative);assert.ok(fs.existsSync(target),'Generated output '+relative);if(relative==='index.html')assert.equal(canonicalHTML(fs.readFileSync(target,'utf8')),fs.readFileSync(file,'utf8'),'Canonical source index');else assert.deepEqual(fs.readFileSync(target),fs.readFileSync(file),'Canonical source '+relative);}
assert.equal(siteFiles(publicDir).length,siteFiles(sourceDir).length+1,'Only version.js is generated beyond the sources');
console.log('PASS canonical sources match generated application');

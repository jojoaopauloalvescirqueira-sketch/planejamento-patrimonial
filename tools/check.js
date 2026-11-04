'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),read=p=>fs.readFileSync(path.join(root,p),'utf8');
const source=JSON.parse(read('docs/source-provenance.json'));
for(const p of source.files.filter(x=>x.modification==='none'))assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(root,p.target))).digest('hex'),p.sha256,'Immutable source '+p.target);
for(const f of fs.readdirSync(path.join(root,'dist/assets')).filter(p=>p.endsWith('.js')))new vm.Script(read('dist/assets/'+f),{filename:f});
const index=read('dist/index.html');assert.ok(!/<iframe|serviceWorker|analytics|gtag|googletagmanager/i.test(index));
for(const [,p] of index.matchAll(/(?:src|href)="((?:assets\/|favicon)[^"]+)"/g))assert.ok(fs.existsSync(path.join(root,'dist',p)),'Asset exists: '+p);
assert.equal([...index.matchAll(/id="planning"/g)].length,1,'One planning host');
assert.ok(!/JP WEALTH|JP Wealth|STOIKUS|Stoikus/.test(read('dist/assets/planning-ui.js')),'Public identity fully separated');
const allowed=['https://api.frankfurter.dev/v2/rate/USD/BRL','http://www.w3.org/2000/svg','https://www.investor.gov/introduction-investing','https://www.investor.gov/additional-resources/information/youth/teachers-classroom-resources/risk-and-return'];
for(const f of fs.readdirSync(path.join(root,'dist/assets')).filter(p=>p.endsWith('.js'))){for(const rawUrl of read('dist/assets/'+f).match(/https?:\/\/[^'"\s<>]+/g)||[]){const url=rawUrl.replace(/\\+$/,'');assert.ok(allowed.includes(url)||url.startsWith('http://www.w3.org/'),'Allowed URL '+url)};}
assert.ok(read('dist/assets/storage.js').includes('planejamento_patrimonial_state_v1'));
assert.ok(!read('dist/assets/storage.js').includes('localStorage.clear('));
console.log('PASS source provenance, syntax, asset closure, independent branding/network, storage scope');

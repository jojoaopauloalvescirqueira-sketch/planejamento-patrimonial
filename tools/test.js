'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),cp=require('node:child_process'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),out=path.join(root,'outputs');fs.mkdirSync(out,{recursive:true});
const runs=[['build',[process.execPath,'tools/build.js']],['source',[process.execPath,'tools/check.js']],...['planning_engine_test.js','planning_parity_engine_test.js','planning_state_test.js','planning_quote_test.js','storage.test.js'].map(f=>[f,[process.execPath,'tests/'+f]]),['browser',[process.env.PP_PYTHON||'python3','tests/browser.py']]];
const results=[];for(const [id,cmd] of runs){const at=Date.now(),r=cp.spawnSync(cmd[0],cmd.slice(1),{cwd:root,env:process.env,encoding:'utf8',timeout:id==='browser'?600000:60000,maxBuffer:16*1024*1024});fs.writeFileSync(path.join(out,'full-'+id+'.log'),(r.stdout||'')+(r.stderr||''));const status=r.status===0&&!r.error?'PASS':'FAIL';results.push({id,status,exit:r.status,elapsedMs:Date.now()-at,log:'outputs/full-'+id+'.log'});console.log(status,id,Date.now()-at+'ms');if(status!=='PASS')break;}
let status=results.length===runs.length&&results.every(x=>x.status==='PASS')?'PASS':'FAIL';
if(status==='PASS'){
 const browser=JSON.parse(fs.readFileSync(path.join(out,'browser/result.json'),'utf8'));if(browser.status!=='PASS'||browser.checks.length!==15||new Set(browser.checks).size!==15||browser.failures.length)status='FAIL';
 for(const f of ['planning_engine_test.js','planning_parity_engine_test.js','planning_state_test.js','planning_quote_test.js','storage.test.js'])if(!/PASS|"passed":\d+/.test(fs.readFileSync(path.join(out,'full-'+f+'.log'),'utf8')))status='FAIL';
}
function files(dir){return fs.readdirSync(dir,{withFileTypes:true}).flatMap(e=>e.isDirectory()?files(path.join(dir,e.name)):[path.join(dir,e.name)]);}
const hashes={};for(const dir of ['dist','tests','tools','docs'])for(const f of files(path.join(root,dir)).filter(f=>!f.includes('/__pycache__/')))hashes[path.relative(root,f)]=crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex');
fs.writeFileSync(path.join(out,'full-result.json'),JSON.stringify({status,candidate:fs.readFileSync(path.join(root,'dist/assets/version.js'),'utf8').match(/PP_BUILD="([^"]+)"/)[1],results,hashes},null,2));console.log('FULL',status);process.exitCode=status==='PASS'?0:1;

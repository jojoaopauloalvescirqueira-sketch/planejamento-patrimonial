'use strict';
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),cp=require('node:child_process'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..'),sandbox=fs.mkdtempSync(path.join(os.tmpdir(),'pp-netlify-test-'));
let count=0;function pass(name){console.log('PASS NETLIFY '+(++count)+' '+name);}
function run(file,cwd){return cp.spawnSync(process.execPath,[file],{cwd,encoding:'utf8',timeout:30000});}
function fixture(name){const target=path.join(sandbox,name);fs.mkdirSync(target);for(const file of ['src','dist','tools','docs','tests','netlify.toml','package.json','README.md','AGENTS.md','.gitignore','requirements-dev.txt'])fs.cpSync(path.join(root,file),path.join(target,file),{recursive:true,filter:p=>!p.includes('__pycache__')&&!p.endsWith('.DS_Store')});return target;}
try{
 const clean=fixture('clean'),first=run('tools/build.js',clean);assert.equal(first.status,0,first.stderr);const version=fs.readFileSync(path.join(clean,'dist/assets/version.js'),'utf8');pass('clean source builds with versioned dist');
 const cleanOutput=fixture('output-absent');fs.rmSync(path.join(cleanOutput,'dist'),{recursive:true});const rebuilt=run('tools/build.js',cleanOutput);assert.equal(rebuilt.status,0,rebuilt.stderr);assert.equal(fs.readFileSync(path.join(cleanOutput,'dist/assets/version.js'),'utf8'),version);pass('build regenerates the complete application when dist is absent, matching Netlify');
 fs.writeFileSync(path.join(clean,'dist/.DS_Store'),'OS metadata');fs.writeFileSync(path.join(clean,'dist/assets/._app.js'),'OS metadata');assert.equal(run('tools/build.js',clean).status,0);assert.equal(fs.readFileSync(path.join(clean,'dist/assets/version.js'),'utf8'),version);pass('macOS metadata does not change the candidate');
 fs.writeFileSync(path.join(clean,'.env'),'SYNTHETIC_SECRET=not-for-export');fs.mkdirSync(path.join(clean,'outputs'),{recursive:true});fs.writeFileSync(path.join(clean,'outputs/recovery.json'),'SYNTHETIC_RECOVERY');fs.mkdirSync(path.join(clean,'other-local-data'));fs.writeFileSync(path.join(clean,'other-local-data/private.json'),'SYNTHETIC');
 const exported=run('tools/package-netlify.js',clean);assert.equal(exported.status,0,exported.stderr);
 const zip=path.join(clean,'outputs/netlify/planejamento-patrimonial-netlify-fonte.zip'),before=fs.readFileSync(zip),manifest=JSON.parse(fs.readFileSync(path.join(clean,'outputs/netlify/manifest.json'),'utf8'));
 assert.ok(manifest.files.some(f=>f.path==='src/site/index.html'));assert.ok(!manifest.files.some(f=>f.path.startsWith('dist/')));assert.ok(manifest.files.some(f=>f.path==='netlify.toml'));assert.ok(!manifest.files.some(f=>/^(outputs|other-local-data|\.openai)\//.test(f.path)||f.path.endsWith('.DS_Store')||f.path.split('/').some(p=>p.startsWith('._')||p==='.env'||p==='__pycache__')));
 assert.equal(run('tools/package-netlify.js',clean).status,0);assert.deepEqual(fs.readFileSync(zip),before);pass('source ZIP includes canonical sources and configuration without generated dist, excludes operational/private data and is deterministic');
 const extracted=path.join(sandbox,'extracted');fs.mkdirSync(extracted);
 const py=cp.spawnSync(process.env.PP_PYTHON||'python3',['-c',String.raw`import sys,zipfile,json,hashlib,pathlib,tomllib
p=pathlib.Path(sys.argv[1]);manifest=json.loads((p.parent/'manifest.json').read_text());dest=pathlib.Path(sys.argv[2])
with zipfile.ZipFile(p) as z:
 assert z.testzip() is None
 assert len(z.namelist())==len(set(z.namelist()))==len(manifest['files'])
 for f in manifest['files']:assert hashlib.sha256(z.read(f['path'])).hexdigest()==f['sha256']
 z.extractall(dest)
c=tomllib.loads((dest/'netlify.toml').read_text());assert c['build']['command']=='npm run build' and c['build']['publish']=='dist' and c['build']['environment']['NODE_VERSION']=='24.22.2'
assert (dest/'src/site/index.html').is_file() and (dest/'tools/build.js').is_file() and not (dest/'dist').exists()
print('PASS independent ZIP CRC, hashes, extraction and TOML')`,zip,extracted],{encoding:'utf8',timeout:30000});assert.equal(py.status,0,py.stderr);
 assert.equal(run('tools/build.js',extracted).status,0);assert.equal(run('tools/check.js',extracted).status,0);assert.equal(fs.readFileSync(path.join(extracted,'dist/assets/version.js'),'utf8'),version);pass('independent ZIP reader and TOML parse; extracted project builds/checks to the same application');
 const missing=fixture('missing-source');const oldIndex=fs.readFileSync(path.join(missing,'dist/index.html'));fs.rmSync(path.join(missing,'src/site'),{recursive:true});const noSource=run('tools/build.js',missing);assert.notEqual(noSource.status,0);assert.match(noSource.stderr,/Pacote de projeto incompleto/);assert.deepEqual(fs.readFileSync(path.join(missing,'dist/index.html')),oldIndex);assert.equal(fs.existsSync(path.join(missing,'outputs/netlify')),false);pass('missing canonical source fails without replacing output with an empty site');
 const asset=fixture('missing-source-asset');fs.unlinkSync(path.join(asset,'src/site/assets/app.js'));const noAsset=run('tools/package-netlify.js',asset);assert.notEqual(noAsset.status,0);assert.match(noAsset.stderr,/src\/site\/assets\/app.js/);assert.equal(fs.existsSync(path.join(asset,'outputs/netlify')),false);pass('incomplete canonical asset closure is refused before export');
 const partial=fixture('partial-output');fs.unlinkSync(path.join(partial,'dist/assets/app.js'));fs.writeFileSync(path.join(partial,'dist/unwanted-stale.txt'),'SYNTHETIC_STALE');assert.equal(run('tools/build.js',partial).status,0);assert.deepEqual(fs.readFileSync(path.join(partial,'dist/assets/app.js')),fs.readFileSync(path.join(partial,'src/site/assets/app.js')));assert.equal(fs.existsSync(path.join(partial,'dist/unwanted-stale.txt')),false);pass('partial and stale output is regenerated from canonical sources');
 const linked=fixture('symlink');fs.symlinkSync(path.join(linked,'README.md'),path.join(linked,'docs/unexpected-link.md'));const unsafe=run('tools/package-netlify.js',linked);assert.notEqual(unsafe.status,0);assert.match(unsafe.stderr,/links simbólicos/);assert.equal(fs.existsSync(path.join(linked,'outputs/netlify')),false);pass('symlinks cannot pull files outside the source allowlist');
 console.log('PASS '+count+' Netlify package contract groups');
}finally{fs.rmSync(sandbox,{recursive:true,force:true});}

'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {randomUUID} = require('node:crypto');
const ROOT = path.resolve(__dirname, '..');
const KEY = 'planejamento_patrimonial_state_v1';
const PREFIX = 'planejamento_patrimonial_recovery_';
const clone = value => JSON.parse(JSON.stringify(value));
let count = 0;
function test(name, fn) { fn(); count++; console.log('PASS STORE ' + name); }
class Storage {
  constructor() { this.map = new Map(); this.calls = []; this.onGet = null; this.onSet = null; }
  get length() { return this.map.size; }
  key(i) { return [...this.map.keys()][i] || null; }
  getItem(key) { if (this.onGet) this.onGet(key, this); return this.map.has(key) ? this.map.get(key) : null; }
  setItem(key, value) { this.calls.push({key,value}); if (this.onSet) this.onSet(key, value, this); this.map.set(key, String(value)); }
  removeItem(key) { this.map.delete(key); }
}
function boot(storage = new Storage()) {
  const events = {};
  const c = {console, structuredClone, TextEncoder, crypto: {randomUUID}, localStorage: storage,
    addEventListener: (name, fn) => { events[name] = fn; }};
  c.window = c;
  vm.createContext(c);
  for (const name of ['planning-engine.js', 'monthly-inputs.js', 'annual-review.js', 'storage.js', 'planning-state.js', 'backup.js']) {
    vm.runInContext(fs.readFileSync(path.join(ROOT, 'dist/assets', name), 'utf8'), c, {filename: name});
  }
  return {c, storage, events, store: c.PlanningStore, backup: c.PlanningBackup, api: c.JPWPlanning};
}
function config(overrides = {}) {
  return {name: 'Conta sintética', broker: 'Exemplo', login: '123', server: 'Demo', startMonth: '2026-01', initialUsd: 1000,
    profileId: 'base', monthlyContributionUsd: 100, goals: {adequate: null, ideal: {value: 500, currency: 'USD'}}, ...overrides};
}
function create(h, name = 'Conta sintética') { return h.api.commands.execute('createAccount', config({name}), h.api.queries.token()); }
function wrapper(document = {}, revision = 1, writeId = 'other-tab') {
  return JSON.stringify({format: 'planejamento_patrimonial_state', schemaVersion: 1, revision, document, writeId});
}

test('empty reads create no stored facts or recovery', () => {
  const h = boot();
  assert.equal(h.store.status().status, 'READY'); assert.deepEqual(clone(h.c.S), {}); assert.equal(h.storage.calls.length, 0);
});
test('source command uses real adapter, read-back and separate own document', () => {
  const h = boot(), result = create(h);
  assert.equal(result.status, 'CONFIRMED'); assert.equal(h.c.S.patrimonialPlanning.accounts.length, 1);
  assert.deepEqual(JSON.parse(h.storage.getItem(KEY)).document, clone(h.c.S));
  assert.deepEqual(Object.keys(h.c.S), ['patrimonialPlanning']);
  assert.equal(h.store.status().revision, 1);
  assert.equal([...h.storage.map.keys()].filter(k => k.startsWith(PREFIX)).length, 1);
  const journal = JSON.parse([...h.storage.map.entries()].find(([k]) => k.startsWith(PREFIX))[1]);
  assert.equal(journal.outcome, 'confirmed'); assert.equal(journal.previousRaw, null);
});
test('reload recovers confirmed command without issuing a new command', () => {
  const h = boot(); create(h); const raw = h.storage.getItem(KEY), next = boot(h.storage);
  assert.equal(next.c.S.patrimonialPlanning.accounts.length, 1); assert.equal(next.storage.getItem(KEY), raw);
});
test('main quota refusal preserves confirmed RAM and disk', () => {
  const h = boot(); create(h); const old = h.storage.getItem(KEY), ram = JSON.stringify(h.c.S);
  h.storage.onSet = key => { if (key === KEY) throw Error('quota'); };
  const result = create(h, 'Segunda conta');
  assert.equal(result.status, 'REFUSED'); assert.equal(h.storage.getItem(KEY), old); assert.equal(JSON.stringify(h.c.S), ram);
});
test('recovery quota refusal never attempts main write', () => {
  const h = boot(); h.storage.onSet = () => { throw Error('quota'); };
  assert.equal(create(h).status, 'REFUSED'); assert.equal(h.storage.getItem(KEY), null);
  assert.equal(h.storage.calls.filter(item => item.key === KEY).length, 0);
});
test('unknown read-after-write blocks automatic repetition and preserves candidate', () => {
  const h = boot(); let written = false;
  h.storage.onSet = key => { if (key === KEY) written = true; };
  h.storage.onGet = key => { if (key === KEY && written) throw Error('readback'); };
  const result = create(h); assert.equal(result.status, 'UNKNOWN');
  const calls = h.storage.calls.length; assert.equal(create(h).status, 'UNKNOWN'); assert.equal(h.storage.calls.length, calls);
  assert.equal(h.store.status().status, 'UNKNOWN');
  const recovery = h.store.exportRecovery(); assert.equal(recovery.candidateDocument.patrimonialPlanning.accounts.length, 1);
  assert.match(recovery.readError, /indisponível/); assert.deepEqual(clone(h.c.S), {});
  h.storage.onGet = null;
  assert.equal(h.store.reload().status, 'READY'); h.api.commands.resetContext();
  assert.equal(h.c.S.patrimonialPlanning.accounts.length, 1);
});
test('write throws after persistence but exact read-back confirms the real outcome', () => {
  const h = boot(); h.storage.onSet = (key, value, storage) => {
    if (key === KEY) { storage.map.set(key, value); throw Error('after commit'); }
  };
  assert.equal(create(h).status, 'CONFIRMED'); assert.equal(h.c.S.patrimonialPlanning.accounts.length, 1);
});
test('competing raw after write is unknown rather than automatic overwrite retry', () => {
  const h = boot(); let written = false;
  h.storage.onSet = key => { if (key === KEY) written = true; };
  h.storage.onGet = (key, storage) => { if (key === KEY && written) storage.map.set(KEY, wrapper({}, 2, 'competing')); };
  assert.equal(create(h).status, 'UNKNOWN'); assert.equal(h.store.status().status, 'UNKNOWN'); assert.deepEqual(clone(h.c.S), {});
});
test('corrupt/future/foreign wrappers stay opaque and blocked', () => {
  for (const raw of ['{bad', JSON.stringify({format:'planejamento_patrimonial_state',schemaVersion:99,revision:0,document:{},writeId:'future'}),
      JSON.stringify({format:'planejamento_patrimonial_state',schemaVersion:1,revision:0,document:{},writeId:'x',extra:true}),
      wrapper({forex:{}})]) {
    const storage = new Storage(); storage.map.set(KEY, raw); const h = boot(storage);
    assert.equal(h.store.status().status, 'BLOCKED'); assert.notEqual(create(h).status, 'CONFIRMED');
    assert.equal(storage.getItem(KEY), raw); assert.equal(storage.calls.length, 0); assert.equal(h.store.exportRecovery().raw, raw);
  }
});
test('read inaccessible never replaces base with defaults', () => {
  const storage = new Storage(); storage.map.set(KEY, 'preserve'); storage.onGet = key => { if (key === KEY) throw Error('denied'); };
  const h = boot(storage); assert.equal(h.store.status().status, 'BLOCKED'); assert.equal(storage.calls.length, 0);
  assert.equal(h.store.exportRecovery().readError, 'Leitura atual indisponível.');
});
test('strict document validator rejects secrets, prototype fields and nonfinite values', () => {
  const h = boot(); create(h); const source = h.store.exportDocument();
  for (const value of [{foreign:{}}, {...source,password:'secret'}, {patrimonialPlanning:{...source.patrimonialPlanning,credential:'secret'}},
      JSON.parse('{"__proto__":{}}'), {patrimonialPlanning:{...source.patrimonialPlanning,revision:Infinity}}]) {
    assert.throws(() => h.store.validateDocument(value));
  }
});
test('stale epoch refuses before recovery/main write', () => {
  const h = boot(), before = h.storage.calls.length;
  assert.equal(h.c.jpWealthPersistDocument({}, {expectedEpoch: h.store.epoch() - 1}).reason, 'CONFLICT');
  assert.equal(h.storage.calls.length, before);
});
test('second raw comparison detects a race during recovery preparation', () => {
  const h = boot(); let reads = 0;
  h.storage.onGet = (key, storage) => { if (key === KEY && ++reads === 2) storage.map.set(KEY, wrapper({}, 1)); };
  assert.equal(create(h).status, 'CONFLICT'); assert.equal(h.store.status().status, 'CONFLICT'); assert.deepEqual(clone(h.c.S), {});
  assert.equal(h.storage.calls.filter(item => item.key === KEY).length, 0);
});
test('two tabs cannot silently adopt each other; reload is explicit', () => {
  const storage = new Storage(), a = boot(storage), b = boot(storage); const old = b.api.queries.token();
  assert.equal(create(a).status, 'CONFIRMED');
  assert.equal(b.api.commands.execute('createAccount', config({name:'Outra'}), old).status, 'CONFLICT');
  assert.deepEqual(clone(b.c.S), {}); assert.equal(a.c.S.patrimonialPlanning.accounts.length, 1);
  b.events.storage({key: KEY, newValue: storage.getItem(KEY)}); assert.equal(b.store.status().status, 'CONFLICT');
  assert.equal(b.store.reload().status, 'READY'); b.api.commands.resetContext();
  assert.equal(b.c.S.patrimonialPlanning.accounts.length, 1); assert.equal(b.api.commands.execute('createAccount', config(), old).status, 'CONFLICT');
});
test('per-tab recovery preserves another tab recovery and unknown context requires review', () => {
  const storage = new Storage(), a = boot(storage); create(a);
  const first = [...storage.map.entries()].find(([k]) => k.startsWith(PREFIX));
  const b = boot(storage); create(b, 'Segunda'); assert.equal(storage.getItem(first[0]), first[1]);
  assert.equal([...storage.map.keys()].filter(k => k.startsWith(PREFIX)).length, 2);
  assert.equal(b.store.exportRecovery().recoveryCopies.length, 2);
  const pending = JSON.parse(first[1]); pending.outcome='pending'; pending.candidateRaw=wrapper({},99,'interrupted'); storage.map.set(first[0],JSON.stringify(pending));
  const c = boot(storage); assert.equal(c.store.status().status, 'RECOVERY'); assert.notEqual(create(c).status,'CONFIRMED');
  assert.equal(c.store.reload().status,'READY'); assert.equal(storage.getItem(first[0]),JSON.stringify(pending));
});
test('opaque recovery copy cannot hide a later valid pending copy', () => {
  const storage = new Storage(); storage.map.set(KEY, wrapper({}, 1, 'current'));
  const opaqueKey = PREFIX + 'opaque', pendingKey = PREFIX + 'pending';
  const candidateRaw = wrapper({}, 9, 'interrupted');
  const pendingRaw = JSON.stringify({format:'planejamento_patrimonial_recovery',schemaVersion:1,owner:'other-tab',
    at:'2026-11-04T12:00:00.000Z',outcome:'pending',previousRaw:storage.getItem(KEY),candidateRaw});
  storage.map.set(opaqueKey, '{broken'); storage.map.set(pendingKey, pendingRaw);
  const h = boot(storage); assert.equal(h.store.status().status, 'RECOVERY');
  assert.equal(h.store.exportRecovery().recovery.candidateRaw, candidateRaw, 'Discovery must continue after an opaque item');
  assert.notEqual(create(h).status, 'CONFIRMED'); assert.equal(storage.calls.length, 0);
  assert.equal(storage.getItem(opaqueKey), '{broken'); assert.equal(storage.getItem(pendingKey), pendingRaw);
});
test('unreadable recovery copy is a barrier and does not stop discovery', () => {
  const storage = new Storage(); storage.map.set(KEY, wrapper({}, 1, 'current'));
  const unreadableKey = PREFIX + 'unreadable', pendingKey = PREFIX + 'pending';
  storage.map.set(unreadableKey, 'preserve');
  const candidateRaw = wrapper({}, 8, 'pending');
  storage.map.set(pendingKey, JSON.stringify({format:'planejamento_patrimonial_recovery',schemaVersion:1,owner:'other-tab',
    at:'2026-11-04T12:00:00.000Z',outcome:'pending',previousRaw:storage.getItem(KEY),candidateRaw}));
  storage.onGet = key => { if (key === unreadableKey) throw Error('denied'); };
  const h = boot(storage); assert.equal(h.store.status().status, 'RECOVERY');
  const exported = h.store.exportRecovery();
  assert.equal(exported.recovery.candidateRaw, candidateRaw);
  assert.equal(exported.recoveryCopies.some(copy => copy.key === pendingKey && typeof copy.raw === 'string'), true);
  assert.equal(exported.recoveryCopies.some(copy => copy.key === unreadableKey && copy.readError), true);
  assert.match(exported.recoveryReadError, /Nem todas/);
  assert.match(h.store.status().reason, /ileg|interpret|confer|revis/i);
  assert.equal(h.store.reload().status, 'READY', 'Explicit confirmed reload may adopt the valid main base');
  assert.match(h.store.status().reason, /ileg|interpret/i, 'Explicit adoption must retain the unresolved-copy warning');
  assert.equal(storage.map.get(unreadableKey), 'preserve'); assert.equal(storage.calls.length, 0);
});
test('opaque or future recovery alone does not automatically certify readiness', () => {
  for (const raw of ['{broken', JSON.stringify({format:'planejamento_patrimonial_recovery',schemaVersion:2,outcome:'confirmed'})]) {
    const storage = new Storage(); storage.map.set(KEY, wrapper({}, 1, 'current')); storage.map.set(PREFIX + 'opaque', raw);
    const h = boot(storage); assert.equal(h.store.status().status, 'RECOVERY'); assert.equal(storage.calls.length, 0);
    assert.equal(h.store.reload().status, 'READY'); assert.match(h.store.status().reason, /ileg|interpret/i);
    assert.equal(storage.map.get(PREFIX + 'opaque'), raw);
  }
});
test('own backup round-trip preserves accounts, history, preferences and only text drafts', () => {
  const h = boot(); create(h);
  const preferences={theme:'dark',monthly:{version:1,highlightPast:false,fromCurrent:true}};
  const backup=h.backup.create({preferences,drafts:[{label:'Formulário',text:'{"initialUsd":"200"}',token:{revision:999},context:{action:'create'}}]});
  assert.deepEqual(clone(backup.drafts),[{label:'Formulário',text:'{"initialUsd":"200"}'}]);
  const fresh=boot(); const parsed=fresh.backup.inspect(JSON.stringify(backup));
  assert.equal(fresh.storage.calls.length,0); const restored=fresh.backup.restore(parsed,{expectedEpoch:fresh.store.epoch()});
  assert.equal(restored.status,'CONFIRMED'); assert.deepEqual(clone(fresh.c.S),clone(h.c.S));
  assert.deepEqual(clone(restored.preferences),preferences); assert.deepEqual(clone(restored.drafts),clone(backup.drafts));
  assert.equal(Object.keys(restored).includes('token'),false);
});
test('export captures confirmed base, not unrelated unconfirmed RAM', () => {
  const h=boot(); create(h); const expected=h.store.exportDocument(); h.c.S={foreign:'unconfirmed'};
  assert.deepEqual(clone(h.backup.create().document),clone(expected));
});
test('malformed, unknown version, JP fullbackup, invalid document and draft authority are rejected before writes', () => {
  const h=boot(); create(h); const good=clone(h.backup.create()), raw=h.storage.getItem(KEY), calls=h.storage.calls.length;
  const bad=[{}, {...good,schemaVersion:99}, {...good,format:'jpwealth_portable_backup'}, {...good,financial:{}},
    {...good,document:{accounts:[]}}, {...good,document:{patrimonialPlanning:{schemaVersion:2}}},
    {...good,preferences:{theme:'dark'}}, {...good,drafts:[{label:'x',text:'x',token:{}}]}];
  for(const value of bad){assert.throws(()=>h.backup.inspect(JSON.stringify(value)));assert.equal(h.backup.restore(value,{expectedEpoch:h.store.epoch()}).status,'REFUSED');}
  assert.throws(()=>h.backup.inspect('{broken'));assert.throws(()=>h.backup.inspect(' '.repeat(32*1024*1024+1)));
  assert.equal(h.storage.getItem(KEY),raw);assert.equal(h.storage.calls.length,calls);
  assert.throws(()=>h.backup.create({drafts:null}));
});
test('valid restore replaces corrupt raw only under explicit epoch and preserves original recovery', () => {
  const source=boot();create(source);const backup=source.backup.create();const storage=new Storage();storage.map.set(KEY,'{corrupt original');const h=boot(storage);
  assert.equal(h.store.status().status,'BLOCKED');assert.equal(h.backup.restore(backup,{expectedEpoch:h.store.epoch()-1}).reason,'CONFLICT');
  const result=h.backup.restore(backup,{expectedEpoch:h.store.epoch()});assert.equal(result.status,'CONFIRMED');
  const recovery=[...storage.map.entries()].filter(([k])=>k.startsWith(PREFIX)).map(([,v])=>JSON.parse(v));
  assert.equal(recovery.some(r=>r.previousRaw==='{corrupt original'),true);assert.equal(h.c.S.patrimonialPlanning.accounts.length,1);
});
test('backup export detects a newly competing raw and cannot certify stale data',()=>{
  const h=boot();create(h);h.storage.map.set(KEY,wrapper({},55));assert.throws(()=>h.backup.create());assert.equal(h.store.status().status,'CONFLICT');
});
test('revision overflow refuses safely',()=>{
  const storage=new Storage();storage.map.set(KEY,wrapper({},Number.MAX_SAFE_INTEGER));const h=boot(storage);
  assert.equal(create(h).status,'REFUSED');assert.equal(JSON.parse(storage.getItem(KEY)).revision,Number.MAX_SAFE_INTEGER);
});
test('explicit lossless compaction preserves keys, exact Unicode snapshots and financial base; foreign copies stay byte-identical',()=>{
 const h=boot();create(h,'Acentos é 😀 '+String.fromCharCode(0xE000)+' \\ "');const main=h.storage.getItem(KEY),ownKey=[...h.storage.map.keys()].find(k=>k.startsWith(PREFIX)),seed=h.store.inspectRecovery(h.storage.getItem(ownKey));
 h.storage.map.set(ownKey,JSON.stringify({...seed,previousRaw:main,candidateRaw:main}));
 for(let i=0;i<8;i++)h.storage.map.set(PREFIX+'legacy-'+i,JSON.stringify({...seed,owner:'legacy-'+i,previousRaw:main,candidateRaw:main}));
 const keys=[...h.storage.map.keys()].sort(),snapshots=[...h.storage.map].filter(([k])=>k.startsWith(PREFIX)).map(([k,v])=>[k,v,h.store.inspectRecovery(v)]),epoch=h.store.epoch();
 const r=h.store.compactRecovery();assert.equal(r.count,1);assert.equal(r.skippedForeign,8);assert.ok(r.savedChars>10000);assert.deepEqual([...h.storage.map.keys()].sort(),keys);assert.equal(h.storage.getItem(KEY),main);assert.equal(h.store.epoch(),epoch);
 for(const [k,raw,item]of snapshots){assert.deepEqual(clone(h.store.inspectRecovery(h.storage.getItem(k))),clone(item));if(k!==ownKey)assert.equal(h.storage.getItem(k),raw);}
 const beforeCalls=h.storage.calls.length,reopened=boot(h.storage);assert.equal(h.storage.calls.length,beforeCalls,'opening never migrates');const freshEpoch=reopened.store.epoch(),noChange=reopened.store.compactRecovery();assert.equal(noChange.count,0);assert.equal(noChange.savedChars,0);assert.equal(noChange.skippedForeign,9);assert.equal(h.storage.calls.length,beforeCalls);assert.equal(reopened.store.epoch(),freshEpoch);assert.equal(reopened.store.status().status,'READY');assert.match(reopened.store.status().reason,/nenhum espaço foi liberado/);
});
test('foreign recovery quota stays refused without deleting copies or silently retrying',()=>{
 const h=boot();create(h);const main=h.storage.getItem(KEY),item=h.store.inspectRecovery([...h.storage.map].find(([k])=>k.startsWith(PREFIX))[1]);for(let i=0;i<8;i++)h.storage.map.set(PREFIX+'full-'+i,JSON.stringify({...item,owner:'full-'+i,previousRaw:main,candidateRaw:main}));
 const originals=[...h.storage.map],max=originals.reduce((n,[,v])=>n+v.length,0)+500;h.storage.onSet=(k,v,s)=>{const total=[...s.map].filter(([key])=>key!==k).reduce((n,[,raw])=>n+raw.length,0)+v.length;if(total>max)throw Error('QuotaExceededError');};const token=h.api.queries.token();assert.equal(create(h,'Pending').storageReason,'RECOVERY_WRITE_REFUSED');const calls=h.storage.calls.length,r=h.store.compactRecovery();assert.equal(r.count,0);assert.equal(r.savedChars,0);assert.equal(r.skippedForeign,8);assert.equal(h.storage.calls.length,calls);assert.deepEqual([...h.storage.map],originals);assert.equal(h.c.S.patrimonialPlanning.accounts.length,1);assert.equal(h.api.commands.execute('createAccount',config(),token).status,'CONFLICT');assert.equal(create(h,'Reviewed again').storageReason,'RECOVERY_WRITE_REFUSED');assert.equal(h.storage.getItem(KEY),main);
});
test('own verified legacy recovery compacts and frees capacity; only explicit fresh review retries',()=>{
 const h=boot();create(h);const main=h.storage.getItem(KEY),key=[...h.storage.map.keys()].find(k=>k.startsWith(PREFIX)),item=h.store.inspectRecovery(h.storage.getItem(key));h.storage.map.set(key,JSON.stringify({...item,previousRaw:main,candidateRaw:main}));
 let blockRecoveryOnce=true;const max=[...h.storage.map.values()].reduce((n,v)=>n+v.length,0)+30000;h.storage.onSet=(k,v,s)=>{if(blockRecoveryOnce&&k===key){blockRecoveryOnce=false;throw Error('Synthetic journal quota');}const total=[...s.map].filter(([key])=>key!==k).reduce((n,[,raw])=>n+raw.length,0)+v.length;if(total>max)throw Error('QuotaExceededError');};const token=h.api.queries.token();assert.equal(create(h,'Pending').storageReason,'RECOVERY_WRITE_REFUSED');assert.equal(h.storage.getItem(KEY),main);const r=h.store.compactRecovery();assert.equal(r.count,1);assert.equal(r.skippedForeign,0);assert.ok(r.savedChars>10000);assert.equal(h.storage.getItem(KEY),main);assert.equal(h.c.S.patrimonialPlanning.accounts.length,1);assert.equal(h.api.commands.execute('createAccount',config(),token).status,'CONFLICT');assert.equal(create(h,'Reviewed again').status,'CONFIRMED');assert.equal(h.c.S.patrimonialPlanning.accounts.length,2);
});
test('malformed compact dictionaries, references and expansion bombs are blocked and preserved',()=>{
 const h=boot();create(h);const valid=JSON.parse([...h.storage.map].find(([k])=>k.startsWith(PREFIX))[1]);assert.equal(valid.schemaVersion,2);
 const cases=[{...valid,dictionary:[3]},{...valid,candidateRaw:valid.marker},{...valid,candidateRaw:valid.marker+String.fromCharCode(0xD6FF)}, {...valid,dictionary:['"'+'x'.repeat(1024*1024)+'"'],candidateRaw:(valid.marker+String.fromCharCode(0x100)).repeat(33)}];
 for(const value of cases){const storage=new Storage();storage.map.set(KEY,h.storage.getItem(KEY));const text=JSON.stringify(value);storage.map.set(PREFIX+'bad',text);const x=boot(storage);assert.equal(x.store.status().status,'RECOVERY');assert.throws(()=>x.store.inspectRecovery(text));assert.equal(storage.getItem(PREFIX+'bad'),text);}
});
test('pending or opaque copies are never compacted, deleted or silently approved',()=>{
 const h=boot();create(h);const main=h.storage.getItem(KEY),item=h.store.inspectRecovery([...h.storage.map].find(([k])=>k.startsWith(PREFIX))[1]);const pending=JSON.stringify({...item,outcome:'pending',candidateRaw:wrapper({},99,'pending')});h.storage.map.set(PREFIX+'pending',pending);h.storage.map.set(PREFIX+'opaque','{bad');const x=boot(h.storage);assert.equal(x.store.status().status,'RECOVERY');assert.throws(()=>x.store.compactRecovery());x.store.reload();x.store.compactRecovery();assert.equal(h.storage.getItem(PREFIX+'pending'),pending);assert.equal(h.storage.getItem(PREFIX+'opaque'),'{bad');assert.equal(h.storage.getItem(KEY),main);
});
test('compaction readback and concurrent base changes never claim success or modify the financial base',()=>{
 function legacy(){const h=boot();create(h);const key=[...h.storage.map.keys()].find(k=>k.startsWith(PREFIX));h.storage.map.set(key,JSON.stringify(h.store.inspectRecovery(h.storage.getItem(key))));return {h,key,raw:h.storage.getItem(key),main:h.storage.getItem(KEY)};}
 {const {h,key,raw,main}=legacy();h.storage.onSet=()=>{throw Error('quota');};assert.throws(()=>h.store.compactRecovery());assert.equal(h.storage.getItem(key),raw);assert.equal(h.storage.getItem(KEY),main);}
 {const {h,key}=legacy();h.storage.onSet=(k,v,s)=>{s.map.set(k,v);throw Error('after write');};assert.equal(h.store.compactRecovery().count,1);assert.equal(boot(h.storage).store.status().status,'READY');}
 {const {h,key,main}=legacy();let written=false;h.storage.onSet=k=>{if(k===key)written=true;};h.storage.onGet=k=>{if(k===key&&written)throw Error('readback');};assert.throws(()=>h.store.compactRecovery());assert.equal(h.store.status().status,'RECOVERY');assert.equal(h.storage.getItem(KEY),main);assert.notEqual(create(h).status,'CONFIRMED');}
 {const {h,key}=legacy();const other=wrapper({},77,'competing');h.storage.onSet=(k,v,s)=>{if(k===key)s.map.set(KEY,other);};assert.throws(()=>h.store.compactRecovery());assert.equal(h.store.status().status,'CONFLICT');assert.equal(h.storage.getItem(KEY),other);}
});
test('audit: compaction cannot overwrite another instance recovery during a pending transition',()=>{
 const storage=new Storage(),a=boot(storage);create(a);const key=[...storage.map.keys()].find(k=>k.startsWith(PREFIX)),original=JSON.stringify(a.store.inspectRecovery(storage.getItem(key)));storage.map.set(key,original);const b=boot(storage),foreignPending=JSON.stringify({...a.store.inspectRecovery(original),outcome:'pending',candidateRaw:wrapper({},99,'competing-pending')});let writes=0;
 storage.onSet=(k,v,s)=>{if(k===key){writes++;s.map.set(key,foreignPending);}};
 const result=b.store.compactRecovery();assert.equal(writes,0,'Must never write a foreign key; another owner can start a pending write after the last comparison');assert.equal(result.count,0);assert.equal(result.savedChars,0);assert.equal(result.skippedForeign,1);assert.equal(storage.getItem(key),original);
 storage.onSet=null;storage.map.set(key,foreignPending);assert.equal(boot(storage).store.status().status,'RECOVERY');assert.equal(storage.getItem(key),foreignPending);
});
test('audit: own-key owner mismatch, pending and unreadable contents are preserved without writes',()=>{
 for(const kind of ['owner','pending','opaque']){const h=boot();create(h);const key=[...h.storage.map.keys()].find(k=>k.startsWith(PREFIX)),item=h.store.inspectRecovery(h.storage.getItem(key));const raw=kind==='opaque'?'{unreadable':JSON.stringify({...item,previousRaw:h.storage.getItem(KEY),...(kind==='owner'?{owner:'another-runtime'}:{outcome:'pending'})});h.storage.map.set(key,raw);const calls=h.storage.calls.length,r=h.store.compactRecovery();assert.equal(r.count,0);assert.equal(r.savedChars,0);assert.equal(r.skippedForeign,kind==='owner'?1:0);assert.equal(h.storage.calls.length,calls);assert.equal(h.storage.getItem(key),raw);}
});
console.log('PASS storage/backup '+count+' groups');

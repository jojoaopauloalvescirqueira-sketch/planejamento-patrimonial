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
  for (const name of ['planning-engine.js', 'storage.js', 'planning-state.js', 'backup.js']) {
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
  for (const raw of ['{bad', JSON.stringify({format:'planejamento_patrimonial_state',schemaVersion:2,revision:0,document:{},writeId:'future'}),
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
  const bad=[{}, {...good,schemaVersion:2}, {...good,format:'jpwealth_portable_backup'}, {...good,financial:{}},
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
console.log('PASS storage/backup '+count+' groups');

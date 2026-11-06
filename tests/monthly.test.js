'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),{randomUUID}=require('node:crypto');
const ROOT=path.resolve(__dirname,'..'),KEY='planejamento_patrimonial_state_v1';let count=0;
const plain=v=>JSON.parse(JSON.stringify(v));
class Storage{constructor(){this.map=new Map();this.onSet=null;this.onGet=null;}get length(){return this.map.size;}key(i){return [...this.map.keys()][i]||null;}getItem(k){if(this.onGet)this.onGet(k);return this.map.get(k)||null;}setItem(k,v){if(this.onSet)this.onSet(k,v);this.map.set(k,String(v));}removeItem(k){this.map.delete(k);}}
function boot(storage=new Storage()){
 class Clock extends Date{constructor(...args){super(...(args.length?args:['2026-11-04T18:00:00Z']));}static now(){return new Date('2026-11-04T18:00:00Z').getTime();}}
 const c={console,structuredClone,TextEncoder,crypto:{randomUUID},localStorage:storage,Date:Clock,addEventListener(){}};c.window=c;vm.createContext(c);
 for(const f of ['planning-engine.js','monthly-inputs.js','annual-review.js','storage.js','planning-state.js','backup.js'])vm.runInContext(fs.readFileSync(f==='planning-state.js'&&process.env.PP_STATE?process.env.PP_STATE:path.join(ROOT,'dist/assets',f),'utf8'),c);
 const api=c.JPWPlanning;return {c,storage,api,cmd:(type,p)=>api.commands.execute(type,p,api.queries.token(p.accountId)),snapshot:()=>JSON.stringify(c.S)};
}
function account(h,name='Teste'){const r=h.cmd('createAccount',{name,broker:'',login:'',server:'',startMonth:'2026-11',initialUsd:1000,profileId:'base',monthlyContributionUsd:200,goals:{adequate:null,ideal:{value:100,currency:'USD'}}});assert.equal(r.status,'CONFIRMED');return r.accountId;}
function ok(h,t,p){const r=h.cmd(t,p);assert.equal(r.status,'CONFIRMED',JSON.stringify(r));return r;}
function none(h,id,kind,month='2026-11'){return ok(h,'confirmNoMovement',{accountId:id,month,kind,confirmation:true});}
function complete(h,id){ok(h,'recordResult',{accountId:id,month:'2026-11',usd:0});none(h,id,'contribution');none(h,id,'withdrawal');}
function test(name,fn){fn();console.log('PASS MONTHLY '+(++count)+' '+name);}
test('all eight combinations gate preview and command; no write when incomplete',()=>{
 for(let mask=0;mask<8;mask++){
  const h=boot(),id=account(h),p={accountId:id,month:'2026-11',confirmFlows:true};
  if(mask&1)ok(h,'recordResult',{...p,usd:0});if(mask&2)none(h,id,'contribution');if(mask&4)none(h,id,'withdrawal');
  const before=h.snapshot(),disk=h.storage.getItem(KEY),r=h.api.queries.previewFinalizeMonth(p);assert.equal(r.ok,mask===7);
  if(mask!==7){assert.equal(h.cmd('finalizeMonth',p).status,'INVALID');assert.equal(h.snapshot(),before);assert.equal(h.storage.getItem(KEY),disk);}
  else {ok(h,'finalizeMonth',p);assert.equal(h.api.queries.account(id).plan.closures[p.month].snapshot.closeUsd,1000);}
 }
});
test('positive multiple flows count, negative result preserved, no fictitious zero ledger',()=>{
 const h=boot(),id=account(h),p={accountId:id,month:'2026-11'};ok(h,'recordResult',{...p,usd:-20});
 for(const usd of [10,25])ok(h,'recordContribution',{...p,usd,brl:usd*5});ok(h,'recordWithdrawal',{...p,usd:5});
 assert.equal(h.cmd('confirmNoMovement',{...p,kind:'contribution',confirmation:true}).status,'INVALID');ok(h,'finalizeMonth',{...p,confirmFlows:true});
 const plan=h.api.queries.account(id).plan;assert.equal(plan.contributions.length,2);assert.equal(plan.withdrawals.length,1);assert.equal(plan.closures[p.month].snapshot.closeUsd,1010);
});
test('annulment invalidates empty-flow declaration and reopens closure',()=>{
 const h=boot(),id=account(h),p={accountId:id,month:'2026-11'};complete(h,id);ok(h,'finalizeMonth',{...p,confirmFlows:true});ok(h,'recordContribution',{...p,usd:10,brl:50});
 let plan=h.api.queries.account(id).plan;assert.equal(plan.closures[p.month].confirmed,false);assert.equal(plan.monthlyInputs.noMovement[p.month].contribution,undefined);
 ok(h,'recordContribution',{...p,id:plan.contributions[0].id,usd:0,brl:0});assert.equal(h.api.queries.previewFinalizeMonth(p).ok,false);none(h,id,'contribution');assert.equal(h.api.queries.previewFinalizeMonth(p).ok,true);
});
test('explicit confirmation, recognized kinds and past/current only',()=>{
 const h=boot(),id=account(h),before=h.snapshot();for(const change of [{confirmation:false},{kind:'bad'},{month:'2026-12'},{month:'2026-10'}])assert.equal(h.cmd('confirmNoMovement',{accountId:id,month:'2026-11',kind:'withdrawal',confirmation:true,...change}).status,'INVALID');assert.equal(h.snapshot(),before);
});
test('metadata survives exact readback, reopen and backup restore; no automatic closure',()=>{
 const h=boot(),id=account(h);complete(h,id);const before=h.snapshot(),r=boot(h.storage);assert.equal(r.snapshot(),before);
 const backup=r.c.PlanningBackup.create(),fresh=boot();const restored=fresh.c.PlanningBackup.restore(backup,{expectedEpoch:fresh.c.PlanningStore.status().epoch});assert.equal(restored.status,'CONFIRMED',JSON.stringify(restored));assert.equal(fresh.snapshot(),before);assert.equal(fresh.api.queries.account(id).plan.closures['2026-11'],undefined);
 assert.equal(fresh.api.queries.account(id).plan.contributions.length,0);assert.equal(fresh.api.queries.account(id).plan.withdrawals.length,0);
});
test('legacy documents accepted; no implicit zero declarations',()=>{
 const h=boot(),id=account(h);ok(h,'recordResult',{accountId:id,month:'2026-11',usd:0});const doc=plain(h.c.S);assert.equal(h.c.PlanningStore.validateDocument(doc).patrimonialPlanning.accounts.length,1);assert.equal(h.api.queries.previewFinalizeMonth({accountId:id,month:'2026-11'}).ok,false);
 complete(h,id);ok(h,'finalizeMonth',{accountId:id,month:'2026-11',confirmFlows:true});const legacy=plain(h.c.S);delete legacy.patrimonialPlanning.accounts[0].plan.monthlyInputs;delete legacy.patrimonialPlanning.accounts[0].plan.closures['2026-11'].recordsReview;assert.doesNotThrow(()=>h.c.PlanningStore.validateDocument(legacy));
});
test('malformed/imported metadata refused before adoption, archive included',()=>{
 const h=boot(),id=account(h);complete(h,id);const backup=h.c.PlanningBackup.create();
 const changes=[m=>m.version=2,m=>m.noMovement['2026-11'].withdrawal.revision=0,m=>m.noMovement['2026-11'].contribution.confirmedAt='bad',m=>m.noMovement['2026-10']=m.noMovement['2026-11'],m=>m.noMovement['2026-11'].result={confirmedAt:new Date().toISOString(),revision:1}];
 for(const change of changes){const bad=plain(backup);change(bad.document.patrimonialPlanning.accounts[0].plan.monthlyInputs);assert.throws(()=>h.c.PlanningBackup.inspect(JSON.stringify(bad)));}
 const bad=plain(backup);bad.document.patrimonialPlanning.accounts[0].plan.contributions.push({id:'x',month:'2026-11',usd:1,brl:5,revision:1});assert.throws(()=>h.c.PlanningBackup.inspect(JSON.stringify(bad)));
});
test('quota refusal preserves missing field and never enables closure',()=>{
 const h=boot(),id=account(h),before=h.snapshot();h.storage.onSet=k=>{if(k===KEY)throw Error('quota');};assert.equal(h.cmd('confirmNoMovement',{accountId:id,month:'2026-11',kind:'withdrawal',confirmation:true}).status,'REFUSED');assert.equal(h.snapshot(),before);assert.equal(h.api.monthlyInputs.status(h.api.queries.account(id).plan,'2026-11').withdrawal,false);
});
test('unknown readback preserves candidate and blocks automatic repetition',()=>{
 const h=boot(),id=account(h),before=h.snapshot();let written=false;h.storage.onSet=k=>{if(k===KEY)written=true;};h.storage.onGet=k=>{if(k===KEY&&written)throw Error('readback');};const p={accountId:id,month:'2026-11',kind:'withdrawal',confirmation:true};assert.equal(h.cmd('confirmNoMovement',p).status,'UNKNOWN');assert.equal(h.snapshot(),before);assert.equal(h.cmd('confirmNoMovement',p).status,'UNKNOWN');assert.equal(h.cmd('finalizeMonth',{...p,confirmFlows:true}).status,'UNKNOWN');
});
test('stale tab token rejects zero confirmation without overwriting other data',()=>{
 const h=boot(),id=account(h),other=boot(h.storage);ok(other,'recordResult',{accountId:id,month:'2026-11',usd:30});const disk=h.storage.getItem(KEY);assert.equal(h.cmd('confirmNoMovement',{accountId:id,month:'2026-11',kind:'withdrawal',confirmation:true}).status,'CONFLICT');assert.equal(h.storage.getItem(KEY),disk);
});
test('accounts independent; explicit reopening never deletes financial history',()=>{
 const h=boot(),a=account(h),b=account(h,'Outra');complete(h,a);assert.equal(h.api.monthlyInputs.status(h.api.queries.account(b).plan,'2026-11').withdrawal,false);ok(h,'finalizeMonth',{accountId:a,month:'2026-11',confirmFlows:true});ok(h,'reopenMonth',{accountId:a,month:'2026-11',reason:'Conferência'});assert.equal(h.api.queries.account(a).plan.results['2026-11'].usd,0);assert.equal(h.api.queries.account(a).plan.closures['2026-11'].confirmed,false);
});
console.log('PASS '+count+' monthly contract groups');

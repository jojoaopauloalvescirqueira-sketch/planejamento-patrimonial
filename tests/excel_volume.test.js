'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const context = vm.createContext({structuredClone, TextEncoder, Blob});
context.window = context;
for (const file of ['planning-engine', 'monthly-inputs', 'excel-model', 'excel-writer']) {
  vm.runInContext(fs.readFileSync(__dirname + '/../dist/assets/' + file + '.js', 'utf8'),context);
}
const app = context.JPWPlanning;
const envelope = {schemaVersion:1, revision:1, accounts:[], archive:[], audit:[], operations:[]};
const options = {month:'2026-11', at:'2026-11-08T13:00:00Z', version:'synthetic', revision:1};
function create(i) {
  const config = {startMonth:'2026-11', initialUsd:1000, monthlyContributionUsd:200, profileId:'base',
    goals:{adequate:null, ideal:{value:100,currency:'USD'}}};
  return {id:'acc'+i, name:'Conta fictícia '+i, active:true, plan:app.engine.createPlan(config,{id:'plan'+i, now:options.at})};
}
envelope.accounts.push(create(0));
const one = app.excelModel.prepare({patrimonialPlanning:envelope},options);
assert.equal(one[0].metrics[0],1000);
assert.equal(one[1].rows.length,120);
assert.equal(one[5].rows[0][4],1230);
assert.equal(one[5].rows[1][4],1466.9);
for (let i=1; i<64; i++) envelope.accounts.push(create(i));
const full = app.excelModel.prepare({patrimonialPlanning:envelope},options);
assert.equal(full[1].rows.length,7680);
assert.equal(full[0].metrics[0],64000);
assert.ok(app.excelWriter.workbook(full,options).size > 1000000);
console.log('PASS Excel single account and 64 accounts with 7,680 monthly rows');

/* Explicit empty-flow facts. Financial calculations remain in the original engine. */
(function (root) {
  'use strict';
  const planning = root.JPWPlanning = root.JPWPlanning || {};
  const own = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
  const object = v => v && typeof v === 'object' && !Array.isArray(v);
  const exact = (v, keys) => object(v) && Object.keys(v).sort().join(',') === keys.sort().join(',');
  const ledger = (plan, kind) => plan[kind === 'contribution' ? 'contributions' : 'withdrawals'];
  const positive = (plan, month, kind) => (ledger(plan, kind) || []).some(x => x.month === month && x.usd > 0);
  function status(plan, month) {
    const empty = plan.monthlyInputs && plan.monthlyInputs.noMovement[month] || {};
    return {result: own(plan.results || {}, month), contribution: positive(plan, month, 'contribution') || !!empty.contribution,
      withdrawal: positive(plan, month, 'withdrawal') || !!empty.withdrawal};
  }
  const stable = v => Array.isArray(v) ? '['+v.map(stable).join(',')+']' : object(v) ? '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+stable(v[k])).join(',')+'}' : JSON.stringify(v);
  function review(plan, month) {
    const flows = kind => (ledger(plan,kind)||[]).filter(r=>r.month===month).map(r=>({id:r.id,revision:r.revision,usd:r.usd,brl:r.brl??null})).sort((a,b)=>a.id.localeCompare(b.id));
    const result=plan.results[month];
    return {version:1,month,result:{usd:result.usd,revision:result.revision},contributions:flows('contribution'),withdrawals:flows('withdrawal'),noMovement:structuredClone(plan.monthlyInputs?.noMovement[month]||{})};
  }
  function validReview(value, month) {
    const revision=v=>Number.isSafeInteger(v)&&v>0, amount=v=>Number.isFinite(v), cents=v=>amount(v)&&Number.isSafeInteger(Math.round(v*100))&&Math.abs(v*100-Math.round(v*100))<1e-6;
    if(!exact(value,['version','month','result','contributions','withdrawals','noMovement'])||value.version!==1||value.month!==month||
      !exact(value.result,['usd','revision'])||!cents(value.result.usd)||!revision(value.result.revision)||!object(value.noMovement))return false;
    for(const kind of ['contributions','withdrawals']){
      const list=value[kind];if(!Array.isArray(list)||new Set(list.map(r=>r?.id)).size!==list.length||list.some(r=>!exact(r,['id','revision','usd','brl'])||typeof r.id!=='string'||!r.id||!revision(r.revision)||!amount(r.usd)||r.usd<0||!(r.brl===null||amount(r.brl)&&r.brl>=0)))return false;
    }
    return Object.entries(value.noMovement).every(([kind,r])=>['contribution','withdrawal'].includes(kind)&&exact(r,['confirmedAt','revision'])&&revision(r.revision)&&typeof r.confirmedAt==='string'&&Number.isFinite(Date.parse(r.confirmedAt)));
  }
  function closureErrors(plan) {
    const errors=[];
    for(const [month,closure] of Object.entries(plan.closures||{})){
      let c=closure,depth=0;
      while(c&&c.recordsReview!==undefined){
        if(++depth>200||!validReview(c.recordsReview,month)){errors.push('Referências do fechamento inválidas em '+month+'.');break;}
        if(c.previous&&(!object(c.previous)||c.previous.revision>=c.revision)){errors.push('Histórico de fechamento inválido em '+month+'.');break;}
        c=c.previous;
      }
      if(closure.confirmed&&closure.recordsReview!==undefined){
        const filled=status(plan,month);
        if(!filled.result||!filled.contribution||!filled.withdrawal||stable(closure.recordsReview)!==stable(review(plan,month)))errors.push('O fechamento não corresponde aos registros de '+month+'.');
      }
    }
    return errors;
  }
  function validatePlan(plan) {
    if (!object(plan)) return [];
    const errors=closureErrors(plan);
    if(plan.monthlyInputs === undefined)return errors;
    const m = plan.monthlyInputs;
    if (!exact(m, ['version', 'noMovement']) || m.version !== 1 || !object(m.noMovement)) return ['Confirmações mensais incompatíveis.'];
    for (const [month, fields] of Object.entries(m.noMovement)) {
      if (planning.engine.monthKey(month) !== month || month < plan.startMonth || month > planning.engine.addMonths(plan.startMonth, 119) || !object(fields) ||
          !Object.keys(fields).length || Object.keys(fields).some(k => !['contribution', 'withdrawal'].includes(k))) {
        errors.push('Mês ou campo de confirmação inválido.'); continue;
      }
      for (const [kind, entry] of Object.entries(fields)) {
        if (!exact(entry, ['confirmedAt', 'revision']) || typeof entry.confirmedAt !== 'string' || !Number.isFinite(Date.parse(entry.confirmedAt)) ||
            !Number.isSafeInteger(entry.revision) || entry.revision < 1 || positive(plan, month, kind)) errors.push('Confirmação de ausência de movimento inválida.');
      }
    }
    return errors;
  }
  function validateEnvelope(value) {
    if (!object(value)) return [];
    return [...(value.accounts || []).flatMap(a => validatePlan(a && a.plan)), ...(value.archive || []).flatMap(a => validatePlan(a && a.plan))];
  }
  function invalidate(plan, month, kind) {
    const months = plan.monthlyInputs && plan.monthlyInputs.noMovement;
    if (!months || !months[month]) return;
    delete months[month][kind];
    if (!Object.keys(months[month]).length) delete months[month];
  }
  function confirm(plan, month, kind, at) {
    if (!['contribution', 'withdrawal'].includes(kind) || positive(plan, month, kind)) throw Error('Há movimentos registrados. Confira os lançamentos antes de confirmar ausência.');
    if (!plan.monthlyInputs) plan.monthlyInputs = {version: 1, noMovement: {}};
    const fields = plan.monthlyInputs.noMovement[month] || (plan.monthlyInputs.noMovement[month] = {}), previous = fields[kind] || null;
    fields[kind] = {confirmedAt: at, revision: (previous ? previous.revision : 0) + 1};
    return previous;
  }
  planning.monthlyInputs = Object.freeze({status, review, validateEnvelope, confirm, invalidate});
})(window);

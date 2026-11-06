/* Annual declarations bind confirmed monthly revisions, never projected facts. */
(function(root){
  'use strict';
  const planning=root.JPWPlanning=root.JPWPlanning||{},E=planning.engine;
  const object=v=>!!v&&typeof v==='object'&&!Array.isArray(v),finite=Number.isFinite,clone=structuredClone;
  const declaration='Declaro que revisei todos os registros de Resultado, Saque e Aporte deste período, que as informações foram preenchidas por mim e são verdadeiras conforme meus registros. Confirmo o encerramento deste ano.';
  function stable(v){return Array.isArray(v)?'['+v.map(stable).join(',')+']':object(v)?'{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+stable(v[k])).join(',')+'}':JSON.stringify(v);}
  function periods(plan){
    if(!object(plan)||!E.monthKey(plan.startMonth))return [];
    const groups=[];
    for(let i=0;i<120;i++){const month=E.addMonths(plan.startMonth,i),year=month.slice(0,4);let g=groups[groups.length-1];if(!g||g.year!==year){g={year,startMonth:month,endMonth:month,months:[]};groups.push(g);}g.endMonth=month;g.months.push(month);}
    return groups;
  }
  function sourceRefs(plan,period){
    const flows=(key,month)=>(plan[key]||[]).filter(r=>r.month===month).map(r=>({id:r.id,revision:r.revision,usd:r.usd,brl:r.brl??null})).sort((a,b)=>a.id.localeCompare(b.id));
    return period.months.map(month=>({month,closureRevision:plan.closures[month]?.revision??null,resultRevision:plan.results[month]?.revision??null,resultUsd:plan.results[month]?.usd??null,
      fxQuote:clone(plan.closures[month]?.fxQuote??null),contributions:flows('contributions',month),withdrawals:flows('withdrawals',month),noMovement:clone(plan.monthlyInputs?.noMovement[month]||{})}));
  }
  function totals(rows){
    const a=E.annual(rows)[0];if(!a)return {openUsd:null,closeUsd:null,resultUsd:null,contributionUsd:null,withdrawalUsd:null,rate:null};
    return Object.fromEntries(['openUsd','closeUsd','resultUsd','contributionUsd','withdrawalUsd','rate'].map(k=>[k,finite(a[k])?a[k]:null]));
  }
  function entry(plan,year){return plan.annualClosures?.years?.[year]||null;}
  function previousPending(plan,year){return periods(plan).find(p=>p.year<year&&entry(plan,p.year)?.confirmed!==true)?.year||null;}
  function guard(plan,month){
    const year=String(month).slice(0,4),prior=previousPending(plan,year);
    if(prior)return {code:'PREVIOUS_YEAR_UNCONFIRMED',year:prior,message:'Encerre o ano de '+prior+' antes de registrar informações efetivas em '+year+'.'};
    if(entry(plan,year)?.confirmed===true)return {code:'YEAR_CLOSED',year,message:'Reabra o ano de '+year+' com um motivo antes de alterar seus registros.'};
    return null;
  }
  function overview(account,year,today){
    const plan=account.plan,period=periods(plan).find(p=>p.year===String(year));if(!period)throw Error('Ano fora do período deste plano.');
    const rows=E.timeline(plan,{month:today,balancePolicy:'confirmed-projection'}).filter(r=>r.month.slice(0,4)===period.year),closed=rows.filter(r=>r.finalized),record=entry(plan,period.year);
    const summary=totals(closed),all=closed.length===period.months.length,prior=previousPending(plan,period.year);
    const reviewKey=stable({accountId:account.id,planId:plan.id,period,summary,monthRevisions:sourceRefs(plan,period)});
    const blockers=[];if(prior)blockers.push({code:'PREVIOUS_YEAR_UNCONFIRMED',year:prior,message:'Encerre primeiro o ano de '+prior+'.'});
    if(!all)blockers.push({code:'MONTHS_UNCONFIRMED',months:rows.filter(r=>!r.finalized).map(r=>r.month),message:'Finalize todos os meses deste período antes de encerrar o ano.'});
    if(period.endMonth>today)blockers.push({code:'FUTURE_PERIOD',message:'O último mês deste período ainda é futuro.'});
    if(all&&Object.values(summary).some(v=>v===null))blockers.push({code:'NOT_COMPUTABLE',message:'O resumo anual não está calculável.'});
    if(record?.confirmed)blockers.push({code:'ALREADY_CLOSED',message:'Este ano já está encerrado.'});
    return {year:period.year,startMonth:period.startMonth,endMonth:period.endMonth,totalMonths:period.months.length,closedMonths:closed.length,partialPeriod:period.months.length<12,
      summary,initialUsd:rows[0]?.openUsd??null,projection:rows.every(r=>r.projectionStatus!=='WAITING_CLOSURE'&&finite(r.closeUsd)&&finite(r.resultUsd))?totals(rows):null,
      closed:record?.confirmed===true,record:record?clone(record):null,blockers,ok:!blockers.length,reviewKey,monthRevisions:sourceRefs(plan,period),declaration,declarationVersion:1};
  }
  function seal(account,input,today,at){
    const preview=overview(account,input.year,today);
    if(!preview.ok)throw Error(preview.blockers.map(b=>b.message).join(' '));
    if(input.declarationAccepted!==true)throw Error('Marque a declaração de revisão anual.');
    const name=typeof input.signerName==='string'?input.signerName.trim():'';
    if(name.length<2||name.length>150)throw Error('Informe seu nome completo, com até 150 caracteres.');
    if(input.reviewKey!==preview.reviewKey)throw Error('Os registros mudaram após a revisão anual. Confira novamente.');
    const plan=account.plan,previous=entry(plan,preview.year);
    if(!plan.annualClosures)plan.annualClosures={version:1,years:{}};
    plan.annualClosures.years[preview.year]={version:1,accountId:account.id,planId:plan.id,accountName:account.name,year:preview.year,startMonth:preview.startMonth,endMonth:preview.endMonth,
      confirmed:true,revision:(previous?.revision||0)+1,confirmedAt:at,signerName:name,declarationVersion:1,declaration,summary:preview.summary,monthRevisions:preview.monthRevisions,
      ...(previous?{previous:clone(previous)}:{})};
    return previous;
  }
  function invalidateFrom(plan,year,at,reason){
    const changed=[];
    for(const [key,value] of Object.entries(plan.annualClosures?.years||{}))if(key>=year&&value.confirmed){
      plan.annualClosures.years[key]={...value,confirmed:false,revision:value.revision+1,invalidatedAt:at,invalidationReason:reason,previous:clone(value)};changed.push(key);
    }
    return changed.sort();
  }
  function validatePlan(plan,accountId){
    if(!object(plan)||plan.annualClosures===undefined)return [];
    const errors=[],data=plan.annualClosures;
    if(!object(data)||data.version!==1||!object(data.years)||Object.keys(data).some(k=>!['version','years'].includes(k)))return ['Encerramentos anuais incompatíveis.'];
    const range=periods(plan);
    for(const [year,value] of Object.entries(data.years)){
      const period=range.find(p=>p.year===year);let r=value,depth=0;
      while(r){
        const keys=['version','accountId','planId','accountName','year','startMonth','endMonth','confirmed','revision','confirmedAt','signerName','declarationVersion','declaration','summary','monthRevisions','previous','invalidatedAt','invalidationReason'];
        if(++depth>200||!period||!object(r)||Object.keys(r).some(k=>!keys.includes(k))||r.version!==1||r.accountId!==accountId||r.planId!==plan.id||typeof r.accountName!=='string'||
          r.year!==year||r.startMonth!==period.startMonth||r.endMonth!==period.endMonth||typeof r.confirmed!=='boolean'||!Number.isSafeInteger(r.revision)||r.revision<1||
          typeof r.signerName!=='string'||r.signerName.trim().length<2||r.signerName.length>150||typeof r.confirmedAt!=='string'||!finite(Date.parse(r.confirmedAt))||r.declarationVersion!==1||r.declaration!==declaration||
          !object(r.summary)||Object.keys(r.summary).sort().join(',')!=='closeUsd,contributionUsd,openUsd,rate,resultUsd,withdrawalUsd'||Object.values(r.summary).some(v=>!finite(v))||
          !Array.isArray(r.monthRevisions)||r.monthRevisions.length!==period.months.length||r.monthRevisions.some((m,i)=>!object(m)||m.month!==period.months[i])||
          (!r.confirmed&&(typeof r.invalidatedAt!=='string'||!finite(Date.parse(r.invalidatedAt))||typeof r.invalidationReason!=='string'||!r.invalidationReason.trim()))){errors.push('Termo anual inválido em '+year+'.');break;}
        if(r.previous&&(!object(r.previous)||r.previous.revision>=r.revision)){errors.push('Histórico do termo anual inválido em '+year+'.');break;}
        r=r.previous;
      }
      if(period&&object(value)&&value.confirmed){
        try{const rows=E.timeline(plan,{month:period.endMonth,balancePolicy:'confirmed-projection'}).filter(r=>r.month.slice(0,4)===year);
          if(previousPending(plan,year)||rows.some(r=>!r.finalized)||stable(value.monthRevisions)!==stable(sourceRefs(plan,period))||stable(value.summary)!==stable(totals(rows)))errors.push('O termo anual não corresponde aos meses confirmados de '+year+'.');
        }catch(_){errors.push('Não foi possível conferir o termo anual de '+year+'.');}
      }
    }
    return errors;
  }
  function validateEnvelope(v){if(!object(v))return [];return [...(Array.isArray(v.accounts)?v.accounts:[]).flatMap(a=>validatePlan(a?.plan,a?.id)),...(Array.isArray(v.archive)?v.archive:[]).flatMap(a=>validatePlan(a?.plan,a?.accountId||a?.id))];}
  planning.annualReview=Object.freeze({declaration,periods,overview,guard,seal,invalidateFrom,validateEnvelope});
})(window);

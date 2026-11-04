function jpWealthPersistDocument(state,options){
  const opt=options||{},component=opt.component||'state';
  const result=(status,reason,error)=>{
    if(status==='UNKNOWN'&&!jpWealthPersistenceOutcomeUnknown)markJPWealthPersistenceOutcomeUnknown(reason);
    const r=jpWealthPersistenceSetResult(status,reason,component,error);
    if(reason==='WRITE_REFUSED'||reason==='SERIALIZE'){
      const message=reason==='SERIALIZE'?'JP Wealth: falha ao preparar (serializar) o estado para gravação.':'JP Wealth: falha ao gravar o estado no armazenamento local.';
      try{console.error(message,error||new Error(reason));}catch(ignored){}
    }
    // Deliberate guards already have their own recovery/modal explanation.
    // Creating a second storage-error banner would misstate the cause and hide controls.
    if(!opt.silent&&reason!=='LOAD_RECOVERY'&&reason!=='BLOCKED')jpWealthPersistenceSafeFeedback(r);
    return r;
  };
  if(jpWealthPersistenceOutcomeUnknown)return result('UNKNOWN','PENDING_VERIFICATION');
  if(opt.expectedEpoch!==undefined&&opt.expectedEpoch!==jpWealthSessionEpoch)return result('REFUSED','CONTEXT_CHANGED');
  if(jpWealthLoadRecovery.active)return result('REFUSED','LOAD_RECOVERY');
  if(jpWealthPersistenceBlocked&&!opt.allowBlocked)return result('REFUSED','BLOCKED');
  if(state?.workspaceRecovery?.pending&&!(typeof jpwWorkspaceRestoring!=='undefined'&&jpwWorkspaceRestoring)&&!opt.allowWorkspaceRecovery)return result('REFUSED','WORKSPACE_RECOVERY');
  if(!state||typeof state!=='object'||Array.isArray(state))return result('REFUSED','INVALID_ROOT');
  let payload,before;
  try{
    payload=JSON.stringify(state,(k,v)=>k==='investorPassword'?'':v);
    const root=JSON.parse(payload);
    if(!root||typeof root!=='object'||Array.isArray(root))throw new Error('A serialização não produziu um documento JSON.');
  }
  catch(error){return result('REFUSED','SERIALIZE',error);}
  try{before=localStorage.getItem(LSKEY);}
  catch(error){return result('REFUSED','READ_BEFORE_WRITE',error);}
  const expected=Object.prototype.hasOwnProperty.call(opt,'expectedRaw')?opt.expectedRaw:jpWealthLastPersistedRaw;
  if(before!==expected)return result('REFUSED','CONFLICT',new Error('Outra aba atualizou a base. A escrita foi recusada.'));
  let writeError=null;
  try{localStorage.setItem(LSKEY,payload);}
  catch(error){writeError=error;}
  let actual;
  try{actual=localStorage.getItem(LSKEY);}
  catch(error){return result('UNKNOWN','READ_AFTER_WRITE',error);}
  if(actual===payload){
    jpWealthAdoptPersistedRaw(payload);
    return {...result('CONFIRMED','READBACK_MATCH'),payload};
  }
  if(actual===before)return result('REFUSED',writeError?'WRITE_REFUSED':'WRITE_NOT_APPLIED',writeError||new Error('A escrita não foi aplicada.'));
  return result('UNKNOWN','READBACK_DIVERGED',writeError||new Error('A releitura divergiu da escrita e da base anterior.'));
}

function jpWealthConfirmedStateSnapshot(){}

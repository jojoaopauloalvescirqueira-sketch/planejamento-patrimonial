"""Standalone actual-browser contract. All financial records are synthetic."""
import contextlib,functools,json,math,os,tempfile,threading,traceback
from pathlib import Path
from datetime import datetime,timezone
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from playwright.sync_api import sync_playwright
import reference_ui as reference
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/browser';OUT.mkdir(parents=True,exist_ok=True)
class Quiet(SimpleHTTPRequestHandler):
 def log_message(self,*_):pass
class Server(ThreadingHTTPServer):request_queue_size=128
server=Server(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT/'dist')));threading.Thread(target=server.serve_forever,daemon=True).start();URL=f'http://127.0.0.1:{server.server_port}/'
report={'status':'PRODUCT_FAIL','checks':[],'failures':[],'limits':['Synthetic contexts; Safari, physical touch and manual screen reader NOT_RUN.']}
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('PP_CHROMIUM'))
 def boot(width=1440,height=1000,context=None,fx=True):
  ctx=context or browser.new_context(viewport={'width':width,'height':height},timezone_id='America/Sao_Paulo',reduced_motion='reduce',service_workers='block');unexpected=[]
  def route(r):
   if r.request.url.startswith('https://api.frankfurter.dev/'):
    if fx:r.fulfill(content_type='application/json',body=json.dumps({'base':'USD','quote':'BRL','date':'2026-11-03','rate':5}))
    else:r.abort('failed')
   elif r.request.url.startswith(URL):r.continue_()
   else:unexpected.append(r.request.url);r.abort('blockedbyclient')
  ctx.route('**/*',route);page=ctx.new_page();page.set_default_timeout(8000);page.clock.set_fixed_time(datetime(2026,11,4,18,tzinfo=timezone.utc));errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto(URL,wait_until='load');page.wait_for_selector('[data-pl-start]');return ctx,page,errors,unexpected
 def check(name,fn):
  try:fn();report['checks'].append(name)
  except Exception as e:report['failures'].append({'case':name,'error':str(e),'traceback':traceback.format_exc()})
 def source_journey(fn):
  ctx,page,errors,network=boot()
  try:
   fn(page);assert not errors,errors;assert not network,network
  finally:ctx.close()
 with (OUT/'source-journeys.log').open('w') as log,contextlib.redirect_stdout(log):
  for name in ['start_journey','form_journey','consolidated_journey','monthly_journey','reference_journey','reset_counts_journey','invalidated_stop_draft_journey','fx_edit_journey','pdf_scope_journey']:
   check('SOURCE-'+name,lambda name=name:source_journey(getattr(reference,name)))
 def geometry(page):
  m=page.evaluate('''()=>{const visible=e=>!!e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden';const rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height,right:r.right,bottom:r.bottom}};
   const controls=[...document.querySelectorAll('button,select,a')].filter(visible).map(e=>({label:e.getAttribute('aria-label')||e.textContent.trim(),...rect(e)}));
   const dialogs=[...document.querySelectorAll('dialog[open]')].map(rect);const centers=[...document.querySelectorAll('.pl-button,.site-actions button,.data-body button')].filter(visible).filter(e=>!e.children.length&&getComputedStyle(e).justifyContent==='center').map(e=>{const r=e.getBoundingClientRect(),range=document.createRange();range.selectNodeContents(e);const t=range.getBoundingClientRect();return {label:e.textContent.trim(),dx:Math.abs(r.x+r.width/2-t.x-t.width/2),dy:Math.abs(r.y+r.height/2-t.y-t.height/2)}});return {width:innerWidth,height:innerHeight,overflow:document.documentElement.scrollWidth>innerWidth,controls,dialogs,centers}}''')
  assert not m['overflow'],m
  for d in m['dialogs']:assert d['x']>=-1 and d['y']>=-1 and d['right']<=m['width']+1 and d['bottom']<=m['height']+1,('dialog outside viewport',m)
  for c in m['centers']:assert c['dx']<=2 and c['dy']<=2,('Internal content alignment exceeds2px',c)
  for c in m['controls']:
   # Brand link is a two-line wordmark with the original minimum target height.
   assert c['w']>=43.9 and c['h']>=43.9,('Target below44px',c)
  return m
 def visual():
  ctx,page,errors,network=boot()
  try:
   reference.seed(page)
   for theme in ['light','dark']:
    page.evaluate('(t)=>document.documentElement.dataset.theme=t',theme)
    for width in [320,390,820,1440]:
     page.set_viewport_size({'width':width,'height':700 if width<500 else 1000});page.evaluate("JPWPlanning.ui.selectView('consolidated')");page.wait_for_timeout(80);geometry(page)
     page.screenshot(path=str(OUT/f'consolidado-{theme}-{width}.png'),full_page=True)
     page.get_by_role('tab',name='Preenchimento mensal',exact=True).click();page.wait_for_timeout(80);geometry(page)
     page.screenshot(path=str(OUT/f'mensal-{theme}-{width}.png'),full_page=True)
   page.set_viewport_size({'width':320,'height':560});page.get_by_role('tab',name='Comece aqui',exact=True).click();page.get_by_role('button',name='Preencher novo formulário',exact=True).click();page.wait_for_timeout(50);geometry(page);page.keyboard.press('Escape')
   assert not errors,errors;assert not network,network
  finally:ctx.close()
 check('VISUAL-two themes four widths, monthly/consolidated,320low-height modal and44px targets',visual)
 def persistence():
  ctx,page,errors,network=boot()
  try:
   reference.form_journey(page);snapshot=page.evaluate('JSON.stringify(JPWPlanning.queries.snapshot())');page.reload(wait_until='load');page.wait_for_selector('[data-pl-start]');assert page.evaluate('JSON.stringify(JPWPlanning.queries.snapshot())')==snapshot
   page.locator('#data-button').click()
   with page.expect_download() as download:page.locator('#export-button').click()
   file=download.value.path();payload=Path(file).read_bytes();value=json.loads(payload);assert value['format']=='planejamento_patrimonial_backup' and len(value['document']['patrimonialPlanning']['accounts'])==1
   ctx2,p2,errors2,network2=boot()
   try:
    p2.locator('#data-button').click();p2.locator('#import-file').set_input_files({'name':'backup.json','mimeType':'application/json','buffer':payload});p2.wait_for_selector('#import-review:visible');assert p2.evaluate('JPWPlanning.queries.snapshot().accounts.length')==0
    p2.locator('#restore-ack').check();p2.locator('#restore-button').click();p2.wait_for_function('JPWPlanning.queries.snapshot().accounts.length===1');assert p2.evaluate('JSON.stringify(JPWPlanning.queries.snapshot())')==snapshot
    assert 'Backup restaurado' in p2.locator('#data-message').inner_text()
    p2.locator('#data-dialog button[aria-label]').click();p2.reload(wait_until='load');assert p2.evaluate('JSON.stringify(JPWPlanning.queries.snapshot())')==snapshot
    assert not errors2,errors2
   finally:ctx2.close()
   assert not errors,errors
  finally:ctx.close()
 check('DATA-save/readback/reopen, export and validated restore in a fresh browser origin context',persistence)
 def first_unknown():
  ctx,page,errors,network=boot()
  try:
   page.get_by_role('button',name='Preencher novo formulário',exact=True).click();page.locator('#pl-native-openProfiles').click();page.locator('[data-pl-choose-profile=base]').click()
   page.locator('#pl-native-mes').select_option('11');page.locator('#pl-native-saldo').fill('1234');page.locator('#pl-native-aporte').fill('100');page.locator('#pl-native-sonhoMoeda').select_option('USD');page.locator('#pl-native-sonhoBRL').fill('300')
   page.locator('dialog[open] [data-pl-submit]').click()
   page.evaluate("""()=>{const get=Storage.prototype.getItem,set=Storage.prototype.setItem;window.__mainWritten=false;window.__get=get;window.__set=set;Storage.prototype.getItem=function(k){if(k===PlanningStore.KEY&&__mainWritten)throw Error('synthetic real readback failure');return get.call(this,k)};Storage.prototype.setItem=function(k,v){const r=set.call(this,k,v);if(k===PlanningStore.KEY)__mainWritten=true;return r}}""")
   page.locator('dialog[open] [data-pl-submit]').click();assert page.evaluate('PlanningStore.status().status')=='UNKNOWN'
   assert page.locator('#planning').is_visible() and page.locator('dialog[open]').is_visible()
   page.get_by_role('button',name='Voltar e editar',exact=True).click();assert page.locator('#pl-native-saldo').is_visible() and page.locator('#pl-native-saldo').input_value()=='1234'
   page.get_by_role('button',name='Fechar e manter rascunho',exact=True).click();page.locator('#recovery-button').click();assert page.locator('#data-dialog').is_visible()
   with page.expect_download() as download:page.locator('#export-recovery').click()
   value=json.loads(Path(download.value.path()).read_text());assert value['status']['status']=='UNKNOWN' and value['unsavedDrafts'] and value['candidateDocument']['patrimonialPlanning']['accounts']
   assert not errors,errors
  finally:ctx.close()
 check('RECOVERY-real first-save readback failure keeps modal/text accessible, closes normally and exports recovery',first_unknown)
 def partial_restore():
  ctx,page,errors,network=boot()
  try:
   reference.seed(page);backup=page.evaluate("PlanningBackup.create({preferences:{theme:'dark',monthly:{version:1,highlightPast:false,fromCurrent:true}},drafts:[{label:'Rascunho sintético',text:'{\"value\":\"75\"}'}]})")
   ctx2,p2,e2,n2=boot()
   try:
    p2.locator('#data-button').click();p2.locator('#import-file').set_input_files({'name':'backup.json','mimeType':'application/json','buffer':json.dumps(backup).encode()});p2.wait_for_selector('#import-review:visible')
    p2.evaluate("()=>{const original=Storage.prototype.setItem;window.__realSet=original;Storage.prototype.setItem=function(k,v){if(k==='planejamento_patrimonial_monthly_view_v1')throw Error('synthetic projection quota');return original.call(this,k,v)}}")
    p2.locator('#restore-ack').check();p2.locator('#restore-button').click();assert 'base foi restaurada' in p2.locator('#data-message').inner_text();assert p2.evaluate('JPWPlanning.queries.snapshot().accounts.length')==1
    assert p2.evaluate("localStorage.getItem('planejamento_patrimonial_restore_projection_v1')!==null")
    p2.evaluate('()=>{Storage.prototype.setItem=__realSet}');p2.locator('#reload-button').click();p2.locator('#confirm-reload').click();assert 'concluídos' in p2.locator('#data-message').inner_text();assert p2.locator('#restored-drafts').is_visible() and p2.locator('#draft-list textarea').input_value()=='{"value":"75"}'
    assert p2.evaluate("localStorage.getItem('planejamento_patrimonial_restore_projection_v1')===null") and p2.locator('html').get_attribute('data-theme')=='dark'
    assert not e2,e2
   finally:ctx2.close()
  finally:ctx.close()
 check('BACKUP-partial preference failure preserves journal and resumes explicitly; imported drafts readonly',partial_restore)
 def unavailable():
  ctx,page,errors,network=boot(fx=False)
  try:
   page.get_by_role('button',name='Preencher novo formulário',exact=True).click();assert page.locator('dialog[open]').is_visible();assert page.evaluate('JPWPlanning.queries.snapshot().accounts.length')==0
   page.keyboard.press('Escape');page.locator('#data-button').click();before=page.evaluate('JSON.stringify(PlanningStore.exportDocument())');bad=json.dumps({'S':{'patrimonialPlanning':{}},'workspace':{}}).encode();page.locator('#import-file').set_input_files({'name':'jp-wealth-backup.json','mimeType':'application/json','buffer':bad});page.wait_for_function("document.querySelector('#data-message').textContent.includes('Arquivo recusado')");assert page.evaluate('JSON.stringify(PlanningStore.exportDocument())')==before
   assert not errors,errors
  finally:ctx.close()
 check('BOUNDARY-no quote does not inventFX; full JP Wealth backup rejected without writes',unavailable)
 def native():
  with tempfile.TemporaryDirectory(prefix='pp-native200-') as folder:
   p=Path(folder)/'Default';p.mkdir();(p/'Preferences').write_text(json.dumps({'partition':{'default_zoom_level':{'x':math.log(2)/math.log(1.2)}}}))
   ctx=pw.chromium.launch_persistent_context(folder,headless=True,no_viewport=True,executable_path=os.environ.get('PP_CHROMIUM'),args=['--window-size=1440,1000'],timezone_id='America/Sao_Paulo',reduced_motion='reduce')
   try:
    _,page,errors,network=boot(context=ctx);ratio=page.evaluate('({outer:outerWidth,inner:innerWidth,css:getComputedStyle(document.documentElement).zoom})');assert abs(ratio['outer']/ratio['inner']-2)<.01 and ratio['css']=='1',ratio;report['nativeZoom']=ratio
    reference.seed(page)
    for theme in ['light','dark']:
     page.evaluate('(t)=>document.documentElement.dataset.theme=t',theme);page.evaluate("JPWPlanning.ui.selectView('monthly')");page.wait_for_timeout(70);geometry(page);page.screenshot(path=str(OUT/f'native200-{theme}.png'),full_page=True)
    assert not errors,errors
   finally:ctx.close()
 check('NATIVE200-real browser zoom,light/dark,monthly fields and44px targets',native)
 def recovery_capacity():
  for own in [False,True]:
   ctx,page,errors,network=boot()
   try:
    reference.seed(page)
    seeded=page.evaluate("""own=>{const main=localStorage.getItem(PlanningStore.KEY),copy=PlanningStore.exportRecovery().recoveryCopies[0],item=PlanningStore.inspectRecovery(copy.raw);if(own)localStorage.setItem(copy.key,JSON.stringify({...item,previousRaw:main,candidateRaw:main}));else for(let i=0;i<8;i++)localStorage.setItem(PlanningStore.RECOVERY_PREFIX+'legacy-capacity-'+i,JSON.stringify({...item,owner:'legacy-capacity-'+i,previousRaw:main,candidateRaw:main}));window.__auditCopies=Object.fromEntries(Object.entries(localStorage).filter(([k])=>k.startsWith(PlanningStore.RECOVERY_PREFIX)));const original=Storage.prototype.setItem;window.__capacityMax=Object.values(localStorage).reduce((n,v)=>n+v.length,0)+(own?30000:500);let blockOnce=own;Storage.prototype.setItem=function(k,v){if(blockOnce&&k===copy.key){blockOnce=false;throw new DOMException('Synthetic journal refusal','QuotaExceededError');}const total=Object.keys(localStorage).filter(key=>key!==k).reduce((n,key)=>n+localStorage.getItem(key).length,0)+String(v).length;if(total>window.__capacityMax)throw new DOMException('Synthetic capacity','QuotaExceededError');return original.call(this,k,v)};return main}""",own)
    page.get_by_role('button',name='Gerenciar ▾',exact=True).click();page.get_by_role('menuitem',name='Adicionar nova conta',exact=True).click();d=page.locator('dialog[data-pl-submit=create]');page.locator('#pl-native-ano').fill('2026');page.locator('#pl-native-mes').select_option('11');page.locator('#pl-native-saldo').fill('1234');page.locator('#pl-native-aporte').fill('100');page.locator('#pl-native-openProfiles').click();page.locator('[data-pl-choose-profile=base]').click();page.locator('#pl-native-custoMoeda').select_option('USD');page.locator('#pl-native-custoValor').fill('150');page.locator('#pl-native-sonhoMoeda').select_option('USD');page.locator('#pl-native-sonhoBRL').fill('300');d.locator('[data-pl-submit]').click();d.locator('[data-pl-submit]').click();assert d.is_visible() and d.locator('[data-pl-submit]').is_disabled();banner=d.locator('[data-pl-draft-stale]');assert 'recusou' in banner.inner_text() and 'Os dados mudaram' not in banner.inner_text();assert page.evaluate('localStorage.getItem(PlanningStore.KEY)')==seeded;assert page.evaluate('JPWPlanning.queries.snapshot().accounts.length')==1;page.screenshot(path=str(OUT/f'capacity-refused-{own}.png'))
    banner.get_by_role('button',name='Compactar cópias de recuperação',exact=True).click();assert page.evaluate('localStorage.getItem(PlanningStore.KEY)')==seeded and page.evaluate('JPWPlanning.queries.snapshot().accounts.length')==1
    if own:
     assert page.locator('#pl-native-saldo').input_value()=='1234' and page.locator('[data-pl-native-fields]').is_visible();assert not d.locator('[data-pl-submit]').is_disabled();page.screenshot(path=str(OUT/'capacity-draft-preserved.png'));d.locator('[data-pl-submit]').click();assert 'Confira antes de salvar' in d.inner_text();d.locator('[data-pl-submit]').click();assert page.evaluate('JPWPlanning.queries.snapshot().accounts.length')==2;assert 'Conta criada' in d.inner_text();page.screenshot(path=str(OUT/'capacity-created.png'));d.get_by_role('button',name='Fechar e manter rascunho',exact=True).click();page.reload();page.wait_for_selector('[data-pl-start]');assert page.evaluate('PlanningStore.status().status')=='READY' and page.evaluate('JPWPlanning.queries.snapshot().accounts.length')==2
    else:
     assert d.locator('[data-pl-submit]').is_disabled();assert 'nenhum espaço foi liberado' in d.inner_text() and 'outras sessões' in d.inner_text();assert page.evaluate('Object.entries(__auditCopies).every(([k,v])=>localStorage.getItem(k)===v)');d.get_by_role('button',name='Voltar e editar',exact=True).click();assert page.locator('#pl-native-saldo').input_value()=='1234';page.screenshot(path=str(OUT/'capacity-foreign-preserved.png'))
    assert not errors,errors;assert not network,network
   finally:ctx.close()
 check('CAPACITY-only owned copies compact; foreign quota stays refused with draft intact; fresh explicit own review creates once',recovery_capacity)
 browser.close()
server.shutdown();server.server_close();report['status']='PASS' if report['checks'] and not report['failures'] else 'PRODUCT_FAIL';(OUT/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps({'status':report['status'],'checks':len(report['checks']),'failures':report['failures']},ensure_ascii=False));raise SystemExit(report['status']!='PASS')

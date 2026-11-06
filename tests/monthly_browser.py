"""Focused monthly-input journeys. Synthetic contexts only; no public visitor data."""
import functools,json,math,os,tempfile,threading,time,traceback
from pathlib import Path
from datetime import datetime,timezone
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/monthly-browser';OUT.mkdir(parents=True,exist_ok=True)
class Quiet(SimpleHTTPRequestHandler):
 def log_message(self,*_):pass
server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT)));threading.Thread(target=server.serve_forever,daemon=True).start();BASE=f'http://127.0.0.1:{server.server_port}/';URL=BASE+'dist/'
report={'checks':[],'failures':[],'limits':['Safari, physical touch and manual screen reader NOT_RUN.']}
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('PP_CHROMIUM'))
 def boot(width=1440,height=1000,context=None,before=False):
  ctx=context or browser.new_context(viewport={'width':width,'height':height},timezone_id='America/Sao_Paulo',reduced_motion='reduce');page=ctx.new_page();page.set_default_timeout(7000);page.clock.set_fixed_time(datetime(2026,11,4,18,tzinfo=timezone.utc));errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  def route(r):
   if r.request.url.startswith('https://api.frankfurter.dev/'):r.fulfill(content_type='application/json',body=json.dumps({'base':'USD','quote':'BRL','date':'2026-11-03','rate':5}))
   elif r.request.url.startswith(BASE):r.continue_()
   else:r.abort()
  startup=[];started=time.monotonic()
  page.on('response',lambda r:startup.append({'url':r.url,'status':r.status}))
  page.on('requestfailed',lambda r:startup.append({'url':r.url,'failure':r.failure}))
  ctx.route('**/*',route);page.goto(BASE+'outputs/monthly-before/dist/' if before else URL,wait_until='load')
  try:page.wait_for_selector('[data-pl-start]')
  except Exception:
   tag=str(time.time_ns());page.screenshot(path=str(OUT/f'boot-failure-{tag}.png'));(OUT/f'boot-failure-{tag}.json').write_text(json.dumps({'url':page.url,'elapsedSeconds':time.monotonic()-started,'errors':errors,'requests':startup,'text':page.locator('body').inner_text()},ensure_ascii=False,indent=2));raise

  id=page.evaluate("""()=>{const r=JPWPlanning.commands.execute('createAccount',{name:'Conta demonstração',broker:'',login:'',server:'',startMonth:'2026-11',initialUsd:1000,profileId:'base',monthlyContributionUsd:200,goals:{adequate:null,ideal:{value:100,currency:'USD'}}},JPWPlanning.queries.token());if(r.status!=='CONFIRMED')throw Error(JSON.stringify(r));JPWPlanning.ui.selectView('monthly');return r.accountId;}""")
  page.locator('[data-pl-account]').select_option(id);return ctx,page,errors,id
 def run(name,fn):
  try:fn();report['checks'].append(name);print('PASS',name,flush=True)
  except Exception as e:report['failures'].append({'name':name,'error':str(e),'traceback':traceback.format_exc()});print('FAIL',name,str(e),flush=True)
 def cell(page,kind):return page.locator(f'[data-pl-inline-open={kind}][data-pl-inline-month="2026-11"]')
 def checkcontrol(page):return page.locator('[data-pl-check-month="2026-11"]')
 def popup(page):return page.locator('dialog.pl-inline-popup[open]')
 def snapshot(page):return page.evaluate('JSON.stringify(JPWPlanning.queries.snapshot())')
 def open_cell(page,kind):
  c=cell(page,kind)
  if not c.is_visible():page.locator('[data-pl-select-month="2026-11"]').click()
  c.click();popup(page).wait_for(state='visible');return popup(page)
 def advance_review(page):
  p=popup(page)
  if p.locator('[data-pl-inline-save]').is_visible():p.locator('[data-pl-inline-save]').click()
  else:assert p.locator('[data-pl-inline-review]').is_visible()
 def review_confirm(page):
  p=popup(page);advance_review(page);assert 'Os valores estão corretos?' in p.inner_text();p.locator('[data-pl-action=inline-confirm]').click();p.wait_for(state='hidden')
 def result(page,value):
  p=open_cell(page,'result');p.locator('[name=value]').fill(str(value));review_confirm(page)
 def choose(p,mode):p.locator('[data-pl-choice="'+mode+'"]').click()
 def noflow(page,kind):
  p=open_cell(page,kind);choose(p,'none');review_confirm(page)
 def flow(page,kind,usd,brl=''):
  p=open_cell(page,kind)
  choose(p,'movement')
  p.locator('[name=usd]').fill(str(usd))
  if brl!='':p.locator('[name=brl]').fill(str(brl))
  review_confirm(page)
 def geometry(page):
  g=page.evaluate("""()=>{const r=e=>{const x=e.getBoundingClientRect();return {x:x.x,y:x.y,w:x.width,h:x.height,right:x.right,bottom:x.bottom}},v=e=>!!e.getClientRects().length;return {width:innerWidth,height:innerHeight,overflow:document.documentElement.scrollWidth>innerWidth,dialogs:[...document.querySelectorAll('dialog[open]')].map(r),controls:[...document.querySelectorAll('dialog[open] button,dialog[open] select,dialog[open] input,.pl-inline-cell,.pl-month-check')].filter(v).map(e=>({...r(e),name:e.getAttribute('aria-label')||e.textContent}))}}""")
  assert not g['overflow'],g
  for d in g['dialogs']:assert d['x']>=-2 and d['y']>=-2 and d['right']<=g['width']+2 and d['bottom']<=g['height']+2,d
  for c in g['controls']:assert c['w']>=42 and c['h']>=42,c
  return g
 def design():
  ctx,page,errors,id=boot(before=True)
  try:page.screenshot(path=str(OUT/'antes-desktop.png'));cell(page,'result').click();page.screenshot(path=str(OUT/'antes-editor.png'))
  finally:ctx.close()
  ctx,page,errors,id=boot()
  try:
   before=snapshot(page);assert checkcontrol(page).is_disabled()
   for kind in ['result','contribution','withdrawal']:assert cell(page,kind).locator('.pl-cell-content').inner_text()=='Preencher'
   page.screenshot(path=str(OUT/'depois-desktop.png'));assert page.locator('[data-pl-finalized-month]').count()==0
   page.locator('[data-pl-select-month="2026-11"]').click();page.locator('[data-pl-select-month="2026-11"]').click();assert page.locator('[data-pl-month-details="2026-11"]').is_hidden()
   cell(page,'result').focus();cell(page,'result').press('Enter');assert page.locator('[data-pl-month-details="2026-11"]').is_hidden();geometry(page)
   p=popup(page);p.locator('[name=value]').fill('123');p.locator('[data-pl-inline-save]').click();assert snapshot(page)==before;assert p.locator('[data-pl-action=inline-confirm]').is_visible()
   p.get_by_role('button',name='Voltar ao preenchimento',exact=True).click();p.locator('[name=value]').fill('124');assert p.locator('[data-pl-action=inline-confirm]').is_hidden();p.locator('[data-pl-action=inline-cancel]').click();assert snapshot(page)==before;assert cell(page,'result').evaluate('e=>e===document.activeElement');cell(page,'result').press('Enter');popup(page).locator('[name=value]').press('Escape');assert popup(page).count()==0 and cell(page,'result').evaluate('e=>e===document.activeElement');assert not errors,errors
  finally:ctx.close()
 run('cell-affordance, no detail expansion, cancel, focus and review invalidation',design)
 def transactions():
  ctx,page,errors,id=boot()
  try:
   result(page,-20);assert checkcontrol(page).is_disabled();flow(page,'contribution',10,50);flow(page,'contribution',25,125);noflow(page,'withdrawal');assert not checkcontrol(page).is_disabled()
   p=open_cell(page,'contribution');assert p.locator('[data-pl-action=inline-record]').count()==2;assert p.locator('[data-pl-choice=none]').is_disabled();p.locator('[data-pl-action=inline-cancel]').click()
   before=snapshot(page);checkcontrol(page).click();d=page.locator('dialog[data-pl-submit=finalize]');assert 'Preencheu e conferiu corretamente estas informações?' in d.inner_text();assert d.locator('.pl-definition dd').all_text_contents()==page.evaluate("()=>[-20,0,35].map(v=>new Intl.NumberFormat('pt-BR',{style:'currency',currency:'USD'}).format(v))");assert d.locator('input,select').count()==0;d.locator('[data-pl-action=close]').first.click();assert snapshot(page)==before and checkcontrol(page).get_attribute('aria-checked')=='false'
   checkcontrol(page).press('Space');d=page.locator('dialog[data-pl-submit=finalize]');d.locator('[data-pl-submit]').click();assert checkcontrol(page).get_attribute('aria-checked')=='true'
   assert page.evaluate('(id)=>JPWPlanning.queries.account(id).plan.closures["2026-11"].snapshot.closeUsd',id)==1015
   checkcontrol(page).click();d=page.locator('dialog[data-pl-submit=reopen]');d.locator('[name=reason]').fill('Corrigir conferência');d.locator('[data-pl-submit]').click();assert checkcontrol(page).get_attribute('aria-checked')=='false';assert not errors,errors
  finally:ctx.close()
 run('negative result, multiple flows, zero withdrawal and explicit closure/reopening',transactions)
 def zeros():
  ctx,page,errors,id=boot()
  try:
   result(page,0);noflow(page,'contribution');noflow(page,'withdrawal');assert not checkcontrol(page).is_disabled();checkcontrol(page).click();page.locator('dialog[data-pl-submit=finalize] [data-pl-submit]').click();before=snapshot(page);page.reload();assert snapshot(page)==before
   a=page.evaluate('(id)=>JPWPlanning.queries.account(id)',id);assert a['plan']['contributions']==[] and a['plan']['withdrawals']==[] and a['plan']['results']['2026-11']['usd']==0
   data=page.evaluate('JSON.stringify(PlanningBackup.create())');fresh=browser.new_context();p2=fresh.new_page();p2.goto(URL);p2.wait_for_selector('[data-pl-start]');restored=p2.evaluate('s=>PlanningBackup.restore(PlanningBackup.inspect(s),{expectedEpoch:PlanningStore.epoch()})',data);assert restored['status']=='CONFIRMED';assert p2.evaluate('JSON.stringify(JPWPlanning.queries.snapshot())')==before;fresh.close();assert not errors,errors
  finally:ctx.close()
 run('explicit zero facts survive reload and backup roundtrip without fake ledger',zeros)
 def annul():
  ctx,page,errors,id=boot()
  try:
   result(page,0);flow(page,'contribution',10,50);noflow(page,'withdrawal');checkcontrol(page).click();page.locator('dialog[data-pl-submit=finalize] [data-pl-submit]').click()
   p=open_cell(page,'contribution');choose(p,'movement');p.locator('[data-pl-action=inline-record]').click();p=popup(page);p.locator('[name=usd]').fill('0');p.locator('[name=brl]').fill('0');p.locator('[data-pl-inline-save]').click();p.locator('[data-pl-inline-ack]').check();p.locator('[data-pl-action=inline-confirm]').click();assert checkcontrol(page).get_attribute('aria-checked')=='false' and checkcontrol(page).is_disabled();assert cell(page,'contribution').locator('.pl-cell-content').inner_text()=='Preencher';noflow(page,'contribution');assert not checkcontrol(page).is_disabled();assert not errors,errors
  finally:ctx.close()
 run('correction/annulment preserves ledger and reopens dependent closure',annul)
 def conflict():
  # Retained draft: saving a different cell must require explicit fresh review,
  # without losing fields or granting a write merely by reopening the popup.
  ctx,page,errors,id=boot()
  try:
   p=open_cell(page,'withdrawal');choose(p,'none');page.mouse.click(2,2);assert popup(page).count()==0
   result(page,0);before=snapshot(page);p=open_cell(page,'withdrawal');choose(p,'none')
   assert snapshot(page)==before
   refresh=p.get_by_role('button',name='Conferir dados atuais',exact=True)
   assert refresh.is_visible(), 'Retained stale draft needs an explicit path to a fresh review'
   page.screenshot(path=str(ROOT/'outputs/inline-review-20261105/explicit-review-desktop.png'))
   page.set_viewport_size({'width':320,'height':700});geometry(page);page.screenshot(path=str(ROOT/'outputs/inline-review-20261105/explicit-review-320.png'));page.evaluate("document.documentElement.dataset.theme='dark'");geometry(page);page.screenshot(path=str(ROOT/'outputs/inline-review-20261105/explicit-review-320-dark.png'));page.evaluate("document.documentElement.dataset.theme='light'");page.set_viewport_size({'width':1440,'height':1000})
   assert p.locator('[data-pl-action=inline-confirm]').is_disabled()
   refresh.click();assert snapshot(page)==before
   choose(p,'none');assert p.locator('[data-pl-inline-review]').is_visible()
   p.locator('[data-pl-action=inline-confirm]').click();p.wait_for(state='hidden')
   assert page.evaluate('(id)=>JPWPlanning.queries.account(id).plan.monthlyInputs.noMovement["2026-11"].withdrawal',id)
   assert not errors,errors
  finally:ctx.close()
  ctx,page,errors,id=boot()
  try:
   before=snapshot(page);oldToken=page.evaluate('(id)=>JPWPlanning.queries.token(id)',id)
   p=open_cell(page,'result');p.locator('[name=value]').fill('17');p.locator('[data-pl-inline-save]').click()
   other=ctx.new_page();other.goto(URL);other.wait_for_selector('[data-pl-start]')
   assert other.evaluate('(id)=>JPWPlanning.commands.execute("recordResult",{accountId:id,month:"2026-11",usd:30},JPWPlanning.queries.token(id)).status',id)=='CONFIRMED'
   p.locator('[data-pl-action=inline-confirm]').click();assert p.is_visible() and p.locator('[name=value]').input_value()=='17'
   assert 'base precisa de conferência' in p.inner_text() and p.get_by_role('button',name='Conferir dados atuais',exact=True).is_disabled()
   assert p.locator('[data-pl-action=inline-confirm]').is_disabled()
   page.mouse.click(2,2);p=open_cell(page,'result');assert p.locator('[name=value]').input_value()=='17'
   p.locator('[data-pl-inline-save]').click()
   assert p.locator('[data-pl-action=inline-confirm]').is_disabled() and p.get_by_role('button',name='Conferir dados atuais',exact=True).is_disabled()
   assert page.evaluate('(x)=>JPWPlanning.commands.execute("recordResult",{accountId:x.id,month:"2026-11",usd:17},x.token).status',{'id':id,'token':oldToken})=='CONFLICT'
   assert snapshot(page)==before and other.evaluate('(id)=>JPWPlanning.queries.account(id).plan.results["2026-11"].usd',id)==30;assert not errors,errors
  finally:ctx.close()
  # A replaced plan never gains a new confirmation token from this UI action.
  ctx,page,errors,id=boot()
  try:
   p=open_cell(page,'result');p.locator('[name=value]').fill('17')
   assert page.evaluate('(id)=>JPWPlanning.commands.execute("resetAccount",{accountId:id,confirmation:JPWPlanning.queries.previewReset({accountId:id}).phrase},JPWPlanning.queries.token(id)).status',id)=='CONFIRMED'
   before=snapshot(page);p.locator('[data-pl-inline-save]').click()
   assert p.get_by_role('button',name='Conferir dados atuais',exact=True).is_disabled()
   assert p.locator('[data-pl-action=inline-confirm]').is_disabled() and p.locator('[name=value]').input_value()=='17'
   assert snapshot(page)==before and not errors,errors
  finally:ctx.close()
 run('two-tab conflict keeps typed value and refuses stale confirmation',conflict)
 def failures():
  for mode in ['quota','unknown']:
   ctx,page,errors,id=boot()
   try:
    p=open_cell(page,'withdrawal');choose(p,'none');advance_review(page);before=snapshot(page)
    page.evaluate("""mode=>{const get=Storage.prototype.getItem,set=Storage.prototype.setItem;let written=false;Storage.prototype.setItem=function(k,v){if(k===PlanningStore.KEY&&mode==='quota')throw Error('synthetic quota');const r=set.call(this,k,v);if(k===PlanningStore.KEY)written=true;return r};Storage.prototype.getItem=function(k){if(k===PlanningStore.KEY&&mode==='unknown'&&written)throw Error('synthetic readback');return get.call(this,k)}}""",mode)
    p.locator('[data-pl-action=inline-confirm]').click();assert p.is_visible() and p.locator('[name=entryMode]').input_value()=='none';assert snapshot(page)==before
    assert checkcontrol(page).get_attribute('aria-checked')=='false'
    if mode=='unknown':
     assert p.locator('[data-pl-action=inline-confirm]').is_disabled() and page.evaluate('PlanningStore.status().status')=='UNKNOWN';page.mouse.click(2,2);p=open_cell(page,'withdrawal');assert p.locator('[data-pl-inline-save]').is_disabled() and 'indeterminado' in p.inner_text();assert snapshot(page)==before;p.locator('[data-pl-action=inline-cancel]').click();assert page.evaluate('JPWPlanning.ui.backupDrafts().some(d=>d.text.includes("entryMode"))')
    else:assert 'confirmada' in p.inner_text()
    assert not errors,errors
   finally:ctx.close()
 run('quota and UNKNOWN preserve draft; UNKNOWN blocks retries and exports recovery text',failures)
 def responsive():
  for width,height in [(320,700),(390,480),(820,700),(1440,1000)]:
   for theme in ['light','dark']:
    ctx,page,errors,id=boot(width,height)
    try:
     page.evaluate('t=>document.documentElement.dataset.theme=t',theme);p=open_cell(page,'result');geometry(page);p.locator('[name=value]').fill('0');p.locator('[data-pl-inline-save]').click();geometry(page);page.screenshot(path=str(OUT/f'editor-{width}-{theme}.png'));p.locator('[data-pl-action=inline-cancel]').click();assert not errors,errors
    finally:ctx.close()
 run('320px through desktop, light/dark, low height and bounded editors/44px controls',responsive)
 def native():
  with tempfile.TemporaryDirectory(prefix='pp-monthly-zoom-') as folder:
   pref=Path(folder)/'Default';pref.mkdir();(pref/'Preferences').write_text(json.dumps({'partition':{'default_zoom_level':{'x':math.log(2)/math.log(1.2)}}}));ctx=pw.chromium.launch_persistent_context(folder,headless=True,no_viewport=True,executable_path=os.environ.get('PP_CHROMIUM'),args=['--window-size=1440,1000'],timezone_id='America/Sao_Paulo',reduced_motion='reduce')
   try:
    _,page,errors,id=boot(context=ctx);r=page.evaluate('({outer:outerWidth,inner:innerWidth,css:getComputedStyle(document.documentElement).zoom})');assert abs(r['outer']/r['inner']-2)<.01 and r['css']=='1';report['nativeZoom']=r
    p=open_cell(page,'result');p.locator('[name=value]').fill('0');p.locator('[data-pl-inline-save]').click();geometry(page);page.screenshot(path=str(OUT/'editor-native200.png'));p.get_by_role('button',name='Voltar ao preenchimento',exact=True).click();assert p.locator('[name=value]').input_value()=='0';p.locator('[data-pl-inline-save]').click();geometry(page);p.locator('[data-pl-action=inline-confirm]').click();assert cell(page,'result').evaluate('e=>e===document.activeElement');p=open_cell(page,'withdrawal');assert p.get_by_role('button',name='Sim, fiz saque este mês',exact=True).is_visible() and p.locator('[name=usd]').is_hidden();geometry(page);page.screenshot(path=str(OUT/'withdrawal-native200.png'));page.mouse.click(2,2);assert popup(page).count()==0;p=open_cell(page,'contribution');assert p.get_by_role('button',name='Sim, fiz aporte este mês',exact=True).is_visible() and p.locator('[name=usd]').is_hidden();geometry(page);page.screenshot(path=str(OUT/'contribution-native200.png'));page.mouse.click(2,2);assert popup(page).count()==0;assert not errors,errors
   finally:ctx.close()
 run('native200 keyboard-accessible bounded editor and focus restoration',native)
 def actual_balance():
  ctx,page,errors,id=boot()
  try:
   balance=page.locator('[data-pl-grid-month="2026-11"] .pl-month-balance');before=snapshot(page);assert balance.get_attribute('data-pl-balance-origin')=='PARTIAL';assert '1.000,00' in balance.locator('.pl-money-primary').inner_text() and 'Parcial' in balance.inner_text();assert 'Aguardando fechamento' in page.locator('[data-pl-grid-month="2026-12"]').inner_text();assert page.locator('[data-pl-grid-month="2026-12"] [data-pl-month-value=open]').inner_text()=='—';assert snapshot(page)==before
   denied=open_cell(page,'withdrawal');choose(denied,'movement');denied.locator('[name=usd]').fill('1020');denied.locator('[data-pl-inline-save]').click();assert 'saldo negativo' in denied.inner_text();assert denied.locator('[data-pl-action=inline-confirm]').is_hidden();assert snapshot(page)==before;page.screenshot(path=str(OUT/'withdrawal-forecast-refused.png'));denied.get_by_role('button',name='Cancelar',exact=True).click()
   result(page,50);assert balance.locator('.pl-money-primary').inner_text().endswith('1.050,00');noflow(page,'contribution');assert cell(page,'contribution').locator('.pl-cell-content').inner_text().endswith('0,00');noflow(page,'withdrawal');assert balance.get_attribute('data-pl-balance-origin')=='RECORDED';assert balance.locator('.pl-money-primary').inner_text().endswith('1.050,00');checkcontrol(page).click();assert page.locator('[data-pl-closure-review]').inner_text().count('1.050,00')==0;page.locator('dialog[data-pl-submit=finalize] [data-pl-submit]').click();assert balance.get_attribute('data-pl-balance-origin')=='CONFIRMED' and balance.locator('.pl-money-primary').inner_text().endswith('1.050,00');page.screenshot(path=str(OUT/'patrimonio-registrado.png'));assert not errors,errors
  finally:ctx.close()
 run('actual1000 distinct from forecast1230; recorded inputs and explicit zero carry through closure',actual_balance)
 def partial_visual():
  for width in [320,1440]:
   ctx,page,errors,id=boot(width)
   try:
    geometry(page);balance=page.locator('[data-pl-grid-month="2026-11"] .pl-month-balance');assert 'Parcial' in balance.inner_text();page.screenshot(path=str(OUT/f'patrimonio-parcial-{width}.png'));assert not errors,errors
   finally:ctx.close()
 run('partial balance labels remain readable at320 and desktop',partial_visual)
 def consistent_sequence():
  ctx,page,errors,id=boot()
  try:
   before=snapshot(page);dec=page.locator('[data-pl-grid-month="2026-12"]');assert dec.locator('[data-pl-month-value=open]').inner_text()=='—';assert dec.locator('.pl-month-balance .pl-money-primary').inner_text()=='—';assert dec.locator('[data-pl-month-value=rate]').inner_text()=='3%';assert dec.locator('[data-pl-inline-open=contributionUsd] .pl-cell-content').inner_text().endswith('200,00');assert 'Aguardando fechamento de' in page.locator('[data-pl-projection-wait]').inner_text();assert snapshot(page)==before
   page.get_by_role('tab',name='Consolidado',exact=True).click();assert page.locator('[data-pl-summary-group=projection] .pl-metric strong').first.inner_text()=='—';assert 'Aguardando fechamento' in page.locator('[data-pl-summary-group=projection]').inner_text();assert page.locator('[data-pl-chart] .pl-line-projected').get_attribute('d')==''
   page.evaluate('window.print=()=>{}');page.get_by_role('button',name='Gerar PDF',exact=True).click();report=page.locator('[data-pl-report]');assert 'Aguardando fechamento' in report.inner_text() and report.locator('.pl-report-projection strong').inner_text()=='—';assert report.locator('.pl-line-projected').get_attribute('d')=='';page.pdf(path=str(OUT/'sequencia-bloqueada.pdf'),format='A4',landscape=True);page.evaluate("dispatchEvent(new Event('afterprint'))")
   page.get_by_role('tab',name='Preenchimento mensal',exact=True).click();result(page,0);noflow(page,'contribution');noflow(page,'withdrawal');checkcontrol(page).click();page.locator('dialog[data-pl-submit=finalize] [data-pl-submit]').click();assert dec.locator('[data-pl-month-value=open]').inner_text().endswith('1.000,00');assert dec.locator('.pl-month-balance .pl-money-primary').inner_text().endswith('1.230,00');page.get_by_role('button',name='Próximo ano',exact=True).click();jan=page.locator('[data-pl-grid-month="2027-01"]');assert jan.locator('[data-pl-month-value=open]').inner_text().endswith('1.230,00') and jan.locator('.pl-month-balance .pl-money-primary').inner_text().endswith('1.466,90');page.screenshot(path=str(OUT/'sequencia-liberada.png'))
   page.get_by_role('tab',name='Consolidado',exact=True).click();year=page.locator('[data-pl-projection-year]');year.select_option('2026');projected=page.locator('[data-pl-summary-group=projection] .pl-metric strong').first.inner_text();assert projected.endswith('1.230,00');page.get_by_role('button',name='Gerar PDF',exact=True).click();assert page.locator('[data-pl-report] .pl-report-projection strong').inner_text()==projected;page.pdf(path=str(OUT/'sequencia-liberada.pdf'),format='A4',landscape=True);page.evaluate("dispatchEvent(new Event('afterprint'))");assert not errors,errors
  finally:ctx.close()
 run('same closure gate and1000->1230->1466.90 in table, chart, Consolidado and actualPDF',consistent_sequence)
 def wait_existing_simulation():
  ctx,page,errors,id=boot()
  try:
   page.get_by_role('tab',name='Consolidado',exact=True).click();page.get_by_role('button',name='Gerenciar ▾',exact=True).click();page.get_by_role('menuitem',name='Editar conta selecionada',exact=True).click();page.get_by_role('button',name='Planejar quando parar de aportar ↗',exact=True).click();assert 'Aguardando fechamento' in page.locator('#pl-native-stopMessage').inner_text();assert page.locator('#pl-native-stopUse').is_disabled();assert page.locator('#pl-native-stopWith').inner_text()=='—';assert page.locator('#pl-native-stopChart svg').count()==0;assert not errors,errors
  finally:ctx.close()
 run('existing-account simulation waits without stale comparison or save permission',wait_existing_simulation)
 def movement_buttons():
  for kind,noun in [('withdrawal','saque'),('contribution','aporte')]:
   ctx,page,errors,id=boot()
   try:
    before=snapshot(page);p=open_cell(page,kind);assert p.locator('select[name=entryMode]').count()==0 and p.locator('[name=entryMode]').input_value()=='';assert p.get_by_role('button',name='Sim, fiz '+noun+' este mês',exact=True).is_visible() and p.get_by_role('button',name='Não fiz '+noun+' esse mês',exact=True).is_visible();assert p.locator('[name=usd]').is_hidden() and p.locator('[name=brl]').is_hidden();assert p.locator('[data-pl-inline-save]').is_hidden()
    p.locator('[data-pl-choice=none]').press('Enter');assert snapshot(page)==before and p.locator('[name=usd]').is_hidden();assert p.locator('[data-pl-choice=none]').get_attribute('aria-pressed')=='true';advance_review(page);assert snapshot(page)==before and 'Sem '+noun+' neste mês' in p.inner_text();p.locator('[data-pl-action=inline-confirm]').click();assert page.evaluate('({id,kind})=>JPWPlanning.queries.account(id).plan[kind===\'withdrawal\'?\'withdrawals\':\'contributions\'].length',{'id':id,'kind':kind})==0
    p=open_cell(page,kind);assert p.locator('[name=entryMode]').input_value()=='';choose(p,'movement');p.locator('[name=usd]').fill('20');p.locator('[name=brl]').fill('100');review_confirm(page)
    p=open_cell(page,kind);assert p.locator('[data-pl-choice=none]').is_disabled();choose(p,'movement');assert p.locator('[data-pl-action=inline-record]').count()==1;p.locator('[data-pl-action=inline-record]').click();p=popup(page);assert p.locator('[name=usd]').input_value()=='20' and p.locator('[name=usd]').is_visible();p.locator('[data-pl-action=inline-cancel]').click();assert not errors,errors
   finally:ctx.close()
 run('both cells use explicit yes/no buttons before fields; review, zero confirmation and individual ledger preserved',movement_buttons)
 def outside_draft():
  ctx,page,errors,id=boot()
  try:
   before=snapshot(page);p=open_cell(page,'result');p.locator('[name=value]').fill('27');p.locator('[data-pl-inline-save]').click();assert p.locator('[data-pl-action=inline-confirm]').is_visible()
   box=p.bounding_box();page.mouse.move(box['x']+20,box['y']+20);page.mouse.down();page.mouse.move(2,2);page.mouse.up();assert p.is_visible();page.mouse.click(2,2);assert popup(page).count()==0 and snapshot(page)==before and cell(page,'result').evaluate('e=>e===document.activeElement');p=open_cell(page,'result');assert p.locator('[name=value]').input_value()=='27' and p.locator('[data-pl-inline-review]').is_hidden();assert snapshot(page)==before;p.locator('[data-pl-action=inline-cancel]').click()
   p=open_cell(page,'withdrawal');choose(p,'movement');p.locator('[name=usd]').fill('12');page.mouse.click(2,2);assert snapshot(page)==before;p=open_cell(page,'withdrawal');assert p.locator('[name=usd]').input_value()=='12';p.locator('[data-pl-action=inline-cancel]').click();p=open_cell(page,'withdrawal');assert p.locator('[name=entryMode]').input_value()=='';page.mouse.click(2,2);assert not errors,errors
  finally:ctx.close()
 run('outside click closes without saving, restores focus and session draft but never prior approval; inside-to-outside drag is ignored',outside_draft)
 def outside_windows():
  for width in [320,1440]:
   for theme in ['light','dark']:
    ctx,page,errors,id=boot(width=width)
    try:
     page.evaluate('t=>document.documentElement.dataset.theme=t',theme);before=snapshot(page)
     for kind in ['withdrawal','contribution']:
      p=open_cell(page,kind);geometry(page);page.screenshot(path=str(OUT/f'{kind}-buttons-{width}-{theme}.png'));choose(p,'movement');geometry(page);page.mouse.click(2,2);assert popup(page).count()==0
     page.get_by_role('button',name='Backup e dados',exact=True).click();page.locator('#data-title').click();assert page.locator('#data-dialog').is_visible();page.mouse.click(2,2);assert not page.locator('#data-dialog').is_visible();page.get_by_role('button',name='Backup e dados',exact=True).click();page.get_by_role('button',name='Conferir base gravada',exact=True).click();assert page.locator('#reload-dialog').is_visible();page.mouse.click(2,2);assert page.locator('dialog[open]').count()==0 and snapshot(page)==before
     page.get_by_role('button',name='Gerenciar ▾',exact=True).click();page.get_by_role('menuitem',name='Editar conta selecionada',exact=True).click();parent=page.locator('dialog[data-pl-submit=edit]');assert parent.is_visible();page.get_by_role('button',name='Planejar quando parar de aportar ↗',exact=True).click();assert page.locator('[data-pl-subdialog=stop]').is_visible();page.mouse.click(2,2);assert page.locator('[data-pl-subdialog=stop]').count()==0 and parent.is_visible();page.mouse.click(2,2);assert page.locator('dialog[open]').count()==0 and snapshot(page)==before;assert not errors,errors
    finally:ctx.close()
 run('outside dismissal of cell, backup, reload and nested planning windows; light/dark320px and desktop',outside_windows)
 def review_steps():
  for width in [320,1440]:
   for theme in ['light','dark']:
    for kind in ['result','withdrawal','contribution']:
     ctx,page,errors,id=boot(width=width)
     try:
      page.evaluate('t=>document.documentElement.dataset.theme=t',theme);before=snapshot(page);p=open_cell(page,kind)
      if kind=='result':p.locator('[name=value]').fill('12.50')
      else:choose(p,'movement');p.locator('[name=usd]').fill('20');p.locator('[name=brl]').fill('100')
      values=p.locator('input[name]').evaluate_all('nodes=>nodes.map(e=>[e.name,e.value])');p.locator('[data-pl-inline-save]').click();assert p.locator('[data-pl-inline-entry]').is_hidden() and p.locator('[data-pl-inline-review]').is_visible();assert p.locator('[data-pl-inline-save]').is_hidden() and p.locator('[data-pl-action=inline-confirm]').is_visible();back=p.get_by_role('button',name='Voltar ao preenchimento',exact=True);assert back.is_visible();assert p.locator('[data-pl-inline-review] h4').evaluate('e=>e===document.activeElement');geometry(page);box=back.bounding_box();pop=p.bounding_box();assert box['x']-pop['x']<=24 and box['y']-pop['y']<=24;page.screenshot(path=str(OUT/f'review-{kind}-{width}-{theme}.png'));assert snapshot(page)==before
      back.press('Enter');assert p.locator('[data-pl-inline-entry]').is_visible() and p.locator('[data-pl-inline-review]').is_hidden();assert p.locator('[data-pl-action=inline-confirm]').is_hidden() and back.is_visible()==(kind!='result');assert p.locator('input[name]').evaluate_all('nodes=>nodes.map(e=>[e.name,e.value])')==values;assert snapshot(page)==before
      if kind=='result':p.locator('[name=value]').fill('13')
      else:p.locator('[name=usd]').fill('21')
      p.locator('[data-pl-inline-save]').click();assert ('13,00' if kind=='result' else '21,00') in p.locator('[data-pl-inline-review]').inner_text();assert snapshot(page)==before;p.locator('[data-pl-action=inline-cancel]').click();assert snapshot(page)==before;assert not errors,errors
     finally:ctx.close()
 run('second review screen for result/withdrawal/contribution; top-left back arrow preserves values, resets approval and supports keyboard/themes320px',review_steps)
 def fixed_frame():
  for width,height in [(320,700),(1440,1000),(390,300)]:
   for theme in ['light','dark']:
    for kind in ['result','withdrawal','contribution']:
     ctx,page,errors,id=boot(width=width,height=height)
     try:
      page.evaluate('t=>document.documentElement.dataset.theme=t',theme);before=snapshot(page);p=open_cell(page,kind);original=p.bounding_box();assert abs(original['height']-min(260,height-24))<=2 and abs(original['width']-min(380,width-24))<=2;page.evaluate('window.__fixedDialog=document.querySelector("dialog.pl-inline-popup")')
      def same():
       current=p.bounding_box();assert all(abs(current[k]-original[k])<=2 for k in ['x','y','width','height']),(original,current);assert page.evaluate('document.querySelector("dialog.pl-inline-popup")===window.__fixedDialog');assert page.locator('dialog.pl-inline-popup').count()==1 and not page.evaluate('document.documentElement.scrollWidth>innerWidth');assert snapshot(page)==before
      if kind!='result':
       assert p.locator('[data-pl-inline-choice]').evaluate('e=>e.scrollHeight<=e.clientHeight+1'), 'Both choice buttons fit without scrolling'
       choose(p,'movement');same();assert p.locator('[data-pl-inline-choice]').is_hidden() and p.locator('[name=usd]').is_visible();p.get_by_role('button',name='Voltar ao preenchimento',exact=True).click();same();assert p.locator('[data-pl-inline-choice]').is_visible();choose(p,'none');same();assert p.locator('[data-pl-inline-review]').is_visible() and p.locator('[data-pl-inline-choice]').is_hidden();p.get_by_role('button',name='Voltar ao preenchimento',exact=True).click();same();assert p.locator('[data-pl-inline-choice]').is_visible();choose(p,'movement');p.locator('[name=usd]').fill('20');p.locator('[name=brl]').fill('100')
      else:p.locator('[name=value]').fill('5')
      advance_review(page);same();geometry(page);assert p.locator('[data-pl-inline-entry]').is_hidden();page.screenshot(path=str(OUT/f'fixed-{kind}-{width}-{theme}.png'));p.get_by_role('button',name='Voltar ao preenchimento',exact=True).click();same();assert p.locator('[data-pl-inline-entry]').is_visible();assert p.locator('[name=value]' if kind=='result' else '[name=usd]').input_value()==('5' if kind=='result' else '20')
      page.emulate_media(reduced_motion='no-preference');advance_review(page);same();assert p.locator('[data-pl-inline-review]').evaluate('e=>getComputedStyle(e).animationName')=='pl-inline-next';p.get_by_role('button',name='Voltar ao preenchimento',exact=True).click();same();assert p.locator('[data-pl-inline-entry]').evaluate('e=>getComputedStyle(e).animationName')=='pl-inline-back';page.emulate_media(reduced_motion='reduce');assert p.locator('[data-pl-inline-entry]').evaluate('e=>getComputedStyle(e).animationName')=='none';p.locator('[data-pl-action=inline-cancel]').click();assert snapshot(page)==before;assert not errors,errors
     finally:ctx.close()
 run('same380x260px dialog and coordinates through choice/entry/review/back; horizontal motion, reduced motion, three cells and low/narrow screens',fixed_frame)
 browser.close()
server.shutdown();server.server_close();report['status']='PASS' if len(report['checks'])==17 and not report['failures'] else 'FAIL';(OUT/'result.json').write_text(json.dumps(report,indent=2,ensure_ascii=False));print(json.dumps(report,ensure_ascii=False));raise SystemExit(report['status']!='PASS')

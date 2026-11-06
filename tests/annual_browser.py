"""Annual pages and explicit declarations in synthetic browser origins only."""
import functools,json,os,math,tempfile,threading,time,traceback
from pathlib import Path
from datetime import datetime,timezone
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/annual-browser';OUT.mkdir(parents=True,exist_ok=True)
class Quiet(SimpleHTTPRequestHandler):
 def log_message(self,*_):pass
server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT/'dist')));threading.Thread(target=server.serve_forever,daemon=True).start();URL=f'http://127.0.0.1:{server.server_port}/';report={'checks':[],'failures':[]}
with sync_playwright() as pw:
 b=pw.chromium.launch(headless=True,executable_path=os.environ.get('PP_CHROMIUM'))
 def boot(width=1440,height=1000,context=None,start='2025-11'):
  c=context or b.new_context(viewport={'width':width,'height':height},timezone_id='America/Sao_Paulo',reduced_motion='reduce');c.route('https://api.frankfurter.dev/**',lambda r:r.fulfill(content_type='application/json',body=json.dumps({'base':'USD','quote':'BRL','date':'2026-11-05','rate':5})))
  p=c.new_page();p.set_default_timeout(6000);errors=[];startup=[];started=time.monotonic();p.on('pageerror',lambda e:errors.append(str(e)));p.on('response',lambda r:startup.append({'url':r.url,'status':r.status}));p.on('requestfailed',lambda r:startup.append({'url':r.url,'failure':r.failure}));p.clock.set_fixed_time(datetime(2026,11,5,15,tzinfo=timezone.utc));p.goto(URL)
  try:p.wait_for_selector('[data-pl-start]')
  except Exception:
   tag=str(time.time_ns());p.screenshot(path=str(OUT/f'boot-failure-{tag}.png'));(OUT/f'boot-failure-{tag}.json').write_text(json.dumps({'url':p.url,'elapsedSeconds':time.monotonic()-started,'errors':errors,'requests':startup,'text':p.locator('body').inner_text(),'state':p.evaluate('({ready:document.readyState,planning:!!window.JPWPlanning,store:window.PlanningStore?.status(),ui:!!window.JPWPlanning?.ui})')},ensure_ascii=False,indent=2));raise

  id=p.evaluate("""start=>{const r=JPWPlanning.commands.execute('createAccount',{name:'Demonstração · dados fictícios',startMonth:start,initialUsd:1000,profileId:'base',monthlyContributionUsd:200,goals:{adequate:null,ideal:{value:100,currency:'USD'}}},JPWPlanning.queries.token());if(!r.ok)throw Error(JSON.stringify(r));JPWPlanning.ui.selectView('monthly');return r.accountId}""",start);p.locator('[data-pl-account]').select_option(id);return c,p,id,errors
 def run(name,fn):
  try:fn();report['checks'].append(name);print('PASS',name,flush=True)
  except Exception as e:report['failures'].append({'name':name,'error':str(e),'traceback':traceback.format_exc()});print('FAIL',name,str(e),flush=True)
 def year(p):return p.locator('[data-pl-year-current]').inner_text()
 def go(p,target):
  while year(p)!=str(target):p.get_by_role('button',name='Próximo ano' if int(year(p))<target else 'Ano anterior',exact=True).click()
 def ready(p,id):
  p.evaluate("""id=>{for(const month of ['2025-11','2025-12']){for(const [t,extra] of [['recordResult',{usd:0}],['confirmNoMovement',{kind:'contribution',confirmation:true}],['confirmNoMovement',{kind:'withdrawal',confirmation:true}],['finalizeMonth',{confirmFlows:true}]]){const r=JPWPlanning.commands.execute(t,{accountId:id,month,...extra},JPWPlanning.queries.token(id));if(!r.ok)throw Error(JSON.stringify(r));}}JPWPlanning.ui.render(true)}""",id)
 def form(p):return p.locator('dialog[data-pl-submit=finalizeYear]')
 def fill(p):
  form(p).locator('[name=signerName]').fill('Pessoa de Teste');form(p).locator('[name=declarationAccepted]').check()
 def snapshot(p):return p.evaluate('JSON.stringify(S)')
 def geometry(p):
  g=p.evaluate("""()=>{const r=e=>{const x=e.getBoundingClientRect();return {x:x.x,y:x.y,w:x.width,h:x.height,right:x.right,bottom:x.bottom}};return {width:innerWidth,height:innerHeight,overflow:document.documentElement.scrollWidth>innerWidth,dialogs:[...document.querySelectorAll('dialog[open]')].map(r),targets:[...document.querySelectorAll('.pl-year-nav button,.pl-table-options>summary,.pl-annual-projection>summary,dialog[open] button,dialog[open] input:not([type=checkbox]),.pl-annual-declaration')].filter(e=>e.getClientRects().length).map(r)}}""")
  assert not g['overflow'],g
  for d in g['dialogs']:assert d['x']>=-2 and d['y']>=-2 and d['right']<=g['width']+2 and d['bottom']<=g['height']+2,d
  for t in g['targets']:assert t['w']>=42 and t['h']>=42,t
 def navigation():
  c,p,id,errors=boot()
  try:
   second=p.evaluate("""()=>{const r=JPWPlanning.commands.execute('createAccount',{name:'Outra conta sintética',startMonth:'2028-01',initialUsd:2000,profileId:'base',monthlyContributionUsd:0,goals:{adequate:null,ideal:{value:100,currency:'USD'}}},JPWPlanning.queries.token());if(!r.ok)throw Error(JSON.stringify(r));JPWPlanning.ui.render(true);return r.accountId}""");raw=snapshot(p);assert year(p)=='2026';assert p.locator('[data-pl-grid-month]').count()==12;assert not p.locator('[data-pl-table-options]').evaluate('e=>e.open');assert not p.get_by_role('button',name='Registrar rentabilidade',exact=True).is_visible();assert p.locator('[data-pl-phase-total],[data-pl-annual]').count()==0
   go(p,2025);assert p.locator('[data-pl-calendar-month]').count()==12 and p.locator('[data-pl-outside-plan-month]').count()==10 and p.locator('[data-pl-grid-month]').count()==2 and p.get_by_role('button',name='Ano anterior',exact=True).is_disabled();assert 'Período parcial' in p.locator('[data-pl-annual-overview]').inner_text();go(p,2035);assert p.locator('[data-pl-calendar-month]').count()==12 and p.locator('[data-pl-outside-plan-month]').count()==2 and p.locator('[data-pl-grid-month]').count()==10 and p.get_by_role('button',name='Próximo ano',exact=True).is_disabled()
   p.get_by_role('tab',name='Consolidado',exact=True).click();p.get_by_role('tab',name='Preenchimento mensal',exact=True).click();assert year(p)=='2035';p.locator('[data-pl-account]').select_option(second);assert year(p)=='2028';p.locator('[data-pl-account]').select_option(id);assert year(p)=='2035';assert snapshot(p)==raw;assert not errors,errors
  finally:c.close()
 run('one civil year,12months/partial boundaries, arrows, account-session year and no duplicate strip',navigation)
 def options():
  c,p,id,errors=boot()
  try:
   before=snapshot(p);p.get_by_text('Opções da tabela',exact=True).click();p.locator('[data-pl-month]').select_option('2026-05');assert p.locator('[data-pl-grid-month]:visible').count()==1;p.locator('[data-pl-month]').select_option('');assert p.locator('[data-pl-grid-month]:visible').count()==12;p.locator('[data-pl-period]').select_option('current');assert p.locator('[data-pl-grid-month]:visible').count()==2;p.get_by_role('button',name='Ano anterior',exact=True).click();assert p.locator('[data-pl-grid-month]:visible').count()==0;p.get_by_role('button',name='Mostrar todos os meses deste ano',exact=True).click();assert year(p)=='2025' and p.locator('[data-pl-grid-month]:visible').count()==2;assert snapshot(p)==before;assert not errors,errors
  finally:c.close()
 run('collapsed options filter only the chosen year and never write financial data',options)
 def signing():
  c,p,id,errors=boot()
  try:
   go(p,2025);assert p.get_by_role('button',name='Encerrar ano',exact=True).is_disabled();ready(p,id);assert not p.get_by_role('button',name='Encerrar ano',exact=True).is_disabled();assert '2 de 2 meses finalizados' in p.locator('[data-pl-annual-overview]').inner_text();before=snapshot(p)
   p.get_by_role('button',name='Encerrar ano',exact=True).click();d=form(p);assert not d.locator('[name=declarationAccepted]').is_checked();d.locator('[data-pl-submit]').click();assert snapshot(p)==before;d.locator('[name=signerName]').fill('Pessoa de Teste');d.locator('[data-pl-submit]').click();assert snapshot(p)==before;d.get_by_role('button',name='Cancelar',exact=True).click();assert snapshot(p)==before
   p.get_by_role('button',name='Encerrar ano',exact=True).click();assert not form(p).locator('[name=declarationAccepted]').is_checked();fill(p);geometry(p);p.screenshot(path=str(OUT/'termo-revisao.png'));form(p).locator('[data-pl-submit]').click();assert 'Ano encerrado' in p.locator('[data-pl-annual-overview]').inner_text();assert p.evaluate('(id)=>JPWPlanning.queries.account(id).plan.annualClosures.years["2025"].signerName',id)=='Pessoa de Teste'
   p.get_by_role('button',name='Ver termo',exact=True).click();assert 'Pessoa de Teste' in p.get_by_role('dialog').inner_text();p.get_by_role('dialog').get_by_role('button',name='Cancelar',exact=True).click();go(p,2026);p.locator('[data-pl-inline-open=result][data-pl-inline-month="2026-01"]').click();assert p.locator('dialog.pl-inline-popup[open]').is_visible();assert not errors,errors
  finally:c.close()
 run('mandatory name/declaration, cancel, confirmed seal and subsequent actual editor',signing)
 def blocking():
  c,p,id,errors=boot()
  try:
   p.locator('[data-pl-inline-open=result][data-pl-inline-month="2026-01"]').click();d=p.get_by_role('dialog');assert '2025' in d.inner_text() and 'Revisar 2025' in d.inner_text();d.get_by_role('button',name='Revisar 2025',exact=True).click();assert year(p)=='2025';ready(p,id);p.get_by_role('button',name='Encerrar ano',exact=True).click();fill(p);form(p).locator('[data-pl-submit]').click();p.get_by_role('button',name='Reabrir ano',exact=True).click();d=p.locator('dialog[data-pl-submit=reopenYear]');before=snapshot(p);d.locator('[data-pl-submit]').click();assert snapshot(p)==before;d.locator('[name=reason]').fill('Conferir comprovantes');d.locator('[data-pl-submit]').click();assert 'termo anterior foi invalidado' in p.locator('[data-pl-annual-overview]').inner_text();go(p,2026);p.locator('[data-pl-inline-open=result][data-pl-inline-month="2026-01"]').click();assert '2025' in p.get_by_role('dialog').inner_text();assert not errors,errors
  finally:c.close()
 run('blocked actual cell points to first unsigned year; explicit annual reopening blocks it again',blocking)
 def conflict():
  c,p,id,errors=boot()
  try:
   go(p,2025);ready(p,id);p.get_by_role('button',name='Encerrar ano',exact=True).click();fill(p);other=c.new_page();other.goto(URL);other.wait_for_selector('[data-pl-start]');assert other.evaluate('(id)=>JPWPlanning.commands.execute("setProjection",{accountId:id,month:"2027-01",rate:.04,contributionUsd:200},JPWPlanning.queries.token(id)).status',id)=='CONFIRMED';form(p).locator('[data-pl-submit]').click();assert form(p).is_visible() and form(p).locator('[name=signerName]').input_value()=='Pessoa de Teste';assert 'mudaram' in form(p).inner_text() or 'mudou' in form(p).inner_text();assert not form(p).locator('[name=declarationAccepted]').is_checked();assert not errors,errors
  finally:c.close()
 run('two-tab stale annual confirmation keeps name, clears authorization and refuses adoption',conflict)
 def failures():
  for mode in ['quota','unknown']:
   c,p,id,errors=boot()
   try:
    go(p,2025);ready(p,id);p.get_by_role('button',name='Encerrar ano',exact=True).click();fill(p);before=snapshot(p)
    p.evaluate("""mode=>{const get=Storage.prototype.getItem,set=Storage.prototype.setItem;let written=false;Storage.prototype.setItem=function(k,v){if(k===PlanningStore.KEY&&mode==='quota')throw Error('Synthetic quota');const r=set.call(this,k,v);if(k===PlanningStore.KEY)written=true;return r};Storage.prototype.getItem=function(k){if(k===PlanningStore.KEY&&mode==='unknown'&&written)throw Error('Synthetic readback');return get.call(this,k)}}""",mode)
    form(p).locator('[data-pl-submit]').click();assert form(p).is_visible() and form(p).locator('[name=signerName]').input_value()=='Pessoa de Teste';assert snapshot(p)==before
    if mode=='unknown':assert form(p).locator('[data-pl-submit]').is_disabled();assert p.evaluate('PlanningStore.status().status')=='UNKNOWN'
    assert not errors,errors
   finally:c.close()
 run('quota/UNKNOWN preserve annual draft and never announce a confirmed signature',failures)
 def responsive():
  for width,height in [(320,700),(390,480),(820,800),(1440,1000)]:
   for theme in ['light','dark']:
    c,p,id,errors=boot(width,height)
    try:
     p.evaluate('t=>document.documentElement.dataset.theme=t',theme);geometry(p);go(p,2025);ready(p,id);p.screenshot(path=str(OUT/f'year-{width}-{theme}.png'));p.get_by_role('button',name='Encerrar ano',exact=True).click();fill(p);geometry(p);p.screenshot(path=str(OUT/f'term-{width}-{theme}.png'));assert not errors,errors
    finally:c.close()
 run('320px through desktop, low height and light/dark preserve bounded table and term targets',responsive)
 def native():
  with tempfile.TemporaryDirectory(prefix='pp-annual-zoom-') as folder:
   pref=Path(folder)/'Default';pref.mkdir();(pref/'Preferences').write_text(json.dumps({'partition':{'default_zoom_level':{'x':math.log(2)/math.log(1.2)}}}));c=pw.chromium.launch_persistent_context(folder,headless=True,no_viewport=True,executable_path=os.environ.get('PP_CHROMIUM'),args=['--window-size=1440,1000'],timezone_id='America/Sao_Paulo',reduced_motion='reduce')
   try:
    _,p,id,errors=boot(context=c);assert abs(p.evaluate('outerWidth/innerWidth')-2)<.01;go(p,2025);ready(p,id);assert p.locator('[data-pl-calendar-month]').count()==12 and p.locator('[data-pl-outside-plan-month]').count()==10;geometry(p);header=p.locator('[data-pl-monthly-grid] thead th').evaluate_all('nodes=>nodes.map(e=>e.getBoundingClientRect().left)');assert all(len(cells)==len(header) and all(abs(x-y)<=2 for x,y in zip(cells,header)) for cells in p.locator('[data-pl-calendar-month]').evaluate_all('nodes=>nodes.map(e=>[...e.children].map(c=>c.getBoundingClientRect().left))'));p.screenshot(path=str(OUT/'calendar-native200.png'));p.get_by_role('button',name='Encerrar ano',exact=True).click();fill(p);geometry(p);p.screenshot(path=str(OUT/'term-native200.png'));assert not errors,errors
   finally:c.close()
 run('native200 bounded annual review and44px controls',native)
 def full_calendar():
  for start in ['2026-01','2026-03','2026-12']:
   for width in [320,1440]:
    for theme in ['light','dark']:
     c,p,id,errors=boot(width=width,start=start)
     try:
      p.evaluate('t=>document.documentElement.dataset.theme=t',theme);before=snapshot(p);domain=p.evaluate('(id)=>JSON.stringify(JPWPlanning.queries.view({accountId:id}).rows)',id);assert len(json.loads(domain))==120
      for target in [2026,2027,2035 if start.endswith('-01') else 2036]:
       go(p,target);rows=p.locator('[data-pl-calendar-month]');assert rows.count()==12;expected=p.evaluate('(id)=>JPWPlanning.queries.account(id).plan.startMonth',id);end=p.evaluate('s=>JPWPlanning.engine.addMonths(s,119)',expected)
       data=rows.evaluate_all("""nodes=>nodes.map(e=>{const b=e.getBoundingClientRect(),c=e.children[0],s=getComputedStyle(c);return {month:e.dataset.plCalendarMonth,outside:e.hasAttribute('data-pl-outside-plan-month'),text:e.innerText,controls:e.querySelectorAll('button,input,select,textarea,a,[tabindex],[contenteditable]').length,disabled:e.getAttribute('aria-disabled'),cells:e.children.length,background:s.backgroundColor,color:s.color,height:b.height,lefts:[...e.children].map(n=>n.getBoundingClientRect().left)}})""")
       headers=p.locator('[data-pl-monthly-grid] thead th').evaluate_all('nodes=>nodes.map(e=>e.getBoundingClientRect().left)');assert len({r['month'] for r in data})==12
       for r in data:
        outside=r['month']<expected or r['month']>end;assert r['outside']==outside and r['cells']==len(headers);assert all(abs(x-y)<=2 for x,y in zip(headers,r['lefts']))
        if outside:
         assert r['controls']==0 and r['disabled']=='true' and r['height']>=44 and all(x not in r['text'] for x in ['US$','Preencher','Finalizado']);assert ('Anterior ao plano' if r['month']<expected else 'Após o término do plano') in r['text'];assert r['text'].count('—')==len(headers)-1
         # Both themes keep readable text; no whole-row disabled opacity.
         def rgb(s):return [int(v.strip())/255 for v in s[s.index('(')+1:s.index(')')].split(',')[:3]]
         def lum(s):
          v=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in rgb(s)];return .2126*v[0]+.7152*v[1]+.0722*v[2]
         l1,l2=sorted([lum(r['background']),lum(r['color'])]);assert (l2+.05)/(l1+.05)>=4.5,r
       assert not p.evaluate('document.documentElement.scrollWidth>innerWidth');assert snapshot(p)==before and p.evaluate('(id)=>JSON.stringify(JPWPlanning.queries.view({accountId:id}).rows)',id)==domain
      if start.endswith('-03'):
       go(p,2026);p.screenshot(path=str(OUT/f'calendar-{width}-{theme}.png'));assert '0 de 10 meses finalizados' in p.locator('[data-pl-annual-overview]').inner_text()
      assert not errors,errors
     finally:c.close()
 run('Jan/Mar/Dec starts:12calendar rows, gray blocked boundaries, unchanged120model months and contrast/alignment',full_calendar)
 def outside_filter():
  c,p,id,errors=boot(start='2026-03')
  try:
   before=snapshot(p);p.get_by_text('Opções da tabela',exact=True).click();p.locator('[data-pl-month]').select_option('2026-01');assert p.locator('[data-pl-calendar-month]:visible').count()==1;row=p.locator('[data-pl-outside-plan-month="2026-01"]');box=row.bounding_box();p.mouse.click(box['x']+12,box['y']+12);assert p.locator('dialog[open]').count()==0 and row.locator('button,input,select,[tabindex]').count()==0
   p.get_by_role('button',name='Gerenciar ▾',exact=True).click();p.get_by_role('menuitem',name='Registrar rentabilidade',exact=True).click();d=p.locator('dialog[data-pl-submit=result]');assert d.locator('[name=flowMonth]').get_attribute('placeholder')=='11/2026';d.get_by_role('button',name='Cancelar',exact=True).click();assert snapshot(p)==before
   for month in ['2026-01','2036-03']:
    results=p.evaluate("""({id,month})=>['recordResult','recordContribution','recordWithdrawal','confirmNoMovement','finalizeMonth','setProjection'].map(type=>JPWPlanning.commands.execute(type,{accountId:id,month,usd:0,brl:0,kind:'contribution',confirmation:true,confirmFlows:true,rate:0,contributionUsd:0},JPWPlanning.queries.token(id)).status)""",{'id':id,'month':month});assert all(r!='CONFIRMED' for r in results);assert snapshot(p)==before
   p.locator('[data-pl-month]').select_option('');assert p.locator('[data-pl-calendar-month]:visible').count()==12;assert not errors,errors
  finally:c.close()
 run('outside-month filtering never selects a financial month or opens an editor; commands still refuse out-of-plan dates',outside_filter)

 b.close()
server.shutdown();server.server_close();report['status']='PASS' if len(report['checks'])==10 and not report['failures'] else 'FAIL';(OUT/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False));raise SystemExit(report['status']!='PASS')

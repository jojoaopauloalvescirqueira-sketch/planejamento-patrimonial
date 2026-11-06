"""Chart sources, toggles and layout in isolated synthetic Chromium origins."""
import functools,json,math,os,tempfile,threading,traceback
from pathlib import Path
from datetime import datetime,timezone
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/chart-series-20261105';OUT.mkdir(parents=True,exist_ok=True)
class Quiet(SimpleHTTPRequestHandler):
 def log_message(self,*_):pass
class Server(ThreadingHTTPServer):request_queue_size=128
server=Server(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT)));threading.Thread(target=server.serve_forever,daemon=True).start();URL=f'http://127.0.0.1:{server.server_port}/'
report={'checks':[],'failures':[],'limits':['Synthetic data only; Safari and manual screen reader NOT_RUN.']}
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('PP_CHROMIUM'))
 def boot(width=1440,height=1000,context=None,before=False,start='2026-11'):
  c=context or browser.new_context(viewport={'width':width,'height':height},timezone_id='America/Sao_Paulo',reduced_motion='reduce');network=[]
  def route(r):
   if r.request.url.startswith('https://api.frankfurter.dev/'):r.fulfill(content_type='application/json',body=json.dumps({'base':'USD','quote':'BRL','date':'2026-11-05','rate':5}))
   elif r.request.url.startswith(URL):r.continue_()
   else:network.append(r.request.url);r.abort()
  c.route('**/*',route);p=c.new_page();p.set_default_timeout(7000);errors=[];p.on('pageerror',lambda e:errors.append(str(e)));p.clock.set_fixed_time(datetime(2026,11,5,15,tzinfo=timezone.utc));p.goto(URL+('outputs/chart-series-20261105/before/dist/' if before else 'dist/'));p.wait_for_selector('[data-pl-start]')
  id=p.evaluate("""start=>{const r=JPWPlanning.commands.execute('createAccount',{name:'Demonstração · dados fictícios',startMonth:start,initialUsd:1000,profileId:'base',monthlyContributionUsd:200,goals:{adequate:null,ideal:{value:100,currency:'USD'}}},JPWPlanning.queries.token());if(!r.ok)throw Error(JSON.stringify(r));JPWPlanning.ui.selectView('consolidated');return r.accountId}""",start)
  p.locator('[data-pl-account]').select_option(id)
  return c,p,id,errors,network
 def snapshot(p):return p.evaluate('JSON.stringify({document:S,stored:localStorage.getItem(PlanningStore.KEY)})')
 def run(name,fn):
  try:fn();report['checks'].append(name);print('PASS',name,flush=True)
  except Exception as e:report['failures'].append({'name':name,'error':str(e),'traceback':traceback.format_exc()});print('FAIL',name,str(e),flush=True)
 def cmd(p,id,t,month,extra={}):
  return p.evaluate("""a=>{const r=JPWPlanning.commands.execute(a.t,{accountId:a.id,month:a.month,...a.extra},JPWPlanning.queries.token(a.id));if(!r.ok)throw Error(JSON.stringify(r));JPWPlanning.ui.render(true);return r}""",{'id':id,'t':t,'month':month,'extra':extra})
 def geometry(p):
  g=p.locator('[data-pl-wealth-chart]').evaluate("""e=>({overflow:document.documentElement.scrollWidth>innerWidth,rects:[...e.querySelectorAll('button,select')].filter(n=>n.getClientRects().length).map(n=>{const r=n.getBoundingClientRect();return {w:r.width,h:r.height,x:r.x,right:r.right}}),width:innerWidth})""")
  assert not g['overflow'],g
  for r in g['rects']:assert r['w']>=43.9 and r['h']>=43.9 and r['x']>=-1 and r['right']<=g['width']+1,g
 def original():
  before_path=ROOT/'outputs/chart-series-20261105/before/dist'
  if before_path.exists():
   c,p,id,errors,network=boot(before=True)
   try:p.locator('.pl-chart').first.screenshot(path=str(OUT/'before.png'))
   finally:c.close()
  c,p,id,errors,network=boot()
  try:
   chart=p.locator('[data-pl-wealth-chart]');assert chart.locator('[aria-pressed=true]').count()==3
   assert chart.locator('[data-pl-chart-series=planning]').get_attribute('d');assert not chart.locator('.pl-chart-blocked').count();assert 'Simulação do formulário — não representa saldo realizado' in chart.inner_text().replace('\xa0',' ')
   assert p.locator('[data-pl-summary-group=projection] .pl-metric strong').first.inner_text().replace('\xa0',' ')=='—';assert p.evaluate("JPWPlanning.queries.sheetView().rows[1].closeUsd") is None
   svg=chart.locator('[data-pl-chart]');svg.focus();p.keyboard.press('Home');tip=chart.locator('.pl-chart-tip');assert 'US$ 1.230,00' in tip.locator('[data-pl-tip-series=planning]').inner_text().replace('\xa0',' ');assert '—' in tip.locator('[data-pl-tip-series=confirmed]').inner_text().replace('\xa0',' ');assert 'US$ 200,00' in tip.locator('[data-pl-tip-series=planned-contributions]').inner_text().replace('\xa0',' ');p.keyboard.press('ArrowRight');assert 'US$ 1.466,90' in tip.locator('[data-pl-tip-series=planning]').inner_text().replace('\xa0',' ');p.keyboard.press('Tab');chart.screenshot(path=str(OUT/'after.png'));assert not errors and not network,(errors,network)
  finally:c.close()
 run('original form simulation visible while confirmed balance waits, correct1230/1466.90 tooltips and before/after',original)
 def toggles():
  c,p,id,errors,network=boot()
  try:
   chart=p.locator('[data-pl-wealth-chart]');before=snapshot(p)
   for k in ['planning','contributions','confirmed']:
    b=chart.locator(f'[data-pl-chart-toggle={k}]');b.focus();p.keyboard.press('Space');assert b.get_attribute('aria-pressed')=='false';assert b.evaluate('(e)=>e===document.activeElement');assert snapshot(p)==before
   assert not chart.locator('svg[data-pl-chart]').count();assert 'Selecione uma categoria' in chart.inner_text().replace('\xa0',' ')
   chart.locator('[data-pl-chart-toggle=planning]').click();assert chart.locator('[data-pl-chart-series]').count()==1
   svg=chart.locator('[data-pl-chart]');svg.focus();p.keyboard.press('Home');assert chart.locator('[data-pl-tip-series]').count()==1
   chart.locator('[data-pl-chart-toggle=contributions]').click();assert chart.locator('[data-pl-chart-series]').count()==3
   chart.locator('[data-pl-chart-period]').select_option('year:2027');assert chart.locator('[data-pl-chart-toggle=confirmed]').get_attribute('aria-pressed')=='false';svg=chart.locator('[data-pl-chart]');svg.focus();p.keyboard.press('Home');assert 'US$ 600,00' in chart.locator('[data-pl-tip-series=planned-contributions]').inner_text().replace('\xa0',' ')
   p.get_by_role('tab',name='Preenchimento mensal',exact=True).click();p.get_by_role('tab',name='Consolidado',exact=True).click();assert chart.locator('[data-pl-chart-toggle=confirmed]').get_attribute('aria-pressed')=='false';assert snapshot(p)==before
   p.reload();p.wait_for_selector('[data-pl-start]');p.get_by_role('tab',name='Consolidado',exact=True).click();assert chart.locator('[aria-pressed=true]').count()==3;assert not errors and not network,(errors,network)
  finally:c.close()
 run('independent toggles, all-off state, focus, period/session selection and read-only financial storage',toggles)
 def cashflows():
  c,p,id,errors,network=boot(start='2026-10')
  try:
   cmd(p,id,'recordContribution','2026-11',{'usd':20,'brl':100});chart=p.locator('[data-pl-wealth-chart]');svg=chart.locator('[data-pl-chart]');svg.focus();p.keyboard.press('Home');p.keyboard.press('ArrowRight');assert '—' in chart.locator('[data-pl-tip-series=registered-contributions]').inner_text().replace('\xa0',' ');assert 'Preenchimento de aportes incompleto' in chart.locator('.pl-chart-tip').inner_text().replace('\xa0',' ')
   cmd(p,id,'confirmNoMovement','2026-10',{'kind':'contribution','confirmation':True});svg=chart.locator('[data-pl-chart]');svg.focus();p.keyboard.press('Home');assert 'US$ 0,00' in chart.locator('[data-pl-tip-series=registered-contributions]').inner_text().replace('\xa0',' ');p.keyboard.press('ArrowRight');assert 'US$ 20,00' in chart.locator('[data-pl-tip-series=registered-contributions]').inner_text().replace('\xa0',' ')
   assert not errors and not network,(errors,network)
  finally:c.close()
 run('registered deposits have gaps, explicit zero and known effective movements without initial capital',cashflows)
 def layout():
  c,p,id,errors,network=boot()
  try:
   for theme in ['light','dark']:
    p.evaluate('(t)=>document.documentElement.dataset.theme=t',theme)
    for width,height in [(1440,1000),(820,700),(390,650),(320,480)]:
     p.set_viewport_size({'width':width,'height':height});geometry(p);p.locator('[data-pl-wealth-chart]').scroll_into_view_if_needed();p.locator('[data-pl-wealth-chart]').screenshot(path=str(OUT/f'chart-{theme}-{width}.png'));svg=p.locator('[data-pl-chart]');svg.focus();p.keyboard.press('End');tip=p.locator('.pl-chart-tip');assert tip.is_visible();r=tip.bounding_box();assert r['x']>=-1 and r['x']+r['width']<=width+1,(width,r)
   assert not errors and not network,(errors,network)
  finally:c.close()
 run('light/dark320/390/820/1440 and low height:44px controls, keyboard tooltips and no horizontal overflow',layout)
 def pdf():
  c,p,id,errors,network=boot()
  try:
   p.locator('[data-pl-chart-toggle=confirmed]').click();p.locator('[data-pl-chart-toggle=contributions]').click();before=snapshot(p);p.evaluate('window.print=()=>{}');p.get_by_role('button',name='Gerar PDF',exact=True).click();r=p.locator('[data-pl-report]');assert r.locator('[data-pl-chart-series]').count()==1;assert r.locator('[data-pl-chart-series=planning]').get_attribute('d');assert 'Simulação do formulário — não representa saldo realizado' in r.inner_text().replace('\xa0',' ');assert r.locator('[data-pl-chart-key]').count()==1;assert r.locator('.pl-report-projection strong').inner_text().replace('\xa0',' ')=='—';p.pdf(path=str(OUT/'chart-report.pdf'),format='A4',landscape=True);p.evaluate("dispatchEvent(new Event('afterprint'))");assert snapshot(p)==before
   assert not errors and not network,(errors,network)
  finally:c.close()
 run('PDF matches visible chart sources and retains actual blocked metrics without mutations',pdf)
 def native():
  with tempfile.TemporaryDirectory(prefix='pp-chart200-') as folder:
   d=Path(folder)/'Default';d.mkdir();(d/'Preferences').write_text(json.dumps({'partition':{'default_zoom_level':{'x':math.log(2)/math.log(1.2)}}}))
   c=pw.chromium.launch_persistent_context(folder,headless=True,no_viewport=True,executable_path=os.environ.get('PP_CHROMIUM'),args=['--window-size=1440,1000'],timezone_id='America/Sao_Paulo',reduced_motion='reduce')
   try:
    _,p,id,errors,network=boot(context=c);ratio=p.evaluate('({outer:outerWidth,inner:innerWidth,css:getComputedStyle(document.documentElement).zoom})');assert abs(ratio['outer']/ratio['inner']-2)<.01 and ratio['css']=='1',ratio;report['nativeZoom']=ratio
    for theme in ['light','dark']:
     p.evaluate('(t)=>document.documentElement.dataset.theme=t',theme);geometry(p);p.locator('[data-pl-chart-toggle=planning]').focus();p.keyboard.press('Space');assert p.locator('[data-pl-chart-toggle=planning]').get_attribute('aria-pressed')=='false';p.keyboard.press('Space');p.locator('[data-pl-wealth-chart]').screenshot(path=str(OUT/f'chart-native200-{theme}.png'))
    assert not errors and not network,(errors,network)
   finally:c.close()
 run('native200 browser zoom, both themes,44px controls and keyboard toggles',native)
 browser.close()
server.shutdown();report['status']='PASS' if len(report['checks'])==6 and not report['failures'] else 'FAIL';(OUT/'browser-result.json').write_text(json.dumps(report,indent=2));print(json.dumps(report));raise SystemExit(0 if report['status']=='PASS' else 1)

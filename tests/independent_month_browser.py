"""Independent monthly confirmations; isolated synthetic Chromium profiles only."""
import functools,json,math,os,tempfile,threading,traceback
from pathlib import Path
from datetime import datetime,timezone
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/independent-month-browser';OUT.mkdir(parents=True,exist_ok=True)
class Quiet(SimpleHTTPRequestHandler):
 def log_message(self,*_):pass
server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT)));threading.Thread(target=server.serve_forever,daemon=True).start();BASE=f'http://127.0.0.1:{server.server_port}/'
report={'checks':[],'failures':[]}
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('PP_CHROMIUM'))
 def boot(width=1440,height=1000,theme='light',start='2026-09',initial=1000,context=None,before=False):
  c=context or browser.new_context(viewport={'width':width,'height':height},timezone_id='America/Sao_Paulo',reduced_motion='reduce');c.route('https://api.frankfurter.dev/**',lambda r:r.fulfill(content_type='application/json',body=json.dumps({'base':'USD','quote':'BRL','date':'2026-11-05','rate':5})))
  p=c.new_page();p.set_default_timeout(7000);errors=[];p.on('pageerror',lambda e:errors.append(str(e)));p.clock.set_fixed_time(datetime(2026,11,5,15,tzinfo=timezone.utc));p.goto(BASE+('outputs/independent-month-20261105/before/dist/' if before else 'dist/'));p.wait_for_selector('[data-pl-start]')
  id=p.evaluate("""c=>{const r=JPWPlanning.commands.execute('createAccount',{name:'Demonstração · dados fictícios',startMonth:c.start,initialUsd:c.initial,profileId:'base',monthlyContributionUsd:200,goals:{adequate:null,ideal:{value:100,currency:'USD'}}},JPWPlanning.queries.token());if(!r.ok)throw Error(JSON.stringify(r));JPWPlanning.ui.selectView('monthly');return r.accountId}""",{'start':start,'initial':initial});p.locator('[data-pl-account]').select_option(id);p.evaluate('theme=>document.documentElement.dataset.theme=theme',theme);return c,p,id,errors
 def cmd(p,id,t,month,extra={}):
  return p.evaluate("""a=>{const r=JPWPlanning.commands.execute(a.type,{accountId:a.id,month:a.month,...a.extra},JPWPlanning.queries.token(a.id));if(!r.ok)throw Error(JSON.stringify(r));JPWPlanning.ui.render(true);return r}""",{'id':id,'type':t,'month':month,'extra':extra})
 def open_result(p,month):
  p.locator(f'[data-pl-inline-open=result][data-pl-inline-month="{month}"]').click();d=p.locator('dialog.pl-inline-popup[open]');d.wait_for(state='visible');return d
 def complete(p,id,month,usd=0):
  cmd(p,id,'recordResult',month,{'usd':usd})
  for kind in ['contribution','withdrawal']:cmd(p,id,'confirmNoMovement',month,{'kind':kind,'confirmation':True})
 def run(name,fn):
  try:fn();report['checks'].append(name);print('PASS',name,flush=True)
  except Exception as e:report['failures'].append({'name':name,'error':str(e),'traceback':traceback.format_exc()});print('FAIL',name,str(e),flush=True)
 def snapshot(p):return p.evaluate('JSON.stringify(S)')
 def geometry(p,d,paired=True):
  g=d.evaluate("""e=>{const r=e=>{const x=e.getBoundingClientRect();return {x:x.x,y:x.y,w:x.width,h:x.height,right:x.right,bottom:x.bottom}};return {d:r(e),width:innerWidth,height:innerHeight,overflow:document.documentElement.scrollWidth>innerWidth,input:r(e.querySelector('[name=value]')),output:r(e.querySelector('[data-pl-result-rate] output')),controls:[...e.querySelectorAll('button,input:not([type=hidden])')].filter(n=>n.getClientRects().length).map(r)}}""")
  assert not g['overflow'],g
  assert g['d']['x']>=-2 and g['d']['right']<=g['width']+2 and g['d']['y']>=-2 and g['d']['bottom']<=g['height']+2,g
  for r in g['controls']:assert r['w']>=43.9 and r['h']>=43.9,r
  if paired:assert g['output']['x']>=g['input']['right']+6 and abs(g['input']['y']-g['output']['y'])<=2,g
  else:assert g['output']['y']>=g['input']['bottom'],g
 def derived():
  c,p,id,errors=boot(start='2026-11')
  try:
   d=open_result(p,'2026-11');before=snapshot(p);assert d.locator('[name=value]').count()==1 and d.locator('select').count()==0;assert d.locator('[data-pl-result-rate] input').count()==0
   for value,expected in [('30','3%'),('-25','-2,5%'),('0','0%'),('','—')]:d.locator('[name=value]').fill(value);assert d.locator('output').inner_text()==expected;assert snapshot(p)==before
   d.locator('[name=value]').fill('30');geometry(p,d);d.screenshot(path=str(OUT/'result-desktop.png'));d.locator('[data-pl-inline-save]').click();assert '3%' in d.locator('[data-pl-inline-review]').inner_text();d.get_by_role('button',name='Voltar ao preenchimento',exact=True).click();assert d.locator('[name=value]').input_value()=='30';assert d.locator('[data-pl-action=inline-confirm]').is_hidden();assert snapshot(p)==before;assert not errors,errors
  finally:c.close()
 run('USD entry and adjacent read-only rate derive positive/negative/zero without writes; back preserves input',derived)
 def independent():
  c,p,id,errors=boot()
  try:
   complete(p,id,'2026-10',5);before=snapshot(p);check=p.locator('[data-pl-check-month="2026-10"]');assert check.is_enabled();check.click();d=p.locator('dialog[data-pl-submit=finalize]');assert 'Você está confirmando os registros deste mês' in d.inner_text();assert snapshot(p)==before;d.screenshot(path=str(OUT/'closure-awaiting-balance.png'));d.locator('[data-pl-submit]').click();assert check.get_attribute('aria-checked')=='true';row=p.locator('[data-pl-grid-month="2026-10"]');assert row.locator('[data-pl-month-value=open]').inner_text()=='—';assert 'Aguardando' in row.locator('.pl-month-balance').inner_text();p.screenshot(path=str(OUT/'october-finalized-with-gap.png'))
   complete(p,id,'2026-09',0);cmd(p,id,'finalizeMonth','2026-09',{'confirmFlows':True});assert check.get_attribute('aria-checked')=='true';assert '1.005,00' in row.locator('.pl-month-balance').inner_text();assert row.locator('[data-pl-month-value=rate]').inner_text()=='0,5%';p.reload();p.wait_for_selector('[data-pl-start]');p.evaluate("JPWPlanning.ui.selectView('monthly')");assert p.locator('[data-pl-check-month="2026-10"]').get_attribute('aria-checked')=='true';assert not errors,errors
  finally:c.close()
 run('October check confirms independently; later September confirmation derives exact balances and reload preserves checks',independent)
 def missing():
  for initial,month in [(1000,'2026-10'),(0,'2026-09')]:
   c,p,id,errors=boot(initial=initial)
   try:
    d=open_result(p,month);d.locator('[name=value]').fill('0');assert d.locator('output').inner_text()=='—';assert 'Percentual indisponível enquanto faltar o saldo de abertura' in d.locator('[data-pl-result-rate]').inner_text();d.locator('[data-pl-inline-save]').click();assert 'indisponível' in d.locator('[data-pl-inline-review]').inner_text();d.locator('[data-pl-action=inline-confirm]').click();assert p.evaluate('(x)=>JPWPlanning.queries.account(x.id).plan.results[x.month].usd',{'id':id,'month':month})==0;assert not errors,errors
   finally:c.close()
 run('unknown or nonpositive opening never creates a percentage but explicit USD zero can be confirmed',missing)
 def corrections():
  c,p,id,errors=boot()
  try:
   for month in ['2026-09','2026-10']:complete(p,id,month,0);cmd(p,id,'finalizeMonth',month,{'confirmFlows':True})
   cmd(p,id,'recordResult','2026-09',{'usd':10});assert p.locator('[data-pl-check-month="2026-10"]').get_attribute('aria-checked')=='true';assert 'Aguardando' in p.locator('[data-pl-grid-month="2026-10"] .pl-month-balance').inner_text();cmd(p,id,'finalizeMonth','2026-09',{'confirmFlows':True});assert '1.010,00' in p.locator('[data-pl-grid-month="2026-10"] .pl-month-balance').inner_text();cmd(p,id,'recordResult','2026-10',{'usd':5});assert p.locator('[data-pl-check-month="2026-10"]').get_attribute('aria-checked')=='false';assert not errors,errors
  finally:c.close()
 run('upstream correction preserves downstream check; own correction reopens only own month',corrections)
 def responsive():
  for width,height in [(320,700),(1440,460),(1440,1000)]:
   for theme in ['light','dark']:
    c,p,id,errors=boot(width,height,theme,start='2026-11')
    try:
     d=open_result(p,'2026-11');d.locator('[name=value]').fill('30');geometry(p,d,width>360);d.screenshot(path=str(OUT/f'result-{width}-{height}-{theme}.png'));d.locator('[name=value]').press('Tab');assert d.locator('[data-pl-inline-save]').evaluate('e=>e===document.activeElement');assert not errors,errors
    finally:c.close()
 run('themes320px and low height keep fields legible, within viewport,44px targets and keyboard focus',responsive)
 def native():
  with tempfile.TemporaryDirectory(prefix='pp-independent-native200-') as folder:
   d=Path(folder)/'Default';d.mkdir();(d/'Preferences').write_text(json.dumps({'partition':{'default_zoom_level':{'x':math.log(2)/math.log(1.2)}}}))
   c=pw.chromium.launch_persistent_context(folder,headless=True,executable_path=os.environ.get('PP_CHROMIUM'),viewport=None,args=['--window-size=1440,1000'])
   try:
    for theme in ['light','dark']:
     _,p,id,errors=boot(context=c,start='2026-11',theme=theme);ratio=p.evaluate('({outer:outerWidth,inner:innerWidth,css:getComputedStyle(document.documentElement).zoom})');assert abs(ratio['outer']/ratio['inner']-2)<.01 and ratio['css']=='1',ratio;report['nativeZoom']=ratio;popup=open_result(p,'2026-11');popup.locator('[name=value]').fill('30');geometry(p,popup,p.evaluate('innerWidth')>360);popup.screenshot(path=str(OUT/f'native200-{theme}.png'));assert not errors,errors;p.close()
   finally:c.close()
 run('native Chromium200percent browser zoom preserves paired entry and focus targets in both themes',native)
 def before():
  c,p,id,errors=boot(start='2026-11',before=True)
  try:d=open_result(p,'2026-11');d.locator('[name=value]').fill('30');d.screenshot(path=str(OUT/'result-before.png'));assert not errors,errors
  finally:c.close()
 run('before screenshot captured from preserved baseline with same synthetic values',before)
 browser.close()
server.shutdown();server.server_close();report['status']='PASS' if len(report['checks'])==7 and not report['failures'] else 'FAIL';(OUT/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False));raise SystemExit(report['status']!='PASS')

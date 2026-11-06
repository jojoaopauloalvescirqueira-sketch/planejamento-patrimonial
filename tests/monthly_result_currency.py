"""Past-open warning and USD-only actual results. Synthetic documents only."""
import functools,json,os,threading,traceback
from pathlib import Path
from datetime import datetime,timezone
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/monthly-result-currency';OUT.mkdir(parents=True,exist_ok=True)
class Quiet(SimpleHTTPRequestHandler):
 def log_message(self,*_):pass
server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT/'dist')));threading.Thread(target=server.serve_forever,daemon=True).start();URL=f'http://127.0.0.1:{server.server_port}/'
report={'checks':[],'failures':[]}
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('PP_CHROMIUM'))
 def boot(width=1440,theme='light',initial=1000):
  c=browser.new_context(viewport={'width':width,'height':1000},timezone_id='America/Sao_Paulo',reduced_motion='reduce');c.route('https://api.frankfurter.dev/**',lambda r:r.fulfill(content_type='application/json',body=json.dumps({'base':'USD','quote':'BRL','date':'2026-11-05','rate':5})))
  p=c.new_page();p.set_default_timeout(5000);p.clock.set_fixed_time(datetime(2026,11,5,15,tzinfo=timezone.utc));p.goto(URL);p.wait_for_selector('[data-pl-start]');errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
  id=p.evaluate("""initial=>{const r=JPWPlanning.commands.execute('createAccount',{name:'Demonstração · dados fictícios',startMonth:'2026-10',initialUsd:initial,profileId:'base',monthlyContributionUsd:200,goals:{adequate:null,ideal:{value:100,currency:'USD'}}},JPWPlanning.queries.token());if(!r.ok)throw Error(JSON.stringify(r));JPWPlanning.ui.selectView('monthly');return r.accountId}""",initial);p.locator('[data-pl-account]').select_option(id);p.evaluate('theme=>document.documentElement.dataset.theme=theme',theme);return c,p,id,errors
 def run(name,fn):
  try:fn();report['checks'].append(name);print('PASS',name,flush=True)
  except Exception as e:report['failures'].append({'name':name,'error':str(e),'traceback':traceback.format_exc()});print('FAIL',name,str(e),flush=True)
 def popup(p,month='2026-10'):
  p.locator(f'[data-pl-inline-open=result][data-pl-inline-month="{month}"]').click();d=p.locator('dialog.pl-inline-popup[open]');d.wait_for(state='visible');return d
 def color(p,month):return p.locator(f'[data-pl-grid-month="{month}"]>th').evaluate('e=>getComputedStyle(e).backgroundColor')
 def colors():
  for theme in ['light','dark']:
   c,p,id,errors=boot(theme=theme)
   try:
    expected='rgb(253, 235, 237)' if theme=='light' else 'rgb(68, 32, 40)';assert color(p,'2026-10')==expected,color(p,'2026-10');assert color(p,'2026-11')!=expected and color(p,'2026-12')!=expected
    p.screenshot(path=str(OUT/f'pending-{theme}.png'))
    p.evaluate("""id=>{for(const [type,payload] of [['recordResult',{usd:0}],['confirmNoMovement',{kind:'contribution',confirmation:true}],['confirmNoMovement',{kind:'withdrawal',confirmation:true}],['finalizeMonth',{confirmFlows:true}]]){const r=JPWPlanning.commands.execute(type,{accountId:id,month:'2026-10',...payload},JPWPlanning.queries.token(id));if(!r.ok)throw Error(JSON.stringify(r))}JPWPlanning.ui.render(true)}""",id)
    assert color(p,'2026-10')!=expected;assert p.locator('[data-pl-check-month="2026-10"]').get_attribute('aria-checked')=='true';assert not errors,errors
   finally:c.close()
 run('past-open red in both themes; finalized/current/future keep distinct states',colors)
 def result():
  c,p,id,errors=boot()
  try:
   before=p.evaluate('JSON.stringify(S)');d=popup(p);assert d.locator('select').count()==0;assert d.locator('label').filter(has_text='Resultado realizado · US$').count()==1
   for value,rate in [('30','3%'),('-25','-2,5%'),('0','0%')]:
    d.locator('[name=value]').fill(value);assert rate in d.locator('[data-pl-result-rate]').inner_text();assert p.evaluate('JSON.stringify(S)')==before
   d.locator('[name=value]').fill('30');d.locator('[data-pl-inline-save]').click();assert '3%' in d.locator('[data-pl-inline-review]').inner_text();assert p.evaluate('JSON.stringify(S)')==before
   d.locator('[data-pl-action=inline-confirm]').click();assert p.evaluate('(id)=>JPWPlanning.queries.account(id).plan.results["2026-10"].usd',id)==30
   d=popup(p);assert d.locator('[name=value]').input_value()=='30';assert '3%' in d.locator('[data-pl-result-rate]').inner_text();d.locator('[name=value]').fill('-25');d.locator('[data-pl-inline-save]').click();d.locator('[data-pl-action=inline-confirm]').click();assert p.evaluate('(id)=>JPWPlanning.queries.account(id).plan.results["2026-10"].previous.usd',id)==30;assert not errors,errors
  finally:c.close()
 run('single USD input derives positive/negative/zero rates; confirmed correction keeps history',result)
 def missing():
  for initial,month in [(1000,'2026-11'),(0,'2026-10')]:
   c,p,id,errors=boot(initial=initial)
   try:
    d=popup(p,month);d.locator('[name=value]').fill('0');assert 'indisponível' in d.locator('[data-pl-result-rate]').inner_text().lower();assert '0%' not in d.locator('[data-pl-result-rate]').inner_text();d.locator('[data-pl-inline-save]').click();assert 'indisponível' in d.locator('[data-pl-inline-review]').inner_text().lower();assert not errors,errors
   finally:c.close()
 run('unavailable or zero opening never fabricates a percentage',missing)
 def invalid():
  c,p,id,errors=boot()
  try:
   before=p.evaluate('JSON.stringify(S)');d=popup(p)
   for value in ['', 'abc', '0.001', '-1000.01']:
    d.locator('[name=value]').fill(value);d.locator('[data-pl-inline-save]').click();assert d.locator('[data-pl-action=inline-confirm]').count()==0 or d.locator('[data-pl-action=inline-confirm]').is_hidden();assert p.evaluate('JSON.stringify(S)')==before
   d.locator('[name=value]').fill('25');d.locator('[data-pl-inline-save]').click();d.get_by_role('button',name='Voltar ao preenchimento',exact=True).click();d.locator('[name=value]').fill('26');assert d.locator('[data-pl-action=inline-confirm]').is_hidden();d.locator('[data-pl-action=inline-cancel]').click();assert p.evaluate('JSON.stringify(S)')==before;assert not errors,errors
  finally:c.close()
 run('invalid cents/limits/blank and edited review cannot write; cancel preserves facts',invalid)
 def responsive():
  for width in [320,1440]:
   for theme in ['light','dark']:
    c,p,id,errors=boot(width,theme)
    try:
     d=popup(p);d.locator('[name=value]').fill('-25');assert '-2,5%' in d.locator('[data-pl-result-rate]').inner_text();d.locator('[data-pl-inline-save]').click();assert p.evaluate('document.documentElement.scrollWidth<=innerWidth');rect=d.bounding_box();assert rect['x']>=-2 and rect['x']+rect['width']<=width+2;d.screenshot(path=str(OUT/f'editor-{width}-{theme}.png'));assert not errors,errors
    finally:c.close()
 run('USD editor and computed rate fit320px and desktop in both themes',responsive)
 browser.close()
server.shutdown();server.server_close();report['status']='PASS' if len(report['checks'])==5 and not report['failures'] else 'FAIL';(OUT/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False));raise SystemExit(report['status']!='PASS')

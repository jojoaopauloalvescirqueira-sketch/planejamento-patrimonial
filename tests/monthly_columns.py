"""Read-only percentage column, blue current month and registered capital baseline."""
import functools,json,os,threading,traceback
from pathlib import Path
from datetime import datetime,timezone
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/monthly-columns';OUT.mkdir(parents=True,exist_ok=True)
class Quiet(SimpleHTTPRequestHandler):
 def log_message(self,*_):pass
class Server(ThreadingHTTPServer):request_queue_size=128
server=Server(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT/'dist')));threading.Thread(target=server.serve_forever,daemon=True).start();URL=f'http://127.0.0.1:{server.server_port}/';report={'checks':[],'failures':[]}
with sync_playwright() as pw:
 b=pw.chromium.launch(headless=True,executable_path=os.environ.get('PP_CHROMIUM'))
 def boot(width=1440,theme='light'):
  c=b.new_context(viewport={'width':width,'height':1000},timezone_id='America/Sao_Paulo',reduced_motion='reduce');c.route('https://api.frankfurter.dev/**',lambda r:r.fulfill(content_type='application/json',body=json.dumps({'base':'USD','quote':'BRL','date':'2026-11-05','rate':5})))
  p=c.new_page();p.set_default_timeout(5000);p.clock.set_fixed_time(datetime(2026,11,5,15,tzinfo=timezone.utc));p.goto(URL);p.wait_for_selector('[data-pl-start]');errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
  id=p.evaluate("""()=>{const r=JPWPlanning.commands.execute('createAccount',{name:'Demonstração · dados fictícios',startMonth:'2026-11',initialUsd:100,profileId:'base',monthlyContributionUsd:20,goals:{adequate:null,ideal:{value:100,currency:'USD'}}},JPWPlanning.queries.token());if(!r.ok)throw Error(JSON.stringify(r));JPWPlanning.ui.selectView('monthly');return r.accountId}""");p.locator('[data-pl-account]').select_option(id);p.evaluate('t=>document.documentElement.dataset.theme=t',theme);return c,p,id,errors
 def run(name,f):
  try:f();report['checks'].append(name);print('PASS',name,flush=True)
  except Exception as e:report['failures'].append({'name':name,'error':str(e),'traceback':traceback.format_exc()});print('FAIL',name,str(e),flush=True)
 def columns():
  for width in [320,820,1100,1440]:
   for theme in ['light','dark']:
    c,p,id,errors=boot(width,theme)
    try:
     row=p.locator('[data-pl-grid-month="2026-11"]');cell=row.locator('[data-pl-month-value=rate]');assert cell.is_visible();assert cell.inner_text()=='—';assert cell.locator('input,select,button').count()==0
     p.evaluate("""id=>{const r=JPWPlanning.commands.execute('recordResult',{accountId:id,month:'2026-11',usd:15},JPWPlanning.queries.token(id));if(!r.ok)throw Error(JSON.stringify(r));JPWPlanning.ui.render(true)}""",id)
     assert cell.inner_text()=='15%';assert row.locator('[data-pl-inline-open=result]').inner_text().count('15%')==0
     geom=p.evaluate("""()=>{const r=document.querySelector('[data-pl-grid-month="2026-11"]'),rate=r.querySelector('[data-pl-month-value=rate]'),money=r.querySelector('[data-pl-inline-open=result]'),wide=document.querySelector('[data-pl-monthly-layout]').dataset.plMonthlyLayout==='wide';return {columns:document.querySelectorAll('[data-pl-monthly-grid] thead th').length,wide,readonly:!rate.closest('button'),left:rate.getBoundingClientRect().right<=money.getBoundingClientRect().left+2,overflow:document.documentElement.scrollWidth>innerWidth,color:getComputedStyle(r.querySelector('th')).backgroundColor}}""")
     assert geom['columns']==(8 if geom['wide'] else 4) and geom['readonly'] and geom['left'] and not geom['overflow'],geom
     assert geom['color']==('rgb(232, 241, 255)' if theme=='light' else 'rgb(23, 50, 79)'),geom
     if width in [320,1440]:p.screenshot(path=str(OUT/f'table-{width}-{theme}.png'))
     p.locator('[data-pl-inline-open=result][data-pl-inline-month="2026-11"]').focus();p.keyboard.press('Enter');d=p.locator('dialog.pl-inline-popup[open]');assert d.locator('select').count()==0;assert d.locator('[name=value]').input_value()=='15';d.locator('[name=value]').press('Escape');assert not errors,errors
    finally:c.close()
 run('8wide/4compact columns; readonly percentage beforeUSD; blue current row; keyboard and themes',columns)
 def capital():
  c,p,id,errors=boot()
  try:
   before=p.evaluate('JSON.stringify(S)');p.get_by_role('tab',name='Consolidado',exact=True).click();summary=p.locator('[data-pl-summary-group=confirmed]');assert summary.locator('.pl-metric strong').first.inner_text().endswith('100,00');assert 'Capital inicial cadastrado' in summary.inner_text();assert 'aguardando' in summary.inner_text().lower();assert p.evaluate('JSON.stringify(S)')==before
   p.evaluate('window.print=()=>{}');p.get_by_role('button',name='Gerar PDF',exact=True).click();r=p.locator('[data-pl-report]');assert r.locator('.pl-metric strong').first.inner_text().endswith('100,00');assert 'Capital inicial cadastrado' in r.inner_text();p.pdf(path=str(OUT/'capital-inicial.pdf'),format='A4',landscape=True);p.evaluate("dispatchEvent(new Event('afterprint'))");p.screenshot(path=str(OUT/'capital-inicial.png'));assert not errors,errors
  finally:c.close()
 run('registered100 capital appears in Consolidado andPDF without any monthly closure or write',capital)
 b.close()
server.shutdown();server.server_close();report['status']='PASS' if len(report['checks'])==2 and not report['failures'] else 'FAIL';(OUT/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False));raise SystemExit(report['status']!='PASS')

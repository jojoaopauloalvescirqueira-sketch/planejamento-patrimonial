"""Warm-cache upgrade: an old cached engine must never enter the new application."""
import json,mimetypes,os,threading,urllib.parse
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from datetime import datetime,timezone
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/asset-cache';OUT.mkdir(parents=True,exist_ok=True);requests=[]
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*_):pass
 def do_GET(self):
  parts=urllib.parse.urlsplit(self.path);requests.append(self.path);path=parts.path
  if path=='/warm.html':data=b'<!doctype html><html><head><script src="assets/planning-engine.js"></script></head><body><p id="warm">Old engine warm-cache test</p></body></html>';kind='text/html';cache='no-store'
  elif path.startswith('/quote'):data=json.dumps({'base':'USD','quote':'BRL','date':'2026-11-05','rate':5}).encode();kind='application/json';cache='no-store'
  else:
   rel='index.html' if path in ['/','/index.html'] else path.lstrip('/');p=ROOT/'dist'/rel
   if '..' in Path(rel).parts or not p.is_file():self.send_error(404);return
   if rel=='assets/planning-engine.js' and not parts.query:p=ROOT/'tests/fixtures/planning-engine-source.js'
   data=p.read_bytes();kind=mimetypes.guess_type(str(p))[0] or 'application/octet-stream';cache='no-store' if rel=='index.html' else 'public, max-age=31536000'
   if rel=='assets/quote.js':data=data.replace(b'https://api.frankfurter.dev/v2/rate/USD/BRL',b'/quote')
  self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Cache-Control',cache);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
class Server(ThreadingHTTPServer):request_queue_size=128
server=Server(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start();base=f'http://127.0.0.1:{server.server_port}/';result={}
try:
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('PP_CHROMIUM'));ctx=browser.new_context(viewport={'width':1440,'height':1000},timezone_id='America/Sao_Paulo');page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.clock.set_fixed_time(datetime(2026,11,5,15,tzinfo=timezone.utc));page.goto(base+'warm.html?visit=1');page.wait_for_selector('#warm');raw=page.evaluate("""()=>{const plan=JPWPlanning.engine.createPlan({startMonth:'2026-11',initialUsd:1000,profileId:'base',monthlyContributionUsd:200,goals:{adequate:null,ideal:{value:100,currency:'USD'}}},{id:'cache-plan',now:'2026-11-05T15:00:00Z'});const document={patrimonialPlanning:{schemaVersion:1,revision:1,accounts:[{id:'cache-account',name:'Conta sintética de cache',active:true,plan}],archive:[],audit:[],operations:[]}};const raw=JSON.stringify({format:'planejamento_patrimonial_state',schemaVersion:1,revision:1,document,writeId:'synthetic-cache'});localStorage.setItem('planejamento_patrimonial_state_v1',raw);return raw;}""");assert page.evaluate("JPWPlanning.engine.timeline(JSON.parse(localStorage.getItem('planejamento_patrimonial_state_v1')).document.patrimonialPlanning.accounts[0].plan,{month:'2026-11'})[0].closeUsd")==1230
  warm_count=requests.count('/assets/planning-engine.js');page.goto(base+'warm.html?visit=2');page.wait_for_selector('#warm');assert requests.count('/assets/planning-engine.js')==warm_count,'old engine really came from HTTP cache'
  page.goto(base+'index.html?upgrade=1');
  try:page.wait_for_selector('[data-pl-start]')
  except Exception:
   page.screenshot(path=str(OUT/'startup-failure.png'));(OUT/'startup-failure.json').write_text(json.dumps({'errors':errors,'body':page.locator('body').inner_text(),'requests':requests},ensure_ascii=False,indent=2));raise
  page.get_by_role('tab',name='Preenchimento mensal',exact=True).click();nov=page.locator('[data-pl-grid-month="2026-11"] .pl-month-balance .pl-money-primary');dec=page.locator('[data-pl-grid-month="2026-12"]');assert nov.inner_text().endswith('1.000,00');assert dec.locator('[data-pl-month-value=open]').inner_text()=='—';assert 'Aguardando fechamento' in dec.inner_text();assert page.evaluate("localStorage.getItem('planejamento_patrimonial_state_v1')")==raw
  build=page.locator('#app-version').inner_text();assert '/assets/planning-engine.js?v='+build in requests;urls=page.locator('script[src],link[href]').evaluate_all("els=>els.map(e=>e.getAttribute('src')||e.getAttribute('href'))");assert all(u.endswith('?v='+build) for u in urls if u.startswith(('assets/','favicon')));page.screenshot(path=str(OUT/'upgrade.png'));result={'status':'PASS','candidate':build,'oldEngineReadFromCache':True,'newEngineRequestedWithBuild':True,'financialDocumentUnchanged':True,'checks':1};ctx.close();browser.close()
finally:server.shutdown();server.server_close()
(OUT/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))

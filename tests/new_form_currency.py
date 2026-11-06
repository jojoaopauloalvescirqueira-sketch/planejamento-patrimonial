"""The Comece aqui action starts a new BRL form; explicit resume preserves units."""
import functools,json,os,threading
from pathlib import Path
from datetime import datetime,timezone
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/new-form-currency';OUT.mkdir(exist_ok=True,parents=True)
class Quiet(SimpleHTTPRequestHandler):
 def log_message(self,*_):pass
class Server(ThreadingHTTPServer):request_queue_size=128
server=Server(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT/'dist')));threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}/';result={}
try:
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True,executable_path=os.environ.get('PP_CHROMIUM'));c=b.new_context(viewport={'width':1440,'height':1000},timezone_id='America/Sao_Paulo');c.route('https://api.frankfurter.dev/**',lambda r:r.fulfill(content_type='application/json',body=json.dumps({'base':'USD','quote':'BRL','date':'2026-11-05','rate':5})));p=c.new_page();p.clock.set_fixed_time(datetime(2026,11,5,15,tzinfo=timezone.utc));p.goto(url);p.wait_for_selector('[data-pl-start]');errors=[];p.on('pageerror',lambda e:errors.append(str(e)));cases=[]
  def units():return [p.locator('#pl-native-custoMoeda').input_value(),p.locator('#pl-native-sonhoMoeda').input_value()]
  def close():p.locator('dialog[open] [data-pl-action=close]').first.click()
  def new():p.get_by_role('button',name='Preencher novo formulário',exact=True).click()
  new();assert units()==['BRL','BRL'];close();cases.append('first configuration BRL/BRL')
  p.evaluate("""()=>{const r=JPWPlanning.commands.execute('createAccount',{name:'Plano USD existente',startMonth:'2026-11',initialUsd:1000,profileId:'base',monthlyContributionUsd:200,goals:{adequate:null,ideal:{value:100,currency:'USD'}}},JPWPlanning.queries.token());if(!r.ok)throw Error(JSON.stringify(r));JPWPlanning.ui.render(true)}""");raw=p.evaluate('JSON.stringify(S)');new();assert units()==['BRL','BRL'];assert p.locator('#pl-native-sonhoBRL').input_value()=='';p.locator('#pl-native-custoValor').fill('5000');p.locator('#pl-native-sonhoBRL').fill('10000');assert units()==['BRL','BRL'];p.screenshot(path=str(OUT/'novo-brl.png'));close();cases.append('existing USD plan never initializes a new form in USD')
  p.get_by_role('button',name='Continuar rascunho',exact=True).click();assert units()==['BRL','BRL'];assert p.locator('#pl-native-custoValor').input_value()=='5000' and p.locator('#pl-native-sonhoBRL').input_value()=='10000';p.locator('#pl-native-sonhoMoeda').select_option('USD');p.locator('#pl-native-sonhoBRL').fill('125');close();cases.append('resume retains typed BRL values and explicit unit changes')
  new();assert units()==['BRL','BRL'] and p.locator('#pl-native-sonhoBRL').input_value()=='';close();p.get_by_role('button',name='Continuar rascunho',exact=True).click();assert units()==['BRL','USD'] and p.locator('#pl-native-sonhoBRL').input_value()=='125';close();assert p.evaluate('JSON.stringify(JPWPlanning.ui.backupDrafts()).includes("125")');cases.append('fresh BRL form never replaces a prior USD draft')
  p.get_by_role('button',name='Editar plano existente',exact=True).click();assert units()==['BRL','USD'];assert p.locator('#pl-native-sonhoBRL').input_value()=='100';close();assert p.evaluate('JSON.stringify(S)')==raw;cases.append('explicit edit retains saved100USD; navigation never writes financial state')
  for width in [320,1440]:
   p.set_viewport_size({'width':width,'height':850});new();assert units()==['BRL','BRL'];assert p.evaluate('document.documentElement.scrollWidth<=innerWidth');close()
  assert not errors,errors;result={'status':'PASS','candidate':p.locator('#app-version').inner_text(),'cases':cases,'checks':len(cases),'financialStateUnchanged':True};c.close();b.close()
finally:server.shutdown();server.server_close()
(OUT/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))

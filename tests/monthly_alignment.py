"""Geometry-only monthly regression. No public or personal financial data."""
import functools,json,math,os,tempfile,threading,traceback
from pathlib import Path
from datetime import datetime,timezone
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/monthly-alignment';OUT.mkdir(parents=True,exist_ok=True)
BEFORE=os.environ.get('PP_ALIGNMENT_BEFORE')=='1'
class Quiet(SimpleHTTPRequestHandler):
 def log_message(self,*_):pass
class Server(ThreadingHTTPServer):request_queue_size=128
server=Server(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT)));threading.Thread(target=server.serve_forever,daemon=True).start();URL=f'http://127.0.0.1:{server.server_port}/'+('outputs/monthly-alignment-before/dist/' if BEFORE else 'dist/')
report={'candidate':None,'checks':[],'failures':[],'measurements':[]}
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('PP_CHROMIUM'))
 def boot(width=1440,context=None):
  ctx=context or browser.new_context(viewport={'width':width,'height':1000},timezone_id='America/Sao_Paulo',reduced_motion='reduce');ctx.route('https://api.frankfurter.dev/**',lambda r:r.abort());page=ctx.new_page();page.clock.set_fixed_time(datetime(2026,11,5,15,tzinfo=timezone.utc));page.goto(URL,wait_until='load');page.wait_for_selector('[data-pl-start]');page.evaluate("""()=>{let r=JPWPlanning.commands.execute('createAccount',{name:'Demonstração · dados fictícios',broker:'',login:'',server:'',startMonth:'2026-11',initialUsd:1000,profileId:'base',monthlyContributionUsd:200,goals:{adequate:null,ideal:{value:100,currency:'USD'}}},JPWPlanning.queries.token());if(!r.ok)throw Error(JSON.stringify(r));JPWPlanning.ui.selectView('monthly')}""");report['candidate']=page.locator('#app-version').inner_text();return ctx,page
 def measure(page):
  return page.evaluate("""()=>{const rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height,cx:r.x+r.width/2,cy:r.y+r.height/2,right:r.right}},row=document.querySelector('[data-pl-grid-month="2026-11"]'),wide=document.querySelector('[data-pl-monthly-layout]').dataset.plMonthlyLayout==='wide',controls=[...document.querySelectorAll('[data-pl-grid-month] .pl-inline-cell,[data-pl-grid-month] .pl-month-check')].filter(e=>e.getClientRects().length).map(rect),headers=[...document.querySelectorAll('[data-pl-monthly-grid] thead th')];let data={wide,width:innerWidth,rowHeight:rect(row).h,overflow:document.documentElement.scrollWidth>innerWidth,controls};if(wide){const slots=[row.querySelector('[data-pl-select-month]'),row.cells[1].firstElementChild,row.querySelector('[data-pl-month-value=rate]'),row.querySelector('[data-pl-inline-open=result]'),row.querySelector('[data-pl-inline-open=withdrawal]'),row.querySelector('[data-pl-inline-open=contribution]'),row.querySelector('.pl-month-balance')||row.cells[6],row.querySelector('.pl-month-check')].map(rect);data.slotCenterSpread=Math.max(...slots.map(s=>s.cy))-Math.min(...slots.map(s=>s.cy));data.headerOffsets=[3,4,5,7].map(i=>(()=>{const range=document.createRange();range.selectNodeContents(headers[i]);const r=range.getBoundingClientRect();return Math.abs(r.x+r.width/2-slots[i].cx)})());const range=document.createRange();range.selectNodeContents(row.cells[1].firstElementChild);data.initialAmountRightOffset=Math.abs(range.getBoundingClientRect().right-(row.cells[1].getBoundingClientRect().right-parseFloat(getComputedStyle(row.cells[1]).paddingRight)));const button=row.querySelector('[data-pl-inline-open=result]'),content=button.querySelector('.pl-cell-content'),arrow=button.querySelector('.pl-cell-chevron');data.resultSpacing={paddingLeft:parseFloat(getComputedStyle(button).paddingLeft),paddingRight:parseFloat(getComputedStyle(button).paddingRight),contentCenterOffset:Math.abs(rect(content).cy-rect(button).cy),arrowCenterOffset:Math.abs(rect(arrow).cy-rect(button).cy)};}return data;}""")
 def check(name,fn):
  try:fn();report['checks'].append(name)
  except Exception as e:report['failures'].append({'case':name,'error':str(e),'traceback':traceback.format_exc()})
 def layout(width,theme):
  ctx,page=boot(width)
  try:
   page.evaluate('t=>document.documentElement.dataset.theme=t',theme);before=page.evaluate('JSON.stringify(JPWPlanning.queries.snapshot())');m=measure(page);report['measurements'].append({'theme':theme,**m});assert not m['overflow'],m
   for c in m['controls']:assert c['w']>=42 and c['h']>=42,c
   if m['wide']:assert m['slotCenterSpread']<=2 and max(m['headerOffsets'])<=2 and m['initialAmountRightOffset']<=2 and m['rowHeight']<=56,m
   if m['wide']:assert min(m['resultSpacing']['paddingLeft'],m['resultSpacing']['paddingRight'])>=10 and m['resultSpacing']['contentCenterOffset']<=2 and m['resultSpacing']['arrowCenterOffset']<=2,m
   assert page.evaluate('JSON.stringify(JPWPlanning.queries.snapshot())')==before
   control=page.locator('[data-pl-check-month="2026-11"]')
   if not control.is_visible():page.locator('[data-pl-select-month="2026-11"]').click()
   wrapper=control.locator('..');note=wrapper.locator('[role=tooltip]');assert note.inner_text().startswith('Preencha ')
   assert note.evaluate('e=>getComputedStyle(e).opacity')=='0'
   wrapper.focus();assert note.evaluate('e=>getComputedStyle(e).opacity')=='1'
   bounds=note.bounding_box();assert bounds['x']>=-2 and bounds['x']+bounds['width']<=width+2,bounds
   assert control.is_disabled() and control.get_attribute('aria-describedby')==note.get_attribute('id')
   wrapper.press('Tab');assert note.evaluate('e=>getComputedStyle(e).opacity')=='0'
   assert page.evaluate('JSON.stringify(JPWPlanning.queries.snapshot())')==before
   if width==1440 or (width==320 and theme=='light'):
    page.screenshot(path=str(OUT/f'{"before" if BEFORE else "after"}-{width}-{theme}.png'))
   if m['wide']:
    page.evaluate("""()=>{const id=JPWPlanning.queries.snapshot().accounts[0].id;for(const [t,p] of [['recordResult',{usd:-20}],['recordContribution',{usd:30,brl:150}],['confirmNoMovement',{kind:'withdrawal',confirmation:true}]]){const r=JPWPlanning.commands.execute(t,{accountId:id,month:'2026-11',...p},JPWPlanning.queries.token(id));if(!r.ok)throw Error(JSON.stringify(r));}JPWPlanning.ui.render(true)}""");m=measure(page);assert m['slotCenterSpread']<=2,m;assert page.locator('[data-pl-inline-open=result][data-pl-inline-month="2026-11"] .pl-money-secondary').count()==0;assert m['resultSpacing']['contentCenterOffset']<=2 and m['resultSpacing']['arrowCenterOffset']<=2,m
  finally:ctx.close()
 for width in [320,820,1100,1440]:
  for theme in ['light','dark']:check(f'{width}px-{theme}-common-baseline-and-column-headers',lambda w=width,t=theme:layout(w,t))
 def native():
  with tempfile.TemporaryDirectory(prefix='pp-align-zoom-') as folder:
   pref=Path(folder)/'Default';pref.mkdir();(pref/'Preferences').write_text(json.dumps({'partition':{'default_zoom_level':{'x':math.log(2)/math.log(1.2)}}}));ctx=pw.chromium.launch_persistent_context(folder,headless=True,no_viewport=True,executable_path=os.environ.get('PP_CHROMIUM'),args=['--window-size=1440,1000'],timezone_id='America/Sao_Paulo',reduced_motion='reduce')
   try:
    _,page=boot(context=ctx);ratio=page.evaluate('outerWidth/innerWidth');assert abs(ratio-2)<.01;report['nativeZoom']=ratio;m=measure(page);assert not m['overflow'];page.screenshot(path=str(OUT/'after-native200.png'))
   finally:ctx.close()
 check('native200-no-overflow',native);browser.close()
server.shutdown();server.server_close();report['status']='PASS' if len(report['checks'])==9 and not report['failures'] else 'FAIL';(OUT/('before-result.json' if BEFORE else 'result.json')).write_text(json.dumps(report,indent=2));print(json.dumps({'status':report['status'],'checks':len(report['checks']),'failures':report['failures'],'candidate':report['candidate']}));raise SystemExit(report['status']!='PASS')

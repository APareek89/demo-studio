import json, pathlib, subprocess
from playwright.sync_api import sync_playwright
root=pathlib.Path('/Users/macbook/Documents/demo-studio'); out=pathlib.Path('/tmp/demo-noise-final-20260925')
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True,args=['--mute-audio'])
 for mode in ['baseline','current']:
  context=browser.new_context(viewport={'width':1440,'height':1000})
  def route(r):
   url=r.request.url
   if not url.startswith('http://127.0.0.1:8913/') or r.request.method!='GET': return r.abort()
   rel=url.split(':8913/',1)[1].split('?',1)[0]
   if mode=='baseline' and rel in ['web/player/player.js','web/player/live-voice.js']:
    return r.fulfill(body=subprocess.check_output(['git','show','cf33be27363a622d0fb0a710a0ef8edb3a3ceb4b:'+rel],cwd=root),content_type='text/javascript')
   return r.continue_()
  context.route('**/*',route)
  context.route_web_socket('**/*',lambda ws:ws.close())
  page=context.new_page();page.goto('http://127.0.0.1:8913/evals/player_contract.html');page.get_by_role('button',name='Run checks').click();page.wait_for_function("document.querySelector('#summary').textContent.includes('failed')",timeout=45000)
  report=page.evaluate('playerContractReport');(out/f'player-browser-{mode}.json').write_text(json.dumps(report,indent=2)+'\n')
  print(mode,report['passed'],'/',report['total'],[{k:c.get(k) for k in ['name','error']} for c in report['cases'] if not c['pass']],flush=True)
  context.close()
 browser.close()

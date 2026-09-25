import json,pathlib,time
from playwright.sync_api import sync_playwright
root=pathlib.Path('/Users/macbook/Documents/demo-studio');out=root/'output/playwright/gallery-preview-2026-09-25';data=json.loads((root/'output/gallery-preview-2026-09-25/preview.json').read_text());rows=[];errors=[];blocked=[]
def check(name,value):
 rows.append({'name':name,'passed':bool(value)})
 if not value: raise AssertionError(name)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True,args=['--mute-audio'])
 c=b.new_context(viewport={'width':1440,'height':960})
 def route(r):
  if r.request.url.startswith('http://127.0.0.1:8911/') and r.request.method=='GET': return r.continue_()
  blocked.append(r.request.url);return r.abort()
 c.route('**/*',route);c.route_web_socket('**/*',lambda w:w.close());page=c.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://127.0.0.1:8911/?mute=1');page.wait_for_function('!!window.galleryPreview')
 for width,height in [(1440,960),(390,844)]:
  page.set_viewport_size({'width':width,'height':height})
  for i,scene in enumerate(data['scenes']):
   page.get_by_role('button',name='View '+scene['title'],exact=True).click();page.wait_for_function("galleryPreview().phase==='narrating'");page.get_by_role('button',name='Pause preview',exact=True).click()
   page.screenshot(path=str(out/f'final-{width}-{i+1:02}.png'))
   g=page.evaluate('''()=>{const s=galleryPreview(),p=document.querySelector('#stage').getBoundingClientRect(),c=document.querySelector('#featureCard').getBoundingClientRect(),a=document.querySelector('audio');return {s,stage:{w:p.width,h:p.height},card:{x:c.left-p.left,y:c.top-p.top,r:c.right-p.left,b:c.bottom-p.top},overflow:document.documentElement.scrollWidth>innerWidth,text:document.querySelector('#speech').textContent,src:a.getAttribute('src'),image:document.querySelector('#focusImage').getAttribute('src'),time:a.currentTime,rate:a.playbackRate};}''')
   point=g['s']['focus'];card=g['card'];stem=f'{width}px scene {i+1}'
   check(stem+' uses exact original caption and clip',g['text']==scene['lines'][0]['text'] and g['src']==scene['lines'][0]['audio'] and g['rate']==1)
   check(stem+' correct photo',g['image']==scene['image'])
   check(stem+' viewport bounded',not g['overflow'] and card['x']>=0 and card['r']<=g['stage']['w']+1 and card['b']<=g['stage']['h']+1)
   check(stem+' focus clear of caption',0<=point['x']<=g['stage']['w'] and 0<=point['y']<=g['stage']['h'] and not (card['x']<=point['x']<=card['r'] and card['y']<=point['y']<=card['b']))
   before=page.evaluate('galleryPreview().audioTime');page.wait_for_timeout(150);check(stem+' audio remains paused',abs(page.evaluate('galleryPreview().audioTime')-before)<0.01)
  print('geometry done',width,flush=True)
 page.get_by_role('button',name='View Wheel design',exact=True).click();page.wait_for_function("galleryPreview().phase==='focusing'");page.get_by_role('button',name='Pause preview').click();t=page.locator('#imagePlane').evaluate('(e)=>getComputedStyle(e).transform');page.wait_for_timeout(200);check('Pause freezes a camera move',page.locator('#imagePlane').evaluate('(e)=>getComputedStyle(e).transform')==t)
 page.get_by_role('button',name='Next feature').click();page.get_by_role('button',name='View Panoramic roof',exact=True).click();page.wait_for_function("galleryPreview().index===4&&galleryPreview().phase==='narrating'");check('Rapid next/jump keeps newest photo and clip',page.locator('#focusImage').get_attribute('src')==data['scenes'][4]['image'] and page.locator('audio').get_attribute('src')==data['scenes'][4]['lines'][0]['audio'])
 page.set_viewport_size({'width':1440,'height':960});page.wait_for_function('galleryPreview().paused');before=page.evaluate('galleryPreview().audioTime');page.get_by_role('button',name='Resume preview').click();page.wait_for_timeout(350);check('Resize during narration preserves and resumes audio',page.evaluate('galleryPreview().audioTime')>before+0.1)
 page.get_by_role('button',name='View Wheel design',exact=True).click();page.wait_for_function("galleryPreview().phase==='focusing'");page.set_viewport_size({'width':390,'height':844});page.wait_for_function("galleryPreview().phase==='gallery'");check('Resize during camera move releases animation ownership',page.evaluate('!galleryPreview().playing&&galleryPreview().animations===0'))
 page.emulate_media(reduced_motion='reduce');page.get_by_role('button',name='View Wireless charging',exact=True).click();page.wait_for_function("galleryPreview().phase==='narrating'");check('Reduced motion does not magnify image',page.evaluate('galleryPreview().focus.z===1'))
 # Completion/replay regression uses a deliberate test seek; natural full playback is a separate saved receipt.
 page.wait_for_function('Number.isFinite(document.querySelector("audio").duration)');page.evaluate('document.querySelector("audio").currentTime=document.querySelector("audio").duration-.05');page.wait_for_function("galleryPreview().phase==='complete'");page.set_viewport_size({'width':1440,'height':960});page.wait_for_timeout(200);check('Completion survives resize',page.evaluate("galleryPreview().phase==='complete'"));page.get_by_role('button',name='Replay the gallery').click();page.wait_for_function("galleryPreview().phase==='narrating'");check('Replay starts first feature',page.evaluate('galleryPreview().index===0'))
 page.get_by_role('button',name='Return to gallery').click();page.wait_for_timeout(150);check('Return to gallery clears all playback',page.evaluate('!galleryPreview().playing&&galleryPreview().animations===0&&document.querySelector("audio").paused'))
 check('No script errors or external requests',not errors and not blocked)
 b.close()
receipt={'passed':sum(r['passed'] for r in rows),'total':len(rows),'checks':rows,'errors':errors,'blocked':blocked,'muted':True,'microphone':False,'provider_calls':0,'scope':'Standalone gallery; fixture seek only for completion/replay test; natural full playback recorded separately'}
(pathlib.Path('/tmp/demo-noise-final-20260925')/'gallery-browser.json').write_text(json.dumps(receipt,indent=2)+'\n');print(receipt['passed'],receipt['total'],flush=True)

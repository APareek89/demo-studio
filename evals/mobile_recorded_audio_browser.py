"""Actual mounted player + native WebKit audio, without autoplay/mute bypass.

All WAV files contain digital silence but retain real audio tracks. APIs are
local deterministic callbacks, capture is forbidden, and external sockets are
blocked. Safari/CriOS user-agent profiles are emulation, not physical iPhones.
"""
import argparse,io,json,mimetypes,subprocess,threading,wave
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
HTML=r'''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="/web/styles.css"><link rel="stylesheet" href="/web/player-ui.css">
<style>html,body,#host{margin:0;width:100%;height:100%;overflow:hidden}</style><div id="host"></div>
<script type="module">
window.recordedQA={played:[],events:[],saved:[],media:[],micAttempts:0,providerAttempts:0};
const delayedRecording=__DELAYED_RECORDING__;
if(navigator.mediaDevices)navigator.mediaDevices.getUserMedia=async()=>{recordedQA.micAttempts++;throw Error('Physical capture forbidden');};
window.SpeechRecognition=window.webkitSpeechRecognition=undefined;
const NativeAudio=window.Audio;
window.Audio=function(...args){const a=new NativeAudio(...args),id=recordedQA.media.length;recordedQA.media.push(a);const play=a.play.bind(a);
 a.play=()=>{const e={id,src:a.src,muted:a.muted,volume:a.volume,active:navigator.userActivation?.isActive??null,at:performance.now()};recordedQA.played.push(e);return play().then(v=>{e.result='playing';return v;},error=>{e.result='rejected';e.error=error.name;throw error;});};
 for(const type of ['playing','ended','pause','error'])a.addEventListener(type,()=>recordedQA.events.push({id,type,src:a.currentSrc||a.src,at:performance.now(),error:a.error?.code||null}));return a;};window.Audio.prototype=NativeAudio.prototype;
const photo='data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="750"><rect width="1200" height="750" fill="#17445a"/><text x="200" y="380" fill="white" font-size="72">Reviewed visual fixture</text></svg>');
const slide=(id,kind,lines=[])=>({id,kind,title:'Reviewed '+id,topics:['Features'],lines,media:[],image_url:photo,callouts:[],checkin:{text:''},deeper:[]});
const bundle={name:'Native audio acceptance',version:1,language:'en-IN',product:{name:'Reviewed product'},voice:{provider:'sarvam',persona:{persona_name:'Guide'}},slides:[slide('hero','hero_open'),slide('proof','proof',[
 {text:'The first reviewed feature stays on screen during this recording.',audio:'/audio/first.wav',fact_ids:['F1']},
 {text:'The second reviewed feature follows after user activation expires.',audio:delayedRecording?null:'/audio/second.wav',fact_ids:['F2']}]),slide('closing','closing',[{text:'That completes these reviewed features.',audio:'/audio/closing.wav',fact_ids:['F1']}]),slide('end','hero_close')],facts:[{id:'F1',claim:'First reviewed feature'},{id:'F2',claim:'Second reviewed feature'}],ctas:[],fillers:{},intake:{q1:'What matters to you?',audio:{q1:'/audio/intake.wav'}}};
const {mountPlayer}=await import('/web/player/player.js');
window.player=mountPlayer(document.querySelector('#host'),bundle,{tts:async()=>{await new Promise(resolve=>setTimeout(resolve,6500));return '/audio/second.wav';},pitch:async()=>null,qa:async()=>{recordedQA.providerAttempts++;throw Error('Questions forbidden');},lead:async()=>({}),saveSession:async s=>recordedQA.saved.push(structuredClone(s)),beacon:s=>recordedQA.saved.push(structuredClone(s))});
window.recordedQA.ready=true;
</script>'''
def wav(seconds):
 with io.BytesIO() as out:
  with wave.open(out,'wb') as f:
   f.setnchannels(1);f.setsampwidth(2);f.setframerate(24000);f.writeframes(b'\0\0'*int(seconds*24000))
  return out.getvalue()
LONG,SHORT=wav(6.5),wav(.25)
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*_):pass
 def do_GET(self):
  p=urlsplit(self.path).path
  if p=='/':data,mime=HTML.replace('__DELAYED_RECORDING__',str(self.server.delayed_recording).lower()).encode(),'text/html'
  elif p.startswith('/audio/') and p.endswith('.wav'):data,mime=(LONG if p.endswith('/first.wav') and not self.server.delayed_recording else SHORT),'audio/wav'
  elif p.startswith('/web/'):
   target=(ROOT/p.lstrip('/')).resolve()
   if not target.is_relative_to(ROOT/'web') or not target.is_file():self.send_error(404);return
   data=subprocess.check_output(['git','show',self.server.revision+':web/player/player.js'],cwd=ROOT) if self.server.revision and p=='/web/player/player.js' else target.read_bytes()
   mime=mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
  else:self.send_error(404);return
  self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--revision');parser.add_argument('--delayed-recording',action='store_true',help='Short first clip followed by a local asynchronous recording callback after 6.5 seconds');parser.add_argument('--output',type=Path,default=ROOT/'output/playwright/mobile-recorded-audio-20260926');args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
 server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.revision=args.revision;server.delayed_recording=args.delayed_recording;threading.Thread(target=server.serve_forever,daemon=True).start();base=f'http://127.0.0.1:{server.server_port}'
 checks,records,errors,blocked=[],[],[],[]
 def check(name,value):checks.append({'name':name,'passed':bool(value)});print(('PASS ' if value else 'FAIL ')+name,flush=True)
 try:
  with sync_playwright() as p:
   browser=p.webkit.launch(headless=True)
   for profile in ['Safari','CriOS']:
    options=dict(p.devices['iPhone 13'])
    if profile=='CriOS':options['user_agent']='Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/139.0.7258.77 Mobile/15E148 Safari/604.1'
    context=browser.new_context(**options,service_workers='block')
    def route(r):
     if r.request.url.startswith(base+'/') and r.request.method=='GET':return r.continue_()
     if urlsplit(r.request.url).hostname=='fonts.googleapis.com':return r.fulfill(status=200,content_type='text/css',body='/* local system fonts */')
     blocked.append(r.request.url.split('?')[0]);r.abort()
    context.route('**/*',route);context.route_web_socket('**/*',lambda ws:(blocked.append('unexpected-websocket'),ws.close()))
    page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.goto(base+'/')
    page.get_by_role('button',name='Browse at my pace',exact=True).tap()
    # Do not poll/read/evaluate the page while autoplay permission is under test:
    # WebKit automation evaluations can themselves refresh activation.
    page.wait_for_timeout(16000)
    result=page.evaluate("()=>({ua:navigator.userAgent,played:recordedQA.played,events:recordedQA.events,saved:recordedQA.saved,micAttempts:recordedQA.micAttempts,providerAttempts:recordedQA.providerAttempts,caption:document.querySelector('.pl-cap .txt')?.textContent})")
    result['profile']=profile;records.append(result)
    first=[e for e in result['played'] if e['src'].endswith('/audio/first.wav')]
    second=[e for e in result['played'] if e['src'].endswith('/audio/second.wav')]
    closing=[e for e in result['played'] if e['src'].endswith('/audio/closing.wav')]
    check(profile+' mounted player plays its first native recorded clip',len(first)==1 and first[0].get('result')=='playing')
    check(profile+' delayed second clip plays after transient activation expires',len(second)==1 and second[0].get('result')=='playing' and second[0]['active'] is False and second[0]['at']-first[0]['at']>6000 if first else False)
    check(profile+' consecutive clips retain the same primed media owner',bool(first and second and closing) and len({e['id'] for e in first+second+closing})==1 and all(e.get('result')=='playing' for e in closing))
    check(profile+' no native playback rejection or mute-policy bypass',all(e.get('result')=='playing' and e['muted'] is False and e['volume']==1 for e in result['played']))
    check(profile+' only local recording callbacks ran without microphone or provider calls',result['micAttempts']==0 and result['providerAttempts']==0)
    page.screenshot(path=str(args.output/(profile.lower()+'-native-recorded.png')))
    stopped=page.evaluate('''()=>{player.destroy();return{playing:recordedQA.media.filter(a=>!a.paused).length,root:!!document.querySelector('.pl')};}''')
    check(profile+' player destruction leaves no recorded audio playing',stopped['playing']==0 and not stopped['root'])
    context.close()
   browser.close()
  check('no browser exceptions or unexpected network requests',not errors and not blocked)
 finally:
  server.shutdown();server.server_close()
  report={'passed':sum(c['passed'] for c in checks),'total':len(checks),'checks':checks,'records':records,'errors':errors,'blocked':blocked,'provider_calls':0,'physical_microphone':False,'physical_iphone':False,'native_audio':True,'audio_content':'Unmuted PCM16 digital-silence WAV, no autoplay override','revision':args.revision,'delayed_recording':args.delayed_recording}
  (args.output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
 print(f"Mounted WebKit recorded audio: {report['passed']}/{report['total']}",flush=True)
 return 0 if report['passed']==report['total'] else 1
if __name__=='__main__':raise SystemExit(main())

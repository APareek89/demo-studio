"""Read-only public welcome-screen deployment proof through isolated Playwright CLI."""
from pathlib import Path
import json, subprocess

root=Path('/Users/macbook/Documents/demo-studio')
out=root/'output/playwright/aws-runtime-gallery-2026-09-25'
out.mkdir(parents=True,exist_ok=True)
code='''async page => {
 const errors=[], failed=[], blocked=[];
 page.on('pageerror', e=>errors.push(String(e)));
 page.on('response', r=>{if(r.status()>=400)failed.push({url:r.url(),status:r.status()});});
 await page.route('**/*', async r=>{
   const q=r.request();
   const host=q.url().split('/')[2];
   if(q.method()!=='GET' || !['13-202-0-79.sslip.io','fonts.googleapis.com','fonts.gstatic.com'].includes(host)){blocked.push({method:q.method(),url:q.url()}); return r.abort();}
   return r.continue();
 });
 await page.routeWebSocket('**/*', ws=>ws.close());
 await page.addInitScript(()=>{
   navigator.sendBeacon=()=>false;
   if(navigator.mediaDevices)navigator.mediaDevices.getUserMedia=()=>Promise.reject(new Error('Read-only release verification'));
 });
 const results=[];
 for(const viewport of [{width:1440,height:1000},{width:390,height:844}]){
   await page.setViewportSize(viewport);
   await page.goto('https://13-202-0-79.sslip.io/?mute=1#/play/dm_29df0418',{waitUntil:'networkidle'});
   await page.locator('.pl-welcome h1').waitFor({state:'visible'});
   await page.waitForFunction(()=>Array.from(document.images).some(i=>i.complete&&i.naturalWidth>0));
   await page.evaluate(()=>document.fonts.ready);
   const layout=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,
      title:document.title,body:document.body.innerText.slice(0,1500),
      images:Array.from(document.images).filter(i=>i.offsetWidth>0).map(i=>({src:i.getAttribute('src'),width:i.naturalWidth,loaded:i.complete&&i.naturalWidth>0}))}));
   await page.screenshot({path:OUT+'/public-welcome-'+viewport.width+'.png',fullPage:true});
   results.push({viewport,layout});
 }
 const report={read_only:true,paid_calls:0,errors,failed,blocked,results};
 if(errors.length||failed.length||results.some(x=>x.layout.scrollWidth>x.viewport.width))throw Error(JSON.stringify(report));
 return report;
}'''.replace('OUT',repr(str(out)))
cmd=['bash','/Users/macbook/.codex/skills/playwright/scripts/playwright_cli.sh','-s=runtime-aws','run-code',code]
result=subprocess.run(cmd,cwd=root,text=True,capture_output=True,timeout=150)
(out/'browser-cli-final.log').write_text(result.stdout+'\n'+result.stderr)
if '### Result\n' in result.stdout:
    report=json.loads(result.stdout.split('### Result\n',1)[1].split('\n###',1)[0])
    (out/'public-browser.json').write_text(json.dumps(report,indent=2)+'\n')
print(result.stdout)
print(result.stderr)
raise SystemExit(result.returncode)

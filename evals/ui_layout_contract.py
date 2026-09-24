"""Browser geometry and workbook template; isolated fixtures, no live mutations or providers."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import json
import mimetypes
import os
import socket
import subprocess
import sys
import tempfile
import threading
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'docs/design/wp11-samples/marine.html'
REFERENCE_IMAGE = ROOT / 'data/demos/dm_cc3d8fa7/sources/src_be8af6_creta-exterior-pc__Hyundai-creta-suv-exterior-big-1120x600-side-1.jpg'


def reference_pixels():
    if REFERENCE_IMAGE.is_file():
        return REFERENCE_IMAGE.read_bytes(),'image/jpeg'
    # The source photo is deliberately not committed. Clean checkouts still
    # compare the very same native-size pixels on both sides of the contract.
    return b'<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="600"><rect width="1120" height="600" fill="#91a8b4"/><rect x="160" y="210" width="800" height="210" rx="70" fill="#254152"/><circle cx="300" cy="435" r="65" fill="#14232b"/><circle cx="820" cy="435" r="65" fill="#14232b"/></svg>','image/svg+xml'
HTML = r'''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="/web/styles.css"><link rel="stylesheet" href="/web/design-system.css"><link rel="stylesheet" href="/web/studio-ui.css"><link rel="stylesheet" href="/web/player-ui.css">
<style>body{display:block;margin:0}#fixture{height:100dvh;width:100%;display:flex;flex-direction:column;position:relative}*{animation:none!important;transition:none!important}</style><div id="fixture" class="stage-area"></div><div id="toasts"></div>
<script type="module">
window.fetch=()=>Promise.reject(new Error('Network blocked'));
const {api}=await import('/web/api.js'); const {renderSlide}=await import('/web/slide.js'); const {mountPlayer}=await import('/web/player/player.js'); const {renderAlign}=await import('/web/studio/align.js'); const {renderRehearse}=await import('/web/studio/rehearse.js');
const host=document.querySelector('#fixture'); let player, view;
const image='data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="600"><rect width="1120" height="600" fill="#b9ced8"/><rect x="160" y="210" width="800" height="210" rx="70" fill="#254152"/><circle cx="300" cy="435" r="65" fill="#14232b"/><circle cx="820" cy="435" r="65" fill="#14232b"/></svg>');
const bundle={name:'Layout fixture',language:'en-IN',product:{name:'Fixture car'},voice:{provider:'sarvam',persona:{persona_name:'Guide'}},intake:{q1:'What matters to you?'},media:{},slides:[{id:'hero',kind:'hero_open',title:'Fixture car',image_url:image,callouts:[],lines:[]}],facts:[],ctas:[],fillers:{}};
const state={demo:{id:'fixture',name:'Layout fixture',status:'ready',approvals:{},settings:{},stages:{}},cards:null,conversation:[],sessions:[],leads:[],bundle_ready:true};
api.get=async path=>path.endsWith('/bundle')?structuredClone(bundle):path.endsWith('/readiness')?{}:structuredClone(state); api.post=async()=>({}); api.patch=async()=>({});
window.settle=()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
window.show=async (mode,theme="marine")=>{window.dispatchEvent(new Event('hashchange'));player?.destroy();player=null;host.replaceChildren();const ctx={demoId:'fixture',area:host,state:structuredClone(state),subscribe(){},setRailStatus(){}};
 if(mode==='align')renderAlign(ctx); else if(mode==='rehearse')renderRehearse(ctx); else {player=mountPlayer(host,{...structuredClone(bundle),visual_theme:theme},{});window.playerUsesCinematic=!host.querySelector('.evidence-layout');host.querySelectorAll('.pl-intake').forEach(n=>n.remove());host.querySelector('.slide-stack').replaceChildren();view=renderSlide({id:'proof',kind:'proof',title:'A stable product view',image_url:image,callouts:[],lines:[]},{fit:true,theme});view.el.classList.add('on');host.querySelector('.slide-stack').append(view.el);host.querySelector('.pl-cap .txt').textContent='A short, grounded line introduces the product.';}
 await window.settle(); await window.settle();window.scrollTo(0,0);};
window.stress=async()=>{host.querySelector('.pl-cap .txt').textContent='A longer grounded answer remains readable while the same product picture stays on screen. '.repeat(5);host.querySelector('.pl-live').textContent='Listening: I would like to understand the different choices before I decide.';host.querySelector('.pl-chips').innerHTML='<button class="chip">Tell me more</button><button class="chip">Something else</button><button class="chip primary">Continue</button>';host.querySelector('.pl-timer').textContent='The tour continues after your question';host.querySelector('.pl-ctas').innerHTML='<button class="chip">View brochure</button><button class="chip primary">Request a callback</button>';host.querySelector('.pl-lead').classList.add('open');await window.settle();await window.settle();};
window.crossed=async(editable=false,pair=false,overlap=false)=>{player?.destroy();player=null;host.replaceChildren();const data={id:'cross',title:'Crossed labels',image_id:'A',image_url:image,callouts:[{id:'one',image_id:'A',placement:'overlay',text:'First reviewed label',anchor:{x:.8,y:.7},label_pos:{x:.15,y:.15},reveal_on_line:0,fact_ids:['F1']},{id:'two',image_id:pair?'B':'A',placement:'overlay',text:'Second reviewed label',anchor:{x:.2,y:.7},label_pos:{x:overlap?.16:.65,y:.15},reveal_on_line:0,fact_ids:['F2']}]};if(pair)data.media=[{image_id:'A',image_url:image,from_line:0},{image_id:'B',image_url:image,from_line:1}];window.savedBefore=JSON.stringify(data);window.slideData=data;view=renderSlide(data,{editable});host.append(view.el);await window.settle();view.layout();};
window.showFactReview=async()=>{window.dispatchEvent(new Event('hashchange'));host.replaceChildren();window.reviewCalls=[];
 const reason='Citation quote/locator was not verified against this source revision.';
 const facts=[{id:'F1',claim:'Held citation',value:'Needs review',approved:false,knowledge:{review_required:reason}},{id:'F2',claim:'Conflict',value:'Needs a separate decision',approved:false,knowledge:{review_required:reason}},{id:'F3',claim:'Manually rejected',value:'Excluded',approved:false,knowledge:{}}];
 const cards={visuals:{shots:[],images:[],segments:[],gaps:[]},facts:{facts,unknowns:[],sources:[],conflicts:[{id:'conf',status:'unresolved',fact_ids:['F2']}]},script:{segments:[]},deck:{slides:[]},faq:{entries:[],unknowns:[]},persona:{provider:'sarvam'},ctas:[]};
 const demo={...state.demo,approvals:{visuals:true}};
 api.get=async()=>({...state,demo,cards});api.patch=async(path,body)=>{if(window.reviewFailTheme)throw new Error('Demo worker is busy');reviewCalls.push({path,body});demo.settings={...demo.settings,...body.settings};demo.approvals.visuals=false;cards.visuals.visual_theme=body.settings.visual_theme;return demo;};
 api.post=async(path,body)=>{reviewCalls.push({path,body});if(body.action==='restore')facts[0].approved=true;return {changed_fact_ids:body.action==='restore'?['F1']:[],still_held:body.action==='retry'?['F1']:[],skipped_conflicts:['F2'],cards,approvals:{}}};
 renderAlign({demoId:'fixture',area:host,state:{...state,demo,cards},subscribe(){},setRailStatus(){}});await window.settle();};
window.approvedLayout=async(theme='marine',pair=false,overlap=false)=>{await show('player',theme);const data={id:'approved',kind:'proof',title:'Reviewed details',image_id:'A',image_url:image,callouts:[{id:'one',image_id:'A',placement:'overlay',text:'First reviewed feature',anchor:{x:.27,y:.73},label_pos:{x:.15,y:.15},reveal_on_line:0,fact_ids:['F1']},{id:'two',image_id:pair?'B':'A',placement:'overlay',text:'Second reviewed feature',anchor:{x:.63,y:.44},label_pos:{x:overlap?.16:.65,y:.15},reveal_on_line:1,fact_ids:['F2']}]};if(pair)data.media=[{image_id:'A',image_url:image,from_line:0},{image_id:'B',image_url:image,from_line:1}];window.approvedSaved=JSON.stringify(data);window.approvedData=data;view=renderSlide(data,{fit:true,theme});view.el.classList.add('on');document.querySelector('.slide-stack').replaceChildren(view.el);await settle();view.setRevealed(1);await settle();view.layout();};
window.visible=n=>{if(!n)return false;const r=n.getBoundingClientRect();if(!r.width||!r.height)return false;for(let p=n;p&&p!==document.body;p=p.parentElement){const c=getComputedStyle(p);if(c.display==='none'||c.visibility==='hidden'||Number(c.opacity)===0)return false;}return true;};
window.labelGeometry=()=>{const slide=document.querySelector('.cinematic'),stage=slide.getBoundingClientRect(),heading=slide.querySelector('.slide-heading').getBoundingClientRect();const overlap=(a,b)=>a.left<b.right-1&&a.right>b.left+1&&a.top<b.bottom-1&&a.bottom>b.top+1;
 const chips=[...slide.querySelectorAll('.callout')].filter(visible),details=[...slide.querySelectorAll('.slide-panel .item')].filter(visible),labels=[...chips,...details];
 const bounded=labels.every(n=>{const r=n.getBoundingClientRect();return r.left>=stage.left-1&&r.right<=stage.right+1&&r.top>=stage.top-1&&r.bottom<=stage.bottom+1;});
 const clear=labels.every((n,i)=>{const r=n.getBoundingClientRect();return !overlap(r,heading)&&!labels.slice(i+1).some(other=>overlap(r,other.getBoundingClientRect()));});
 const represented=approvedData.callouts.every(c=>labels.some(n=>n.dataset.id===c.id&&n.textContent.includes(c.text)));
 const ownership=approvedData.callouts.every(c=>{const dot=slide.querySelector(`.dot[data-id="${c.id}"]`),pic=dot?.closest('.slide-pic');if(!pic||pic.dataset.imageId!==c.image_id)return false;const p=pic.getBoundingClientRect(),d=dot.getBoundingClientRect();return Math.abs((d.left+d.width/2-p.left)/p.width-c.anchor.x)<.005&&Math.abs((d.top+d.height/2-p.top)/p.height-c.anchor.y)<.005;});
 return{bounded,clear,represented,ownership,overlayCount:chips.length,detailCount:details.length};};
window.densePictures=async()=>{await approvedLayout('marine',true);const data=structuredClone(approvedData);data.callouts=['A','B'].flatMap((id,p)=>[[.2695,.7245],[.632,.4105],[.8785,.585]].map(([x,y],i)=>({id:`dense-${p}-${i}`,image_id:id,placement:'overlay',part:['Wheel','Mirror','Light'][i],text:`Reviewed picture ${id} detail ${i+1}`,anchor:{x,y},label_pos:{x:.1+i*.3,y:.15},reveal_on_line:0,fact_ids:['F1']})));window.approvedData=data;window.approvedSaved=JSON.stringify(data);view=renderSlide(data,{fit:true,theme:'marine'});view.el.classList.add('on');host.querySelector('.slide-stack').replaceChildren(view.el);await settle();view.setRevealed(99);await settle();view.layout();};
window.anchorlessPicture=async()=>{await approvedLayout('marine');const data=structuredClone(approvedData);data.media=[{image_id:'A',image_url:image,from_line:0,proxy:true,proxy_reason:'This source illustrates the view.'}];data.callouts=[{id:'unknown',image_id:'A',placement:'overlay',label_pos:{x:.4,y:.2},anchor:null,text:'Reviewed detail with no trusted picture anchor',reveal_on_line:0,fact_ids:['F1']}];window.approvedData=data;window.approvedSaved=JSON.stringify(data);view=renderSlide(data,{fit:true,theme:'marine'});view.el.classList.add('on');host.querySelector('.slide-stack').replaceChildren(view.el);await settle();view.setRevealed(0);await settle();view.layout();};
window.showSample=async({scene,size,built})=>{window.dispatchEvent(new Event('hashchange'));player?.destroy();player=null;host.replaceChildren();host.style.width=size.width+'px';host.style.height=size.height+'px';host.style.margin='0 auto';
 const sample=built||{...structuredClone(bundle),name:'Hyundai CRETA',product:{name:'CRETA'},voice:{provider:'sarvam',persona:{persona_name:'Priya'}},visual_theme:'marine',slides:[scene]};
 player=mountPlayer(host,sample,{});window.initialUsesSample=!!host.querySelector('.sample-layout');host.querySelectorAll('.pl-intake').forEach(n=>n.remove());const data=scene||sample.slides.find(s=>s.kind==='proof');window.approvedData=data;window.approvedSaved=JSON.stringify(data);
 view=renderSlide(data,{fit:true,theme:sample.visual_theme||'marine',position:{index:3,total:7}});view.el.classList.add('on');host.querySelector('.slide-stack').replaceChildren(view.el);host.querySelector('.pl-cap .txt').textContent='From the side, you can see how the wheel design, mirrors and front lights sit together.';
 host.querySelector('.pl-ctas').innerHTML='<button class="chip">View brochure ↗</button><button class="chip">Ask for a callback</button><button class="chip primary">Continue →</button>';
 await settle();await settle();await Promise.all([...view.el.querySelectorAll('img')].map(i=>i.complete?Promise.resolve():new Promise(r=>i.addEventListener('load',r,{once:true}))));view.setRevealed(99);if(scene)view.highlight('sample-0');await settle();view.layout();await settle();};
window.ready=true;
</script>'''

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/':
            data, mime = HTML.encode(), 'text/html'
        elif path == '/reference/marine.html':
            data, mime = REFERENCE.read_bytes(), 'text/html'
        elif path == '/' + str(REFERENCE_IMAGE.relative_to(ROOT)) or path == '/reference-car.jpg' or (path.startswith('/media/dm_') and path.endswith('/sources/reference.jpg')):
            data, mime = reference_pixels()
        elif path.startswith('/web/'):
            target = (ROOT / path.lstrip('/')).resolve()
            if not target.is_relative_to(ROOT / 'web') or not target.is_file():
                self.send_error(404); return
            data, mime = target.read_bytes(), mimetypes.guess_type(target.name)[0]
        else:
            self.send_error(404); return
        self.send_response(200)
        self.send_header('Content-Type', mime or 'application/octet-stream')
        self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'none'; connect-src 'none'; font-src 'self'")
        self.end_headers(); self.wfile.write(data)


def build_mock_fixture(output):
    """Run the real Bundle assembler against a new, fully isolated recorded fixture."""
    assert not output.resolve().is_relative_to(ROOT)
    attempts=[]
    def blocked(*args, **kwargs):
        attempts.append(True)
        raise AssertionError('Outbound connection blocked in mock fixture build')
    socket.create_connection=socket.socket.connect=socket.socket.connect_ex=blocked
    with tempfile.TemporaryDirectory(prefix='sample-parity-build-') as tmp:
        os.environ.update(MOCK_LLM='1',CLOUD_SYNC='0',STORAGE_BACKEND='local',DEMO_STUDIO_DATA=str(Path(tmp)/'demos'),DEMO_STUDIO_GRAPH_DB=str(Path(tmp)/'graph.sqlite'))
        sys.path[:0]=[str(ROOT),str(ROOT/'evals')]
        from server import store
        from server.agents import bundle
        from minimum_narration_contract import rich_fixture
        did=store.new_demo('Sample parity isolated build')['id']
        fixture=rich_fixture(did,recorded=True)
        image=store.path(did,'sources/reference.jpg');image.parent.mkdir(parents=True,exist_ok=True);image.write_bytes(reference_pixels()[0])
        fixture['understanding']['images']=[{'id':'im01','source_id':'fixture-reference','path':'sources/reference.jpg','angle':'side','quality':5,'full_product':True,'description':'Retained reference asset used only by this isolated layout fixture','parts':[]}]
        store.update(did,lambda demo:demo['sources'].append({'id':'fixture-reference','kind':'image','path':'sources/reference.jpg','name':'reference.jpg','role':'product','use_in_demo':True}))
        fixture['deck']['slides'][0].update(image_id='im01',media=[{'image_id':'im01','from_line':0}],title='A newly built reviewed view')
        store.write_json(did,'understanding.json',fixture['understanding']);store.write_json(did,'deck.json',fixture['deck'])
        built=bundle.build(did,lambda _:None)
        assert built['runtime']['narration_minimum']['measured'] and built['runtime']['narration_minimum']['sufficient']
        output.write_text(json.dumps(built))
    assert not attempts
    print('MOCK PARITY BUILD: real Bundle, measured WAV minimum, isolated storage, OUTBOUND_ATTEMPTS 0',flush=True)


SAMPLE_METRICS = r'''() => {
 const root=document.querySelector('#customer'),stage=root.querySelector('.stage'),header=root.querySelector('.player-header'),title=root.querySelector('.visual-heading h2'),picture=root.querySelector('.slide-scene>img'),dock=root.querySelector('.dock'),footer=root.querySelector('.action-bar');
 const rect=(e,origin=stage)=>{const r=e.getBoundingClientRect(),o=origin.getBoundingClientRect();return {x:r.x-o.x,y:r.y-o.y,width:r.width,height:r.height};};
 const style=e=>{const s=getComputedStyle(e);return {background:s.backgroundColor,gradient:s.backgroundImage,fontSize:s.fontSize,fontFamily:s.fontFamily,color:s.color};};
 const img=picture.getBoundingClientRect();
 return {size:{width:root.clientWidth,height:root.clientHeight},header:rect(header,root),stage:rect(stage,root),title:rect(title),picture:rect(picture),dock:rect(dock,root),footer:rect(footer,root),headerStyle:style(header),stageStyle:style(stage),titleStyle:style(title),dockStyle:style(dock),reply:rect(root.querySelector('.composer'),root),composerLabel:rect(root.querySelector('.composer-label'),root),composerHint:rect(root.querySelector('.composer-foot'),root),captionStyle:style(root.querySelector('.caption')),card:rect(root.querySelector('.slide-feature.active')),cardStyle:style(root.querySelector('.slide-feature.active')),cardTitleStyle:style(root.querySelector('.slide-feature.active strong')),image:picture.src,
 scene:{id:'sample-reference',kind:'proof',title:title.textContent,image_id:'A',image_url:'/reference-car.jpg',callouts:[...root.querySelectorAll('.slide-feature')].map((c,i)=>{const r=c.getBoundingClientRect(),[x,y]=c.dataset.anchor.split(',').map(Number);return {id:'sample-'+i,image_id:'A',placement:'overlay',part:c.querySelector('strong').textContent,text:c.querySelector('small').textContent,anchor:{x,y},label_pos:{x:(r.x-img.x)/img.width,y:(r.y-img.y)/img.height},reveal_on_line:0,fact_ids:['F'+(i+1)]};}),lines:[]}};
}'''


ACTUAL_METRICS = r'''() => {
 const root=document.querySelector('.pl'),stage=root.querySelector('.slide-stack'),header=root.querySelector('.pl-top'),title=root.querySelector('.slide-title'),picture=root.querySelector('.slide-pic img'),dock=root.querySelector('.pl-dock'),footer=root.querySelector('.pl-action-bar');
 const rect=(e,origin=stage)=>{const r=e.getBoundingClientRect(),o=origin.getBoundingClientRect();return {x:r.x-o.x,y:r.y-o.y,width:r.width,height:r.height};};
 const style=e=>{const s=getComputedStyle(e);return {background:s.backgroundColor,gradient:s.backgroundImage,fontSize:s.fontSize,fontFamily:s.fontFamily,color:s.color};};
 return {size:{width:root.clientWidth,height:root.clientHeight},header:rect(header,root),stage:rect(stage,root),title:rect(title),picture:rect(picture),dock:rect(dock,root),footer:rect(footer,root),headerStyle:style(header),stageStyle:style(root.querySelector('.sample-layout')),titleStyle:style(title),dockStyle:style(dock),reply:rect(root.querySelector('.pl-reply'),root),composerLabel:rect(root.querySelector('.pl-composer-label'),root),composerHint:rect(root.querySelector('.pl-mic-row'),root),captionStyle:style(root.querySelector('.pl-cap .txt')),card:rect(root.querySelector('.callout')),cardStyle:style(root.querySelector('.callout')),cardTitleStyle:style(root.querySelector('.callout strong')),image:picture.src};
}'''


def run_sample_parity(browser,page,base,screenshots,check,live_url):
    # The earlier sample retains the reviewed image/anchors and compact control
    # dimensions. The24September workbook supersedes its dark colors and title.
    print('PARITY ASSET: '+('retained source photograph, read-only' if REFERENCE_IMAGE.is_file() else 'synthetic 1120x600 clean-checkout fallback; identical pixels on both sides'),flush=True)
    reference=page.context.new_page()
    reference.goto(base+'/reference/marine.html');reference.wait_for_function("document.querySelector('#customer .slide-scene img')?.complete")
    for width in (1440,850,390):
        viewport={'width':width,'height':1100}
        reference.set_viewport_size(viewport);page.set_viewport_size(viewport)
        reference.evaluate('() => new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
        expected=reference.evaluate(SAMPLE_METRICS)
        page.evaluate('showSample',{'scene':expected['scene'],'size':expected['size']})
        actual=page.evaluate(ACTUAL_METRICS)
        (screenshots/f'parity-metrics-{width}.json').write_text(json.dumps({'reference':expected,'actual':actual},indent=2))
        reference.locator('#customer').screenshot(path=str(screenshots/f'reference-marine-{width}.png'))
        page.locator('.pl').screenshot(path=str(screenshots/f'actual-marine-{width}.png'))
        near=lambda a,b,tolerance=2:abs(a-b)<=tolerance
        check(f'{width}px reference and app use the same image pixels and native ratio',page.evaluate("document.querySelector('.slide-pic img').naturalWidth===1120&&document.querySelector('.slide-pic img').naturalHeight===600") and near(actual['picture']['width']/actual['picture']['height'],1120/600,.01))
        check(f'{width}px compact header and slide retain75percent space with portrait guidance',near(actual['header']['height'],expected['header']['height']) and near(actual['stage']['height']+(32 if width<720 else 0),expected['stage']['height']))
        check(f'{width}px workbook header and slide are white without a dark gradient',actual['headerStyle']['background']==actual['stageStyle']['background']=='rgb(255, 255, 255)' and actual['stageStyle']['gradient']=='none')
        check(f'{width}px workbook heading is half-sized and close to the header',float(actual['titleStyle']['fontSize'][:-2])<=float(expected['titleStyle']['fontSize'][:-2])/2 and actual['title']['y']<expected['title']['y'])
        check(f'{width}px composer, label and hint heights match the approved sample',all(near(actual[k]['height'],expected[k]['height'],1) for k in ('reply','composerLabel','composerHint')))
        check(f'{width}px readable caption type and compact feature card sizes are preserved',actual['captionStyle']['fontSize']==expected['captionStyle']['fontSize'] and actual['captionStyle']['fontFamily']==expected['captionStyle']['fontFamily'] and near(actual['card']['width'],expected['card']['width'],1) and actual['cardStyle']['background'] in ('rgb(255, 255, 255)','rgba(255, 255, 255, 0.96)') and actual['cardStyle']['color']=='rgb(16, 45, 66)' and actual['cardTitleStyle']['fontSize']==expected['cardTitleStyle']['fontSize'])
        check(f'{width}px native-ratio picture is centered below the smaller heading',near(actual['picture']['x']+actual['picture']['width']/2,actual['size']['width']/2) and actual['picture']['width']>actual['size']['width']*.45 and actual['picture']['y']>=actual['title']['y']+actual['title']['height'])
        check(f'{width}px white conversation and CTA footer follow the sample order',actual['dockStyle']['background']==expected['dockStyle']['background']=='rgb(255, 255, 255)' and actual['dock']['y']>=actual['stage']['y']+actual['stage']['height']-1 and actual['footer']['y']>=actual['dock']['y']+actual['dock']['height']-1 and near(actual['footer']['height'],expected['footer']['height']))
        check(f'{width}px sample feature words and unchanged trusted anchors remain visible without overlaps',page.evaluate("(()=>{const g=labelGeometry();return g.represented&&g.bounded&&g.clear&&g.ownership&&JSON.stringify(approvedData)===approvedSaved})()"))
        check(f'{width}px sample anchors are small unnumbered dots, not badges',page.locator('.sample-layout .dot').evaluate_all("nodes=>nodes.length===3&&nodes.every(n=>{const r=n.getBoundingClientRect();return r.width<=10&&r.height<=10&&(!n.querySelector('.num')||getComputedStyle(n.querySelector('.num')).display==='none')})"))
        before=page.evaluate(ACTUAL_METRICS)
        page.evaluate('stress()')
        after=page.evaluate(ACTUAL_METRICS)
        check(f'{width}px answer, listening and callback keep sample frame dimensions stable',all(before[k]==after[k] for k in ('header','stage','picture','dock','footer')))
    reference.close()
    with tempfile.TemporaryDirectory(prefix='sample-parity-bundle-') as tmp:
        output=Path(tmp)/'bundle.json'
        subprocess.run([sys.executable,str(Path(__file__).resolve()),'--build-mock-fixture',str(output)],cwd=ROOT,check=True)
        built=json.loads(output.read_text())
        page.set_viewport_size({'width':1440,'height':1100})
        page.evaluate('showSample',{'built':built,'size':{'width':1374,'height':878}})
        check('a newly built isolated mock bundle uses the same sample renderer and recorded publication gate',page.evaluate("initialUsesSample&&!!document.querySelector('.sample-player .sample-layout')") and built['runtime']['narration_minimum']['measured'] and built['visual_theme']=='marine')
        page.locator('.pl').screenshot(path=str(screenshots/'new-built-mock-sample.png'))
        page.evaluate("titles=>{const n=document.querySelector('.pl-progress');n.replaceChildren(...titles.map(t=>{const b=document.createElement('button');b.className='pp';b.textContent=t;return b}));n.scrollLeft=0;}",[slide['title'] for slide in built['slides']])
        check('long reviewed routes keep the first navigation stop reachable',page.evaluate("(()=>{const n=document.querySelector('.pl-progress'),r=n.getBoundingClientRect(),f=n.firstElementChild.getBoundingClientRect();return f.left>=r.left-1&&f.right<=r.right+1})()"))
        page.evaluate("document.querySelector('.pl-progress').lastElementChild.scrollIntoView({block:'nearest',inline:'end'})")
        check('long reviewed routes keep the last navigation stop reachable',page.evaluate("(()=>{const n=document.querySelector('.pl-progress'),r=n.getBoundingClientRect(),f=n.lastElementChild.getBoundingClientRect();return f.left>=r.left-1&&f.right<=r.right+1})()"))
    for width in (1440,390):
        page.set_viewport_size({'width':width,'height':1100});page.evaluate("document.querySelector('#fixture').style.cssText='height:100dvh;width:100%;margin:0'")
        page.evaluate('densePictures()')
        check(f'{width}px two pictures keep all six reviewed labels and their original anchor owners',page.evaluate("document.querySelectorAll('.sample-layout .dot').length===6&&labelGeometry().represented&&labelGeometry().ownership&&JSON.stringify(approvedData)===approvedSaved"))
        check(f'{width}px six-label picture layout has no overlapping text boxes',page.evaluate('labelGeometry().clear'))
        page.locator('.pl').screenshot(path=str(screenshots/f'six-labels-{width}.png'))
        page.evaluate('anchorlessPicture()')
        check(f'{width}px missing anchor remains a visible on-slide detail without a guessed marker',page.evaluate("document.querySelectorAll('.sample-layout .dot,.sample-layout .leaders line').length===0&&labelGeometry().represented&&labelGeometry().bounded&&JSON.stringify(approvedData)===approvedSaved"))
        check(f'{width}px proxy keeps its illustration label',page.locator('.slide-proxy-badge').is_visible())
    if live_url:
        parsed=urlsplit(live_url)
        assert parsed.scheme=='http' and parsed.hostname in ('127.0.0.1','localhost') and parsed.port!=8896
        rejected=[];live_errors=[]
        context=browser.new_context(viewport={'width':1440,'height':1100},reduced_motion='reduce')
        def live_guard(route):
            if route.request.url.startswith(live_url.rstrip('/')+'/') and route.request.method=='GET':
                route.continue_()
            elif route.request.url.startswith('https://fonts.googleapis.com/') and route.request.method=='GET':
                # Both sides use the system font fallback; never fetch an external font.
                route.fulfill(status=200,content_type='text/css',body='/* Offline parity font fallback. */')
            else:
                rejected.append(route.request.url);route.abort()
        context.route('**/*',live_guard)
        context.add_init_script("window.WebSocket=class{constructor(){throw new Error('Live capture disabled for read-only layout check')}};navigator.sendBeacon=()=>false;")
        live=context.new_page();live.on('pageerror',lambda e:live_errors.append(str(e)))
        live.goto(live_url.rstrip('/')+'/?mute=1#/play/dm_cc3d8fa7');live.wait_for_selector('.pl')
        proof=live.evaluate("async()=>{const b=await(await fetch('/api/demos/dm_cc3d8fa7/bundle')).json(),s=b.slides.find(s=>s.kind==='proof'&&s.image_url);document.querySelectorAll('.pl-intake').forEach(n=>n.remove());const {renderSlide}=await import('/web/slide.js');const v=renderSlide(s,{fit:true,theme:b.visual_theme||'marine'});v.el.classList.add('on');document.querySelector('.slide-stack').replaceChildren(v.el);v.setRevealed(99);await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));return {id:s.id,callouts:s.callouts?.length||0};}")
        check('existing app on the requested local port renders its unchanged published bundle with the sample design',bool(proof['id']) and live.locator('.sample-player .sample-layout').count()==1)
        if rejected or live_errors:
            print('LIVE READONLY DIAGNOSTICS',json.dumps({'rejected':rejected,'errors':live_errors}),flush=True)
        check('live app render is read-only with no customer turn, socket, provider or mutation request',not rejected and not live_errors)
        live.locator('.pl').screenshot(path=str(screenshots/'live-app-readonly-sample.png'))
        context.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live-url', help='Optional existing local app URL for a GET-only render check.')
    parser.add_argument('--build-mock-fixture', help=argparse.SUPPRESS)
    parser.add_argument('--screenshots', help='Optional artifact folder outside the repository; otherwise temporary screenshots are removed.')
    args=parser.parse_args()
    if args.build_mock_fixture:
        build_mock_fixture(Path(args.build_mock_fixture)); return
    if args.screenshots:
        assert not Path(args.screenshots).resolve().is_relative_to(ROOT), 'Keep test artifacts outside the repository and protected outputs'
    results, errors, rejected = [], [], []
    def check(name, ok):
        assert ok, name
        results.append(name)
        print('PASS', name, flush=True)
    server=ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}'
    try:
        with tempfile.TemporaryDirectory(prefix='demo-ui-layout-') as tmp, sync_playwright() as pw:
            os.environ.update(MOCK_LLM='1',CLOUD_SYNC='0',STORAGE_BACKEND='local',DEMO_STUDIO_DATA=tmp+'/demos',DEMO_STUDIO_GRAPH_DB=tmp+'/graph.sqlite')
            sys.path.insert(0,str(ROOT))
            from server.crawl import _render_executable
            screenshots=Path(args.screenshots or tmp)
            screenshots.mkdir(parents=True,exist_ok=True)
            browser=pw.chromium.launch(executable_path=_render_executable(pw.chromium),chromium_sandbox=True,headless=True,args=['--mute-audio','--disable-background-networking'])
            context=browser.new_context(viewport={'width':1440,'height':1000}, reduced_motion='reduce')
            def guard(route):
                if route.request.url.startswith(base+'/') and route.request.method=='GET':route.continue_()
                else: rejected.append(route.request.url);route.abort()
            context.route('**/*',guard)
            page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(base+'/?mute=1');page.wait_for_function('window.ready')
            for width in (1440, 850, 390):
                page.set_viewport_size({'width':width,'height':1000})
                page.evaluate("show('player')")
                before=page.evaluate("Object.fromEntries(['.slide-stack','.slide-pic','.pl-dock','.pl-action-bar'].map(s=>{const r=document.querySelector(s).getBoundingClientRect();return[s,[r.x,r.y,r.width,r.height]]}))")
                check(f'{width}px dock is white',page.locator('.pl-dock').evaluate("el=>getComputedStyle(el).backgroundColor==='rgb(255, 255, 255)'"))
                check(f'{width}px stage begins directly below header',page.evaluate("Math.abs(document.querySelector('.pl-top').getBoundingClientRect().bottom-document.querySelector('.pl-stage').getBoundingClientRect().top)<1"))
                check(f'{width}px slide spans the full player width without a side rail',page.evaluate("(()=>{const s=document.querySelector('.slide-stack').getBoundingClientRect(),p=document.querySelector('.pl').getBoundingClientRect();return playerUsesCinematic&&!document.querySelector('.evidence-layout')&&Math.abs(s.left-p.left)<1&&Math.abs(s.width-p.width)<1})()"))
                check(f'{width}px slide plus portrait guidance occupies75percent of the player',page.evaluate("(()=>{const p=document.querySelector('.pl'),s=document.querySelector('.slide-stack');return Math.abs((s.getBoundingClientRect().height+(p.classList.contains('portrait-player')?32:0))/p.getBoundingClientRect().height-.75)<.005})()"))
                check(f'{width}px top bar and slide are white and borderless',page.evaluate("['.pl-top','.cinematic'].every(s=>{const c=getComputedStyle(document.querySelector(s));return c.backgroundColor==='rgb(255, 255, 255)'&&c.backgroundImage==='none'&&c.borderBottomWidth==='0px'})"))
                page.evaluate('stress()')
                after=page.evaluate("Object.fromEntries(['.slide-stack','.slide-pic','.pl-dock','.pl-action-bar'].map(s=>{const r=document.querySelector(s).getBoundingClientRect();return[s,[r.x,r.y,r.width,r.height]]}))")
                check(f'{width}px CTA, contact, long answer and capture leave picture and dock fixed', before==after)
                check(f'{width}px caption remains scrollable',page.locator('.pl-cap').evaluate("el=>['auto','scroll'].includes(getComputedStyle(el).overflowY)&&el.clientHeight>0"))
                check(f'{width}px microphone stays inside the visible dock',page.evaluate("document.querySelector('.pl-controls .mic').getBoundingClientRect().bottom<=document.querySelector('.pl-dock').getBoundingClientRect().bottom-8"))
                check(f'{width}px contact form does not cover the conversation dock',page.evaluate("document.querySelector('.pl-lead').getBoundingClientRect().bottom<=document.querySelector('.pl-dock').getBoundingClientRect().top-8"))
                page.screenshot(path=str(screenshots/f'player-{width}.png'))
                page.evaluate("document.querySelector('.pl').classList.add('film-on');document.querySelector('video').setAttribute('width','854');document.querySelector('video').setAttribute('height','480')")
                page.evaluate('settle()')
                check(f'{width}px opening film hides normal header/stage/drawer',page.evaluate("['.pl-top','.pl-stage','.pl-drawer'].every(s=>getComputedStyle(document.querySelector(s)).display==='none')"))
                check(f'{width}px film Skip remains below video',page.evaluate("document.querySelector('.pl-film-skip').getBoundingClientRect().top-document.querySelector('video').getBoundingClientRect().bottom>=15"))
                page.evaluate("show('align')")
                box=page.locator('.dock .box');box.locator('textarea').fill('Please review this source.')
                page.locator('input[type=file]').set_input_files({'name':'a-very-long-source-filename-for-layout-validation.pdf','mimeType':'application/pdf','buffer':b'fixture'})
                check(f'{width}px Align composer and controls remain within panel',page.evaluate("(()=>{const p=document.querySelector('.dock').getBoundingClientRect();return [...document.querySelectorAll('.dock .box,.dock textarea,.dock button,.dock .attach>span')].every(n=>{const r=n.getBoundingClientRect();return r.left>=p.left&&r.right<=p.right+1})})()"))
                check(f'{width}px Attach and Send share one row',page.evaluate("Math.abs(document.querySelector('.dock .box>.btn.ghost').getBoundingClientRect().top-document.querySelector('.dock .box>.btn.primary').getBoundingClientRect().top)<1"))
                page.screenshot(path=str(screenshots/f'align-{width}.png'))
                page.evaluate("show('rehearse')")
                check(f'{width}px Rehearse has one feedback conversation without an oversized header',page.locator('.rehearse-page-head,.rpanel').count()==0 and page.locator('.rehearse-feedback').count()==1)
                check(f'{width}px Rehearse player and feedback fit the available viewport',page.evaluate("[...document.querySelectorAll('.rehearse-workspace>.player-host,.rehearse-feedback')].every(n=>{const r=n.getBoundingClientRect();return r.width>0&&r.height>0&&r.left>=0&&r.right<=innerWidth+1&&r.top>=0&&r.bottom<=innerHeight+1})"))
                page.screenshot(path=str(screenshots/f'rehearse-{width}.png'))
            page.set_viewport_size({'width':1440,'height':1000});page.evaluate('crossed()')
            check('crossed leaders use the existing rail',page.locator('.slide-panel .rail-fallback').count()==1 and page.locator('line.rail-only').count()==1)
            check('collision fallback preserves reviewed positions and anchors',page.evaluate('JSON.stringify(slideData)===savedBefore'))
            page.evaluate('crossed(false,false,true)')
            check('overlapping label boxes use the existing rail',page.locator('.callout.rail-only').count()==1)
            page.evaluate('crossed(true)')
            check('editing retains draggable labels while hiding crossed leaders',page.locator('.callout.rail-only').count()==0 and page.locator('line.rail-only').count()==1)
            page.evaluate('crossed(false,true)')
            check('separate picture coordinates do not cause a false cross',page.locator('line.rail-only').count()==0)
            page.evaluate('showFactReview()')
            check('bulk review counts only eligible citation-held facts', '1 citation-held fact can be reviewed together.' in page.locator('.fact-validation-review').inner_text())
            page.get_by_role('button',name='Retry validation',exact=True).click()
            check('retry sends the bounded-review action',page.evaluate("reviewCalls[0].path==='/api/demos/fixture/align/facts/review-held'&&reviewCalls[0].body.action==='retry'"))
            check('retry reports unchanged held facts and preserved conflicts','0 verified and restored · 1 still held · 1 conflicts preserved.' in page.locator('.fact-validation-review').inner_text())
            page.get_by_role('button',name='Restore all flagged facts',exact=True).click()
            check('restore is explicit owner approval and sends restore action',page.evaluate("reviewCalls[1].body.action==='restore'") and 'restored by your approval' in page.locator('.fact-validation-review').inner_text())
            check('returned conflict and manual exclusions remain visibly excluded',page.locator('[data-card=facts] tr.removed').count()==2 and page.get_by_role('button',name='Restore all flagged facts',exact=True).is_disabled())
            for width in (1440, 850, 390):
                page.set_viewport_size({'width':width,'height':1000})
                for theme in ('marine','sage','graphite'):
                    page.evaluate('theme=>approvedLayout(theme)',theme)
                    check(f'{width}px {theme} is applied from the bundle',page.locator('.pl').get_attribute('data-visual-theme')==theme)
                    check(f'{width}px {theme} keeps small trusted anchors on the picture',page.evaluate("document.querySelectorAll('.cinematic .dot:not(.hidden)').length===2&&labelGeometry().ownership"))
                    check(f'{width}px {theme} shows feature text on the slide without label collisions',page.evaluate("(()=>{const g=labelGeometry();return g.represented&&g.bounded&&g.clear})()"))
                    check(f'{width}px {theme} uses overlay labels when the slide has room',page.evaluate("document.querySelector('.cinematic').clientWidth<700||labelGeometry().overlayCount>0"))
                    check(f'{width}px {theme} visible connectors start at label edges, outside the text',page.evaluate("(()=>{if(document.querySelector('.cinematic').clientWidth<700)return true;const chips=[...document.querySelectorAll('.cinematic .callout')].filter(visible);return chips.length>0&&chips.every(chip=>{const pic=chip.closest('.slide-pic'),i=[...pic.querySelectorAll('.callout')].indexOf(chip),line=pic.querySelectorAll('.leaders line')[i];if(!line||line.classList.contains('rail-only'))return false;const x=Number(line.getAttribute('x1'))/100*pic.clientWidth,y=Number(line.getAttribute('y1'))/100*pic.clientHeight,l=chip.offsetLeft,t=chip.offsetTop,r=l+chip.offsetWidth,b=t+chip.offsetHeight;return x>=l-1&&x<=r+1&&y>=t-1&&y<=b+1&&Math.min(Math.abs(x-l),Math.abs(x-r),Math.abs(y-t),Math.abs(y-b))<1.5})})()"))
                    check(f'{width}px {theme} keeps reviewed image ratio and saved coordinates',page.evaluate("(()=>{const i=document.querySelector('.cinematic img'),p=i.getBoundingClientRect();return Math.abs(p.width/p.height-i.naturalWidth/i.naturalHeight)<.015&&JSON.stringify(approvedData)===approvedSaved})()"))
                    check(f'{width}px {theme} hides raw source IDs from customer labels',page.locator('.cinematic .slide-panel .cite').evaluate_all("nodes=>nodes.every(n=>getComputedStyle(n).display==='none')"))
                    check(f'{width}px {theme} has no evidence rail or off-slide details',page.evaluate("!document.querySelector('.evidence-layout,.evidence-heading')&&labelGeometry().bounded"))
                    page.screenshot(path=str(screenshots/f'approved-{theme}-{width}.png'))
                page.evaluate("approvedLayout('marine',true)")
                check(f'{width}px two pictures retain separate anchors and native ratios',page.evaluate("(()=>{const pics=[...document.querySelectorAll('.cinematic .slide-pic')];return pics.length===2&&labelGeometry().ownership&&pics.every(p=>{const i=p.querySelector('img'),r=p.getBoundingClientRect();return p.querySelectorAll('.dot').length===1&&Math.abs(r.width/r.height-i.naturalWidth/i.naturalHeight)<.015})})()"))
                check(f'{width}px two-picture feature text remains visible and separate',page.evaluate("(()=>{const g=labelGeometry();return g.represented&&g.bounded&&g.clear&&JSON.stringify(approvedData)===approvedSaved})()"))
            page.set_viewport_size({'width':1440,'height':1000});page.evaluate("approvedLayout('marine',false,true)")
            check('colliding reviewed label positions produce readable on-slide text without changing anchors',page.evaluate("(()=>{const g=labelGeometry();return g.represented&&g.bounded&&g.clear&&g.ownership&&JSON.stringify(approvedData)===approvedSaved})()"))
            page.set_viewport_size({'width':390,'height':640});page.evaluate("approvedLayout('marine')")
            check('short phone viewport keeps a full-width slide while reserving readable controls',page.evaluate("(()=>{const s=document.querySelector('.slide-stack').getBoundingClientRect(),p=document.querySelector('.pl').getBoundingClientRect();return s.height>0&&s.height<=p.height*.75+1&&Math.abs(s.width-p.width)<1&&p.bottom<=innerHeight+1})()"))
            check('short phone keeps its feature labels on the slide without overlaps',page.evaluate("(()=>{const g=labelGeometry();return g.represented&&g.bounded&&g.clear&&g.ownership})()"))
            page.set_viewport_size({'width':390,'height':400});page.evaluate("approvedLayout('marine')");page.evaluate('stress()')
            check('very short viewport reserves non-overlapping header, slide, CTA and dock regions',page.evaluate("(()=>{const r=s=>document.querySelector(s).getBoundingClientRect(),p=r('.pl'),h=r('.pl-top'),s=r('.slide-stack'),c=r('.pl-action-bar'),d=r('.pl-dock');return s.height>0&&s.height<=p.height*.75+1&&h.bottom<=s.top+1&&s.bottom<=d.top+1&&d.bottom<=c.top+1&&c.bottom<=p.bottom+1&&d.height>0})()"))
            check('very short viewport keeps microphone and typed reply visible while feedback scrolls',page.evaluate("(()=>{const d=document.querySelector('.pl-dock').getBoundingClientRect();return ['.pl-controls .mic','.pl-reply input'].every(s=>{const r=document.querySelector(s).getBoundingClientRect();return r.top>=d.top&&r.bottom<=d.bottom&&r.left>=d.left&&r.right<=d.right})&&['auto','scroll'].includes(getComputedStyle(document.querySelector('.pl-feedback')).overflowY)})()"))
            check('very short phone keeps one readable caption line and reply feedback',page.evaluate("(()=>{const c=document.querySelector('.pl-cap'),t=getComputedStyle(document.querySelector('.pl-cap .txt'));return c.clientHeight>=parseFloat(t.lineHeight)&&document.querySelector('.pl-feedback').clientHeight>=22})()"))
            page.screenshot(path=str(screenshots/'player-short-390x400.png'))
            for height in (640,720):
                page.set_viewport_size({'width':1440,'height':height});page.evaluate("approvedLayout('marine')");page.evaluate('stress()')
                check(f'1440x{height} keeps reply chips reachable in a visible scrollable feedback area',page.evaluate("(()=>{const f=document.querySelector('.pl-feedback'),r=f.getBoundingClientRect(),d=document.querySelector('.pl-dock').getBoundingClientRect();return f.clientHeight>=22&&r.top>=d.top&&r.bottom<=d.bottom&&['auto','scroll'].includes(getComputedStyle(f).overflowY)})()"))
                check(f'1440x{height} keeps microphone and typed reply inside the fixed dock',page.evaluate("(()=>{const d=document.querySelector('.pl-dock').getBoundingClientRect();return ['.pl-controls .mic','.pl-reply input'].every(s=>{const r=document.querySelector(s).getBoundingClientRect();return r.top>=d.top&&r.bottom<=d.bottom&&r.left>=d.left&&r.right<=d.right})})()"))
                page.screenshot(path=str(screenshots/f'player-short-1440x{height}.png'))
            page.set_viewport_size({'width':1440,'height':1000});page.evaluate('showFactReview()')
            check('three palettes stay inside the existing six approval cards',page.locator('.acard').count()==6 and page.locator('[aria-label="Demo palette"] button').count()==3)
            page.locator('[data-card=visuals]>.head').click()
            page.get_by_role('button',name='Sage',exact=True).click()
            check('palette selection saves the exact setting and reflects reopened Visuals',page.evaluate("reviewCalls.at(-1).path==='/api/demos/fixture'&&reviewCalls.at(-1).body.settings.visual_theme==='sage'&&document.querySelector('[data-card=visuals]').classList.contains('approved')===false&&document.querySelector('.visual-theme-option[data-visual-theme=sage]').getAttribute('aria-pressed')==='true'"))
            calls=page.evaluate('reviewCalls.length');page.get_by_role('button',name='Sage',exact=True).click()
            check('reselecting the saved palette sends no change',page.evaluate('reviewCalls.length')==calls)
            page.evaluate('window.reviewFailTheme=true');page.get_by_role('button',name='Graphite',exact=True).click()
            check('blocked palette save keeps selection and re-enables its button',page.get_by_role('button',name='Graphite',exact=True).is_enabled() and page.get_by_role('button',name='Sage',exact=True).get_attribute('aria-pressed')=='true' and 'Demo worker is busy' in page.locator('#toasts').inner_text())
            run_sample_parity(browser, page, base, screenshots, check, args.live_url)
            check('no browser exceptions',not errors)
            check('no external request or mutation attempts',not rejected)
            browser.close()
    finally:
        server.shutdown();server.server_close()
    print(f'UI layout: {len(results)}/{len(results)} passed; isolated headless browser, zero outbound attempts')

if __name__=='__main__':main()

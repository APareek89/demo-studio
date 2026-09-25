"""Actual muted player: pinned answer image and tag before audio; no paid/network API."""
from pathlib import Path
import json, os, sys, tempfile
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'evals')]
from gallery_template_browser import serve

def main():
    with tempfile.TemporaryDirectory(prefix='runtime-image-player-') as temp:
        os.environ.update(MOCK_LLM='1',CLOUD_SYNC='0',STORAGE_BACKEND='local',DEMO_STUDIO_DATA=temp+'/data',DEMO_STUDIO_GRAPH_DB=temp+'/graph.sqlite')
        from server.crawl import _render_executable
        passed=[];errors=[];blocked=[]
        def check(name,ok):
            assert ok,name
            passed.append(name);print('PASS',name,flush=True)
        server,base=serve()
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(headless=True,executable_path=_render_executable(pw.chromium),args=['--mute-audio'])
                context=browser.new_context(viewport={'width':1440,'height':960},reduced_motion='reduce')
                def route(r):
                    if r.request.url.startswith(base+'/') and r.request.method=='GET':return r.continue_()
                    blocked.append(r.request.url);return r.abort()
                context.route('**/*',route);context.route_web_socket('**/*',lambda w:w.close())
                page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(base+'/');page.wait_for_function('()=>window.galleryQA?.ready')
                cases=page.evaluate('''async()=>{
                  const {resolveAnswerVisual:resolve}=await import('/web/player/answer-visual.js');
                  const b=galleryQA.synthetic();b.knowledge_snapshot_id='kb_fixture';
                  const r={answered:true,slide_id:'pair',callout_id:'front-tag',visual:{kind:'image',ref:'front',url:b.slides[1].media[0].image_url,line_index:0,snapshot_id:'kb_fixture',demo_version:1}};
                  const test=(change)=>resolve(b,b.slides,{...r,...change});
                  return [
                    ['valid pinned image accepted',test({})?.imageId==='front'],
                    ['decline cannot introduce image',test({answered:false})===null],
                    ['clarification cannot introduce image',test({clarifying_question:'Which one?'})===null],
                    ['stale pin rejected',test({visual:{...r.visual,snapshot_id:'kb_old'}})===null],
                    ['stale version rejected',test({visual:{...r.visual,demo_version:2}})===null],
                    ['arbitrary URL rejected',test({visual:{...r.visual,url:'https://invalid.test/x.jpg'}})===null],
                    ['unknown image rejected',test({visual:{...r.visual,ref:'invented'}})===null],
                    ['unknown slide rejected',test({slide_id:'missing'})===null],
                    ['other photo tag ignored',test({callout_id:'cabin-tag'})?.calloutId===null],
                    ['negative line falls back to reviewed start',test({visual:{...r.visual,line_index:-20}})?.lineIndex===0],
                    ['missing visual preserves legacy result',test({visual:null})===null],
                    ['pointer only comes from reviewed slide',!Object.hasOwn(test({visual:{...r.visual,focus:{x:1,y:0}}}),'anchor')]];
                }''')
                for name,ok in cases:check(name,ok)
                for width in (1440,390):
                    page.set_viewport_size({'width':width,'height':960 if width==1440 else 844})
                    page.evaluate('''()=>{
                      const b=galleryQA.synthetic();b.knowledge_snapshot_id='kb_fixture';
                      const s=b.slides[1];
                      const answer={answered:true,answer:'Here is the reviewed front feature.',audio:'fixture-audio:Here%20is%20the%20reviewed%20front%20feature.',fact_ids:['F1'],route:'stay',slide_id:s.id,callout_id:'front-tag',from_bank:true,visual:{kind:'image',ref:'front',url:s.media[0].image_url,line_index:0,snapshot_id:'kb_fixture',demo_version:1}};
                      return galleryQA.setup(b,answer);
                    }''')
                    page.evaluate("galleryQA.click('Browse at my pace')")
                    page.wait_for_function("()=>galleryQA.state().active.some(a=>a.text==='Approved first image detail.')")
                    page.evaluate('galleryQA.finish()')
                    page.wait_for_function("()=>galleryQA.state().active.some(a=>a.text==='Approved second image detail.')")
                    before=page.evaluate('galleryQA.state()')
                    check(f'{width}: different later photo initially visible',page.locator('.slide.on .gallery-surface').get_attribute('data-image-id')=='cabin')
                    page.evaluate("galleryQA.question('Show me the front feature')")
                    page.wait_for_function("()=>galleryQA.state().played.some(a=>a.text==='Here is the reviewed front feature.')")
                    state=page.evaluate('galleryQA.state()')
                    answer=next(a for a in state['played'] if a['text']=='Here is the reviewed front feature.')
                    check(f'{width}: same-slide answer selects exact earlier image before speech',answer['imageId']=='front' and answer['phase']=='ready')
                    check(f'{width}: same-slide answer selects owning reviewed tag',answer['tag']=='front-tag')
                    check(f'{width}: one question and no overlapping output',len(state['qa'])==1 and state['maxActive']==1)
                    check(f'{width}: published bundle unchanged',state['unchanged'])
                    page.wait_for_function("()=>[...document.querySelectorAll('.pl-chips button')].some(b=>b.textContent==='Continue demo')")
                    page.evaluate("galleryQA.click('Continue demo')")
                    page.wait_for_function("()=>galleryQA.state().active.some(a=>a.text==='Approved second image detail.')")
                    check(f'{width}: Continue restores interrupted photo',page.locator('.slide.on .gallery-surface').get_attribute('data-image-id')=='cabin')
                    check(f'{width}: player remains within viewport',page.evaluate("document.querySelector('.pl').getBoundingClientRect().right<=innerWidth+1"))
                page.set_viewport_size({'width':1440,'height':960})
                for failure in ('missing','stale','decode','factual_decode'):
                    page.evaluate('''failure=>{
                      const b=galleryQA.synthetic();b.knowledge_snapshot_id='kb_fixture';
                      const s=b.slides[1];
                      if(failure.includes('decode')){s.media[0].image_url='/fixtures/missing-picture.png';s.image_url=s.media[0].image_url;}
                      const answer={answered:failure!=='missing',visual_only:failure!=='factual_decode',answer:failure==='missing'?"I don't have a reviewed image for that request in this demo.":failure==='factual_decode'?'The approved feature is supported.':'Here is the reviewed image.',fact_ids:failure==='factual_decode'?['F1']:[],route:'stay',slide_id:s.id,callout_id:'front-tag',from_bank:true};
                      answer.audio='fixture-audio:'+encodeURIComponent(answer.answer);
                      if(failure!=='missing')answer.visual={kind:'image',ref:'front',url:s.media[0].image_url,line_index:0,snapshot_id:failure==='stale'?'kb_old':'kb_fixture',demo_version:1};
                      return galleryQA.setup(b,answer);
                    }''',failure)
                    page.evaluate("galleryQA.click('Browse at my pace')")
                    page.wait_for_function("()=>galleryQA.state().active.some(a=>a.text==='Approved first image detail.')")
                    page.evaluate("galleryQA.question('Show me the front feature')")
                    expected=("I don't have a reviewed image for that request in this demo." if failure=='missing' else
                              'The approved feature is supported.' if failure=='factual_decode' else
                              "I couldn't display that picture. You can try again or continue the demo.")
                    page.wait_for_function("expected=>galleryQA.state().played.some(a=>a.text===expected)",arg=expected)
                    state=page.evaluate('galleryQA.state()')
                    check(f'{failure}: honest response without false picture acknowledgement',not any(a['text']=='Here is the reviewed image.' for a in state['played']))
                    check(f'{failure}: no automatic follow-up form',not page.locator('.pl-lead').evaluate("e=>e.classList.contains('open')"))
                    if failure!='factual_decode':
                        page.evaluate("galleryQA.click('Stop and see the summary')")
                        page.wait_for_function("()=>document.querySelector('.pl-handoff')?.classList.contains('open')")
                        check(f'{failure}: image navigation failure is absent from factual open questions',page.locator('.pl-handoff').inner_text().find('No unanswered questions noted.')>=0)
                page.evaluate('''async()=>{
                  const {renderSlide}=await import('/web/slide.js');
                  const {createWalkthrough}=await import('/web/player/walkthrough.js');
                  const b=galleryQA.synthetic(),s=b.slides[1],host=document.createElement('div');
                  Object.assign(host.style,{position:'fixed',inset:'0',width:'1000px',height:'600px'});document.body.append(host);
                  const native=renderSlide(s,{walkthrough:true}),presentation=createWalkthrough();presentation.mount(b.slides);
                  const view=presentation.wrap(s,native);host.append(view.el);await view.prepareLine(0);
                  let release;const wait=new Promise(r=>release=r);
                  window.visualGate={host,view,presentation,entered:false,release,before:host.querySelector('.gallery-image').src};
                  visualGate.result=view.prepareLine(1,()=>{visualGate.entered=true;return wait;});
                }''')
                page.wait_for_function('()=>visualGate.entered')
                check('Decoded gallery picture remains unchanged during speech hold',page.evaluate("visualGate.host.querySelector('.gallery-image').src===visualGate.before && visualGate.host.querySelector('.gallery-surface').dataset.imageId==='front'"))
                check('No gallery camera move starts during decode hold',page.evaluate("visualGate.host.getAnimations({subtree:true}).length===0"))
                page.evaluate('visualGate.release(true)')
                check('Releasing hold presents pending picture exactly once',page.evaluate("async()=>await visualGate.result && visualGate.host.querySelector('.gallery-surface').dataset.imageId==='cabin'"))
                page.evaluate('''()=>{
                  let release;const wait=new Promise(r=>release=r);visualGate.release=release;visualGate.entered=false;
                  visualGate.result=visualGate.view.focusMedia('front',{lineIndex:0,calloutId:'front-tag',awaitPlayback:()=>{visualGate.entered=true;return wait;}});
                }''')
                page.wait_for_function('()=>visualGate.entered')
                page.evaluate('visualGate.presentation.freeze();visualGate.release(true)')
                check('Cancelled held answer cannot change current picture',page.evaluate("async()=>!await visualGate.result && visualGate.host.querySelector('.gallery-surface').dataset.imageId==='cabin'"))
                page.evaluate('visualGate.presentation.destroy();visualGate.host.remove()')
                check('No microphone, external request or script error',not errors and not blocked and page.evaluate('window.microphoneAttempts')==0)
                browser.close()
        finally:server.shutdown();server.server_close()
        print(json.dumps({'passed':len(passed),'total':len(passed),'provider_calls':0,'checks':passed}))

if __name__=='__main__':main()

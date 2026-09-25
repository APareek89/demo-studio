// Native fallback compatibility and gallery geometry helpers.
// This deliberately non-DOM harness tests fallback forwarding only. Eligible
// gallery DOM, before-audio timing and shell parity are tested in
// gallery_template_browser.py and gallery_template_contract.html.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../web/player/walkthrough.js'), 'utf8');
function harness(enabled = true) {
  const unexpected = () => { throw Error('Non-DOM/native fallback cannot allocate gallery resources'); };
  const api = vm.runInNewContext(source.replace(/export function /g, 'function ') + '\n({createWalkthrough,walkthroughStopGeometry,walkthroughFit})', {
    document: {createElement: unexpected}, setTimeout: unexpected, clearTimeout: unexpected,
    queueMicrotask: unexpected, matchMedia: unexpected, ResizeObserver: class {constructor() {unexpected();}},
  });
  const stage = {className: 'pl-stage', style: {transform: ''}}, stack = {className: 'slide-stack', style: {transform: ''}};
  const slides = [{id: 'hero', kind: 'hero_open', image_url: '/hero.png', callouts: []},
    {id: 'proof', kind: 'proof', media: [{image_id:'front',image_url:'/front.png',from_line:0},{image_id:'cabin',image_url:'/cabin.png',from_line:1}], lines: [{id:'l1',text:'Reviewed front.',fact_ids:['F1']},{id:'l2',text:'Reviewed cabin.',fact_ids:['F2']}],callouts:[{id:'tag',image_id:'cabin',text:'Reviewed cabin.',fact_ids:['F2'],reveal_on_line:1}]},
    {id:'closing',kind:'closing',image_url:'/closing.png',callouts:[]}];
  const bundle = {slides}, before = JSON.stringify(bundle), calls = [];
  const pictures = slides[1].media.map(entry => ({entry, pic:{className:'slide-pic'}, img:{src:entry.image_url}, cam:{style:{display:'contents',transform:''}}}));
  const view = {el:{className:'slide cinematic on'}, pics:pictures.map(p=>p.pic),images:pictures.map(p=>p.img),walkthroughPictures:pictures,
    setRevealed:index=>calls.push(['reveal',index]),highlight:id=>calls.push(['highlight',id]),layout:()=>calls.push(['layout']),
    setPosition:position=>calls.push(['position',position]),setImage:(...args)=>calls.push(['image',...args]),destroy:()=>calls.push(['destroy'])};
  const originals={...view}, presentation=api.createWalkthrough({stage,stack,bundle,enabled});
  return {api,presentation,stage,stack,bundle,slides,view,originals,calls,before};
}
const groups=[];
function group(name,test){groups.push([name,test]);}
group('non-DOM fallback returns the exact renderer and every original method',()=>{const h=harness();h.presentation.mount(h.slides);assert.equal(h.presentation.wrap(h.slides[1],h.view,{reveal:0}),h.view);for(const key of Object.keys(h.originals))assert.equal(h.view[key],h.originals[key]);});
group('flag-off compatibility leaves the renderer and source unchanged',()=>{const h=harness(false);assert.equal(h.presentation.wrap(h.slides[1],h.view),h.view);assert.equal(JSON.stringify(h.bundle),h.before);assert.deepEqual(h.calls,[]);});
group('hero and closing keep their own source pictures without gallery substitution',()=>{const h=harness();for(const slide of [h.slides[0],h.slides[2]]){const view={...h.view,images:[{src:slide.image_url}]};assert.equal(h.presentation.wrap(slide,view,{reveal:0}),view);assert.equal(view.images[0].src,slide.image_url);assert.equal(view.el.className,'slide cinematic on');}});
group('narration reveal reaches the native view synchronously',()=>{const h=harness(),view=h.presentation.wrap(h.slides[1],h.view);view.setRevealed(0);assert.deepEqual(h.calls,[['reveal',0]]);assert.equal(view.walkthroughPictures[0].cam.style.display,'contents');});
group('question highlight and exact-line return remain native calls in order',()=>{const h=harness(),v=h.presentation.wrap(h.slides[1],h.view);v.setRevealed(99);v.highlight('tag');h.presentation.freeze();h.presentation.resume();v.setRevealed(0);v.highlight(null);assert.deepEqual(h.calls,[['reveal',99],['highlight','tag'],['reveal',0],['highlight',null]]);});
group('two-picture ownership and line mapping stay with the reviewed renderer',()=>{const h=harness(),v=h.presentation.wrap(h.slides[1],h.view);v.setRevealed(1);assert.equal(v.walkthroughPictures,h.originals.walkthroughPictures);assert.deepEqual(v.images.map(i=>i.src),['/front.png','/cabin.png']);assert.deepEqual(h.calls,[['reveal',1]]);});
group('explicit no-picture view never restores a stale legacy image',()=>{const h=harness(),slide={id:'terms',media:[],image_url:'/stale.png',lines:[{text:'Reviewed terms.'}]},view={...h.view,images:[],walkthroughPictures:[]};assert.equal(h.presentation.wrap(slide,view),view);assert.deepEqual(view.images,[]);assert.deepEqual(view.walkthroughPictures,[]);});
group('pause freeze and resume cannot hide or transform native content',()=>{const h=harness();h.presentation.wrap(h.slides[1],h.view);h.presentation.freeze();h.presentation.pause();h.presentation.resume();assert.equal(h.view.el.className,'slide cinematic on');assert.ok(h.view.walkthroughPictures.every(p=>p.cam.style.display==='contents'&&p.cam.style.transform===''));assert.deepEqual(h.calls,[]);});
group('reset and remount do not replace or destroy the current renderer',()=>{const h=harness();h.presentation.wrap(h.slides[1],h.view);h.presentation.reset();h.presentation.mount(h.slides);assert.deepEqual(h.calls,[]);assert.equal(h.view.images,h.originals.images);});
group('presentation teardown leaves native teardown owned exactly once by the player',()=>{const h=harness();h.presentation.wrap(h.slides[1],h.view);h.presentation.destroy();h.presentation.destroy();assert.deepEqual(h.calls,[]);h.view.destroy();assert.deepEqual(h.calls,[['destroy']]);});
group('viewport resizing never inserts timing or changes stage geometry',()=>{const h=harness();for(const [width,height]of[[1440,900],[700,320],[699,319],[390,400]])h.presentation.resize({width,height});assert.deepEqual(h.stage,{className:'pl-stage',style:{transform:''}});assert.deepEqual(h.stack,{className:'slide-stack',style:{transform:''}});assert.deepEqual(h.calls,[]);});
group('all compatibility operations preserve reviewed facts and image references',()=>{const h=harness();h.presentation.mount(h.slides);for(const s of h.slides)h.presentation.wrap(s,h.view,{jump:true,reveal:99});h.presentation.reset();h.presentation.destroy();assert.equal(JSON.stringify(h.bundle),h.before);});
group('retained zoom helper never exceeds the native-pixel cap',()=>{const h=harness();for(const[nw,rw]of[[1120,800],[830,760],[800,760],[100,200]]){const g=h.api.walkthroughStopGeometry({placement:'overlay',anchor:{x:.5,y:.5},part_box:{w:.01,h:.02}},nw,rw);assert.ok(g.z<=Math.min(2.2,nw/rw*1.15));}});
group('retained anchored zoom clamps pan to the available image',()=>{const h=harness();for(const x of[0,.2,.5,.8,1])for(const y of[0,.5,1]){const g=h.api.walkthroughStopGeometry({placement:'overlay',anchor:{x,y}},1120,760);assert.ok(Math.abs(g.x)<=g.lim&&Math.abs(g.y)<=g.lim);assert.ok(g.z*(.5-Math.abs(g.x))>=.5);}});
group('caption-only or missing-anchor evidence cannot produce a zoom target',()=>{const h=harness();for(const callout of[{placement:'panel',anchor:{x:0,y:1}},{placement:'overlay'},null]){const g=h.api.walkthroughStopGeometry(callout,1120,760);assert.equal(g.z,1);assert.equal(Math.abs(g.x),0);assert.equal(Math.abs(g.y),0);}});
group('retained native fit never enlarges a small source',()=>{const fit=harness().api.walkthroughFit(200,100,900,400);assert.equal(fit.width,200);assert.equal(fit.height,100);assert.equal(fit.scale,1);});
group('retained native fit contains portrait and landscape without changing aspect',()=>{const h=harness();for(const[w,hh]of[[600,1000],[1120,600]]){const fit=h.api.walkthroughFit(w,hh,390,180);assert.ok(fit.width<=390&&fit.height<=180);assert.ok(Math.abs(fit.width/fit.height-w/hh)<.0001);}});
group('gallery visibility overrides require the gallery slide opt-in class',()=>{const css=fs.readFileSync(path.join(__dirname,'../web/player-ui.css'),'utf8');assert.ok(!/\.wt-(?:wide|tour|view|hall)\b/.test(css));assert.match(css,/\.slide\.gallery-slide > \.slide-media/);assert.match(css,/\.slide\.gallery-slide > \.slide-panel/);});
let passed=0;for(const[name,test]of groups){try{test();passed++;console.log(`PASS walkthrough compatibility: ${name}`);}catch(e){console.error(`FAIL ${name}\n${e.stack}`);}}
console.log(`Walkthrough native fallback and geometry: ${passed}/${groups.length} (non-DOM fallback and geometry; full gallery covered by browser contract)`);process.exitCode=passed===groups.length?0:1;

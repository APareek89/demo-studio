// Full shipped Align renderer with mocked DOM/API; no network, providers or data writes.
import fs from 'node:fs';
import assert from 'node:assert/strict';
class Node {
  constructor(tag='#text',text=''){this.tag=tag;this.nodeType=tag==='#text'?3:1;this.children=[];this.attrs={};this.listeners={};this.className='';this._text=text;this.disabled=false;this.clicks=0;}
  get classList(){const n=this;return{contains:k=>n.className.split(/\s+/).includes(k),add:k=>{n.className=[...new Set([...n.className.split(/\s+/).filter(Boolean),k])].join(' ');},remove:k=>{n.className=n.className.split(/\s+/).filter(x=>x!==k).join(' ');},toggle(k,force){const on=force??!this.contains(k);this[on?'add':'remove'](k);}};}
  setAttribute(k,v){this.attrs[k]=String(v);if(k==='disabled')this.disabled=true;}
  addEventListener(k,fn){this.listeners[k]=fn;}
  append(...children){for(const c of children.flat()){if(c===null||c===undefined||c===false)continue;this.children.push(c instanceof Node?c:new Node('#text',String(c)));}}
  replaceChildren(...children){this.children=[];this.append(...children);}
  get textContent(){return this._text+this.children.map(n=>n.textContent).join('');}
  set textContent(text){this._text=String(text);this.children=[];}
  querySelector(selector){return all(this).find(n=>selector.startsWith('.')?n.classList.contains(selector.slice(1)):n.tag===selector)||null;}
  click(){this.clicks++;return this.listeners.click?.();}
}
const all=n=>n.children.flatMap(c=>[c,...all(c)]);
const area=new Node('main'),listeners=new Map();
const timers=new Map();let nextTimer=0;
globalThis.document={visibilityState:'visible',createElement:t=>new Node(t),createTextNode:t=>new Node('#text',t),addEventListener(){},removeEventListener(){}};
globalThis.window={addEventListener:(name,fn)=>listeners.set(name,fn)};
globalThis.setInterval=()=>1;globalThis.clearInterval=()=>{};
globalThis.setTimeout=(fn,ms)=>{const id=++nextTimer;timers.set(id,{fn,ms});return id;};globalThis.clearTimeout=id=>timers.delete(id);
globalThis.fetch=()=>{throw new Error('Outbound request forbidden');};
const {h,esc}=await import('../web/api.js');
const approvals=Object.fromEntries(['visuals','facts','script','faq','persona','ctas'].map(k=>[k,true]));
let remote={demo:{id:'dm_12345678',name:'Narration fixture',status:'error',settings:{},approvals,stages:{author:{status:'error',error:'Drafting provider unavailable.'}}},
  cards:{visuals:{images:[],shots:[],segments:[],gaps:[]},facts:{facts:[],unknowns:[],sources:[],conflicts:[]},script:{segments:[],timeline:{},preparation:{status:'incomplete',words:4,target_words:495,attempts:2,mock_preview:false},narration_minimum:{seconds:2.11,minimum_seconds:180,measured:false,basis:'estimated'}},deck:{slides:[]},faq:{entries:[],unknowns:[]},persona:{provider:'mock'},ctas:[]},conversation:[],running:false};
const calls=[],toasts=[],routes=[];let post,events,readinessSuffix='?override_readiness=true';
const api={get:async p=>p.startsWith('/api/voices')?{voices:[],chain:[],provider:'mock'}:structuredClone(remote),post:(p,body)=>{calls.push({path:p,body});return post(p,body);}};
globalThis.__narrationRecovery={api,h,esc,toast:(text)=>toasts.push(text),icon:()=>h('svg'),renderSlide:()=>{throw new Error('No preview expected');},readinessQuery:()=>readinessSuffix};
let source=fs.readFileSync(new URL('../web/studio/align.js',import.meta.url),'utf8').replace(/^import .*;\n/gm,'');
source='const {api,h,esc,toast,icon,renderSlide,readinessQuery}=globalThis.__narrationRecovery;\n'+source;
const {renderAlign}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
renderAlign({demoId:'dm_12345678',state:structuredClone(remote),area,setRailStatus(){},navigate:p=>routes.push(p),subscribe:fn=>{events=fn;}});
const flush=async()=>{for(let i=0;i<8;i++)await Promise.resolve();};
const refresh=async()=>{events('phase_done',{phase:'align'});await flush();};
const find=(node,label)=>all(node).find(n=>n.tag==='button'&&n.textContent===label);
const cardArea=area.querySelector('.cards'),overlay=area.querySelector('.overlay'),buildBar=area.querySelector('.build-bar');
const scriptCard=()=>all(cardArea).find(n=>n.attrs['data-card']==='script');
const notice=()=>cardArea.querySelector('.narration-status');
let passed=0;const check=(label,ok)=>{assert.ok(ok,label);passed++;console.log('PASS',label);};
check('unfinished draft has compact actionable status, no manual three-minute preparation or word deficit',!!find(notice(),'Retry drafting')&&!area.textContent.includes('Prepare three-minute narration')&&!area.textContent.includes('491')&&!cardArea.querySelector('.narration-minimum'));
check('duration target and estimated timing stay within Script',scriptCard().textContent.includes('3-minute narration target')&&scriptCard().textContent.includes('0:02 estimated')&&!notice().textContent.includes('0:02'));
check('saved six approvals cannot present incomplete Script as customer-ready',cardArea.textContent.includes('5 of 6 approved')&&find(scriptCard(),'Approve').disabled&&find(cardArea,'Approve all').disabled&&buildBar.classList.contains('hidden'));
await find(scriptCard(),'Approve').click();await find(cardArea,'Approve all').click();await find(buildBar,'Build the demo').click();
check('disabled approval and Build handlers also reject programmatic activation without writes',calls.length===0);
check('error overlay preserves provider error with Retry drafting, not unrelated Build retry',overlay.textContent.includes('Drafting provider unavailable.')&&!!find(overlay,'Retry drafting')&&!find(overlay,'Retry'));
find(overlay,'Back to the cards').click();
let reject;post=()=>new Promise((_,no)=>{reject=no;});
const button=find(notice(),'Retry drafting'),pending=button.click();button.click();
check('explicit retry disables duplicate clicks while pending',calls.length===1&&find(notice(),'Retrying…').disabled);
check('draft retry uses guarded Author revision and never requests automatic Build',calls[0].path==='/api/demos/dm_12345678/revise?override_readiness=true'&&calls[0].body.stage==='author'&&calls[0].body.rebuild===false&&calls[0].body.instruction==='Expand the default guided narration to the selected demo duration using distinct supported detail from the approved facts. Preserve the reviewed story, voice and CTAs. Film, questions, deeper-only lines and repeated claims do not count; do not pad or slow the voice.');
reject(new Error('Provider readiness is required'));await pending;await flush();
check('readiness failure remains visible and retry is re-enabled',toasts.at(-1)==='Provider readiness is required'&&notice().textContent.includes('Provider readiness is required')&&!find(notice(),'Retry drafting').disabled);
readinessSuffix='';post=async()=>{remote.demo.status='reading';remote.running=true;};
await find(notice(),'Retry drafting').click();await flush();
check('default readiness policy is respected on retry',calls.length===2&&calls[1].path.endsWith('/revise')&&overlay.textContent.includes('Preparing your demo'));
remote.demo.status='align';remote.running=false;remote.demo.approvals.script=false;
remote.cards.script.preparation={status:'ready',words:495,target_words:495,mock_preview:false};remote.cards.script.narration_minimum={seconds:260,minimum_seconds:180,measured:false,basis:'estimated'};
await refresh();
check('completed automatic draft has no recovery banner and returns for human approval',!notice()&&!find(cardArea,'Retry drafting')&&!find(scriptCard(),'Approve').disabled&&routes.length===0&&calls.length===2&&overlay.classList.contains('hidden'));
remote.cards.script.preparation={status:'needs_sources',mock_preview:false};await refresh();
check('only explicit source-gap status requests evidence rather than another model retry',notice().textContent.includes('Product evidence needed')&&!!find(notice(),'Add source material')&&!find(notice(),'Retry drafting')&&find(scriptCard(),'Approve').disabled);
const fileInput=all(area).find(n=>n.tag==='input'&&n.attrs.type==='file');await find(notice(),'Add source material').click();
check('source action opens existing attachment control without automatic POST',fileInput.clicks===1&&calls.length===2);
remote.demo.approvals.facts=false;post=async p=>{if(p.endsWith('/approve/facts'))remote.demo.approvals.facts=true;};await refresh();
const factsCard=all(cardArea).find(n=>n.attrs['data-card']==='facts');await find(factsCard,'Approve').click();await flush();
check('other cards remain individually reviewable while Script is blocked',calls.at(-1).path.endsWith('/approve/facts')&&remote.demo.approvals.facts===true);
remote.demo.approvals.script=true;remote.cards.script.preparation={status:'needs_preparation',mock_preview:true};remote.cards.script.narration_minimum.seconds=2.11;remote.cards.script.timeline={total_seconds:2.11,planned_total_seconds:180};await refresh();
check('mock placeholder is explicitly not customer-ready, with no false duration or futile Retry',notice().textContent.includes('MOCK preview')&&notice().textContent.includes('Placeholder narration is not ready for customers')&&!scriptCard().textContent.includes('0:02')&&!scriptCard().textContent.includes('2 s estimated')&&!find(notice(),'Retry drafting')&&cardArea.textContent.includes('5 of 6 approved')&&buildBar.classList.contains('hidden'));
remote.cards.script.preparation={status:'needs_preparation',mock_preview:false};remote.cards.script.narration_minimum={seconds:128.3,minimum_seconds:180,measured:true,basis:'measured',language:'hi-IN'};await refresh();
check('legacy short recording keeps normal Build and compact language timing without a repair task',!notice()&&!buildBar.classList.contains('hidden')&&!find(buildBar,'Build the demo').disabled&&scriptCard().textContent.includes('2:08 recorded (hi-IN)'));
post=async()=>{};await find(buildBar,'Build the demo').click();
check('legacy normal Build delegates preparation to server without an extra revision request',calls.at(-1).path.endsWith('/build')&&!calls.at(-1).body);
remote.cards.script.preparation={status:'needs_recording',mock_preview:false,recording_incomplete:true,reason:'A selected-language recording needs updating during Build.'};await refresh();
check('missing or stale recording keeps normal Build without rewriting the draft',!notice()&&!find(cardArea,'Retry drafting')&&!buildBar.classList.contains('hidden')&&!find(buildBar,'Build the demo').disabled&&scriptCard().textContent.includes('A selected-language recording needs updating during Build.'));
remote.cards.script.preparation={status:'incomplete',mock_preview:false};remote.running=true;await refresh();
const beforeBusy=calls.length;await find(notice(),'Retry drafting').click();
check('running worker suppresses retry even through an old handler',find(notice(),'Retry drafting').disabled&&calls.length===beforeBusy);
const runTimer=async()=>{const [id,timer]=timers.entries().next().value;timers.delete(id);timer.fn();await flush();return timer.ms;};
remote.running=false;
check('bounded completion refresh promptly re-enables retry',await runTimer()===250&&!find(notice(),'Retry drafting').disabled&&timers.size===0);
remote.running=true;await refresh();const delays=[];while(timers.size)delays.push(await runTimer());
check('worker refresh stops after four short attempts',delays.join(',')==='250,750,1500,3000');
remote.running=false;await refresh();remote.running=true;await refresh();listeners.get('hashchange')?.();
check('navigation cancels the owned refresh timer',timers.size===0);
console.log(`Align narration recovery contracts: ${passed}/${passed}; no network/providers`);

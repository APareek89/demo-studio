// Full shipped Align renderer with mocked DOM/API; no network, providers or data writes.
import fs from 'node:fs';
import assert from 'node:assert/strict';
class Node {
  constructor(tag='#text',text=''){this.tag=tag;this.nodeType=tag==='#text'?3:1;this.children=[];this.attrs={};this.listeners={};this.className='';this._text=text;this.disabled=false;}
  get classList(){const n=this;return{contains:k=>n.className.split(/\s+/).includes(k),add:k=>{n.className=[...new Set([...n.className.split(/\s+/).filter(Boolean),k])].join(' ');},remove:k=>{n.className=n.className.split(/\s+/).filter(x=>x!==k).join(' ');},toggle(k,force){const on=force??!this.contains(k);this[on?'add':'remove'](k);}};}
  setAttribute(k,v){this.attrs[k]=String(v);if(k==='disabled')this.disabled=true;}
  addEventListener(k,fn){this.listeners[k]=fn;}
  append(...children){for(const c of children.flat()){if(c===null||c===undefined||c===false)continue;this.children.push(c instanceof Node?c:new Node('#text',String(c)));}}
  replaceChildren(...children){this.children=[];this.append(...children);}
  get textContent(){return this._text+this.children.map(n=>n.textContent).join('');}
  set textContent(text){this._text=String(text);this.children=[];}
  querySelector(selector){return all(this).find(n=>selector.startsWith('.')&&n.classList.contains(selector.slice(1)))||null;}
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
let remote={demo:{id:'dm_12345678',name:'Narration fixture',status:'error',settings:{},approvals,stages:{bundle:{status:'error',error:'Default guided narration is 128.3s; 180s required.'}}},
  cards:{visuals:{images:[],shots:[],segments:[],gaps:[]},facts:{facts:[],unknowns:[],sources:[],conflicts:[]},script:{segments:[],timeline:{},narration_minimum:{seconds:128.3,minimum_seconds:180,measured:true,basis:'measured'}},deck:{slides:[]},faq:{entries:[],unknowns:[]},persona:{provider:'mock'},ctas:[]},conversation:[],running:false};
const calls=[],toasts=[],routes=[];let post,events,readinessSuffix='?override_readiness=true';
const api={get:async p=>p.startsWith('/api/voices')?{voices:[],chain:[],provider:'mock'}:structuredClone(remote),post:(p,body)=>{calls.push({path:p,body});return post(p,body);}};
globalThis.__narrationRecovery={api,h,esc,toast:(text)=>toasts.push(text),icon:()=>h('svg'),renderSlide:()=>{throw new Error('No preview expected');},readinessQuery:()=>readinessSuffix};
let source=fs.readFileSync(new URL('../web/studio/align.js',import.meta.url),'utf8').replace(/^import .*;\n/gm,'');
source='const {api,h,esc,toast,icon,renderSlide,readinessQuery}=globalThis.__narrationRecovery;\n'+source;
const {renderAlign}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
renderAlign({demoId:'dm_12345678',state:structuredClone(remote),area,setRailStatus(){},navigate:p=>routes.push(p),subscribe:fn=>{events=fn;}});
const flush=async()=>{for(let i=0;i<8;i++)await Promise.resolve();};
const find=(node,label)=>all(node).find(n=>n.tag==='button'&&n.textContent===label);
const cardArea=area.querySelector('.cards'),overlay=area.querySelector('.overlay');
let passed=0;const check=(label,ok)=>{assert.ok(ok,label);passed++;console.log('PASS',label);};
check('128.3s shortage is visible above the six cards with a direct recovery action',cardArea.children[1].classList.contains('narration-minimum')&&cardArea.children[1].textContent.includes('52 more seconds')&&!!find(cardArea.children[1],'Prepare three-minute narration'));
check('error overlay offers the same direct recovery without hiding it inside Script preview',!overlay.classList.contains('hidden')&&!!find(overlay,'Prepare three-minute narration'));
find(overlay,'Back to the cards').listeners.click();
check('returning to Align keeps recovery visible even with Script collapsed',overlay.classList.contains('hidden')&&!!find(cardArea,'Prepare three-minute narration'));
let reject;post=()=>new Promise((_,no)=>{reject=no;});
const button=find(cardArea,'Prepare three-minute narration'),pending=button.listeners.click();button.listeners.click();
check('pending request disables recovery and suppresses duplicate clicks',calls.length===1&&find(cardArea,'Preparing narration…')?.disabled===true);
check('recovery uses readiness policy and exact Plan revision without automatic rebuild',calls[0].path==='/api/demos/dm_12345678/revise?override_readiness=true'&&calls[0].body.stage==='plan'&&calls[0].body.rebuild===false&&calls[0].body.instruction==='Expand the default guided narration to at least three measured minutes using distinct supported detail from the approved facts. Preserve the reviewed story, voice and CTAs. Film, questions, deeper-only lines and repeated claims do not count; do not pad or slow the voice.');
reject(new Error('Provider readiness is required'));await pending;await flush();
check('readiness or request error is visible and re-enables recovery',toasts.at(-1)==='Provider readiness is required'&&cardArea.textContent.includes('Provider readiness is required')&&!find(cardArea,'Prepare three-minute narration').disabled);
readinessSuffix='';post=async()=>{remote.demo.status='reading';remote.running=true;};
await find(cardArea,'Prepare three-minute narration').listeners.click();await flush();
check('retry respects default readiness and shows preparation progress',calls.length===2&&calls[1].path.endsWith('/revise')&&!overlay.classList.contains('hidden')&&overlay.textContent.includes('Preparing your demo'));
remote.demo.status='align';remote.running=false;remote.demo.approvals.script=false;remote.cards.script.narration_minimum={seconds:194,minimum_seconds:180,measured:false,basis:'estimated'};
events('phase_done',{phase:'revise'});await flush();
check('completed draft returns to human review without Build, approval or navigation calls',overlay.classList.contains('hidden')&&calls.every(c=>c.path.includes('/revise'))&&routes.length===0&&cardArea.textContent.includes('5 of 6 approved'));
check('sufficient estimated draft has no expansion action and still requires measured publication',!find(cardArea,'Prepare three-minute narration')&&cardArea.textContent.includes('publication requires at least three measured minutes'));
remote.cards.script.narration_minimum={seconds:210,minimum_seconds:180,measured:false,basis:'estimated',preparation:{words:400,target_words:495,sufficient:false}};
events('phase_done',{phase:'revise'});await flush();
check('210s estimate below the distinct-content target still offers preparation with an accurate word deficit',!!find(cardArea,'Prepare three-minute narration')&&cardArea.textContent.includes('95 more words')&&!cardArea.textContent.includes('more seconds'));
remote.cards.script.narration_minimum.measured=true;remote.cards.script.narration_minimum.basis='measured';
events('phase_done',{phase:'revise'});await flush();
check('three measured minutes take precedence over a stale preparation target',!find(cardArea,'Prepare three-minute narration')&&cardArea.textContent.includes('Recorded narration meets the minimum.')&&!cardArea.textContent.includes('more words'));
remote.demo.status='error';remote.cards.script.narration_minimum={seconds:128.3,minimum_seconds:180,measured:true,basis:'measured'};
events('phase_done',{phase:'revise'});await flush();
post=async()=>{throw new Error('Preparation unavailable. Try again.');};
await find(overlay,'Prepare three-minute narration').listeners.click();await flush();
check('preparation failure in the error overlay remains visible and re-enables the action on both surfaces',!overlay.classList.contains('hidden')&&overlay.textContent.includes('Preparation unavailable. Try again.')&&!find(overlay,'Prepare three-minute narration').disabled&&!find(cardArea,'Prepare three-minute narration').disabled);
remote.running=true;events('hello',{snapshot:structuredClone(remote.demo)});await flush();
const beforeBusy=calls.length;
await find(overlay,'Preparing narration…').listeners.click();
check('an active worker prevents preparation even if an old click handler is invoked',find(overlay,'Preparing narration…').disabled&&calls.length===beforeBusy);
const runTimer=async()=>{const [id,timer]=timers.entries().next().value;timers.delete(id);timer.fn();await flush();return timer.ms;};
remote.running=false;
check('short refresh observes the finished worker and promptly enables recovery',await runTimer()===250&&!find(overlay,'Prepare three-minute narration').disabled&&timers.size===0);
remote.cards.script.narration_minimum.language='hi-IN';events('phase_done',{phase:'align'});await flush();
check('limiting alternate-language narration is labelled and can be prepared without navigating to Rehearse',cardArea.textContent.includes('Spoken narration (hi-IN)')&&!!find(cardArea,'Prepare three-minute narration')&&routes.length===0);
remote.running=true;events('phase_done',{phase:'align'});await flush();
const delays=[];while(timers.size)delays.push(await runTimer());
check('a lingering worker gets only four bounded short refreshes',delays.join(',')==='250,750,1500,3000'&&find(overlay,'Preparing narration…').disabled);
remote.running=false;events('phase_done',{phase:'align'});await flush();
remote.running=true;events('phase_done',{phase:'align'});await flush();
listeners.get('hashchange')?.();
check('navigation cancels the owned short-refresh timer',timers.size===0);
console.log(`Align narration recovery contracts: ${passed}/${passed}; no network/providers`);

// WebKit-style suspended/interrupted AudioContext doubles, virtual time only.
// No real device, browser, socket, application data or provider calls.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync(new URL('../web/player/live-voice.js',import.meta.url),'utf8');
let passed=0;
const flush=async()=>{for(let i=0;i<20;i++)await Promise.resolve();};
function fixture(){
  const clock={now:0,next:0,jobs:new Map(),set(fn,ms){const id=++this.next;this.jobs.set(id,{fn,at:this.now+ms});return id;},clear(id){this.jobs.delete(id);},async advance(ms){this.now+=ms;for(let pass=0;pass<10;pass++){const due=[...this.jobs].filter(([,v])=>v.at<=this.now);if(!due.length)break;for(const [id,v]of due){this.jobs.delete(id);v.fn();}await flush();}}};
  const contexts=[],errors=[],sent=[];let permissions=0;
  class Context{
    constructor(){this.state='suspended';this.currentTime=0;this.destination={};this.resumes=[];this.audioWorklet={addModule:async()=>{}};contexts.push(this);}
    resume(){if(this.state==='running')return Promise.resolve();return new Promise((resolve,reject)=>this.resumes.push({resolve:()=>{this.state='running';resolve();},reject}));}
    suspend(){this.state='suspended';return Promise.resolve();}
    close(){this.state='closed';return Promise.resolve();}
    createGain(){return{gain:{value:1},connect(){}};}
    createMediaStreamSource(){return{connect(){},disconnect(){}};}
  }
  class Worklet{constructor(){this.port={};}connect(){}disconnect(){}}
  const {LiveVoiceClient}=vm.runInNewContext(source.replace(/export /g,'')+'\n({LiveVoiceClient})',{setTimeout:clock.set.bind(clock),clearTimeout:clock.clear.bind(clock),Date:{now:()=>clock.now},Float32Array,Uint8Array,Math,atob});
  const client=new LiveVoiceClient({url:'/run/live',sessionId:'mobile_audio',env:{AudioContext:Context,AudioWorkletNode:Worklet,navigator:{mediaDevices:{getUserMedia:async()=>{permissions++;return{getTracks:()=>[],getAudioTracks:()=>[]};}}}},onError:e=>errors.push(e)});
  client.connect=async()=>{client.ready=true;};client.send=(type,data)=>sent.push({type,...data});
  return{client,clock,contexts,errors,sent,get permissions(){return permissions;}};
}
function observe(promise){const out={settled:false};promise.then(value=>Object.assign(out,{settled:true,value}),error=>Object.assign(out,{settled:true,error}));return out;}
function check(name,condition){assert.ok(condition,name);passed++;console.log('PASS',name);}
{
  const f=fixture(),result=observe(f.client.startCapture());await flush();await f.clock.advance(5000);
  check('blocked capture-context resume settles instead of leaving microphone startup pending',result.settled&&result.value===false);
  check('blocked capture requests no device and releases its setup context',f.permissions===0&&f.contexts[0].state==='closed'&&!f.client.mic&&f.errors.some(e=>/audio|sound/i.test(e)));
  f.client.close();
}
{
  const f=fixture(),result=observe(f.client.startCapture());await flush();const first=f.contexts[0];f.client.stopCapture();
  check('switching the microphone off immediately releases its pending setup context',first.state==='closed');
  first.resumes[0].resolve();await flush();
  check('late resumed capture cannot request microphone permission or activate input',result.settled&&result.value===false&&f.permissions===0&&!f.client.mic);f.client.close();
}
{
  const f=fixture(),old=observe(f.client.startCapture());await flush();const first=f.contexts[0];f.client.stopCapture();const fresh=observe(f.client.startCapture());await flush();const second=f.contexts[1];first.resumes[0].resolve();await flush();
  check('late cancelled setup cannot take ownership from a newer capture attempt',old.settled&&f.client.captureSetupContext===second&&!fresh.settled);
  f.client.stopCapture();second.resumes[0].resolve();await flush();f.client.close();
}
{
  const f=fixture(),result=observe(f.client.speak('Reviewed answer'));await flush();const context=f.contexts[0];await f.clock.advance(5000);
  check('blocked output resume rejects before requesting paid speech or deferred playback',result.settled&&!!result.error&&!f.client.delivery&&!f.sent.some(e=>e.type==='delivery.speak'||e.type==='delivery.request'));
  context.resumes[0].resolve();await flush();
  check('late output resume after timeout cannot revive an obsolete utterance',!f.client.delivery&&!f.sent.some(e=>e.type==='delivery.speak'));f.client.close();
}
{
  const f=fixture(),result=observe(f.client.unlockOutput());await flush();const context=f.contexts[0];f.client.close();context.resumes[0].resolve();await flush();
  check('closing during audio unlock rejects its old owner without reopening output',result.settled&&result.error?.name==='AbortError'&&f.client.outputContext===null);
  const count=f.contexts.length,closed=observe(f.client.unlockOutput());await flush();
  check('a disposed client cannot create a fresh audio context',closed.settled&&closed.error?.name==='AbortError'&&f.contexts.length===count);
}
{
  const f=fixture(),unlock=f.client.unlockOutput();await flush();const context=f.contexts[0];context.resumes[0].resolve();await unlock;
  context.state='suspended';let rejected;const active={utteranceId:'u',turnId:'t',sources:new Set(),nextAt:1,ended:false,started:true,reject:e=>{rejected=e;},resolve(){}};f.client.delivery=active;
  f.client.resumeOutput();await flush();await f.clock.advance(5000);
  check('blocked resume after a temporary speech hold settles the owned delivery',!!rejected&&!f.client.delivery&&f.sent.some(e=>e.type==='delivery.end'&&e.completed===false));f.client.close();
}
{
  const f=fixture(),unlock=f.client.unlockOutput();await flush();const context=f.contexts[0];context.resumes[0].resolve();await unlock;
  context.state='suspended';const old={utteranceId:'old'},fresh={utteranceId:'fresh'};f.client.delivery=old;f.client.resumeOutput();await flush();f.client.delivery=fresh;await f.clock.advance(5000);
  check('failed stale resume cannot cancel a replacement delivery',f.client.delivery===fresh);f.client.delivery=null;f.client.close();
}
{
  const f=fixture(),unlock=f.client.unlockOutput();await flush();f.client.setMuted(true);f.contexts[0].resumes[0].resolve();await unlock;
  check('successful mobile unlock preserves the current muted output setting',f.client.gain.gain.value===0);f.client.close();
}
{
  const f=fixture(),unlock=observe(f.client.unlockOutput());await flush();const context=f.contexts[0];context.resumes[0].resolve();context.state='interrupted';await flush();
  check('a resolved resume in interrupted state is not mistaken for playable audio',unlock.settled&&!!unlock.error);f.client.close();
}
console.log(`Mobile audio lifecycle: ${passed}/${passed}; virtual contexts only, no physical iPhone claim`);

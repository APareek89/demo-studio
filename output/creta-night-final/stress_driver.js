// Eval-only driver: real player, real live client; no application file mutation.
// Synthetic delivery durations are control stimuli, never voice latency evidence.
const $ = s => document.querySelector(s);
const nativeFetch = window.fetch.bind(window);
async function json(url, body) {
  const response = await nativeFetch(url, body === undefined ? {} : { method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body) });
  if (!response.ok) throw new Error(`${url}: ${response.status} ${await response.text()}`);
  return response.json();
}
const config = await json('/stress/config'), bundle = await json('/stress/bundle');
const cases = config.cases, speed = config.live ? 1 : .04;
const evidence = {mode:config.live?'live_caption_only':'offline_synthetic',boundary:cases.boundary,started_at:null,checks:[],issues:[],steps:[],interruptions:[],responses:[],wire:[],synthetic_media:[],session_id:null};
const log = (kind, fields={}) => {
  const row={at_ms:Date.now(),kind,...fields}; evidence.steps.push(row);
  $('#events').textContent += JSON.stringify(row)+'\n';
  json('/stress/event',row).catch(error=>{evidence.issues.push({kind:'evidence_save',message:error.message});});
  return row;
};
const sleep = ms => new Promise(resolve=>setTimeout(resolve,ms));
async function until(fn, label, timeout=45000) {
  const start=Date.now(); while(Date.now()-start<timeout) {const result=fn();if(result)return result;await sleep(40);}
  throw new Error(`Timed out: ${label}`);
}
function check(name, passed, detail={}) {
  evidence.checks.push({name,passed:!!passed,at_ms:Date.now(),detail});log('check',{name,passed:!!passed});
  if(!passed)evidence.issues.push({kind:'assertion',name,detail});
}
function button(name, required=true) {
  const found=[...document.querySelectorAll('#fixture button')].find(el=>(el.textContent.trim()===name||el.getAttribute('aria-label')===name)&&el.getClientRects().length);
  if(!found&&required)throw new Error(`Visible button missing: ${name}`);return found;
}
function closeLead(){document.querySelector('.pl-lead.open .lead-close')?.click();}
function submit(text, intake=false) {
  closeLead();const input=$(intake?'.pl-intake.open input[aria-label="Your answer"]':'.pl-reply input[aria-label="Your question or answer"]');
  if(!input?.getClientRects().length)throw new Error('Visible customer input missing');
  input.value=text;input.dispatchEvent(new Event('input',{bubbles:true}));input.form.requestSubmit();log('customer_input',{text,intake});
}
const snap=()=>window.__stressSnapshot?.();
const recorded=new Map();
function recordAudio(value) {
  if(!value||typeof value!=='object')return;
  if(value.audio&&value.text)recorded.set(value.audio,{text:value.text,duration:value.duration_exact||value.duration_seconds});
  for(const part of Object.values(value))if(part&&typeof part==='object')Array.isArray(part)?part.forEach(recordAudio):recordAudio(part);
}
recordAudio(bundle);
if(bundle.intake?.audio?.q1)recorded.set(bundle.intake.audio.q1,{text:bundle.intake.q1});
window.__stressAudio=[];window.__stressTracks=[];
// Codex's programmatic command is not a trusted autoplay gesture. The harness
// therefore uses no browser audio device at all. These minimal clocked nodes
// are control fakes; the real LiveVoiceClient still owns and cancels them.
const node=()=>({connect(){},disconnect(){}});
class SilentContext {
  constructor(){this.started=Date.now();this.state='running';this.sampleRate=24000;this.destination=node();this.audioWorklet={addModule:async()=>{}};}
  get currentTime(){return (Date.now()-this.started)/1000;}
  resume(){this.state='running';return Promise.resolve();}
  close(){this.state='closed';return Promise.resolve();}
  createGain(){return {...node(),gain:{value:0}};}
  createMediaStreamSource(){return node();}
  createBuffer(channels,length,rate){return {duration:length/rate,copyToChannel(){}};}
  createBufferSource(){const context=this,source={...node(),buffer:null,onended:null,start(at=0){this.timer=setTimeout(()=>this.onended?.(),Math.max(0,at-context.currentTime)*1000+(this.buffer?.duration||0)*1000);},stop(){clearTimeout(this.timer);}};return source;}
}
window.AudioContext=SilentContext;window.webkitAudioContext=SilentContext;
window.AudioWorkletNode=class {constructor(){this.port={onmessage:null,postMessage(){}};}connect(){}disconnect(){}};
class CaptionAudio {
  constructor(url) {this.src=url;this.paused=true;this.ended=false;this.muted=true;this.volume=0;this.duration=1;this.listeners={};window.__stressAudio.push(this);}
  addEventListener(kind,fn){(this.listeners[kind]||=[]).push(fn);}
  removeEventListener(kind,fn){this.listeners[kind]=(this.listeners[kind]||[]).filter(x=>x!==fn);}
  fire(kind){this['on'+kind]?.();for(const fn of this.listeners[kind]||[])fn();}
  load(){} removeAttribute(){}
  get currentTime(){return this.started?Math.min(this.duration,(Date.now()-this.started)/1000):0;}
  play(){const item=recorded.get(this.src)||{};this.duration=Math.max(1.2,item.duration||String(item.text||'').split(/\s+/).length/2.5)*speed;this.paused=false;this.ended=false;this.started=Date.now();this.fire('playing');evidence.synthetic_media.push({at_ms:Date.now(),kind:'recorded_caption_clock',url:this.src,text:item.text||'',duration:this.duration,synthetic:true});this.timer=setTimeout(()=>{if(!this.paused){this.ended=true;this.paused=true;this.fire('ended');}},this.duration*1000);return Promise.resolve();}
  pause(){clearTimeout(this.timer);this.paused=true;this.fire('pause');}
}
window.Audio=CaptionAudio;
window.speechSynthesis.speak=()=>{throw new Error('Browser speech is forbidden in caption-only review');};
// No physical microphone. A silent local stream permits real capture ownership
// and generation fences to run; the proxy drops every PCM frame before upstream.
navigator.mediaDevices.getUserMedia=async()=>{const track={readyState:'live',stop(){this.readyState='ended';}};window.__stressTracks.push(track);return {getTracks:()=>[track],getAudioTracks:()=>[track]};};
const NativeSocket=window.WebSocket;
window.WebSocket=class extends NativeSocket {
  constructor(...args){super(...args);window.__stressSocket=this;this.addEventListener('message',e=>{try{const value=JSON.parse(e.data);evidence.wire.push({at_ms:Date.now(),direction:'in',...value,audio:value.audio?'[synthetic silence]':undefined});if(value.type==='turn.result'){const provenance=value.utterance_id==='stale-synthetic'?'injected_stale_test':config.live&&!value.synthetic?'live_api_result':'offline_synthetic';evidence.responses.push({at_ms:Date.now(),...value,provenance});log('answer_result',{turn_id:value.turn_id,answer:value.answer,provenance});}}catch{}});}
  send(raw){const value=JSON.parse(raw);if(value.type!=='audio.input')evidence.wire.push({at_ms:Date.now(),direction:'out',...value});return super.send(raw);}
};
function inject(event) {window.__stressSocket.dispatchEvent(new MessageEvent('message',{data:JSON.stringify({session_id:evidence.session_id,input_generation:snap().input_generation,...event,synthetic:true})}));}
async function onset(label) {
  const before=snap();inject({type:'input.speech_start',input_id:label});inject({type:'transcript.final',input_id:label,text:''});await sleep(30);const after=snap();
  const row={label,at_ms:Date.now(),before,after,synthetic:true,measurement:'Synthetic browser event to client stop only; not acoustic onset'};evidence.interruptions.push(row);
  check(label+' cancels current delivery',!after.delivery&&window.__stressAudio.every(a=>a.paused||a.ended),{phase:before.playback.phase});return row;
}
function decorate(payload){return {...payload,profile:{...(payload.profile||{}),name:cases.profile_name}};}
let player, savedPromise, frozenSession;
function sanitizedSession(record){
  const copy=structuredClone(record);copy.profile.name=cases.profile_name;
  copy.evaluation={mode:evidence.mode,synthetic_audio:true,synthetic_speech_onsets:true,physical_microphone:false,voice_provider_calls:0,audio_latency_valid:false,harness:'creta-night-final',real_runtime_answers:config.live};
  for(const turn of copy.turns||[]){
    turn.synthetic_delivery_timestamps={ack_audio:turn.ack_audio??null,answer_audio:turn.answer_audio??null,delivery_done:turn.delivery_done??null};
    turn.ack_audio=null;turn.answer_audio=null;turn.delivery_done=null;
    turn.speech_end_basis='typed_or_synthetic_review';turn.input_source='caption_stress_review';
  }
  return copy;
}
async function saveSession(record){
  if(!record.ended)return {ok:true,deferred_until_ended:true};
  if(savedPromise)return savedPromise;
  frozenSession=sanitizedSession(record);evidence.final_player_session=structuredClone(record);evidence.submitted_session=frozenSession;
  savedPromise=json(`/api/demos/dm_41513908/run/session`,frozenSession).then(value=>{evidence.save_result=value;return value;});return savedPromise;
}
async function prepare(){
  const {mountPlayer}=await import('/web/player/player.js');
  player=mountPlayer($('#fixture'),bundle,{liveUrl:'/api/demos/dm_41513908/run/live',
    qa:body=>json('/api/demos/dm_41513908/run/qa',decorate(body)),
    pitch:body=>json('/api/demos/dm_41513908/run/pitch',decorate(body)),
    tts:async()=>{throw new Error('Voice API forbidden');},stt:async()=>{throw new Error('Voice API forbidden');},lead:async()=>{throw new Error('Lead submission forbidden');},saveSession});
  evidence.session_id=snap().session.id;log('player_mounted',{session_id:evidence.session_id,bundle_version:bundle.version});
}
async function answerWait(id, beforeCount) {
  await until(()=>{const s=snap();return s.session.turns.length>beforeCount&&s.waiting&&!s.pending&&!s.speaking;},id+' answer or clarification completed',50000);
  const state=snap();check(id+' waits for customer without automatic route return',state.waiting&&!state.speaking,{playback:state.playback});
  await sleep(config.live?700:80);check(id+' still waits',snap().waiting,{playback:snap().playback});closeLead();return state;
}
async function continueRoute(label) {
  closeLead();const before=snap(),origin=before.origin;
  button('Continue demo').click();
  const bridge=bundle.fillers?.back_to_demo?.text||"Let's return to where we paused.";
  await until(()=>{const s=snap();return !s.origin&&!s.pending&&s.speaking?.text!==bridge&&['route','closing'].includes(s.playback.phase)&&(s.speaking||s.waiting);},label+' returned past the owned bridge',35000);
  const after=snap();
  if(origin?.phase==='route'){
    const next=origin.index+(origin.checkin?1:0),closed=next>=before.session.slides.length;
    check(label+' resumes its owned route point',closed?after.playback.phase==='closing':after.playback.phase==='route'&&after.playback.index===next,{origin,after:after.playback});
  }
  log('explicit_continue',{label,origin,after:after.playback});
}
async function reachCheckin(label){
  await until(()=>snap().waiting&&!snap().speaking&&!snap().pending,label+' reviewed check-in',60000);
  const choices=[...document.querySelectorAll('.pl-chips button')].map(x=>x.textContent.trim());
  const choice=['That settles it','Yes, continue','Continue'].find(x=>choices.includes(x));
  if(choice){button(choice).click();log('reviewed_checkin_choice',{label,choice});}
}
async function askCase(item){
  $('#status').textContent=`${item.id} · ${item.purpose}`;const before=snap(),count=before.session.turns.length;
  submit(item.text);
  await until(()=>snap().session.turns.length>count,item.id+' question accepted');
  if(item.cancel_after_ms){await sleep(item.cancel_after_ms);await onset(item.id+' rapid replacement');return;}
  if(item.interrupt_caption){
    await until(()=>snap().activeTurn?.qa_done&&snap().speaking,item.id+' response caption begins');
    await sleep(180);await onset(item.id+' answer interruption');
    check(item.id+' interrupted answer does not auto-complete',snap().waiting&&!snap().activeTurn,{turn:snap().session.turns.at(-1)});return;
  }
  const after=await answerWait(item.id,count);
  if(item.expect_clarification)check(item.id+' asks missing inputs',after.session.turns.at(-1).response_kind==='clarification');
  if(!item.expect_clarification&&after.session.turns.at(-1).response_kind==='clarification'){
    log('unexpected_clarification',{id:item.id,caption:$('.pl-cap .txt').textContent});
    button('Skip this question',false)?.click();await sleep(80);
  }
  if(item.id==='s05'){
    const old=evidence.wire.find(x=>x.direction==='out'&&x.type==='turn.ask'&&x.question===cases.questions.find(q=>q.id==='s04').text);
    const current=snap();inject({type:'turn.result',turn_id:old?.turn_id,utterance_id:'stale-synthetic',answer:{answered:true,answer:'STALE ANSWER MUST NOT APPEAR',route:'stay'}});await sleep(100);
    check('Old result cannot replace newer answer',!$('.pl-thread,.pl-drawer .body')?.textContent.includes('STALE ANSWER MUST NOT APPEAR')&&snap().context.slide===current.context.slide);
  }
}
async function naturalFinish(){
  if(button('Continue demo',false))await continueRoute('final question');
  const expected=[...snap().session.slides];log('natural_completion_expected',{slides:expected});
  for(let i=0;i<40;i++){
    await until(()=>snap().waiting&&!snap().speaking&&!snap().pending,'next reviewed route choice',60000);closeLead();
    if(button('Not yet',false)){button('Not yet').click();break;}
    const choice=['That settles it','Yes, continue','Continue demo','Continue'].find(label=>button(label,false));
    if(!choice)throw new Error('Unknown route wait; no automatic answer invented');
    button(choice).click();log('natural_route_choice',{choice});
  }
  await until(()=>$('.pl-handoff.open'),'natural recap',45000);
  const state=snap(),visited=new Set(state.session.slides_visited.map(x=>x.slide_id));
  check('Natural route reaches its closing',state.playback.phase==='closing'&&expected.every(id=>visited.has(id)),{expected,visited:[...visited]});
  check('Recap ends synthetic capture and has no lead',window.__stressTracks.every(t=>t.readyState==='ended')&&!state.session.leads.length);
  check('Recap never claims Listening after end',$('.pl-status').textContent.includes('Demo complete'));
}
async function finishEvidence(status){
  if(!savedPromise&&snap()){button('Stop and see the summary',false)?.click();await sleep(100);}
  if(savedPromise)try{await savedPromise;}catch(error){evidence.issues.push({kind:'session_save',message:error.message});}
  if(evidence.session_id&&savedPromise){
    const untilAt=Date.now()+90000;
    while(Date.now()<untilAt){
      try{const record=await json(`/api/demos/dm_41513908/sessions/${evidence.session_id}`);if(record.summary){evidence.persisted_session=record;break;}}catch(error){log('session_read_wait',{message:error.message});}
      await sleep(1500);
    }
    check('Exactly the same session has a readable summary',evidence.persisted_session?.id===evidence.session_id&&!!evidence.persisted_session?.summary&&!evidence.persisted_session?.summary?.error);
  }
  evidence.status=status;evidence.finished_at=Date.now();evidence.end_snapshot=snap();
  evidence.response_counts={live_api:evidence.responses.filter(x=>x.provenance==='live_api_result').length,offline_synthetic:evidence.responses.filter(x=>x.provenance==='offline_synthetic').length,injected_stale:evidence.responses.filter(x=>x.provenance==='injected_stale_test').length};
  await json('/stress/final',evidence);
  const {renderSummary}=await import('/web/studio/sessions.js');
  const title=document.createElement('h2');title.textContent='Session evidence · '+(config.live?'live reasoning, synthetic media':'OFFLINE SYNTHETIC FIXTURE');$('#report').append(title);
  if(evidence.persisted_session)$('#report').append(renderSummary(evidence.persisted_session,{full:true}));
  const issue=document.createElement('pre');issue.id='issues';issue.textContent=JSON.stringify({status,checks:evidence.checks.length,failed:evidence.checks.filter(x=>!x.passed),issues:evidence.issues},null,2);$('#report').append(issue);
  $('#status').textContent=`${status} · ${evidence.checks.filter(x=>x.passed).length}/${evidence.checks.length} checks · one session ${evidence.session_id}`;
}
async function run(){
  $('#start').disabled=true;
  try{
    await json('/stress/start',{});evidence.started_at=Date.now();await prepare();button('Explore with me').click();
    await until(()=>$('.pl-intake.open'),'intake');submit(cases.intake,true);
    await until(()=>!$('.pl-intake.open'),'intake accepted');$('.pl-mic-row .mic').click();await until(()=>snap().mic_ready,'synthetic capture ready');
    await until(()=>snap().playback.phase==='overview'&&snap().speaking,'concurrent overview');
    await onset('overview interruption 1');await continueOpening();
    await until(()=>snap().playback.phase==='overview'&&snap().speaking,'overview resumes');await onset('overview interruption 2');await continueOpening();
    await until(()=>snap().playback.phase==='route'&&snap().speaking,'reviewed route starts',45000);
    await onset('narration interruption');
    for(const item of cases.questions){
      if(item.id==='s10'){
        submit(cases.priority_correction);await until(()=>snap().waiting&&!snap().speaking,'priority correction acknowledged');
        check('Explicit priority stays in recap needs',snap().session.profile.stated_needs.includes(cases.priority_correction));
      }
      await askCase(item);
      if(['s03','s05','s09'].includes(item.id)&&button('Continue demo',false)){
        await continueRoute(item.id);await reachCheckin(item.id);await until(()=>snap().speaking||snap().waiting,'next boundary');await onset(item.id+' route interruption');
      }
    }
    await naturalFinish();await finishEvidence(evidence.issues.length?'completed_with_issues':'completed');
  }catch(error){evidence.issues.push({kind:'fatal',message:error.message,stack:error.stack});log('failed',{message:error.message});await finishEvidence('failed_preserved');}
}
async function continueOpening(){button('Continue demo').click();await sleep(50);}
window.addEventListener('error',event=>evidence.issues.push({kind:'browser_error',message:event.message}));
window.addEventListener('unhandledrejection',event=>evidence.issues.push({kind:'unhandled_rejection',message:String(event.reason)}));
$('#start').disabled=!!config.run.started;$('#start').onclick=run;
$('#status').textContent=config.run.started?'This one-session run was already started. Reload cannot repeat it.':config.live?'LIVE READY · root starts once · $3.50 dispatch stop / $5 total allowance':'OFFLINE READY · synthetic responses only · zero paid calls';
window.__stressEvidence=evidence;
// Root-controlled command is only another explicit activation of the same
// button handler. No command exists on a fresh run, and the server latch wins.
let consumedCommand=false;
const commandPoll=setInterval(async()=>{
  if(consumedCommand||evidence.started_at)return;
  try{const state=await json('/stress/config');if(state.run.command_requested&&!state.run.started){consumedCommand=true;clearInterval(commandPoll);run();}}
  catch(error){$('#status').textContent='Control connection unavailable; no session started.';}
},750);

// Real capture/transport/player functions with deterministic audio and time.
// No microphone, server, stored demo or provider call; no acoustic-quality claim.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import net from 'node:net';
import tls from 'node:tls';
net.connect = net.createConnection = net.Socket.prototype.connect = tls.connect = () => { throw Error('Sockets blocked'); };
globalThis.fetch = () => { throw Error('Network blocked'); };
const read = path => fs.readFileSync(new URL('../' + path, import.meta.url), 'utf8');
const liveSource = read('web/player/live-voice.js'), playerSource = read('web/player/player.js');
const part = (source, begin, end) => source.slice(source.indexOf(begin), source.indexOf(end, source.indexOf(begin)));
let count = 0;
async function check(name, run) { await run(); count++; console.log('PASS', name); }
const flush = async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); };
function fixture() {
  let now = 1000, next = 0; const timers = new Map(), holds = [], ends = [], finals = [], onsets = [], sends = [];
  const clock = { now: () => now, set(fn, ms) { const id = ++next; timers.set(id, {fn, at: now + ms}); return id; }, clear(id) { timers.delete(id); } };
  const sandbox = { URL, atob, btoa, Float32Array, Uint8Array, Date: {now: clock.now}, setTimeout: clock.set, clearTimeout: clock.clear };
  const {LiveVoiceClient, meaningfulTranscript} = vm.runInNewContext(liveSource.replace(/^export /gm, '') + '\n({LiveVoiceClient,meaningfulTranscript})', sandbox);
  const qualifier = vm.runInNewContext(part(playerSource, 'function playbackCommand(', 'function defaultVoiceMode(') + '\n({qualifiesCustomerSpeech,playbackCommand})', {meaningfulTranscript});
  const client = new LiveVoiceClient({url:'/unused', sessionId:'test', qualifyInput: text => qualifier.qualifiesCustomerSpeech(text, {terms:['warranty','boot']}), shouldInterrupt: text => !qualifier.playbackCommand(text),
    onSpeechHold: e => holds.push(e), onSpeechHoldEnd: e => ends.push(e), onTranscript: e => { if(e.final) finals.push(e); }, onSpeechStart: e => onsets.push(e)});
  client.mic = true; client.inputGeneration = 1; client.localOnsetArmed = true;
  client.socket = {readyState:1,send: text => sends.push(JSON.parse(text))};
  client.outputContext = {state:'running', currentTime:7.125, async suspend(){this.state='suspended';}, async resume(){this.state='running';}};
  client.gain = {gain:{value:1}};
  const frame = (speechLike, rms=.12) => client.observeSpeechFrame({speechLike, rms}, .018);
  const emit = (text, final=false, id='one', generation=1) => client.receive({type:final?'transcript.final':'transcript.partial',text,input_id:id,input_generation:generation});
  return {client, holds, ends, finals, onsets, sends, timers, clock, frame, emit, sandbox,
    async advance(ms) { const end = now + ms; for (;;) { const entry = [...timers].filter(([,job]) => job.at <= end).sort((a,b) => a[1].at-b[1].at)[0]; if(!entry)break; now=entry[1].at;timers.delete(entry[0]);entry[1].fn();await flush(); }now=end;await flush(); },
    close(){client.endSpeechHold('test_done',false);} };
}
let Capture; const packets=[];
vm.runInNewContext(read('web/player/voice-worklet.js'), { AudioWorkletProcessor:class {constructor(){this.port={postMessage:p=>packets.push(p)};}}, sampleRate:16000, registerProcessor:(_, C)=>{Capture=C;} });
function packet(samples) { packets.length=0; const capture=new Capture();capture.process([[Float32Array.from(samples)]]);return packets[0]; }
const voiced = packet(Array.from({length:320}, (_,i)=>.15*Math.sin(2*Math.PI*200*i/16000)));
await check('worklet marks a structured voiced frame, not mere loudness', () => {
  assert(voiced.speechLike); assert.equal(packet(Array(320).fill(.3)).speechLike,false);
  assert.equal(packet(Array.from({length:320},(_,i)=>i===15?.9:0)).speechLike,false);
});
await check('cup transient and short voiced throat-like burst cannot take playback', async()=>{
  const f=fixture();f.frame(false,.9);for(let i=0;i<5;i++){f.frame(true);await f.advance(20);}for(let i=0;i<10;i++)f.frame(false,0);
  assert.equal(f.holds.length,0);assert.equal(f.client.outputContext.state,'running');f.close();
});
await check('sustained voiced input pauses locally at160ms before any transcript or server turn', async()=>{
  const f=fixture();for(let i=0;i<8;i++){f.frame(voiced.speechLike,voiced.rms);await f.advance(20);}
  assert.equal(f.holds.length,1);assert.equal(f.client.outputContext.state,'suspended');assert.equal(f.client.gain.gain.value,0);
  assert.equal(f.finals.length,0);assert.equal(f.onsets.length,0);assert.equal(f.sends.length,0);assert.equal(f.clock.now(),1160);f.close();
});
await check('raw server VAD alone never pauses audio',()=>{
  const f=fixture();f.client.receive({type:'input.speech_start',input_generation:1});assert.equal(f.holds.length,0);f.close();
});
await check('qualified interim pauses immediately and does not ask or cancel server work',()=>{
  const f=fixture();f.emit('What is the warranty');assert.equal(f.holds.length,1);assert.equal(f.client.outputContext.state,'suspended');assert.equal(f.sends.length,0);assert.equal(f.finals.length,0);f.close();
});
await check('irrelevant TV interim and known noise annotations cannot independently hold output',()=>{
  const f=fixture();for(const text of ['Breaking news and the weather forecast','Ahem?','[clears throat]',"It's"])f.emit(text);
  assert.equal(f.holds.length,0);f.close();
});
await check('rejected final releases provisional speech at the exact paused sample',async()=>{
  const f=fixture();for(let i=0;i<8;i++)f.frame(true);const at=f.client.outputContext.currentTime;f.emit('[clears throat]',true);await flush();
  assert.equal(f.client.outputContext.state,'running');assert.equal(f.client.outputContext.currentTime,at);assert.equal(f.ends.at(-1).reason,'rejected');assert.equal(f.onsets.length,0);assert.equal(f.finals.length,0);f.close();
});
await check('silence without a final releases a local hold instead of freezing the tour',async()=>{
  const f=fixture();for(let i=0;i<8;i++)f.frame(true);await f.advance(1401);assert.equal(f.client.inputHold,null);assert.equal(f.client.outputContext.state,'running');assert.equal(f.timers.size,0);f.close();
});
await check('a qualifying partial extends the listening window until a final arrives',async()=>{
  const f=fixture();f.emit('What is the warranty');await f.advance(2000);f.emit('What is the warranty and boot');await f.advance(1000);assert(f.client.inputHold);
  f.emit('What is the warranty and boot space?',true);assert.equal(f.onsets.length,1);assert.equal(f.finals.length,1);assert.equal(f.ends.at(-1).resume,false);assert.equal(f.timers.size,0);f.close();
});
await check('local tail frames cannot shorten a qualified partials final-text grace',async()=>{
  const f=fixture();f.emit('What is the warranty');for(let i=0;i<8;i++)f.frame(true);await f.advance(1500);assert(f.client.inputHold);await f.advance(901);assert.equal(f.client.inputHold,null);f.close();
});
await check('duplicate/stale final still produces one semantic interruption',()=>{
  const f=fixture();f.emit('Warranty',false);f.emit('Warranty?',true);f.emit('Warranty?',true);f.emit('Warranty?',true,'old',0);
  assert.equal(f.onsets.length,1);assert.equal(f.finals.length,1);f.close();
});
await check('Continue remains a local command and resumes provisional media without a QA turn',async()=>{
  const f=fixture();for(let i=0;i<8;i++)f.frame(true);f.emit('Continue',true);await flush();assert.equal(f.onsets.length,0);assert.equal(f.finals[0].text,'Continue');assert.equal(f.client.outputContext.state,'running');f.close();
});
await check('superseding control abandons a hold without reviving the old audio',()=>{
  const f=fixture();f.emit('Warranty');f.client.interrupt();assert.equal(f.ends.at(-1).resume,false);assert.equal(f.timers.size,0);assert.equal(f.client.inputHold,null);f.close();
});
await check('explicitly paused or ended player cannot acquire a listening hold',()=>{
  const f=fixture();f.client.canHold=()=>false;f.emit('What is the warranty');for(let i=0;i<10;i++)f.frame(true);assert.equal(f.holds.length,0);f.close();
});
await check('continuous background speech has a hard bound and cannot immediately reacquire hold',async()=>{
  const f=fixture();for(let i=0;i<20;i++){f.emit('Warranty');await f.advance(1000);}assert.equal(f.ends.at(-1).reason,'deadline');assert.equal(f.client.inputHold,null);
  f.emit('Warranty');assert.equal(f.client.inputHold,null);f.close();
});
await check('recognized question progress beyond20s keeps narration paused until the final',async()=>{
  const f=fixture();for(let i=0;i<30;i++){f.emit('What is the warranty '+Array(i+1).fill('and').join(' '));await f.advance(1000);}
  assert(f.client.inputHold);assert.equal(f.client.outputContext.state,'suspended');assert.equal(f.ends.length,0);
  f.emit('What is the warranty?',true);assert.equal(f.finals.length,1);assert.equal(f.onsets[0].provisional_detected_at,1000);assert.equal(f.timers.size,0);f.close();
});
await check('a late output resume promise cannot unmute a newer listening hold',async()=>{
  const f=fixture();let resolve;f.client.outputContext.resume=()=>new Promise(done=>{resolve=()=>{f.client.outputContext.state='running';done();};});
  f.emit('Warranty');f.emit('[cough]',true);f.emit('What is the warranty');resolve();await flush();
  assert.equal(f.client.outputContext.state,'suspended');assert.equal(f.client.gain.gain.value,0);f.close();
});
await check('microphone disconnect releases a provisional hold and its watchdogs',async()=>{
  const f=fixture();f.emit('Warranty');f.client.stopCapture();await flush();assert.equal(f.client.inputHold,null);assert.equal(f.client.outputContext.state,'running');assert.equal(f.timers.size,0);f.close();
});
await check('mute state survives temporary listening and release',async()=>{
  const f=fixture();f.client.setMuted(true);f.emit('Warranty');f.emit('[cough]',true);await flush();assert.equal(f.client.gain.gain.value,0);f.close();
});
function playerFixture() {
  let pauses=0,plays=0,armed=0,now=1000;
  const audio={currentTime:13.75,paused:false,pause(){pauses++;this.paused=true;},play(){plays++;this.paused=false;return Promise.resolve();}};
  const S={run:4,audio,speaking:{startedAt:500},postAnswerListen:{timer:9}};
  const el={status:{className:'pl-status speaking'},statusTxt:{textContent:'Speaking'},live:{textContent:''},stage:{getAnimations:()=>[]},film:{paused:true}};
  const code=part(playerSource,'  function beginSpeechHold(', '  // Unlock output, connect');
  const api=vm.runInNewContext(code+'\n({beginSpeechHold,finishSpeechHold,awaitSpeechHold})',{S,el,root:{classList:{contains:()=>false}},Date:{now:()=>now},clearTimeout(){},setStatus(){},armPostAnswerListen(){armed++;}});
  return {S,audio,el,api,stats:()=>({pauses,plays,armed}),advance:ms=>{now+=ms;}};
}
await check('actual player pauses recorded audio synchronously without seeking or cancelling its owner',()=>{
  const f=playerFixture();f.api.beginSpeechHold({});assert(f.audio.paused);assert.equal(f.audio.currentTime,13.75);assert.equal(f.S.run,4);assert.equal(f.S.postAnswerListen.timer,null);f.api.finishSpeechHold({resume:false});
});
await check('rejected sound resumes exact recorded position and retains the three-second reply owner',async()=>{
  const f=playerFixture();f.api.beginSpeechHold({});const promise=f.api.awaitSpeechHold(4);f.advance(700);f.api.finishSpeechHold({resume:true});assert(await promise);assert.equal(f.audio.currentTime,13.75);assert(!f.audio.paused);assert.equal(f.S.speaking.startedAt,1200);assert.equal(f.stats().armed,1);
});
await check('committed question or newer run cannot auto-resume recorded narration',async()=>{
  for(const newer of [false,true]){const f=playerFixture();f.api.beginSpeechHold({});const promise=f.api.awaitSpeechHold(4);if(newer)f.S.run++;f.api.finishSpeechHold({resume:newer});assert.equal(await promise,false);assert(f.audio.paused);assert.equal(f.stats().plays,0);}
});
for(const browser of [false,true]) for(const cancel of [false,true]) {
  await check(`${browser?'browser voice':'readable caption'} deadline pauses during listening and ${cancel?'cannot revive after cancellation':'retains its remaining time'}`,async()=>{
    const f=fixture(), state={run:1,ttsToken:0}, logs=[];
    const code=part(playerSource,'  function captionOnly(', '  // Use a recorded URL first');
    const api=vm.runInNewContext(code+'\n({captionOnly,speakBrowser})',{
      S:state,Date:{now:f.clock.now},setTimeout:f.clock.set,clearTimeout:f.clock.clear,
      wordsOf:text=>text.split(' ').length,setStatus(){},logHeard:(sp,complete)=>logs.push(complete),
      SpeechSynthesisUtterance:class{constructor(text){this.text=text;}},speechSynthesis:{speak(){}},browserVoice:()=>null,LANG:'en-IN',firstAudio(){},
    });
    let complete=null; const promise=(browser?api.speakBrowser('Some words',1):api.captionOnly('Some words',1)).then(value=>{complete=value;});
    await f.advance(200);const resume=state.speaking.pauseDeadline();await f.advance(10000);assert.equal(complete,null);assert.equal(logs.length,0);
    if(cancel){state.cancelVoice();await flush();assert.equal(complete,false);resume();await f.advance(12000);assert.equal(logs.length,1);assert.equal(logs[0],false);}
    else{resume();await f.advance(500);assert.equal(complete,null);await f.advance(12000);assert.equal(complete,true);assert.equal(logs.length,1);}
    await promise;f.close();
  });
}
console.log(`Immediate speech hold: ${count}/${count} passed (synthetic signals; physical speaker/noise quality unverified)`);

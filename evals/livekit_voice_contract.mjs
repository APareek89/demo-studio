// Offline SDK/device doubles. No microphone, network or paid provider calls.
import assert from "node:assert/strict";
import fs from "node:fs";
import { createHash } from "node:crypto";
const path = name => new URL(`../${name}`, import.meta.url);
const uri = source => "data:text/javascript;base64," + Buffer.from(source).toString("base64");
const live = uri(fs.readFileSync(path("web/player/live-voice.js"), "utf8"));
const source = fs.readFileSync(path("web/player/livekit-voice.js"), "utf8");
const module = source.replace('from "/web/player/live-voice.js"', `from "${live}"`).replace('import * as LiveKit from "/web/vendor/livekit-client-2.22.3.esm.mjs";', "const LiveKit = {};");
const { LiveKitVoiceClient, LiveKitSocket, FragmentReader, fragmentMessage, LIVEKIT_TOPIC } = await import(uri(module));
let passes = 0;
function check(name, value) { assert.ok(value, name); passes++; console.log("PASS", name); }
const tick = () => new Promise(resolve => setTimeout(resolve, 0));
const settle = async () => { for (let i = 0; i < 5; i++) await tick(); };
const decode = packets => {
  let result; const reader = new FragmentReader({ onMessage: raw => { result = JSON.parse(raw); }, onFailure: error => { throw error; } });
  for (const packet of packets) reader.add(packet); reader.close(); return result;
};
const sample = JSON.stringify({ type: "turn.result", answer: "फीचर " + "A".repeat(19000) });
const chunks = fragmentMessage(sample, "utf8");
check("large UTF-8 messages round-trip with bounded wire packets", chunks.length === 3 && chunks.every(p => p.length <= 12288) && decode(chunks).answer === JSON.parse(sample).answer);
check("oversize outgoing messages and invalid ids are rejected", (() => { try { fragmentMessage("a".repeat(1024001), "big"); return false; } catch {} try { fragmentMessage("{}", "../bad"); return false; } catch {} return true; })());
let received = 0; const reader = new FragmentReader({ onMessage: () => { received++; }, onFailure: () => {} });
for (const packet of chunks) reader.add(packet); for (const packet of chunks) reader.add(packet);
check("completed reliable-message replay does not repeat an answer", received === 1); reader.close();
function rejected(packets) { const r = new FragmentReader({ onMessage() {}, onFailure() {} }); try { packets.forEach(p => r.add(p)); return false; } catch { return true; } finally { r.close(); } }
check("out-of-order and duplicate partial messages fail closed", rejected([chunks[1]]) && rejected([chunks[0], chunks[0]]));
const wire = obj => new TextEncoder().encode(JSON.stringify(obj));
check("invalid base64 and excessive part counts fail closed", rejected([wire({ v:1,id:"x",part:0,parts:1,payload:"!" })]) && rejected([wire({v:1,id:"x",part:0,parts:129,payload:"e30="})]));
check("inflight assembly is bounded to four messages", rejected(["a","b","c","d","e"].map(id => fragmentMessage(sample,id)[0])));
let clock = 0; const timed = new FragmentReader({ now:()=>clock, onMessage(){},onFailure(){} }); timed.add(chunks[0]); clock = 10001;
let timedOut = false; try { timed.add(chunks[1]); } catch { timedOut=true; } finally { timed.close(); }
check("expired assembly cannot deliver an old turn", timedOut);
check("malformed UTF-8 and invalid JSON cannot enter runtime", rejected([wire({v:1,id:"bad",part:0,parts:1,payload:"/w=="})]) && rejected([wire({v:1,id:"bad",part:0,parts:1,payload:"bm90LWpzb24="})]));

class Node { connect() {} disconnect() { this.disconnected = true; } }
class AudioSource extends Node { start() { this.started = true; } stop() { this.stopped = true; } }
class Context {
  static sources=[];
  constructor(){ this.currentTime=0;this.state="running";this.destination={};this.audioWorklet={addModule:async()=>{}}; }
  async resume(){this.state="running";} async suspend(){this.state="suspended";} async close(){this.state="closed";}
  createGain(){return Object.assign(new Node(),{gain:{value:1}});} createMediaStreamSource(){return new Node();}
  createBuffer(_,samples,rate){return{duration:samples/rate,copyToChannel(){}};} createBufferSource(){const s=new AudioSource();Context.sources.push(s);return s;}
}
class Worklet extends Node { constructor(){super();this.port={};} }
class Track { constructor(mediaStreamTrack){this.mediaStreamTrack=mediaStreamTrack;} }
const events={DataReceived:"data",Disconnected:"disconnected",Reconnecting:"reconnecting",SignalReconnecting:"signalReconnecting",ParticipantConnected:"participant",ParticipantDisconnected:"participantLeft"};
class Room {
  static instances=[]; static publishWait=null; static readyWait=null; static nextSession=null;
  constructor(options){this.options=options;this.sessionId=Room.nextSession;this.handlers=new Map();this.remoteParticipants=new Map([["agent",{identity:"agent"}]]);this.data=[];this.messages=[];this.tracks=[];this.unpublished=[];this.order=[];Room.instances.push(this);
    this.inbound = new FragmentReader({onMessage:raw=>{const event=JSON.parse(raw);this.messages.push(event);this.order.push(event.type);if(event.type==="session.start")queueMicrotask(()=>this.reply({type:"session.ready",session_id:event.session_id}));},onFailure:error=>{throw error;}});
    this.localParticipant={publishData:async(packet,options)=>{this.data.push({packet,options});this.inbound.add(packet);},publishTrack:async(track,options)=>{this.order.push("publishTrack");this.tracks.push({track,options});if(Room.publishWait)await Room.publishWait;return{};},unpublishTrack:async(track,stop)=>{this.unpublished.push({track,stop});}};
  }
  on(name,fn){const set=this.handlers.get(name)||new Set();set.add(fn);this.handlers.set(name,set);return this;}
  off(name,fn){this.handlers.get(name)?.delete(fn);return this;}
  emit(name,...args){for(const fn of this.handlers.get(name)||[])fn(...args);}
  async connect(url,token,options){this.connection={url,token,options};const send=()=>this.reply({type:"trial.ready",session_id:this.sessionId});if(Room.readyWait)Room.readyWait.then(send);else queueMicrotask(send);}
  async disconnect(){this.disconnected=true;this.inbound.close();this.emit(events.Disconnected);}
  reply(event,{identity="agent",topic=LIVEKIT_TOPIC,kind=0}={}){for(const packet of fragmentMessage(JSON.stringify(event),`reply_${++this.seq|| (this.seq=1)}`))this.emit(events.DataReceived,packet,{identity},kind,topic);}
}
const sdk={Room,RoomEvent:events,LocalAudioTrack:Track,Track:{Source:{Microphone:"microphone"}},DataPacket_Kind:{RELIABLE:0}};
let captures=0,requests=[];const media=[];
const env={location:{href:"http://127.0.0.1:8912/"},atob,AudioContext:Context,AudioWorkletNode:Worklet,navigator:{mediaDevices:{getUserMedia:async()=>{captures++;const track={readyState:"live",stop(){this.readyState="ended";}};media.push(track);return{getTracks:()=>[track],getAudioTracks:()=>[track]};}}},fetch:async(url,options)=>{requests.push({url,options});const sessionId=JSON.parse(options.body).session_id;Room.nextSession=sessionId;return{ok:true,json:async()=>({url:"ws://127.0.0.1:7880",token:"mock-token",room:"room",identity:"viewer",agent_identity:"agent",session_id:sessionId,transport:"livekit-trial"})};}};
const errors=[],transcripts=[];const client=new LiveKitVoiceClient({url:"/api/demos/dm_test/run/live",sessionId:"trial_1",env,onError:e=>errors.push(e),onTranscript:e=>transcripts.push(e)},{sdk});
await client.connect();const room=Room.instances.at(-1);
check("trial token endpoint is same-origin and session-bound", requests[0].url==="http://127.0.0.1:8912/api/demos/dm_test/run/livekit/token" && JSON.parse(requests[0].options.body).session_id==="trial_1");
check("text trial joins RTC without microphone or subscribed second voice", captures===0 && room.connection.options.autoSubscribe===false && room.connection.options.rtcConfig.iceServers.length===0);
check("runtime controls use reliable data addressed only to the worker", room.data.every(d=>d.options.reliable&&d.options.topic===LIVEKIT_TOPIC&&JSON.stringify(d.options.destinationIdentities)==='["agent"]'));
await Promise.all([client.startCapture(),client.startCapture()]);await settle();
check("one physical capture feeds both RTC and local onset detector", captures===1 && room.tracks.length===1 && room.tracks[0].track.mediaStreamTrack===client.stream.getAudioTracks()[0] && !!client.worklet);
check("microphone generation control precedes matching named RTC publication", room.order.indexOf("mic.set")<room.order.indexOf("publishTrack") && room.tracks[0].options.name===`demo-mic-${client.inputGeneration}` && room.tracks[0].options.source==="microphone");
room.reply({type:"mic.ready",session_id:"trial_1",input_generation:client.inputGeneration});
client.worklet.port.onmessage({data:{pcm:new Int16Array(320).buffer,rms:0.04,speechLike:true}});await settle();
check("PCM is never duplicated onto reliable control data", client.micReady && !room.messages.some(m=>m.type==="audio.input"));
for(let i=0;i<8;i++)client.worklet.port.onmessage({data:{pcm:new Int16Array(320).buffer,rms:0.04,speechLike:true}});
check("same worklet still pauses immediately before any final transcript", !!client.inputHold && transcripts.length===0);
const generation=client.inputGeneration;
room.reply({type:"transcript.final",input_generation:generation,text:"ahem",input_id:"noise"});
check("noise qualification and reversible hold recovery remain inherited", !client.inputHold && transcripts.length===0);
room.reply({type:"transcript.final",input_generation:generation,text:"Show the cabin",input_id:"q"},{identity:"other"});
room.reply({type:"transcript.final",input_generation:generation,text:"Show the cabin",input_id:"q"},{topic:"other"});
check("other participant or topic cannot inject customer input", transcripts.length===0);
room.reply({type:"transcript.final",input_generation:generation,text:"Show the cabin",input_id:"q"});
check("qualified RTC transcription enters the existing single semantic owner", transcripts.length===1 && transcripts[0].final);
client.socket.pingWorker();await settle();const pingDeadline=client.socket.pongDeadline;
room.reply({type:"trial.pong",session_id:"trial_1"},{identity:"other"});
check("only the exact worker can acknowledge runtime liveness", pingDeadline && client.socket.pongDeadline===pingDeadline && room.messages.some(e=>e.type==="trial.ping"));
room.reply({type:"trial.pong",session_id:"trial_1"});
check("matching worker pong clears the bounded liveness deadline", client.socket.pongDeadline===null);
client.stopCapture();await settle();
check("mic off stops physical track and unpublishes while retaining text transport", media[0].readyState==="ended" && room.unpublished.length>0 && client.ready && !client.mic);
await client.startCapture();await settle();const secondGeneration=client.inputGeneration;
room.reply({type:"transcript.final",input_generation:generation,text:"An old question",input_id:"old"});
check("reopened capture rejects transcripts from old microphone generation", captures===2 && secondGeneration>generation && transcripts.length===1 && room.tracks.at(-1).options.name===`demo-mic-${secondGeneration}`);
const answer=client.ask({question:"Where is the cabin?"});await settle();const turn=client.pending.turnId;
room.reply({type:"turn.result",turn_id:turn,utterance_id:"answer_audio",answer:{answered:true,answer:"Reviewed cabin",visual:{kind:"image",ref:"im_1"}}});
const result=await answer;
check("answer preserves image and deferred audio ownership before playback", result.visual.ref==="im_1" && result.runtime_utterance_id==="answer_audio" && !room.messages.some(m=>m.type==="delivery.request"));
const speech=client.speak(result.answer,{turnId:result.runtime_turn_id,utteranceId:result.runtime_utterance_id});await settle();
room.reply({type:"audio.chunk",turn_id:turn,utterance_id:"answer_audio",seq:0,audio:"AAAAAA==",sample_rate:24000,format:"pcm_s16le"});
check("RTC data output uses the existing single audio queue", Context.sources.length===1 && client.delivery.sources.size===1);
client.interrupt();check("local interruption stops PCM immediately without ending capture", Context.sources[0].stopped && await speech===false && client.mic);
const priorSources=Context.sources.length;room.reply({type:"audio.chunk",turn_id:turn,utterance_id:"answer_audio",seq:1,audio:"AAAAAA==",sample_rate:24000,format:"pcm_s16le"});
check("late audio cannot resurrect an interrupted utterance", Context.sources.length===priorSources);
const pending=client.ask({question:"Pending answer"}).catch(e=>e);await settle();room.emit(events.Reconnecting);const failed=await pending;
check("reconnect closes ownership instead of replaying an answered or pending turn", failed instanceof Error && client.socket.readyState===3 && !client.mic && room.disconnected && errors.some(e=>e.includes("LiveKit trial:")));
client.close();
check("destroy closes both contexts and all owned tracks", media.every(t=>t.readyState==="ended") && client.outputContext===null && client.captureContext===null);

let workerJoined;Room.readyWait=new Promise(resolve=>{workerJoined=resolve;});const handshake=new LiveKitVoiceClient({url:"/api/demos/dm_test/run/live",sessionId:"handshake",env},{sdk});const handshakeConnection=handshake.connect();await settle();const handshakeRoom=Room.instances.at(-1);
check("session start waits for the worker's participant visibility acknowledgement", !handshake.ready && !handshakeRoom.messages.some(e=>e.type==="session.start"));
handshakeRoom.reply({type:"trial.ready",session_id:"handshake"},{identity:"other"});await tick();
check("an unrelated participant cannot unlock worker readiness", !handshake.ready);
workerJoined();Room.readyWait=null;await handshakeConnection;
check("owned readiness starts one session without replay", handshake.ready && handshakeRoom.messages.filter(e=>e.type==="session.start").length===1);
handshakeRoom.reply({type:"trial.ready",session_id:"handshake"});await settle();
check("repeated worker readiness cannot reopen or replay the session", handshake.ready && handshakeRoom.messages.filter(e=>e.type==="session.start").length===1);handshake.close();
let earlyRelease;Room.readyWait=new Promise(resolve=>{earlyRelease=resolve;});const early=new LiveKitVoiceClient({url:"/api/demos/dm_test/run/live",sessionId:"early",env},{sdk});const earlyConnection=early.connect().catch(e=>e);await settle();const earlyRoom=Room.instances.at(-1);earlyRoom.reply({type:"session.ready",session_id:"early"});
check("runtime events cannot bypass the explicit worker readiness handshake", (await earlyConnection) instanceof Error && !early.ready && earlyRoom.disconnected);early.close();Room.readyWait=null;earlyRelease();await tick();
let abandonedRelease;Room.readyWait=new Promise(resolve=>{abandonedRelease=resolve;});const abandoned=new LiveKitVoiceClient({url:"/api/demos/dm_test/run/live",sessionId:"abandoned",env},{sdk});const abandonedConnection=abandoned.connect().catch(e=>e);await settle();const abandonedRoom=Room.instances.at(-1);abandoned.close();await abandonedConnection;Room.readyWait=null;abandonedRelease();await settle();
check("ending during worker readiness cannot open a late session", abandonedRoom.disconnected && !abandonedRoom.messages.some(e=>e.type==="session.start") && !abandoned.ready);

const race=new LiveKitVoiceClient({url:"/api/demos/dm_test/run/live",sessionId:"race",env},{sdk});await race.connect();const raceRoom=Room.instances.at(-1);let release;Room.publishWait=new Promise(r=>{release=r;});
await race.startCapture();await tick();race.stopCapture();release();Room.publishWait=null;await settle();
check("late RTC publication after mic-off is unbound and cannot survive", raceRoom.unpublished.some(p=>p.track===raceRoom.tracks[0].track) && !race.mic && media.at(-1).readyState==="ended");race.close();
const identity=new LiveKitVoiceClient({url:"/api/demos/dm_test/run/live",sessionId:"identity",env,onError(){}},{sdk});await identity.connect();Room.instances.at(-1).reply({type:"session.ready",session_id:"another"});
check("wrong session from even the assigned worker fails closed", identity.socket.readyState===3);identity.close();
const departed=new LiveKitVoiceClient({url:"/api/demos/dm_test/run/live",sessionId:"departed",env},{sdk});await departed.connect();const departureRoom=Room.instances.at(-1);departureRoom.emit(events.ParticipantDisconnected,{identity:"other"});
check("unrelated participant departure does not disrupt this runtime", departed.ready);
departureRoom.emit(events.ParticipantDisconnected,{identity:"agent"});
check("worker departure ends the live connection immediately", !departed.ready && departed.socket.readyState===3);departed.close();
let fulfill;const delayedEnv={...env,fetch:()=>new Promise(resolve=>{fulfill=resolve;})};const cancelled=new LiveKitVoiceClient({url:"/api/demos/dm_test/run/live",sessionId:"cancelled",env:delayedEnv},{sdk});const cancelledConnect=cancelled.connect().catch(e=>e);await tick();const roomsBefore=Room.instances.length;cancelled.close();fulfill({ok:true,json:async()=>({})});await cancelledConnect;await settle();
check("a late token after destroy cannot open a room", Room.instances.length===roomsBefore);
const invalid=new LiveKitVoiceClient({url:"/api/demos/dm_test/run/live",sessionId:"invalid",env:{...env,fetch:async()=>({ok:false})},onError:e=>errors.push(e)},{sdk});await invalid.connect().catch(()=>{});
check("disabled trial fails visibly and cannot instantiate legacy WebSocket", errors.some(e=>e.includes("trial is unavailable")) && invalid.socket===null);invalid.close();
const queuedClient={sessionId:"queue",onError(){}};const socket=new LiveKitSocket("ws://127.0.0.1:8912/api/demos/dm_test/run/live",{client:queuedClient,sdk,env});await settle();let publishResume;socket.room.localParticipant.publishData=()=>new Promise(r=>{publishResume=r;});socket.send(JSON.stringify({type:"blocked"}));await tick();socket.send(JSON.stringify({type:"should_not_replay"}));socket.close();publishResume();await settle();
check("queued controls are invalidated on disconnect", socket.readyState===3 && socket.bufferedAmount===0 && socket.queueCount===0);
const overloaded=new LiveKitSocket("ws://127.0.0.1:8912/api/demos/dm_test/run/live",{client:queuedClient,sdk,env});await settle();let freeQueue;overloaded.room.localParticipant.publishData=()=>new Promise(r=>{freeQueue=r;});overloaded.send(JSON.stringify({type:"blocked",text:"x".repeat(550000)}));await tick();overloaded.send(JSON.stringify({type:"overflow",text:"x".repeat(550000)}));freeQueue();await settle();
check("bounded send backlog fails closed rather than consuming unbounded memory", overloaded.readyState===3 && overloaded.queueCount===0);
const app=fs.readFileSync(path("web/app.js"),"utf8"),player=fs.readFileSync(path("web/player/player.js"),"utf8");
check("trial SDK is lazy-loaded behind only the exact URL flag", /get\("voice_transport"\) === "livekit"/.test(app) && app.includes('await import("/web/player/livekit-voice.js")') && !/^import .*livekit/m.test(app));
check("legacy bundles cannot silently claim trial transport", app.includes('if (!(bundle.runtime?.version >= 1))') && app.includes("The LiveKit trial requires a demo with the live runtime."));
check("normal and restarted players retain the existing client by default", player.includes("api.liveClientFactory || (options => new LiveVoiceClient(options))") && player.includes("createLive(); startLive(); renderProgress(); runIntake();"));
check("vendored SDK has fixed provenance and license with no application build", fs.existsSync(path("web/vendor/livekit-client-LICENSE.txt")) && JSON.parse(fs.readFileSync(path("web/vendor/livekit-client-provenance.json"),"utf8")).version==="2.22.3");
const provenance=JSON.parse(fs.readFileSync(path("web/vendor/livekit-client-provenance.json"),"utf8"));
check("vendored SDK and license exactly match recorded content hashes", Object.entries(provenance.files).every(([file,hash])=>createHash("sha256").update(fs.readFileSync(path(`web/vendor/${file}`))).digest("hex")===hash));
console.log(`livekit_voice_contract: ${passes}/${passes}`);

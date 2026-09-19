// Real API subscription behavior with a local fake EventSource; no browser/network.
import assert from 'node:assert/strict';
class FakeSource {
  static instances=[];
  constructor(url) { this.url=url;this.listeners={};FakeSource.instances.push(this); }
  addEventListener(type,fn) { this.listeners[type]=fn; }
  fire(type,data) { this.listeners[type]({data:JSON.stringify(data)}); }
  close() { this.closed=true; }
}
globalThis.EventSource=FakeSource;
const {api}=await import('../web/api.js');
const received=[];
const stop=api.subscribe('dm_12345678',(type,event)=>received.push([type,event]));
const stream=FakeSource.instances.at(-1);
assert.equal(stream.url,'/api/demos/dm_12345678/events');
stream.fire('hello',{seq:100,snapshot:{status:'align'}});
stream.fire('phase_done',{seq:90,phase:'build'});
assert.deepEqual(received.map(row=>row[0]),['hello']);
console.log('PASS fresh mount uses snapshot and ignores historical build redirect');
stream.fire('progress',{seq:101,message:'Current progress'});
stream.fire('progress',{seq:101,message:'Duplicate'});
assert.equal(received.length,2);
console.log('PASS duplicate reconnect delivery is suppressed');
stream.fire('hello',{seq:101,snapshot:{status:'reading'}});
stream.fire('status',{seq:102,status:'align'});
assert.equal(received.at(-1)[1].status,'align');
console.log('PASS reconnect baseline accepts subsequent live state');
stop();assert.equal(stream.closed,true);
const stopCursor=api.subscribe('dm_12345678',()=>{},7);
assert.equal(FakeSource.instances.at(-1).url,'/api/demos/dm_12345678/events?since=7');stopCursor();
console.log('PASS explicit cursor and subscription cleanup remain supported');
console.log('SSE client contracts: 4/4');

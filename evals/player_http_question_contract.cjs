// Actual HTTP fallback helper with virtual time and abortable/stubborn mocks.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(path.join(__dirname, '../web/player/player.js'), 'utf8');
const start = source.indexOf('  function questionHttp(');
const end = source.indexOf('  // Give fast answers', start);
assert(start >= 0 && end > start);
function fixture(qa) {
  const S = {}, timers = new Map(); let serial = 0;
  const question = vm.runInNewContext(source.slice(start, end) + '\nquestionHttp', {
    S, api: {qa}, AbortController, DOMException,
    setTimeout: (fn, ms) => { const id = ++serial; timers.set(id, {fn, ms}); return id; },
    clearTimeout: id => timers.delete(id),
  });
  return {S, timers, question};
}
const cases = [
  ['successful HTTP answer clears its deadline and ownership', async () => {
    let signal; const f = fixture((body, options) => {signal = options.signal; return Promise.resolve(body);});
    const value = await f.question({question:'fixture'});
    assert.equal(value.question, 'fixture'); assert.equal(f.timers.size, 0); assert.equal(f.S.httpQuestion, null); assert(!signal.aborted);
  }],
  ['timeout is exactly 16s and aborts even an uncooperative request', async () => {
    let signal, late; const f = fixture((_, options) => {signal=options.signal;return new Promise(r=>{late=r;});});
    const result = f.question({}).then(()=> 'fulfilled', error=>error.name);
    assert.equal([...f.timers.values()][0].ms, 16000); [...f.timers.values()][0].fn();
    assert.equal(await result, 'TimeoutError'); assert(signal.aborted); assert.equal(f.S.httpQuestion, null);
    late({answer:'obsolete'}); assert.equal(await result, 'TimeoutError'); assert.equal(f.timers.size, 0);
  }],
  ['run cancellation settles immediately and aborts the request', async () => {
    let signal; const f = fixture((_,options)=>{signal=options.signal;return new Promise(()=>{});});
    const result=f.question({}).catch(error=>error.name);f.S.httpQuestion.cancel();
    assert.equal(await result,'AbortError');assert(signal.aborted);assert.equal(f.timers.size,0);
  }],
  ['late old completion cannot clear the replacement request owner', async () => {
    const resolves=[];const f=fixture(()=>new Promise(r=>resolves.push(r)));
    const old=f.question({}).catch(error=>error.name);f.S.httpQuestion.cancel();
    const next=f.question({}), owner=f.S.httpQuestion;resolves[0]({answer:'old'});await old;
    assert.equal(f.S.httpQuestion,owner);resolves[1]({answer:'new'});assert.equal((await next).answer,'new');
  }],
  ['synchronous API failure clears timeout and retains the original error', async () => {
    const f=fixture(()=>{throw new Error('fixture failure');});
    await assert.rejects(f.question({}),/fixture failure/);assert.equal(f.timers.size,0);assert.equal(f.S.httpQuestion,null);
  }],
  ['HTTP API forwards optional AbortSignal without altering request body', async () => {
    const apiSource=fs.readFileSync(path.join(__dirname,'../web/api.js'),'utf8').replace(/export /g,'');let request;
    const api=vm.runInNewContext(apiSource+'\napi',{fetch:(url,options)=>{request={url,options};return Promise.resolve({ok:true,status:200,json:()=>({ok:true})});}});
    const abort=new AbortController();await api.post('/fixture',{question:'reviewed'},{signal:abort.signal});
    assert.equal(request.options.signal,abort.signal);assert.equal(request.options.body,'{"question":"reviewed"}');
    await api.post('/fixture',{});assert(!('signal' in request.options));
  }],
];
(async()=>{let passed=0;for(const [name, test] of cases){try{await test();passed++;console.log('PASS',name);}catch(error){console.error('FAIL',name,error);}}
console.log(`Player HTTP question contracts: ${passed}/${cases.length}; no network/providers`);process.exitCode=passed===cases.length?0:1;})();

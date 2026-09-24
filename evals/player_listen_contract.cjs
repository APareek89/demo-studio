// Execute the shipped player wait/timer functions; no DOM, browser, network or providers.
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), assert = require('node:assert/strict');
const source = fs.readFileSync(path.join(__dirname, '../web/player/player.js'), 'utf8');
function part(start, end) { const a = source.indexOf(start), b = source.indexOf(end, a); assert.ok(a >= 0 && b > a, `Missing implementation: ${start}`); return source.slice(a, b); }
function single(name) { const text = source.match(new RegExp('^  (?:async )?function ' + name + '\\([^\\n]+$', 'm'))?.[0]; assert.ok(text, `Missing single-line implementation: ${name}`); return text; }
const helpers = [single('preferTyping'), part('  function cancelPostAnswerListen()', '  function clearTimer()'), single('clearTimer'),
  part('  function waitFor(chips', '  // Speak a question and wait'), single('askAndListen'),
  part('  async function holdConversation(', '  // ---------- questions,')].join('\n');
const flush = async () => { for (let i = 0; i < 30; i++) await Promise.resolve(); };
function setup({leadOpen = false, drawerOpen = false} = {}) {
  let now = 0, next = 1; const timers = new Map(), calls = {resumed: [], questions: [], selected: [], listen: 0, stopped: 0, focus: []};
  const S = {run: 1, inputMode: 'voice', ended: false, listenId: 1};
  const classes = new Set(leadOpen ? ['open'] : []);
  const focus = name => ({focus: () => calls.focus.push(name)});
  const el = {lead: {classList: {contains: key => classes.has(key), remove: key => classes.delete(key)}}, leadName: focus('lead'),
    drawer: {classList: {contains: () => drawerOpen}}, q: focus('drawer'), reply: focus('reply'), hint: {}, cite: {}, timer: {replaceChildren() {}}, live: {}};
  const context = {S, el, live: null, bundle: {ctas: [{id: 'book', label: 'Book a test drive'}]}, POST_ANSWER_LISTEN_MS: 3000,
    setTimeout: (fn, ms) => {const id = next++; timers.set(id, {at: now + ms, fn}); return id;}, clearTimeout: id => timers.delete(id), clearInterval: id => timers.delete(id), Date: {now: () => now},
    setChips: list => {calls.choices = list;}, setStatus() {}, setVoiceMode: enabled => { S.voiceMode = !!enabled; S.inputMode = enabled ? "voice" : "typed"; }, stopListening: () => calls.stopped++, listenForTurn: () => calls.listen++,
    addMsg() {}, replyForTurn: text => ({value: 'answer', text}), speakPrompt: async () => true,
    resumeAfterQA: options => calls.resumed.push(options), ctaFlow: async id => calls.selected.push(id),
    handleQuestion: text => calls.questions.push(text), listenForQuestion: () => calls.questions.push('__listen')};
  const api = vm.runInNewContext(helpers + '\n({holdConversation,waitFor,resolveWait,askAndListen,preferTyping,cancelPostAnswerListen,armPostAnswerListen,dismissLeadPrompt})', context);
  async function tick(ms) { const end = now + ms; await flush(); for (;;) {const nextJob = [...timers].filter(([, job]) => job.at <= end).sort((a,b) => a[1].at-b[1].at)[0]; if (!nextJob) break; const [id, job] = nextJob; now=job.at; timers.delete(id); job.fn(); await flush();} now=end; await flush(); }
  return {S, api, calls, el, context, timers, tick};
}
async function run() {
  let count = 0;
  async function check(name, fn) { await fn(); count++; console.log('PASS ' + name); }
  await check('post-answer choices retain voice listening and focus a visible text field', async () => {const t=setup();t.api.holdConversation(1);await flush();assert.equal(t.calls.listen,1);assert.ok(t.calls.focus.includes('reply'));assert.deepEqual(Array.from(t.calls.choices,c=>c.value),['question','continue']);});
  await check('3000ms expires exactly once and annotates the owning turn', async () => {const t=setup(),turn={};const done=t.api.holdConversation(1,{turn});await t.tick(2999);assert.equal(t.calls.resumed.length,0);await t.tick(1);await done;assert.equal(t.calls.resumed.length,1);assert.equal(t.calls.resumed[0].automatic,true);assert.equal(turn.auto_resumed,true);assert.equal(turn.post_answer_listen_ms,3000);assert.equal(turn.auto_resumed_at,3000);await t.tick(9000);assert.equal(t.calls.resumed.length,1);});
  await check('typing one character cancels the silence timer without a question', async () => {const t=setup(),turn={};t.api.holdConversation(1,{turn});await t.tick(1200);t.api.preferTyping();await t.tick(30000);assert.equal(t.S.inputMode,'typed');assert.equal(t.calls.resumed.length,0);assert.equal(t.calls.questions.length,0);assert.equal(turn.auto_resumed,false);});
  await check('explicit Continue cancels timeout and resumes once as an explicit choice', async () => {const t=setup(),turn={};const done=t.api.holdConversation(1,{turn});t.api.resolveWait('continue');await done;await t.tick(10000);assert.equal(t.calls.resumed.length,1);assert.equal(t.calls.resumed[0].automatic,false);assert.equal(turn.auto_resumed,false);});
  await check('Ask another question cancels timeout and opens the question path', async () => {const t=setup();const done=t.api.holdConversation(1);await t.tick(1200);t.api.resolveWait('question');await done;await t.tick(10000);assert.deepEqual(t.calls.questions,['__listen']);assert.equal(t.calls.resumed.length,0);});
  await check('a proposed CTA is only selected by an explicit response', async () => {const t=setup();const done=t.api.holdConversation(1,{suggested:'book'});assert.ok(t.calls.choices.some(c=>c.value==='cta:book'));assert.equal(t.calls.selected.length,0);t.api.resolveWait('cta:book');await done;await t.tick(10000);assert.deepEqual(t.calls.selected,['book']);assert.equal(t.calls.resumed.length,0);});
  await check('clarification holds beyond 3s and only resolves a real reply', async () => {const t=setup();let settled=false;const done=t.api.askAndListen('Which version?',1).then(value=>{settled=true;return value;});await t.tick(30000);assert.equal(settled,false);assert.equal(t.calls.resumed.length,0);assert.equal(t.S.waiter.openAnswer,true);t.api.resolveWait({value:'answer',text:'The automatic.'});assert.equal(await done,'The automatic.');});
  await check('explicit solicitation opts out of the answer timer', async () => {const t=setup();t.api.holdConversation(1,{autoResume:false});await t.tick(30000);assert.ok(t.S.waiter);assert.equal(t.calls.resumed.length,0);});
  await check('a superseded run cannot resume from an obsolete deadline', async () => {const t=setup();t.api.holdConversation(1);t.S.run++;await t.tick(3000);assert.equal(t.calls.resumed.length,0);});
  await check('an ended session cannot resume from a pending deadline', async () => {const t=setup();t.api.holdConversation(1);t.S.ended=true;await t.tick(3000);assert.equal(t.calls.resumed.length,0);});
  await check('a new genuine wait cancels the previous answer deadline', async () => {const t=setup();t.api.holdConversation(1);t.api.waitFor([{label:'Choose',value:'chosen'}]);await t.tick(30000);assert.equal(t.calls.resumed.length,0);assert.equal(t.S.waiter.chips[0].value,'chosen');});
  await check('visible lead form holds indefinitely then dismiss starts a fresh 3s window', async () => {const t=setup({leadOpen:true}),turn={};t.api.holdConversation(1,{turn});await t.tick(10000);assert.equal(t.calls.resumed.length,0);assert.ok(t.calls.focus.includes('lead'));t.api.dismissLeadPrompt();await t.tick(2999);assert.equal(t.calls.resumed.length,0);await t.tick(1);assert.equal(t.calls.resumed.length,1);assert.equal(turn.auto_resumed_at,13000);});
  await check('a typed answer while contact form is open cannot later resurrect its timer', async () => {const t=setup({leadOpen:true});t.api.holdConversation(1);t.api.preferTyping();t.api.dismissLeadPrompt();await t.tick(30000);assert.equal(t.calls.resumed.length,0);});
  await check('legacy raw onset leaves the timer intact; qualified final takes the turn', async () => {
    const t=setup(),rec={start(){},abort(){},stop(){}};t.context.SR=function(){return rec;};t.context.LANG='en-IN';t.context.setMicUI=()=>{};t.context.qualifiesCustomerSpeech=text=>text==='What about the cabin?';t.context.speechTerms=[];
    const listen=vm.runInNewContext(part('  function listenBrowser(', '  // Stop or finish legacy listening')+'\nlistenBrowser',t.context);
    t.api.holdConversation(1);listen({},1);await t.tick(1200);rec.onspeechstart();assert.ok(t.S.postAnswerListen?.timer);
    const result=[{transcript:'What about the cabin?'}];result.isFinal=true;rec.onresult({results:[result]});assert.equal(t.S.postAnswerListen,null);rec.onend();await t.tick(4000);assert.equal(t.calls.resumed.length,0);
  });
  await check('automatic return speaks only a recorded bridge and restores the saved checkpoint', async () => {
    for (const audio of [null,'cached-audio']) {const S={run:1,playback:{phase:'route',line:5},conversationOrigin:{phase:'route',line:2}},spoken=[],resumed=[];
      const resume=vm.runInNewContext(part('  async function resumeAfterQA(', '  // Dispatch a saved phase')+'\nresumeAfterQA',{S,cur:{view:{highlight(){}}},bundle:{fillers:{back_to_demo:{audio}}},newRun:()=>++S.run,speakF:async(...args)=>{spoken.push(args);return true;},resumePlayback:(...args)=>resumed.push(args)});
      await resume({automatic:true});assert.equal(spoken.length,audio?1:0);assert.equal(resumed.length,1);assert.equal(resumed[0][0].line,2);assert.equal(S.conversationOrigin,null);
    }
  });
  await check('legacy question check-in is not spoken and does not wait', async () => {
    for (const text of ['Any questions?  ', 'Anything else？']) {
      const S = {run: 0, covered: new Set(), plan: [
        {slide: {id: 'old', lines: [{text: 'First proof.'}], checkin: {text, audio: 'old-question.wav'}}},
        {slide: {id: 'next', lines: [{text: 'Next proof.'}], checkin: {text: 'That completes this stop.', audio: 'statement.wav'}}}
      ]}, spoken = [], prefetched = [], played = [];
      let closed = 0;
      const play = vm.runInNewContext(part('  async function playFrom(', '  // Play a slide\'s deeper') + '\nplayFrom', {
        S, bundle: {}, el: {cite: {}}, newRun: () => ++S.run, applyUpcomingPlan: async () => true, renderProgress() {},
        prefetch: items => prefetched.push(...items), showSlideView: () => ({}),
        playLines: async slide => {played.push(slide.id); return true;}, speak: async text => {spoken.push(text); return true;},
        waitForLineQuestion: () => {throw Error('Legacy check-in waited');}, closeFlow: async () => {closed++;}
      });
      await play(0);
      assert.deepEqual(played, ['old', 'next']); assert.deepEqual(spoken, ['That completes this stop.']);
      assert.equal(S.checkin_skipped, 'legacy_question'); assert.equal(closed, 1);
      assert.equal(prefetched.some(item => item.text === text), false);
      assert.equal(S.plan[0].slide.checkin.text, text); assert.equal(S.plan[0].slide.checkin.audio, 'old-question.wav');
    }
  });
  console.log(`Player listen contracts: ${count}/${count}; real functions, virtual time, no browser/network/provider`);
}
run().catch(error=>{console.error(error);process.exitCode=1;});

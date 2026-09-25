// Free contract: pure helpers and the actual question-result coordinator.
// No app, storage, microphone, sockets or provider calls.
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const moduleSource = fs.readFileSync(new URL("../web/player/question-ack.js", import.meta.url), "utf8");
const { QUESTION_ACKNOWLEDGEMENTS: phrases, nextQuestionAcknowledgement: next } = await import("data:text/javascript;base64," + Buffer.from(moduleSource).toString("base64"));
const playerSource = fs.readFileSync(new URL("../web/player/player.js", import.meta.url), "utf8");
const coordinator = playerSource.slice(playerSource.indexOf("  async function questionResult("), playerSource.indexOf("  async function handleQuestion("));
let passed = 0;
function check(name, condition) { assert.ok(condition, name); passed++; console.log("PASS", name); }
function deferred() { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; }
const tick = () => new Promise(resolve => setTimeout(resolve, 0));

check("ten distinct short acknowledgements contain no automatic question praise", phrases.length === 10 && new Set(phrases).size === 10 && phrases.every(text => text.split(/\s+/).length <= 9 && !/good question|great question/i.test(text)));
const visit = {}, cycle = Array.from({ length: 30 }, () => next(visit).text);
check("every phrase plays once before repeating across three cycles", cycle.every((text, index) => text === phrases[index % 10]) && cycle.slice(1).every((text, index) => text !== cycle[index]));
check("new visits have independent rotation state", next({}).text === phrases[0] && next({ questionAckIndex: 4 }).text === phrases[4]);
check("only an exact matching published clip is reused", next({}, { legacy: { text: phrases[0], audio: "/media/fixture/ack.wav" } }).audio === "/media/fixture/ack.wav");
check("legacy hold-on-question wording cannot play under a new caption", next({}, { hold_on_question: { text: "Let me check that.", audio: "/media/fixture/old.wav" } }).audio === null);
check("empty or partial old filler banks use the locked runtime speech path", next({}, {}).audio === null && next({}, { wrong: null, missing: { text: phrases[0] } }).audio === null);

function harness({ state = { run: 1 }, early = null, fillers = {} } = {}) {
  const qa = deferred(), filler = deferred(), calls = { spoken: [], cancel: 0, waiting: 0 };
  const result = vm.runInNewContext(coordinator + "\nquestionResult", {
    S: state, bundle: { fillers }, nextQuestionAcknowledgement: next,
    withTimeout: async () => early,
    speak: (text, run, audio) => { calls.spoken.push({ text, run, audio }); return filler.promise; },
    cancelSpeech: () => { calls.cancel++; }, setStatus: () => { calls.waiting++; },
  });
  return { state, qa, filler, calls, result };
}
{
  const h = harness({ early: { answered: true, answer: "Already ready" } });
  check("fast answers do not speak or consume a phrase", (await h.result(h.qa.promise, 1, {})).answer === "Already ready" && !h.calls.spoken.length && h.state.questionAckIndex === undefined);
}
{
  const h = harness({ state: { run: 2 } });
  check("a superseded run does not consume a phrase after its grace", await h.result(h.qa.promise, 1, {}) === null && !h.calls.spoken.length && h.state.questionAckIndex === undefined);
}
{
  const state = { run: 1 }, heard = [];
  for (let i = 0; i < 11; i++) {
    const h = harness({ state }); const pending = h.result(h.qa.promise, 1, {}); await tick();
    heard.push(h.calls.spoken[0].text); h.qa.resolve({ answer: "Approved detail" }); await pending;
  }
  check("actual question coordinator rotates the complete pool within one visit", heard.every((text, i) => text === phrases[i % phrases.length]));
}
{
  const h = harness({ fillers: { matching: { text: phrases[0], audio: "/media/fixture/ack.wav" } } });
  const turn = {}, pending = h.result(h.qa.promise, 1, turn); await tick(); h.state.onFirstAudio(123);
  check("coordinator sends exact recorded audio and keeps acknowledgement timing separate", h.calls.spoken[0].audio === "/media/fixture/ack.wav" && turn.ack_audio === 123 && turn.answer_audio === undefined);
  h.qa.resolve({ answer: "Useful answer" });
  check("ready answer immediately cancels filler without waiting for its audio", (await pending).answer === "Useful answer" && h.calls.cancel === 1 && h.state.onFirstAudio === null);
}
{
  const h = harness(), pending = h.result(h.qa.promise, 1, {}); await tick();
  h.state.run = 2; const newer = () => {}; h.state.onFirstAudio = newer; h.qa.resolve({ answer: "Old" });
  check("late old answer cannot cancel newer voice or steal its timing callback", await pending === null && !h.calls.cancel && h.state.onFirstAudio === newer);
}
{
  const h = harness(), pending = h.result(h.qa.promise, 1, {}).catch(error => error); await tick(); h.qa.reject(new Error("Provider failed"));
  check("provider failure cancels only filler and propagates existing recovery", (await pending).message === "Provider failed" && h.calls.cancel === 1);
}
{
  const h = harness(); let complete = false;
  const pending = h.result(h.qa.promise, 1, {}).then(value => { complete = true; return value; }); await tick(); h.filler.resolve(true); await tick();
  check("completed acknowledgement waits for the original answer without inventing a turn", !complete && h.calls.waiting === 1 && !h.calls.cancel);
  h.qa.resolve({ answer: "Later" }); await pending;
}
console.log(`question_ack: ${passed}/${passed}`);

// CR47: execute real nested route assembly/application with the frozen live case.
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), assert = require('node:assert/strict');
const source = fs.readFileSync(path.join(__dirname,'../web/player/player.js'),'utf8');
const fixture = JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures/pitch_priority_revision.json'),'utf8'));
const bundle = fixture.published_bundle, request = fixture.actual_calls[1].request.body;
const part = (start,end) => source.slice(source.indexOf(start),source.indexOf(end,source.indexOf(start)));
const code = part('  function buildRoute(plan) {','  function rememberContext(') + '\n' + part('  async function applyUpcomingPlan(index, run) {','  async function waitForLineQuestion(')
  + '\n' + part('  async function playFrom(idx, lineIdx','  async function playDeeper(')
  + '\n' + part('  function resumePlayback(origin, run','  // ---------- intake + standard opening')
  + '\n({buildRoute,applyUpcomingPlan,playFrom,resumePlayback})';
const rear = bundle.segments.find(s=>s.id==='seating-and-cargo');
const exact = rear.deeper.find(l=>l.id==='seating-and-cargo-D2');
const selected = {route:[{segment_id:rear.id}],revisit_segment_ids:[rear.id],personalized_segments:[{segment_id:rear.id,lines:[{id:rear.id+'-personal',text:'You said, “my parents in the rear seats”.',fact_ids:[],base_line_index:null},{...exact,base_line_index:null}]}]};
function setup(plan=selected, status='ready') {
  const previous = [{slide:bundle.slides.find(s=>s.segment_id==='standard-safety-suite')}];
  const S={plan:previous,seg:0,run:3,covered:new Set(bundle.slides.map(s=>s.id)),profile:{focus:[]},pitch:{},pendingRefinement:{status,afterSegment:null,seen:request.seen_segments,plan:structuredClone(plan)}};
  const calls={notes:[],spoken:[],closed:[],waits:0};
  const api=vm.runInNewContext(code,{S,bundle,el:{cite:{textContent:'sources: fixture'}},waitFor:()=>{calls.waits++;throw new Error('Route narration must not wait');},library:()=>bundle.slides.filter(s=>s.segment_id),topicOf:s=>s.topics?.[0],renderProgress(){},prefetch(){},addMsg:(...v)=>calls.notes.push(v),speak:async text=>{calls.spoken.push(text);return true;},
    newRun:()=>++S.run,showSlideView:()=>({setRevealed(){}}),
    playLines:async(sl,run,view,from,upto)=>{calls.spoken.push(...sl.lines.slice(from,upto).map(l=>l.text));return true;},closeFlow:async(run,line)=>calls.closed.push({run,line})});
  return {S,api,calls,previous};
}
async function run(){
  let count=0;
  async function check(name,fn){await fn();count++;console.log('PASS '+name);}
  await check('actual selected rear proof survives seen filtering with exact reviewed audio/visual',async()=>{const t=setup();await t.api.applyUpcomingPlan(0,3);assert.equal(t.S.plan[0].slide.segment_id,rear.id);assert.equal(t.S.plan[0].slide.lines[1].text,exact.text);assert.equal(t.S.plan[0].slide.lines[1].audio,exact.audio);assert.equal(t.S.plan[0].slide.image_id,bundle.slides.find(s=>s.segment_id===rear.id).image_id);});
  await check('ordinary continuation does not repeat a seen route',async()=>{const t=setup({...selected,revisit_segment_ids:[]});await t.api.applyUpcomingPlan(0,3);assert.equal(t.S.plan,t.previous);});
  await check('unselected or unknown permission cannot authorize a seen route',async()=>{for(const id of ['invented','standard-safety-suite']){const t=setup({...selected,revisit_segment_ids:[id]});await t.api.applyUpcomingPlan(0,3);assert.equal(t.S.plan,t.previous);}});
  await check('completed prefix is retained before explicit selected revisit',async()=>{const t=setup();await t.api.applyUpcomingPlan(1,3);assert.deepEqual(Array.from(t.S.plan,s=>s.slide.segment_id),['standard-safety-suite',rear.id]);});
  await check('pending plan never applies prematurely',async()=>{const t=setup(selected,'pending');await t.api.applyUpcomingPlan(0,3);assert.equal(t.S.plan,t.previous);assert.ok(t.S.pendingRefinement);});
  await check('current return boundary stays owned before refined route',async()=>{const t=setup();t.S.pendingRefinement.afterSegment='not-completed';await t.api.applyUpcomingPlan(0,3);assert.equal(t.S.plan,t.previous);assert.ok(t.S.pendingRefinement);});
  await check('explicit continue from actual closing point plays full reviewed revisit, not only preface',async()=>{const t=setup();await t.api.resumePlayback({phase:'closing',line:2},3);assert.ok(t.calls.spoken.includes(exact.text));assert.equal(t.S.plan.at(-1).slide.segment_id,rear.id);assert.equal(t.calls.closed.length,1);});
  await check('ordinary covered slide still uses its original brief replay',async()=>{const t=setup();t.api.buildRoute(selected);t.S.pendingRefinement=null;await t.api.playFrom(0,0);assert.deepEqual(t.calls.spoken,[selected.personalized_segments[0].lines[0].text]);assert.equal(t.calls.closed.length,1);});
  await check('ordinary closing remains unchanged without ready refinement',async()=>{const t=setup(selected,'pending');await t.api.resumePlayback({phase:'closing',line:2},3);assert.deepEqual(t.calls.closed,[{run:3,line:2}]);assert.equal(t.calls.spoken.length,0);});
  await check('superseded closing continuation never delivers revised proof',async()=>{const t=setup();const pending=t.api.resumePlayback({phase:'closing',line:2},3);t.S.run++;await pending;assert.equal(t.calls.spoken.length,0);assert.equal(t.calls.closed.length,0);});
  await check('a reviewed revisit skips its legacy question check-in without reopening a wait',async()=>{const t=setup();await t.api.applyUpcomingPlan(0,3);t.S.pendingRefinement=null;t.S.plan[0].slide={...t.S.plan[0].slide,checkin:{text:'Does that fit your needs?',audio:'reviewed-checkin-audio'}};await t.api.playFrom(0,0);assert.ok(t.calls.spoken.includes(exact.text));assert.ok(!t.calls.spoken.includes('Does that fit your needs?'));assert.equal(t.S.checkin_skipped,'legacy_question');assert.equal(t.S.plan[0].slide.checkin.audio,'reviewed-checkin-audio');assert.equal(t.calls.waits,0);assert.equal(t.calls.closed.length,1);});
  console.log(`Player priority revision contracts: ${count}/${count}; no browser/network/provider`);
}
run().catch(e=>{console.error(e);process.exitCode=1;});

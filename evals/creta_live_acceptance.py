"""Controlled, muted browser acceptance against an explicitly authorized real bundle.

No user browser/profile or physical microphone. Real app, prerecorded audio,
WebAudio output, WS reasoning, tools and TTS. Microphone capture is synthetic
silence; STT transport is replaced with injected events. This does not validate
acoustic onset, recognition accuracy, echo cancellation or human voice quality.
A read-only observer is inserted into the served player module, never its file.
Every paid outbound browser request checks recorded usage before forwarding.
"""
import argparse
import json
import signal
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright, expect, TimeoutError as PlaywrightTimeout

parser = argparse.ArgumentParser()
parser.add_argument('--url', required=True)
parser.add_argument('--authorized-real-batch', action='store_true')
parser.add_argument('--safety-only', action='store_true', help='Authorized targeted full safety replay; preserves master counters and baseline')
parser.add_argument('--mock-dry-run', action='store_true', help='Free isolated mock fixture on8897; never real providers')
parser.add_argument('--mock-natural-only', action='store_true', help='With mock-dry-run, exercise natural completions without provider-latency interruption phases')
parser.add_argument('--mock-pitch-failure', action='store_true', help='Free mock only: fail planning locally to prove honest fallback still completes')
args = parser.parse_args()
assert not args.safety_only or (args.authorized_real_batch and not args.mock_dry_run), 'Safety replay is an explicitly authorized real batch'
assert not args.mock_natural_only or args.mock_dry_run, 'Natural-only mode is restricted to the free mock fixture'
assert not args.mock_pitch_failure or args.mock_dry_run, 'Planning fault injection is restricted to the free mock fixture'
assert args.authorized_real_batch or args.mock_dry_run, 'Explicit parent authorization is required'
BASE = 'http://127.0.0.1:8897' if args.mock_dry_run else 'http://127.0.0.1:8896'
assert args.url.startswith(BASE + '/') and 'mute=1' in args.url
DEMO = args.url.split('/play/')[-1]
OUT = Path('output/playwright/creta-harness-free-natural' if args.mock_natural_only else 'output/playwright/creta-harness-free-v2' if args.mock_dry_run else 'output/playwright/creta-real-runtime')
if args.mock_pitch_failure: OUT = Path('output/playwright/creta-harness-free-fallback')
BATCH_OUT = OUT
if args.safety_only:
    replay = BATCH_OUT / 'safety-replay'
    attempt = 1
    while (replay / f'attempt-{attempt:02}').exists(): attempt += 1
    OUT = replay / f'attempt-{attempt:02}'
OUT.mkdir(parents=True, exist_ok=True)
pause_file = OUT / 'pause-requested'
pause_reason = ''


def check_pause():
    if pause_reason or pause_file.exists() or (BATCH_OUT / 'pause-requested').exists():
        raise RuntimeError(pause_reason or 'Parent requested pause via pause-requested file; no further paid request forwarded')


check_pause()
http = httpx.Client(base_url=BASE, timeout=12)
usage_path = f'/api/demos/{DEMO}/usage'
bundle = http.get(f'/api/demos/{DEMO}/bundle').raise_for_status().json()
assert bundle.get('runtime', {}).get('version') == 1 and bundle['runtime']['overview'].get('audio'), 'Built runtime overview required'
budget_file = BATCH_OUT / 'budget-state.json'
budget = json.loads(budget_file.read_text()) if budget_file.exists() else {'usage_before': http.get(usage_path).raise_for_status().json(), 'counters': {'reasoning_requests': 0, 'tts_requests': 0}}
usage_before = budget['usage_before']
ledger, checks, scenarios, errors, journeys, planning_outcomes = [], [], [], [], [], []
counters = budget['counters']
budget_file.write_text(json.dumps(budget, indent=2))
started = time.time()
interruptions_per_phase = 0 if args.mock_natural_only or args.safety_only else 4
expected_interruptions = interruptions_per_phase * 5


def stamp(): return round(time.time() * 1000)
def note(kind, **detail):
    row = {'at_ms': stamp(), 'kind': kind, **detail}; ledger.append(row)
    with (OUT / 'events.jsonl').open('a') as file: file.write(json.dumps(row) + '\n')
    return row

def guard(kind):
    check_pause()
    guard_started = time.monotonic()
    current = http.get(usage_path).raise_for_status().json()
    delta = current['total_usd'] - usage_before['total_usd']
    llm_calls = sum(max(0, item['calls'] - usage_before.get('by_model', {}).get(model, {}).get('calls', 0))
                    for model, item in current.get('by_model', {}).items() if item.get('in', 0) or item.get('out', 0))
    note('budget_before_request', request_kind=kind, total_usd=current['total_usd'], shared_usage_delta_usd=round(delta, 4), shared_recorded_llm_calls=llm_calls, budget_check_ms=round((time.monotonic()-guard_started)*1000, 2), counters=dict(counters))
    # Reserve headroom for the accepted request and any already-running call.
    # The separately authorized concurrent QA batch shares this demo's usage ledger.
    # Parent authorized a combined $6 shared delta ($3.50 QA + $2.50 browser reserve)
    # after concurrent QA consumed the original browser-only shared-ledger ceiling.
    # Parent authorized final cumulative caps32/32 after the preserved harness and
    # provider failures. Every prior request and the original baseline still count.
    # The shared $6 and overall $19.50 guards remain unchanged.
    if current['total_usd'] >= 19.5 or delta >= 6.0 or (kind == 'reasoning' and counters['reasoning_requests'] >= 32) or (kind == 'tts' and counters['tts_requests'] >= 32):
        raise RuntimeError('Authorized paid batch ceiling reached; no further paid request forwarded')
    counters['reasoning_requests' if kind == 'reasoning' else 'tts_requests'] += 1
    budget_file.write_text(json.dumps(budget, indent=2))

def check(name, ok, detail=None):
    checks.append({'name': name, 'passed': bool(ok), 'at_ms': stamp(), 'detail': detail})
    print(('PASS ' if ok else 'FAIL ') + name, flush=True)
    if not ok: raise AssertionError(name)

INSTRUMENT = r"""(() => {
window.__wire=[];window.__audios=[];window.__sources=[];window.__captures=0;window.__tracks=[];window.__media=[];
const WS=window.WebSocket;window.WebSocket=class extends WS {
 constructor(...a){super(...a);window.__liveSocket=this;this.addEventListener('message',e=>{try{const x=JSON.parse(e.data);window.__wire.push({at_ms:Date.now(),direction:'in',...x,audio:x.audio?'[PCM]':undefined});}catch{}});}
 send(raw){try{const x=JSON.parse(raw);window.__wire.push({at_ms:Date.now(),direction:'out',...x,audio:x.audio?'[PCM]':undefined});}catch{}return super.send(raw);}
};
const Audio=window.Audio;window.Audio=function(...a){const media=new Audio(...a);window.__audios.push(media);for(const kind of ['playing','pause','ended','error'])media.addEventListener(kind,()=>window.__media.push({at_ms:Date.now(),kind,src:media.src,currentTime:media.currentTime}));return media;};window.Audio.prototype=Audio.prototype;
const make=AudioContext.prototype.createBufferSource;AudioContext.prototype.createBufferSource=function(...a){const s=make.apply(this,a);window.__sources.push(s);const play=s.start.bind(s),stop=s.stop.bind(s);s.start=(...b)=>{s.__playing=true;s.__startAt=Date.now();return play(...b)};s.stop=(...b)=>{s.__playing=false;s.__stopAt=Date.now();return stop(...b)};s.addEventListener('ended',()=>s.__playing=false);return s;};
navigator.mediaDevices.getUserMedia=async()=>{window.__captures++;const c=new AudioContext(),s=c.createConstantSource(),g=c.createGain(),d=c.createMediaStreamDestination();g.gain.value=0;s.connect(g);g.connect(d);s.start();await c.resume();for(const t of d.stream.getTracks()){window.__tracks.push(t);const stop=t.stop.bind(t);t.stop=()=>{stop();s.stop();c.close();};}return d.stream;};
window.__inject=(e)=>{const g=window.__reviewSnapshot?.().input_generation;window.__liveSocket.dispatchEvent(new MessageEvent('message',{data:JSON.stringify({input_generation:g,...e})}));};
})();"""
OBSERVER = '''  window.__reviewSnapshot = () => ({at_ms:Date.now(),context:context(),pitch:S.pitch,playback:{...S.playback},origin:S.conversationOrigin?{...S.conversationOrigin}:null,speaking:S.speaking?{text:S.speaking.text,startedAt:S.speaking.startedAt,recorded:!!S.speaking.audio}:null,waiting:!!S.waiter,activeTurn:S.activeTurn?{...S.activeTurn}:null,session:sessionRecord(),pending:!!live?.pending,mic:!!live?.mic,input_generation:live?.inputGeneration,mic_ready:!!live?.micReady,delivery:live?.delivery?{utteranceId:live.delivery.utteranceId,started:live.delivery.started}:null});
'''

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless=True, args=['--mute-audio', '--autoplay-policy=no-user-gesture-required'])
    context = browser.new_context(viewport={'width': 1440, 'height': 1000})
    context.add_init_script(INSTRUMENT)
    def route_http(route):
        url = route.request.url
        if not url.startswith((BASE, 'data:', 'blob:')): route.abort(); return
        if args.mock_pitch_failure and route.request.method == 'POST' and url.endswith('/run/pitch'):
            route.fulfill(status=503,content_type='application/json',body=json.dumps({'detail':'Free local planning-failure regression'})); return
        if url.endswith('/web/player/player.js'):
            response = route.fetch(); source = response.text()
            needle = '  return { destroy, restart, pause, context };'
            assert source.count(needle) == 1
            route.fulfill(response=response, body=source.replace(needle, OBSERVER + needle)); return
        try:
            if route.request.method == 'POST' and url.endswith(('/run/pitch', '/run/qa')): guard('reasoning')
            elif route.request.method == 'POST' and url.endswith('/run/tts'): guard('tts')
            elif url.endswith('/run/lead'): raise RuntimeError('Acceptance never submits contact information')
        except Exception as error:
            errors.append(str(error)); route.abort(); return
        route.continue_()
    context.route('**/*', route_http)
    def route_socket(route):
        server = route.connect_to_server()
        def outbound(raw):
            try:
                data = json.loads(raw)
                kind = data.get('type')
                if kind == 'mic.set':
                    if data.get('enabled'): route.send(json.dumps({'type':'mic.ready','session_id':data['session_id'],'input_generation':data['input_generation']}))
                    return
                if kind == 'audio.input': return
                if kind == 'turn.ask': guard('reasoning')
                elif kind in ('delivery.request', 'delivery.speak'): guard('tts')
                note('client_message', **{k:v for k,v in data.items() if k not in ('audio','history')})
                server.send(raw)
            except Exception as error:
                errors.append(str(error)); route.close(code=1000, reason='Acceptance budget or transport guard')
        route.on_message(outbound)
    context.route_web_socket('**/run/live*', route_socket)
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    def snap(): return page.evaluate('__reviewSnapshot()')
    def wait(condition, timeout=45000):
        deadline = time.monotonic() + timeout / 1000
        while True:
            check_pause()
            left = int((deadline - time.monotonic()) * 1000)
            if left <= 0: raise TimeoutError(f'Timed out waiting for browser condition: {condition}')
            try:
                return page.wait_for_function(condition, timeout=min(1000, left))
            except PlaywrightTimeout:
                pass
    def lead_close():
        if page.locator('.pl-lead.open').count(): page.locator('.pl-lead.open .lead-close').click()
    def question(text):
        check_pause()
        lead_close(); field=page.get_by_role('textbox',name='Your question or answer',exact=True); field.fill(text); field.press('Enter')
    def capture():
        if not snap()['mic']:
            page.locator('.pl-mic-row .mic').click()
            wait('__reviewSnapshot().mic && __reviewSnapshot().mic_ready')
    def barge(label):
        before=snap(); recorded = page.evaluate('__audios.filter(a=>!a.paused&&!a.ended).length'); streamed=page.evaluate('__sources.filter(a=>a.__playing).length')
        at=stamp()
        page.evaluate("label=>{__inject({type:'input.speech_start',input_id:label});__inject({type:'transcript.final',input_id:label,text:''});}",label)
        after=snap(); stopped=stamp()
        quiet=page.evaluate('__audios.every(a=>a.paused||a.ended)&&__sources.every(a=>!a.__playing)')
        client_stop=after['session']['interruptions'][-1] if after['session']['interruptions'] else None
        item={'label':label,'injected_at_ms':at,'observed_stopped_at_ms':stopped,'browser_observation_ms':stopped-at,'client_interrupt':client_stop,'client_event_to_stop_ms':client_stop['stopped_at']-client_stop['detected_at'] if client_stop else None,'before':before,'after':after,'active_recorded_before':recorded,'active_streamed_before':streamed,'quiet_after':quiet,'synthetic_onset':True,'measurement_note':'Browser observation includes automation round trips; client event-to-stop uses one browser clock, and neither is acoustic onset.'}
        scenarios.append(item); note('controlled_interruption',label=label,observed_phase=before['playback']['phase'],stopped=quiet,browser_observation_ms=stopped-at)
        check(label+' stops current delivery and owns a wait',quiet and after['waiting'] and not after['pending'])
        if label.endswith('-1'): page.screenshot(path=str(OUT/(label+'.png')))
        # The onset injected above is not an acoustic timestamp.
        return item
    def continue_demo():
        check_pause()
        lead_close(); page.get_by_role('button',name='Continue demo',exact=True).click()
    def end_journey(name, natural=False, expected_slides=None):
        check_pause(); lead_close()
        if not natural: page.get_by_role('button',name='Stop and see the summary',exact=True).click()
        expect(page.get_by_role('heading',name='Your recap',exact=True)).to_be_visible()
        state=snap(); record={'name':name,'completion_mode':'natural_route_end' if natural else 'deliberate_interruption_early_exit','expected_route_slides':expected_slides or [],**state}
        journeys.append(record);(OUT/(name+'.json')).write_text(json.dumps(record,indent=2));page.screenshot(path=str(OUT/(name+'.png')))
        check(name+' ends without submitting a lead',not state['session']['leads'] and page.evaluate('__tracks.every(t=>t.readyState==="ended")'))
        if natural:
            visited={visit['slide_id'] for visit in state['session']['slides_visited']}
            check(name+' completed every planned slide before natural recap',state['playback']['phase']=='closing' and set(expected_slides or []).issubset(visited) and not state['origin'] and not state['activeTurn'], {'expected':expected_slides,'visited':sorted(visited),'playback':state['playback']})
        if name == 'safety-evidence':
            page.get_by_role('button',name='Request dealership follow-up',exact=True).click()
            expect(page.get_by_role('textbox',name='Your name',exact=True)).to_be_visible()
            check('dealership follow-up still requires explicit contact submission',not snap()['session']['leads'] and page.locator('.pl-lead.open .consent').is_visible())
            page.screenshot(path=str(OUT/'optional-consent.png'));lead_close()
    def finish_tour(name, expected_slides):
        # Continue only explicit reviewed confirmation/return choices. Unknown or
        # stale questions fail; Stop is never used to manufacture route completion.
        history=[]
        for _ in range(30):
            check_pause(); lead_close(); wait('__reviewSnapshot().waiting',timeout=75000)
            state=snap(); chips=page.locator('.pl-chips button'); labels=chips.all_text_contents()
            history.append({'at_ms':stamp(),'playback':state['playback'],'slide':state['context']['slide'],'choices':labels})
            note('natural_route_boundary',journey=name,playback=state['playback'],slide=state['context']['slide'],choices=labels)
            check(name+' has no stale active question at continuation',not state['activeTurn'] and not state['pending'])
            if state['playback']['phase']=='closing' and 'Not yet' in labels:
                page.get_by_role('button',name='Not yet',exact=True).click()
                wait('!!document.querySelector(".pl-handoff.open")',timeout=30000)
                (OUT/(name+'-completion.json')).write_text(json.dumps(history,indent=2))
                end_journey(name,natural=True,expected_slides=expected_slides); return
            choice=next((label for label in ['Continue demo','That settles it','Continue','Yes, continue'] if label in labels),None)
            check(name+' exposes an owned route continuation',bool(choice),{'phase':state['playback'],'choices':labels})
            page.get_by_role('button',name=choice,exact=True).click()
        raise AssertionError(name+' exceeded30 route boundaries without natural completion')
    def begin(profile):
        check_pause()
        if page.url == args.url: page.reload()
        else: page.goto(args.url)
        page.get_by_role('button',name='Explore with me',exact=True).click();field=page.get_by_role('textbox',name='Your answer',exact=True);expect(field).to_be_visible();field.fill(profile);field.press('Enter');capture()
    def request_pause(signum, _frame):
        global pause_reason
        pause_reason=f'Parent requested cooperative pause with {signal.Signals(signum).name}; no further paid request forwarded'
    signal.signal(signal.SIGINT,request_pause); signal.signal(signal.SIGTERM,request_pause)
    try:
        if not args.safety_only:
            begin('I am exploring a family SUV. Rear-seat comfort and boot space matter most, and I want to understand the safety features.')
            for i in range(interruptions_per_phase):
                wait("__reviewSnapshot().playback.phase==='overview' && !!__reviewSnapshot().speaking?.startedAt")
                row=barge(f'overview-{i+1}');check('overview return point retained',row['after']['origin']['phase']=='overview');continue_demo()
            for i in range(interruptions_per_phase):
                wait("__reviewSnapshot().playback.phase==='route' && !__reviewSnapshot().playback.checkin && !!__reviewSnapshot().speaking?.startedAt && !!__reviewSnapshot().speaking?.recorded && !__reviewSnapshot().waiting")
                row=barge(f'narration-{i+1}');origin=row['after']['origin'];check('narration exact line return retained',origin['index']==row['before']['playback']['index'] and origin['line']==row['before']['playback']['line']);continue_demo()
            wait('__reviewSnapshot().waiting')
            faqs=[entry for entry in bundle.get('faq',[]) if entry.get('answered') and entry.get('question')]
            bank_question=(faqs[0]['question'] if faqs else 'What safety equipment is included?')
            for i in range(interruptions_per_phase):
                question(bank_question)
                wait("!!__reviewSnapshot().activeTurn?.qa_done && !!__reviewSnapshot().speaking?.startedAt && __reviewSnapshot().speaking.text===__wire.filter(e=>e.type==='turn.result').at(-1)?.answer?.answer")
                barge(f'answer-{i+1}')
            for i in range(interruptions_per_phase):
                question(f'Estimate the monthly EMI for a loan of {10+i} lakh rupees at 9 percent annual interest over 5 years. Show the assumptions.')
                wait("!!__reviewSnapshot().pending && /moment|check that|checking/i.test(__reviewSnapshot().speaking?.text||'') && !!__reviewSnapshot().speaking?.startedAt",timeout=18000)
                barge(f'acknowledgment-filler-{i+1}')
            for i in range(interruptions_per_phase):
                question(f'Calculate the illustrative monthly EMI on a loan of {15+i} lakh rupees at 8 percent annual interest over 4 years.')
                wait('__reviewSnapshot().pending')
                barge(f'calculation-request-pending-{i+1}')
            check(f'{expected_interruptions} controlled interruptions completed',len(scenarios)==expected_interruptions)
            end_journey('family-comfort-interruptions-early-exit')
        for name,profile,text in [
            ('commute-calculation','I commute in the city and care most about everyday comfort and monthly ownership cost.','Calculate the illustrative monthly EMI on a loan of 10 lakh rupees at 9 percent annual interest over 5 years.'),
            ('safety-evidence','Safety and confidence on family highway trips matter most to me. I would like to understand the approved driver assistance features.','What driver assistance features are available, and which variant conditions apply?')]:
            if args.safety_only and name != 'safety-evidence': continue
            begin(profile)
            # A valid selected route may contain no authored check-in. Ask during
            # reviewed narration instead of assuming a question wait must exist.
            wait("__reviewSnapshot().playback.phase==='route' && (__reviewSnapshot().waiting || (!!__reviewSnapshot().speaking?.startedAt && !!__reviewSnapshot().speaking?.recorded))",timeout=75000)
            state=snap()
            check(name+' preserves the stated need and reaches a reviewed route',state['session']['profile']['why']==profile and bool(state['context']['route']))
            disclosed = any("couldn't finish tailoring" in item.get('text', '') for item in state['session']['transcript'])
            planning = {'journey':name,'personalized':bool(state['session']['personalized']),'fallback_disclosed':disclosed,'planning_failed':not bool(state['session']['personalized']),'status':'personalized' if state['session']['personalized'] else 'honest_fallback' if disclosed else 'unexplained_fallback','at_ms':stamp()}
            planning_outcomes.append(planning); note('planning_outcome',**planning)
            check(name+' either personalizes or explicitly discloses planning failure',planning['personalized'] or planning['fallback_disclosed'],planning)
            expected_slides=list(state['session']['slides'])
            question(text);wait('__reviewSnapshot().waiting && !__reviewSnapshot().pending && !__reviewSnapshot().activeTurn',timeout=45000)
            state=snap();check(name+' answer requires explicit continuation',state['waiting'] and bool(state['session']['turns']))
            if not args.mock_dry_run:check(name+' receives an answer without provider failure',state['session']['turns'][-1].get('answered') and not state['session']['turns'][-1].get('failed'),state['session']['turns'][-1])
            if name=='commute-calculation' and not args.mock_natural_only:check('calculation result records tool provenance',state['session']['turns'][-1].get('tool_count',0)>0,state['session']['turns'][-1])
            finish_tour(name,expected_slides)
        check('no browser exception or guard violation',not errors,errors)
    except Exception as error:
        errors.append(str(error));note('batch_stopped',error=str(error))
        try: page.screenshot(path=str(OUT/'failure.png'));(OUT/'failure-state.json').write_text(json.dumps(snap(),indent=2))
        except Exception: pass
    finally:
        try:
            (OUT/'browser-events.json').write_text(json.dumps(page.evaluate('({wire:__wire,media:__media})'),indent=2))
            if not page.locator('.pl-handoff.open').count() and page.locator('.pl').count(): page.get_by_role('button',name='Stop and see the summary',exact=True).click()
        except Exception: pass
        context.close();browser.close()
usage_after=http.get(usage_path).raise_for_status().json()
result={'started_at_ms':round(started*1000),'finished_at_ms':stamp(),'bundle_version':bundle.get('version'),'demo_id':DEMO,'checks':checks,'interruptions':scenarios,'journeys':journeys,'errors':errors,'counters':counters,'usage_before':usage_before,'usage_after':usage_after,'batch_usd_recorded':round(usage_after['total_usd']-usage_before['total_usd'],4),'usage_attribution':'Dollar delta and provider completion counts share the demo ledger with separately authorized concurrent QA; may overestimate browser cost. Persistent outbound reasoning/TTS request counters apply only to this browser batch and are never reset between attempts.','boundary':'Isolated headless Chrome, all output muted. Actual prerecorded/WebAudio delivery and real backend reasoning/tools/TTS. Synthetic silent capture and injected STT onset/finals. Read-only observer only. No acoustic onset/STT accuracy/echo/human quality claim. Calculation-request-pending is browser state, not proof of active tool execution.'}
result['budget_limits'] = {'shared_incremental_usd_stop':6.0,'shared_scope':'Separately authorized concurrent QA $3.50 plus browser $2.50 reserve; not browser-attributed spending.','overall_demo_usd_stop':19.5,'browser_reasoning_requests_cumulative':32,'browser_tts_requests_cumulative':32,'cap_authorization':'Parent raised TTS20 to24 during attempt03, then28 for targeted replay, then final TTS32/reasoning32 for corrected source publication v3; counters and original baseline preserved','baseline_and_counters_reset':False}
result['targeted_safety_replay'] = args.safety_only
result['planning_outcomes'] = planning_outcomes
result['mock_planning_fault_injected'] = args.mock_pitch_failure
result['evaluation_mode'] = 'mock_natural_completion_only_no_tool_accuracy_claim' if args.mock_natural_only else 'mock_interruption_dry_run' if args.mock_dry_run else 'real_provider_controlled_browser_acceptance'
(OUT/'results.json').write_text(json.dumps(result,indent=2))
print(json.dumps({'checks':f'{sum(c["passed"] for c in checks)}/{len(checks)}','interruptions':len(scenarios),'journeys':len(journeys),'planning_failures':sum(item['planning_failed'] for item in planning_outcomes),'errors':errors,'counters':counters,'batch_usd_recorded':result['batch_usd_recorded']},indent=2))
raise SystemExit(1 if errors or len(scenarios)!=expected_interruptions or len(journeys)!=(1 if args.safety_only else 3) else 0)

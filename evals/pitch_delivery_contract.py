"""Free actual-pitch regressions: overview goes straight into reviewed route speech."""
from __future__ import annotations
import copy
import asyncio
import sys
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import config, schemas, store
from server.agents import pitch, voice

passed=[]
def check(name, ok):
    print(('PASS ' if ok else 'FAIL ')+name)
    if not ok: raise AssertionError(name)
    passed.append(name)

facts=[{'id':'F1','kind':'feature','claim':'Seat ventilation','value':'Ventilated front seats','conditions':'Selected variants only','approved':True,'source':{'ref':'brochure','quote':'Ventilated front seats'}},
       {'id':'F2','kind':'feature','claim':'Airbags','value':'Six airbags standard','conditions':'Every variant','approved':True,'source':{'ref':'brochure','quote':'Six airbags as standard'}},
       {'id':'F_UNUSED','kind':'feature','claim':'Unused equipment','value':'Unrelated to reviewed route','conditions':'Unused condition','approved':True,'source':{'quote':'PROVENANCE_TABLE_SENTINEL '+('unrelated cell '*1000)}}]
lines=[{'id':'cabin-L1','text':'Selected variants offer ventilated front seats.','fact_ids':['F1'],'audio':'audio/cabin-reviewed.wav','visual':{'kind':'image','ref':'im01'},'delivery':{'tone':'warm'}},
       {'id':'safety-L1','text':'Six airbags come as standard across the range.','fact_ids':['F2'],'audio':'audio/safety-reviewed.wav','visual':{'kind':'image','ref':'im02'},'delivery':{'tone':'calm'}}]
segments=[{'id':sid,'role':'proof','title':sid.title(),'topic':sid,'lines':[copy.deepcopy(line)],'deeper':[{**copy.deepcopy(line),'audio':'/media/fixture/audio/deeper-reviewed.wav'}],'checkin':'Is that enough detail for now?','checkin_audio':'audio/checkin-reviewed.wav'} for sid,line in zip(['cabin','safety'],lines)]
files={'understanding.json':{'product':{'name':'Fixture'},'facts':facts,'images':[],'shots':[]},'plan.json':{'voice':{},'segments':[],'ctas':[]},'script.json':{'segments':segments},'deck.json':{'slides':[{'id':'sl-'+s['id'],'segment_id':s['id']} for s in segments]}}
files['bundle.json']={'id':'fixture','version':2,'knowledge_snapshot_id':'kb_fixture','product':{'name':'Fixture'},'facts':copy.deepcopy(facts),'segments':copy.deepcopy(segments),'pitch':{},'voice':{'persona':{'persona_name':'Priya'}},'ctas':[],'slides':copy.deepcopy(files['deck.json']['slides']),'media':{'images':[]},'language':'en-IN'}
profile={'why':'I care about family safety and warmer afternoons.'}
proposal=schemas.PitchPlan(customer_state='stated_need',decision_frame='We will talk about your needs before we take a long tour through every area and explain all the options.',follow_up_question='',primary_outcome='Family safety',focus_topics=['safety'],route=[schemas.RouteStep(segment_id='safety',bridge='Next: Safety.'),schemas.RouteStep(segment_id='cabin')],advance='Review the choices.',custom_batches=[schemas.CustomBatch(text=lines[0]['text'],fact_ids=['F1'])])
with ExitStack() as stack:
    stack.enter_context(patch.object(config,'MOCK_LLM',True))
    stack.enter_context(patch.object(store,'load',return_value={'settings':{'language':'en-IN'},'approvals':{'script':True}}))
    stack.enter_context(patch.object(store,'read_json',side_effect=lambda _id,name:copy.deepcopy(files.get(name))))
    stack.enter_context(patch.object(store,'log'))
    stack.enter_context(patch.object(store,'write_json',side_effect=AssertionError('No data writes')))
    tts=stack.enter_context(patch.object(voice,'render_line',side_effect=AssertionError('Live route cannot block on TTS')))
    sockets=[stack.enter_context(patch(name,side_effect=AssertionError('No outbound'))) for name in ['socket.create_connection','socket.socket.connect','socket.socket.connect_ex']]
    with patch.object(pitch.runtime,'structured',return_value=proposal) as model:
        result=pitch.plan_pitch('fixture',profile,voice_it=False)
        unknown=pitch.plan_pitch('fixture',{'focus':['safety']},voice_it=False)
        unseen=pitch.plan_pitch('fixture',profile,voice_it=False,seen_segment_ids=['safety'])
    prompt=model.call_args_list[0].args[0]
    check('live payload excludes uncited assertions source tables and media paths while retaining conditions',all(word not in prompt for word in ['F_UNUSED','PROVENANCE_TABLE_SENTINEL','audio/cabin-reviewed.wav','checkin_audio']) and 'Selected variants only' in prompt and lines[0]['text'] in prompt and lines[1]['text'] in prompt)
    with patch.object(pitch.runtime,'structured',side_effect=RuntimeError('capture only')) as legacy_model:
        try: pitch.plan_pitch('fixture',profile,voice_it=True)
        except RuntimeError: pass
    check('legacy recorded planner retains full source-context contract','PROVENANCE_TABLE_SENTINEL' in legacy_model.call_args.args[0] and 'audio/cabin-reviewed.wav' in legacy_model.call_args.args[0])
    replacements=result['personalized_segments']
    check('omitted model replacements yield exact reviewed fallback for every selected unseen route', [r['segment_id'] for r in replacements]==['safety','cabin'] and all(r['personalization_basis']=='reviewed_route_fallback' for r in replacements))
    all_lines=[line for r in replacements for line in r['lines']]
    check('one short verbatim context preface lives on first slide only',sum(line.get('step')=='frame' for line in all_lines)==1 and replacements[0]['lines'][0]['step']=='frame' and 'I care about family safety and warmer afternoons' in replacements[0]['lines'][0]['text'] and len(replacements[0]['lines'][0]['text'].split())<=10)
    for r in replacements:
        expected=next(line for line in lines if line['id'].startswith(r['segment_id']))
        actual=next(line for line in r['lines'] if line.get('fact_ids'))
        check('reviewed '+r['segment_id']+' IDs audio citations delivery and callout mapping survive',all(actual[k]==expected[k] for k in ['id','text','fact_ids','delivery','visual']) and actual['audio']=='/media/fixture/'+expected['audio'] and actual['base_line_index']==0)
    check('replacement questions and deeper media retain client-ready bundle shape',all(r['checkin']=={'text':'Is that enough detail for now?','audio':'/media/fixture/audio/checkin-reviewed.wav'} and r['deeper'][0]['audio']=='/media/fixture/audio/deeper-reviewed.wav' for r in replacements))
    check('no custom pre-roll bridge or decision audio and no extra TTS',not result['custom_batches'] and result['decision_frame_audio'] is None and all(not r['bridge'] and r['bridge_audio'] is None for r in result['route']) and not tts.called)
    check('unknown customer is not assigned personal details or fabricated replacements',not unknown['personalized_segments'] and unknown['customer_state']=='unknown' and not unknown['custom_batches'])
    check('seen segments remain absent from fallback route and replacements',[r['segment_id'] for r in unseen['route']]==['cabin'] and [r['segment_id'] for r in unseen['personalized_segments']]==['cabin'])
    malicious=proposal.model_copy(deep=True);malicious.personalized_segments=[schemas.PersonalizedSegment(segment_id='safety',customer_quote='you travel two hundred kilometres',lines=[schemas.LineOut(text='Six airbags guarantee accident-free travel.',fact_ids=['F2'],visual={'kind':'none'})])]
    with patch.object(pitch.runtime,'structured',return_value=malicious):
        held=pitch.plan_pitch('fixture',profile,voice_it=False)
    text=' '.join(line['text'] for r in held['personalized_segments'] for line in r['lines'])
    check('invalid rewrite and invented context never enter deterministic fallback','guarantee' not in text and 'two hundred' not in text and held['personalized_segments'][0]['personalization_basis']=='reviewed_route_fallback')
    selected=proposal.model_copy(deep=True);selected.personalized_segments=[schemas.PersonalizedSegment(segment_id='safety',customer_quote='family safety',lines=[schemas.LineOut.model_validate(lines[1])])]
    with patch.object(pitch.runtime,'structured',return_value=selected):
        composed=pitch.plan_pitch('fixture',profile,voice_it=False)
    check('valid model selection distinguished from missing-segment fallback', [r['personalization_basis'] for r in composed['personalized_segments']]==['model_reviewed_selection','reviewed_route_fallback'] and 'family safety' in composed['personalized_segments'][0]['lines'][0]['text'])
    check('live prompt requests replacement speech instead of optional monologue','LIVE ROUTE DELIVERY' in model.call_args.args[0] and 'Return personalized_segments for every selected segment' in model.call_args.args[0])
    long_reply={'why':'I usually enjoy discussing screens, but today I do not want screens; I need to check child seat mounting.'}
    with patch.object(pitch.runtime,'structured',return_value=proposal):
        uncut=pitch.plan_pitch('fixture',long_reply,voice_it=False)
    check('long customer reply is never arbitrarily clipped into a context claim',not any(line.get('step')=='frame' for segment in uncut['personalized_segments'] for line in segment['lines']) and uncut['personalized_segments'][0]['context_preface_omitted']=='unsafe_quote_or_segment_budget')
    with patch.object(pitch.runtime,'structured',return_value=proposal) as pinned_model:
        before=pitch.plan_pitch('fixture',profile,voice_it=False,expected_snapshot_id='kb_fixture',expected_demo_version=2)
        prompt_before=pinned_model.call_args.args[0]
        files['understanding.json']['facts']=[];files['script.json']['segments']=[];files['plan.json']={'voice':{'persona_name':'Unpublished'}};files['deck.json']['slides']=[]
        with patch.object(store,'load',return_value={'approvals':{'script':False},'settings':{'language':'hi-IN'}}) as draft:
            after=pitch.plan_pitch('fixture',profile,voice_it=False,expected_snapshot_id='kb_fixture',expected_demo_version=2)
        check('unpublished edits and false draft approval cannot alter live published pitch',before==after and prompt_before==pinned_model.call_args.args[0] and not draft.called and after['demo_version']==2)
    with patch.object(pitch.runtime,'structured',side_effect=AssertionError('Must reject before model')):
        blocked=[]
        for expected in [{'expected_snapshot_id':'kb_old'},{'expected_demo_version':1}]:
            try:pitch.plan_pitch('fixture',profile,voice_it=False,**expected)
            except pitch.PublishedDemoChanged:blocked.append(True)
        check('snapshot and same-evidence publication-version mismatch fail before model',len(blocked)==2)
    from server import runtime_graph as graph, runtime_state
    async def visit():
        with patch.object(store,'write_json',side_effect=lambda _id,name,value:files.__setitem__(name,copy.deepcopy(value))),patch.object(graph.usage,'trace'),patch.object(pitch.runtime,'structured',return_value=proposal) as model:
            first=await graph.run_turn('fixture',{'session_id':'pinned_version','profile':profile,'demo_version':2},kind='explore')
            saved=runtime_state.previous_state('fixture','pinned_version')
            files['bundle.json']['version']=3
            second=await graph.run_turn('fixture',{'session_id':'pinned_version','profile':profile,'demo_version':3},kind='explore')
            return first,second,saved,model.call_count
    first,second,saved,calls=asyncio.run(visit())
    check('actual runtime checkpoint pins first publication and rejects later build with same evidence',saved['demo_version']==2 and first['result']['demo_version']==2 and second['result'].get('publication_changed') and not second['result']['provider_failed'] and not second['result']['route'] and calls==1)
    check('all controls avoid outbound calls',not any(p.called for p in sockets))
print(f'Pitch delivery contracts: {len(passed)}/{len(passed)}')

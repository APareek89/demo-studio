"""Free real-path authoring, style/cache, overview and personalized-script contracts."""
from __future__ import annotations
import copy
import sys
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run(check):
    from server import config, schemas, store
    from server.agents import author, pitch, speech_style, translate, voice
    from server.llm import mock
    with tempfile.TemporaryDirectory(prefix='speech-style-') as tmp, ExitStack() as stack:
        stack.enter_context(patch.multiple(config, DATA_DIR=Path(tmp), MOCK_LLM=True))
        blocked = [stack.enter_context(patch(n, side_effect=AssertionError('No outbound calls'))) for n in ('socket.create_connection','socket.socket.connect','socket.socket.connect_ex')]
        stack.enter_context(patch.object(voice, '_TRIPPED', {}))
        demo = store.new_demo('Speech contract'); did = demo['id']
        store.update(did, lambda d: d['settings'].update(tts_provider='sarvam',voice_locked=True,sarvam_speaker='priya',language='en-IN'))
        store.update(did, lambda d: d['approvals'].update(script=True))
        store.write_json(did,'plan.json',{'voice':{'persona_description':'A helpful cheerful guide','tone':'warm'},'segments':[],'ctas':[]})
        calls=[]
        def tts(text,speaker,lang,**kw):
            calls.append((text,speaker,lang,kw));return mock.silent_wav(12.2),'wav'
        stack.enter_context(patch.object(voice.sarvam,'tts',side_effect=tts))
        text='Explore the cabin, at your own pace.'
        a=voice.render_line(did,text,delivery={'tone':'calm'})
        b=voice.render_line(did,text,delivery={'tone':'calm'})
        c=voice.render_line(did,text,delivery={'tone':'upbeat'})
        check('delivery: matching effective style reuses cache; pace change records separately',a==b and c!=a and len(calls)==2 and calls[0][3]['pace']==.96 and calls[1][3]['pace']==1.03)
        plan=store.read_json(did,'plan.json');plan['voice']['tone']='calm';store.write_json(did,'plan.json',plan)
        d=voice.render_line(did,text,delivery={'tone':'upbeat'})
        check('delivery: changed persona invalidates cache without changing locked Priya',d!=c and len(calls)==3 and all(row[1]=='priya' for row in calls))
        raw='[cheerful] Hello. <break time="1s"/> Take a look.'
        prepared=speech_style.prepare(raw,{'tone':'reassuring','pace':50})
        voice.render_line(did,raw,delivery={'tone':'reassuring'})
        check('delivery: tags never reach provider or captions, pace is finite and bounded',prepared=={'text':'Hello. Take a look.','plain_text':'Hello. Take a look.','pace':1.08} and calls[-1][0]=='Hello. Take a look.' and speech_style.prepare('Hi',{'pace':float('nan')})['pace']==1)
        fact={'id':'F1','kind':'feature','claim':'Front seat ventilation','value':'Ventilated front seats','approved':True,'conditions':'Selected variants only','source':{'ref':'official','quote':'Front row ventilated seats','locator':'page 14'}}
        und={'product':{'name':'Fixture'},'facts':[fact],'shots':[],'images':[]}
        line={'id':'cabin-L1','text':'Selected variants offer ventilated front seats.','fact_ids':['F1'],'visual':{'kind':'none','ref':''},'delivery':{'tone':'upbeat','pace':1.03}}
        overview={**copy.deepcopy(line),'text':'Start with the cabin: selected variants offer ventilated front seats. We can explore the seating first, then choose the details that matter most to you.'}
        script={'segments':[{'id':'cabin','role':'proof','topic':'comfort','title':'Cabin','lines':[line],'deeper':[],'checkin':'Does that matter to you?'}],'closing':[],'intake_q1':'What would you like to explore?','intake_q2':'','overview':overview}
        issues=author.validate(script,und)
        author._assign_ids(script)
        check('overview: separately validated and assigned without inserting duplicate narration',not issues and script['runtime_overview']['id']=='runtime-overview' and len(script['segments'])==1 and script['runtime_overview']['fact_ids']==['F1'])
        store.write_json(did,'script.json',script)
        voiced=voice._render_one(did,lambda message:None,store.load(did),'script.json',None)
        check('overview: actual same-voice WAV duration and evidence preserved',voiced['runtime_overview']['duration_seconds']==12.2 and voiced['runtime_overview']['duration_exact'] and voiced['runtime_overview']['duration_in_range'] and voiced['runtime_overview']['fact_ids']==['F1'])
        bad=copy.deepcopy(script);bad['segments'][0]['lines'][0]['text']='The DCT gives you imperceptible gear shifts.'
        issues=author.validate(bad,und)
        check('author: source ID does not authorize an invented gearbox outcome',bad['segments'][0]['lines'][0]['unverified'] and any('transmission evidence' in item for item in issues))
        technical=copy.deepcopy(script);technical['segments'][0]['lines'][0]['text']='Explore the ADAS and DCT.'
        check('author: everyday main speech flags automotive jargon',any('jargon' in item for item in author.validate(technical,und)))
        store.write_json(did,'understanding.json',und)
        proposed=schemas.PitchPlan(customer_state='stated_need',decision_frame="Let's begin with the cabin.",follow_up_question='',primary_outcome='Seating',focus_topics=['comfort'],route=[schemas.RouteStep(segment_id='cabin')],advance='Explore the cabin.',personalized_segments=[schemas.PersonalizedSegment(segment_id='cabin',customer_quote='warm afternoons',lines=[schemas.LineOut.model_validate(line)])])
        with patch.object(pitch.runtime,'structured',return_value=proposed),patch.object(voice,'render_line',side_effect=AssertionError('Must not block on TTS')):
            result=pitch.plan_pitch(did,{'why':'I travel on warm afternoons'},voice_it=False,timeout_budget_s=3)
            unseen=pitch.plan_pitch(did,{'why':'I travel on warm afternoons'},voice_it=False,seen_segment_ids=['cabin'])
        replacement=result['personalized_segments'][0]
        check('personalization: customer framing replaces speech, preserves sourced sentence/style and callout index',len(replacement['lines'])==2 and 'warm afternoons' in replacement['lines'][0]['text'] and replacement['lines'][0]['base_line_index'] is None and replacement['lines'][1]['base_line_index']==0 and replacement['lines'][1]['text']==line['text'] and replacement['lines'][1]['delivery']==line['delivery'] and not result['custom_batches'])
        check('personalization: seen segments cannot replay',not unseen['route'] and not unseen['personalized_segments'])
        proposed.personalized_segments[0].lines[0].text='Ventilated seats eliminate discomfort in all weather.'
        with patch.object(pitch.runtime,'structured',return_value=proposed):
            rejected=pitch.plan_pitch(did,{'why':'I travel on warm afternoons'},voice_it=False)
        check('personalization: unsupported rewrite falls back to unchanged reviewed speech',not rejected['personalized_segments'] and rejected['script_segments'][0]['lines'][0]['text']==line['text'])
        source=store.read_json(did,'script.json');source['runtime_overview']['text']='A quoted 12 km route.';store.write_json(did,'script.json',source)
        translated=translate.TScript(segments=[translate.TSegment(id='cabin',title='Cabin',lines=[translate.TLine(id='cabin-L1',text='Selected variants offer ventilated front seats.')],checkin='Does that matter to you?')],closing=[],intake_q1='What would you like to explore?',intake_q2='',overview=translate.TLine(id='runtime-overview',text='बताया गया रास्ता 12 km है।'))
        with patch.object(config,'MOCK_LLM',False),patch.object(translate.claude,'structured',return_value=translated) as model:
            alternate=translate.translate(did,'hi-IN',lambda _:None)
            source['runtime_overview'].update(audio='audio/other.wav',duration_seconds=10);store.write_json(did,'script.json',source)
            repeated=translate.translate(did,'hi-IN',lambda _:None)
            check('translation: overview keeps citations/style, clears source audio and reuses semantic translation',alternate['runtime_overview']['text']==translated.overview.text and alternate['runtime_overview']['fact_ids']==['F1'] and alternate['runtime_overview']['delivery']==line['delivery'] and 'audio' not in alternate['runtime_overview'] and repeated==alternate and model.call_count==1)
            translated.overview.text='बताया गया रास्ता 12 है।';store.path(did,translate.script_path('hi-IN')).unlink()
            held=translate.translate(did,'hi-IN',lambda _:None)
            check('translation: a dropped overview quantity unit is held before speech',held['runtime_overview']['unverified'] and held['runtime_overview']['translation_issue'])
        check('all contracts: no outbound calls',not any(call.called for call in blocked))

if __name__=='__main__':
    rows=[]
    def check(name,ok,detail=''):
        rows.append(bool(ok));print(('PASS ' if ok else 'FAIL ')+name)
    run(check)
    print(f'Speech style contracts: {sum(rows)}/{len(rows)}')
    raise SystemExit(0 if all(rows) else 1)

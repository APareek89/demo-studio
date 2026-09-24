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
    from server.agents import author, pitch, plan as planner, speech_style, translate, voice
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
        script={'segments':[{'id':'cabin','role':'proof','topic':'comfort','title':'Cabin','lines':[line],'deeper':[],'checkin':'Let’s keep exploring.'}],'closing':[],'intake_q1':'What would you like to explore?','intake_q2':'','overview':overview}
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
        sparse=copy.deepcopy(script);sparse['segments']=[]
        for index in range(7):
            segment=copy.deepcopy(script['segments'][0]);segment.update(id=f'part-{index}',role='features' if index==6 else 'proof',checkin='Let’s keep exploring.' if index in [0,3] else '')
            sparse['segments'].append(segment)
        check('author: two closing statements across seven sections pass without a reply gate',not author.validate(sparse,und) and sum(bool(segment['checkin']) for segment in sparse['segments'])==2)
        unsafe=copy.deepcopy(sparse);unsafe['segments'][1]['lines'][0]['text']='Would you like to see more?';unsafe['segments'][2]['checkin']='Would you like six airbags?'
        sparse_issues=author.validate(unsafe,und)
        check('author: sparse cadence still rejects hidden questions and uncited claims in checkins',any('narration must use statements' in issue for issue in sparse_issues) and any('checkin contains a figure or claim' in issue for issue in sparse_issues) and unsafe['segments'][2]['checkin']=='')
        incompatible=['Would you like a closer look here, or shall we continue?', "Anything you'd like to check about the seats or boot?", 'Would you like to compare these options, or keep exploring?', 'Do you need more detail?', 'Should we take a closer look?']
        meaning_warnings=[]
        for prompt in incompatible:
            trial=copy.deepcopy(script);trial['segments'][0].update(checkin=prompt,checkin_audio='audio/reviewed.wav')
            warnings=author.validate(trial,und);segment=trial['segments'][0]
            meaning_warnings.append(any('never a question' in row for row in warnings) and segment['checkin']==prompt and segment['checkin_audio']=='audio/reviewed.wav' and not segment['lines'][0]['unverified'])
        check('author: question checkins require repair while reviewed text and audio remain unchanged',all(meaning_warnings))
        compatible=['Let’s keep exploring.', 'On to the next part.', 'That brings us to the next stop.', '']
        meaning_valid=[]
        for prompt in compatible:
            trial=copy.deepcopy(script);trial['segments'][0]['checkin']=prompt
            meaning_valid.append(not author.validate(trial,und))
        check('author: short closing statements and empty checkins remain valid',all(meaning_valid))
        trial=copy.deepcopy(script);trial['segments'][0].update(checkin='Ready to continue？',checkin_audio='audio/old.wav')
        check('author: full-width question mark requires repair without mutating reviewed text or audio',any('never a question' in row for row in author.validate(trial,und)) and trial['segments'][0]['checkin']=='Ready to continue？' and trial['segments'][0]['checkin_audio']=='audio/old.wav')
        trial=copy.deepcopy(script);trial['segments'][0]['checkin']='It includes six airbags.'
        check('author: a declarative checkin cannot bypass citation requirements',any('without citations' in row for row in author.validate(trial,und)) and trial['segments'][0]['checkin']=='')
        from server.agents import principles
        check('author: all active authoring instructions agree checkins never wait',
              'Segment checkins stay empty.' in planner.PLAN_SYSTEM and 'one short closing statement' in author.AUTHOR_SYSTEM
              and 'never a question' in schemas.SegmentOut.model_fields['checkin'].description
              and 'Narration never waits' in principles.AUTHOR_CRAFT
              and 'yes continues' not in '\n'.join([author.AUTHOR_SYSTEM, principles.PITCH_SHAPE, principles.PROOF_BLOCK]))
        trial=copy.deepcopy(script);trial['intake_q1']='Would you like to tell me what matters most, or shall we get started?'
        check('author: closing-statement rule does not constrain the separate open intake flow',not author.validate(trial,und) and trial['intake_q1'].startswith('Would you like'))
        everyday_phrases=['The body measures 4330 mm in length.', 'Dimensions: 4330mm.', 'A four-cylinder engine.', 'Quad-beam lamps and a parametric grille.', 'A dual-clutch automatic.']
        warned=[]
        for phrase in everyday_phrases:
            trial=copy.deepcopy(script);trial['segments'][0]['lines'][0]['text']=phrase
            warnings=author.validate(trial,und)
            warned.append(any('everyday register warning' in row for row in warnings) and not trial['segments'][0]['lines'][0]['unverified'] and trial['segments'][0]['lines'][0]['text']==phrase)
        check('author: observed everyday dimensions and component labels warn without withholding cited speech',all(warned))
        deeper=copy.deepcopy(script);deeper['segments'][0]['deeper']=[{**copy.deepcopy(line),'text':'A four-cylinder engine with a dual-clutch gearbox and 4330 mm length.'}]
        expert=copy.deepcopy(deeper);expert['segments'][0]['lines'][0]['text']=deeper['segments'][0]['deeper'][0]['text']
        check('author: requested technical audience and deeper lines retain complete quantities without register warnings',not any('register warning' in row for row in author.validate(deeper,und)) and not any('register warning' in row for row in author.validate(expert,und,'technical')) and not expert['segments'][0]['lines'][0]['unverified'])
        anywhere=copy.deepcopy(script);anywhere['segments'][0]['checkin']='The dual-clutch details are available separately.';anywhere['closing']=[{**copy.deepcopy(line),'text':'Explore the parametric grille.'}];anywhere['runtime_overview']['text']='Start with the cabin and its parametric design: selected variants offer ventilated front seats. We can explore seating first, then the details you choose.'
        warnings=author.validate(anywhere,und)
        check('author: overview closing and checkin receive the same warning-only register review',all(any(place in row and 'register warning' in row for row in warnings) for place in ['Explore overview','closing 1','checkin']) and not anywhere['runtime_overview']['unverified'] and anywhere['segments'][0]['checkin']=='The dual-clutch details are available separately.')
        saved_plan=store.read_json(did,'plan.json')
        plan_und={**und,'brand':{},'unknowns':[]};store.write_json(did,'understanding.json',plan_und)
        authored=mock.fake(schemas.Plan);authored.voice.persona_name='Karan';authored.voice.persona_description='Karan is a helpful guide. He explains choices in his own words.';authored.voice.sample_line="Hi, I'm Karan. Let's explore.";authored.intake.q1="I'm Karan. What would you like to explore?"
        with patch.object(planner.claude,'structured',return_value=authored) as model:
            selected=planner.run(did,lambda _:None)
            envelope=model.call_args.args
        check('plan: actual generation gets configured identity and observed grounding examples', 'CONFIGURED VOICE:' in envelope[1] and '"speaker": "priya"' in envelope[1] and 'every engine offers manual or automatic' in envelope[0] and 'assured stopping' in envelope[0])
        check('plan: locked Priya identity overrides generated name and neutralizes persona without changing model object',selected['voice']['persona_name']=='Priya' and selected['voice']['suggested_voice']=='priya' and 'Karan' not in selected['voice']['sample_line']+selected['intake']['q1'] and 'He ' not in selected['voice']['persona_description'] and 'his ' not in selected['voice']['persona_description'] and authored.voice.persona_name=='Karan')
        store.write_json(did,'plan.json',authored.model_dump())
        with patch.object(planner.claude,'structured',return_value=authored):
            revised=planner.run(did,lambda _:None,instruction='Reorder the cabin segment')
            store.update(did,lambda demo:demo['settings'].update(voice_locked=False))
            unlocked=planner.run(did,lambda _:None)
        check('plan: preserved revision fields cannot restore wrong locked identity; unlocked persona stays editable',revised['voice']['persona_name']=='Priya' and unlocked['voice']['persona_name']=='Karan')
        store.update(did,lambda demo:demo['settings'].update(voice_locked=True))
        seed='https://example.com/in/en/find-a-car/creta/highlights'
        urls={'brochure':'https://example.com/content/dam/in/en/creta.pdf','dealer':'https://example.com/in/en/find-a-dealer-and-website','test_drive':'https://example.com/in/en/creta-request-a-test-drive?id=creta&prod=creta'}
        links=[{'url':u,'label':k} for k,u in urls.items()]+[{'url':'https://example.com/in/en/exter-request-a-test-drive?id=exter','label':'Other car'},{'url':'https://example.com/content/dam/ng/en/creta.pdf','label':'Wrong market'},{'url':'https://evil.example/creta.pdf','label':'CRETA brochure'},{'url':seed,'label':'Download brochure'}]
        store.write_json(did,'knowledge/cta-links.json',{'links':links})
        store.update(did,lambda demo:demo.update(product={'name':'Hyundai CRETA','url':seed},sources=[{'id':'src-cta','role':'product','url':seed,'evidence_path':'knowledge/cta-links.json'}]))
        authored.ctas=[schemas.CTA(id='brochure',label='Download Brochure',kind='link',url=seed,primary=False,when='always'),schemas.CTA(id='dealer',label='Locate Dealer',kind='contact',url=seed,primary=False,when='always'),schemas.CTA(id='drive',label='Book a Test Drive',kind='book',url=seed,primary=True,when='end')]
        authored.advance='Choose Download Brochure.'
        with patch.object(planner.claude,'structured',return_value=authored) as model:
            linked=planner.run(did,lambda _:None)
        check('plan: source action URLs reach actual planner and replace misleading highlights destinations',set(row['url'] for row in linked['ctas'])==set(urls.values()) and all(u in model.call_args.args[1] for u in urls.values()))
        choices=planner._action_urls(did,store.load(did))
        check('plan: CTA candidates exclude other model market host and label-only download claims',len(choices)==3 and {row['url'] for row in choices}==set(urls.values()))
        store.write_json(did,'knowledge/cta-links.json',{'links':[]})
        with patch.object(planner.claude,'structured',return_value=authored):
            absent=planner.run(did,lambda _:None)
        check('plan: missing destinations become honest local contact requests with matching advance',all(not row['url'] and row['kind']=='contact' for row in absent['ctas']) and absent['ctas'][0]['label']=='Ask about a brochure' and absent['ctas'][1]['label']=='Ask about a dealer' and absent['advance']=='Choose Ask about a brochure.')
        store.write_json(did,'plan.json',saved_plan)
        store.write_json(did,'understanding.json',und)
        store.write_json(did,'bundle.json',{'id':did,'version':1,'knowledge_snapshot_id':'kb_speech_fixture','product':und['product'],'facts':und['facts'],'segments':store.read_json(did,'script.json')['segments'],'pitch':{},'voice':{'persona':saved_plan['voice']},'ctas':[],'slides':[],'media':{'images':[]},'language':'en-IN'})
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
        rejected_lines=rejected['personalized_segments'][0]['lines']
        check('personalization: unsupported rewrite falls back to marked reviewed speech without admitting the claim',rejected['personalized_segments'][0]['personalization_basis']=='reviewed_route_fallback' and rejected_lines[-1]['text']==line['text'] and all('eliminate discomfort' not in item['text'] for item in rejected_lines) and rejected['script_segments'][0]['lines'][0]['text']==line['text'])
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

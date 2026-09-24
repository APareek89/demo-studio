"""Selected 1–5 minute duration: real drafting, WAVs, publication and pinned tours."""
from __future__ import annotations
import copy
import json
import unittest
import time
from unittest.mock import patch
from narration_preparation_contract import fixture, draft, record, author, bundle, deck, narration, pitch, plan, schemas, store, voice, OUTBOUND
from fastapi.testclient import TestClient
from server import graph
from server.app import app

EXTRA = [
"The outer mirrors fold using a switch on the driver door. Their adjustment control sits beside that switch, with a separate selector for the left and right mirror before changing the position of either glass. The switch is illuminated.",
"The rear window has a wiper mounted below the glass. Its control is on the steering column stalk, separate from the rear screen heater button on the dashboard, so the two functions can be selected independently.",
"The bonnet release sits beneath the dashboard near the driver door. After that release is pulled, a second catch beneath the bonnet edge must be moved before the bonnet can be lifted for access to the engine compartment.",
"The spare wheel sits beneath the luggage floor beside the vehicle tool kit. A retaining fastener holds it in its storage position, and the equipment guide shows where to find that fastener before lifting the wheel out.",
"The fuel flap release is positioned beside the driver seat. The filler cap remains attached by a tether when opened, and a holder on the flap keeps the cap away from the bodywork during refuelling.",
"The windscreen washer reservoir has a marked cap within the engine compartment. The equipment guide identifies the reservoir separately from the coolant tank, helping the owner locate the correct filler before following the specified maintenance procedure.",
"The passenger sun visor includes a covered vanity mirror. Its cover slides sideways while the visor remains lowered, allowing the passenger to close the mirror without raising the entire visor back against the roof lining.",
"The rear door child lock is set using a control at the door edge. Once engaged, that door cannot be opened with its inside handle; the equipment guide describes how to disengage it before restoring normal handle operation.",
"The luggage cover attaches to supports at both sides of the boot. Its lifting cords connect to the tailgate, while releasing those connections allows the cover to be removed when carrying taller items in the loading space.",
]

def duration_fixture(minutes):
    und, p = fixture()
    if minutes == 1:
        p['segments'] = [s for s in p['segments'] if s['role'] in ('intro', 'outcome') or s['id'] == 'seat']
    elif minutes == 2:
        p['segments'] = [s for s in p['segments'] if s['role'] not in ('features', 'establish')]
    elif minutes in (4,5):
        for i, text in enumerate(EXTRA[:5] if minutes == 4 else EXTRA):
            fid = f'EX{i}'
            und['facts'].append({'id':fid,'kind':'feature','claim':text.split('.')[0], 'value':text,
                'approved':True,'source':{'ref':'fixture-guide','locator':f'additional paragraph {i}','quote':text}})
            s = copy.deepcopy(p['segments'][3])
            s.update(id=f'extra{i}', title=f'Additional control {i}', fact_ids=[fid], fundamental=False,
                     word_budget=author.words(text))
            p['segments'].insert(-2,s)
    return und,p

class DurationPreferenceContract(unittest.TestCase):
    def setUp(self):
        self.did=store.new_demo('Selected duration fixture')['id']
        store.update(self.did,lambda d:d['settings'].update(tts_provider='sarvam',sarvam_speaker='priya',voice_locked=True,language='en-IN',languages=[]))
        self.api=TestClient(app)
    def tearDown(self): self.assertEqual(OUTBOUND,[])
    def select(self,minutes): return self.api.patch(f'/api/demos/{self.did}',json={'settings':{'pitch_minutes':minutes}})
    def prepare(self,minutes):
        self.assertEqual(self.select(minutes).status_code,200)
        und,p=duration_fixture(minutes)
        store.write_json(self.did,'understanding.json',und)
        store.write_json(self.did,'plan.json',p)
        prepared=plan.prepare_existing(self.did)
        def model(system,content,schema,**kwargs):
            actual=json.loads(content.split('\nPLAN: ',1)[1].split('\n\nFACT REGISTRY',1)[0])
            self.assertEqual(actual['guided_minimum_seconds'],minutes*60)
            return schemas.ScriptOut.model_validate(draft(actual,und['facts'],complete=True))
        with patch.object(author.claude,'structured',side_effect=model),patch.object(author.visuals,'align',side_effect=lambda did,sc,und,emit:sc):
            sc=author.run(self.did,lambda *_:None)
        return und,prepared,sc
    def build(self,minutes):
        und,p,sc=self.prepare(minutes)
        self.assertEqual(sc['narration_preparation']['status'],'ready',sc['issues'])
        self.assertEqual(p['total_words'],minutes*165)
        record(self.did,sc,wps=2.5)
        sc.update(voice_provider='sarvam',voice_name='priya')
        store.write_json(self.did,'script.json',sc)
        sc['voice_input_hash']=voice.input_hash(self.did)
        store.write_json(self.did,'script.json',sc)
        deck.build(self.did,lambda *_:None)
        store.update(self.did,lambda d:d['approvals'].update({card:True for card in store.CARDS}))
        b=bundle.build(self.did,lambda *_:None)
        self.assertEqual(b['runtime']['narration_minimum']['minimum_seconds'],minutes*60)
        self.assertTrue(b['runtime']['narration_minimum']['measured'])
        self.assertGreaterEqual(b['runtime']['narration_minimum']['seconds'],minutes*60)
        return b,sc
    def test_default_is_three_minutes(self):
        self.assertEqual(store.load(self.did)['settings']['pitch_minutes'],3)
        self.assertEqual(narration.word_target({}),495)
    def test_all_selections_have_distinct_targets_and_identities(self):
        ids=set()
        for m in (1,2,3,4,5):
            d={'settings':{'pitch_minutes':m}}
            self.assertEqual(narration.minimum_seconds(d),m*60)
            self.assertEqual(narration.word_target(d),m*165)
            ids.add(narration.preparation_identity(d))
        self.assertEqual(len(ids),5)
    def test_invalid_api_duration_rejects_entire_write(self):
        before=store.path(self.did,'demo.json').read_bytes()
        for bad in (0,6,-1,1.5,3.0,'2',None,True,[],{}):
            r=self.api.patch(f'/api/demos/{self.did}',json={'name':'Must not save','settings':{'pitch_minutes':bad}})
            self.assertEqual(r.status_code,400,(bad,r.text))
            self.assertEqual(store.path(self.did,'demo.json').read_bytes(),before)
    def test_running_work_cannot_change_duration(self):
        with patch.object(graph,'is_running',return_value=True): self.assertEqual(self.select(1).status_code,409)
        self.assertEqual(store.load(self.did)['settings']['pitch_minutes'],3)
    def test_change_resets_only_dependent_review_and_stages(self):
        def ready(d):
            d.update(status='ready');d['approvals'].update({c:True for c in store.CARDS})
            for s in d['stages'].values():s['status']='done'
        store.update(self.did,ready)
        published={'version':7,'runtime':{'narration_minimum':{'minimum_seconds':180}}}
        store.write_json(self.did,'bundle.json',published)
        self.select(1);d=store.load(self.did)
        self.assertEqual(d['status'],'align')
        for c in store.CARDS:self.assertEqual(d['approvals'][c],c not in ('script','visuals'))
        for stage in ('plan','author','deck','voice','rehearsal','bundle'):self.assertEqual(d['stages'][stage]['status'],'stale')
        for stage in ('understand','coach','faq'):self.assertEqual(d['stages'][stage]['status'],'done')
        self.assertEqual(store.read_json(self.did,'bundle.json'),published)
    def test_lower_duration_reprepares_actual_build_and_returns_to_review(self):
        self.build(3)
        store.update(self.did,lambda d:[stage.update(status='done') for stage in d['stages'].values()])
        old_script=store.read_json(self.did,'script.json')
        old_plan=store.read_json(self.did,'plan.json')
        publication={name:store.path(self.did,name).read_bytes() for name in ('bundle.json','knowledge/published.json','understanding.json')}
        version=store.load(self.did)['version']
        self.assertEqual(self.select(1).status_code,200)
        status=narration.preparation_status(self.did)
        self.assertEqual(status['status'],'needs_preparation')
        self.assertTrue(status['duration_changed'])
        self.assertIn('prepared for 3 minutes',status['reason'])
        # Legacy preparation enters through the existing explicit Build action;
        # these approvals cannot authorize the newly generated words.
        for card in ('script','visuals'):
            self.assertEqual(self.api.post(f'/api/demos/{self.did}/approve/{card}').status_code,200)
        calls=[]
        def model(system,content,schema,**kwargs):
            actual=json.loads(content.split('\nPLAN: ',1)[1].split('\n\nFACT REGISTRY',1)[0])
            calls.append(actual)
            self.assertEqual((actual['total_words'],actual['guided_minimum_seconds']),(165,60))
            return schemas.ScriptOut.model_validate(draft(actual,store.read_json(self.did,'understanding.json')['facts'],complete=False))
        with patch.object(author.claude,'structured',side_effect=model),patch.object(author.visuals,'align',side_effect=lambda did,sc,und,emit:sc),patch.object(voice,'render_script',side_effect=AssertionError('Changed duration must return for review before Voice')) as speech:
            response=self.api.post(f'/api/demos/{self.did}/build')
            self.assertEqual(response.status_code,200,response.text)
            deadline=time.monotonic()+20
            while graph.is_running(self.did) and time.monotonic()<deadline:time.sleep(.01)
            self.assertFalse(graph.is_running(self.did))
            speech.assert_not_called()
        self.assertTrue(calls)
        state=store.load(self.did)
        self.assertEqual(state['status'],'align',state['stages'])
        self.assertFalse(state['approvals']['script']);self.assertFalse(state['approvals']['visuals'])
        revised=store.read_json(self.did,'script.json');replanned=store.read_json(self.did,'plan.json')
        self.assertEqual(replanned['narration_preparation']['target_words'],165)
        self.assertEqual(narration.preparation_status(self.did)['status'],'ready')
        self.assertFalse(narration.preparation_status(self.did)['duration_changed'])
        self.assertLess(narration.preparation_report(revised)['words'],narration.preparation_report(old_script)['words'])
        for key in ('voice','ctas'):self.assertEqual(replanned.get(key),old_plan.get(key))
        for name,data in publication.items():self.assertEqual(store.path(self.did,name).read_bytes(),data)
        self.assertEqual(store.load(self.did)['version'],version)

    def test_manual_edit_after_duration_change_stays_incomplete_without_automatic_overwrite(self):
        self.build(3);self.assertEqual(self.select(1).status_code,200)
        script=store.read_json(self.did,'script.json');line=script['segments'][2]['lines'][0]
        text='The front seat slides.'
        with patch.object(author.visuals,'align',side_effect=AssertionError('Blocked draft cannot run image audit')):
            response=self.api.patch(f'/api/demos/{self.did}/align/script',json={'lines':[{'id':line['id'],'text':text,'fact_ids':line['fact_ids']}]})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['cards']['script']['preparation']['status'],'incomplete')
        self.assertEqual(self.api.post(f'/api/demos/{self.did}/approve/script').status_code,409)
        before=store.path(self.did,'script.json').read_bytes()
        store.update(self.did,lambda d:d['approvals'].update({card:True for card in store.CARDS}))
        self.assertEqual(self.api.post(f'/api/demos/{self.did}/build').status_code,409)
        self.assertEqual(store.path(self.did,'script.json').read_bytes(),before)
        self.assertIn(text,before.decode())

    def test_voice_change_without_duration_change_retains_recording_recovery(self):
        self.build(3)
        store.update(self.did,lambda d:d['settings'].update(sarvam_speaker='shubh'))
        status=narration.preparation_status(self.did)
        self.assertFalse(status['duration_changed'])
        self.assertEqual(status['status'],'needs_recording')

    def test_identical_duration_keeps_approvals(self):
        store.update(self.did,lambda d:d['approvals'].update({c:True for c in store.CARDS}))
        self.select(3);self.assertTrue(all(store.load(self.did)['approvals'].values()))
    def test_one_minute_actual_author_recording_and_bundle(self):self.build(1)
    def test_two_minute_actual_author_recording_and_bundle(self):self.build(2)
    def test_three_minute_actual_author_recording_and_bundle(self):self.build(3)
    def test_four_minute_actual_author_recording_and_bundle(self):self.build(4)
    def test_five_minute_actual_author_recording_and_bundle(self):self.build(5)
    def test_selected_languages_enforce_selected_minimum_not_180(self):
        for minutes in (1,2,3,5):
            with self.subTest(minutes=minutes):
                # A fresh identity prevents a prior recording calibration entering the next fixture.
                self.did=store.new_demo('Selected language duration')['id']
                store.update(self.did,lambda d:d['settings'].update(tts_provider='sarvam',sarvam_speaker='priya',voice_locked=True,languages=[]))
                _,sc=self.build(minutes)
                store.update(self.did,lambda d:d['settings'].update(languages=['en-IN','hi-IN']))
                sc['voice_input_hash']=voice.input_hash(self.did);store.write_json(self.did,'script.json',sc)
                alt=copy.deepcopy(sc)
                words=narration.preparation_report(alt)['words']
                record(self.did,alt,wps=words/(minutes*60+3),prefix='hindi-pass')
                store.write_json(self.did,'script.hi-IN.json',alt)
                self.assertEqual(narration.preparation_status(self.did)['status'],'ready')
                published=bundle.build(self.did,lambda *_:None)
                self.assertEqual(published['alt_languages']['hi-IN']['narration_minimum']['minimum_seconds'],minutes*60)
                previous=store.path(self.did,'bundle.json').read_bytes()
                previous_version=store.load(self.did)['version']
                record(self.did,alt,wps=words/(minutes*60-3),prefix='hindi-short')
                store.write_json(self.did,'script.hi-IN.json',alt)
                status=narration.preparation_status(self.did)
                self.assertEqual(status['status'],'needs_preparation')
                self.assertEqual(status['minimum_seconds'],minutes*60)
                with self.assertRaises(narration.NarrationTooShort):bundle.build(self.did,lambda *_:None)
                self.assertEqual(store.path(self.did,'bundle.json').read_bytes(),previous)
                self.assertEqual(store.load(self.did)['version'],previous_version)
    def test_runtime_uses_published_duration_despite_draft_changes(self):
        for minutes in (1,2,3,5):
            with self.subTest(minutes=minutes):
                self.did=store.new_demo('Published tour duration')['id']
                store.update(self.did,lambda d:d['settings'].update(tts_provider='sarvam',sarvam_speaker='priya',voice_locked=True,languages=[]))
                b,sc=self.build(minutes)
                self.select(5 if minutes !=5 else 1)
                choice=schemas.PitchPlan(customer_state='unknown',decision_frame='',follow_up_question='',primary_outcome='',focus_topics=[],advance='',route=[])
                with patch.object(pitch.runtime,'structured',return_value=choice):visit=pitch.plan_pitch(self.did,{},voice_it=False)
                self.assertEqual(visit['narration_minimum']['minimum_seconds'],minutes*60)
                self.assertGreaterEqual(visit['narration_minimum']['seconds'],minutes*60)
                self.assertTrue(set(x['segment_id'] for x in visit['route']) <= {x['segment_id'] for x in b['slides']})
    def test_recorded_shortfall_reports_selected_threshold_and_preserves_publication(self):
        for minutes in (1,2,3,5):
            und,p,sc=self.prepare(minutes)
            # Build remains a hard measured gate, even when prepared words are sufficient.
            record(self.did,sc,wps=100,prefix=f'too-short-{minutes}')
            with self.assertRaises(narration.NarrationTooShort) as raised:
                narration.require_minimum(sc,demo_id=self.did,require_recorded=True,minimum_seconds=minutes*60)
            self.assertIn(f'at least {minutes*60}s',str(raised.exception))
            self.assertEqual(raised.exception.result['minimum_seconds'],minutes*60)
    def test_shorter_selection_does_not_reuse_old_calibrated_target(self):
        und,p,sc=self.prepare(5)
        self.select(1)
        self.assertEqual(narration.word_target(store.load(self.did),sc,self.did),165)
    def test_sources_selector_matches_backend_values(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parents[1]/'web/studio/sources.js').read_text()
        self.assertIn('id: "source-duration"',source)
        self.assertIn('[1, 2, 3, 4, 5]',source)
        self.assertIn('pitch_minutes: Number(durationSel.value)',source)
        self.assertIn('await ctx.ensureDemo()',source)

if __name__=='__main__': unittest.main()

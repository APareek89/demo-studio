"""Free human-checkpoint, semantic reuse and durable SSE contracts; no provider calls."""
from __future__ import annotations
import copy
import sys
import tempfile
import threading
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def run(check):
    from server import cloud, config, events, graph, media, orchestrator as orch, schemas, store
    from server.llm import gemini
    from server.agents import rehearsal
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import Command
    with tempfile.TemporaryDirectory(prefix='build-hardening-') as tmp, ExitStack() as stack:
        stack.enter_context(patch.multiple(config,DATA_DIR=Path(tmp),MOCK_LLM=True))
        stack.enter_context(patch.object(cloud,'enabled',return_value=False))
        stack.enter_context(patch.object(cloud,'sync_demo_async'))
        stack.enter_context(patch.object(cloud,'put_event'))
        # This graph-plumbing section already stubs Author, Voice and Bundle.
        # Its three-word candidate is not a customer script. Real automatic
        # readiness is covered by automatic_narration_contract/release_mock_contract;
        # keep the separate rehearsal-cache section below outside this fixture.
        stack.enter_context(patch.object(orch.narration,'preparation_status',return_value={
            'status':'ready','mock_preview':False,'target_words':495,'words':495,
            'attempts':0,'missing_words':0,'measured':False,'seconds':180,
            'basis':'synthetic graph-plumbing fixture','reason':'Explicit graph-plumbing fixture','errors':[]}))
        print('PREPARATION FIXTURE: synthetic only inside graph-plumbing stage stubs; automatic/release contracts use real readiness')
        blocked=[stack.enter_context(patch(n,side_effect=AssertionError('No outbound calls'))) for n in ('socket.create_connection','socket.socket.connect','socket.socket.connect_ex')]
        demo=store.new_demo('Hardening fixture');did=demo['id']
        with patch.object(gemini,'client',side_effect=AssertionError('Mock media must never initialize a provider')) as client:
            generated=gemini.generate_image([], 'Mock-only fixture')
            mascot=media.generate_mascot(did,{'persona_description':'A helpful guide'})
            check('mock: image and mascot paths never initialize provider clients',generated is None and mascot is None and not client.called)
        def ready(d):
            d.update(status='ready',running=None)
            d['approvals'].update({k:True for k in store.CARDS})
            for st in d['stages'].values():st['status']='done'
        store.update(did,ready)
        script={'segments':[{'id':'one','lines':[{'id':'one-L1','text':'Original approved text.','fact_ids':['F1']}]}],'closing':[]}
        store.write_json(did,'script.json',script)
        store.write_json(did,'deck.json',{'slides':[{'id':'sl1','image_id':'im1'}]})
        store.write_json(did,'plan.json',{'voice':{},'ctas':[]})
        store.write_json(did,'understanding.json',{'facts':[{'id':'F1','claim':'Feature','value':'Present'}]})
        store.write_json(did,'faq.json',{'question_policy':orch.faq.QUESTION_POLICY,'entries':[{'question':'Feature?','answer':'Present.','fact_ids':['F1'],'answered':True}]})
        calls=[]
        def author(did,emit,instruction):
            updated=copy.deepcopy(script);updated['segments'][0]['lines'][0]['text']='Changed approved candidate.'
            store.write_json(did,'script.json',updated);return updated
        def deck(did,emit,instruction):return store.read_json(did,'deck.json')
        stack.enter_context(patch.object(orch.author,'run',side_effect=author))
        stack.enter_context(patch.object(orch.deck,'build',side_effect=deck))
        stack.enter_context(patch.object(orch.voice,'render_script',side_effect=lambda *a:calls.append('voice') or {}))
        stack.enter_context(patch.object(orch.rehearsal,'run',side_effect=lambda *a:calls.append('rehearsal') or {}))
        stack.enter_context(patch.object(orch.bundle,'build',side_effect=lambda *a:calls.append('bundle') or {}))
        workflow=graph.build_graph().compile(checkpointer=MemorySaver());cfg={'configurable':{'thread_id':did}}
        workflow.invoke({'demo_id':did,'entry':'revise','revise_stage':'author','instruction':'Improve','rebuild':True,'prev_ready':True,'pending':None},cfg)
        d=store.load(did)
        check('revision: Ready author change stops at actual Align interrupt before any voice',d['status']=='align' and not d['approvals']['script'] and d['approvals']['facts'] and not calls and workflow.get_state(cfg).next==('align_wait',))
        store.update(did,lambda d:d['approvals'].update({k:True for k in store.CARDS}))
        workflow.invoke(Command(resume={'type':'build'}),cfg)
        check('revision: explicit approved Build completes without automatic rehearsal',store.load(did)['status']=='ready' and calls==['voice','bundle'])
        before_approvals=copy.deepcopy(store.load(did)['approvals']); checkpoint=workflow.get_state(cfg).next
        graph._run_rehearsal(did)
        check('rehearsal: explicit run preserves Ready, approvals, bundle and graph checkpoint',calls==['voice','bundle','rehearsal'] and store.load(did)['status']=='ready' and store.load(did)['approvals']==before_approvals and store.load(did)['stages']['bundle']['status']=='done' and workflow.get_state(cfg).next==checkpoint)
        check('rehearsal: explicit completion emits its own phase',any(ev.get('type')=='phase_done' and ev.get('phase')=='rehearsal' for ev in events.since(did,0)))
        with patch.object(orch.rehearsal,'run',side_effect=RuntimeError('review unavailable')):
            graph._run_rehearsal(did)
        check('rehearsal: failed optional review preserves the published demo',store.load(did)['status']=='ready' and store.load(did)['stages']['bundle']['status']=='done' and store.load(did)['stages']['rehearsal']['status']=='error' and any(ev.get('type')=='phase_error' and ev.get('phase')=='rehearsal' for ev in events.since(did,0)))
        entered, release = threading.Event(), threading.Event()
        def hold(*args): entered.set(); release.wait(2)
        with patch.object(graph,'_run_rehearsal',side_effect=hold):
            graph.start_rehearsal(did); started=entered.wait(1)
            try: graph.start_rehearsal(did); refused=False
            except RuntimeError: refused=True
            release.set(); graph._threads[did].join(2)
        check('rehearsal: serializes on-demand work with the shared demo worker',started and refused and not graph.is_running(did))
        store.update(did,lambda d:d['approvals'].__setitem__('faq',False))
        def empty_faq(*args,**kwargs):
            result={'question_policy':orch.faq.QUESTION_POLICY,'entries':[],'total':0,'answered':0};store.write_json(did,'faq.json',result);return result
        with patch.object(orch.faq,'run',side_effect=empty_faq):orch._run_stage(did,'faq')
        check('FAQ: empty bank auto-approves with exact note and can proceed to voice',store.load(did)['approvals']['faq'] and store.load(did)['stages']['faq']['message']=='No questions yet; this card fills from customer questions' and graph.after_author({'demo_id':did,'entry':'build'})=='voice')
        store.update(did,lambda d:d['approvals'].__setitem__('faq',False))
        with patch.object(graph.align,'opening_message',return_value='Ready for review'):
            graph.align_enter({'demo_id':did,'entry':'read'})
        check('FAQ: reused Read also approves an empty bank',store.load(did)['approvals']['faq'])
        store.write_json(did,'faq.json',{'entries':[{'question':'A legacy guess?','origin':'generated','answer':'An old answer.','answered':True,'fact_ids':['F1']}]})
        needs_migration=graph.after_author({'demo_id':did,'entry':'build'})=='faq'
        with patch.object(orch.faq,'run',side_effect=empty_faq) as reconcile:
            graph.faq({'demo_id':did,'entry':'build'})
            graph.faq({'demo_id':did,'entry':'build'})
        check('FAQ: completed legacy banks reconcile once before normal reuse',needs_migration and reconcile.call_count==1 and graph.after_author({'demo_id':did,'entry':'build'})=='voice')
        check('FAQ: repeated ask counts preserve card approval content',orch.changed_cards('faq',{'entries':[{'question':'Feature?','answer':'Present.','asked_count':1}]},{'entries':[{'question':'Feature?','answer':'Present.','asked_count':2}]})==set())
        check('revision: deck-only content changes clear visual review without invalidating facts',orch.changed_cards('deck',{'slides':[{'image_id':'im1'}]},{'slides':[{'image_id':'im2'}]})=={'visuals'} and orch.changed_cards('author',{'version':1,'audio':'a','text':'same'},{'version':2,'audio':'b','text':'same'})==set())
        orch.set_stage(did,'author','running');orch.emit_for(did,'author')('Voice sample skipped: unavailable');orch.emit_for(did,'author')('Draft complete');orch.set_stage(did,'author','done')
        stage=store.load(did)['stages']['author']
        check('progress: warnings survive stage completion alongside latest progress',stage['message']=='Draft complete' and stage['warnings'][0]['message']=='Voice sample skipped: unavailable' and len(stage['progress'])==2)
        events.publish(did,'phase_done',phase='build')
        fresh=events.snapshot(did)
        check('SSE: fresh Align snapshot has no historic phase_done replay',fresh['reset'] and not events.since(did,fresh['seq']) and fresh['snapshot']['stages']['author']['warnings'])
        before=fresh['seq'];next_event=events.publish(did,'progress',stage='deck',message='Next update')
        resume=events.snapshot(did,before)
        check('SSE: valid reconnect returns only new events',not resume['reset'] and events.since(did,resume['seq'])==[next_event])
        with events._guard:
            events._events.pop(did,None);events._seq.pop(did,None)
        check('SSE: sequence and warnings survive process-memory loss',events.latest_seq(did)==next_event['seq'] and events.snapshot(did)['snapshot']['stages']['author']['warnings'])
        check('SSE: future or expired cursors reset safely',events.snapshot(did,10**10)['reset'])
        check('all contracts: no outbound calls',not any(call.called for call in blocked))

    # Exercise real rehearsal caching, outside graph stage stubs.
    with tempfile.TemporaryDirectory(prefix='rehearsal-cache-') as tmp, patch.multiple(config,DATA_DIR=Path(tmp),MOCK_LLM=True):
        did=store.new_demo('Rehearsal fixture')['id'];store.write_json(did,'script.json',script)
        store.write_json(did,'understanding.json',{'facts':[{'id':'F1','claim':'Feature','value':'Present'}]})
        store.write_json(did,'plan.json',{})
        store.write_json(did,'faq.json',{'entries':[{'question':'Feature?','answer':'Present.','fact_ids':['F1'],'answered':True}]})
        with patch.object(rehearsal,'score_script',return_value={'scores':[],'total':0,'weakest':[]}) as score:
            original=rehearsal.run(did,lambda _:None)
            revised=copy.deepcopy(script);revised.update(version=2,timeline={'total_seconds':99});revised['segments'][0]['lines'][0].update(audio='audio/new.wav',start=6,duration=4)
            store.write_json(did,'script.json',revised)
            cached=rehearsal.run(did,lambda _:None)
            check('rehearsal: recording/version/timeline changes reuse scorecard and question results',score.call_count==1 and cached==original)
            und=store.read_json(did,'understanding.json');und['images']=[{'id':'new-image','path':'image.jpg'}];store.write_json(did,'understanding.json',und)
            check('rehearsal: image-only maintenance reuses text/evidence review',rehearsal.run(did,lambda _:None)==original and score.call_count==1)
            revised['segments'][0]['lines'][0]['text']='Changed meaningful speech.';store.write_json(did,'script.json',revised)
            changed=rehearsal.run(did,lambda _:None)
            check('rehearsal: script meaning change requires a new review',score.call_count==2 and changed['input_hash']!=original['input_hash'])
            with patch.object(rehearsal,'SCORE_SYSTEM',rehearsal.SCORE_SYSTEM+' New review requirement.'):
                changed_prompt=rehearsal.run(did,lambda _:None)
            check('rehearsal: prompt changes invalidate prior score',score.call_count==3 and changed_prompt['input_hash']!=changed['input_hash'])
            bank=store.read_json(did,'faq.json');bank['entries'][0]['answer']='Different reviewed answer.';store.write_json(did,'faq.json',bank)
            changed_bank=rehearsal.run(did,lambda _:None)
            check('rehearsal: FAQ answer changes invalidate prior results',score.call_count==4 and changed_bank['input_hash']!=changed['input_hash'])
            und['facts'][0]['value']='A changed specification';store.write_json(did,'understanding.json',und)
            changed_fact=rehearsal.run(did,lambda _:None)
            check('rehearsal: evidence changes invalidate prior results',score.call_count==5 and changed_fact['input_hash']!=changed_bank['input_hash'])
            store.write_json(did,'faq.json',{'entries':[
                {'id':'document','question':'Uploaded?','answer':'From the file.','answered':True,'fact_ids':['F1'],'source':'document'},
                {'id':'customer','question':'Actual question?','answer':'A sourced answer.','answered':True,'fact_ids':['F1'],'source':'customer','asked_count':3},
                {'id':'rejected','question':'Rejected?','answer':'Never serve.','answered':True,'fact_ids':['F1'],'rejected':True}]})
            with patch.object(rehearsal,'generate_questions',side_effect=AssertionError('Existing bank must not generate')) as generated,patch.object(rehearsal.qa,'answer',side_effect=AssertionError('Existing answers must not regenerate')) as answer:
                actual=rehearsal.run(did,lambda _:None)
            check('rehearsal: customer questions precede documents and rejected rows are excluded',[row['question'] for row in actual['questions']]==['Actual question?','Uploaded?'] and not generated.called and not answer.called)
            counted=store.read_json(did,'faq.json');counted['entries'][1]['asked_count']=4;store.write_json(did,'faq.json',counted)
            with patch.object(rehearsal,'score_script',side_effect=AssertionError('Counts do not change the reviewed script')):
                check('rehearsal: repeat question counts reuse the semantic review',rehearsal.run(did,lambda _:None)==actual)
            counted['entries'][1]['registry_hash']='old-snapshot-registry';store.write_json(did,'faq.json',counted)
            with patch.object(rehearsal.qa,'answer',return_value={'answered':False,'answer':'The current sources do not establish this.','fact_ids':[],'escalate':'ask brand'}) as answer:
                updated=rehearsal.run(did,lambda _:None)
            check('rehearsal: earlier-snapshot questions are rechecked without trusting old answers',answer.call_count==1 and answer.call_args.args[:2]==(did,'Actual question?') and answer.call_args.kwargs=={'voice_it':False,'learn':False} and not updated['questions'][0]['answered'] and updated['questions'][0]['answer']=='The current sources do not establish this.' and store.read_json(did,'faq.json')==counted)
            store.write_json(did,'faq.json',{'entries':[]})
            before_unknowns=copy.deepcopy(store.read_json(did,'understanding.json'))
            with patch.object(rehearsal,'generate_questions',return_value=[f'Sample {i}?' for i in range(8)]) as generated,patch.object(rehearsal.qa,'answer',return_value={'answered':False,'answer':'I will not guess.','fact_ids':[],'escalate':'ask brand'}) as answer:
                fallback=rehearsal.run(did,lambda _:None)
            check('rehearsal: empty-bank fallback is bounded to five unvoiced non-customer questions',len(fallback['questions'])==5 and generated.call_args.args==(did,5) and answer.call_count==5 and all(call.kwargs=={'voice_it':False,'learn':False} for call in answer.call_args_list) and store.read_json(did,'understanding.json')==before_unknowns)

if __name__=='__main__':
    rows=[]
    def check(name,ok,detail=''):
        rows.append(bool(ok));print(('PASS ' if ok else 'FAIL ')+name)
    run(check);print(f'Build hardening contracts: {sum(rows)}/{len(rows)}');raise SystemExit(0 if all(rows) else 1)

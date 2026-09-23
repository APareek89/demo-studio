"""Cached wording must pass the current turn's existing deterministic evidence rules."""
import asyncio
import copy
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

scratch=tempfile.TemporaryDirectory(prefix="faq-scope-")
os.environ.update(MOCK_LLM="1",CLOUD_SYNC="0",STORAGE_BACKEND="local",DEMO_STUDIO_DATA=scratch.name,
                  DEMO_STUDIO_GRAPH_DB=str(Path(scratch.name)/"graph.sqlite"))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import config,knowledge,runtime_graph,runtime_state,store
from server.agents import faq
config.DATA_DIR=Path(scratch.name)

class FAQScope(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.blockers=[patch.object(socket.socket,"connect",side_effect=AssertionError("outbound forbidden")),
                       patch.object(socket,"create_connection",side_effect=AssertionError("outbound forbidden"))]
        for blocker in self.blockers:blocker.start()
        self.demo=store.new_demo("Example");self.did=self.demo["id"]
        self.fact={"id":"F1","claim":"Airbags","value":"Six airbags are listed.","approved":True,
                   "source":{"ref":"brochure","quote":"Six airbags are listed."}}
        self.question="How many airbags are listed?"

    def tearDown(self):
        for blocker in reversed(self.blockers):blocker.stop()

    def fixture(self, *, profile=None, answer=None, fact_ids=None):
        store.write_json(self.did,"understanding.json",{"facts":[self.fact],"product":{"name":"Example"},"unknowns":[]})
        sid=knowledge.snapshot(self.did)["id"]
        state={"demo_id":self.did,"session_id":"scope","turn_id":"one","snapshot_id":sid,"question":self.question,
               "profile":profile or {},"history":[],"timings":{},"control":runtime_state.claim_turn(self.did,"scope","one")}
        entry={"id":"C1","answer":answer or self.fact["value"],"question":self.question,"fact_ids":fact_ids or ["F1"],"reviewed":True}
        return state,entry

    async def test_scope_mismatch_is_a_miss_instead_of_cross_trim_answer(self):
        self.fact.update(claim="Sunroof",value="A sunroof is available on SX.",scope={"variant":"SX"})
        self.question="Is a sunroof available?"
        state,entry=self.fixture(profile={"scope":{"variant":"EX"}})
        update,result=await runtime_graph._validated_bank_result(state,entry)
        self.assertIsNone(result)
        self.assertEqual(update["requested_scope"],{"variant":"EX"})
        self.assertEqual(update["evidence"],[])

    async def test_expired_and_future_dated_answers_miss(self):
        for scope in ({"effective_to":"2020-01-01"},{"effective_from":"2100-01-01"}):
            self.fact["scope"]=scope
            state,entry=self.fixture()
            _,result=await runtime_graph._validated_bank_result(state,entry)
            self.assertIsNone(result)

    async def test_valid_exact_answer_keeps_enriched_evidence_without_model(self):
        state,entry=self.fixture()
        with patch.object(runtime_graph.runtime,"structured",side_effect=AssertionError("No model on cache hit")):
            update,result=await runtime_graph._validated_bank_result(state,entry)
        self.assertEqual(result["answer"],entry["answer"])
        self.assertEqual(result["fact_ids"],["F1"])
        self.assertEqual(result["facts"][0]["snapshot_id"],state["snapshot_id"])
        self.assertIn("source_metadata",result["facts"][0])
        self.assertIn("runtime_transmission_conditions",result["facts"][0])
        self.assertEqual(update["profile"].get("scope"),{})

    async def test_missing_or_held_citation_misses(self):
        state,entry=self.fixture(fact_ids=["missing"])
        self.assertIsNone((await runtime_graph._validated_bank_result(state,entry))[1])
        self.fact["approved"]=False
        state,entry=self.fixture()
        self.assertIsNone((await runtime_graph._validated_bank_result(state,entry))[1])

    async def test_unsupported_number_cannot_bypass_grounding(self):
        state,entry=self.fixture(answer="Eight airbags are listed.")
        self.assertIsNone((await runtime_graph._validated_bank_result(state,entry))[1])

    async def test_exact_reviewed_words_are_not_silently_rewritten(self):
        self.fact.update(claim="ADAS",value="ADAS is available.")
        self.question="Is ADAS available?"
        state,entry=self.fixture()
        entry["reviewed"]=False
        self.assertIsNone((await runtime_graph._validated_bank_result(state,entry))[1])
        entry["reviewed"]=True
        self.assertEqual((await runtime_graph._validated_bank_result(state,entry))[1]["answer"],"ADAS is available.")
        bad={**entry,"fact_ids":["missing"]}
        self.assertIsNone((await runtime_graph._validated_bank_result(state,bad))[1])
        # Existing technical-audience rule permits the exact sourced wording.
        entry["reviewed"]=False
        store.update(self.did,lambda demo:demo["settings"].update(audience="technical"))
        result=(await runtime_graph._validated_bank_result(state,entry))[1]
        self.assertEqual(result["answer"],"ADAS is available.")

    async def test_helper_uses_session_snapshot_after_draft_changes(self):
        state,entry=self.fixture()
        changed=copy.deepcopy(self.fact);changed["value"]="Eight airbags are listed."
        store.write_json(self.did,"understanding.json",{"facts":[changed],"unknowns":[]})
        result=(await runtime_graph._validated_bank_result(state,entry))[1]
        self.assertEqual(result["answer"],"Six airbags are listed.")
        self.assertEqual(result["facts"][0]["value"],"Six airbags are listed.")

    async def test_validation_does_not_increment_count_or_edit_bank(self):
        state,entry=self.fixture()
        store.write_json(self.did,"faq.json",{"entries":[{**entry,"asked_count":4}]})
        before=store.path(self.did,"faq.json").read_bytes()
        await runtime_graph._validated_bank_result(state,entry)
        self.assertEqual(store.path(self.did,"faq.json").read_bytes(),before)

    async def test_cancelled_candidate_does_not_validate_or_deliver(self):
        state,entry=self.fixture();state["control"].cancelled.set()
        with self.assertRaises(InterruptedError):await runtime_graph._validated_bank_result(state,entry)

    def cache_fixture(self,state,entry):
        stored=faq.cache_answer(self.did,entry["question"],{"answered":True,"answer":entry["answer"],
            "fact_ids":entry["fact_ids"],"facts":[self.fact]},snapshot_id=state["snapshot_id"])
        self.assertIsNotNone(stored)
        return stored

    async def test_actual_turn_cross_trim_misses_without_incrementing_cached_answer(self):
        self.fact.update(claim="Sunroof",value="A sunroof is available on SX.",scope={"variant":"SX"})
        self.question="Is a sunroof available?"
        state,entry=self.fixture();stored=self.cache_fixture(state,entry)
        with patch.object(runtime_graph.graph,"ainvoke",wraps=runtime_graph.graph.ainvoke) as graph:
            final=await runtime_graph.run_turn(self.did,{"question":self.question,"snapshot_id":state["snapshot_id"],
                "session_id":"other-trim","profile":{"scope":{"variant":"EX"}}})
        self.assertEqual(graph.call_count,1)
        self.assertFalse(final["result"]["from_bank"])
        self.assertFalse(final["result"]["answered"])
        self.assertEqual(final["result"]["fact_ids"],[])
        saved=next(row for row in store.read_json(self.did,"faq.json")["entries"] if row["id"]==stored["id"])
        self.assertEqual(saved["asked_count"],1)

    async def test_actual_turn_expired_cache_miss_preserves_count_and_learns_only_gap(self):
        self.fact.update(claim="Offer",value="A discount of 1000 rupees is available.",scope={"effective_to":"2020-01-01"})
        self.question="What discount is available?"
        state,entry=self.fixture();stored=self.cache_fixture(state,entry)
        facts=copy.deepcopy(store.read_json(self.did,"understanding.json")["facts"])
        clean_decline=runtime_state.TurnDecision(action="answer",answered=False,
            sentences=[{"text":"I couldn't verify a current discount.","kind":"limitation"}])
        with patch.object(runtime_graph,"_mock_decision",return_value=clean_decline):
            final=await runtime_graph.run_turn(self.did,{"question":self.question,"snapshot_id":state["snapshot_id"],"session_id":"expired-offer"})
        self.assertFalse(final["result"]["from_bank"])
        self.assertFalse(final["result"]["answered"])
        self.assertEqual(final["result"]["validation_errors"],[])
        saved=store.read_json(self.did,"faq.json")["entries"][0]
        self.assertEqual(saved["id"],stored["id"]);self.assertEqual(saved["asked_count"],1)
        und=store.read_json(self.did,"understanding.json")
        self.assertEqual(und["facts"],facts)
        self.assertEqual(len(und["unknowns"]),1,final["result"]);self.assertEqual(und["unknowns"][0]["source"],"customer")

    async def test_actual_graph_result_cannot_be_replaced_by_other_trim_human_answer(self):
        self.fact.update(claim="Sunroof",value="A sunroof is available on SX.",scope={"variant":"SX"})
        self.question="Is a sunroof available?"
        state,entry=self.fixture()
        other={"id":"F2","claim":"Sunroof","value":"A sunroof is not available on EX.","approved":True,"scope":{"variant":"EX"},
               "source":{"ref":"brochure","quote":"A sunroof is not available on EX."}}
        und=store.read_json(self.did,"understanding.json");und["facts"].append(other);store.write_json(self.did,"understanding.json",und)
        state["snapshot_id"]=knowledge.snapshot(self.did)["id"]
        stored=self.cache_fixture(state,entry)
        faq.review_entry(self.did,stored["id"],action="approve")
        final=await runtime_graph.run_turn(self.did,{"question":self.question,"snapshot_id":state["snapshot_id"],
            "session_id":"other-trim-answer","profile":{"scope":{"variant":"EX"}}})
        self.assertFalse(final["result"]["from_bank"])
        self.assertTrue(final["result"]["answered"],final["result"])
        self.assertIn(other["value"],final["result"]["answer"])
        self.assertNotIn("on SX",final["result"]["answer"])
        self.assertEqual(final["result"]["fact_ids"],["F2"])
        self.assertEqual(final["delivery"]["speech"],final["result"]["answer"])

    async def test_actual_failed_repair_does_not_create_customer_unknown(self):
        state,_=self.fixture()
        async def failed_graph(current,config):
            return await runtime_graph.delivery_plan({**current,"result":{"answered":False,"answer":"I won't guess.","fact_ids":[],
                "facts":[],"from_bank":False,"validation_repair":{"attempted":True,"accepted":False}}})
        with patch.object(runtime_graph.graph,"ainvoke",side_effect=failed_graph):
            final=await runtime_graph.run_turn(self.did,{"question":self.question,"snapshot_id":state["snapshot_id"],"session_id":"failed-repair"})
        self.assertFalse(final["result"]["answered"])
        self.assertEqual(store.read_json(self.did,"understanding.json")["unknowns"],[])
        self.assertIsNone(store.read_json(self.did,"faq.json"))

    async def test_old_snapshot_only_bank_is_currently_empty_and_auto_approves(self):
        from server import orchestrator
        state,entry=self.fixture();stored=self.cache_fixture(state,entry)
        current=store.read_json(self.did,"understanding.json")
        current["facts"][0]["value"]="Eight airbags are listed."
        store.write_json(self.did,"understanding.json",current)
        bank=faq.run(self.did,lambda _:None)
        self.assertNotEqual(bank["snapshot_id"],state["snapshot_id"])
        self.assertEqual(bank["total"],0)
        self.assertEqual(bank["answered"],0)
        self.assertEqual(faq.current_entries(bank),[])
        self.assertEqual(bank["entries"][0]["id"],stored["id"])
        self.assertTrue(orchestrator.approve_empty_faq(self.did))
        self.assertTrue(store.load(self.did)["approvals"]["faq"])
        self.assertIsNotNone(faq.match(self.did,self.question,snapshot_id=state["snapshot_id"]))

    async def test_reject_during_postgraph_review_validation_cannot_serve_old_entry(self):
        state,entry=self.fixture();stored=self.cache_fixture(state,entry)
        edited="There are six airbags."
        faq.review_entry(self.did,stored["id"],action="edit",answer=edited,fact_ids=["F1"])
        original=runtime_graph._validated_bank_result
        reached=[]
        async def reject_after_validation(current,candidate):
            update,result=await original(current,candidate)
            self.assertIsNotNone(result)
            reached.append(candidate["id"])
            faq.review_entry(self.did,candidate["id"],action="reject")
            return update,result
        with patch.object(runtime_graph,"_validated_bank_result",side_effect=reject_after_validation):
            final=await runtime_graph.run_turn(self.did,{"question":self.question,"snapshot_id":state["snapshot_id"],
                "session_id":"reject-during-review","skip_bank":True})
        self.assertEqual(reached,[stored["id"]])
        self.assertNotEqual(final["result"]["answer"],edited)
        self.assertNotIn("faq_entry_id",final["result"])
        self.assertTrue(store.read_json(self.did,"faq.json")["entries"][0]["rejected"])

    async def test_read_preserves_customer_unknowns_and_counts_arriving_during_extraction(self):
        from server.agents import understand,visuals
        self.fixture()
        store.add_text_source(self.did,"Product guide","Example vehicle comes with six airbags.","product")
        question="Does the rear seat offer ventilation?"
        before=faq.record_unknown(self.did,question,session_id="before-read")
        resolved=faq.record_unknown(self.did,"What documents are needed for finance approval?",session_id="resolved-customer")
        draft=store.read_json(self.did,"understanding.json")
        next(row for row in draft["unknowns"] if row["id"]==resolved["id"])["status"]="resolved"
        store.write_json(self.did,"understanding.json",draft)
        def question_during_read(*args):
            faq.record_unknown(self.did,question,session_id="during-read")
            return {}
        with patch.object(visuals,"build_map",side_effect=question_during_read):
            understand.run(self.did,lambda _:None)
        und=store.read_json(self.did,"understanding.json")
        customer=[row for row in und["unknowns"] if row.get("source")=="customer"]
        self.assertEqual(len(customer),2)
        unanswered=next(row for row in customer if row["id"]==before["id"])
        self.assertEqual(unanswered["question"],question)
        self.assertEqual(unanswered["asked_count"],2)
        self.assertEqual(unanswered["session_id"],"during-read")
        self.assertEqual(next(row for row in customer if row["id"]==resolved["id"]),{**resolved,"status":"resolved"})
        self.assertEqual(len({row["id"] for row in und["unknowns"]}),len(und["unknowns"]))
        self.assertFalse(any(question in str(fact) for fact in und["facts"]))

    async def test_cache_audio_uses_current_voice_identity_on_hit_and_postgraph_adoption(self):
        from server.agents import voice
        state,entry=self.fixture();stored=self.cache_fixture(state,entry)
        store.update(self.did,lambda demo:demo["settings"].update(tts_provider="sarvam",sarvam_speaker="priya",voice_locked=True,language="en-IN"))
        old=voice.save_streamed_clip(self.did,entry["answer"],b"\0\0"*2400,speaker="priya",language="en-IN")
        faq.update_audio(self.did,stored["id"],entry["answer"],old)
        store.update(self.did,lambda demo:demo["settings"].update(sarvam_speaker="neha"))
        for skip in (False,True):
            final=await runtime_graph.run_turn(self.did,{"question":self.question,"snapshot_id":state["snapshot_id"],
                "session_id":"voice-"+str(skip),"skip_bank":skip})
            self.assertEqual(final["result"]["answer"],entry["answer"])
            self.assertIsNone(final["result"]["audio"])
        current=voice.save_streamed_clip(self.did,entry["answer"],b"\1\0"*2400,speaker="neha",language="en-IN")
        final=await runtime_graph.run_turn(self.did,{"question":self.question,"snapshot_id":state["snapshot_id"],"session_id":"correct-voice"})
        self.assertTrue(final["result"]["audio"].endswith(current))
        self.assertNotEqual(current,old)

    async def test_published_voice_language_and_persona_own_cache_and_stream_after_draft_edit(self):
        import base64
        from server.agents import voice
        from server.runtime_delivery import DeliveryCoordinator
        state,entry=self.fixture();stored=self.cache_fixture(state,entry)
        persona={"persona_name":"Published guide","tone":"warm"}
        store.update(self.did,lambda demo:demo["settings"].update(tts_provider="sarvam",sarvam_speaker="priya",voice_locked=True,language="en-IN"))
        store.write_json(self.did,"plan.json",{"voice":persona})
        original=voice.save_streamed_clip(self.did,entry["answer"],b"\0\0"*2400,speaker="priya",language="en-IN")
        bundle={"version":1,"language":"en-IN","voice":{"provider":"sarvam","name":"priya","persona":persona},
                "knowledge_snapshot_id":state["snapshot_id"],"slides":[],"alt_languages":{"hi-IN":{"voice_provider":"sarvam"}}}
        store.write_json(self.did,"bundle.json",bundle)
        store.update(self.did,lambda demo:demo["settings"].update(sarvam_speaker="neha",language="hi-IN"))
        store.write_json(self.did,"plan.json",{"voice":{"persona_name":"Unpublished guide","tone":"direct"}})
        draft=voice.save_streamed_clip(self.did,entry["answer"],b"\1\0"*2400,speaker="neha",language="hi-IN")
        faq.update_audio(self.did,stored["id"],entry["answer"],draft)
        for skip in (False,True):
            final=await runtime_graph.run_turn(self.did,{"question":self.question,"session_id":"published-voice-"+str(skip),"skip_bank":skip})
            self.assertTrue(final["result"]["audio"].endswith(original))
            self.assertFalse(final["result"]["audio"].endswith(draft))
            self.assertEqual(final["delivery"]["language"],"en-IN")
        store.path(self.did,original).unlink()
        final=await runtime_graph.run_turn(self.did,{"question":self.question,"session_id":"published-render"})
        self.assertIsNone(final["result"]["audio"])
        calls=[];packets=[]
        async def stream(text,**kwargs):
            calls.append((text,kwargs))
            yield {"audio":base64.b64encode(b"\2\0"*2400).decode(),"sample_rate":24000,"format":"pcm_s16le"}
        async def send(packet):packets.append(packet)
        delivery=DeliveryCoordinator(self.did,send)
        with patch("server.llm.sarvam_stream.stream_tts",side_effect=stream):
            await delivery._stream(final["delivery"],0)
        self.assertEqual((calls[0][1]["speaker"],calls[0][1]["language"]),("priya","en-IN"))
        self.assertEqual(voice._cached(self.did,entry["answer"],voice.runtime_demo(self.did)),original)
        self.assertEqual(faq.match(self.did,self.question,snapshot_id=state["snapshot_id"])["audio"],original)
        self.assertTrue(any(packet["type"]=="audio.end" for packet in packets))
        alternate=voice.runtime_demo(self.did,"hi-IN")
        hindi=voice.save_streamed_clip(self.did,entry["answer"],b"\3\0"*2400,speaker="priya",language="hi-IN",demo=alternate)
        final=await runtime_graph.run_turn(self.did,{"question":self.question,"session_id":"published-hindi","profile":{"language":"hi-IN"}})
        self.assertTrue(final["result"]["audio"].endswith(hindi))
        self.assertEqual(final["delivery"]["language"],"hi-IN")
        self.assertNotEqual(hindi,draft)

    async def test_rest_followup_without_profile_renders_persisted_language_and_published_voice(self):
        import httpx
        import io
        import wave
        from server.app import app
        from server.agents import voice
        state,entry=self.fixture();self.cache_fixture(state,entry)
        persona={"persona_name":"Published guide","tone":"warm"}
        store.write_json(self.did,"bundle.json",{"version":1,"runtime":{"version":1},"language":"en-IN",
            "voice":{"provider":"sarvam","name":"priya","persona":persona},"slides":[],
            "alt_languages":{"hi-IN":{"voice_provider":"sarvam"}},"knowledge_snapshot_id":state["snapshot_id"]})
        store.update(self.did,lambda demo:demo["settings"].update(tts_provider="sarvam",sarvam_speaker="neha",voice_locked=True,language="en-IN"))
        store.write_json(self.did,"plan.json",{"voice":{"persona_name":"Draft guide","tone":"direct"}})
        wav_bytes=io.BytesIO()
        with wave.open(wav_bytes,"wb") as wav:
            wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(24000);wav.writeframes(b"\0\0"*2400)
        calls=[]
        def tts(text,speaker,language,**kwargs):
            calls.append((text,speaker,language))
            return wav_bytes.getvalue(),"wav"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as api:
            with patch.object(voice.sarvam,"tts",side_effect=tts):
                first=await api.post(f"/api/demos/{self.did}/run/qa",json={"session_id":"rest-language","turn_id":"one",
                    "question":self.question,"profile":{"language":"hi-IN"},"voice_it":False})
                self.assertEqual(first.status_code,200,first.text)
                self.assertEqual(calls,[])
                second=await api.post(f"/api/demos/{self.did}/run/qa",json={"session_id":"rest-language","turn_id":"two","question":self.question})
        self.assertEqual(second.status_code,200,second.text)
        self.assertEqual(calls,[(entry["answer"],"priya","hi-IN")])
        effective=voice.runtime_demo(self.did,"hi-IN")
        cached=voice._cached(self.did,entry["answer"],effective)
        self.assertIsNotNone(cached)
        self.assertTrue(second.json()["audio"].endswith(cached))
        self.assertEqual(voice._delivery_identity(self.did,None,demo=effective)["persona"],persona)
        self.assertEqual(runtime_state.previous_state(self.did,"rest-language")["profile"]["language"],"hi-IN")

if __name__=="__main__":unittest.main()

"""Snapshot-bound FAQ/learning contracts; fake providers, temporary data, blocked sockets."""
from __future__ import annotations

import copy
import asyncio
import base64
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch, AsyncMock

_STORAGE = tempfile.TemporaryDirectory(prefix="faq-cache-contract-")
os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", DEMO_STUDIO_DATA=_STORAGE.name,
                  DEMO_STUDIO_GRAPH_DB=str(Path(_STORAGE.name) / "graph.sqlite"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
OUTBOUND = []
def blocked(*args, **kwargs):
    OUTBOUND.append(True)
    raise AssertionError("FAQ contracts must not open outbound sockets")
socket.socket.connect = socket.socket.connect_ex = socket.create_connection = blocked

from server import config, knowledge, schemas, store
from server.agents import faq, qa, rehearsal


class FAQCacheContract(unittest.TestCase):
    def setUp(self):
        self.did = store.new_demo("Customer FAQ cache")['id']
        self.q = "How many airbags are fitted?"
        self.fact = {"id":"F1", "claim":"Airbags", "value":"Six airbags are listed.", "approved":True,
                     "kind":"feature", "truth":"stated", "source":{"ref":"source", "quote":"Six airbags are listed."}}
        self.und = {"product":{"name":"Example", "category":"Car"}, "facts":[self.fact], "competitors":[], "shots":[], "images":[], "unknowns":[]}
        store.write_json(self.did, "understanding.json", self.und)
        store.write_json(self.did, "plan.json", {"voice":{}, "segments":[], "ctas":[]})
        self.sid = knowledge.snapshot(self.did)['id']
        self.fingerprint = faq._registry_hash(self.did, snapshot_id=self.sid)
        self.result = {"answer":"Six airbags are listed.", "answered":True, "fact_ids":["F1"], "facts":[self.fact],
                       "provider_failed":False, "repair_failed":False, "validation_errors":[], "tool_results":[]}

    def tearDown(self):
        self.assertEqual(OUTBOUND, [])

    def cache(self, result=None, question=None):
        return faq.cache_answer(self.did, question or self.q, result or self.result,
                                snapshot_id=self.sid, registry_hash=self.fingerprint, session_id="session-one")

    def hit(self, **kwargs):
        return faq.match(self.did, self.q, snapshot_id=self.sid, registry_hash=self.fingerprint, **kwargs)

    def test_build_uses_only_uploaded_questions_without_generation_or_quota(self):
        store.add_text_source(self.did, "FAQ", self.q, "faq")
        store.update(self.did, lambda demo: demo['settings'].update(faq_questions=100))
        with patch.object(rehearsal, "generate_questions", side_effect=AssertionError("No generated questions")) as generate, \
             patch.object(qa, "answer", return_value=self.result) as answer:
            bank = faq.run(self.did, lambda _: None)
        self.assertFalse(generate.called)
        self.assertEqual(answer.call_count, 1)
        self.assertFalse(answer.call_args.kwargs['learn'])
        self.assertEqual([entry['question'] for entry in bank['entries']], [self.q])
        self.assertEqual(bank['entries'][0]['source'], 'document')
        self.assertEqual(bank['entries'][0]['snapshot_id'], knowledge.snapshot(self.did)['id'])

    def test_empty_bank_is_valid_and_discards_guessed_legacy_questions(self):
        store.write_json(self.did, 'faq.json', {'entries':[{'id':'Q01','question':self.q,'origin':'generated',**self.result}]})
        with patch.object(rehearsal, 'generate_questions', side_effect=AssertionError('No generation')), \
             patch.object(qa, 'answer', side_effect=AssertionError('No answer call')):
            bank = faq.run(self.did, lambda _: None)
        self.assertEqual(bank['entries'], [])
        self.assertEqual((bank['answered'], bank['total'], bank['partial']), (0,0,False))

    def test_clean_customer_answer_has_snapshot_provenance_and_no_unverified_audio(self):
        result = {**self.result, 'audio':'audio/untrusted.wav'}
        entry = self.cache(result)
        self.assertEqual(entry['source'], 'customer')
        self.assertEqual(entry['asked_count'], 1)
        self.assertFalse(entry['reviewed'])
        self.assertEqual(entry['registry_hash'], self.fingerprint)
        self.assertEqual(entry['snapshot_id'], self.sid)
        self.assertIsNone(entry['audio'])
        self.assertEqual(self.hit()['answer'], self.result['answer'])

    def test_declines_clarifications_failures_errors_and_tools_are_not_cached(self):
        changes = [dict(answered=False), dict(clarifying_question='Which version?'), dict(provider_failed=True),
                   dict(repair_failed=True), dict(validation_errors=['unsupported_citation']), dict(cta='book'),
                   dict(offer_callback=True), dict(fact_ids=[]), dict(fact_ids=['missing']), dict(cancelled=True),
                   dict(answer="I won't guess about that."),
                   dict(validation_repair={'attempted':True,'accepted':False}), dict(tool_results=[{'tool':'calculator'}]),
                   dict(facts=[{**self.fact,'provenance':'live_web'}]), dict(facts=[{**self.fact,'provenance':'calculation'}])]
        for update in changes:
            with self.subTest(update=update):
                self.assertIsNone(self.cache({**self.result, **update}))
        self.assertIsNone(store.read_json(self.did, 'faq.json'))

    def test_unknown_or_mismatched_snapshot_identity_fails_closed(self):
        self.assertIsNone(faq.cache_answer(self.did,self.q,self.result,snapshot_id='kb_'+'f'*24))
        self.assertIsNone(faq.cache_answer(self.did,self.q,self.result,snapshot_id=self.sid,registry_hash='wrong'))
        self.cache()
        self.assertIsNone(faq.match(self.did,self.q,snapshot_id='../understanding'))
        self.assertIsNone(faq.match(self.did,self.q,snapshot_id=self.sid,registry_hash='wrong'))

    def test_pinned_hash_survives_draft_changes_and_new_snapshot_cannot_hit(self):
        self.cache()
        self.und['facts'][0]['value']='Two airbags are listed.'
        store.write_json(self.did, 'understanding.json', self.und)
        new_sid=knowledge.snapshot(self.did)['id']
        self.assertNotEqual(new_sid,self.sid)
        self.assertEqual(faq._registry_hash(self.did,snapshot_id=self.sid), self.fingerprint)
        self.assertIsNone(faq.match(self.did,self.q,snapshot_id=new_sid))
        self.assertEqual(self.hit()['answer'], 'Six airbags are listed.')

    def test_match_counts_actual_hits_without_resetting_approval(self):
        self.cache()
        store.update(self.did, lambda demo: demo['approvals'].update(faq=True))
        self.assertEqual(self.hit()['asked_count'],1)
        self.assertEqual(self.hit(increment=True)['asked_count'],2)
        self.assertTrue(store.load(self.did)['approvals']['faq'])

    def test_concurrent_cache_and_hit_counts_do_not_lose_writes(self):
        self.cache()
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(lambda _: self.hit(increment=True), range(24)))
        self.assertEqual(self.hit()['asked_count'],25)
        self.assertEqual(len(store.read_json(self.did,'faq.json')['entries']),1)

    def test_plain_language_is_applied_before_storage_and_audio_identity(self):
        self.und['facts'][0].update(claim='Suspension',value='McPherson strut suspension is listed.')
        store.write_json(self.did,'understanding.json',self.und)
        sid=knowledge.snapshot(self.did)['id']
        entry=faq.cache_answer(self.did,'Which front suspension is fitted?',
                               {**self.result,'answer':'McPherson strut suspension is listed.'},snapshot_id=sid)
        self.assertEqual(entry['answer'],'strut-type front suspension is listed.')
        self.assertEqual(entry['plain_language_substitutions'], [('mcpherson strut','strut-type front suspension')])
        self.assertIsNone(entry['audio'])

    def test_exact_reviewed_edit_survives_cache_and_normalization(self):
        entry=self.cache()
        words='Six airbags are listed as standard equipment.'
        edited=faq.review_entry(self.did,entry['id'],action='edit',answer=words,fact_ids=['F1'])
        self.assertTrue(edited['reviewed'])
        self.assertIsNone(edited['audio'])
        self.assertEqual(self.cache()['answer'],words)
        self.assertEqual(self.hit()['answer'],words)
        self.assertEqual(faq.normalize_entry({**edited,'answer':'Reviewed ADAS wording.'},'everyday')['answer'],'Reviewed ADAS wording.')

    def test_audio_attach_requires_current_exact_text_and_retains_counts(self):
        entry=self.cache()
        self.hit(increment=True)
        self.assertFalse(faq.update_audio(self.did,entry['id'],'old answer','audio/old.wav'))
        self.assertTrue(faq.update_audio(self.did,entry['id'],entry['answer'],'audio/exact.wav'))
        self.assertEqual((self.hit()['audio'],self.hit()['asked_count']),('audio/exact.wav',2))
        faq.review_entry(self.did,entry['id'],action='edit',answer='Six airbags are specified.',fact_ids=['F1'])
        self.assertFalse(faq.update_audio(self.did,entry['id'],entry['answer'],'audio/late.wav'))
        self.assertIsNone(self.hit()['audio'])

    def test_rejected_tombstone_prevents_hit_recache_and_doc_rebuild(self):
        entry=self.cache()
        faq.review_entry(self.did,entry['id'],action='reject')
        self.assertIsNone(self.hit())
        self.assertIsNone(self.cache())
        store.add_text_source(self.did,'FAQ',self.q,'faq')
        with patch.object(qa,'answer',side_effect=AssertionError('Rejected question must not rebuild')):
            bank=faq.run(self.did,lambda _:None)
        self.assertTrue(bank['entries'][0]['rejected'])
        self.assertEqual(bank['total'],0)
        self.assertFalse(faq.update_audio(self.did,entry['id'],entry['answer'],'audio/rejected.wav'))

    def test_customer_unknowns_dedupe_by_match_similarity_and_never_become_facts(self):
        before=copy.deepcopy(self.und['facts'])
        first=faq.record_unknown(self.did,'What is the warranty period?',session_id='s1')
        second=faq.record_unknown(self.did,'Tell me the warranty period please?',session_id='s2')
        self.assertEqual(first['id'],second['id'])
        self.assertEqual((second['source'],second['asked_count'],second['session_id']),('customer',2,'s2'))
        saved=store.read_json(self.did,'understanding.json')
        self.assertEqual(saved['facts'],before)
        self.assertEqual(len(saved['unknowns']),1)
        self.assertEqual(faq._registry_hash(self.did,snapshot_id=self.sid),self.fingerprint)

    def test_concurrent_unknown_counts_are_atomic(self):
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(lambda i: faq.record_unknown(self.did,'What is the warranty period?',session_id=str(i)),range(24)))
        unknowns=store.read_json(self.did,'understanding.json')['unknowns']
        self.assertEqual(len(unknowns),1)
        self.assertEqual(unknowns[0]['asked_count'],24)

    def test_build_merge_preserves_customer_write_during_slow_doc_answer(self):
        store.add_text_source(self.did,'FAQ','What is the engine option?','faq')
        def answer(*args,**kwargs):
            self.cache()
            return self.result
        with patch.object(qa,'answer',side_effect=answer):
            bank=faq.run(self.did,lambda _:None)
        self.assertEqual({entry['source'] for entry in bank['entries']},{'document','customer'})
        self.assertEqual(self.hit()['asked_count'],1)

    def test_build_decline_does_not_learn_and_provider_outage_does_not_learn(self):
        with patch.object(qa.claude,'structured',return_value=schemas.QAOut(answer=qa.DONT_GUESS,answered=False,fact_ids=[])):
            result=qa.answer(self.did,'What is the warranty period?',voice_it=False,learn=False)
        self.assertFalse(result['answered'])
        self.assertEqual(store.read_json(self.did,'understanding.json')['unknowns'],[])
        with patch.object(qa.claude,'structured',side_effect=RuntimeError('provider down')):
            result=qa.answer(self.did,'What is the warranty period?',voice_it=False)
        self.assertTrue(result['provider_failed'])
        self.assertEqual(store.read_json(self.did,'understanding.json')['unknowns'],[])

    def test_store_is_temporary_and_sockets_are_blocked(self):
        self.assertEqual(config.DATA_DIR,Path(_STORAGE.name).resolve())
        self.assertEqual(OUTBOUND,[])

    def turn(self, **body):
        from server import runtime_graph
        return asyncio.run(runtime_graph.run_turn(self.did, {"question": self.q, "snapshot_id": self.sid, **body}))

    def test_actual_graph_learns_then_hit_precedes_graph_and_counts(self):
        from server import runtime_graph
        first = self.turn(session_id="first-customer")
        self.assertTrue(first["result"]["answered"])
        self.assertFalse(first["result"]["from_bank"])
        self.assertEqual(self.hit()["asked_count"], 1)
        with patch.object(runtime_graph.graph, "ainvoke", side_effect=AssertionError("Cache hit must precede graph")) as graph:
            second = self.turn(session_id="second-customer")
        self.assertFalse(graph.called)
        self.assertTrue(second["result"]["from_bank"])
        self.assertEqual(second["delivery"]["speech"], first["result"]["answer"])
        self.assertEqual(self.hit()["asked_count"], 2)

    def test_skip_bank_runs_actual_graph_even_when_an_answer_is_cached(self):
        from server import runtime_graph
        self.cache()
        with patch.object(runtime_graph.graph, "ainvoke", wraps=runtime_graph.graph.ainvoke) as graph:
            result = self.turn(skip_bank=True)
        self.assertEqual(graph.call_count, 1)
        self.assertFalse(result["result"]["from_bank"])
        self.assertTrue(result["result"]["answered"])

    def test_declines_learn_once_per_customer_turn_but_clarification_and_outage_do_not(self):
        from server import runtime_graph
        async def fake_graph(state, config):
            return await runtime_graph.delivery_plan({**state, "result": copy.deepcopy(result)})
        facts_before = copy.deepcopy(self.und["facts"])
        result = {**self.result, "answer": "I won't guess.", "answered": False, "fact_ids": []}
        with patch.object(runtime_graph.graph, "ainvoke", side_effect=fake_graph):
            self.turn(session_id="decline-one")
            self.turn(session_id="decline-two")
            result = {**result, "clarifying_question": "Which variant?"}
            self.turn(question="What is the warranty?", session_id="clarification")
            result = {**result, "clarifying_question": "", "provider_failed": True}
            self.turn(question="What is the warranty?", session_id="outage")
        und = store.read_json(self.did, "understanding.json")
        self.assertEqual(und["facts"], facts_before)
        self.assertEqual(len(und["unknowns"]), 1)
        self.assertEqual(und["unknowns"][0]["asked_count"], 2)
        self.assertEqual(und["unknowns"][0]["session_id"], "decline-two")

    def test_learning_storage_failure_does_not_discard_a_valid_answer(self):
        with patch.object(faq, "cache_answer", side_effect=OSError("disk full")):
            result = self.turn()
        self.assertTrue(result["result"]["answered"])
        self.assertEqual(result["result"]["fact_ids"], ["F1"])

    def test_human_edit_uses_exact_words_citations_and_new_audio(self):
        from server.agents import voice
        entry = self.cache()
        old_audio = voice.save_streamed_clip(self.did, entry["answer"], b"\0\0" * 2400, speaker="priya", language="en-IN")
        faq.update_audio(self.did, entry["id"], entry["answer"], old_audio)
        edited = "The supplied source lists six airbags."
        faq.review_entry(self.did, entry["id"], action="edit", answer=edited, fact_ids=["F1"])
        result = self.turn()
        self.assertEqual(result["result"]["answer"], edited)
        self.assertIsNone(result["result"]["audio"])
        self.assertEqual(result["result"]["facts"][0]["id"], "F1")
        new_audio = voice.save_streamed_clip(self.did, edited, b"\0\0" * 2400, speaker="priya", language="en-IN")
        self.assertNotEqual(new_audio, old_audio)
        self.assertFalse(faq.update_audio(self.did, entry["id"], entry["answer"], old_audio))
        self.assertTrue(faq.update_audio(self.did, entry["id"], edited, new_audio))
        self.assertTrue(self.turn()["result"]["audio"].endswith(new_audio))

    def test_streamed_audio_is_saved_once_and_reused_without_another_tts_call(self):
        from server.runtime_delivery import DeliveryCoordinator
        from server.agents import voice
        entry = self.cache()
        packets = []
        pcm = b"\1\0" * 4800
        async def send(packet): packets.append(packet)
        async def stream(*args, **kwargs):
            yield {"audio": base64.b64encode(pcm).decode(), "sample_rate": 24000, "format": "pcm_s16le"}
        plan = {"utterance_id": "u-one", "turn_id": "t-one", "speech": entry["answer"], "result": {"faq_entry_id": entry["id"]}}
        async def deliver():
            coordinator = DeliveryCoordinator(self.did, send)
            with patch("server.llm.sarvam_stream.stream_tts", side_effect=stream) as tts:
                await coordinator._stream(plan, 0)
            self.assertEqual(tts.call_count, 1)
            with patch("server.llm.sarvam_stream.stream_tts", side_effect=AssertionError("Exact clip must be reused")) as tts:
                await coordinator._stream({**plan, "utterance_id": "u-two"}, 0)
            self.assertFalse(tts.called)
        asyncio.run(deliver())
        self.assertEqual(sum(p["type"] == "audio.end" for p in packets), 2)
        audio = self.hit()["audio"]
        self.assertEqual(audio, voice._cached(self.did, entry["answer"], store.load(self.did)))
        self.assertTrue(store.path(self.did, audio).is_file())

    def test_failed_or_cancelled_stream_never_caches_partial_audio(self):
        from server.runtime_delivery import DeliveryCoordinator
        entry = self.cache()
        plan = {"utterance_id": "u", "turn_id": "t", "speech": entry["answer"], "result": {"faq_entry_id": entry["id"]}}
        for failure in (RuntimeError("provider failed"), asyncio.CancelledError()):
            packets = []
            async def send(packet): packets.append(packet)
            async def stream(*args, **kwargs):
                yield {"audio": base64.b64encode(b"\0\0" * 2400).decode(), "sample_rate": 24000}
                raise failure
            async def deliver():
                with patch("server.llm.sarvam_stream.stream_tts", side_effect=stream):
                    try:
                        await DeliveryCoordinator(self.did, send)._stream(plan, 0)
                    except asyncio.CancelledError:
                        pass
            asyncio.run(deliver())
            self.assertIsNone(self.hit()["audio"])
            self.assertFalse(any(p["type"] == "audio.end" for p in packets))

    def test_empty_card_autoapproves_and_build_can_continue_without_rehearsal(self):
        from server import graph
        from server.agents import align
        faq.run(self.did, lambda _: None)
        def ready(demo):
            demo["approvals"].update({key: key != "faq" for key in store.CARDS})
            for stage in demo["stages"].values(): stage["status"] = "done"
        store.update(self.did, ready)
        graph.align_enter({"demo_id": self.did, "entry": "read"})
        self.assertTrue(store.load(self.did)["approvals"]["faq"])
        self.assertEqual(align.cards(self.did)["faq"]["empty_note"], "No questions yet; this card fills from customer questions")
        self.assertEqual(graph.after_author({"demo_id": self.did, "entry": "build"}), "voice")
        self.assertEqual(graph.after_voice({"demo_id": self.did, "entry": "build"}), "bundle")

    def test_customer_unknown_is_a_coach_gap_and_never_a_fact(self):
        from server.agents import coach
        unknown = faq.record_unknown(self.did, "What is the warranty period?", session_id="customer")
        playbook = coach.run(self.did, lambda _: None)
        self.assertTrue(any(unknown["question"] in gap.get("what", "") for gap in playbook["evidence_gaps"]))
        self.assertEqual(store.read_json(self.did, "understanding.json")["facts"], self.und["facts"])

    def test_rehearsal_endpoint_starts_only_explicitly(self):
        from fastapi.testclient import TestClient
        from server import graph
        from server.app import app
        with patch.object(graph, "start_rehearsal") as start:
            response = TestClient(app).post(f"/api/demos/{self.did}/rehearsal", json={})
        self.assertEqual(response.status_code, 200)
        start.assert_called_once_with(self.did)


if __name__=='__main__':
    unittest.main(verbosity=2)

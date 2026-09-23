"""Public search remains fetched, cited, turn-local and bounded. No provider or network calls."""
import asyncio
import copy
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

scratch = tempfile.TemporaryDirectory(prefix="runtime-web-search-")
os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", STORAGE_BACKEND="local", DEMO_STUDIO_DATA=scratch.name,
                  DEMO_STUDIO_GRAPH_DB=str(Path(scratch.name)/"graph.sqlite"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import config, runtime_graph, runtime_state, runtime_tools, store
from server.agents import faq
from server.llm import gemini
config.DATA_DIR = Path(scratch.name)
URL = "https://maker.example/creta/safety"
QUOTE = "Six airbags are available."

class WebSearch(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.blockers = [patch.object(socket.socket, "connect", side_effect=AssertionError("outbound forbidden")),
                         patch.object(socket, "create_connection", side_effect=AssertionError("outbound forbidden"))]
        for blocker in self.blockers: blocker.start()
        self.demo = store.new_demo("Creta")
        self.did = self.demo["id"]
        store.write_json(self.did, "understanding.json", {"facts":[], "unknowns":[]})
        store.write_json(self.did, "bundle.json", {"slides":[], "version":1})
        self.calls = []

    def tearDown(self):
        for blocker in reversed(self.blockers): blocker.stop()

    def fetch(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return {"final_url":url, "sections":[{"text":QUOTE, "locator":"Safety"}], "links":[]}

    def search(self, query="How many airbags are available?", urls=None, **kwargs):
        with patch.object(runtime_tools, "_search_sources", return_value={"urls": urls or [URL], "search_queries":[query], "search_entry_point":"<div>Search suggestions</div>"}), patch("server.crawl.fetch_public", side_effect=self.fetch):
            return runtime_tools.web_search({"tool":"web_search", "query":query}, query, **kwargs)

    def test_schema_addition_preserves_other_tool_fields(self):
        self.assertEqual(runtime_state.ToolRequest(tool="web_search", query="airbags").tool, "web_search")
        with self.assertRaises(ValueError): runtime_state.ToolRequest(tool="web_search", query="a"*401)

    def test_mock_fails_closed_without_provider(self):
        with patch.object(gemini, "client", side_effect=AssertionError("provider called")):
            with self.assertRaisesRegex(ValueError, "mock mode"):
                runtime_tools.web_search({"tool":"web_search", "query":"airbags"}, "airbags")

    def test_fetched_sections_only_are_evidence_and_keep_citations(self):
        result = self.search()
        fact = result["evidence"][0]
        self.assertEqual(fact["value"], QUOTE)
        self.assertEqual(fact["source"], {"ref":URL, "quote":QUOTE, "locator":"Safety"})
        self.assertEqual(fact["provenance"], "live_web")
        self.assertTrue(fact["scope_unverified"])
        self.assertTrue(fact["id"].startswith("W"))
        self.assertIn("Search suggestions", result["search_entry_point"])
        self.assertEqual(store.read_json(self.did, "understanding.json")["facts"], [])

    def test_max_two_unique_fetches_and_existing_size_limit(self):
        self.search(urls=[URL,URL,"https://review.example/safety","https://extra.example/safety"])
        self.assertEqual([url for url,_ in self.calls], [URL,"https://review.example/safety"])
        self.assertTrue(all(0 < args["timeout"] <= 5 and args["max_bytes"] == 2_000_000 for _,args in self.calls))

    def test_no_cited_sources_does_not_fetch_or_use_search_prose(self):
        with patch.object(runtime_tools, "_search_sources", return_value={"urls":[],"text":QUOTE}), patch("server.crawl.fetch_public") as fetch:
            with self.assertRaisesRegex(ValueError, "no cited"):
                runtime_tools.web_search({"tool":"web_search", "query":"airbags"}, "airbags")
        fetch.assert_not_called()

    def test_question_only_and_unrelated_sections_cannot_answer(self):
        with patch.object(runtime_tools, "_search_sources", return_value={"urls":[URL]}), patch("server.crawl.fetch_public", return_value={"sections":[{"text":"How many airbags are available?"},{"text":"This is an unrelated warranty page."}]}):
            with self.assertRaisesRegex(ValueError, "No fetched"):
                runtime_tools.web_search({"tool":"web_search", "query":"airbags"}, "airbags")

    def test_table_headers_footnotes_are_preserved_whole(self):
        section={"text":"Airbags | Trim A | Trim B\nCount | 6 | 4\nOnly applies to the stated market.","kind":"table","rows":[["Airbags","Trim A","Trim B"],["Count","6","4"]],"footnote":"Only applies to the stated market."}
        with patch.object(runtime_tools, "_search_sources", return_value={"urls":[URL]}), patch("server.crawl.fetch_public", return_value={"sections":[section]}):
            fact=runtime_tools.web_search({"tool":"web_search", "query":"airbags"}, "airbags")["evidence"][0]
        self.assertEqual(fact["value"],section["text"])
        self.assertEqual(fact["context"]["rows"],section["rows"])
        self.assertEqual(fact["context"]["footnote"],section["footnote"])

    def test_redirect_is_cited_at_actual_fetched_url(self):
        target="https://actual.example/safety"
        with patch.object(runtime_tools, "_search_sources", return_value={"urls":[URL]}), patch("server.crawl.fetch_public", return_value={"final_url":target,"text":QUOTE}):
            result=runtime_tools.web_search({"tool":"web_search", "query":"airbags"}, "airbags")
        self.assertEqual(result["evidence"][0]["source"]["ref"],target)

    def test_private_or_failed_sources_are_not_evidence(self):
        with patch.object(runtime_tools, "_search_sources", return_value={"urls":["http://127.0.0.1/private"]}), patch("server.crawl.fetch_public", side_effect=ValueError("Private address")):
            with self.assertRaisesRegex(ValueError, "No fetched"):
                runtime_tools.web_search({"tool":"web_search", "query":"airbags"}, "airbags")

    def test_actual_fetch_security_rejects_private_dns_before_socket(self):
        answer=[(socket.AF_INET,socket.SOCK_STREAM,6,"",("127.0.0.1",80))]
        with patch.object(runtime_tools,"_search_sources",return_value={"urls":["http://private.example/"]}), patch.object(socket,"getaddrinfo",return_value=answer):
            with self.assertRaisesRegex(ValueError,"No fetched"):
                runtime_tools.web_search({"tool":"web_search","query":"airbags"},"airbags")

    def test_oversize_whole_section_is_dropped_not_truncated(self):
        with patch.object(runtime_tools,"_search_sources",return_value={"urls":[URL]}), patch("server.crawl.fetch_public",return_value={"text":"Airbags "+"x"*12000}):
            with self.assertRaisesRegex(ValueError,"No fetched"):
                runtime_tools.web_search({"tool":"web_search","query":"airbags"},"airbags")

    def test_cancellation_before_discovery_prevents_all_work(self):
        event=threading.Event();event.set()
        with patch.object(runtime_tools,"_search_sources") as search:
            with self.assertRaises(InterruptedError): runtime_tools.web_search({"tool":"web_search", "query":"airbags"}, "airbags",cancel_event=event)
        search.assert_not_called()

    def test_cancellation_after_discovery_prevents_fetch(self):
        event=threading.Event()
        def discover(*_): event.set();return {"urls":[URL]}
        with patch.object(runtime_tools,"_search_sources",side_effect=discover), patch("server.crawl.fetch_public") as fetch:
            with self.assertRaises(InterruptedError): runtime_tools.web_search({"tool":"web_search", "query":"airbags"}, "airbags",cancel_event=event)
        fetch.assert_not_called()

    def test_deadline_after_discovery_prevents_fetch(self):
        with patch.object(runtime_tools,"_search_sources",return_value={"urls":[URL]}), patch("server.runtime_tools.time.monotonic",side_effect=[10,10.1,16]), patch("server.crawl.fetch_public") as fetch:
            with self.assertRaises(TimeoutError): runtime_tools.web_search({"tool":"web_search", "query":"airbags"}, "airbags")
        fetch.assert_not_called()

    def test_cancellation_after_page_does_not_publish_evidence(self):
        event=threading.Event()
        def fetch(*_,**kwargs): event.set();return {"text":QUOTE}
        with patch.object(runtime_tools,"_search_sources",return_value={"urls":[URL]}),patch("server.crawl.fetch_public",side_effect=fetch):
            with self.assertRaises(InterruptedError):
                runtime_tools.web_search({"tool":"web_search","query":"airbags"},"airbags",cancel_event=event)

    def test_optional_timeout_retains_completed_cited_passage(self):
        clock = [0.0]
        def fetch(url, **kwargs):
            if url == URL:
                clock[0] += .1
                return {"final_url": url, "text": QUOTE}
            clock[0] += kwargs["timeout"]
            raise TimeoutError("optional page timed out")
        with patch.object(runtime_tools.time, "monotonic", side_effect=lambda: clock[0]), \
             patch.object(runtime_tools, "_search_sources", return_value={"urls": [URL, "https://slow.example/safety"]}), \
             patch("server.crawl.fetch_public", side_effect=fetch):
            result = runtime_tools.web_search({"tool": "web_search", "query": "airbags"}, "airbags")
        self.assertEqual(result["evidence"][0]["source"]["ref"], URL)
        self.assertEqual(result["evidence"][0]["source"]["quote"], QUOTE)
        self.assertTrue(any("optional page timed out" in warning for warning in result["coverage"]))
        self.assertLess(result["elapsed_ms"], 5000)

    def test_cancelled_optional_timeout_discards_prior_page(self):
        event = threading.Event()
        def fetch(url, **kwargs):
            if url == URL:
                return {"text": QUOTE}
            event.set()
            raise TimeoutError("optional page timed out during cancellation")
        with patch.object(runtime_tools, "_search_sources", return_value={"urls": [URL, "https://slow.example/safety"]}), \
             patch("server.crawl.fetch_public", side_effect=fetch):
            with self.assertRaises(InterruptedError):
                runtime_tools.web_search({"tool": "web_search", "query": "airbags"}, "airbags", cancel_event=event)

    async def test_actual_dispatch_returns_partial_search_before_outer_deadline(self):
        control = runtime_state.claim_turn(self.did, "s_partial", "t_partial", budget=.5)
        state = {"demo_id": self.did, "question": "Search the web for airbags", "history": [], "evidence": [],
                 "tool_results": [], "errors": [], "tool_count": 0, "tool_rounds": 0, "control": control,
                 "decision": {"action": "tools", "tool_calls": [{"tool": "web_search", "query": "airbags"}]}}
        def fetch(url, **kwargs):
            if url == URL:
                return {"final_url": url, "text": QUOTE}
            time.sleep(kwargs["timeout"])
            raise TimeoutError("optional page timed out")
        with patch.object(runtime_tools, "_search_sources", return_value={"urls": [URL, "https://slow.example/safety"]}), \
             patch("server.crawl.fetch_public", side_effect=fetch):
            result = await runtime_graph.tools_node(state)
        self.assertGreater(control.remaining(), 0)
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["tool_count"], 1)
        self.assertEqual(result["tool_rounds"], 1)
        self.assertEqual(result["evidence"][0]["source"]["quote"], QUOTE)
        self.assertEqual(result["tool_results"][0]["pages"][0]["url"], URL)

    def test_official_sdk_contract_uses_only_cited_grounding_metadata(self):
        metadata=NS(grounding_chunks=[NS(web=NS(uri=URL)),NS(web=NS(uri="https://uncited.example/"))],
                    grounding_supports=[NS(grounding_chunk_indices=[0])],web_search_queries=["airbags"],search_entry_point=NS(rendered_content="widget"))
        response=NS(candidates=[NS(grounding_metadata=metadata)],text="Invented search prose is discarded.",usage_metadata=NS(prompt_token_count=10,candidates_token_count=5,thoughts_token_count=0))
        calls=[]
        def generate(**kwargs): calls.append(kwargs);return response
        with patch.object(config,"MOCK_LLM",False),patch.object(gemini,"client",return_value=NS(models=NS(generate_content=generate))):
            result=runtime_tools._search_sources("airbags",2)
        self.assertEqual(result["urls"],[URL]);self.assertNotIn("text",result)
        self.assertEqual(calls[0]["model"],config.GEMINI_RUNTIME_MODEL)
        self.assertIsNotNone(calls[0]["config"].tools[0].google_search)
        self.assertEqual(calls[0]["config"].http_options.retry_options.attempts,1)
        self.assertEqual(calls[0]["config"].http_options.timeout,2000)

    def test_web_answer_is_never_cacheable(self):
        fact=self.search()["evidence"][0]
        result={"answered":True,"answer":QUOTE,"fact_ids":[fact["id"]],"facts":[fact],"tool_results":[{"tool":"web_search"}]}
        self.assertIsNone(faq.cache_answer(self.did,"airbags?",result))
        self.assertIsNone(store.read_json(self.did,"faq.json"))

    def test_existing_supplied_url_tool_still_rejects_unprovided_urls(self):
        with patch("server.crawl.fetch_public") as fetch:
            with self.assertRaisesRegex(ValueError,"exact public website"):
                runtime_tools.source_lookup({"tool":"source_lookup","url":URL,"query":"airbags"},"airbags",[])
        fetch.assert_not_called()

    def test_public_fact_answer_passes_normal_grounding_with_host_attribution(self):
        fact=self.search()["evidence"][0]
        result,errors=runtime_graph.validate_decision({"action":"answer","answered":True,"sentences":[{"text":QUOTE,"kind":"fact","fact_ids":[fact["id"]]}]},[fact],"How many airbags are available?")
        self.assertEqual(errors,[])
        self.assertTrue(result["answered"])
        self.assertEqual(result["answer"],"According to maker.example, six airbags are available.")

    async def test_dispatch_counts_and_rejects_repeated_search(self):
        state={"demo_id":self.did,"question":"Search the web for airbags","history":[],"evidence":[],"tool_results":[],"errors":[],"tool_count":0,"tool_rounds":0,
               "decision":{"action":"tools","tool_calls":[{"tool":"web_search","query":"airbags"}]*2},
               "control":runtime_state.claim_turn(self.did,"s_search","t_one",budget=12)}
        expected=self.search()
        with patch.object(runtime_graph,"web_search",return_value=expected) as search:
            result=await runtime_graph.tools_node(state)
        self.assertEqual(search.call_count,1);self.assertEqual(result["tool_count"],2)
        self.assertEqual(result["tool_results"][1]["error"],"Public search already attempted for this turn")
        self.assertEqual(len(result["evidence"]),1)

    def test_explicit_search_intents_and_negation_are_bounded(self):
        for text in ("Search the web for Creta airbags", "Please search the public web for safety", "Could you look online for airbags?",
                     "Look this up online", "Check online for warranty", "What is the warranty? Search online, please."):
            self.assertTrue(runtime_graph._explicit_web_search(text),text)
        for text in ("How many airbags?", "The web could have that answer", "Don't search the web", "Do not look online",
                     "No need to search the internet", "Answer without searching the web", 'What does "search the web" mean?',
                     "I saw someone search the web for this", "What does search online mean?"):
            self.assertFalse(runtime_graph._explicit_web_search(text),text)

    def test_followup_search_uses_actual_customer_question_context(self):
        request=runtime_graph._requested_web_search({"demo_id":self.did,"question":"Look this up online",
            "history":[{"role":"user","text":"How many airbags?"},{"role":"assistant","text":"Invented model details"}]})
        self.assertIn("airbags",request["query"])
        self.assertNotIn("Invented",request["query"])

    def test_negated_search_does_not_fall_into_automatic_customer_source_lookup(self):
        for question in ("Don't search the web for warranty", "Do not look online for airbags", "Answer without searching the internet"):
            state={"demo_id":self.did,"question":question,"customer_urls":[URL],"evidence":[]}
            self.assertIsNone(runtime_graph._automatic_lookup(state),question)

    async def test_explicit_intent_dispatches_before_model_and_url_checks_take_precedence(self):
        state={"demo_id":self.did,"question":"Please search the web for airbags","history":[],"evidence":[],"timings":{},
               "control":runtime_state.claim_turn(self.did,"s_dispatch","t_search")}
        result=await runtime_graph.reason(state)
        self.assertEqual(result["decision"]["tool_calls"][0]["tool"],"web_search")
        state["question"]="Check "+URL+". Search the web for airbags."
        result=await runtime_graph.reason(state)
        self.assertEqual(result["decision"]["tool_calls"][0]["tool"],"source_lookup")

    async def test_model_can_search_when_retrieved_evidence_cannot_answer(self):
        state={"demo_id":self.did,"question":"How many airbags?","history":[],"evidence":[],"tool_results":[],"errors":[],
               "decision":{"action":"tools","tool_calls":[{"tool":"web_search","query":"airbags"}]},
               "control":runtime_state.claim_turn(self.did,"s_no_intent","t_search")}
        with patch.object(runtime_graph,"web_search",return_value=self.search()) as search:
            result=await runtime_graph.tools_node(state)
        search.assert_called_once()
        self.assertEqual(result["errors"],[])
        self.assertEqual(len(result["evidence"]),1)

    async def test_empty_retrieval_automatically_searches_before_model(self):
        before=copy.deepcopy(store.read_json(self.did,"understanding.json"))
        with patch.object(runtime_tools,"_search_sources",return_value={"urls":[URL]}) as discover,patch("server.crawl.fetch_public",side_effect=self.fetch):
            final=await runtime_graph.run_turn(self.did,{"question":"How many airbags are available?","session_id":"automatic","skip_bank":True})
        discover.assert_called_once()
        self.assertIn("Creta",discover.call_args.args[0])
        self.assertTrue(final["result"]["answered"],final["result"])
        self.assertEqual(final["result"]["answer"],"According to maker.example, six airbags are available.")
        self.assertEqual(final["tool_rounds"],1)
        self.assertEqual(store.read_json(self.did,"understanding.json"),before)
        self.assertFalse((store.read_json(self.did,"faq.json") or {}).get("entries"))

    async def test_first_clean_decline_searches_despite_nonempty_retrieval(self):
        fact={"id":"F1","claim":"Sunroof","value":"A sunroof is available.","approved":True,"source":{"ref":"brochure","quote":"A sunroof is available."}}
        store.write_json(self.did,"understanding.json",{"facts":[fact],"unknowns":[]})
        original=runtime_graph._mock_decision
        def decision(state):
            if not state.get("tool_results"):
                return runtime_state.TurnDecision(action="answer",answered=False,sentences=[{"text":"I don't have that information in the reviewed material.","kind":"limitation"}])
            live=[item for item in state["evidence"] if item.get("provenance")=="live_web"]
            return original({**state,"evidence":live})
        with patch.object(runtime_graph,"_mock_decision",side_effect=decision),patch.object(runtime_tools,"_search_sources",return_value={"urls":[URL]}) as discover,patch("server.crawl.fetch_public",side_effect=self.fetch):
            final=await runtime_graph.run_turn(self.did,{"question":"How many airbags?","session_id":"decline","skip_bank":True})
        discover.assert_called_once()
        self.assertTrue(final["result"]["answered"],final["result"])
        self.assertEqual(final["tool_count"],1)

    async def test_customer_site_precedes_public_fallback_within_two_rounds(self):
        preferred="https://preferred.example/creta"
        order=[]
        def fetch(url,**kwargs):
            order.append(url)
            if url==preferred: raise ValueError("Customer page temporarily unavailable")
            return self.fetch(url,**kwargs)
        with patch.object(runtime_tools,"_search_sources",return_value={"urls":[URL]}) as discover,patch("server.crawl.fetch_public",side_effect=fetch):
            final=await runtime_graph.run_turn(self.did,{"question":"How many airbags?","session_id":"preferred","skip_bank":True,"profile":{"customer_urls":[preferred]}})
        self.assertEqual(order,[preferred,URL])
        discover.assert_called_once()
        self.assertEqual([item["tool"] for item in final["tool_results"]],["source_lookup","web_search"])
        self.assertEqual((final["tool_count"],final["tool_rounds"]),(2,2))
        self.assertTrue(final["result"]["answered"],final["result"])

    async def test_successful_customer_site_answer_does_not_search_again(self):
        with patch.object(runtime_tools,"_search_sources") as discover,patch("server.crawl.fetch_public",side_effect=self.fetch):
            final=await runtime_graph.run_turn(self.did,{"question":"How many airbags?","session_id":"preferred-good","skip_bank":True,"profile":{"customer_urls":[URL]}})
        discover.assert_not_called()
        self.assertTrue(final["result"]["answered"])
        self.assertEqual(final["tool_rounds"],1)

    async def test_greetings_controls_clarifications_failures_and_calculations_never_auto_search(self):
        state={"demo_id":self.did,"question":"How many airbags?","history":[],"evidence":[],"errors":[],
               "decision":{"action":"answer","answered":False}}
        for question in ("Hello", "Continue the demo", "Please book a test drive", "Don't search online for airbags",
                         "Calculate 10 lakh at 9% per year over 5 years", "What is 2 + 2?", "What would fuel cost?", "What is my EMI?"):
            for decline in (False,True):
                self.assertIsNone(runtime_graph._automatic_public_search({**state,"question":question},decline=decline),question)
        for patch_state in ({"decision":{"action":"clarify","answered":False}},
                            {"errors":["reasoning_unavailable"]},
                            {"decision":{"action":"answer","answered":False,"cta":"book-test-drive"}},
                            {"tool_results":[{"tool":"calculator","error":"Missing input"}]}):
            for decline in (False,True):
                self.assertIsNone(runtime_graph._automatic_public_search({**state,**patch_state},decline=decline),patch_state)
        missing={**state,"question":"What is the on-road price?"}
        self.assertIsNone(runtime_graph._automatic_public_search(missing))

    async def test_failed_search_is_not_retried_or_promoted(self):
        with patch.object(runtime_graph,"web_search",side_effect=ValueError("No cited public sources")) as search:
            final=await runtime_graph.run_turn(self.did,{"question":"How many airbags?","session_id":"failed-search","skip_bank":True})
        search.assert_called_once()
        self.assertFalse(final["result"]["answered"])
        self.assertEqual((final["tool_rounds"],final["tool_count"]),(1,1))
        self.assertFalse(final["result"]["fact_ids"])
        self.assertFalse((store.read_json(self.did,"faq.json") or {}).get("entries"))

    def test_automatic_search_respects_shared_tool_limits_and_prior_attempt(self):
        state={"demo_id":self.did,"question":"How many airbags?","evidence":[],"decision":{"action":"answer","answered":False}}
        for patch_state in ({"tool_rounds":2},{"tool_count":4},{"tool_results":[{"tool":"web_search","error":"timeout"}]}):
            for decline in (False,True):
                self.assertIsNone(runtime_graph._automatic_public_search({**state,**patch_state},decline=decline))

    async def test_fresh_source_requests_bypass_compatible_cache_before_retrieval(self):
        for question in ("Search the web for airbags", "Check "+URL+" for airbags"):
            with patch.object(runtime_graph,"retrieve",side_effect=AssertionError("Fresh check bypasses cached evidence")):
                update,result=await runtime_graph._validated_bank_result({"question":question},{"answer":QUOTE,"fact_ids":["F1"]})
            self.assertEqual(update,{})
            self.assertIsNone(result)

    async def test_actual_requested_search_fetches_and_cites_without_facts_or_cache_writes(self):
        before=copy.deepcopy(store.read_json(self.did,"understanding.json"))
        with patch.object(runtime_tools,"_search_sources",return_value={"urls":[URL]}),patch("server.crawl.fetch_public",side_effect=self.fetch):
            final=await runtime_graph.run_turn(self.did,{"question":"Search the web for airbags","session_id":"explicit","turn_id":"search","skip_bank":True})
        self.assertTrue(final["result"]["answered"],final["result"])
        self.assertEqual(final["result"]["answer"],"According to maker.example, six airbags are available.")
        self.assertEqual(final["result"]["tool_results"][0]["tool"],"web_search")
        self.assertEqual(store.read_json(self.did,"understanding.json"),before)
        self.assertFalse((store.read_json(self.did,"faq.json") or {}).get("entries"))

if __name__ == "__main__": unittest.main()

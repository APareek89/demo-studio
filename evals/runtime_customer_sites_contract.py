"""Customer source persistence and bounded lookup, with fake pages and blocked sockets."""
import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

scratch = tempfile.TemporaryDirectory(prefix="runtime-customer-sites-")
os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", STORAGE_BACKEND="local", DEMO_STUDIO_DATA=scratch.name,
                  DEMO_STUDIO_GRAPH_DB=str(Path(scratch.name) / "graph.sqlite"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import config, runtime_graph, runtime_state, runtime_tools, store
from server.runtime_state import TurnDecision
config.DATA_DIR = Path(scratch.name)

URL = "https://hyundai.example/creta"
FACT = {"id":"F1", "claim":"Airbags", "value":"Six airbags are available.", "approved":True, "truth":"source",
        "source":{"ref":"brochure", "quote":"Six airbags are available."}}


class CustomerSites(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.blockers = [patch.object(socket.socket, "connect", side_effect=AssertionError("outbound forbidden")),
                         patch.object(socket, "create_connection", side_effect=AssertionError("outbound forbidden"))]
        for blocker in self.blockers: blocker.start()
        self.demo = store.new_demo("Hyundai Creta")
        self.demo["product"]["name"] = "Hyundai Creta"
        self.demo["settings"]["runtime_default_sites"] = "off"
        self.demo["sources"] = [{"id":"owner", "kind":"url", "role":"product", "url":URL}]
        self.demo_id = self.demo["id"]
        store.save(self.demo_id, self.demo)
        store.write_json(self.demo_id, "bundle.json", {"slides":[], "version":1})
        store.write_json(self.demo_id, "understanding.json", {"facts":[FACT]})
        self.fetched = []

    def tearDown(self):
        for blocker in reversed(self.blockers): blocker.stop()

    def fetch(self, url, **kwargs):
        self.fetched.append((url, kwargs))
        return {"final_url":url, "sections":[{"text":"Six airbags are available.", "locator":"Safety"}], "links":[]}

    async def turn(self, question="How many airbags are available?", *, evidence=None, session="s_sites", turn="t_1", profile=None):
        body = {"session_id":session,"turn_id":turn,"question":question}
        if profile is not None: body["profile"] = profile
        with patch("server.knowledge.retrieve", return_value={"evidence":evidence or []}), patch("server.crawl.fetch_public", side_effect=self.fetch):
            return await runtime_graph.run_turn(self.demo_id, body)

    def test_parser_accepts_bare_www_https_and_excludes_email_number_fragments(self):
        text = 'Use (hyundai.com/in/en/find-a-car/creta), www.example.com/car; HTTPS://EXAMPLE.ORG/car! Email user@example.co.in and foo.bar@example.com. Version 1.5 is a number.'
        self.assertEqual(runtime_tools.supplied_urls(text), ["https://hyundai.com/in/en/find-a-car/creta", "https://www.example.com/car", "HTTPS://EXAMPLE.ORG/car"])
        self.assertEqual(runtime_tools.supplied_urls("hyundai.com hyundai.com", [{"role":"assistant","text":"https://unrequested.example/car"}]), ["https://hyundai.com"])

    def test_bare_filenames_and_unlisted_suffixes_are_not_customer_sites(self):
        self.assertEqual(runtime_tools.supplied_urls("creta.pdf node.js specs.xlsx photos.JPG notes.md source.example/catalog"), [])
        self.assertEqual(runtime_tools.supplied_urls(" ".join(f"file.{extension}" for extension in runtime_tools.DOC_EXTENSIONS)), [])
        self.assertEqual(runtime_tools.supplied_urls("hyundai.com/in/en/find-a-car/creta www.carwale.com https://x.in"),
                         ["https://hyundai.com/in/en/find-a-car/creta", "https://www.carwale.com", "https://x.in"])

    def test_public_suffixes_two_level_forms_and_explicit_urls_keep_their_scope(self):
        for suffix in runtime_tools.PUBLIC_TLDS | {"co.in", "gov.in", "nic.in", "ac.in", "co.uk", "com.au"}:
            token = f"dealer.{suffix}:8443/car?trim=top#details"
            self.assertEqual(runtime_tools.supplied_urls(token), ["https://" + token])
        self.assertEqual(runtime_tools.supplied_urls("https://creta.pdf http://node.js www.specs.xlsx https://source.example/car www.source.example/car"),
                         ["https://creta.pdf", "http://node.js", "https://www.specs.xlsx", "https://source.example/car", "https://www.source.example/car"])

    def test_shared_javascript_python_parser_parity_and_limits(self):
        cases = ['(hyundai.com/in/en/find-a-car/creta), www.example.com; HTTPS://EXAMPLE.ORG/car!',
                 'user@example.co.in foo.bar@example.com 1.5-litre petrol', '[https://example.com/car]. https://example.com/car',
                 'creta.pdf node.js specs.xlsx source.example/catalog https://creta.pdf www.source.example/car',
                 ' '.join(f"file.{suffix}" for suffix in runtime_tools.DOC_EXTENSIONS),
                 *[f"dealer.{suffix}:8443/car?trim=top#details" for suffix in sorted(runtime_tools.PUBLIC_TLDS | {"co.in", "gov.in", "nic.in", "ac.in", "co.uk", "com.au"})],
                 ' '.join(f"source{i}.example.com/car" for i in range(12))]
        script = r'''const fs=require('node:fs'),vm=require('node:vm');const s=fs.readFileSync('web/player/player.js','utf8');const a=s.indexOf('const CUSTOMER_URL_PATTERN ='),b=s.indexOf('export function mountPlayer',a);const api=vm.runInNewContext(s.slice(a,b)+'\n({customerUrls,publicTlds:[...PUBLIC_TLDS].sort(),docExtensions:[...DOC_EXTENSIONS].sort()})');const cases=JSON.parse(fs.readFileSync(0,'utf8'));process.stdout.write(JSON.stringify({publicTlds:api.publicTlds,docExtensions:api.docExtensions,results:cases.map(t=>({all:api.customerUrls(t),intake:api.customerUrls(t,5)}))}));'''
        parsed = json.loads(subprocess.run(["node", "-e", script], input=json.dumps(cases), text=True, capture_output=True, check=True, cwd=Path(__file__).resolve().parents[1]).stdout)
        self.assertEqual(parsed["publicTlds"], sorted(runtime_tools.PUBLIC_TLDS))
        self.assertEqual(parsed["docExtensions"], sorted(runtime_tools.DOC_EXTENSIONS))
        self.assertEqual(runtime_tools.PUBLIC_TLDS, {"com","in","co","net","org","io","ai","info","biz","edu","gov","uk","de","jp","sg","ae","au","ca","us","eu"})
        self.assertEqual(runtime_tools.DOC_EXTENSIONS, {"pdf","doc","docx","xls","xlsx","ppt","pptx","csv","txt","md","json","js","cjs","mjs","ts","py","html","css","png","jpg","jpeg","gif","webp","svg","mp4","mov","wav","mp3","zip"})
        results = parsed["results"]
        for text, result in zip(cases, results):
            self.assertEqual(result["all"], runtime_tools.supplied_urls(text))
            self.assertEqual(result["intake"], runtime_tools.supplied_urls(text)[:5])
        self.assertEqual(len(results[-1]["all"]), 8)
        self.assertEqual(len(results[-1]["intake"]), 5)

    async def test_intake_urls_persist_and_merge_across_three_actual_graph_turns(self):
        await self.turn(evidence=[FACT], profile={"customer_urls":[URL, URL]})
        await self.turn("Airbags matter; I also supplied https://dealer.example/creta.", evidence=[FACT], turn="t_2", profile={"why":"Family travel"})
        await self.turn(evidence=[FACT], turn="t_3", profile={"customer_urls":["https://specs.example/creta"]})
        saved = runtime_state.previous_state(self.demo_id, "s_sites")
        self.assertEqual(saved["customer_urls"], [URL])  # Customer input cannot add permission.
        self.assertEqual(saved["profile"]["customer_urls"], saved["customer_urls"])
        self.assertEqual(saved["profile"]["why"], "Family travel")
        self.assertEqual(self.fetched, [])

    async def test_no_registry_evidence_fetches_once_and_attributes_live_answer(self):
        final = await self.turn(profile={"customer_urls":[URL]})
        self.assertEqual([url for url, _ in self.fetched], [URL])
        self.assertTrue(final["result"]["answer"].startswith("According to hyundai.example,"), final["result"])
        self.assertEqual(final["tool_rounds"], 1)
        self.assertEqual(final["tool_count"], 1)
        self.assertTrue(all(f["id"].startswith("W") and f["provenance"]=="live_web" for f in final["result"]["facts"]))
        self.assertNotIn("W", json.dumps(store.read_json(self.demo_id, "understanding.json")))

    async def test_supported_registry_answer_does_not_fetch(self):
        final = await self.turn(evidence=[FACT], profile={"customer_urls":[URL]})
        self.assertEqual(self.fetched, [])
        self.assertTrue(final["result"]["answered"])
        self.assertEqual(final["result"]["fact_ids"], ["F1"])

    async def test_model_decline_with_retrieved_evidence_gets_one_lookup_then_reasons_again(self):
        seen = []
        def decision(state):
            seen.append(state.get("tool_rounds", 0))
            live = [fact for fact in state["evidence"] if fact.get("provenance")=="live_web"]
            if live: return TurnDecision(action="answer", sentences=[{"text":live[0]["value"],"fact_ids":[live[0]["id"]]}])
            return TurnDecision(action="answer", answered=False, sentences=[{"text":"I don't have that information in the reviewed material.","kind":"limitation"}])
        with patch.object(runtime_graph, "_mock_decision", side_effect=decision):
            final = await self.turn(evidence=[FACT], profile={"customer_urls":[URL]})
        self.assertEqual(seen, [0, 1])
        self.assertEqual(len(self.fetched), 1)
        self.assertTrue(final["result"]["answer"].startswith("According to hyundai.example,"))

    async def test_selector_prefers_product_host_then_falls_back_to_first_supplied(self):
        await self.turn(profile={"customer_urls":["https://other.example/car", URL]})
        self.assertEqual(self.fetched[0][0], URL)
        self.fetched.clear()
        await self.turn(session="s_other", profile={"customer_urls":["https://third.example/car", "https://fourth.example/car"]})
        self.assertEqual(self.fetched[0][0], URL)

    def test_extra_allowlist_still_rejects_off_host_seed_and_cross_host_redirect(self):
        with patch("server.crawl.fetch_public", side_effect=self.fetch) as fetch:
            with self.assertRaisesRegex(ValueError, "demo owner"):
                runtime_tools.source_lookup({"tool":"source_lookup","url":"https://evil.example/car","query":"airbags"}, "Airbags?", [], extra=[URL], allowed_urls=[URL])
            fetch.assert_not_called()
        with patch("server.crawl.fetch_public", return_value={"final_url":"https://evil.example/car", "text":"Six airbags are available."}):
            with self.assertRaisesRegex(ValueError, "No readable section"):
                runtime_tools.source_lookup({"tool":"source_lookup","url":URL,"query":"airbags"}, "Airbags?", [], extra=[URL], allowed_urls=[URL])

    def test_as_per_website_cannot_attribute_stored_fact_to_an_unread_page(self):
        decision = TurnDecision(action="answer", sentences=[{"text":"As per the website, six airbags are available.","fact_ids":["F1"]}])
        result, errors = runtime_graph.validate_decision(decision.model_dump(), [FACT], "How many airbags are available?", {})
        self.assertIn("unverified_web_attribution", errors)
        self.assertFalse(result["answered"])

    async def test_explicit_check_bare_url_still_overrides_existing_registry_evidence(self):
        self.demo["sources"].append({"id":"owner-bare", "kind":"url", "url":"https://hyundai.com/"})
        store.save(self.demo_id, self.demo)
        final = await self.turn("Check hyundai.com/creta for airbags.", evidence=[FACT])
        self.assertEqual([url for url, _ in self.fetched], ["https://hyundai.com/creta"])
        self.assertEqual(final["tool_rounds"], 1)
        self.assertTrue(final["tool_results"][0]["evidence"][0]["id"].startswith("W"))

    async def test_legacy_default_setting_cannot_override_owner_source_permission(self):
        self.demo["product"]["url"] = "https://unselected.example/car"
        self.demo["sources"] = [
            {"id":"source-root","kind":"url","role":"product","url":URL,"use_in_demo":True},
            {"id":"source-rival","kind":"url","role":"competitor","url":"https://competitor.example/car"},
            {"id":"source-excluded","kind":"url","role":"product","url":"https://excluded.example/car","use_in_demo":False},
            {"id":"source-child","kind":"url","role":"product","url":"https://child.example/car","crawl_parent":"source-root"},
        ]
        store.save(self.demo_id, self.demo)
        await self.turn(session="s_off")
        self.assertEqual([url for url, _ in self.fetched], [URL])
        self.fetched.clear()
        self.demo["settings"]["runtime_default_sites"]="on"; store.save(self.demo_id,self.demo)
        await self.turn(session="s_on")
        self.assertEqual([url for url, _ in self.fetched], [URL])
        self.assertEqual(runtime_state.previous_state(self.demo_id,"s_on")["customer_urls"], [URL,"https://competitor.example/car"])

    async def test_interactions_and_explicit_no_lookup_never_auto_fetch(self):
        for index, question in enumerate(["Hello", "Continue the demo", "Thank you", "Do not check the website; how many airbags are there?"]):
            await self.turn(question, session=f"s_no_{index}", profile={"customer_urls":[URL]})
        self.assertEqual(self.fetched, [])
        control = runtime_state.TurnControl(10**20)
        state={"question":"Which version?", "demo_id":self.demo_id, "customer_urls":[URL], "control":control,
               "decision":TurnDecision(action="clarify", answered=False, clarification="Which version?").model_dump()}
        self.assertEqual(runtime_graph.after_reason(state), "validate")

    async def test_cancellation_during_fetch_does_not_publish_live_evidence(self):
        claim = runtime_graph.claim_turn
        controls = []
        def own(*args, **kwargs):
            control = claim(*args, **kwargs); controls.append(control); return control
        def cancel_fetch(url, **kwargs):
            controls[-1].cancelled.set(); return self.fetch(url, **kwargs)
        with patch.object(runtime_graph, "claim_turn", side_effect=own), patch("server.knowledge.retrieve", return_value={"evidence":[]}), patch("server.crawl.fetch_public", side_effect=cancel_fetch):
            with self.assertRaises(InterruptedError):
                await runtime_graph.run_turn(self.demo_id,{"session_id":"s_cancel","turn_id":"t_1","question":"How many airbags?","profile":{"customer_urls":[URL]}})
        self.assertEqual(runtime_state.previous_state(self.demo_id,"s_cancel")["phase"], "accepted")

    async def test_fake_clock_lookup_stays_within_tool_and_total_deadlines(self):
        clock = [100.0]
        class Control:
            def remaining(self):
                left = 112.0-clock[0]
                if left<=0: raise TimeoutError("Conversation deadline reached")
                return left
        def fetch(url, **kwargs):
            self.assertLessEqual(kwargs["timeout"], 5)
            clock[0] += 4
            return self.fetch(url, **kwargs)
        state={"demo_id":self.demo_id,"question":"How many airbags?","history":[],"customer_urls":[URL],"control":Control(),
               "decision":TurnDecision(action="tools",tool_calls=[{"tool":"source_lookup","url":URL,"query":"airbags"}]).model_dump()}
        fake_time = SimpleNamespace(monotonic=lambda: clock[0], time=time.time)
        with patch.object(runtime_tools, "time", fake_time), patch.object(runtime_graph, "time", fake_time), patch("server.crawl.fetch_public", side_effect=fetch):
            result = await runtime_graph.tools_node(state)
        self.assertEqual(result["tool_count"], 1)
        self.assertEqual(result["timings"]["tools_ms"], 4000)
        self.assertLess(clock[0]-100,12)
        for rounds, count in [(2,0),(0,4),(1,1)]:
            self.assertIsNone(runtime_graph._automatic_lookup({**state,"tool_rounds":rounds,"tool_count":count,"decision":{"answered":False}},decline=True))

    def test_private_source_still_fails_before_outbound_connection(self):
        url="http://127.0.0.1/private"
        with self.assertRaisesRegex(ValueError,"Could not read"):
            runtime_tools.source_lookup({"tool":"source_lookup","url":url,"query":"airbags"},"Airbags?",[],extra=[url],allowed_urls=[url])

    async def test_decline_ignores_unrequested_stale_tool_calls(self):
        state={"demo_id":self.demo_id,"question":"How many airbags?","history":[],"customer_urls":[URL],
               "control":runtime_state.TurnControl(time.monotonic()+12), "evidence":[FACT],
               "decision":TurnDecision(action="answer",answered=False,tool_calls=[{"tool":"source_lookup","url":"https://evil.example/car","query":"airbags"}]).model_dump()}
        self.assertEqual(runtime_graph.after_reason(state), "tools")
        with patch("server.crawl.fetch_public", side_effect=self.fetch):
            result=await runtime_graph.tools_node(state)
        self.assertEqual([url for url,_ in self.fetched], [URL])
        self.assertEqual(result["tool_count"],1)

    async def test_reason_payload_includes_persisted_customer_urls(self):
        payloads=[]
        def model(system,payload,*args,**kwargs):
            payloads.append(json.loads(payload))
            return TurnDecision(action="answer", sentences=[{"text":FACT["value"],"fact_ids":["F1"]}])
        state={"demo_id":self.demo_id,"question":"How many airbags?","history":[],"customer_urls":[URL],
               "control":runtime_state.TurnControl(time.monotonic()+12), "evidence":[FACT]}
        with patch.object(runtime_graph.config,"MOCK_LLM",False), patch.object(runtime_graph.runtime,"structured",side_effect=model):
            await runtime_graph.reason(state)
        self.assertEqual(payloads[0]["CUSTOMER_URLS"],[URL])

    def test_owner_restricted_prompt_and_isolated_storage(self):
        self.assertIn("Only websites supplied by the demo owner authorize live access.", runtime_graph.SYSTEM)
        self.assertTrue(str(config.DATA_DIR).startswith(scratch.name))


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Owner-domain runtime permission: real graph, fake pages, no outbound sockets."""
import copy
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

scratch = tempfile.TemporaryDirectory(prefix="runtime-domain-")
os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", STORAGE_BACKEND="local", DEMO_STUDIO_DATA=scratch.name,
                  DEMO_STUDIO_GRAPH_DB=str(Path(scratch.name) / "graph.sqlite"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import config, crawl, runtime_graph as graph, runtime_state, runtime_tools as tools, store
config.DATA_DIR = Path(scratch.name)
OWNER = "https://maker.example/abc"
PAGE = "https://maker.example/safety"
OUTSIDE = "https://other.example/safety"
QUOTE = "Six airbags are available."
FACT = {"id":"F1", "claim":"Airbags", "value":QUOTE, "approved":True, "truth":"source",
        "source":{"ref":"uploaded-brochure", "quote":QUOTE}}


class RuntimeDomains(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.blockers = [patch.object(socket, name, side_effect=AssertionError("network forbidden"))
                         for name in ("getaddrinfo", "create_connection")]
        self.blockers += [patch.object(socket.socket, name, side_effect=AssertionError("network forbidden"))
                          for name in ("connect", "connect_ex", "sendto")]
        for blocker in self.blockers:
            blocker.start()
        self.demo = store.new_demo("Creta")
        self.did = self.demo["id"]
        self.set_sources([OWNER])
        store.write_json(self.did, "understanding.json", {"facts":[FACT], "unknowns":[]})
        store.write_json(self.did, "bundle.json", {"slides":[], "version":1})
        self.reads = []

    def tearDown(self):
        for blocker in reversed(self.blockers):
            blocker.stop()

    def set_sources(self, urls):
        self.demo["sources"] = [{"id":f"s{i}", "kind":"url", "role":"product", "url":url} for i,url in enumerate(urls)]
        store.save(self.did, self.demo)

    def fetch(self, url, **kwargs):
        self.reads.append((url, kwargs))
        return {"final_url":url, "sections":[{"text":QUOTE, "locator":"Safety"}], "links":[]}

    def search(self, urls, *, allowed=None):
        with patch.object(tools, "_search_sources", return_value={"urls":urls, "search_entry_point":"<a href='https://other.example'>Other</a>"}) as discover, \
             patch.object(crawl, "fetch_public", side_effect=self.fetch):
            result = tools.web_search({"tool":"web_search", "query":"airbags"}, "airbags", allowed_urls=[OWNER] if allowed is None else allowed)
        return result, discover

    async def turn(self, question="How many airbags?", *, evidence=None, profile=None, session="test"):
        with patch("server.knowledge.retrieve", return_value={"evidence":evidence or []}), \
             patch.object(crawl, "fetch_public", side_effect=self.fetch):
            return await graph.run_turn(self.did, {"question":question, "profile":profile or {}, "session_id":session, "skip_bank":True})

    def test_authority_only_enabled_owner_root_url_rows(self):
        demo = {"product":{"url":OUTSIDE}, "sources":[
            {"kind":"url", "url":OWNER}, {"kind":"url", "url":OWNER},
            {"kind":"url", "url":OUTSIDE, "crawl_parent":"s0"},
            {"kind":"url", "url":OUTSIDE, "use_in_demo":False},
            {"kind":"url", "url":OUTSIDE, "crawl_active":False, "use_in_demo":False},
            {"kind":"url", "url":OUTSIDE, "scope_excluded":True},
            {"kind":"file", "url":OUTSIDE}, {"kind":"url", "url":"file:///tmp/read"}]}
        self.assertEqual(tools.runtime_source_urls(demo), [OWNER])

    async def test_failed_bmw_build_crawl_keeps_enabled_owner_permission(self):
        # Reproduce the published BMW source shape; fetched pages remain fixtures.
        owner = "https://www.bmw.in/en/all-models/x-series/x7/bmw-x7-overview.html"
        self.demo["sources"] = [{"id":"bmw-owner", "kind":"url", "url":owner,
                                 "use_in_demo":True, "crawl_active":False, "crawl_cached":False}]
        store.save(self.did, self.demo)
        before = copy.deepcopy(store.read_json(self.did, "understanding.json"))
        final = await self.turn()
        self.assertEqual([url for url,_ in self.reads], [owner])
        self.assertEqual(self.reads[0][1]["allowed_hosts"], {"bmw.in", "www.bmw.in"})
        self.assertTrue(final["result"]["answered"])
        self.assertEqual(final["tool_results"][0]["tool"], "source_lookup")
        self.assertEqual(store.read_json(self.did, "understanding.json"), before)
        self.assertFalse(store.load(self.did)["sources"][0]["crawl_active"])
        self.assertFalse((store.read_json(self.did, "faq.json") or {}).get("entries"))

    async def test_failed_build_crawl_still_allows_domain_restricted_search(self):
        self.demo["sources"][0].update(crawl_active=False, crawl_cached=False)
        store.save(self.did, self.demo)
        with patch.object(tools, "_search_sources", return_value={"urls":[OUTSIDE, PAGE]}) as search:
            final = await self.turn("Search the web for airbags")
        self.assertTrue(final["result"]["answered"])
        self.assertEqual([url for url,_ in self.reads], [PAGE])
        self.assertIn("site:maker.example", search.call_args.args[0])

    async def test_failed_crawl_never_overrides_owner_disable_or_scope_exclusion(self):
        for index, exclusion in enumerate(({"use_in_demo":False}, {"scope_excluded":True}, {"crawl_parent":"seed"})):
            with self.subTest(exclusion=exclusion):
                self.demo["sources"] = [{"id":"owner", "kind":"url", "url":OWNER,
                                         "crawl_active":False, "use_in_demo":True, **exclusion}]
                store.save(self.did, self.demo)
                with patch.object(tools, "_search_sources") as search:
                    await self.turn("Search the web for airbags", profile={"customer_urls":[PAGE]}, session=f"excluded{index}")
                search.assert_not_called()
                self.assertEqual(self.reads, [])
                self.assertEqual(tools.runtime_source_urls(store.load(self.did)), [])

    async def test_failed_crawl_permission_never_makes_failed_live_read_evidence(self):
        self.demo["sources"][0].update(crawl_active=False, crawl_cached=False)
        store.save(self.did, self.demo)
        before = copy.deepcopy(store.read_json(self.did, "understanding.json"))
        with patch.object(tools, "_search_sources", return_value={"urls":[PAGE]}), \
             patch.object(crawl, "fetch_public", side_effect=TimeoutError("Read timed out")), \
             patch("server.knowledge.retrieve", return_value={"evidence":[]}):
            final = await graph.run_turn(self.did, {"question":"How many airbags?", "session_id":"failed-live", "skip_bank":True})
        self.assertFalse(final["result"]["answered"])
        self.assertFalse(final["result"]["fact_ids"])
        self.assertEqual(final["evidence"], [])
        self.assertEqual(store.read_json(self.did, "understanding.json"), before)
        self.assertFalse((store.read_json(self.did, "faq.json") or {}).get("entries"))

    def test_exact_domain_www_alias_and_explicit_subdomains(self):
        for url in (PAGE, "https://www.maker.example/faq", "HTTP://MAKER.EXAMPLE/faq"):
            self.assertTrue(tools.allowed_source_url(url, [OWNER]), url)
        for url in (OUTSIDE, "https://dealer.maker.example/faq", "https://maker.example.evil.com/", "https://evil-maker.example/"):
            self.assertFalse(tools.allowed_source_url(url, [OWNER]), url)
        self.assertTrue(tools.allowed_source_url("https://dealer.maker.example/faq", ["https://dealer.maker.example/"]))
        self.assertFalse(tools.allowed_source_url(OWNER, ["https://dealer.maker.example/"]))

    def test_invalid_credentials_and_non_http_never_authorized(self):
        for url in ("https://user@maker.example/", "https://maker.example./", "file://maker.example/a", "https://maker.example:bad/a", "https://maker.example/\nfoo"):
            self.assertFalse(tools.allowed_source_url(url, [OWNER]), url)

    def test_direct_lookup_cannot_gain_permission_from_customer_context(self):
        with patch.object(crawl, "fetch_public") as fetch:
            with self.assertRaisesRegex(ValueError, "demo owner"):
                tools.source_lookup({"tool":"source_lookup", "url":OUTSIDE, "query":"airbags"}, "Check "+OUTSIDE,
                                    [{"role":"user", "text":OUTSIDE}], extra=[OUTSIDE], allowed_urls=[OWNER])
        fetch.assert_not_called()

    def test_allowed_domain_can_check_relevant_page_outside_seed_subtree(self):
        with patch.object(crawl, "fetch_public", side_effect=self.fetch):
            result = tools.source_lookup({"tool":"source_lookup", "url":PAGE, "query":"airbags"}, "airbags", [], allowed_urls=[OWNER])
        self.assertEqual(result["evidence"][0]["source"]["ref"], PAGE)
        self.assertEqual(self.reads[0][1]["allowed_hosts"], {"maker.example", "www.maker.example"})

    def test_generic_owner_homepage_follows_relevant_links_only_on_its_domain(self):
        homepage = "https://maker.example/"
        def pages(url, **kwargs):
            result = self.fetch(url, **kwargs)
            result["links"] = [{"url":PAGE,"label":"Airbags"}, {"url":OUTSIDE,"label":"Airbags"}]
            return result
        with patch.object(crawl, "fetch_public", side_effect=pages):
            tools.source_lookup({"tool":"source_lookup", "url":homepage, "query":"airbags"}, "airbags", [], allowed_urls=[OWNER])
        self.assertEqual([url for url,_ in self.reads], [homepage, PAGE])

    def test_search_filters_discovery_before_fetch_and_cites_fetched_page(self):
        result, discover = self.search([OUTSIDE, "https://sub.maker.example/safety", PAGE])
        self.assertEqual([url for url,_ in self.reads], [PAGE])
        self.assertIn("site:maker.example", discover.call_args.args[0])
        self.assertEqual(result["evidence"][0]["source"]["quote"], QUOTE)
        self.assertNotIn("search_entry_point", result)
        self.assertEqual(result["allowed_domains"], ["maker.example"])

    def test_no_accepted_discovery_never_fetches(self):
        with patch.object(tools, "_search_sources", return_value={"urls":[OUTSIDE]}), patch.object(crawl, "fetch_public") as fetch:
            with self.assertRaisesRegex(ValueError, "allowed websites"):
                tools.web_search({"tool":"web_search", "query":"airbags"}, "airbags", allowed_urls=[OWNER])
        fetch.assert_not_called()

    def test_no_owner_url_blocks_discovery_and_direct_fetch(self):
        with patch.object(tools, "_search_sources") as discover, patch.object(crawl, "fetch_public") as fetch:
            with self.assertRaisesRegex(ValueError, "No owner-supplied"):
                tools.web_search({"tool":"web_search", "query":"airbags"}, "airbags")
            with self.assertRaisesRegex(ValueError, "demo owner"):
                tools.source_lookup({"tool":"source_lookup", "url":OWNER, "query":"airbags"}, OWNER, [])
        discover.assert_not_called(); fetch.assert_not_called()

    def test_returned_redirect_outside_owner_domains_is_never_evidence(self):
        with patch.object(tools, "_search_sources", return_value={"urls":[PAGE]}), \
             patch.object(crawl, "fetch_public", return_value={"final_url":OUTSIDE,"text":QUOTE}):
            with self.assertRaisesRegex(ValueError, "No fetched"):
                tools.web_search({"tool":"web_search", "query":"airbags"}, "airbags", allowed_urls=[OWNER])
            with self.assertRaisesRegex(ValueError, "No readable"):
                tools.source_lookup({"tool":"source_lookup", "url":PAGE, "query":"airbags"}, "airbags", [], allowed_urls=[OWNER])

    def test_real_redirect_hop_rejects_unallowed_host_before_dns_or_connection(self):
        response = MagicMock(status_code=302, headers={"location":OUTSIDE})
        client = MagicMock()
        client.__enter__.return_value = client
        client.stream.return_value.__enter__.return_value = response
        dns = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34",443))]
        with patch.object(crawl.httpx, "Client", return_value=client), patch.object(socket, "getaddrinfo", return_value=dns) as resolve:
            with self.assertRaisesRegex(ValueError, "outside the allowed"):
                crawl.fetch_public(PAGE, allowed_hosts=tools.source_hosts([OWNER]))
        self.assertEqual(client.stream.call_count, 1)
        self.assertEqual(resolve.call_count, 1)
        self.assertEqual(resolve.call_args.args[0], "maker.example")

    def test_private_dns_remains_blocked_even_for_owner_domain(self):
        dns = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1",443))]
        with patch.object(socket, "getaddrinfo", return_value=dns):
            with self.assertRaisesRegex(ValueError, "Private"):
                crawl._public_address(PAGE, tools.source_hosts([OWNER]))

    async def test_explicit_domain_search_actual_graph(self):
        with patch.object(tools, "_search_sources", return_value={"urls":[OUTSIDE, PAGE]}) as search:
            final = await self.turn("Search the web for airbags")
        self.assertTrue(final["result"]["answered"], final["result"])
        self.assertEqual([url for url,_ in self.reads], [PAGE])
        self.assertIn("site:maker.example", search.call_args.args[0])

    async def test_automatic_lookup_uses_owner_site_without_customer_url(self):
        final = await self.turn()
        self.assertEqual([url for url,_ in self.reads], [OWNER])
        self.assertTrue(final["result"]["answered"])
        self.assertEqual(final["tool_count"], 1)

    async def test_failed_owner_lookup_falls_back_only_to_owner_domain_search(self):
        def fetch(url, **kwargs):
            if url == OWNER:
                raise ValueError("Page unavailable")
            return self.fetch(url, **kwargs)
        with patch.object(tools, "_search_sources", return_value={"urls":[OUTSIDE,PAGE]}), \
             patch.object(crawl, "fetch_public", side_effect=fetch), \
             patch("server.knowledge.retrieve", return_value={"evidence":[]}):
            final = await graph.run_turn(self.did, {"question":"How many airbags?", "session_id":"fallback", "skip_bank":True})
        self.assertEqual([url for url,_ in self.reads], [PAGE])
        self.assertEqual([tool["tool"] for tool in final["tool_results"]], ["source_lookup", "web_search"])
        self.assertTrue(final["result"]["answered"])

    async def test_legacy_no_url_never_searches_even_with_customer_profile_url(self):
        self.set_sources([])
        with patch.object(tools, "_search_sources") as search:
            for index, question in enumerate(("How many airbags?", "Search the web for airbags", "Check "+OUTSIDE+" for airbags")):
                await self.turn(question, profile={"customer_urls":[OUTSIDE]}, session=f"legacy{index}")
        search.assert_not_called()
        self.assertEqual(self.reads, [])
        self.assertEqual(runtime_state.previous_state(self.did,"legacy0")["customer_urls"], [])

    async def test_approved_upload_facts_still_answer_without_any_website(self):
        self.set_sources([])
        with patch.object(tools, "_search_sources") as search:
            final = await self.turn(evidence=[FACT])
        self.assertTrue(final["result"]["answered"])
        self.assertEqual(final["result"]["fact_ids"], ["F1"])
        self.assertEqual(self.reads, [])
        search.assert_not_called()

    async def test_revoked_source_cannot_survive_session_history(self):
        await self.turn(evidence=[FACT], profile={"customer_urls":[PAGE,OUTSIDE]})
        self.demo["sources"][0]["use_in_demo"] = False
        store.save(self.did, self.demo)
        with patch.object(tools, "_search_sources") as search:
            await self.turn(profile={"customer_urls":[PAGE,OUTSIDE]})
        self.assertEqual(self.reads, [])
        self.assertEqual(runtime_state.previous_state(self.did,"test")["customer_urls"], [])
        search.assert_not_called()

    async def test_model_tool_call_cannot_bypass_owner_domain(self):
        state = {"demo_id":self.did,"question":"Airbags?","history":[],"customer_urls":[OUTSIDE],"evidence":[],
                 "decision":{"action":"tools","tool_calls":[{"tool":"source_lookup","url":OUTSIDE,"query":"airbags"}]},
                 "control":runtime_state.claim_turn(self.did,"model","call")}
        with patch.object(crawl,"fetch_public") as fetch:
            result = await graph.tools_node(state)
        self.assertIn("demo owner",result["errors"][0])
        self.assertEqual(result["evidence"],[])
        fetch.assert_not_called()

    async def test_explicit_allowed_path_and_unallowed_customer_context(self):
        final = await self.turn("Check "+PAGE+" for airbags", profile={"customer_urls":[OUTSIDE]}, evidence=[FACT])
        self.assertEqual([url for url,_ in self.reads],[PAGE])
        self.assertTrue(final["tool_results"][0]["evidence"])
        self.assertNotIn(OUTSIDE,runtime_state.previous_state(self.did,"test")["customer_urls"])

    async def test_live_evidence_never_written_to_registry_or_faq(self):
        before = copy.deepcopy(store.read_json(self.did,"understanding.json"))
        await self.turn()
        self.assertEqual(store.read_json(self.did,"understanding.json"),before)
        self.assertFalse((store.read_json(self.did,"faq.json") or {}).get("entries"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

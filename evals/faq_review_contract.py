"""Free API contracts for durable, human-reviewed FAQ answers."""
from __future__ import annotations

import copy
import sys
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch


def run(check, _demo_id=None):
    from fastapi.testclient import TestClient
    from server import cloud, config, graph, orchestrator, schemas, store
    from server.agents import faq, qa, rehearsal
    from server.app import app

    with tempfile.TemporaryDirectory(prefix="faq-review-") as tmp, ExitStack() as stack:
        stack.enter_context(patch.multiple(config, MOCK_LLM=True, DATA_DIR=Path(tmp)))
        stack.enter_context(patch.object(cloud, "enabled", return_value=False))
        outbound = [stack.enter_context(patch(name, side_effect=AssertionError("Unexpected provider/network call")))
                    for name in ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex",
                                 "server.llm.gemini.client", "server.llm.runware._post", "server.llm.claude._client_opts")]
        generated = stack.enter_context(patch.object(rehearsal, "generate_questions", side_effect=AssertionError("FAQ correction must not generate questions")))
        answered = stack.enter_context(patch.object(qa, "answer", side_effect=AssertionError("FAQ correction must not regenerate answers")))
        demo = store.new_demo("FAQ review fixture"); did = demo["id"]
        source = store.add_text_source(did, "Product", "Length 3995 mm. Six airbags standard.", "product")
        rival = store.add_text_source(did, "Rival", "Rival length 4000 mm.", "competitor")
        def fact(fid, value, approved=True, ref=None):
            return schemas.Fact(id=fid, kind="spec", claim=value, value=value, approved=approved,
                                confidence=1, source=schemas.FactSource(ref=ref or source["id"], quote=value)).model_dump()
        und = {"product":{"name":"Product", "category":"Car"}, "facts":[fact("F001", "3995 mm"), fact("F002", "Six airbags"), fact("F003", "Ten airbags", False)],
               "competitors":[{"name":"Rival", "source_id":rival["id"], "facts":[fact("C001", "4000 mm", ref=rival["id"]), fact("C002", "4100 mm", False, rival["id"])]}],
               "images":[{"id":"im02", "source_id":source["id"], "angle":"safety", "description":"Cabin"}],
               "shots":[], "unknowns":[], "brand":{}, "image_map":{"F002":["im02"]}}
        store.write_json(did, "understanding.json", und)
        store.write_json(did, "plan.json", {"voice":{}, "segments":[], "ctas":[]})
        store.write_json(did, "script.json", {"segments":[], "closing":[]})
        slides = [{"id":"dimensions", "kind":"feature", "title":"Dimensions", "topics":[], "lines":[{"text":"Length is 3995 mm.", "fact_ids":["F001"]}], "fact_ids":["F001"], "callouts":[{"id":"length", "text":"3995 mm", "fact_ids":["F001"]}]},
                  {"id":"safety", "kind":"feature", "title":"Safety", "topics":[], "lines":[{"text":"Six airbags.", "fact_ids":["F002"]}], "fact_ids":["F002"], "callouts":[{"id":"airbags", "text":"Six airbags", "fact_ids":["F002"]}]}]
        store.write_json(did, "deck.json", {"slides":slides})
        def configure(d):
            d["settings"].update({"faq_questions":2, "competition":"off"})
            d["approvals"].update({key:True for key in store.CARDS})
            d["running"] = None
            for stage in d["stages"].values():stage["status"] = "done"
        store.update(did, configure)
        bank = {"entries":[{"id":"Q01", "question":"How many airbags are fitted?", "origin":"generated", "answer":"Old unsupported answer", "fact_ids":["F001"], "answered":False, "audio":"audio/old.wav", "visual":{"kind":"image", "ref":"old"}, "slide_id":"dimensions", "offer_callback":True, "clarifying_question":"Which version?", "error":"old generation error"},
                           {"id":"Q02", "question":"What is the vehicle length?", "origin":"generated", "answer":"Length is 3995 mm.", "fact_ids":["F001"], "answered":True, "audio":"audio/keep.wav", "offer_callback":False, "clarifying_question":"", "slide_id":"dimensions"}],
                "answered":1, "total":2, "registry_hash":faq._registry_hash(did), "partial":False}
        store.write_json(did, "faq.json", bank)
        api = TestClient(app)
        url = f"/api/demos/{did}/align/faq/Q01"
        def snapshot():return {name:store.path(did, name).read_bytes() for name in ("faq.json", "demo.json", "understanding.json", "plan.json", "script.json", "deck.json")}
        for label, payload in (
            ("uncited numeric answer", {"answer":"Six airbags are standard.", "fact_ids":[]}),
            ("uncited claim", {"answer":"Free maintenance is included.", "fact_ids":[]}),
            ("unsupported nonnumeric answer", {"answer":"It keeps everyone comfortable.", "fact_ids":[]}),
            ("missing citation", {"answer":"Six airbags are standard.", "fact_ids":["F999"]}),
            ("mixed valid and missing citation", {"answer":"Six airbags are standard.", "fact_ids":["F002", "F999"]}),
            ("human-held product citation", {"answer":"Ten airbags are standard.", "fact_ids":["F003"]}),
            ("mixed valid and held citation", {"answer":"Ten airbags are standard.", "fact_ids":["F002", "F003"]}),
            ("comparison disabled", {"answer":"The rival is 4000 mm long.", "fact_ids":["C001"]}),
            ("mixed product and disabled rival", {"answer":"The rival is 4000 mm long.", "fact_ids":["F001", "C001"]}),
            ("missing required field", {"answer":"Six airbags."}),
            ("non-array citations", {"answer":"Six airbags.", "fact_ids":"F002"}),
            ("non-text citation", {"answer":"Six airbags.", "fact_ids":[2]}),
            ("duplicate citation", {"answer":"Six airbags.", "fact_ids":["F002", "F002"]}),
            ("empty answer", {"answer":" ", "fact_ids":["F002"]}),
            ("non-text answer", {"answer":6, "fact_ids":["F002"]}),
            ("oversize answer", {"answer":"a"*2001, "fact_ids":["F002"]}),
            ("structural question mutation", {"answer":"Six airbags.", "fact_ids":["F002"], "question":"Changed?"}),
            ("CTA escape", {"answer":"₹999.", "fact_ids":[], "cta":"book"}),
            ("clarification not in this supported-answer route", {"answer":"Which one?", "fact_ids":[], "clarifying_question":"Which one?"}),
        ):
            before = snapshot();response = api.patch(url,json=payload)
            check(f"FAQ review: {label} rejected atomically", response.status_code==400 and snapshot()==before)
        before=snapshot();response=api.patch(url.replace('Q01','Q99'),json={"answer":"Six airbags.","fact_ids":["F002"]})
        check("FAQ review: unknown question rejected atomically",response.status_code==404 and snapshot()==before)
        for label, edit_bank, edit_demo in (
            ("stale registry",lambda b:b.update(registry_hash="old"),None),
            ("partial bank",lambda b:b.update(partial=True),None),
            ("active worker",None,lambda d:d.update(running="faq")),
            ("running stage",None,lambda d:d["stages"]["voice"].update(status="running")),
            ("stale FAQ stage",None,lambda d:d["stages"]["faq"].update(status="stale")),
        ):
            modified=copy.deepcopy(bank)
            if edit_bank:edit_bank(modified)
            store.write_json(did,"faq.json",modified)
            if edit_demo:store.update(did,edit_demo)
            before=snapshot();response=api.patch(url,json={"answer":"Six airbags.","fact_ids":["F002"]})
            check(f"FAQ review: {label} requires a finished current bank",response.status_code==409 and snapshot()==before)
            store.update(did,configure)
        store.write_json(did,"faq.json",bank)
        with patch.object(graph,"is_running",return_value=True):
            before=snapshot();response=api.patch(url,json={"answer":"Six airbags.","fact_ids":["F002"]})
            check("FAQ review: graph between stages rejects edits atomically",response.status_code==409 and snapshot()==before)
        old_hash=bank["registry_hash"];old_other=copy.deepcopy(bank["entries"][1]);words="Six airbags are listed as standard equipment."
        before=snapshot();response=api.patch(url,json={"answer":words,"fact_ids":["F002"]});saved=store.read_json(did,"faq.json");entry=saved["entries"][0];demo=store.load(did)
        check("FAQ review: supported edit succeeds and exact reviewed wording is saved",response.status_code==200 and entry["answer"]==words and entry["fact_ids"]==["F002"] and entry["answered"])
        check("FAQ review: id/question/origin/hash and unrelated answer remain intact", all(entry[k]==bank["entries"][0][k] for k in ("id","question","origin")) and saved["registry_hash"]==old_hash and saved["entries"][1]==old_other and saved["total"]==2 and saved["answered"]==2)
        check("FAQ review: old audio/error/clarification/callback removed", entry["audio"] is None and "error" not in entry and entry["clarifying_question"]=="" and not entry["offer_callback"])
        check("FAQ review: visual and slide derive from corrected facts",entry["slide_id"]=="safety" and entry["visual"]=={"kind":"image","ref":"im02","source_id":source["id"]})
        check("FAQ review: only FAQ approval clears and only its build dependants become stale",demo["stages"]["faq"]["status"]=="done" and not demo["approvals"]["faq"] and all(v for k,v in demo["approvals"].items() if k!="faq") and all(demo["stages"][k]["status"]=="stale" for k in ("voice","rehearsal","bundle")) and all(demo["stages"][k]["status"]=="done" for k in ("understand","plan","author","deck")))
        check("FAQ review: source/plan/script/deck artifacts are unchanged",all(store.path(did,k).read_bytes()==before[k] for k in ("understanding.json","plan.json","script.json","deck.json")))
        with patch.object(orchestrator,"_run_stage",side_effect=AssertionError("normal Build must not regenerate FAQ")) as stage:
            check("FAQ review: normal Build proceeds to voice and skips FAQ generation",graph.after_author({"demo_id":did,"entry":"build"})=="voice" and graph.faq({"demo_id":did,"entry":"build"})=={} and not stage.called)
        reused=faq.run(did,lambda _:None)
        check("FAQ review: explicit unchanged-registry reuse preserves reviewed answer without a model call",reused["entries"][0]["answer"]==words and reused["entries"][0]["audio"] is None and not generated.called and not answered.called)
        response=api.post(f"/api/demos/{did}/run/qa",json={"question":entry["question"],"slide_id":"dimensions"});result=response.json()
        check("FAQ review: bank serves exact correction and routes from current slide",response.status_code==200 and result.get("from_bank") and result["answer"]==words and result["audio"] is None and result["route"]=="jump" and result["slide_id"]=="safety")
        response=api.post(f"/api/demos/{did}/run/qa",json={"question":entry["question"],"slide_id":"safety"})
        check("FAQ review: runtime derives stay instead of retaining the old route",response.status_code==200 and response.json()["route"]=="stay")
        stale_slides=copy.deepcopy(slides)
        for slide, old_fact in zip(stale_slides, ("F002", "F001")):
            slide.update(segment_id=slide["id"], fact_ids=[old_fact], lines=[{"text":"Old copied narration", "fact_ids":[old_fact]}], callouts=[])
        store.write_json(did,"deck.json",{"slides":stale_slides})
        store.write_json(did,"script.json",{"segments":[{"id":"dimensions", "title":"Dimensions", "lines":[{"id":"dimensions-L1","text":"Length is 3995 mm.","fact_ids":["F001"]}]},
                                                                        {"id":"safety", "title":"Safety", "lines":[{"id":"safety-L1","text":"Six airbags.","fact_ids":["F002"]}]}],"closing":[]})
        response=api.patch(url,json={"answer":words,"fact_ids":["F002"]})
        check("FAQ review: slide target uses corrected script citations over stale deck copies",response.status_code==200 and store.read_json(did,"faq.json")["entries"][0]["slide_id"]=="safety" and store.read_json(did,"deck.json")["slides"][0]["fact_ids"]==["F002"])
        def exclude_visual(d):
            next(s for s in d["sources"] if s["id"]==source["id"])["use_in_demo"]=False
        store.update(did,exclude_visual)
        response=api.patch(url,json={"answer":words,"fact_ids":["F002"]})
        check("FAQ review: a stale image map cannot restore an excluded visual",response.status_code==200 and store.read_json(did,"faq.json")["entries"][0]["visual"] is None)
        store.update(did,lambda d:d["settings"].update(competition="on"));saved=store.read_json(did,"faq.json");saved["registry_hash"]=faq._registry_hash(did);store.write_json(did,"faq.json",saved)
        before=snapshot();response=api.patch(url,json={"answer":"The rival is 4100 mm long.","fact_ids":["F001","C002"]})
        check("FAQ review: held competitor still rejected with comparisons enabled",response.status_code==400 and snapshot()==before)
        response=api.patch(url,json={"answer":"The rival is listed at 4000 mm; that is as per their website when we checked — please verify on their site.","fact_ids":["C001"]})
        entry=store.read_json(did,"faq.json")["entries"][0]
        check("FAQ review: approved competitor accepted only when comparisons enabled",response.status_code==200 and entry["fact_ids"]==["C001"] and entry["visual"] is None and entry["audio"] is None)
        check("FAQ review: no model or outbound calls in any case",not generated.called and not answered.called and all(not mock.called for mock in outbound))


if __name__ == "__main__":
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    results=[]
    def check(label,ok):
        results.append(bool(ok));print(("PASS " if ok else "FAIL ")+label)
    run(check)
    print(f"FAQ review: {sum(results)}/{len(results)} passed")
    raise SystemExit(0 if all(results) else 1)

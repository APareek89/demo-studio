"""Free behavioral regressions: actual graph, scoped tools, evidence and ownership.

Runs in isolated storage. Providers and source network are replaced at their
boundaries, not at graph nodes. This is not a live semantic-quality benchmark.
"""
import asyncio
import copy
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

tmp = tempfile.TemporaryDirectory(prefix="runtime-graph-contract-")
os.environ.update(MOCK_LLM="1",CLOUD_SYNC="0",STORAGE_BACKEND="local",DEMO_STUDIO_DATA=tmp.name+"/demos",DEMO_STUDIO_GRAPH_DB=tmp.name+"/graph.sqlite")

from server import config, knowledge, store, runtime_graph as rg
from server.runtime_state import TurnDecision, cancel_turn, claim_turn, checkpoint, previous_state
from server.runtime_tools import calculate, source_lookup, supplied_urls

passed = []
def check(name, value):
    assert value, name
    passed.append(name)

demo = store.new_demo("Contract car")
d = demo["id"]
fact = {"id":"F001","kind":"feature","claim":"Airbags","value":"Six airbags are standard.","source":{"ref":"src_doc","quote":"Six airbags are standard.","locator":"p2"},"confidence":1,"conditions":"India, model year2026, all variants","truth":"stated","approved":True}
store.write_json(d,"understanding.json",{"product":{"name":"Contract car"},"facts":[fact],"competitors":[],"images":[],"shots":[],"brand":{}})
store.write_json(d,"plan.json",{"voice":{"persona_name":"Guide","tone":"warm"},"segments":[],"ctas":[]})
store.update(d,lambda x:x["approvals"].update({c:True for c in store.CARDS}))
snap=knowledge.snapshot(d,publish=True)
store.write_json(d,"bundle.json",{"runtime":{"version":1},"knowledge_snapshot_id":snap["id"],"slides":[]})

q="Estimate EMI for a loan of 10 lakh at 9% per year over 5 years."
emi={"tool":"calculator","operation":"emi","inputs":[{"name":"principal","value":1000000,"unit":"INR","source_id":"customer","quote":"10 lakh"},{"name":"annual_rate","value":9,"unit":"percent","source_id":"customer","quote":"9% per year"},{"name":"tenure","value":5,"unit":"years","source_id":"customer","quote":"5 years"}]}
computed=calculate(emi,[],q)
check("EMI uses deterministic formula and rounded result",computed["value"]=="20758.36 INR/month")
check("Calculation retains input provenance and formula",len(computed["derivation"]["inputs"])==3 and "P*r" in computed["derivation"]["formula"])
zero=copy.deepcopy(emi);zero["inputs"][1].update(value=0,quote="0% per year")
check("Zero-interest EMI avoids division by zero",calculate(zero,[],q.replace("9%","0%"))["value"]=="16666.67 INR/month")
for label, mutate in [
    ("invented interest",lambda r:r["inputs"][1].update(value=7)),
    ("invented quote",lambda r:r["inputs"][0].update(quote="loan of12 lakh")),
    ("unknown source",lambda r:r["inputs"][0].update(source_id="F999")),
    ("wrong tenure unit",lambda r:r["inputs"][2].update(unit="months")),
    ("infinite amount",lambda r:r["inputs"][0].update(value=float("inf"))),
    ("duplicate input",lambda r:r["inputs"].append(r["inputs"][0].copy())),
]:
    bad=copy.deepcopy(emi);mutate(bad)
    try:calculate(bad,[],q)
    except ValueError:check("Reject "+label,True)
    else:check("Reject "+label,False)

for label, field, replacement, source in [
    ("unit borrowed from another quantity",2,{"value":5,"unit":"months","quote":"5-year warranty; loan tenure120 months"},q+" 5-year warranty; loan tenure120 months"),
    ("monthly interest mislabeled annual",1,{"quote":"9% per month"},q.replace("per year","per month")),
    ("annual basis missing",1,{"quote":"9%"},q),
    ("scale silently discarded",0,{"value":10},q),
]:
    bad=copy.deepcopy(emi);bad["inputs"][field].update(replacement)
    try:calculate(bad,[],source)
    except ValueError:check("Reject "+label,True)
    else:check("Reject "+label,False)

fuel={"tool":"calculator","operation":"fuel_cost","inputs":[{"name":"distance","value":1000,"unit":"km/month","source_id":"customer","quote":"1000 km per month"},{"name":"efficiency","value":15,"unit":"km/litre","source_id":"customer","quote":"15 km/litre"},{"name":"fuel_price","value":100,"unit":"INR/litre","source_id":"customer","quote":"₹100 per litre"}]}
fq="I drive1000 km per month, assume15 km/litre and ₹100 per litre."
check("Fuel calculation preserves monthly basis",calculate(fuel,[],fq)["value"]=="6666.67 INR/month")
bad=copy.deepcopy(fuel);bad["inputs"][0]["quote"]="1000 km"
try:calculate(bad,[],fq)
except ValueError:check("Distance cannot silently become monthly",True)
else:check("Distance cannot silently become monthly",False)

def answer(text,ids=None,kind="fact"):
    return {"action":"answer","answered":True,"sentences":[{"text":text,"fact_ids":ids or [],"kind":kind}]}

result,errors=rg.validate_decision(answer("It has six airbags.",["F001"]),[fact],"airbags")
check("Approved factual answer survives",result["answered"] and result["fact_ids"]==["F001"])
for label,text,ids in [("new quantity","It has eight airbags.",["F001"]),("fake id","It has six airbags.",["F999"]),("no citation","It has six airbags.",[])]:
    r,e=rg.validate_decision(answer(text,ids),[fact],"airbags")
    check("Reject "+label,not r["fact_ids"] and bool(e))
r,e=rg.validate_decision({"action":"answer","answered":True,"sentences":[{"text":"It has six airbags.","fact_ids":["F001"],"kind":"fact"},{"text":"It costs ₹1000000.","fact_ids":[],"kind":"fact"}]},[fact],"safety and price")
check("Useful supported portion survives unknown price",r["fact_ids"]==["F001"] and "six airbags" in r["answer"] and "1000000" not in r["answer"])
r,e=rg.validate_decision(answer("The EMI is 20758.36 INR/month.",[computed["id"]]),[computed],q)
check("Unqualified modeled EMI is rejected","unqualified_calculation" in e)
r,e=rg.validate_decision(answer("The illustrative EMI is 20758.36 INR/month.",[computed["id"]]),[computed],q)
check("Auditable estimate is allowed",r["answered"] and not e)
r,e=rg.validate_decision({"action":"clarify","clarification":"What annual interest rate should I use?","sentences":[]},[],q)
check("Clarification is a wait with no fact claim",r["clarifying_question"].endswith("?") and not r["fact_ids"])
r,e=rg.validate_decision({"action":"clarify","clarification":"It has six airbags, right?","sentences":[]},[],q)
check("Question cannot smuggle a product claim",not r["clarifying_question"])
trim=copy.deepcopy(fact);trim["scope"]={"variant":"SX(O)"}
r,e=rg.validate_decision(answer("It has six airbags.",["F001"]),[trim],"Tell me about safety")
check("Variant-specific feature cannot become universal","missing_variant_qualification" in e)
r,e=rg.validate_decision(answer("It has six airbags.",["F001"]),[trim],"Does SX(O) have airbags?")
check("Explicit variant question supplies applicability",r["answered"] and not e)
scope=rg.explicit_scope("Tell me about SX(O)",[trim,{"scope":{"variant":"SX"}}])
check("Longer canonical trim wins substring",scope=={"variant":"SX(O)"})
check("Two named variants retain comparison",set(rg.explicit_scope("SX(O) versus SX",[trim,{"scope":{"variant":"SX"}}])["variant"])=={"SX(O)","SX"})
check("Single letter trim never matches a letter inside prose",not rg.explicit_scope("Does it have airbags?",[{"scope":{"variant":"E"}}]))
check("Unknown parenthesized trim never aliases base trim",not rg.explicit_scope("Does SX(O) have airbags?",[{"scope":{"variant":"SX"}}]))
check("Model brand prefix has the same explicit identity",rg.explicit_scope("Tell me about Creta",[{"scope":{"model":"Hyundai CRETA"}}])=={"model":"Hyundai CRETA"})
scope=rg.explicit_scope("Actually I meant E, not SX",[{"scope":{"variant":"SX"}},{"scope":{"variant":"E"}}],{"scope":{"variant":"SX"}})
check("Latest explicit correction replaces previous scope",scope=={"variant":"E"})
check("Terse follow-up retains corrected scope",rg.explicit_scope("And the airbags?",[trim],{"scope":scope})=={"variant":"E"})
base_trim=copy.deepcopy(fact);base_trim["scope"]={"variant":"SX"}
r,e=rg.validate_decision(answer("It has six airbags.",["F001"]),[base_trim],"Does SX(O) have airbags?")
check("Unknown longer variant cannot qualify base fact","missing_variant_qualification" in e)
listed=copy.deepcopy(fact);listed["scope"]={"variant":"King, King Knight"}
check("Explicit list provides two atomic canonical trims",rg.explicit_scope("Tell me about King Knight",[listed])=={"variant":"King Knight"})
r,e=rg.validate_decision(answer("It has six airbags.",["F001"]),[listed],"Does King Knight have airbags?",requested_scope={"variant":"King Knight"})
check("Listed trim applicability qualifies a cited assertion",r["answered"] and not e)
r,e=rg.validate_decision(answer("It has six airbags.",["F001"]),[listed],"Does E have airbags?",requested_scope={"variant":"E"})
check("Listed trims cannot leak to an unlisted trim","inapplicable_scope" in e)
r,e=rg.validate_decision(answer("The car offers a panoramic sunroof.",kind="context"),[],"Tell me more")
check("Context label cannot bypass citations","uncited_product_assertion" in e)
webfact=copy.deepcopy(fact);webfact["provenance"]="live_web"
r,e=rg.validate_decision(answer("It has six airbags.",["F001"]),[webfact],"airbags")
check("Live website claims require attribution","unattributed_web_claim" in e)

check("Only user messages authorize lookup URLs",supplied_urls("Check www.example.com/car",[{"role":"assistant","text":"https://evil.example"}])==["https://www.example.com/car"])
with patch("server.crawl.fetch_public",return_value={"text":"A model-specific official passage describes six airbags for this vehicle.","final_url":"https://example.com/car","fetched_at":123}):
    result=source_lookup({"tool":"source_lookup","url":"https://example.com/car","query":"airbags"},"Check https://example.com/car",[])
    check("Web evidence retains exact passage and date",result["evidence"][0]["source"]["quote"].startswith("A model-specific") and result["evidence"][0]["fetched_at"]==123)
    try:source_lookup({"tool":"source_lookup","url":"https://other.example/car"},"Check https://example.com/car",[])
    except ValueError:check("LLM cannot invent a source",True)
    else:check("LLM cannot invent a source",False)

async def main():
    final=await rg.run_turn(d,{"session_id":"s_graph","turn_id":"t_one","question":"How many airbags?"})
    check("Actual LangGraph reaches a versioned DeliveryPlan",final["delivery"]["version"]==1 and final["result"]["answered"])
    check("Graph itself produces no audio",final["result"]["audio"] is None)
    check("Graph pins reviewed evidence snapshot",final["delivery"]["snapshot_id"]==snap["id"])
    check("Meaningful boundary persisted",previous_state(d,"s_graph")["phase"]=="ready_to_deliver")
    await rg.run_turn(d,{"session_id":"s_context","question":"I drive 1000 km per month","profile":{"needs":"family"}})
    await rg.run_turn(d,{"session_id":"s_context","question":"What would fuel cost?"})
    restored=previous_state(d,"s_context")
    check("Explicit context survives following turn without repeated payload",restored["profile"]["needs"]=="family" and any("1000" in m["text"] for m in restored["history"]))
    control=claim_turn(d,"s_race","t_old")
    claim_turn(d,"s_race","t_new")
    checkpoint({"demo_id":d,"session_id":"s_race","turn_id":"t_old","control":control},"old_finished")
    check("Superseded turn cannot checkpoint over new input",control.cancelled.is_set() and not previous_state(d,"s_race"))
    cancel_turn(d,"s_race")
    old=config.MOCK_LLM;config.MOCK_LLM=False
    calls=[]
    def model(system,content,schema,**kwargs):
        import json
        payload=json.loads(content);calls.append(payload)
        if len(calls)==1:return TurnDecision(action="tools",tool_calls=[emi])
        tool_fact=next(f for f in payload["evidence"] if f["id"].startswith("D"))
        return TurnDecision.model_validate(answer("The illustrative EMI is 20758.36 INR/month.",[tool_fact["id"]]))
    try:
        with patch("server.llm.runtime.structured",side_effect=model):
            final=await rg.run_turn(d,{"session_id":"s_calculate","question":q})
        check("Actual graph invokes tool then recomposes",len(calls)==2 and len(final["result"]["tool_results"])==1 and final["result"]["answered"])
        check("Tool result stays session scoped",all(f["id"]=="F001" for f in store.read_json(d,"understanding.json")["facts"]))
        def failing(*a,**k):raise RuntimeError("outage")
        with patch("server.llm.runtime.structured",side_effect=failing):
            final=await rg.run_turn(d,{"session_id":"s_failure","question":"airbags"})
        check("Outage is not cached as a knowledge gap",final["result"]["provider_failed"] and not final["result"]["fact_ids"])
    finally:config.MOCK_LLM=old

asyncio.run(main())
print(f"{len(passed)}/{len(passed)} runtime graph contracts passed")
for name in passed:print("PASS",name)
tmp.cleanup()

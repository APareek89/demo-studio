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
check("General feature discovery retains selected-variant qualification",r["answered"] and r["answer"].startswith("On selected variants,") and not e)
r,e=rg.validate_decision(answer("It has six airbags.",["F001"]),[trim],"Does SX(O) have airbags?")
check("Explicit variant question supplies applicability",r["answered"] and not e)
scope=rg.explicit_scope("Tell me about SX(O)",[trim,{"scope":{"variant":"SX"}}])
check("Longer canonical trim wins substring",scope=={"variant":"SX(O)"})
check("Two named variants retain comparison",set(rg.explicit_scope("SX(O) versus SX",[trim,{"scope":{"variant":"SX"}}])["variant"])=={"SX(O)","SX"})
check("Single letter trim never matches a letter inside prose",not rg.explicit_scope("Does it have airbags?",[{"scope":{"variant":"E"}}]))
check("Unknown parenthesized trim never aliases base trim",rg.explicit_scope("Does SX(O) have airbags?",[{"scope":{"variant":"SX"}}])=={"variant":"SX(O)"})
check("Model brand prefix has the same explicit identity",rg.explicit_scope("Tell me about Creta",[{"scope":{"model":"Hyundai CRETA"}}])=={"model":"Hyundai CRETA"})
scope=rg.explicit_scope("Actually I meant E, not SX",[{"scope":{"variant":"SX"}},{"scope":{"variant":"E"}}],{"scope":{"variant":"SX"}})
check("Latest explicit correction replaces previous scope",scope=={"variant":"E"})
check("Terse follow-up retains corrected scope",rg.explicit_scope("And the airbags?",[trim],{"scope":scope})=={"variant":"E"})
unknown_scope=rg.explicit_scope("Actually I meant E, not SX",[{"scope":{"variant":"SX"}}],{"scope":{"variant":"SX"}})
check("Unlisted explicit correction clears stale trim",unknown_scope=={"variant":"E"})
check("Unlisted correction persists on a terse follow-up",rg.explicit_scope("And the sunroof?",[trim],{"scope":unknown_scope})=={"variant":"E"})
check("Explicit comparison retains an unlisted requested trim",rg.explicit_scope("Compare only E and King",[{"scope":{"variant":"King"}}],{"scope":{"variant":"SX"}})=={"variant":["E","King"]})
check("Explicit comparison accepts lowercase customer identifiers",rg.explicit_scope("compare only e and king",[{"scope":{"variant":"King"}}])["variant"]==["e","King"])
check("Conversational comparison retains both requested trims",rg.explicit_scope("Compare that E with King on comfort",[{"scope":{"variant":"King"}}],{"scope":{"variant":"E"}})["variant"]==["E","King"])
check("Capitalized topic comparison never invents trim names",not rg.explicit_scope("Compare Safety and Comfort",[{"scope":{"variant":"King"}}]))
check("Explicit trim label is customer scope without registry endorsement",rg.explicit_scope("Tell me about variant EX(O)",[{"scope":{"variant":"EX"}}])=={"variant":"EX(O)"})
check("Verb after a named variant never becomes another trim",rg.explicit_scope("Does the E variant have a panoramic sunroof?",[{"scope":{"variant":"King"}}])=={"variant":"E"})
check("Ordinary comparison words do not invent trims",not rg.explicit_scope("Compare safety and comfort",[{"scope":{"variant":"SX"}}]))
check("Ordinary correction does not replace trim scope",rg.explicit_scope("Actually I meant safety",[{"scope":{"variant":"SX"}}],{"scope":{"variant":"SX"}})=={"variant":"SX"})
year_scope=rg.explicit_scope("Did the 2015 Creta have airbags?",[{"scope":{"model":"Hyundai CRETA"}}])
check("Explicit unsupported model year stays in customer scope",year_scope=={"model":"Hyundai CRETA","model_year":"2015"})
check("Explicit year filters undated facts conservatively",not knowledge.scope_matches({"scope":{"model":"Hyundai CRETA"}},year_scope))
check("Customer monetary amount does not become model year",not rg.explicit_scope("My monthly budget is 2026 rupees",[{"scope":{"model":"Hyundai CRETA"}}]))
check("Gearbox choices do not impose a selected transmission filter",not rg.explicit_scope("What automatic gearbox choices are available?",[{"scope":{"transmission":"automatic"}}],{"scope":{"transmission":"manual"}}))
check("Explicit engine capacity is preserved as requested scope",rg.explicit_scope("What about the 2.0-litre turbo petrol?",[{"scope":{"powertrain":"turbo petrol"}}])["powertrain"]=="2.0-litre turbo petrol")
for quantity in ("My budget for CRETA is 2026 rupees", "I drive my CRETA 2026 km per month"):
    check("Model-adjacent quantity never becomes model year: "+quantity,"model_year" not in rg.explicit_scope(quantity,[{"scope":{"model":"Hyundai CRETA"}}]))
base_trim=copy.deepcopy(fact);base_trim["scope"]={"variant":"SX"}
r,e=rg.validate_decision(answer("It has six airbags.",["F001"]),[base_trim],"Does SX(O) have airbags?")
check("Unknown longer variant cannot qualify base fact","inapplicable_scope" in e)
listed=copy.deepcopy(fact);listed["scope"]={"variant":"King, King Knight"}
check("Explicit list provides two atomic canonical trims",rg.explicit_scope("Tell me about King Knight",[listed])=={"variant":"King Knight"})
r,e=rg.validate_decision(answer("It has six airbags.",["F001"]),[listed],"Does King Knight have airbags?",requested_scope={"variant":"King Knight"})
check("Listed trim applicability qualifies a cited assertion",r["answered"] and not e)
r,e=rg.validate_decision(answer("It has six airbags.",["F001"]),[listed],"Does E have airbags?",requested_scope={"variant":"E"})
check("Listed trims cannot leak to an unlisted trim","inapplicable_scope" in e)
king=copy.deepcopy(fact);king["scope"]={"variant":"King"}
for text in ("Both have six airbags.", "E and King have six airbags.", "They each have six airbags."):
    r,e=rg.validate_decision(answer(text,["F001"]),[king],"Compare only E and King",requested_scope={"variant":["E","King"]})
    check("Single-trim evidence cannot universalize comparison: "+text,not r["answered"] and "overgeneralized_variant_comparison" in e)
r,e=rg.validate_decision(answer("It has six airbags.",["F001"]),[king],"Compare only E and King",requested_scope={"variant":["E","King"]})
check("A partial comparison must identify the supported trim","missing_comparison_qualification" in e)
r,e=rg.validate_decision({"action":"answer","answered":True,"sentences":[{"text":"King has six airbags.","fact_ids":["F001"],"kind":"fact"},{"text":"Both have six airbags.","fact_ids":["F001"],"kind":"fact"}]},[king],"Compare only E and King",requested_scope={"variant":["E","King"]})
check("Supported partial comparison survives rejected universal claim",r["answered"] and "King has" in r["answer"] and "Both have" not in r["answer"])
base=copy.deepcopy(king);base.update(id="F002",scope={"variant":"E"})
r,e=rg.validate_decision(answer("Both E and King have six airbags.",["F001","F002"]),[king,base],"Compare E and King",requested_scope={"variant":["E","King"]})
check("Comparison with evidence for both configurations is allowed",r["answered"] and not e)
all_trims=copy.deepcopy(fact);all_trims["scope"]={"variant":"all variants"}
r,e=rg.validate_decision(answer("Both have six airbags.",["F001"]),[all_trims],"Compare E and King",requested_scope={"variant":["E","King"]})
check("Explicit all-variant evidence can support both requested trims",r["answered"] and not e)
for decision in ({"action":"tools","tool_calls":[],"answered":True}, {"action":"answer","sentences":[],"answered":True}, answer("I could not verify that.",kind="limitation")):
    r,e=rg.validate_decision(decision,[],"Does E have it?")
    check("Empty or unsupported answer offers callback: "+decision["action"]+str(bool(decision.get("sentences"))),not r["answered"] and r["offer_callback"])
r,e=rg.validate_decision(answer("The car offers a panoramic sunroof.",kind="context"),[],"Tell me more")
check("Context label cannot bypass citations","uncited_product_assertion" in e)
webfact=copy.deepcopy(fact);webfact["provenance"]="live_web"
r,e=rg.validate_decision(answer("It has six airbags.",["F001"]),[webfact],"airbags")
check("Live website claims require attribution","unattributed_web_claim" in e)
webfact["source"]["ref"]="https://example.com/car"
r,e=rg.validate_decision(answer("It has six airbags.",["F001"]),[webfact],"airbags")
check("Real fetched source restores attribution on every surviving sentence",r["answer"].startswith("According to example.com,") and not e)
conditional=copy.deepcopy(fact);conditional["conditions"]="Available only on higher trims";conditional["scope"]={"model":"CRETA"}
r,e=rg.validate_decision(answer("These include six airbags.",["F001"]),[conditional],"What safety is offered?")
check("Conditions outside structured variant scope remain in delivered sentence",r["answer"].startswith("On selected higher trims,") and "These include" not in r["answer"])
r,e=rg.validate_decision(answer("Every variant has six airbags.",["F001"]),[conditional],"What safety is offered?")
check("Generic condition preservation never permits every-trim overclaim","overgeneralized_variant" in e)
matrix=copy.deepcopy(fact);matrix.update(claim="Phone connectivity",value="Wireless phone mirroring",conditions="Selected trims",scope={})
matrix["source"]["quote"]="Wireless phone mirroring. Rear entertainment: 11.6 inch screen."
matrix["context"]=[{"text":matrix["source"]["quote"]}]
r,e=rg.validate_decision(answer("There is an 11.6 inch rear screen.",["F001"]),[matrix],"Screen options?")
check("Unrelated table quantities cannot borrow a different assertion ID",bool(set(e)&{"unsupported_quantity","unsupported_assertion_feature"}) and not r["answered"])
payload=rg._reason_evidence(matrix)
check("Runtime assertion payload excludes broad source/context while retaining locator","context" not in payload and "quote" not in payload["source"] and payload["source"]["locator"]=="p2" and matrix["context"])
diesel=copy.deepcopy(fact);diesel.update(claim="Diesel maximum power",value="85 kW (116 PS) @ 4 000 r/min",conditions="1.5l diesel engine",scope={})
r,e=rg.validate_decision(answer("The 1.5-litre diesel produces 85 kW or 116 PS at 4,000 r/min.",["F001"]),[diesel],"Diesel power?")
check("Space-grouped PDF thousands equal comma-grouped spoken quantities",r["answered"] and not e)
r,e=rg.validate_decision(answer("I cannot guarantee your EMI will stay under 20000 rupees.",kind="limitation"),[],"Can you guarantee EMI under 20000 rupees?")
check("Safe negative guarantee retains customer quantity",not r["answered"] and not e and "cannot guarantee" in r["answer"])
r,e=rg.validate_decision(answer("I cannot guarantee the quote; the car has 12 airbags.",kind="limitation"),[],"Can you guarantee 12 airbags?")
check("Negative guarantee label never exempts a positive product claim",bool(e) and "12 airbags" not in r["answer"])
for appended in ("and you get ADAS on every variant", "but all variants have ADAS", "and King has ADAS"):
    text="I cannot guarantee the quote, "+appended+"."
    check("Negative clause exemption rejects positive continuation: "+appended,not rg._safe_limitation(text,text))
for connector in ("because", "although", "since", "—"):
    text="I cannot guarantee comfort "+connector+" the Creta has bulletproof glass."
    r,e=rg.validate_decision(answer(text,kind="limitation"),[],"Can you guarantee comfort?")
    check("Negative exemption rejects causal/appositive positive claim: "+connector,bool(e) and "bulletproof" not in r["answer"])
rounded=copy.deepcopy(computed);rounded["value"]="19530.34 INR/month";rounded["derivation"]["value"]="19530.34"
r,e=rg.validate_decision(answer("The illustrative EMI is about 19,530 rupees per month.",[rounded["id"]]),[rounded],q)
check("Explicit nearest-rupee calculator rounding is accepted",r["answered"] and not e)
r,e=rg.validate_decision(answer("The illustrative EMI is about 19,000 rupees per month.",[rounded["id"]]),[rounded],q)
check("Unjustified approximate calculator amount is rejected","unsupported_quantity" in e and "19,000" not in r["answer"])
r,e=rg.validate_decision({"action":"answer","answered":True,"sentences":[]},[computed],q)
check("Empty model response preserves verified calculator result",r["answered"] and "20758.36" in r["answer"] and "annual interest" in r["answer"])
r,e=rg.validate_decision(answer("This is an illustrative estimate, not a lender quote.",[computed["id"]],kind="limitation"),[computed],q)
check("Caveat-only response cannot hide a successful calculator result",r["answered"] and "20758.36" in r["answer"])
r,e=rg.validate_decision(answer("I could not verify that.",["F001"],kind="limitation"),[fact],"Can you confirm it?")
check("Caveat citation alone is not an answered product question",not r["answered"] and r["offer_callback"])
excluded=copy.deepcopy(fact);excluded.update(claim="Panoramic sunroof",value="Standard on King",conditions="Excludes E and EX variants",scope={"variant":"King"})
excluded["applicability_projection"]=knowledge.variant_projection(excluded,{"variant":"E"})
r,e=rg.validate_decision(answer("E does not have a panoramic sunroof.",["F001"]),[excluded],"Does E have a sunroof?",requested_scope={"variant":"E"})
check("Explicit reviewed exclusion supports a negative answer for E",r["answered"] and not e)
for text in ("E has a panoramic sunroof.", "E does not have a panoramic sunroof, but it has ventilated seats.", "E does not have ventilated seats."):
    r,e=rg.validate_decision(answer(text,["F001"]),[excluded],"Does E have a sunroof?",requested_scope={"variant":"E"})
    check("Negative applicability cannot license another positive or unrelated claim: "+text,"unsupported_projected_polarity" in e and not r["answered"])
projected_payload=rg._reason_evidence(excluded)
check("Negative projection never exposes positive higher-trim feature as E evidence","Standard on King" not in projected_payload["value"] and "Excludes E" in projected_payload["value"])
matrix_ac=copy.deepcopy(fact);matrix_ac.update(claim="Air conditioning",value="Manual on E, EX; Dual zone automatic temperature control (DATC) on SX and above",conditions="DATC on King, King Knight",scope={})
matrix_ac["applicability_projection"]=knowledge.variant_projection(matrix_ac,{"variant":["E","King"]})
r,e=rg.validate_decision(answer("E has manual air conditioning.",["F001"]),[matrix_ac],"Compare E and King",requested_scope={"variant":["E","King"]})
check("Exact positive matrix clause supports its explicit trim",r["answered"] and not e)
r,e=rg.validate_decision(answer("King has dual zone automatic temperature control.",["F001"]),[matrix_ac],"Compare E and King",requested_scope={"variant":["E","King"]})
check("Explicit conditions mapping can support an acronym-defined feature",r["answered"] and not e)
for text in ("King has manual air conditioning.","E has dual zone automatic temperature control."):
    r,e=rg.validate_decision(answer(text,["F001"]),[matrix_ac],"Compare E and King",requested_scope={"variant":["E","King"]})
    check("Matrix features cannot swap named trim applicability: "+text,"unsupported_projected_polarity" in e and not r["answered"])
ventilation=copy.deepcopy(excluded);ventilation.update(claim="Front row ventilated seats availability",value="Standard on King",conditions="Not available on SX")
ventilation["applicability_projection"]=knowledge.variant_projection(ventilation,{"variant":"SX"})
for text in ("SX has ventilated seats without a surcharge.","SX does not lack ventilated seats.","SX is not without ventilated seats.","SX does not have rear seats.","SX lacks front seats."):
    r,e=rg.validate_decision(answer(text,["F001"]),[ventilation],"SX seats?",requested_scope={"variant":"SX"})
    check("Projected exclusion cannot invert or broaden its feature: "+text,not r["answered"] and "unsupported_projected_polarity" in e)
isofix=copy.deepcopy(fact);isofix.update(claim="Child seat anchoring",value="ISOFIX child seat anchors",conditions="Standard on all variants",scope={"variant":"all variants"})
r,e=rg.validate_decision(answer("E has a panoramic sunroof.",["F001"]),[isofix],"E sunroof?",requested_scope={"variant":"E"})
check("Unrelated feature cannot borrow an ISOFIX citation","unsupported_assertion_feature" in e and not r["answered"])
torque=copy.deepcopy(fact);torque.update(claim="Maximum torque",value="253 Nm @ 1 500~3 500 r/min",conditions="Turbo petrol engine",scope={})
for text in ("The turbo petrol makes 253 PS.","The turbo petrol has maximum power of 253 Nm."):
    r,e=rg.validate_decision(answer(text,["F001"]),[torque],"Power?")
    check("Torque does not authorize power even when the quantity is equal: "+text,not r["answered"] and bool(set(e)&{"unsupported_assertion_feature","unsupported_quantity_unit"}))
tank=copy.deepcopy(fact);tank.update(claim="Fuel tank capacity",value="50 litres",conditions="",scope={})
r,e=rg.validate_decision(answer("The fuel tank holds 50 kilograms.",["F001"]),[tank],"Tank?")
check("A supported quantity cannot change its unit","unsupported_quantity_unit" in e and not r["answered"])
r,e=rg.validate_decision(answer("The Creta has six gearbox speeds.",["F001"]),[fact],"Gearbox?")
check("Airbag count cannot authorize gearbox speeds","unsupported_assertion_feature" in e and not r["answered"])
for text, source in (("The E variant does not have ISOFIX child-seat anchors.",isofix),("The CRETA has no airbags.",fact),("Airbags are absent.",fact),("The E variant comes without ISOFIX child-seat anchors.",isofix)):
    r,e=rg.validate_decision(answer(text,["F001"]),[source],"Equipment?",requested_scope={"variant":"E"} if source is isofix else {})
    check("Positive equipment cannot license inverse absence: "+text,"unsupported_assertion_polarity" in e and not r["answered"])
for text in ("I cannot guarantee comfort in the bulletproof cabin.","I cannot guarantee comfort, which comes from its titanium armour."):
    r,e=rg.validate_decision(answer(text,kind="limitation"),[],"Can you guarantee comfort?")
    check("Negative limitation cannot smuggle an attributed product property: "+text,bool(e) and text not in r["answer"])
r,e=rg.validate_decision(answer("The CRETA has six gears.",["F001"]),[fact],"Gears?")
check("Gear count requires gearbox assertion rather than another feature count","unsupported_assertion_feature" in e and not r["answered"])
gears=copy.deepcopy(fact);gears.update(id="F002",claim="Turbo transmission",value="7-speed DCT",conditions="Turbo petrol",scope={})
r,e=rg.validate_decision(answer("The turbo petrol has a six-speed gearbox.",["F001","F002"]),[fact,gears],"Gearbox?")
check("Counts stay bound to their feature across multiple citations","unsupported_quantity_unit" in e and not r["answered"])
r,e=rg.validate_decision(answer("The turbo petrol has a seven-speed gearbox.",["F002"]),[gears],"Gearbox?")
check("Correct word-form transmission count remains answerable",r["answered"] and not e)

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
        result=TurnDecision.model_validate(answer("The illustrative EMI is 20758.36 INR/month.",[tool_fact["id"]]))
        object.__setattr__(result,"_runtime_provider","runware")
        object.__setattr__(result,"_runtime_model","contract-fallback")
        return result
    try:
        with patch("server.llm.runtime.structured",side_effect=model):
            final=await rg.run_turn(d,{"session_id":"s_calculate","question":q})
        check("Actual graph invokes tool then recomposes",len(calls)==2 and len(final["result"]["tool_results"])==1 and final["result"]["answered"])
        check("Actual graph reports the provider that returned the answer",final["result"]["provider_used"]=="runware" and final["result"]["model_used"]=="contract-fallback")
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

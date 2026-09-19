"""Offline saved-v5 decisions and approved-v6 lineage regressions; no live quality claim."""
import asyncio
import copy
import json
import os
import socket
import time
from pathlib import Path
from unittest.mock import patch

os.environ.update(MOCK_LLM="1",CLOUD_SYNC="0")
def no_network(*args,**kwargs):raise AssertionError("Final cohort contracts must not open sockets")
socket.socket.connect=no_network
socket.create_connection=no_network
from server import runtime_graph as rg
from server.knowledge import variant_projection
from server.runtime_state import TurnControl

fixture=json.loads((Path(__file__).parent/"fixtures/runtime_final_decisions.json").read_text())
cases=fixture["cases"];registry=fixture["v6_scope_registry"]["facts"];by_id={f["id"]:f for f in registry}
checks=[]
def check(name,passed):
    assert passed,name
    checks.append(name)
def validate(key):
    c=copy.deepcopy(cases[key]);feedback=[]
    result,errors=rg.validate_decision(c["decision"],c["evidence"],c["question"],requested_scope=c["requested_scope"],row_feedback=feedback)
    return result,errors,feedback

for key in ("final_q025","final_q025_repair"):
    answer,errors,feedback=validate(key)
    check(key+" still rejects omitted device purchase rather than treating ownership as payment",not answer["answered"] and "missing_required_condition" in errors)
    check(key+" repair feedback contains the exact reviewed commercial condition",any("third-party purchase" in c["condition"] for row in feedback for c in row.get("required_conditions",[])))
for key in ("final_q041","final_q041_repair"):
    answer,errors,_=validate(key)
    check(key+" exact positive wheel comparisons survive independently grounded clauses",answer["answered"] and not errors and "18-inch alloy" in answer["answer"] and "17-inch" in answer["answer"] and "16-inch steel spare" in answer["answer"])
    c=copy.deepcopy(cases[key]);c["decision"]["sentences"]=[{"text":"The S(O) Knight has 17-inch alloy wheels, whereas the S(O) has 18-inch alloy wheels.","kind":"fact","fact_ids":["F049"]}]
    bad,errors=rg.validate_decision(c["decision"],c["evidence"],c["question"],requested_scope=c["requested_scope"])
    check(key+" clause splitting cannot swap the two trim quantities",not bad["answered"] and bool(errors))
answer,errors,_=validate("final_q049")
check("Actual model-year limit survives terminal yet",not answer["answered"] and "couldn't verify feature details for the 2026 model year" in answer["answer"])
check("Unsupported ongoing and approaching-model-year premises are removed","ongoing model" not in answer["answer"] and "closer" not in answer["answer"] and "unverified_model_availability" in errors)
answer,errors,_=validate("final_q047")
check("Actual SX(O) listing cannot lend unrelated universal equipment",answer["fact_ids"]==["F192"] and "unverified_lineup_applicability" in errors)

boundaries=rg._variant_boundaries(registry,{"variant":"SX(O)"})
check("V6 source-limited name is tied to the reviewed Pune revision",len(boundaries)==1 and boundaries[0]["sources"][0]["listing_id"]=="F252")
excluded=copy.deepcopy(by_id["F250"]);excluded.update(id="excluded_anchor",value="Alloy wheels",conditions="Named fitment",scope={"model":"CRETA","market":"India","variant":"SX(O)"});excluded["knowledge"]["excluded_by_precedence"]=True
check("An excluded named upload cannot grant cross-source lineage",bool(rg._variant_boundaries([*registry,excluded],{"variant":"SX(O)"})))
excluded_listing=copy.deepcopy(by_id["F252"]);excluded_listing["knowledge"]["excluded_by_precedence"]=True
check("An excluded listing cannot anchor same-source inheritance",not rg._variant_boundaries([excluded_listing],{"variant":"SX(O)"})[0]["sources"])
for name in ("E","EX","King"):
    check("V6 affirmative compatible named matrix remains usable: "+name,not rg._variant_boundaries(registry,{"variant":name}))
for title,changes in (
    ("old year",{"scope":{"model":"CRETA","market":"India","variant":"SX(O)","model_year":"2020"}}),
    ("foreign market",{"scope":{"model":"CRETA","market":"Japan","variant":"SX(O)"}}),
    ("different model",{"scope":{"model":"VENUE","market":"India","variant":"SX(O)"}}),
    ("negative mention",{"value":"Not available on SX(O)"}),
    ("uncertain mention",{"conditions":"SX(O) applicability remains unverified"}),
    ("lacks feature",{"value":"SX(O) lacks rear disc brakes."}),
    ("absent feature",{"value":"Rear disc brakes are absent on SX(O)."}),
    ("unconfirmed fitment",{"conditions":"Fitment is not confirmed."}),
    ("future confirmation",{"conditions":"SX(O) applicability is yet to be confirmed"}),
    ("pending confirmation",{"conditions":"Fitment pending confirmation"}),
):
    poison=copy.deepcopy(by_id["F250"]);poison.update(id="contract_upload",value="Alloy wheels",conditions="Named fitment",scope={"model":"CRETA","market":"India","variant":"SX(O)"});poison.update(changes)
    check("Uploaded "+title+" does not establish unrelated current-lineup fitment",bool(rg._variant_boundaries([*registry,poison],{"variant":"SX(O)"})))
same=copy.deepcopy(by_id["F195"]);same["applicability_projection"]=variant_projection(same,{"variant":"SX(O)"});same["runtime_variant_boundary"]=boundaries
listing=copy.deepcopy(by_id["F252"]);listing["applicability_projection"]=variant_projection(listing,{"variant":"SX(O)"});listing["runtime_variant_boundary"]=boundaries
direct={"action":"answer","answered":True,"sentences":[{"text":"According to Hyundai, this trim includes six airbags and rear parking sensors.","kind":"fact","fact_ids":["F195"]}]}
answer,errors=rg.validate_decision(direct,[listing,same],"What does the source say about SX(O)?",requested_scope={"variant":"SX(O)"})
check("Same-revision universal facts remain source-qualified",answer["answered"] and not errors and "reviewed Pune, India record" in answer["answer"] and "equivalence remains unverified" in answer["answer"])
for text in ("SX(O) is in the current India lineup and has six airbags.","The current SX(O) trim includes six airbags."):
    candidate=copy.deepcopy(direct);candidate["sentences"][0]["text"]=text
    answer,errors=rg.validate_decision(candidate,[listing,same],"What does the source say about SX(O)?",requested_scope={"variant":"SX(O)"})
    check("A source qualifier cannot rescue unsupported current identity: "+text,not answer["answered"] and "unverified_lineup_identity" in errors)
other=copy.deepcopy(same);other["knowledge"]["source_revision"]="different_revision"
check("Same ref with a different revision cannot borrow listing scope",not rg._boundary_source(other,boundaries)[0])
check("Unknown trim cannot inherit universal equipment",not rg._boundary_source(same,rg._variant_boundaries(registry,{"variant":"ZZZ"}))[0])
for names in (["SX(O)","ZZZ"],["ZZZ","SX(O)"]):
    check("Every name in a mixed scope is checked: "+str(names),not rg._boundary_source(same,rg._variant_boundaries(registry,{"variant":names}))[0])
explicit=copy.deepcopy(by_id["F103"]);explicit["scope"]["variant"]="SX(O)"
check("An explicit source-scoped website fitment remains eligible",rg._boundary_source(explicit,boundaries)[0])
lounge=rg._variant_boundaries(registry,{"variant":"Lounge Edition"})
guide=copy.deepcopy(by_id["F032"]);guide["applicability_projection"]=variant_projection(guide,{"variant":"Lounge Edition"});guide["runtime_variant_boundary"]=lounge
answer,errors=rg.validate_decision({"action":"answer","answered":True,"sentences":[{"text":"Lounge Edition has five seats.","kind":"fact","fact_ids":["F032"]}]},[guide],"How many seats does Lounge Edition have?",requested_scope={"variant":"Lounge Edition"})
check("An affirmative guide matrix permits its own revision's universal fact with qualification",answer["answered"] and not errors and "reviewed source record" in answer["answer"] and "equivalence remains unverified" in answer["answer"])
unrelated=copy.deepcopy(guide);unrelated["source"]["ref"]="other_guide"
check("An own-guide anchor cannot license an unrelated source",not rg._boundary_source(unrelated,lounge)[0])
cruise=copy.deepcopy(by_id["F154"])
check("A retained cruise assertion cannot omit its explicit transmission restriction",rg._missing_required_condition("Lounge Edition has Smart Cruise Control with Stop & Go.",[cruise]))
check("The cruise restriction can be stated in everyday automatic language",not rg._missing_required_condition("Automatic Lounge Edition variants have Smart Cruise Control with Stop & Go.",[cruise]))
check("The cruise restriction can retain its literal transmission choices",not rg._missing_required_condition("Lounge Edition has Smart Cruise Control with Stop & Go on IVT, AT and DCT versions only.",[cruise]))
check("A restricted automatic feature cannot extend to manual",rg._missing_required_condition("Manual and automatic Lounge Edition versions have Smart Cruise Control.",[cruise]))
check("Ordinary at cannot impersonate an AT transmission",rg._missing_required_condition("At present, Lounge Edition has Smart Cruise Control with Stop and Go.",[cruise]))
check("An unrelated transmission clause cannot qualify cruise",rg._missing_required_condition("Lounge Edition has Smart Cruise Control with Stop and Go; DCT is another option.",[cruise]))
cruise["applicability_projection"]=variant_projection(cruise,{"variant":"Lounge Edition"});cruise["runtime_variant_boundary"]=lounge
answer,errors=rg.validate_decision({"action":"answer","sentences":[{"text":"Automatic Lounge Edition variants have Smart Cruise Control with Stop & Go.","kind":"fact","fact_ids":["F154"]}]},[cruise],"Does Lounge Edition have Smart Cruise Control?",requested_scope={"variant":"Lounge Edition"})
check("Actual conditional cruise survives complete grounding with its automatic qualifier",answer["answered"] and not errors and "equivalence remains unverified" in answer["answer"])

# Actual q064 produced only this clarification, not a discarded refusal. The
# additional controls exercise the newly instructed composition, not a live retry.
q064="I have a budget of 20 lakh but no loan quote. Can you guarantee my EMI will be under 20000 rupees?"
clarify="What loan amount, interest rate, and tenure in months or years would you like to calculate with?"
answer,errors=rg.validate_decision({"action":"clarify","clarification":clarify},[],q064)
check("Actual q064 clarification retains its single-question waiting contract",not errors and answer["clarifying_question"]==clarify)
answer,errors=rg.validate_decision({"action":"clarify","clarification":"I cannot guarantee that EMI. "+clarify},[],q064)
check("A safe atomic refusal can precede one validated clarification",not errors and answer["answer"].startswith("I cannot guarantee that EMI.") and answer["clarifying_question"]==clarify)
answer,errors=rg.validate_decision({"action":"clarify","clarification":clarify,"sentences":[{"kind":"limitation","text":"I cannot guarantee that EMI."}]},[],q064)
check("A separately generated atomic refusal is not discarded by clarify",not errors and answer["answer"].startswith("I cannot guarantee that EMI."))
for prefix in ("I cannot guarantee comfort because the cabin is bulletproof.","I guarantee that EMI.","I cannot guarantee that EMI. This car has twelve airbags."):
    answer,errors=rg.validate_decision({"action":"clarify","clarification":prefix+" "+clarify},[],q064)
    check("Clarification cannot wrap an unsupported claim: "+prefix,"invalid_clarification" in errors and not answer["clarifying_question"])

async def run():
    state={"demo_id":"contract-unused","question":"What does the source say about SX(O)?","snapshot_id":fixture["v6_scope_registry"]["snapshot_id"],"profile":{},"history":[],"control":TurnControl(time.monotonic()+12)}
    pack={"snapshot_id":state["snapshot_id"],"evidence":[copy.deepcopy(by_id[fid]) for fid in ("F252","F195","F175","F082","F151")]}
    with patch("server.runtime_graph.store.load",return_value={"settings":{}}),patch("server.runtime_graph.store.read_json",return_value={"facts":registry}),patch("server.knowledge.retrieve",return_value=pack):
        retrieved=await rg.retrieve(state)
    check("Actual retrieval wiring restricts source-only trim before model composition",{f["id"] for f in retrieved["evidence"]}=={"F252","F195"} and all(f.get("runtime_variant_boundary") for f in retrieved["evidence"]))
    state={**copy.deepcopy(cases["final_q025"]),"demo_id":"contract-unused","control":TurnControl(time.monotonic()+12),"errors":[],"tool_results":[]}
    def repaired(system,content,schema,**kwargs):
        payload=json.loads(content)
        check("One repair receives exact purchase-condition feedback",any(row.get("required_conditions") for row in payload["validation_feedback"]) and "purchased separately" in system)
        return rg._CompositionRepair(sentences=[{"text":"On selected variants, Home-to-Car with Alexa requires a separate purchase of an Echo device.","kind":"fact","fact_ids":["F168"]}])
    with patch("server.runtime_graph.config.MOCK_LLM",False),patch("server.runtime_graph.runtime.structured",side_effect=repaired) as model,patch("server.runtime_graph.store.read_json",return_value={}),patch("server.runtime_graph.usage.trace"):
        result=await rg.validate(state)
    check("Correctly conditioned composition uses one repair and unchanged guards",model.call_count==1 and result["result"]["validation_repair"]["accepted"] and not result["result"]["validation_errors"])
    state={**copy.deepcopy(cases["final_q049"]),"demo_id":"contract-unused","control":TurnControl(time.monotonic()+12),"errors":[],"tool_results":[]}
    with patch("server.runtime_graph.config.MOCK_LLM",False),patch("server.runtime_graph.runtime.structured") as model,patch("server.runtime_graph.store.read_json",return_value={}):
        result=await rg.validate(state)
    check("An intact precise year limit needs no repair for removed unsupported context",not model.called and not result["result"]["answered"] and "2026" in result["result"]["answer"])
asyncio.run(run())
print(f"{len(checks)}/{len(checks)} final cohort contracts passed")
for name in checks:print("PASS",name)

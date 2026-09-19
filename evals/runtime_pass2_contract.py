"""Offline replays of observed QA100 pass2 decisions; no provider or source calls."""
import copy
import asyncio
import json
import os
import re
import socket
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0")
def no_network(*args, **kwargs):
    raise AssertionError("Trace replay must not open a socket")
socket.socket.connect = no_network
socket.create_connection = no_network

from server import knowledge, runtime_graph as rg

fixture=json.loads((Path(__file__).parent/"fixtures/runtime_pass2_decisions.json").read_text())
cases=fixture["cases"]
passed=[]
def check(name, value):
    assert value, name
    passed.append(name)
def replay(key):
    row=cases[key]
    return rg.validate_decision(**{k:row[k] for k in ("decision","evidence","question","customer_text","requested_scope")})

r,e=replay("q051")
check("q051 exact calculator rescue speaks plain decimal principal", "loan of 1000000 rupees" in r["answer"] and not re.search(r"\d[eE][+-]\d",r["answer"]) and r["answered"])
calc=copy.deepcopy(next(f for f in cases["q051"]["evidence"] if f.get("provenance")=="calculation"))
rate=next(v for v in calc["derivation"]["inputs"] if v["name"]=="annual_rate")
rate.update(name="monthly_rate",value=0.9)
check("Calculator speech preserves explicit monthly interest basis", "0.9% monthly interest" in rg._calculation_delivery(calc) and "annual" not in rg._calculation_delivery(calc))

row=cases["q086"]
scope=rg.explicit_scope(row["question"],row["evidence"])
check("q086 ordinary so does not select S(O)",scope.get("variant")=="all variants")
check("Explicit S(O) punctuation remains recognized",rg.canonical_scope_matches("Compare S(O) and S(O) Knight",["S(O)","S(O) Knight"],"variant")==["S(O)","S(O) Knight"])

r,e=replay("q098")
check("q098 universal airbag fact survives redundant E projection citation",not e and "six airbags across all variants, including the E trim" in r["answer"])
r,e=replay("q100")
check("q100 opposing applicability clauses remain independently grounded",not e and "King trim has front row ventilated seats" in r["answer"] and "Front row ventilated seats are not available on the E" in r["answer"])
check("q100 pronoun is replaced by the explicit prior trim", "King also has an electric parking brake" in r["answer"] and not r["answer"].startswith("It also"))
for key,phrase in (("q081","I cannot guarantee that this car will never have a mechanical fault."),("q088","I cannot verify or confirm a 50 percent dealer discount."),("q089","I cannot claim the Creta is objectively safer"),("q093","I could not access that web address.")):
    r,e=replay(key)
    check(key+" exact direct refusal survives",not e and phrase in r["answer"])
r,e=replay("q088")
check("q088 refusal does not assert that no official record exists anywhere","no official record" not in r["answer"])
r,e=replay("q041")
check("q041 retrieved subset cannot establish global coverage absence","unverified_coverage_claim" in e and "aren't covered" not in r["answer"] and "retrieved evidence" in r["answer"])
r,e=replay("q073")
check("q073 linked passages cannot establish whole highlights-page absence","unverified_coverage_claim" in e and "page doesn't state" not in r["answer"])
r,e=replay("q074")
check("q074 document assertions cannot impersonate fresh page verification","unverified_web_attribution" in e and "provided Hyundai page and records list" not in r["answer"])

fact=copy.deepcopy(cases["q098"]["evidence"][1]);fact.update(id="scope-prefix",scope={"variant":"King"},conditions="Available on selected trims")
for qualifier in ("select variants", "selected variants"):
    text="Six airbags are available on "+qualifier+"."
    decision={"action":"answer","sentences":[{"text":text,"fact_ids":[fact["id"]],"kind":"fact"}]}
    r,e=rg.validate_decision(decision,[fact],"Safety features?")
    check("An existing "+qualifier+" qualifier is not prefixed twice",r["answer"]==text and not e)

wheel=fixture["comparison_assertion"]
wheel["applicability_projection"]=knowledge.variant_projection(wheel,{"variant":["S(O)","S(O) Knight"]})
def wheel_answer(text):
    return rg.validate_decision({"action":"answer","sentences":[{"text":text,"fact_ids":[wheel["id"]],"kind":"fact"}]},[wheel],"How is S(O) Knight different from S(O)?",requested_scope={"variant":["S(O)","S(O) Knight"]})
r,e=wheel_answer("S(O) has R17 alloy wheels.")
check("Literal R17 wheel row licenses its S(O) trim",r["answered"] and not e)
r,e=wheel_answer("S(O) Knight has R18 alloy wheels.")
check("Literal R18 wheel row licenses S(O) Knight",r["answered"] and not e)
r,e=wheel_answer("S(O) has R18 alloy wheels.")
check("S(O) cannot borrow R18 from another projected row",not r["answered"] and "unsupported_quantity" in e)
r,e=wheel_answer("Both S(O) and S(O) Knight have R18 alloy wheels.")
check("A mixed comparison cannot universalize the other row's R18 quantity",not r["answered"])

focused=json.loads((Path(__file__).parent/"fixtures/runtime_focused_decisions.json").read_text())["cases"]
def focused_replay(key):
    row=focused[key]
    return rg.validate_decision(**{k:row[k] for k in ("decision","evidence","question","customer_text","requested_scope")})
row=focused["q041"]
scope=rg.explicit_scope(row["question"],row["evidence"])
check("Focused q041 parenthesized fallback never shortens S(O) Knight",set(scope["variant"])=={"S(O)","S(O) Knight"})
r,e=focused_replay("q047")
check("Focused q047 preserves the market-specific FAQ scope","reviewed Pune, India FAQ lists SX(O)" in r["answer"] and "Current availability still needs confirmation" in r["answer"])
f=next(f for f in focused["q047"]["evidence"] if f["id"]=="F192")
check("Projection prompt retains original material market conditions","Market-specific" in rg._reason_evidence(f)["conditions"])
r,e=focused_replay("q050")
check("Focused q050 can state a supported subset of standard safety equipment","Rear parking sensors come standard on both the E and King trims" in r["answer"])
r,e=focused_replay("q098")
check("Focused q098 broad safety projection preserves its airbag subset",not e and r["answered"] and "standard with six airbags" in r["answer"])
r,e=focused_replay("q100")
check("Focused q100 plural which-are comparison stays grounded",not e and r["answered"] and "King trim has front row ventilated seats and an electric parking brake" in r["answer"] and "are not available on the E variant" in r["answer"])
check("Focused q100 shared seat/airbag/ISOFIX subsets remain answerable","five seats, six airbags, and ISOFIX child seat anchors" in r["answer"])

async def required_lookup_contract():
    row=focused["q067"]
    state={"demo_id":"contract-unused","question":row["question"],"control":SimpleNamespace(remaining=lambda:12.0),"tool_results":[],"evidence":row["evidence"]}
    decision=await rg.reason(state)
    check("Focused q067 explicit supplied-page intent dispatches lookup before any model answer",decision["decision"]["action"]=="tools" and decision["decision"]["tool_calls"][0]["tool"]=="source_lookup")
    state["decision"]=decision["decision"]
    with patch("server.runtime_graph.source_lookup",side_effect=ValueError("Source unavailable")):
        result=await rg.tools_node(state)
    check("Failed source attempt records the requested URL for loop prevention",result["tool_results"][0]["requested_url"]=="https://www.hyundai.com/in/en/find-a-car/creta/specification")
    state.update(result)
    with patch("server.runtime_graph.store.load",return_value={}),patch("server.runtime_graph.store.read_json",return_value={}):
        next_step=await rg.reason(state)
    check("A failed explicit page lookup is not dispatched again",next_step["decision"]["action"]=="answer")
    row=cases["q098"]
    state={"demo_id":"contract-unused","question":"Check https://example.com/car for airbags","decision":row["decision"],"evidence":row["evidence"],"requested_scope":row["requested_scope"]}
    with patch("server.runtime_graph.store.read_json",return_value={}):
        result=await rg.validate(state)
    check("Unattempted lookup is never described as a failed page check",result["result"]["answer"].startswith("I haven't checked that page. From reviewed material,") and "requested_page_not_used" in result["result"]["validation_errors"])
    state["tool_results"]=[{"tool":"source_lookup","requested_url":"https://example.com/car","error":"Source unavailable"}]
    with patch("server.runtime_graph.store.read_json",return_value={}):
        result=await rg.validate(state)
    check("Attempted lookup failure is distinguished from stored evidence",result["result"]["answer"].startswith("I couldn't verify that from the requested page. From reviewed material,"))
    private={"demo_id":"contract-unused","question":cases["q093"]["question"],"control":SimpleNamespace(remaining=lambda:12.0),"tool_results":[],"evidence":[]}
    private["decision"]=(await rg.reason(private))["decision"]
    rejected=await rg.tools_node(private)
    check("Forced private-URL intent still uses the public-source safety boundary",rejected["tool_results"][0].get("error") and not rejected["tool_results"][0].get("evidence"))
asyncio.run(required_lookup_contract())
check("Explicit do-not-fetch instruction never triggers deterministic lookup",not rg._verification_urls("Do not check https://example.com/car; use the reviewed brochure."))
linked=next(f for f in cases["q073"]["evidence"] if f.get("provenance")=="live_web")
r,e=rg.validate_decision({"action":"answer","sentences":[{"text":"The provided highlights page lists roadside assistance.","fact_ids":[linked["id"]],"kind":"fact"}]},[linked],cases["q073"]["question"])
check("A linked child passage cannot impersonate the requested page","unverified_web_attribution" in e and not r["answered"])

print(f"{len(passed)}/{len(passed)} pass2 trace replay contracts passed")
for name in passed:print("PASS",name)

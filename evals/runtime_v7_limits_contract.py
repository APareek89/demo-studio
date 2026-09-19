"""Saved v7 drafts: precise limits, transmission scope and relation checks, offline."""
import asyncio
import copy
import json
import os
import socket
import time
from pathlib import Path
from unittest.mock import patch

os.environ.update(MOCK_LLM="1",CLOUD_SYNC="0")
def no_network(*a,**k):raise AssertionError("V7 contracts must not open sockets")
socket.socket.connect=no_network;socket.create_connection=no_network
from server import runtime_graph as rg
from server.runtime_state import TurnControl

fixture=json.loads((Path(__file__).parent/"fixtures/runtime_v7_limits.json").read_text())
cases=fixture["cases"];checks=[]
registry={f["id"]:f for f in fixture["lineage_registry"]["facts"]}
for case in cases.values():
    case["evidence"]=[{**copy.deepcopy(registry[f["id"]]),**f} for f in case["evidence"]]
def check(name,passed):
    assert passed,name
    checks.append(name)
def validate(key):
    c=copy.deepcopy(cases[key]);feedback=[]
    answer,errors=rg.validate_decision(c["decision"],c["evidence"],c["question"],requested_scope=c["requested_scope"],row_feedback=feedback)
    return answer,errors,feedback

for key,phrase in (
    ("q016","whether a rear-seat armrest is included"),("q016_repair","rear-seat armrest availability"),
    ("q029","scheduled maintenance intervals, routine service costs, or service packages"),
    ("q029_repair","vehicle maintenance schedules, routine service costs, or servicing packages"),
    ("q030","fuel-economy figures or their test conditions"),("q030_repair","fuel-economy figures or their applicable test conditions"),
    ("q034","boot capacity measurements (litres)"),("q034_repair","boot volume (litres)"),
    ("q082","I cannot guarantee how comfortably three adults will fit."),("q082_repair","I cannot guarantee individual comfort."),
    ("q083","I cannot confirm the crash-test rating, testing agency or test year."),
    ("q083_repair","I cannot confirm the crash-test rating, testing body or test year."),
    ("q095","I cannot guarantee that a future offer is available today."),
    ("q080","insurance renewal three years ahead"),
):
    answer,errors,feedback=validate(key)
    check(key+" keeps its actual precise limitation",phrase in answer["answer"])
    check(key+" does not reject that own-limit row",not any(row.get("kind")=="limitation" for row in feedback))
answer,errors,_=validate("q030")
check("Missing economy cannot be replaced by tank capacity",not answer["answered"] and "50" not in answer["answer"] and "unresponsive_attribute" in errors)
answer,errors,_=validate("q065")
check("A non-estimation acknowledgement keeps all explicitly requested inputs",answer["answered"] and not errors and all(word in answer["answer"] for word in ("won't estimate","driving distance","fuel efficiency","fuel price")))
answer,errors,_=validate("q092")
check("An instruction-attack refusal can remain ordinary assistant interaction",answer["answered"] and not errors and "No, that will not change my answer" in answer["answer"] and "Please let me know" in answer["answer"])
for text in (
    "I cannot verify comfort from the bulletproof cabin.",
    "I cannot guarantee comfort because the car has bulletproof glass.",
    "I do not have the details because every variant has airbags.",
    "I cannot confirm the rating because those details are not in my reviewed documents and every variant has a five-star rating.",
    "I could not verify from our current details whether a rear-seat armrest is included, and it has twelve airbags.",
    "I won't estimate running costs without fuel efficiency and the car has a titanium body.",
    "Whenever you'd like to calculate it, let me know fuel efficiency and the car has twelve airbags.",
):
    answer,errors=rg.validate_decision({"action":"answer","answered":True,"sentences":[{"text":text,"kind":"limitation" if text.startswith("I ") else "context","fact_ids":[]}]},[],"What can you verify?")
    check("Own-limit normalization cannot leak a positive premise: "+text,not answer["answered"] and bool(errors) and not any(word in answer["answer"] for word in ("bulletproof","titanium","twelve","five-star")))

for key in ("q078","q080"):
    answer,errors,_=validate(key)
    check(key+" cannot invent a financial dependence from a different assertion", "unsupported_dependency_relation" in errors and "depend" not in answer["answer"])
relation={"id":"relation","approved":True,"claim":"Variant availability","value":"Availability depends on powertrain configuration and dealership stock.","conditions":"", "scope":{}}
positive="Variant availability depends on powertrain configuration and dealership stock."
check("A same-assertion explicit dependence remains supported",not rg._unsupported_dependency_relation(positive,[relation]))
check("An own uncertainty is not a positive dependence claim",not rg._unsupported_dependency_relation("I cannot verify whether the discount depends on stock.",[relation]))
split=[{**relation,"value":"Variant availability"},{**relation,"id":"stock","claim":"Stock policy","value":"Discount depends on dealership stock."}]
check("Different facts cannot jointly invent the dependence subject",rg._unsupported_dependency_relation(positive,split))
quote={**relation,"value":"Variant availability","source":{"quote":positive}}
check("A provenance quote cannot fund an unrelated dependence",rg._unsupported_dependency_relation(positive,[quote]))
web={"id":"W1","provenance":"live_web","value":"Price depends on configuration.","conditions":"","source":{"url":"https://example.com/car/price"}}
for sentence,supported in (("According to example.com, price depends on configuration.",True),("According to example.com, price depends on dealership stock.",False)):
    answer,errors=rg.validate_decision({"action":"answer","answered":True,"sentences":[{"text":sentence,"fact_ids":["W1"],"kind":"fact"}]},[web],"What does the page say about price?")
    check("Selected live assertion relation is checked without rejecting attribution: "+sentence,answer["answered"]==supported and ((not errors) if supported else "unsupported_dependency_relation" in errors))

c=copy.deepcopy(cases["q040_repair"]);feature=next(f for f in c["evidence"] if f["id"]=="F064")
answer,errors,_=validate("q040_repair")
check("Actual automatic S(O) parking brake projection accepts its feature anchor",not errors and "electric parking brake" in answer["answer"] and "automatic" in answer["answer"])
for text in ("S(O) has an electric parking brake with auto hold.","Manual S(O) has an electric parking brake with auto hold.","S(O) has an electric parking brake with auto hold; automatic is another option.","S(O) has an electric parking brake with auto hold, and automatic is another option."):
    check("Transmission projection still rejects unqualified or unrelated automatic language: "+text,not rg._projected_support(feature,text,c["requested_scope"])[0])

async def run():
    for key in ("q016","q030","q083","q095"):
        state={**copy.deepcopy(cases[key]),"demo_id":"contract-unused","control":TurnControl(time.monotonic()+12),"errors":[],"tool_results":[]}
        with patch("server.runtime_graph.config.MOCK_LLM",False),patch("server.runtime_graph.runtime.structured") as model,patch("server.runtime_graph.store.read_json",return_value={}):
            result=await rg.validate(state)
        check(key+" intact useful limit does not spend a repair call",not model.called and not result["result"].get("validation_repair",{}).get("attempted"))
    c=copy.deepcopy(cases["q096"])
    state={"demo_id":"contract-unused","question":c["question"],"snapshot_id":fixture["snapshot_id"],"profile":{},"history":[],"control":TurnControl(time.monotonic()+12)}
    pack={"snapshot_id":fixture["snapshot_id"],"evidence":c["evidence"]}
    with patch("server.runtime_graph.store.load",return_value={"settings":{}}),patch("server.runtime_graph.store.read_json",return_value=fixture["lineage_registry"]),patch("server.knowledge.retrieve",return_value=pack):
        retrieved=await rg.retrieve(state)
    check("Full pinned registry's empty SX boundary survives reduced evidence",all(f.get("runtime_variant_boundary") == [] for f in retrieved["evidence"]))
    check("Compact provider payload preserves the authoritative empty marker",all("runtime_variant_boundary" in rg._reason_evidence(f) for f in retrieved["evidence"]))
    answer,errors=rg.validate_decision(c["decision"],retrieved["evidence"],c["question"],requested_scope=c["requested_scope"])
    check("Actual SX parking facts and EPB absence survive the correct lineage",not errors and all(phrase in answer["answer"] for phrase in ("rear parking sensors","rear camera","isn't available")) and "unverified" not in answer["answer"])
asyncio.run(run())
print(f"{len(checks)}/{len(checks)} v7 precise-limit contracts passed")
for name in checks:print("PASS",name)

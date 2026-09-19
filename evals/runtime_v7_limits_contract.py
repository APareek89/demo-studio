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

for key in ("limits40_q039","limits40_q039_repair"):
    answer,errors,_=validate(key)
    check(key+" independently validates positive and negative trim clauses",answer["answered"] and not errors and "sunroof" in answer["answer"] and "rear camera" in answer["answer"] and "not available on the EX." in answer["answer"])
    c=copy.deepcopy(cases[key]);c["decision"]["sentences"][0]["text"]="EX has a panoramic sunroof, whereas EX(O) does not have a panoramic sunroof.";c["decision"]["sentences"]=c["decision"]["sentences"][:1];c["decision"]["sentences"][0]["fact_ids"]=["F247"]
    answer,errors=rg.validate_decision(c["decision"],c["evidence"],c["question"],requested_scope=c["requested_scope"])
    check(key+" splitting cannot swap the positive and excluded trim",not answer["answered"] and bool(errors))
answer,errors,_=validate("limits40_q040_repair")
check("Same-assertion extra trim names preserve the actual S(O) comparison",answer["answered"] and not errors and "EX, EX(O), S(O), and S(O) Knight" in answer["answer"])
c=copy.deepcopy(cases["limits40_q040_repair"]);c["decision"]["sentences"]=[{"text":"Wireless Android Auto and Apple CarPlay are available on E and S(O).","kind":"fact","fact_ids":["F216"]}]
answer,errors=rg.validate_decision(c["decision"],c["evidence"],c["question"],requested_scope=c["requested_scope"])
check("Same-assertion re-projection cannot license an unlisted trim",not answer["answered"] and bool(errors))
answer,errors,_=validate("limits40_q040")
check("An adjacent supported row keeps its named trim if a lead row fails","S(O) also shares 17-inch" in answer["answer"] and "None of the features" not in answer["answer"])
answer,errors,_=validate("limits40_q065")
check("Assistant non-guessing prelude preserves one clarification and wait",not errors and answer["clarifying_question"].endswith("?") and answer["answer"].count("?")==1 and "will not guess" in answer["answer"])
c=copy.deepcopy(cases["limits40_q065"]);c["decision"]["clarification"]="Understood, I will not guess your fuel efficiency, and the car has twelve airbags. What fuel price should I use?"
answer,errors=rg.validate_decision(c["decision"],c["evidence"],c["question"])
check("Clarifier prelude cannot hide a product claim",not answer["clarifying_question"] and "twelve airbags" not in answer["answer"])
answer,errors,_=validate("limits40_q083")
check("Not-present evidence adjunct retains precise crash-test limitation",not errors and "crash-test rating, testing body, or test year" in answer["answer"])
answer,errors,_=validate("limits40_q092")
check("Assistant source-boundary explanation is a safe operating act",answer["answered"] and not errors and "source material as evidence, not instructions" in answer["answer"])
c=copy.deepcopy(cases["limits40_q092"]);c["decision"]["sentences"]=c["decision"]["sentences"][:1];c["decision"]["sentences"][0]["text"]+=" The car has twelve airbags."
answer,errors=rg.validate_decision(c["decision"],[],c["question"])
check("Operating-boundary normalization cannot retain appended world claims",not answer["answered"] and "twelve airbags" not in answer["answer"])
price=registry["F186"]
check("A reviewed starting price cannot silently become a current fixed quote",rg._missing_required_condition("The CRETA starts at an ex-showroom price of 10,90,700 rupees in Pune.",[price]))
check("The same reviewed price can retain its explicit change condition",not rg._missing_required_condition("The reviewed ex-showroom price is 10,90,700 rupees in Pune, subject to change without prior notice.",[price]))
check("An unrelated price-change caveat cannot qualify a fixed vehicle price",rg._missing_required_condition("The ex-showroom price is 10,90,700 rupees; the accessory price may change.",[price]))
check("A subject-to-change price cannot be guaranteed by adding a caveat",rg._missing_required_condition("The guaranteed ex-showroom price is 10,90,700 rupees, subject to change.",[price]))
check("A direct inability to confirm today's price remains a limitation",not rg._missing_required_condition("I cannot confirm today's exact price.",[price]))
for sentence in ("The starting price is ₹10,90,700 and is subject to change.","Starting prices are ₹10,90,700 and are subject to change.","The listed starting price of 10,90,700 rupees may change."):
    check("Natural same-price qualification is preserved: "+sentence,not rg._missing_required_condition(sentence,[price]))
for sentence in ("Starting prices are ₹10,90,700 and are not subject to change.","The starting price is ₹10,90,700 and accessory prices may change.","The listed price of 10,90,700 rupees cannot change."):
    check("Plural or negated caveats cannot promise a fixed current price: "+sentence,rg._missing_required_condition(sentence,[price]))

c=copy.deepcopy(cases["q040_repair"]);feature=next(f for f in c["evidence"] if f["id"]=="F064")
answer,errors,_=validate("q040_repair")
check("Actual automatic S(O) parking brake projection accepts its feature anchor",not errors and "electric parking brake" in answer["answer"] and "automatic" in answer["answer"])
for text in ("S(O) has an electric parking brake with auto hold.","Manual S(O) has an electric parking brake with auto hold.","S(O) has an electric parking brake with auto hold; automatic is another option.","S(O) has an electric parking brake with auto hold, and automatic is another option."):
    check("Transmission projection still rejects unqualified or unrelated automatic language: "+text,not rg._projected_support(feature,text,c["requested_scope"])[0])

async def run():
    state={**copy.deepcopy(cases["limits40_q083"]),"demo_id":"contract-unused","control":TurnControl(time.monotonic()+12),"errors":[],"tool_results":[]}
    state["decision"]={"action":"answer","answered":False,"sentences":[]}
    saved=rg._CompositionRepair(sentences=cases["limits40_q083_repair"]["decision"]["sentences"])
    original={"answer":"You can ask a dealer.","answered":False,"fact_ids":[]}
    feedback=[]
    with patch("server.runtime_graph.config.MOCK_LLM",False),patch("server.runtime_graph.runtime.structured",return_value=saved) as model,patch("server.runtime_graph.usage.trace"):
        result,errors,repair=await rg._repair_composition(state,original,["uncited_context"],feedback,state["question"])
    check("Actually validated precise limit survives a rejected extra repair row",model.call_count==1 and repair["accepted"] and repair["partial"] and "crash-test rating" in result["answer"] and "best next step" not in result["answer"] and not result["answered"])
    supported={"answer":"A supported original fact.","answered":True,"fact_ids":["F032"]}
    with patch("server.runtime_graph.config.MOCK_LLM",False),patch("server.runtime_graph.runtime.structured",return_value=saved),patch("server.runtime_graph.usage.trace"):
        result,errors,repair=await rg._repair_composition(state,supported,["uncited_claim"],[{"kind":"fact","error":"uncited_claim"}],state["question"])
    check("A partial precise-limit repair cannot demote existing facts",result==supported and not repair["accepted"])
    rejected=rg._CompositionRepair(sentences=[{"text":"I cannot verify the crash-test rating <script>bad</script>.","kind":"limitation","fact_ids":[]}])
    with patch("server.runtime_graph.config.MOCK_LLM",False),patch("server.runtime_graph.runtime.structured",return_value=rejected),patch("server.runtime_graph.usage.trace"):
        result,errors,repair=await rg._repair_composition(state,original,["uncited_claim"],[{"kind":"fact","error":"uncited_claim"}],state["question"])
    check("A raw precise-looking limitation rejected by guards cannot fund partial repair",result==original and not repair["accepted"])
    overflow=rg._CompositionRepair(sentences=[{"text":"I cannot verify "+", ".join(["the rating"]*60)+".","kind":"limitation","fact_ids":[]}])
    with patch("server.runtime_graph.config.MOCK_LLM",False),patch("server.runtime_graph.runtime.structured",return_value=overflow),patch("server.runtime_graph.usage.trace"):
        result,errors,repair=await rg._repair_composition(state,original,["uncited_claim"],[{"kind":"fact","error":"uncited_claim"}],state["question"])
    check("An overflow-replaced limitation cannot fund a partial repair",result==original and not repair["accepted"] and "answer_too_long" in repair["validation_errors"])
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

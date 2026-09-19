"""Operational failure speech and cumulative reason timing, no network/data writes."""
import asyncio
import os
import socket
import time
from unittest.mock import patch

os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0")
def no_network(*args, **kwargs):
    raise AssertionError("Operational-failure contracts must not open sockets")
socket.socket.connect = no_network
socket.create_connection = no_network

from server import runtime_graph as rg
from server.runtime_state import TurnControl, TurnDecision
from server.runtime_tools import calculate

checks = []
def check(name, passed):
    assert passed, name
    checks.append(name)

QUESTION = "Estimate EMI for a loan of 600000 INR at zero percent annual interest over 3 years."
TOOL = {"tool":"calculator", "operation":"emi", "inputs":[
    {"name":"principal", "value":600000, "unit":"INR", "source_id":"customer", "quote":"600000 INR"},
    {"name":"annual_rate", "value":0, "unit":"percent", "source_id":"customer", "quote":"zero percent annual interest"},
    {"name":"tenure", "value":3, "unit":"years", "source_id":"customer", "quote":"3 years"},
]}
CALCULATED = calculate(TOOL, [], QUESTION)
OPERATIONAL = "I'm having trouble checking that right now. You can ask again, or we can carry on."

def state():
    return {"demo_id":"contract-unused", "question":QUESTION, "profile":{}, "history":[],
            "evidence":[], "tool_results":[], "errors":[], "timings":{"retrieve_ms":200},
            "control":TurnControl(time.monotonic()+12)}

async def run():
    # Recorded durations reproduce the q053 accounting shape without a real wait.
    original = state()
    with patch("server.runtime_graph.config.MOCK_LLM",False), patch("server.runtime_graph.store.load",return_value={"settings":{}}), patch("server.runtime_graph.store.read_json",return_value={}), patch("server.runtime_graph.usage.trace"), patch("server.runtime_graph.runtime.structured",return_value=TurnDecision(action="tools",tool_calls=[TOOL])), patch("server.runtime_graph._elapsed",return_value=4700):
        first = await rg.reason(original)
    after_tool = {**original, **first, "evidence":[CALCULATED], "tool_results":[{"tool":"calculator","evidence":[CALCULATED]}]}
    with patch("server.runtime_graph.config.MOCK_LLM",False), patch("server.runtime_graph.store.load",return_value={"settings":{}}), patch("server.runtime_graph.store.read_json",return_value={}), patch("server.runtime_graph.usage.trace"), patch("server.runtime_graph.runtime.structured",side_effect=TimeoutError("provider composition deadline")), patch("server.runtime_graph._elapsed",return_value=6800):
        second = await rg.reason(after_tool)
    check("A failed second reasoning round includes the completed first round",first["timings"]["reason_ms"]==4700 and second["timings"]["reason_ms"]==11500)
    check("Cumulative reasoning retains other stage timings and failure identity",second["timings"]["retrieve_ms"]==200 and second["errors"]==["reasoning_unavailable"])
    with patch("server.runtime_graph.store.read_json",return_value={}), patch("server.runtime_graph.runtime.structured") as provider:
        rescued = await rg.validate({**after_tool, **second})
    result=rescued["result"]
    check("Completed audited arithmetic takes precedence over operational failure speech",result["answered"] and result["calculation_fallback"] and not result["provider_failed"] and result["reasoning_failed"] and result["fact_ids"]==[CALCULATED["id"]] and "16666.67" in result["answer"] and OPERATIONAL not in result["answer"])
    check("The recovered calculation preserves assumptions and needs no further provider",not provider.called and all(t in result["answer"] for t in ("600000","0% annual","3 years","fees","lender quote")))

    first_failure=state()
    with patch("server.runtime_graph.config.MOCK_LLM",False), patch("server.runtime_graph.store.load",return_value={"settings":{}}), patch("server.runtime_graph.store.read_json",return_value={}), patch("server.runtime_graph.usage.trace"), patch("server.runtime_graph.runtime.structured",side_effect=TimeoutError("initial provider deadline")), patch("server.runtime_graph._elapsed",return_value=11600):
        failure=await rg.reason(first_failure)
    check("A first-round failure does not invent an earlier reasoning duration",failure["timings"]["reason_ms"]==11600)
    with patch("server.runtime_graph.store.read_json",return_value={}), patch("server.runtime_graph.runtime.structured") as provider:
        failed=await rg.validate({**first_failure,**failure})
    result=failed["result"]
    check("Actual provider failure delivers an operational explanation, not a knowledge gap",result["answer"]==OPERATIONAL and not result["answered"] and result["provider_failed"] and result["reasoning_failed"] and not result["fact_ids"])
    check("Operational failure preserves flags without reporting its own code prose as ungrounded",failed["errors"]==["reasoning_unavailable"] and not result["validation_errors"] and not result["offer_callback"] and not provider.called)

    # A provider label cannot turn arbitrary model text into a factual answer.
    fake=dict(first_failure)
    fake.update(errors=["reasoning_unavailable"],decision={"action":"answer","answered":True,"sentences":[{"text":"The car has twelve airbags.","kind":"fact","fact_ids":[]}]})
    with patch("server.runtime_graph.store.read_json",return_value={}):
        result=(await rg.validate(fake))["result"]
    check("Failed-provider content cannot escape through the operational path",result["answer"]==OPERATIONAL and not result["answered"] and "twelve" not in result["answer"])
    nonfailure={**state(),"decision":{"action":"answer","answered":True,"sentences":[{"text":OPERATIONAL+" The car has twelve airbags.","kind":"context","fact_ids":[]}]}}
    with patch("server.runtime_graph.store.read_json",return_value={}):
        result=(await rg.validate(nonfailure))["result"]
    check("Operational wording is not a new uncited model-claim exemption",not result["provider_failed"] and not result["answered"] and "twelve" not in result["answer"])

    for label,tool_results in (
        ("pending",[]),
        ("failed",[{"tool":"calculator","error":"operand rejected","evidence":[CALCULATED]}]),
        ("lookup",[{"tool":"source_lookup","evidence":[CALCULATED]}]),
    ):
        current={**state(),**failure,"evidence":[CALCULATED],"tool_results":tool_results}
        with patch("server.runtime_graph.store.read_json",return_value={}):
            result=(await rg.validate(current))["result"]
        check(label+" calculator evidence cannot replace the operational failure",result["answer"]==OPERATIONAL and result["provider_failed"] and not result["fact_ids"] and not result["calculation_fallback"])

    cancelled={**state(),"session_id":"cancelled","turn_id":"failure", "kind":"qa","result":result}
    cancelled["control"].cancelled.set()
    with patch("server.runtime_graph.checkpoint") as checkpoint:
        try: await rg.delivery_plan(cancelled)
        except InterruptedError: rejected=True
        else: rejected=False
    check("Cancellation still prevents operational failure speech delivery",rejected and not checkpoint.called)

asyncio.run(run())
print(f"{len(checks)}/{len(checks)} operational failure contracts passed")
for name in checks:print("PASS",name)

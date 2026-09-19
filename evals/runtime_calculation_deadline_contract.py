"""Actual graph with a blocked composition provider; no network or real data."""
import asyncio
import copy
import json
import os
import socket
import threading
import time
from unittest.mock import patch

os.environ.update(MOCK_LLM="1",CLOUD_SYNC="0")
def no_network(*a,**k):raise AssertionError("Deadline contracts must not open sockets")
socket.socket.connect=no_network;socket.create_connection=no_network
from server import runtime_graph as rg
from server.runtime_state import TurnControl,TurnDecision
from server.runtime_tools import calculate

checks=[]
def check(name,passed):
    assert passed,name
    checks.append(name)
question="Estimate EMI for a loan of 800000 INR at 8% per year over 4 years."
tool={"tool":"calculator","operation":"emi","inputs":[
    {"name":"principal","value":800000,"unit":"INR","source_id":"customer","quote":"800000 INR"},
    {"name":"annual_rate","value":8,"unit":"percent","source_id":"customer","quote":"8% per year"},
    {"name":"tenure","value":4,"unit":"years","source_id":"customer","quote":"4 years"},
]}
calculated=calculate(tool,[],question)

async def graph_case(mode):
    control=TurnControl(time.monotonic()+0.75)
    release=threading.Event();entered=threading.Event();calls=[];marks=[]
    def provider(system,payload,schema,**kw):
        data=json.loads(payload);calls.append((data,kw["timeout_budget_s"]))
        if len(calls)==1 and mode!="no_tool":
            request=copy.deepcopy(tool)
            if mode=="invalid":request["inputs"][1]["value"]=9
            return TurnDecision(action="tools",tool_calls=[request])
        entered.set();release.wait(2)
        return TurnDecision(action="answer",answered=True,sentences=[{"text":"The payment is 999999 rupees.","fact_ids":[],"kind":"fact"}])
    with patch("server.runtime_graph.config.MOCK_LLM",False),patch("server.runtime_graph.store.load",return_value={"settings":{}}),patch("server.runtime_graph.store.read_json",return_value={}),patch("server.knowledge.retrieve",return_value={"evidence":[],"snapshot_id":""}),patch("server.runtime_graph.previous_state",return_value={}),patch("server.runtime_graph.claim_turn",return_value=control),patch("server.runtime_graph.checkpoint",side_effect=lambda state,mark:marks.append(mark)),patch("server.runtime_graph.usage.trace"),patch("server.runtime_graph.runtime.structured",side_effect=provider):
        started=time.monotonic();task=asyncio.create_task(rg.run_turn("contract-unused",{"session_id":"deadline","turn_id":mode,"question":question}))
        while not entered.is_set():await asyncio.sleep(0.005)
        if mode=="cancel":control.cancelled.set()
        try:
            final=await task
        except InterruptedError:
            check("Superseded calculation composition cannot deliver",mode=="cancel" and "ready_to_deliver" not in marks)
            final=None
        elapsed=time.monotonic()-started
        if final:
            result=final["result"]
            check(mode+" validates and delivers within the original reduced deadline",elapsed<0.75 and calls[-1][1]<0.51)
            if mode=="complete":
                check("A completed audited EMI survives a blocked second composition",result["answered"] and result["calculation_fallback"] and result["fact_ids"]==[calculated["id"]] and "19530.34" in result["answer"])
                check("Calculation speech retains annual rate, amount and tenure",all(value in result["answer"] for value in ("800000","8%","annual","4 years")))
                check("Composition failure remains visible without marking delivered arithmetic unavailable",result["reasoning_failed"] and not result["provider_failed"] and "reasoning_unavailable" in final["errors"])
                check("Only completed audited tool provenance is retained",result["tool_results"][0]["evidence"][0]["derivation"]==calculated["derivation"])
            else:
                check(mode+" cannot fabricate a calculator result",not result["answered"] and result["provider_failed"] and not result["fact_ids"] and not result["calculation_fallback"])
            before=json.dumps({k:final[k] for k in ("result","delivery")},sort_keys=True);mark_count=len(marks)
        release.set();await asyncio.sleep(0.04)
        if final:check(mode+" late provider result cannot overwrite delivery",json.dumps({k:final[k] for k in ("result","delivery")},sort_keys=True)==before and len(marks)==mark_count and "999999" not in final["result"]["answer"])

async def run():
    for mode in ("complete","no_tool","invalid","cancel"):await graph_case(mode)
    for label,results in (("none",[]),("failed",[{"tool":"calculator","error":"rejected operand","evidence":[calculated]}]),("lookup",[{"tool":"source_lookup","evidence":[calculated]}])):
        state={"demo_id":"contract-unused","question":question,"evidence":[calculated],"tool_results":results,"errors":["reasoning_unavailable"],"decision":{"action":"answer","answered":False,"sentences":[]},"control":TurnControl(time.monotonic()+1)}
        with patch("server.runtime_graph.store.read_json",return_value={}):result=await rg.validate(state)
        check("A "+label+" calculator completion cannot be salvaged from evidence alone",not result["result"]["answered"] and not result["result"]["fact_ids"])
    state={"demo_id":"contract-unused","question":question,"evidence":[calculated],"tool_results":[{"tool":"calculator","evidence":[calculated]}],"control":TurnControl(time.monotonic()+0.2)}
    with patch("server.runtime_graph.config.MOCK_LLM",False),patch("server.runtime_graph.store.load",return_value={"settings":{}}),patch("server.runtime_graph.store.read_json",return_value={}),patch("server.runtime_graph.usage.trace"),patch("server.runtime_graph.runtime.structured") as model:
        reason=await rg.reason(state);result=await rg.validate({**state,**reason})
    check("Low remaining budget skips the provider and validates completed arithmetic",not model.called and result["result"]["calculation_fallback"])
asyncio.run(run())
print(f"{len(checks)}/{len(checks)} calculation deadline contracts passed")
for name in checks:print("PASS",name)

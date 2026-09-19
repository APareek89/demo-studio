"""Offline replays of observed QA100 pass2 decisions; no provider or source calls."""
import copy
import json
import os
import re
import socket
from pathlib import Path

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

print(f"{len(passed)}/{len(passed)} pass2 trace replay contracts passed")
for name in passed:print("PASS",name)

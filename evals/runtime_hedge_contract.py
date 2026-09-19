"""Off-default delayed fallback race: real threads, fake providers, zero egress."""
import copy
import json
import os
import socket
import threading
import time
from contextlib import ExitStack
from unittest.mock import patch

os.environ.update(MOCK_LLM="1",CLOUD_SYNC="0")
def no_network(*args,**kwargs):raise AssertionError("Hedge contracts must not open sockets")
socket.socket.connect=no_network;socket.create_connection=no_network
import httpx
from pydantic import BaseModel
from server import config,usage
from server.llm import runtime,gemini,claude,runware

class Answer(BaseModel):
    answer:str

def answer(text):return Answer(answer=text)
checks=[]
def check(name,passed):
    assert passed,name
    checks.append(name)

def setup(stack, *, enabled=True, delay=.04):
    stack.enter_context(patch.multiple(config,MOCK_LLM=False,RUNTIME_HEDGE_ENABLED=enabled,
        RUNTIME_PROVIDERS=["gemini","claude","runware"],RUNTIME_TIMEOUT=15,
        GEMINI_RUNTIME_MODEL="gemini-test",CLAUDE_RUNTIME_MODEL="claude-test",RUNWARE_TEXT_MODEL="runware-test"))
    stack.enter_context(patch.object(runtime,"_HEDGE_DELAY_S",delay))
    stack.enter_context(patch.object(runtime,"_MIN_ATTEMPT_S",.003))
    traces=[];records=[]
    stack.enter_context(patch.object(usage,"trace",side_effect=lambda kind,model,**kw:traces.append((kind,model,kw,usage.current_demo.get(),usage.current_stage.get()))))
    stack.enter_context(patch.object(usage,"record",side_effect=lambda *a,**kw:records.append((a,kw,usage.current_demo.get(),usage.current_stage.get()))))
    stack.enter_context(patch.object(runtime,"_credit_wait",return_value=0))
    return traces,records

def invoke(**kw):
    return runtime.structured("Guide system","Current question",Answer,timeout_budget_s=kw.pop("timeout_budget_s",.6),cancel_event=kw.pop("cancel_event",threading.Event()),**kw)

# Disabled means existing provider order/timing and no race threads/events.
with ExitStack() as stack:
    traces,_=setup(stack,enabled=False)
    g=stack.enter_context(patch.object(gemini,"text_structured",return_value=answer("primary")))
    c=stack.enter_context(patch.object(claude,"structured"));w=stack.enter_context(patch.object(runware,"structured"))
    out=invoke(timeout_budget_s=12)
    check("Flag-off dispatch retains sequential primary cap and provider metadata",out.answer=="primary" and out._runtime_provider=="gemini" and g.call_args.kwargs["timeout_s"]==7 and not c.called and not w.called)
    check("Flag-off emits no hedge events",not any(t[0]=="runtime-hedge" for t in traces))

with ExitStack() as stack:
    traces,_=setup(stack)
    g=stack.enter_context(patch.object(gemini,"text_structured",return_value=answer("legacy")))
    c=stack.enter_context(patch.object(claude,"structured"))
    out=runtime.structured("System","Question",Answer,timeout_budget_s=12)
    check("A legacy caller without a turn-cancellation token never starts a race",out.answer=="legacy" and not c.called and not any(t[0]=="runtime-hedge" for t in traces))

with ExitStack() as stack:
    traces,_=setup(stack)
    g=stack.enter_context(patch.object(gemini,"text_structured",return_value=answer("fast primary")))
    c=stack.enter_context(patch.object(claude,"structured"));w=stack.enter_context(patch.object(runware,"structured"))
    out=invoke(timeout_budget_s=12,trace_context={"session_id":"s1","turn_id":"t1","phase":"reason"})
    check("Fast primary never launches fallback and still has7s local cap",out.answer=="fast primary" and g.call_args.kwargs["timeout_s"]==7 and not c.called and not w.called)
    check("Winner metadata stays outside the declared schema",out.model_dump()=={"answer":"fast primary"} and out._runtime_call_id.startswith("rh_"))
    events=[json.loads(t[2]["response"]) for t in traces if t[0]=="runtime-hedge"]
    check("Race events retain call and turn identity",events and all(e["session_id"]=="s1" and e["turn_id"]=="t1" and e["call_id"]==out._runtime_call_id for e in events))

# A5–7s primary success (scaled delay here) remains eligible after fallback began.
with ExitStack() as stack:
    traces,_=setup(stack)
    fallback_entered=threading.Event();release=threading.Event();fallback_done=threading.Event()
    def slow_primary(*a,**kw):
        assert fallback_entered.wait(.3)
        return answer("late primary wins")
    def blocked_fallback(*a,**kw):
        fallback_entered.set();release.wait(.5)
        try:raise RuntimeError("unavailable after winner")
        finally:fallback_done.set()
    g=stack.enter_context(patch.object(gemini,"text_structured",side_effect=slow_primary))
    c=stack.enter_context(patch.object(claude,"structured",side_effect=blocked_fallback))
    w=stack.enter_context(patch.object(runware,"structured"))
    out=invoke();release.set();assert fallback_done.wait(.3);time.sleep(.015)
    check("Primary can win after hedge launch without another fallback pass",out.answer=="late primary wins" and g.call_count==1 and c.call_count==1 and not w.called)
    check("Late failed lane is observable but cannot overwrite winner",any('late_error_ignored' in t[2].get('response','') for t in traces) and out._runtime_provider=="gemini")

# A losing provider's returned usage keeps the originating Context after return.
with ExitStack() as stack:
    traces,records=setup(stack)
    release=threading.Event();done=threading.Event();history=[{"role":"user","content":"Earlier question"}]
    def blocked_primary(*a,**kw):
        release.wait(.5)
        usage.record("runtime","gemini-test",input_tokens=7,output_tokens=2)
        done.set();return answer("late primary")
    def credit_failure(*a,**kw):
        kw["history"].append({"role":"assistant","content":"private mutation"})
        raise RuntimeError("credit unavailable")
    def good_runware(*a,**kw):
        assert not kw["stop_event"].is_set()
        assert kw["history"]==history
        usage.record("runware-structured","runware-test",input_tokens=3,output_tokens=1)
        return answer("fallback wins")
    stack.enter_context(patch.object(gemini,"text_structured",side_effect=blocked_primary))
    c=stack.enter_context(patch.object(claude,"structured",side_effect=credit_failure))
    w=stack.enter_context(patch.object(runware,"structured",side_effect=good_runware))
    td=usage.current_demo.set("original-demo");ts=usage.current_stage.set("runtime")
    out=invoke(history=history)
    usage.current_demo.reset(td);usage.current_stage.reset(ts)
    td=usage.current_demo.set("later-demo")
    release.set();assert done.wait(.3);time.sleep(.015);usage.current_demo.reset(td)
    check("Delayed fallback wins with one attempt per remaining provider",out.answer=="fallback wins" and out._runtime_provider=="runware" and c.call_count==1 and w.call_count==1)
    check("Independent provider lanes cannot mutate shared history",history==[{"role":"user","content":"Earlier question"}])
    check("Late returned usage retains original demo and stage",len(records)==2 and all(r[2:]==("original-demo","runtime") for r in records))
    check("Late successful response is traced and never replaces the chosen answer",any('late_result_ignored' in t[2].get('response','') for t in traces) and out.answer=="fallback wins")

with ExitStack() as stack:
    traces,_=setup(stack,delay=.3)
    g=stack.enter_context(patch.object(gemini,"text_structured",side_effect=TimeoutError("early failure")))
    c=stack.enter_context(patch.object(claude,"structured",return_value=answer("early fallback")))
    w=stack.enter_context(patch.object(runware,"structured"))
    started=time.monotonic();out=invoke()
    check("Early primary failure starts fallback without waiting for hedge delay",time.monotonic()-started<.2 and out.answer=="early fallback" and not w.called)

for label,cancel_at in (("before_hedge",.01),("after_hedge",.06)):
    with ExitStack() as stack:
        traces,_=setup(stack);release=threading.Event();cancel=threading.Event();finished=[]
        def blocked(name):
            def f(*a,**kw):
                release.wait(.5);finished.append(name);return answer(name)
            return f
        g=stack.enter_context(patch.object(gemini,"text_structured",side_effect=blocked("gemini")))
        c=stack.enter_context(patch.object(claude,"structured",side_effect=blocked("claude")))
        w=stack.enter_context(patch.object(runware,"structured"))
        timer=threading.Timer(cancel_at,cancel.set);timer.start()
        try:invoke(cancel_event=cancel)
        except InterruptedError:cancelled=True
        else:cancelled=False
        release.set();timer.join();time.sleep(.04)
        check(label+" cancellation discards pending outputs and starts no further provider",cancelled and not w.called and (not c.called if label=="before_hedge" else c.call_count==1))

with ExitStack() as stack:
    traces,_=setup(stack)
    release=threading.Event()
    def blocked(*a,**kw):release.wait(.5);return answer("too late")
    stack.enter_context(patch.object(gemini,"text_structured",side_effect=blocked))
    stack.enter_context(patch.object(claude,"structured",side_effect=blocked))
    w=stack.enter_context(patch.object(runware,"structured"))
    started=time.monotonic()
    try:invoke(timeout_budget_s=.13)
    except TimeoutError:timed_out=True
    else:timed_out=False
    elapsed=time.monotonic()-started;release.set();time.sleep(.04)
    check("Both lanes share one hard call deadline without waiting for threads",timed_out and elapsed<.20 and not w.called)

with ExitStack() as stack:
    traces,_=setup(stack)
    stack.enter_context(patch.object(config,"RUNTIME_PROVIDERS",["gemini","claude","runware","runware"]))
    g=stack.enter_context(patch.object(gemini,"text_structured",side_effect=RuntimeError("failed")))
    c=stack.enter_context(patch.object(claude,"structured",side_effect=RuntimeError("failed")))
    w=stack.enter_context(patch.object(runware,"structured",side_effect=RuntimeError("failed")))
    try:invoke()
    except RuntimeError:failed=True
    else:failed=False
    check("Failure and duplicated configuration never start a second fallback chain",failed and g.call_count==c.call_count==w.call_count==1)

with ExitStack() as stack:
    traces,_=setup(stack)
    stack.enter_context(patch.object(runtime,"_credit_wait",return_value=30))
    stack.enter_context(patch.object(gemini,"text_structured",side_effect=RuntimeError("failed")))
    c=stack.enter_context(patch.object(claude,"structured"))
    w=stack.enter_context(patch.object(runware,"structured",return_value=answer("skip credit")))
    out=invoke()
    check("Existing explicit-credit cooldown skips only that provider",out.answer=="skip credit" and not c.called and w.call_count==1 and any('credit_cooldown_skip' in t[2].get('response','') for t in traces))

# Simultaneous structured completions still have exactly one elected owner.
with ExitStack() as stack:
    traces,_=setup(stack);stack.enter_context(patch.object(config,"RUNTIME_PROVIDERS",["gemini","claude"]))
    barrier=threading.Barrier(2);done=threading.Event()
    def first(*args,**kwargs):barrier.wait(.3);return answer("gemini")
    def second(*args,**kwargs):barrier.wait(.3);done.set();return answer("claude")
    stack.enter_context(patch.object(gemini,"text_structured",side_effect=first));stack.enter_context(patch.object(claude,"structured",side_effect=second))
    out=invoke();assert done.wait(.2);time.sleep(.02)
    events=[json.loads(t[2]["response"]) for t in traces if t[0]=="runtime-hedge"]
    check("Simultaneous completions elect one winner and ignore the other",sum(e["event"]=="winner" for e in events)==1 and sum(e["event"]=="late_result_ignored" for e in events)==1 and out.answer==out._runtime_provider)

with ExitStack() as stack:
    traces,_=setup(stack)
    stack.enter_context(patch.object(gemini,"text_structured",return_value={"answer":"not validated schema"}))
    stack.enter_context(patch.object(claude,"structured",return_value=answer("validated fallback")))
    out=invoke()
    check("First raw object cannot beat a schema-valid structured completion",out.answer=="validated fallback" and out._runtime_provider=="claude")

with ExitStack() as stack:
    setup(stack);cancel=threading.Event();cancel.set()
    g=stack.enter_context(patch.object(gemini,"text_structured"));c=stack.enter_context(patch.object(claude,"structured"));w=stack.enter_context(patch.object(runware,"structured"))
    try:invoke(cancel_event=cancel)
    except InterruptedError:stopped=True
    else:stopped=False
    check("An already cancelled turn starts no provider lane",stopped and not g.called and not c.called and not w.called)

# Scheduled dispatch races: the launch trace is preparation, not permission to
# send a paid request after another lane wins while that trace is blocked.
with ExitStack() as stack:
    traces,_=setup(stack)
    entered=threading.Event();winner=threading.Event();blocked_threads=[]
    capture=usage.trace
    def delayed_launch(kind,model,**kw):
        capture(kind,model,**kw)
        event=json.loads(kw["response"])["event"] if kind=="runtime-hedge" else ""
        if event=="launch" and model=="claude":
            blocked_threads.append(threading.current_thread());entered.set()
            assert winner.wait(.4)
        if event=="winner" and model=="gemini":winner.set()
    stack.enter_context(patch.object(usage,"trace",side_effect=delayed_launch))
    def win_during_trace(*args,**kwargs):
        assert entered.wait(.3)
        return answer("won during fallback launch logging")
    stack.enter_context(patch.object(gemini,"text_structured",side_effect=win_during_trace))
    c=stack.enter_context(patch.object(claude,"structured"));w=stack.enter_context(patch.object(runware,"structured"))
    out=invoke()
    for worker in blocked_threads:worker.join(.3)
    check("Winner during fallback launch trace prevents late paid dispatch",winner.is_set() and out._runtime_provider=="gemini" and not c.called and not w.called and all(not t.is_alive() for t in blocked_threads))

# A customer's history may have a slow deep copy. Win/cancel/deadline during
# that preparation must all prevent the eventual fallback adapter call.
for outcome in ("winner","cancel","deadline"):
    with ExitStack() as stack:
        traces,_=setup(stack)
        copying=threading.Event();release=threading.Event();winner=threading.Event();cancel=threading.Event()
        workers=[];copies=[];copy_lock=threading.Lock()
        class SlowHistory(list):
            def __deepcopy__(self,memo):
                with copy_lock:
                    copies.append(threading.current_thread())
                    is_fallback=len(copies)==2
                if is_fallback:
                    workers.append(threading.current_thread());copying.set()
                    assert (winner if outcome=="winner" else release).wait(.4)
                return [dict(item) for item in self]
        capture=usage.trace
        def observe_winner(kind,model,**kw):
            capture(kind,model,**kw)
            if kind=="runtime-hedge" and json.loads(kw["response"])["event"]=="winner":winner.set()
        stack.enter_context(patch.object(usage,"trace",side_effect=observe_winner))
        def primary_during_copy(*args,**kwargs):
            workers.append(threading.current_thread())
            assert copying.wait(.3)
            if outcome=="cancel":cancel.set()
            if outcome!="winner":assert release.wait(.4)
            return answer("primary")
        stack.enter_context(patch.object(gemini,"text_structured",side_effect=primary_during_copy))
        c=stack.enter_context(patch.object(claude,"structured"));w=stack.enter_context(patch.object(runware,"structured"))
        result=None;failure=None
        try:result=invoke(history=SlowHistory([{"role":"user","content":"Earlier input"}]),cancel_event=cancel,timeout_budget_s=.13 if outcome=="deadline" else .6)
        except (InterruptedError,TimeoutError) as exc:failure=exc
        finally:
            release.set()
            for worker in workers:worker.join(.3)
        expected=(result is not None and result._runtime_provider=="gemini") if outcome=="winner" else isinstance(failure,InterruptedError if outcome=="cancel" else TimeoutError)
        check("History preparation observes "+outcome+" before fallback dispatch",copying.is_set() and expected and not c.called and not w.called and all(not t.is_alive() for t in workers))

with ExitStack() as stack:
    traces,_=setup(stack)
    stack.enter_context(patch.object(config,"RUNTIME_PROVIDERS",["gemini","claude"]))
    release=threading.Event();workers=[];copies=[];sent=[]
    class BudgetHistory(list):
        def __deepcopy__(self,memo):
            copies.append(threading.current_thread())
            if len(copies)==2:threading.Event().wait(.065)
            return [dict(item) for item in self]
    def pending_primary(*args,**kwargs):
        workers.append(threading.current_thread());assert release.wait(.4)
        return answer("late")
    def prepared_fallback(*args,**kwargs):
        sent.append(kwargs["timeout"])
        return answer("remaining budget")
    stack.enter_context(patch.object(gemini,"text_structured",side_effect=pending_primary))
    stack.enter_context(patch.object(claude,"structured",side_effect=prepared_fallback))
    out=invoke(history=BudgetHistory([{"role":"user","content":"History"}]))
    release.set()
    for worker in workers:worker.join(.3)
    launch=next(json.loads(t[2]["response"]) for t in traces if t[0]=="runtime-hedge" and t[1]=="claude" and json.loads(t[2]["response"])["event"]=="launch")
    check("Slow history preparation is deducted from the adapter timeout",out._runtime_provider=="claude" and len(sent)==1 and .003<sent[0]<launch["timeout_ms"]/1000-.04)

# Real Runware adapter: a completed but lost invalid generation must be accounted
# once and must never trigger its otherwise-allowed second JSON repair request.
for output in ('not json',Answer(answer="late valid").model_dump_json()):
    with ExitStack() as stack:
        traces,records=setup(stack);stack.enter_context(patch.object(config,"RUNWARE_API_KEY","synthetic-test-key"));stop=threading.Event()
        def post(task,timeout):
            stop.set()
            return httpx.Response(200,json={"data":[{"taskType":"textInference","taskUUID":task["taskUUID"],"model":task["model"],"finishReason":"stop","text":output,"usage":{"promptTokens":10,"completionTokens":5},"cost":.01}]},request=httpx.Request("POST",runware.ENDPOINT))
        post_mock=stack.enter_context(patch.object(runware,"_post",side_effect=post))
        try:runware.structured("System","Question",Answer,stop_event=stop)
        except runware.RunwareError as exc:lost="after cancellation" in str(exc)
        else:lost=False
        check("Lost Runware generation retains usage but cannot publish or JSON-repair: "+output[:8],lost and post_mock.call_count==1 and len(records)==1)

with ExitStack() as stack:
    _,records=setup(stack);stack.enter_context(patch.object(config,"RUNWARE_API_KEY","synthetic-test-key"));stop=threading.Event();stop.set()
    post=stack.enter_context(patch.object(runware,"_post"))
    try:runware.structured("System","Question",Answer,stop_event=stop)
    except runware.RunwareError:stopped=True
    else:stopped=False
    check("Already lost Runware lane does not send its first request",stopped and not post.called and not records)

check("The experimental flag is off in the current environment",not config.RUNTIME_HEDGE_ENABLED)
print(f"{len(checks)}/{len(checks)} hedge contracts passed")
for name in checks:print("PASS",name)

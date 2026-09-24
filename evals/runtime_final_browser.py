"""Bounded real paid browser visit, invoked only by runtime_final_qa.py.

No model/audio fixtures, speech injection, shortened timers or accelerated media.
Muted output uses the real recordings and streaming transport; physical capture
is disabled. This proves delivery/flow, not acoustic noise rejection or STT.
"""
import json
import time
from urllib.parse import urlsplit


def run(journey):
    from playwright.sync_api import sync_playwright, TimeoutError as BrowserTimeout
    from runtime_final_qa import BASE, WORK, save
    journey.guard(); journey.once("browser")
    evidence = WORK / "browser"
    evidence.mkdir(exist_ok=True)
    checks, errors, saves, answers, wire = [], [], [], [], []
    counters = {"reasoning":0,"speech":0}
    started = time.monotonic()

    def check(label, ok, detail=None):
        checks.append({"name":label,"passed":bool(ok),"detail":detail})
        print(("PASS " if ok else "FAIL ")+label, flush=True)
        assert ok, label

    def guard(kind):
        journey.guard()
        assert time.monotonic()-started < 720, "One browser visit exceeded twelve minutes"
        limit = {"reasoning":4,"speech":32}[kind]
        assert counters[kind] < limit, "Bounded runtime request count reached"
        counters[kind] += 1

    observer = """
  window.__finalQaSnapshot = () => ({playback:{...S.playback}, session:sessionRecord(),
    waiting:!!S.waiter, speaking:S.speaking?{text:S.speaking.text,startedAt:S.speaking.startedAt}:null,
    pending:!!live?.pending, inConversation:!!S.conversationOrigin, mic:!!live?.mic,
    narratingRoute:!!S.speaking?.startedAt && (S.plan[S.seg]?.slide.lines||[]).some(line=>line.text===S.speaking.text),
    sectionCount:S.plan.filter((step,i)=>topicOf(step.slide)!==topicOf(S.plan[i+1]?.slide||{})).length,
    leadOpen:el.lead.classList.contains('open')});
"""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            headless=True, args=["--mute-audio","--autoplay-policy=no-user-gesture-required","--disable-background-networking"])
        context = browser.new_context(viewport={"width":1440,"height":1000})
        context.add_init_script("""window.__micAttempts=0;navigator.mediaDevices.getUserMedia=async()=>{window.__micAttempts++;throw Error('Physical microphone is disabled for final QA');};""")

        def route_http(route):
            request = route.request
            if urlsplit(request.url).netloc != "127.0.0.1:8910":
                route.abort(); return
            if request.method == "POST" and request.url.endswith("/run/lead"):
                errors.append("Unexpected lead submission"); route.abort(); return
            try:
                if request.method == "POST" and request.url.endswith(("/run/pitch","/run/qa")):
                    guard("reasoning")
                elif request.method == "POST" and request.url.endswith("/run/tts"):
                    guard("speech")
            except Exception as error:
                errors.append(str(error)); route.abort(); return
            if urlsplit(request.url).path == "/web/player/player.js":
                response = route.fetch()
                source = response.text()
                anchor = "  return { destroy, restart, pause, context };"
                assert source.count(anchor) == 1
                route.fulfill(response=response, body=source.replace(anchor,observer+anchor)); return
            if request.method == "POST" and request.url.endswith("/run/session"):
                saves.append(request.post_data_json)
            route.continue_()

        def route_socket(route):
            server = route.connect_to_server()
            def outbound(raw):
                try:
                    body = json.loads(raw)
                    if body.get("type") == "turn.ask": guard("reasoning")
                    elif body.get("type") in {"delivery.request","delivery.speak"}: guard("speech")
                    if body.get("type") == "audio.input": raise AssertionError("No capture in final QA")
                    wire.append({"direction":"out", **{k:v for k,v in body.items() if k not in {"audio","history"}}})
                    server.send(raw)
                except Exception as error:
                    errors.append(str(error)); route.close(code=1000,reason="Acceptance request bound")
            def inbound(raw):
                body = json.loads(raw)
                if body.get("type") == "turn.result": answers.append(body)
                wire.append({"direction":"in", **{k:v for k,v in body.items() if k != "audio"}})
                route.send(raw)
            route.on_message(outbound)
            server.on_message(inbound)

        context.route("**/*",route_http)
        context.route_web_socket("**/run/live*",route_socket)
        page = context.new_page()
        page.on("pageerror",lambda error:errors.append(str(error)))

        def wait(predicate, seconds=45):
            deadline = time.monotonic()+seconds
            while time.monotonic() < deadline:
                try:
                    return page.wait_for_function(predicate,timeout=min(1000,max(1,int((deadline-time.monotonic())*1000))))
                except BrowserTimeout:
                    pass
            raise AssertionError("Timed out: "+predicate)

        def submit(text):
            field = page.get_by_role("textbox",name="Your question or answer",exact=True)
            field.fill(text); field.press("Enter")

        try:
            page.goto(BASE+f"/?mute=1&presentation=walkthrough#/play/{journey.did}")
            page.get_by_role("button",name="Explore with me",exact=True).wait_for()
            page.screenshot(path=str(evidence / "welcome.png"))
            page.get_by_role("button",name="Explore with me",exact=True).click()
            intake = page.get_by_role("textbox",name="Your answer",exact=True)
            intake.fill("show me around"); intake.press("Enter")
            wait("__finalQaSnapshot().playback.phase==='route' && __finalQaSnapshot().speaking",90)
            snapshot = page.evaluate("__finalQaSnapshot()")
            sid = snapshot["session"]["id"]
            page.screenshot(path=str(evidence / "guided-route.png"))
            check("generic intake uses a tour acknowledgement without invented preferences",
                  not snapshot["session"]["profile"].get("why") and
                  any("Let me take you through" in row.get("text","") for row in snapshot["session"]["transcript"]) and
                  not any("helps me focus" in row.get("text","") for row in snapshot["session"]["transcript"]))
            check("visit is checkpointed before its ending",bool(journey.api("GET","sessions/"+sid)["transcript"]))
            prior = len(answers)
            submit(journey.args.question)
            wait("__finalQaSnapshot().session.questions.length>0 && !__finalQaSnapshot().pending",60)
            deadline = time.monotonic()+60
            while len(answers) <= prior and time.monotonic()<deadline: page.wait_for_timeout(100)
            answer = answers[-1]["answer"] if len(answers)>prior else {}
            check("typed question returns a validated, cited answer through real live transport",
                  answer.get("answered") and bool(answer.get("fact_ids")), answer)
            page.screenshot(path=str(evidence / "question-answer.png"))
            wait("!__finalQaSnapshot().inConversation && !__finalQaSnapshot().pending && !__finalQaSnapshot().waiting && __finalQaSnapshot().playback.phase==='route' && __finalQaSnapshot().narratingRoute",60)
            check("answered question resumes the tour without a blocking lead form",not page.evaluate("__finalQaSnapshot().leadOpen"))
            # Natural narration and the new three-second section windows continue
            # without clicking Continue, skipping slides or speeding up recordings.
            closing_deadline = min(time.monotonic()+540,started+720)
            while time.monotonic() < closing_deadline:
                try:
                    page.get_by_role("button",name="Not yet",exact=True).wait_for(timeout=10000)
                    break
                except BrowserTimeout:
                    print(json.dumps({"phase":"natural_tour", "seconds":round(time.monotonic()-started),
                                      "playback":page.evaluate("__finalQaSnapshot().playback")}),flush=True)
            else:
                raise AssertionError("Natural tour did not reach closing within its bounded visit")
            page.screenshot(path=str(evidence / "natural-closing.png"))
            check("natural full tour reaches closing and customer CTA choices",bool(page.locator(".pl-chips button").count()))
            final_snapshot = page.evaluate("__finalQaSnapshot()")
            prompts = sum(row.get("text")=="Anything you'd like to know about what we've just covered?"
                          for row in final_snapshot["session"]["transcript"])
            check("every completed section asks for customer questions",final_snapshot["sectionCount"] > 0 and
                  prompts >= final_snapshot["sectionCount"], {"prompts":prompts,"sections":final_snapshot["sectionCount"]})
            check("no page overflow at closing",page.evaluate("document.documentElement.scrollWidth<=window.innerWidth+1"))
            page.get_by_role("button",name="Not yet",exact=True).click()
            page.get_by_role("heading",name="Your recap",exact=True).wait_for(timeout=45000)
            deadline = time.monotonic()+10
            saved = {}
            while time.monotonic()<deadline:
                saved = journey.api("GET","sessions/"+sid)
                if saved.get("ended"): break
                page.wait_for_timeout(200)
            check("final session retains typed question and closing transcript",saved.get("ended") and
                  any(row.get("text")==journey.args.question for row in saved.get("transcript",[])))
            check("incremental and final saves both occurred",any(not row.get("ended") for row in saves) and any(row.get("ended") for row in saves))
            check("physical microphone was never requested",page.evaluate("__micAttempts") == 0)
            check("browser and request-budget handlers have no errors",not errors,errors)
            page.screenshot(path=str(evidence / "saved-recap.png"))
            save("browser-saved-session.json",saved)
        except Exception:
            page.screenshot(path=str(evidence / "failure.png"))
            raise
        finally:
            save("browser-results.json",{"checks":checks,"errors":errors,"counters":counters,
                 "seconds":round(time.monotonic()-started,2),"wire":wire,"save_count":len(saves),
                 "boundary":"Real app/providers, muted natural-speed playback, read-only observation hook, no microphone or acoustic claim."})
            context.close(); browser.close()
    journey.record["browser_checks"] = checks
    journey.persist(); journey.guard()

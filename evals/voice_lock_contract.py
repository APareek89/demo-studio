"""Free locked-speaker recovery and Sarvam rate-limit contracts. No live calls."""
from __future__ import annotations

import base64
import copy
import sys
import tempfile
from contextlib import ExitStack
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def run(check, _demo_id=None):
    from server import config, store
    from server.agents import voice
    from server.llm import mock, sarvam

    wav = mock.silent_wav(0.1)
    gcloud_impl = voice._gcloud
    with tempfile.TemporaryDirectory(prefix="voice-lock-") as tmp, ExitStack() as stack:
        stack.enter_context(patch.multiple(config, DATA_DIR=Path(tmp), MOCK_LLM=False, SARVAM_API_KEY="test-only", GEMINI_API_KEY="test-only", GCLOUD_TTS_API_KEY="test-only"))
        blocked = [stack.enter_context(patch(name, side_effect=AssertionError("Unexpected outbound call")))
                   for name in ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex")]
        stack.enter_context(patch.object(voice, "_TRIPPED", {}))
        stack.enter_context(patch.object(voice, "VOICE_WORKERS", 1))
        stack.enter_context(patch.object(voice, "FILLERS", {"ack":"Thanks for sharing.", "hold":"One moment, please."}))
        gemini = stack.enter_context(patch.object(voice.gemini, "tts", side_effect=AssertionError("Unexpected Gemini voice")))
        cloud = stack.enter_context(patch.object(voice, "_gcloud", side_effect=AssertionError("Unexpected Cloud voice")))
        demo = store.new_demo("Voice fixture"); did = demo["id"]
        store.update(did, lambda d:d["settings"].update(tts_provider="sarvam", voice_locked=True, sarvam_speaker="priya", language="en-IN"))
        demo = store.load(did)
        store.write_json(did, "plan.json", {"voice":{}, "segments":[]})
        def cache(text, provider="sarvam", speaker="priya", lang="en-IN"):
            rel = f"audio/{voice._cache_key(provider, speaker, lang, text)}.wav"
            path = store.path(did, rel); path.parent.mkdir(exist_ok=True); path.write_bytes(wav)
            return rel
        main = "Explore the cabin."
        cached = cache(main)
        voice._TRIPPED["sarvam"] = (10**12, "temporary rate limit")
        with patch.object(voice.sarvam, "tts", side_effect=AssertionError("Cache should avoid speech")) as call:
            rel = voice.render_line(did, main, strict=True)
        check("voice lock: the chosen cache remains usable during a transient breaker", rel == cached and not call.called)
        with patch.object(config, "SARVAM_API_KEY", None):
            rel = voice.render_line(did, main)
            check("voice lock: missing selected key does not select a configured fallback or hide cached Priya", voice.provider_chain(demo) == ["sarvam"] and rel == cached)
        foreign = cache("Other language text.", lang="hi-IN")
        try:
            voice.render_line(did, "Other language text.")
        except RuntimeError as exc:
            check("voice lock: foreign-language cache cannot satisfy the chosen identity", "locked voice sarvam/priya" in str(exc) and foreign.endswith(".wav"))
        else:
            check("voice lock: foreign-language cache cannot satisfy the chosen identity", False)
        voice._TRIPPED.clear()

        script = {"intake_q1":"What matters to you?", "intake_q2":"", "intake_audio":{}, "closing":[{"id":"close", "text":"Choose your next step.", "fact_ids":[]}],
                  "segments":[{"id":"proof", "role":"proof", "title":"Cabin", "lines":[{"id":"line", "text":main, "fact_ids":[]}],
                               "deeper":[{"id":"deep", "text":"Take a closer look.", "fact_ids":[]}], "checkin":"Does that suit you?"}]}
        main_texts = [main, script["intake_q1"], script["closing"][0]["text"], script["segments"][0]["deeper"][0]["text"], script["segments"][0]["checkin"]]
        for text in main_texts:
            cache(text)
        for obj, key, text in ((script["segments"][0]["lines"][0], "audio", main), (script["segments"][0], "checkin_audio", script["segments"][0]["checkin"]), (script["intake_audio"], "q1", script["intake_q1"])):
            obj[key] = cache(text, "gemini", "Sulafat")
        store.write_json(did, "script.json", script)
        faq_cached, faq_mixed, faq_missing = "A reviewed FAQ answer.", "Another reviewed FAQ answer.", "A missing FAQ answer."
        for text in (faq_cached, "Thanks for sharing."):
            cache(text)
        store.write_json(did, "faq.json", {"entries":[{"id":"Q1", "answer":faq_cached, "audio":cache(faq_cached, "gemini", "Sulafat")},
                                                      {"id":"Q2", "answer":faq_mixed, "audio":cache(faq_mixed, "gemini", "Sulafat")},
                                                      {"id":"Q3", "answer":faq_missing, "audio":None}]})
        store.write_json(did, "fillers.json", {key:{"text":text, "audio":cache(text, "gemini", "Sulafat")} for key,text in voice.FILLERS.items()})
        requested = []
        def fails_once(text, speaker, lang):
            requested.append((text, speaker, lang))
            if text == faq_missing:
                raise sarvam.RateLimitError(10, "test limit")
            return wav, "wav"
        with patch.object(voice.sarvam, "tts", side_effect=fails_once):
            try:
                voice.render_script(did, lambda _message:None)
            except RuntimeError as exc:
                failed = "Voice bank incomplete" in str(exc) and "sarvam" in str(exc)
            else:
                failed = False
        check("voice lock: bank rate failure is explicit and never falls through to Gemini or Cloud", failed and not gemini.called and not cloud.called)
        saved = store.read_json(did, "script.json")
        check("voice lock: main, checkin, deeper, closing and intake reuse only matching Priya cache",
              saved["voice_provider"] == "sarvam" and saved["voice_name"] == "priya"
              and saved["segments"][0]["lines"][0]["audio"] == voice._cached(did, main, demo)
              and saved["segments"][0]["checkin_audio"] == voice._cached(did, script["segments"][0]["checkin"], demo)
              and saved["intake_audio"]["q1"] == voice._cached(did, script["intake_q1"], demo)
              and not any(text in main_texts for text, _speaker, _lang in requested))
        bank = store.read_json(did, "faq.json"); fillers = store.read_json(did, "fillers.json")
        check("voice lock: mixed FAQ/filler references are replaced or cleared and successes checkpointed",
              bank["entries"][0]["audio"] == voice._cached(did, faq_cached, demo)
              and bank["entries"][1]["audio"] == voice._cached(did, faq_mixed, demo)
              and bank["entries"][2]["audio"] is None and fillers["ack"]["audio"] == voice._cached(did, voice.FILLERS["ack"], demo)
              and fillers["hold"]["audio"] is None)
        voice._TRIPPED.clear()  # Simulate expiry; no real waiting or account request.
        requested.clear()
        with patch.object(voice.sarvam, "tts", side_effect=lambda text,speaker,lang:(requested.append((text,speaker,lang)) or (wav,"wav"))):
            voice.render_script(did, lambda _message:None)
        check("voice lock: rebuild after cooldown requests only the missing selected-speaker clips",
              sorted(text for text,_speaker,_lang in requested) == sorted([faq_missing, voice.FILLERS["hold"]])
              and all(speaker == "priya" and lang == "en-IN" for _text,speaker,lang in requested))
        check("voice lock: recovered bank and fillers contain only matching cache paths",
              all(row["audio"] == voice._cached(did, row["answer"], demo) for row in store.read_json(did, "faq.json")["entries"])
              and all(row["audio"] == voice._cached(did, row["text"], demo) for row in store.read_json(did, "fillers.json").values()))
        with patch.object(voice.sarvam, "tts", side_effect=AssertionError("Complete recovery should be cache-only")) as call:
            voice.render_script(did, lambda _message:None)
        check("voice lock: a complete repeat build performs no synthesis", not call.called)

        script["segments"][0]["lines"] = [{"id":f"bad{n}", "text":f"Missing statement {n}.", "fact_ids":[]} for n in range(5)] + [{"id":"cached", "text":main, "fact_ids":[]}]
        store.write_json(did, "script.json", script)
        with patch.object(voice.sarvam, "tts", side_effect=sarvam.RateLimitError(10,"test limit")) as call:
            try:
                voice._render_one(did, lambda _message:None, demo, "script.json", None)
            except RuntimeError as exc:
                failed = "Locked voice sarvam/priya incomplete" in str(exc)
            else:
                failed = False
        check("voice lock: missing main narration fails before bundle while later cached clips survive stop",
              failed and call.call_count == 1 and store.read_json(did,"script.json")["segments"][0]["lines"][-1]["audio"] == cached)
        voice._TRIPPED.clear()
        gdemo = copy.deepcopy(demo); gdemo["settings"].update(tts_provider="gemini", voice_name="Sulafat")
        policy_script = copy.deepcopy(script); policy_script["segments"][0]["lines"] = [{"id":"policy", "text":"Policy refusal fixture.", "fact_ids":[]}]
        policy_script["segments"][0]["deeper"] = []; policy_script["segments"][0]["checkin"] = ""; policy_script["closing"] = []; policy_script["intake_q1"] = ""
        store.write_json(did,"script.json",policy_script)
        with patch.object(voice.gemini,"tts",side_effect=RuntimeError("PROHIBITED_CONTENT: policy refusal")) as refused, patch.object(voice.sarvam,"tts") as fallback:
            try:
                voice._render_one(did,lambda _message:None,gdemo,"script.json",None)
            except RuntimeError as exc:
                failed = "policy" in str(exc).lower()
            else:
                failed = False
        check("voice lock: Gemini policy refusal is explicit, called once and never sent to another provider", failed and refused.call_count == 1 and not fallback.called)
        gdemo["settings"]["voice_locked"] = False
        with patch.object(voice.gemini,"tts",side_effect=RuntimeError("Input blocked sensitive words")) as refused, patch.object(voice.sarvam,"tts") as fallback:
            try:
                voice.render_line(did,"Observed refusal fixture.",demo=gdemo)
            except voice.VoicePolicyError:
                failed=True
            else:
                failed=False
        check("voice lock: the observed sensitive-words refusal cannot bypass policy through an unlocked fallback", failed and refused.call_count==1 and not fallback.called)
        gdemo["settings"]["voice_locked"] = True
        check("voice lock: runtime strict still pins the primary provider on failure", voice.provider_chain(gdemo) == ["gemini"])
        gdemo["settings"]["tts_provider"] = "gcloud"
        with patch.object(config,"MOCK_LLM",True), patch.object(voice,"_gcloud",gcloud_impl), patch.object(voice.httpx,"Client",side_effect=AssertionError("Mock Cloud TTS must not construct an HTTP client")) as client:
            rel = voice.render_line(did,"Locked Cloud mock fixture.",demo=gdemo)
        check("voice lock: locked Cloud voice keeps cache identity without any HTTP in mock mode", rel == voice._cached(did,"Locked Cloud mock fixture.",gdemo) and not client.called)

        class Clock:
            def __init__(self): self.now=0.0; self.waits=[]
            def monotonic(self): return self.now
            def time(self): return 1800000000.0+self.now
            def sleep(self, delay): self.waits.append(delay); self.now+=delay
        def response(status=200, retry=None):
            return SimpleNamespace(status_code=status, headers={} if retry is None else {"Retry-After":retry}, text="test rate limit" if status==429 else "test failure",
                                   json=lambda:{"audios":[base64.b64encode(wav).decode()]})
        def scenario(responses, twice=False):
            clock=Clock(); posts=[]; rows=list(responses)
            class Client:
                def __enter__(self): return self
                def __exit__(self,*args): pass
                def post(self,_url,**kwargs): posts.append((clock.now,copy.deepcopy(kwargs["json"]))); return rows.pop(0)
            error=None
            with patch.object(sarvam,"time",clock), patch.object(sarvam,"_TTS_NEXT_REQUEST",0.0), patch.object(sarvam.httpx,"Client",return_value=Client()), patch.object(sarvam.usage,"record"), patch.object(sarvam.usage,"trace"):
                try:
                    sarvam.tts("Unchanged request text.","priya","en-IN")
                    if twice: sarvam.tts("Second request text.","priya","en-IN")
                except RuntimeError as exc: error=exc
            return clock,posts,error
        clock,posts,error=scenario([response(),response()],True)
        check("sarvam pacing: consecutive calls share conservative request spacing", error is None and posts[1][0]-posts[0][0] >= 2.1)
        clock,posts,error=scenario([response(429,"5"),response()])
        check("sarvam pacing: 429 honors numeric Retry-After with identical text and speaker", error is None and len(posts)==2 and posts[1][0]>=5 and posts[0][1]==posts[1][1])
        date=format_datetime(datetime.fromtimestamp(1800000007,timezone.utc),usegmt=True)
        clock,posts,error=scenario([response(429,date),response()])
        check("sarvam pacing: 429 honors an HTTP-date Retry-After", error is None and posts[1][0]>=7)
        clock,posts,error=scenario([response(429,"not a date"),response()])
        check("sarvam pacing: malformed Retry-After uses bounded backoff", error is None and len(posts)==2 and 2 <= posts[1][0] <= 3)
        clock,posts,error=scenario([response(429),response(429),response(429)])
        check("sarvam pacing: persistent429 stops after three attempts with an explicit shared cooldown", isinstance(error,sarvam.RateLimitError) and len(posts)==3 and error.retry_after>=8 and sum(clock.waits)<30)
        clock,posts,error=scenario([response(429,"120")])
        check("sarvam pacing: a long Retry-After is retained without waiting or retrying early", isinstance(error,sarvam.RateLimitError) and len(posts)==1 and error.retry_after>=120 and clock.waits==[])
        for status in (400,401,402,403,500,503):
            clock,posts,error=scenario([response(status)])
            check(f"sarvam pacing: HTTP{status} is not treated as a429 retry", error is not None and len(posts)==1 and clock.waits==[])
        check("voice lock: all contracts avoid outbound requests", not any(item.called for item in blocked))


if __name__ == "__main__":
    sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
    rows=[]
    def check(name,ok,detail=""):
        rows.append(bool(ok)); print(("PASS " if ok else "FAIL ")+name+(" — "+detail if detail else ""))
    run(check)
    print(f"Voice lock contracts: {sum(rows)}/{len(rows)}")
    raise SystemExit(0 if all(rows) else 1)

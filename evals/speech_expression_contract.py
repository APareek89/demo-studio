"""Free expressive-delivery contracts: real adapter assembly, fake transports, blocked sockets."""
from __future__ import annotations

import asyncio
import base64
import copy
import hashlib
import json
import os
import sys
import tempfile
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run(check):
    with tempfile.TemporaryDirectory(prefix="speech-expression-") as tmp, ExitStack() as stack:
        root = Path(tmp)
        stack.enter_context(patch.dict(os.environ, {"MOCK_LLM": "1", "CLOUD_SYNC": "0", "STORAGE_BACKEND": "local",
            "DEMO_STUDIO_DATA": str(root / "data"), "DEMO_STUDIO_GRAPH_DB": str(root / "graph.sqlite")}))
        from server import config, store
        from server.agents import narration, speech_style, voice
        from server.llm import mock, sarvam, sarvam_stream
        from server.runtime_delivery import DeliveryCoordinator
        stack.enter_context(patch.multiple(config, MOCK_LLM=True, DATA_DIR=root / "data", GRAPH_DB=root / "graph.sqlite",
            SARVAM_TTS_MODEL="bulbul:v3", SARVAM_API_KEY="test-only"))
        blocked = [stack.enter_context(patch(name, side_effect=AssertionError("No outbound socket"))) for name in
            ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex")]
        stack.enter_context(patch.object(voice, "_TRIPPED", {}))
        stack.enter_context(patch.object(sarvam.usage, "record"))
        stack.enter_context(patch.object(sarvam.usage, "trace"))
        plain = {"tone": "warm", "pace": 1.0}
        styled = {**plain, "expressiveness": .7}
        check("optional expression preserves the exact legacy normalized shape", speech_style.normalize() == plain
              and speech_style.normalize(plain) == plain and speech_style.prepare("Hello.", plain) ==
              {"text": "Hello.", "plain_text": "Hello.", "pace": 1.0})
        check("numeric expression is retained and conservatively bounded", speech_style.normalize(styled) == styled
              and speech_style.normalize({"expressiveness": -10})["expressiveness"] == .5
              and speech_style.normalize({"expressiveness": 10})["expressiveness"] == .8)
        bad = [None, True, False, "0.7", {}, [], float("nan"), float("inf"), -float("inf"), 10**1000]
        check("invalid expression is omitted rather than creating arbitrary provider controls",
              all("expressiveness" not in speech_style.normalize({"expressiveness": value}) for value in bad))
        prepared = speech_style.prepare("[upbeat] Hello. <emphasis>Look here.</emphasis>", styled)
        check("expression never enters the spoken words or changes pace", prepared ==
              {"text": "Hello. Look here.", "plain_text": "Hello. Look here.", "pace": 1.0, "expressiveness": .7})

        wav = mock.silent_wav(.25)
        posts = []
        class Client:
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def post(self, url, **kwargs):
                posts.append(copy.deepcopy(kwargs["json"]))
                return SimpleNamespace(status_code=200, headers={}, text="", json=lambda:
                    {"audios": [base64.b64encode(wav).decode()]})
        # Execute real HTTP request assembly only under a fake Client and blocked
        # sockets. No provider credential, request or paid probe is used.
        with patch.object(sarvam.httpx, "Client", return_value=Client()), patch.object(sarvam, "_tts_slot"), patch.object(config, "MOCK_LLM", False):
            sarvam.tts("Reviewed words.", "sumit", "en-IN")
            legacy_body = posts[-1]
            audio, ext = sarvam.tts("Reviewed words.", "sumit", "en-IN", temperature=.7)
            expressive_body = posts[-1]
            check("actual REST default payload keeps temperature absent", "temperature" not in legacy_body
                  and legacy_body["speaker"] == "sumit" and legacy_body["model"] == "bulbul:v3")
            check("actual REST forwards only selected temperature with unchanged words and voice",
                  expressive_body == {**legacy_body, "temperature": .7} and audio == wav and ext == "wav"
                  and not {"pitch", "loudness", "ssml", "expression"} & expressive_body.keys())
            before = len(posts)
            rejected = []
            for value in [True, "0.7", float("nan"), float("inf"), 0, 1.01]:
                try: sarvam.tts("Reviewed words.", "sumit", "en-IN", temperature=value)
                except ValueError: rejected.append(value)
            check("direct adapter rejects invalid temperature before HTTP", len(rejected) == 6 and len(posts) == before)
            with patch.object(config, "SARVAM_TTS_MODEL", "bulbul:v2"):
                try: sarvam.tts("Reviewed words.", "sumit", "en-IN", temperature=.7)
                except ValueError: refused_legacy = True
                else: refused_legacy = False
            check("unsupported older models never receive v3 temperature", refused_legacy and len(posts) == before)

        messages = []
        class Socket:
            def __init__(self): self.events = [
                {"type": "audio", "data": {"audio": base64.b64encode(b"\0\0" * 240).decode()}},
                {"type": "event", "data": {"event_type": "final"}}]
            async def __aenter__(self): return self
            async def __aexit__(self, *_): pass
            async def send(self, message): messages.append(json.loads(message))
            async def recv(self): return json.dumps(self.events.pop(0))
        async def adapter_stream():
            with patch.object(sarvam_stream.websockets, "connect", side_effect=lambda *a, **kw: Socket()), patch.object(config, "MOCK_LLM", False):
                first = [chunk async for chunk in sarvam_stream.stream_tts("Reviewed words.", "sumit", "en-IN")]
                default_config = copy.deepcopy(messages[0]["data"])
                messages.clear()
                second = [chunk async for chunk in sarvam_stream.stream_tts("Reviewed words.", "sumit", "en-IN", temperature=.7)]
                expression_config = messages[0]["data"]
                check("actual streaming defaults omit expression while preserving Sumit and pace",
                      "temperature" not in default_config and default_config["speaker"] == "sumit" and default_config["pace"] == 1)
                check("actual streaming forwards the same optional temperature and valid PCM",
                      expression_config == {**default_config, "temperature": .7} and first == second
                      and first[0]["sample_rate"] == 24000 and first[0]["format"] == "pcm_s16le"
                      and not {"pitch", "loudness", "ssml"} & expression_config.keys())
        asyncio.run(adapter_stream())

        demo = store.new_demo("Expression fixture"); did = demo["id"]
        store.update(did, lambda d: d["settings"].update(tts_provider="sarvam", sarvam_speaker="sumit", voice_locked=True, language="en-IN"))
        persona = {"persona_description": "A composed product guide", "tone": "warm"}
        store.write_json(did, "plan.json", {"voice": persona})
        demo = store.load(did)
        text = "The reviewed cabin offers a panoramic glass roof."
        old_identity = f"sarvam|sumit|en-IN|{text}|delivery-v1|" + json.dumps({"delivery": plain, "persona": persona}, sort_keys=True, ensure_ascii=False)
        old_key = hashlib.sha1(old_identity.encode()).hexdigest()[:20]
        old_path = store.path(did, "audio", f"{old_key}.wav"); old_path.parent.mkdir(exist_ok=True); old_path.write_bytes(wav)
        calls = []
        def render(text, speaker, language, **kwargs):
            calls.append((text, speaker, language, kwargs)); return wav, "wav"
        with patch.object(sarvam, "tts", side_effect=render), patch.object(voice.gemini, "tts", side_effect=AssertionError("Locked provider changed")), patch.object(voice, "_gcloud", side_effect=AssertionError("Locked provider changed")):
            legacy = voice.render_line(did, text, delivery=plain)
            check("existing default cache remains byte-compatible without a synthesis call", legacy == f"audio/{old_key}.wav" and not calls)
            first = voice.render_line(did, text, delivery=styled)
            same = voice.render_line(did, text, delivery=styled)
            different = voice.render_line(did, text, delivery={**styled, "expressiveness": .8})
            check("effective expression changes recordings while repeats reuse exact cached audio",
                  first == same and different != first != legacy and len(calls) == 2)
            check("voice stage forwards selected expression with locked Sumit and unchanged speed",
                  all(row[:3] == (text, "sumit", "en-IN") for row in calls)
                  and [row[3] for row in calls] == [{"temperature": .7}, {"temperature": .8}])
            default_again = voice.render_line(did, text, delivery={**plain, "expressiveness": float("nan")})
            check("invalid metadata reuses the original effective default audio", default_again == legacy and len(calls) == 2)

        line = {"id": "roof-L1", "text": text, "fact_ids": ["F1"], "audio": first, "delivery": copy.deepcopy(styled)}
        script = {"segments": [{"id": "roof", "role": "proof", "lines": [line], "deeper": [], "checkin": ""}], "closing": []}
        store.write_json(did, "script.json", script)
        first_hash = voice.input_hash(did)
        script["segments"][0]["lines"][0]["delivery"]["expressiveness"] = .8
        store.write_json(did, "script.json", script)
        check("changed expression invalidates the Voice-stage input identity", voice.input_hash(did) != first_hash)
        report = narration.preparation_report(script, demo_id=did, allowed_fact_ids={"F1"}, minimum_seconds=180)
        check("expression cannot satisfy duration by estimate or metadata", report["measured"] and report["seconds"] == .25 and not report["sufficient"])

        store.write_json(did, "bundle.json", {"voice": {"provider": "sarvam", "name": "sumit", "persona": persona}})
        async def coordinator_stream():
            forwarded, delivered = [], []
            async def send(message): delivered.append(message)
            async def stream(text, **kwargs):
                forwarded.append((text, kwargs)); yield {"audio": base64.b64encode(b"\0\0" * 240).decode(), "sample_rate": 24000, "format": "pcm_s16le"}
            coordinator = DeliveryCoordinator(did, send)
            with patch.object(sarvam_stream, "stream_tts", side_effect=stream):
                for i, delivery in enumerate([None, styled]):
                    plan = {"turn_id": f"turn-{i}", "utterance_id": f"speech-{i}", "speech": text, "delivery": delivery}
                    await coordinator._stream(plan, coordinator.generation)
            check("runtime plain speech retains default controls and the published locked voice",
                  forwarded[0] == (text, {"speaker": "sumit", "language": "en-IN", "pace": 1.0}))
            check("runtime prepared metadata uses identical optional expression without changing ownership",
                  forwarded[1] == (text, {"speaker": "sumit", "language": "en-IN", "pace": 1.0, "temperature": .7})
                  and [row["utterance_id"] for row in delivered if row["type"] == "audio.end"] == ["speech-0", "speech-1"])
            saved = voice.save_streamed_clip(did, text, b"\0\0" * 240, speaker="sumit", language="en-IN", delivery=styled, demo=voice.runtime_demo(did))
            check("streamed and recorded styled audio share the same effective cache identity", saved == first)
        asyncio.run(coordinator_stream())
        check("all expression contracts use isolated storage and zero outbound sockets", not any(call.called for call in blocked))


if __name__ == "__main__":
    rows = []
    def check(name, ok):
        rows.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name)
    run(check)
    print(f"Speech expression contracts: {sum(rows)}/{len(rows)}")
    raise SystemExit(0 if all(rows) else 1)

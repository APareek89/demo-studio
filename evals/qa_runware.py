"""Free contract tests for the raw Runware TRELLIS.2 client (no network, no spend)."""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server import config, usage
from server.llm import mock, runware

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))


def client_for(*responses: httpx.Response) -> httpx.Client:
    queue = list(responses)

    def handle(request: httpx.Request) -> httpx.Response:
        response = queue.pop(0)
        response.request = request
        return response

    return httpx.Client(transport=httpx.MockTransport(handle))


with client_for(httpx.Response(400, json={"errors": [{
    "code": "insufficientCredits",
    "message": "Insufficient credits, please add your credit card and top-up your balance",
    "taskUUID": "00000000-0000-4000-8000-000000000001",
}]})) as client:
    try:
        runware._post(client, [{"taskType": "3dInference"}])
        message = "no error raised"
    except runware.RunwareAPIError as exc:
        message = str(exc)
check("400 JSON body becomes an actionable error", "insufficientCredits" in message and "Top up" in message, message)
check("generic HTTP help link is not shown", "developer.mozilla.org" not in message, message)

original_sleep = runware.time.sleep
runware.time.sleep = lambda _seconds: None
try:
    with client_for(
        httpx.Response(429, json={"errors": [{"code": "providerRateLimitExceeded", "message": "Busy"}]}),
        httpx.Response(200, json={"data": [{"status": "processing"}]}),
    ) as client:
        payload = runware._post(client, [{"taskType": "getResponse"}])
    check("transient provider response is retried", payload.get("data", [{}])[0].get("status") == "processing")
finally:
    runware.time.sleep = original_sleep

task = "00000000-0000-4000-8000-000000000002"
row = runware._task_data({"data": [
    {"taskUUID": task, "status": "processing", "progress": 80},
    {"taskUUID": task, "status": "success", "modelURL": "https://cdn.example/model.glb", "cost": 0.0123},
]}, task)
check("completed row wins over earlier processing row", row.get("status") == "success", str(row))
check("insecure asset URL is rejected", runware._find_glb_url({"modelURL": "http://cdn.example/model.glb"}) is None)
check("unrelated image URL is ignored", runware._find_glb_url({"imageURL": "https://cdn.example/image.jpg"}) is None)

original_post = runware._post
original_mock = config.MOCK_LLM
original_key = config.RUNWARE_API_KEY
try:
    config.MOCK_LLM = False
    config.RUNWARE_API_KEY = "test-only-key"
    runware._post = lambda _client, body: {"data": [{
        "taskUUID": body[0]["taskUUID"], "balance": {"amount": 0, "freeBalance": 0, "currency": "USD"}
    }]}
    try:
        runware.preflight()
        preflight_error = "no error raised"
    except runware.RunwareAPIError as exc:
        preflight_error = str(exc)
    check("zero balance is blocked before generation", "insufficientCredits" in preflight_error, preflight_error)

    runware._post = lambda _client, body: {"data": [{
        "taskUUID": body[0]["taskUUID"], "balance": {"amount": 1.0, "freeBalance": 0, "currency": "USD"}
    }]}
    check("positive balance passes preflight", bool(runware.preflight().get("available")))
finally:
    runware._post = original_post
    config.MOCK_LLM = original_mock
    config.RUNWARE_API_KEY = original_key


class FakeDownload:
    headers = {"content-length": str(len(mock.cube_glb()))}

    def raise_for_status(self) -> None:
        return None

    def iter_bytes(self):
        yield mock.cube_glb()


captured: dict[str, object] = {}


@contextmanager
def fake_stream(method: str, url: str, **kwargs):
    captured["download_method"] = method
    captured["download_url"] = url
    captured["download_headers"] = kwargs.get("headers")
    yield FakeDownload()


originals = {
    "mock": config.MOCK_LLM,
    "key": config.RUNWARE_API_KEY,
    "post": runware._post,
    "stream": httpx.stream,
    "sleep": runware.time.sleep,
    "record": usage.record,
    "trace": usage.trace,
}
try:
    config.MOCK_LLM = False
    config.RUNWARE_API_KEY = "test-only-key"
    calls = 0

    def fake_post(_client, _body):
        global calls
        calls += 1
        if calls == 1:
            return {"data": [{"taskUUID": task, "status": "processing"}]}
        return {"data": [
            {"taskUUID": task, "status": "processing", "progress": 90},
            {"taskUUID": task, "status": "success", "modelURL": "https://cdn.example/model.glb", "cost": 0.0123},
        ]}

    runware._post = fake_post
    httpx.stream = fake_stream
    runware.time.sleep = lambda _seconds: None
    usage.record = lambda *args, **kwargs: captured.update(record_usd=kwargs.get("usd"))
    usage.trace = lambda *args, **kwargs: captured.update(trace_usd=kwargs.get("usd"))
    output = runware.generate(ROOT / "samples" / "iqube" / "front.webp")
    check("successful GLB and exact cost are returned", output["bytes"][:4] == b"glTF" and output["cost"] == 0.0123)
    check("download never receives the API key", captured.get("download_headers") is None, str(captured.get("download_headers")))
    check("exact provider cost reaches usage and trace", captured.get("record_usd") == 0.0123 and captured.get("trace_usd") == 0.0123, str(captured))

    runware._post = lambda _client, _body: (_ for _ in ()).throw(
        runware.RunwareAPIError("Runware: insufficientCredits: Top up", status_code=400, codes=("insufficientCredits",))
    )
    usage.trace = lambda *args, **kwargs: captured.update(rejected_usd=kwargs.get("usd"), rejected_error=kwargs.get("error"))
    try:
        runware.generate(ROOT / "samples" / "iqube" / "front.webp")
    except runware.RunwareAPIError:
        pass
    check("rejected task records zero cost", captured.get("rejected_usd") == 0.0, str(captured.get("rejected_usd")))
finally:
    config.MOCK_LLM = originals["mock"]
    config.RUNWARE_API_KEY = originals["key"]
    runware._post = originals["post"]
    httpx.stream = originals["stream"]
    runware.time.sleep = originals["sleep"]
    usage.record = originals["record"]
    usage.trace = originals["trace"]

failed = [item for item in results if not item[1]]
for name, ok, detail in results:
    print(("✅" if ok else "❌"), name, ("— " + detail) if detail else "")
print(f"\n{len(results) - len(failed)}/{len(results)} Runware contract cases passed")
if failed:
    raise SystemExit(1)

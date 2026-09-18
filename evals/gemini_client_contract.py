"""Free cold-start singleton regression. No real SDK client or network is used."""
from __future__ import annotations

import gc
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from google import genai
from server import config
from server.llm import gemini


def main() -> int:
    results = []

    def check(name, ok):
        results.append(bool(ok))
        print(f"{'PASS' if ok else 'FAIL'} {name}")

    first_constructing, release_constructor = threading.Event(), threading.Event()
    second_called, second_constructing = threading.Event(), threading.Event()
    both_model_calls, release_models = threading.Event(), threading.Event()
    state_lock = threading.Lock()
    state = {"constructors": 0, "calls": 0, "closed": [], "options": []}

    class Transport:
        def __init__(self, identity):
            self.identity, self.closed = identity, False

    class Models:
        def __init__(self, transport):
            self.transport = transport  # Like the SDK, models do not retain Client.

        def generate_content(self):
            with state_lock:
                state["calls"] += 1
                if state["calls"] == 2:
                    both_model_calls.set()
            if not release_models.wait(3):
                raise AssertionError("Model-call test synchronization timed out")
            if self.transport.closed:
                raise RuntimeError("Cannot send a request, as the client has been closed.")
            return self.transport.identity

    class Client:
        def __init__(self, **kwargs):
            with state_lock:
                state["constructors"] += 1
                identity = state["constructors"]
                state["options"].append(kwargs)
            self.transport = Transport(identity)
            self.models = Models(self.transport)
            if identity == 1:
                first_constructing.set()
                if not release_constructor.wait(3):
                    raise AssertionError("Constructor test synchronization timed out")
            else:
                second_constructing.set()

        def __del__(self):
            self.transport.closed = True
            state["closed"].append(self.transport.identity)

    def request(second=False):
        if second:
            second_called.set()
        # Match the production expression: keep Models alive, not a local Client.
        return gemini.client().models.generate_content()

    with patch.object(config, "GEMINI_API_KEY", "fake-no-network"), patch.object(gemini, "_client", None), \
            patch.object(genai, "Client", Client), \
            patch("socket.socket.connect", side_effect=AssertionError("Network forbidden")), \
            patch("socket.create_connection", side_effect=AssertionError("Network forbidden")):
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(request)
            assert first_constructing.wait(2), "First constructor never started"
            b = pool.submit(request, True)
            assert second_called.wait(2), "Second caller never started"
            # Before the fix, this event arrives and a second client enters a
            # model call while the first constructor is still held. With the
            # lock, it stays blocked until the same client can be reused.
            second_constructing.wait(.25)
            release_constructor.set()
            assert both_model_calls.wait(2), "Both callers did not reach the model seam"
            gc.collect()
            release_models.set()
            values, errors = [], []
            for future in (a, b):
                try:
                    values.append(future.result(timeout=2))
                except Exception as error:
                    errors.append(str(error))
        check("concurrent cold callers construct exactly one SDK client", state["constructors"] == 1)
        check("both in-flight model calls retain an open transport", len(values) == 2 and not errors)
        check("both callers use the same transport", len(values) == 2 and len(set(values)) == 1)
        check("the cached client remains alive after both calls", not state["closed"])
        check("client initialization preserves configured timeout and key", all(
            options == {"api_key": "fake-no-network", "http_options": {"timeout": 90_000}}
            for options in state["options"]))

    with patch.object(config, "GEMINI_API_KEY", ""), patch.object(gemini, "_client", None), \
            patch.object(genai, "Client") as constructor:
        try:
            gemini.client()
            missing_key = False
        except RuntimeError as error:
            missing_key = "GEMINI_API_KEY is not set" in str(error)
        check("missing key fails before SDK construction", missing_key and not constructor.called)

    sentinel = object()
    with patch.object(config, "GEMINI_API_KEY", "fake-no-network"), patch.object(gemini, "_client", None), \
            patch.object(genai, "Client", side_effect=[RuntimeError("constructor failed"), sentinel]) as constructor:
        try:
            gemini.client()
        except RuntimeError:
            pass
        check("a failed constructor releases initialization for a later caller",
              gemini.client() is sentinel and gemini.client() is sentinel and constructor.call_count == 2)
    print(f"Gemini client contracts: {sum(results)}/{len(results)} (no network or paid calls)")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

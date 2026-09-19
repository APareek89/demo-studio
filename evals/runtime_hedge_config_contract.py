"""Fresh-process hedge-delay configuration and dispatch contracts; no network."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHILD = r'''
import json, socket, threading
from unittest.mock import patch

def no_network(*args, **kwargs):
    raise AssertionError("Configuration contracts must not open sockets")
socket.socket.connect = socket.socket.connect_ex = no_network
socket.create_connection = no_network
# Local developer .env must not alter the unset/default assertions.
with patch("dotenv.load_dotenv", return_value=False):
    from server import config
    from server.llm import runtime

from pydantic import BaseModel
class Answer(BaseModel):
    answer: str

health = config.health()
result = {
    "enabled": config.RUNTIME_HEDGE_ENABLED,
    "config_delay": config.RUNTIME_HEDGE_DELAY_S,
    "runtime_delay": runtime._HEDGE_DELAY_S,
    "health_delay": health["runtime_hedge_delay_s"],
    "health_enabled": health["runtime_hedge_enabled"],
}
with patch.multiple(config, MOCK_LLM=False,
                    RUNTIME_PROVIDERS=["gemini", "claude", "runware"], RUNTIME_TIMEOUT=15):
    if not config.RUNTIME_HEDGE_ENABLED:
        with patch.object(runtime.gemini, "text_structured", return_value=Answer(answer="primary")) as primary, \
             patch.object(runtime.claude, "structured") as second, \
             patch.object(runtime.runware, "structured") as third, \
             patch.object(runtime.usage, "trace"):
            answer = runtime.structured("System", "Question", Answer, timeout_budget_s=12,
                                        cancel_event=threading.Event())
            result.update(provider=answer._runtime_provider,
                          primary_timeout=primary.call_args.kwargs["timeout_s"],
                          fallback_calls=second.call_count + third.call_count)
    else:
        # Exercise the real dispatch gate, not a second copy of its arithmetic.
        # Real concurrency/deadline/cancellation is covered by runtime_hedge_contract.
        with patch.object(runtime, "_hedged", return_value=Answer(answer="hedged")) as hedged, \
             patch.object(runtime, "_sequential", return_value=Answer(answer="sequential")) as sequential:
            answer = runtime.structured("System", "Question", Answer, timeout_budget_s=4,
                                        cancel_event=threading.Event())
            result.update(dispatch=answer.answer, hedged_calls=hedged.call_count,
                          sequential_calls=sequential.call_count)
print(json.dumps(result))
'''


def fresh(delay: str | None, *, enabled: bool = False):
    with tempfile.TemporaryDirectory(prefix="hedge-config-") as temp:
        env = os.environ.copy()
        env.update(MOCK_LLM="1", CLOUD_SYNC="0", STORAGE_BACKEND="local",
                   DEMO_STUDIO_DATA=str(Path(temp) / "demos"),
                   DEMO_STUDIO_GRAPH_DB=str(Path(temp) / "graph.sqlite"), PYTHONPATH=str(ROOT))
        env.pop("RUNTIME_HEDGE_ENABLED", None)
        env.pop("RUNTIME_HEDGE_DELAY_S", None)
        if enabled:
            env["RUNTIME_HEDGE_ENABLED"] = "1"
        if delay is not None:
            env["RUNTIME_HEDGE_DELAY_S"] = delay
        return subprocess.run([sys.executable, "-c", CHILD], cwd=ROOT, env=env,
                              capture_output=True, text=True, timeout=30)


class HedgeConfigurationContract(unittest.TestCase):
    def accepted(self, delay, expected, *, enabled=False):
        result = fresh(delay, enabled=enabled)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["config_delay"], expected)
        self.assertEqual(payload["runtime_delay"], expected)
        self.assertEqual(payload["health_delay"], expected)
        self.assertEqual(payload["enabled"], enabled)
        self.assertEqual(payload["health_enabled"], enabled)
        return payload

    def test_unset_is_five_seconds_and_off(self):
        result = self.accepted(None, 5.0)
        self.assertEqual((result["provider"], result["primary_timeout"], result["fallback_calls"]),
                         ("gemini", 7.0, 0))

    def test_three_seconds_does_not_enable_the_experiment(self):
        result = self.accepted("3", 3.0)
        self.assertEqual((result["provider"], result["primary_timeout"], result["fallback_calls"]),
                         ("gemini", 7.0, 0))

    def test_inclusive_bounds_and_fractional_configuration(self):
        for delay in ("1", "2.5", "5"):
            with self.subTest(delay=delay):
                self.accepted(delay, float(delay))

    def test_invalid_values_fail_fast_even_when_disabled(self):
        for delay in ("", " ", "bad", "nan", "NaN", "inf", "-inf", "0.99", "5.01"):
            with self.subTest(delay=delay):
                result = fresh(delay)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("RUNTIME_HEDGE_DELAY_S must be finite and between 1 and 5 seconds", result.stderr)
                self.assertEqual(result.stdout, "")

    def test_enabled_three_second_delay_reaches_existing_dispatch_gate(self):
        result = self.accepted("3", 3.0, enabled=True)
        self.assertEqual((result["dispatch"], result["hedged_calls"], result["sequential_calls"]),
                         ("hedged", 1, 0))

    def test_default_delay_keeps_short_budget_sequential(self):
        result = self.accepted(None, 5.0, enabled=True)
        self.assertEqual((result["dispatch"], result["hedged_calls"], result["sequential_calls"]),
                         ("sequential", 0, 1))


if __name__ == "__main__":
    unittest.main()

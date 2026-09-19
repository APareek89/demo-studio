"""Fake-clock runtime fallback controls; no network, keys or provider calls."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from pydantic import BaseModel

from server import config, usage
from server.llm import claude, gemini, runware, runtime


class Answer(BaseModel):
    answer: str


def credit_error():
    body = {"type": "error", "error": {"type": "invalid_request_error", "message":
        "Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."}}
    return claude.anthropic.BadRequestError("Error code: 400 - " + str(body),
        response=httpx.Response(400, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")), body=body)


class RuntimeCreditCooldown(unittest.TestCase):
    def setUp(self):
        self.now, self.calls = 1000.0, []
        self.claude_error, self.runware_error = credit_error(), None
        self.enterContext(patch.multiple(config, MOCK_LLM=False, RUNTIME_PROVIDERS=["gemini", "claude", "runware"],
            RUNTIME_TIMEOUT=10.0, CLAUDE_RUNTIME_MODEL="synthetic-runtime-model", ANTHROPIC_API_KEY="synthetic-config-key"))
        self.enterContext(patch.dict(runtime.os.environ, {"ANTHROPIC_BASE_URL": "https://api.anthropic.com/"}))
        self.enterContext(patch.object(claude, "_client", SimpleNamespace(api_key="synthetic-effective-key", base_url="https://api.anthropic.com/")))
        self.enterContext(patch.dict(runtime._credit_cooldowns, {}, clear=True))
        self.enterContext(patch.object(runtime.time, "monotonic", side_effect=lambda: self.now))
        self.enterContext(patch.object(runtime.time, "time", side_effect=lambda: self.now))
        self.trace = self.enterContext(patch.object(usage, "trace"))
        for name in ["socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection"]:
            self.enterContext(patch(name, side_effect=AssertionError("network forbidden")))
        self.enterContext(patch.object(gemini, "text_structured", side_effect=self.gemini_call))
        self.enterContext(patch.object(claude, "structured", side_effect=self.claude_call))
        self.enterContext(patch.object(runware, "structured", side_effect=self.runware_call))

    def gemini_call(self, *args, **kwargs):
        self.calls.append(("gemini", kwargs["timeout_s"]))
        self.now += kwargs["timeout_s"]
        raise TimeoutError("synthetic primary timeout")

    def claude_call(self, *args, **kwargs):
        self.calls.append(("claude", kwargs["timeout"]))
        self.now += .6
        if self.claude_error:
            raise self.claude_error
        return Answer(answer="Reviewed answer")

    def runware_call(self, *args, **kwargs):
        self.calls.append(("runware", kwargs["timeout"]))
        self.now += kwargs["timeout"] if self.runware_error else .2
        if self.runware_error:
            raise self.runware_error
        return Answer(answer="Reviewed answer")

    def call(self, budget=12):
        return runtime.structured("System", "Customer question", Answer, timeout_budget_s=budget)

    def test_later_turn_skips_only_credit_failure_and_retains_fallback_success(self):
        first = self.call()
        self.assertEqual([p for p, _ in self.calls], ["gemini", "claude", "runware"])
        first_timeout = self.calls[-1][1]
        expires = dict(runtime._credit_cooldowns)
        self.calls.clear()
        second = self.call()
        self.assertEqual([p for p, _ in self.calls], ["gemini", "runware"])
        self.assertAlmostEqual(self.calls[-1][1] - first_timeout, .6)
        self.assertEqual(first._runtime_provider, "runware")
        self.assertEqual(second._runtime_provider, "runware")
        self.assertEqual(runtime._credit_cooldowns, expires, "Skipping must not extend the cooldown")
        skips = [call for call in self.trace.call_args_list if call.args[0] == "runtime-claude-skipped"]
        self.assertEqual(len(skips), 1)
        self.assertIn("insufficient-credit", skips[0].kwargs["error"])
        self.assertEqual((skips[0].kwargs["latency_ms"], skips[0].kwargs["usd"]), (0, 0))
        captured = str(self.trace.call_args_list) + repr(runtime._credit_cooldowns)
        self.assertNotIn("synthetic-effective-key", captured)
        self.assertNotIn("synthetic-config-key", captured)
        self.assertTrue(all(isinstance(key, bytes) and len(key) == 32 for key in runtime._credit_cooldowns))

    def test_expiry_retries_provider_and_accepts_recovered_answer(self):
        self.call(); self.calls.clear(); self.now += 61; self.claude_error = None
        answer = self.call()
        self.assertEqual([p for p, _ in self.calls], ["gemini", "claude"])
        self.assertEqual(answer._runtime_provider, "claude")
        self.assertFalse(runtime._credit_cooldowns)

    def test_timeouts_429_other_400_and_opaque_messages_do_not_start_cooldown(self):
        errors = [TimeoutError("synthetic timeout"), ConnectionError("synthetic connection failure"),
            claude.anthropic.RateLimitError("credit balance temporarily unavailable",
                response=httpx.Response(429, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")),
                body={"error": {"type": "rate_limit_error", "message": "rate limit"}}),
            claude.anthropic.BadRequestError("invalid request",
                response=httpx.Response(400, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")),
                body={"error": {"type": "invalid_request_error", "message": "Invalid schema"}}),
            RuntimeError(str(credit_error()))]
        for error in errors:
            with self.subTest(error=type(error).__name__):
                self.calls.clear(); self.claude_error = error
                self.call(); self.call()
                self.assertEqual([p for p, _ in self.calls].count("claude"), 2)
                self.assertFalse(runtime._credit_cooldowns)

    def test_effective_key_change_bypasses_stale_cooldown_but_unused_config_change_does_not(self):
        self.call(); self.calls.clear()
        with patch.object(config, "ANTHROPIC_API_KEY", "new-unused-config-key"):
            self.call()
        self.assertNotIn("claude", [p for p, _ in self.calls])
        self.calls.clear(); self.claude_error = None
        with patch.object(claude, "_client", SimpleNamespace(api_key="new-effective-key", base_url="https://api.anthropic.com/")):
            answer = self.call()
        self.assertEqual([p for p, _ in self.calls], ["gemini", "claude"])
        self.assertEqual(answer._runtime_provider, "claude")

    def test_model_or_effective_endpoint_change_does_not_reuse_cooldown(self):
        self.call(); self.calls.clear(); self.claude_error = None
        with patch.object(config, "CLAUDE_RUNTIME_MODEL", "new-runtime-model"):
            self.assertEqual(self.call()._runtime_model, "new-runtime-model")
        self.assertEqual([p for p, _ in self.calls], ["gemini", "claude"])
        self.calls.clear()
        with patch.object(claude._client, "base_url", "https://synthetic-other-endpoint.example"):
            self.assertEqual(self.call()._runtime_provider, "claude")
        self.assertEqual([p for p, _ in self.calls], ["gemini", "claude"])

    def test_cold_configuration_identity_matches_the_created_effective_client(self):
        with patch.object(claude, "_client", None):
            self.call()
        self.calls.clear()
        with patch.object(claude, "_client", SimpleNamespace(api_key=config.ANTHROPIC_API_KEY, base_url="https://api.anthropic.com/")):
            self.call()
        self.assertEqual([p for p, _ in self.calls], ["gemini", "runware"])

    def test_success_and_failure_share_original_deadline_when_provider_is_skipped(self):
        self.call(); self.calls.clear(); self.runware_error = TimeoutError("synthetic final timeout")
        started = self.now
        with self.assertRaisesRegex(RuntimeError, "insufficient-credit"):
            self.call()
        self.assertEqual([p for p, _ in self.calls], ["gemini", "runware"])
        self.assertLessEqual(self.now - started, 12.000001)
        self.assertAlmostEqual(self.calls[-1][1], 5)
        self.calls.clear()
        with self.assertRaisesRegex(RuntimeError, "whole-turn deadline"):
            self.call(.2)
        self.assertFalse(self.calls)

    def test_legacy_no_deadline_path_keeps_its_provider_attempts(self):
        self.call(); self.calls.clear(); previous = dict(runtime._credit_cooldowns)
        self.call(None)
        self.assertEqual([p for p, _ in self.calls], ["gemini", "claude", "runware"])
        self.assertEqual(runtime._credit_cooldowns, previous)


if __name__ == "__main__":
    unittest.main(verbosity=2)

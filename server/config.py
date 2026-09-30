"""Central configuration. Keys come from .env (never from the browser)."""
from __future__ import annotations

import math
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = Path(os.getenv("DEMO_STUDIO_DATA")).resolve() if os.getenv("DEMO_STUDIO_DATA") else ROOT / "data" / "demos"  # tests set DEMO_STUDIO_DATA=data/test-demos
WEB_DIR = ROOT / "web"
# The LangGraph checkpoint file. Overridable so the app can run where the project dir is read-only
# (serverless hosts); those platforms must point it at writable storage.
GRAPH_DB = Path(os.getenv("DEMO_STUDIO_GRAPH_DB")).resolve() if os.getenv("DEMO_STUDIO_GRAPH_DB") else ROOT / "data" / "graph.sqlite"
DATA_DIR.mkdir(parents=True, exist_ok=True)
GRAPH_DB.parent.mkdir(parents=True, exist_ok=True)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
RUNWARE_API_KEY = os.getenv("RUNWARE_API_KEY", "").strip()
PIXELBIN_API_TOKEN = os.getenv("PIXELBIN_API_TOKEN", "").strip()
MEDIA_PROVIDER_ORDER = list(dict.fromkeys(p.strip().lower() for p in os.getenv("MEDIA_PROVIDER_ORDER", "runware,pixelbin").split(",") if p.strip()))
if not MEDIA_PROVIDER_ORDER or set(MEDIA_PROVIDER_ORDER) - {"runware", "pixelbin"}:
    raise ValueError("MEDIA_PROVIDER_ORDER must list runware and/or pixelbin")
RUNWARE_IMAGE_MODEL = os.getenv("RUNWARE_IMAGE_MODEL", "google:4@3").strip() or "google:4@3"
GCLOUD_TTS_API_KEY = os.getenv("GCLOUD_TTS_API_KEY", "").strip()
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "").strip()
SARVAM_TTS_MODEL = os.getenv("SARVAM_TTS_MODEL", "bulbul:v3").strip() or "bulbul:v3"  # v2 deprecated Sep 2026
SARVAM_STT_MODEL = os.getenv("SARVAM_STT_MODEL", "saarika:v2.5").strip() or "saarika:v2.5"
# Speech: Sarvam is primary for the Indian context when its key is present; Gemini / Cloud TTS / browser fall back.
_default_tts = "sarvam" if SARVAM_API_KEY else "gemini"
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "").strip() or _default_tts
if TTS_PROVIDER == "sarvam" and not SARVAM_API_KEY:
    TTS_PROVIDER = "gemini"
STT_PROVIDER = os.getenv("STT_PROVIDER", "").strip() or ("sarvam" if SARVAM_API_KEY else "browser")
if STT_PROVIDER == "sarvam" and not SARVAM_API_KEY:
    STT_PROVIDER = "browser"
MOCK_LLM = os.getenv("MOCK_LLM", "").strip() == "1"  # schema-shaped fake outputs, no keys, no spend

# The tier chooses text-model and build-order defaults. Explicit overrides win;
# runtime order and media/speech stay independent.
MODEL_TIER = os.getenv("MODEL_TIER", "eval").strip() or "eval"
if MODEL_TIER not in {"eval", "customer"}:
    raise ValueError("MODEL_TIER must be 'eval' or 'customer'")
_claude_default = "claude-opus-5" if MODEL_TIER == "customer" else "claude-haiku-4-5-20251001"
_gemini_text_default = "gemini-3.8-flash" if MODEL_TIER == "customer" else "gemini-3.5-flash-lite"
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "").strip() or _claude_default
CLAUDE_PLAN_MODEL = os.getenv("CLAUDE_PLAN_MODEL", "").strip() or _claude_default
CLAUDE_LITE_MODEL = os.getenv("CLAUDE_LITE_MODEL", "").strip() or _claude_default
GEMINI_TEXT_MODEL = os.getenv("GEMINI_TEXT_MODEL", "").strip() or _gemini_text_default
# RUNWARE_TEXT_MODEL is the eval override; the adapter receives the selected effective value.
# In customer tier, RUNWARE_TEXT_MODEL_PREMIUM wins even if the eval override is also set.
_runware_eval_model = os.getenv("RUNWARE_TEXT_MODEL", "").strip() or "deepseek:v4@flash"
RUNWARE_TEXT_MODEL_PREMIUM = os.getenv("RUNWARE_TEXT_MODEL_PREMIUM", "").strip() or "openai:gpt@5.5"
RUNWARE_TEXT_MODEL = RUNWARE_TEXT_MODEL_PREMIUM if MODEL_TIER == "customer" else _runware_eval_model
# Structured text-only build work uses its own configurable order. Media adapters
# retain their current provider, and explicit runtime calls disable this chain.
_build_default = "runware,gemini,claude" if MODEL_TIER == "customer" else "gemini,claude,runware"
BUILD_PROVIDERS = list(dict.fromkeys(p.strip().lower() for p in (os.getenv("BUILD_PROVIDERS", "").strip() or _build_default).split(",") if p.strip()))
if not BUILD_PROVIDERS or set(BUILD_PROVIDERS) - {"gemini", "claude", "runware"}:
    raise ValueError("BUILD_PROVIDERS must list gemini, claude and/or runware")
# Runtime (the live demo — the customer is waiting): a provider order the user can flip and a short timeout per try.
# Default Gemini first, then Claude, then Runware; the adapter owns each provider's bounded retry.
RUNTIME_PROVIDERS = [p.strip() for p in os.getenv("RUNTIME_PROVIDERS", "gemini,claude,runware").split(",") if p.strip()]
RUNTIME_TIMEOUT = float(os.getenv("RUNTIME_TIMEOUT", "15"))
# Experimental delayed fallback race; opt-in only after a separate paid comparison.
RUNTIME_HEDGE_ENABLED = os.getenv("RUNTIME_HEDGE_ENABLED", "").strip() == "1"
try:
    RUNTIME_HEDGE_DELAY_S = float(os.getenv("RUNTIME_HEDGE_DELAY_S", "5"))
except ValueError as exc:
    raise ValueError("RUNTIME_HEDGE_DELAY_S must be finite and between 1 and 5 seconds") from exc
if not math.isfinite(RUNTIME_HEDGE_DELAY_S) or not 1 <= RUNTIME_HEDGE_DELAY_S <= 5:
    raise ValueError("RUNTIME_HEDGE_DELAY_S must be finite and between 1 and 5 seconds")
CLAUDE_RUNTIME_MODEL = os.getenv("CLAUDE_RUNTIME_MODEL", "").strip() or CLAUDE_MODEL
GEMINI_RUNTIME_MODEL = os.getenv("GEMINI_RUNTIME_MODEL", "").strip() or GEMINI_TEXT_MODEL
STORAGE_BACKEND = (os.getenv("STORAGE_BACKEND", "local").strip().lower() or "local")  # local | aws — aws falls back to local without credentials
DDB_TABLE_SESSIONS = os.getenv("DDB_TABLE_SESSIONS", "demo-studio-sessions").strip() or "demo-studio-sessions"
SESSION_TTL_DAYS = int(os.getenv("SESSION_TTL_DAYS", "180") or 180)  # customer data does not live forever
MEDIA_SIGNED_URL_SECONDS = int(os.getenv("MEDIA_SIGNED_URL_SECONDS", "900") or 900)
SHARE_SECRET = os.getenv("SHARE_SECRET", "").strip()  # empty → a random secret generated once into data/.share-secret
GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-lite-image").strip() or "gemini-3.1-flash-lite-image"  # background clean-up + mascot
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip() or "gemini-3.6-flash"  # the proven vision tier (video shots + image tags); lite was the MVP downgrade
GEMINI_TTS_MODEL = os.getenv("GEMINI_TTS_MODEL", "gemini-3.1-flash-tts-preview").strip() or "gemini-3.1-flash-tts-preview"
GCLOUD_TTS_VOICE = "en-IN-Chirp3-HD-Aoede"
GEMINI_TTS_VOICE = "Sulafat"

# Rehearsal: how many likely customer questions to generate and answer at build time.
# Each one is a paid Claude call — kept small on purpose; raise in demo settings.
REHEARSAL_QUESTIONS = int(os.getenv("REHEARSAL_QUESTIONS", "12"))

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "1024"))  # Gemini Files API takes up to 2 GB; playback streams the original


def health() -> dict:
    return {
        "anthropic": bool(ANTHROPIC_API_KEY),
        "gemini": bool(GEMINI_API_KEY),
        "runware": bool(RUNWARE_API_KEY),
        "pixelbin": bool(PIXELBIN_API_TOKEN),
        "media_provider_order": MEDIA_PROVIDER_ORDER,
        "runware_image_model": RUNWARE_IMAGE_MODEL,
        "gcloud_tts": bool(GCLOUD_TTS_API_KEY),
        "storage": STORAGE_BACKEND,
        "sarvam": bool(SARVAM_API_KEY),
        "tts_provider": TTS_PROVIDER,
        "stt_provider": STT_PROVIDER,
        "mock": MOCK_LLM,
        "model_tier": MODEL_TIER,
        "claude_model": CLAUDE_MODEL, "claude_plan_model": CLAUDE_PLAN_MODEL, "claude_lite_model": CLAUDE_LITE_MODEL, "gemini_image_model": GEMINI_IMAGE_MODEL,
        "gemini_model": GEMINI_MODEL, "gemini_text_model": GEMINI_TEXT_MODEL, "gemini_tts_model": GEMINI_TTS_MODEL,
        "runware_text_model": RUNWARE_TEXT_MODEL, "runware_text_model_premium": RUNWARE_TEXT_MODEL_PREMIUM,
        "build_providers": BUILD_PROVIDERS,
        "runtime_providers": RUNTIME_PROVIDERS, "runtime_timeout": RUNTIME_TIMEOUT, "runtime_hedge_enabled": RUNTIME_HEDGE_ENABLED,
        "runtime_hedge_delay_s": RUNTIME_HEDGE_DELAY_S,
        "claude_runtime_model": CLAUDE_RUNTIME_MODEL, "gemini_runtime_model": GEMINI_RUNTIME_MODEL,
    }

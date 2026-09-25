"""Provider-neutral delivery metadata; Bulbul v3 receives pace and optional temperature.

Sarvam documents punctuation, pace and temperature, not SSML or emotion tags:
https://docs.sarvam.ai/api/api-guides-tutorials/text-to-speech/best-practices
Tone is an authoring instruction, not a promise of a vendor emotion control.
"""
from __future__ import annotations

import math
import re

_TONES = {"warm": 1.0, "upbeat": 1.03, "calm": 0.96, "reassuring": 0.96}
_MARKERS = re.compile(r"\[(?:warm|warmly|cheerful|cheerfully|upbeat|calm|calmly|reassuring|excited|excitedly|pause|short pause|long pause|smile|smiling|laugh|laughs|sigh|sighs|whisper|whispers|emphasis)\]", re.I)
_SSML = re.compile(r"</?(?:speak|prosody|break|emphasis|voice|say-as|phoneme|sub|p|s|mark|audio)\b[^>]*>", re.I)


def normalize(delivery: dict | None = None) -> dict:
    delivery = delivery if isinstance(delivery, dict) else {}
    tone = delivery.get("tone", "warm")
    tone = tone if isinstance(tone, str) and tone in _TONES else "warm"
    try:
        pace = float(delivery.get("pace", _TONES[tone]))
    except (TypeError, ValueError):
        pace = _TONES[tone]
    if not math.isfinite(pace):
        pace = _TONES[tone]
    # A subtle guide: vendor's full 0.5–2.0 range is intentionally not exposed.
    normalized = {"tone": tone, "pace": round(max(0.9, min(1.08, pace)), 2)}
    # The author can choose restrained variation for an occasional line. An
    # omitted/invalid value stays absent so legacy audio identities do not change.
    expression = delivery.get("expressiveness")
    if isinstance(expression, (int, float)) and not isinstance(expression, bool):
        try:
            expression = float(expression)
        except OverflowError:
            expression = float("nan")
        if math.isfinite(expression):
            normalized["expressiveness"] = round(max(0.5, min(0.8, expression)), 2)
    return normalized


def prepare(text: str, delivery: dict | None = None) -> dict:
    """Return text, pace and optional expressiveness; never send delivery tags to TTS.

    Script punctuation carries natural pauses. Keep captions and spoken words
    identical, and keep styling out of source claims and customer quotations.
    """
    plain = _SSML.sub(" ", _MARKERS.sub(" ", str(text or "")))
    plain = re.sub(r"[ \t]+", " ", plain).strip()
    plain = re.sub(r" +([,.!?;:])", r"\1", plain)
    normalized = normalize(delivery)
    return {"text": plain, "plain_text": plain, "pace": normalized["pace"],
            **({"expressiveness": normalized["expressiveness"]} if "expressiveness" in normalized else {})}

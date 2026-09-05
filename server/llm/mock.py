"""MOCK_LLM=1 — schema-shaped fake outputs so the whole pipeline and UI can be exercised
without API keys or spend. Not intelligence; plumbing verification only."""
from __future__ import annotations

import io
import json
import struct
from typing import Any, Literal, Union, get_args, get_origin

from pydantic import BaseModel


def _fake_value(name: str, ann: Any, depth: int = 0) -> Any:
    origin = get_origin(ann)
    if origin is Union or str(origin) == "types.UnionType":
        args = [a for a in get_args(ann) if a is not type(None)]
        return _fake_value(name, args[0], depth) if args else None
    if origin is Literal:
        prefer = {"role": "proof", "step": "say", "customer_state": "unknown", "kind": "spec", "truth": "stated", "type": "answer", "card": "none", "category": "features"}
        if name in prefer and prefer[name] in get_args(ann):
            return prefer[name]
        return get_args(ann)[0]
    if origin is list:
        (item,) = get_args(ann) or (str,)
        n = 2 if depth > 1 else (5 if name == "segments" else 3)
        out = [_fake_value(name, item, depth + 1) for _ in range(n)]
        for i, o in enumerate(out):
            if isinstance(o, dict):
                if "start" in o and "end" in o:
                    o["start"], o["end"] = float(i * 5), float(i * 5 + 4)
                if "index" in o:
                    o["index"] = i
                if "id" in o and isinstance(o["id"], str):
                    o["id"] = f"{o['id'].split(' ')[0]}{i+1}"
                if "role" in o and "lines" in o or ("role" in o and "goal" in o):  # segments: a realistic role mix
                    o["role"] = ["intro", "outcome", "proof", "features", "establish"][i % 5]
                if "segment_id" in o:
                    o["segment_id"] = f"mock{3 + (i % 2)}"
        return out
    if origin is dict:
        return {"k1": "v1 (mock)"}
    if isinstance(ann, type) and issubclass(ann, BaseModel):
        return fake_dict(ann, depth + 1)
    if ann is bool:
        return True
    if ann is int:
        return 4 if name == "quality" else 3
    if ann is float:
        return 0.9 if name == "confidence" else 1.0
    lower = name.lower()
    if lower in ("id",):
        return "mock"
    if lower == "type":
        return "answer"
    if lower == "role":
        return "proof"
    if lower == "step":
        return "say"
    if lower == "customer_state":
        return "unknown"
    if lower == "truth":
        return "stated"
    if lower in ("kind",):
        return "spec"
    if lower == "suggested_voice" or lower == "voice_name":
        return "Sulafat"
    if lower == "language":
        return "en-IN"
    if lower in ("url", "locator", "quote", "ref", "visual_ref", "cta", "escalate", "conditions", "on_screen_text", "instruction", "reason", "stage", "card"):
        return ""
    return f"{name.replace('_', ' ')} (mock)"


def fake_dict(schema: type[BaseModel], depth: int = 0) -> dict:
    out = {}
    for fname, field in schema.model_fields.items():
        out[fname] = _fake_value(fname, field.annotation, depth)
    return out


def fake(schema: type[BaseModel]) -> BaseModel:
    d = fake_dict(schema)
    # keep AlignOut harmless
    if "actions" in d and "reply" in d:
        d["actions"] = [{"type": "answer"}]
    if "answered" in d:
        d["answered"] = False
        d["fact_ids"] = []
    return schema.model_validate(d)


def silent_wav(seconds: float = 1.0, rate: int = 16000) -> bytes:
    n = int(seconds * rate)
    pcm = b"\x00\x00" * n
    buf = io.BytesIO()
    buf.write(b"RIFF"); buf.write(struct.pack("<I", 36 + len(pcm))); buf.write(b"WAVE")
    buf.write(b"fmt "); buf.write(struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16))
    buf.write(b"data"); buf.write(struct.pack("<I", len(pcm))); buf.write(pcm)
    return buf.getvalue()


def cube_glb() -> bytes:
    """Small valid GLB used to exercise upload, storage and <model-viewer> without spend."""
    positions = [
        -1.0, -1.0, -1.0,  1.0, -1.0, -1.0,  1.0, 1.0, -1.0, -1.0, 1.0, -1.0,
        -1.0, -1.0,  1.0,  1.0, -1.0,  1.0,  1.0, 1.0,  1.0, -1.0, 1.0,  1.0,
    ]
    indices = [0, 1, 2, 0, 2, 3, 4, 6, 5, 4, 7, 6, 0, 4, 5, 0, 5, 1,
               1, 5, 6, 1, 6, 2, 2, 6, 7, 2, 7, 3, 4, 0, 3, 4, 3, 7]
    bin_chunk = struct.pack("<" + "f" * len(positions), *positions) + struct.pack("<" + "H" * len(indices), *indices)
    while len(bin_chunk) % 4:
        bin_chunk += b"\x00"
    doc = {"asset": {"version": "2.0", "generator": "Demo Studio mock"}, "scene": 0,
           "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
           "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
           "buffers": [{"byteLength": len(bin_chunk)}],
           "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(positions) * 4, "target": 34962},
                           {"buffer": 0, "byteOffset": len(positions) * 4, "byteLength": len(indices) * 2, "target": 34963}],
           "accessors": [{"bufferView": 0, "componentType": 5126, "count": 8, "type": "VEC3", "min": [-1, -1, -1], "max": [1, 1, 1]},
                         {"bufferView": 1, "componentType": 5123, "count": len(indices), "type": "SCALAR"}]}
    js = json.dumps(doc, separators=(",", ":")).encode()
    while len(js) % 4:
        js += b" "
    total = 12 + 8 + len(js) + 8 + len(bin_chunk)
    return (struct.pack("<4sII", b"glTF", 2, total) + struct.pack("<I4s", len(js), b"JSON") + js
            + struct.pack("<I4s", len(bin_chunk), b"BIN\x00") + bin_chunk)

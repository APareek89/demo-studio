"""Render the approved, non-interactive demo route as a downloadable MP4.

The live player stays richer (3D, questions and lead capture). The export deliberately
uses the same bundled narration and per-line visual contract so it cannot invent a
second script or silently pick a different image.
"""
from __future__ import annotations

import subprocess
import threading
from pathlib import Path
from urllib.parse import unquote, urlparse

from PIL import Image, ImageDraw, ImageFont

from . import media, runlog, store

_locks: dict[str, threading.Lock] = {}
_guard = threading.Lock()


def _rel(demo_id: str, url: str | None) -> str | None:
    if not url:
        return None
    path = unquote(urlparse(url).path)
    prefix = f"/media/{demo_id}/"
    return path[len(prefix):] if path.startswith(prefix) else None


def _font(size: int, bold: bool = False):
    names = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/SFNS.ttf",
    ]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    words = text.split()
    rows, row = [], ""
    for word in words:
        trial = (row + " " + word).strip()
        if row and draw.textbbox((0, 0), trial, font=font)[2] > width:
            rows.append(row)
            row = word
        else:
            row = trial
    if row:
        rows.append(row)
    return rows[:3]


def _source_image(demo_id: str, bundle: dict, line: dict) -> Path | None:
    visual = line.get("visual") or {}
    mode = visual.get("display_mode") or ""
    # Literal evidence is the only time the exported frame uses a script image.
    # Model/card lines use the approved product preview as the visual placeholder.
    rel = _rel(demo_id, visual.get("url")) if mode == "evidence" and visual.get("kind") == "image" else None
    if not rel:
        rel = (bundle.get("visual_asset") or {}).get("preview")
    if not rel:
        rel = _rel(demo_id, (bundle.get("media") or {}).get("hero"))
    path = store.path(demo_id, rel) if rel else None
    return path if path and path.exists() else None


def _frame(demo_id: str, bundle: dict, line: dict, target: Path) -> None:
    media._codecs()
    canvas = Image.new("RGB", (1280, 720), "#EDF2F9")
    source = _source_image(demo_id, bundle, line)
    if source:
        try:
            with Image.open(source) as raw:
                im = raw.convert("RGB")
                im.thumbnail((1160, 545), Image.Resampling.LANCZOS)
                canvas.paste(im, ((1280 - im.width) // 2, max(18, (560 - im.height) // 2)))
        except Exception:
            pass
    draw = ImageDraw.Draw(canvas, "RGBA")
    draw.rounded_rectangle((42, 558, 1238, 694), radius=18, fill=(255, 255, 255, 242), outline=(198, 211, 232, 255), width=2)
    title_font, copy_font = _font(18, True), _font(27)
    guide = ((bundle.get("voice") or {}).get("persona") or {}).get("persona_name") or "Guide"
    draw.text((68, 579), guide.upper(), font=title_font, fill="#1F5EFF")
    y = 610
    for row in _wrap(draw, line.get("text", ""), copy_font, 1125):
        draw.text((68, y), row, font=copy_font, fill="#12213A")
        y += 32
    target.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(target, "JPEG", quality=91)


def _run(cmd: list[str], timeout: int = 300) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or "ffmpeg failed")[-900:])


def render(demo_id: str) -> Path:
    bundle_path = store.path(demo_id, "bundle.json")
    if not bundle_path.exists():
        raise RuntimeError("Build the demo before downloading its MP4")
    target = store.path(demo_id, "export", "demo.mp4")
    if target.exists() and target.stat().st_mtime >= bundle_path.stat().st_mtime:
        return target
    with _guard:
        lock = _locks.setdefault(demo_id, threading.Lock())
    if not lock.acquire(blocking=False):
        raise RuntimeError("The MP4 is already being prepared — try the download again in a moment")
    try:
        ff = media.ffmpeg()
        if not ff:
            raise RuntimeError("MP4 export needs ffmpeg")
        bundle = store.read_json(demo_id, "bundle.json") or {}
        work = store.path(demo_id, "export", "work")
        work.mkdir(parents=True, exist_ok=True)
        clips: list[Path] = []

        intro_rel = _rel(demo_id, (bundle.get("intro_video") or {}).get("url")) if (bundle.get("intro_video") or {}).get("enabled") else None
        intro = store.path(demo_id, intro_rel) if intro_rel else None
        if intro and intro.exists():
            clip = work / "000-intro.mp4"
            _run([ff, "-y", "-i", str(intro), "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=0x07101d,fps=24", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-ac", "2", "-movflags", "+faststart", str(clip)])
            clips.append(clip)

        lines = [line for seg in bundle.get("segments", []) for line in seg.get("lines", []) if not line.get("unverified")]
        lines += [line for line in bundle.get("closing", []) if not line.get("unverified")]
        for index, line in enumerate(lines, 1):
            audio_rel = _rel(demo_id, line.get("audio"))
            audio = store.path(demo_id, audio_rel) if audio_rel else None
            if not audio or not audio.exists():
                continue
            frame, clip = work / f"{index:03d}.jpg", work / f"{index:03d}.mp4"
            _frame(demo_id, bundle, line, frame)
            _run([ff, "-y", "-loop", "1", "-framerate", "24", "-i", str(frame), "-i", str(audio), "-vf", "fps=24", "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-ac", "2", "-shortest", "-movflags", "+faststart", str(clip)])
            clips.append(clip)
        if not clips:
            raise RuntimeError("The bundle has no rendered narration or opening film to export")
        listing = work / "clips.txt"
        listing.write_text("\n".join("file '" + str(p).replace("'", "'\\''") + "'" for p in clips) + "\n")
        temp = target.with_suffix(".tmp.mp4")
        _run([ff, "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(temp)], timeout=600)
        temp.replace(target)
        runlog.event(demo_id, "MP4 demo exported", f"{len(clips)} approved visual/narration clip(s) · {target.stat().st_size / 1e6:.1f} MB")
        return target
    finally:
        lock.release()

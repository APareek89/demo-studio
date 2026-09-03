"""Failure / acceptance QA (free, MOCK_LLM=1): what happens when people upload the wrong thing.
Every case must end in one of: accepted (and survives the read stage), or a clean 4xx with a message a
person can act on. A 500, a hang, or a demo stuck in `error` is a failure. Prints a markdown table."""
import io
import os
import struct
import sys
import time
import zlib

os.environ["MOCK_LLM"] = "1"
os.environ.setdefault("DEMO_STUDIO_DATA", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "test-demos"))  # keep test demos out of the real list
os.environ["MAX_UPLOAD_MB"] = "5"  # keep the "too big" case cheap: 5 MB limit for this run
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi.testclient import TestClient  # noqa: E402

from server.app import app  # noqa: E402

c = TestClient(app)


def png(w, h, color=(30, 90, 255)):
    raw = b"".join(b"\x00" + bytes(color) * w for _ in range(h))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")


def pil_bytes(fmt, size=(640, 480), **kw):
    from PIL import Image
    im = Image.new("RGB", size, (20, 94, 255))
    buf = io.BytesIO()
    im.save(buf, fmt, **kw)
    return buf.getvalue()


def avif_bytes():
    try:
        import pillow_avif  # noqa: F401
        return pil_bytes("AVIF")
    except Exception:
        return None


def heic_bytes():
    try:
        from pillow_heif import register_heif_opener
        register_heif_opener()
        return pil_bytes("HEIF")
    except Exception:
        return None


real_webp = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "samples", "iqube", sorted(os.listdir("samples/iqube"))[0]), "rb").read()
dummy_mp4_path = "samples/iqube_dummy.mp4"
dummy_mp4 = open(dummy_mp4_path, "rb").read() if os.path.exists(dummy_mp4_path) else None

CASES = [
    # name, filename, bytes, mime, expect ("accept" | "reject")
    ("WEBP product image", "a.webp", real_webp, "image/webp", "accept"),
    ("PNG 4000×4000 (large dimensions)", "big.png", png(4000, 4000), "image/png", "accept"),
    ("PNG 1×1 (tiny)", "tiny.png", png(1, 1), "image/png", "accept"),
    ("JPEG", "a.jpg", pil_bytes("JPEG", quality=85), "image/jpeg", "accept"),
    ("AVIF", "a.avif", avif_bytes(), "image/avif", "accept"),
    ("HEIC", "a.heic", heic_bytes(), "image/heic", "accept"),
    ("BMP (not supported)", "a.bmp", pil_bytes("BMP"), "image/bmp", "reject"),
    ("TIFF (not supported)", "a.tiff", pil_bytes("TIFF"), "image/tiff", "reject"),
    ("Corrupted JPEG (random bytes)", "bad.jpg", os.urandom(40_000), "image/jpeg", "accept"),
    ("Corrupted AVIF (random bytes)", "bad.avif", os.urandom(40_000), "image/avif", "accept"),
    ("Empty file (0 bytes)", "empty.jpg", b"", "image/jpeg", "reject"),
    ("Wrong extension (.exe)", "setup.exe", os.urandom(10_000), "application/octet-stream", "reject"),
    ("No extension", "README", b"hello", "text/plain", "reject"),
    ("MP4 dummy video (20 s, 720p)", "demo.mp4", dummy_mp4, "video/mp4", "accept"),
    ("Corrupted MP4 (random bytes)", "bad.mp4", os.urandom(200_000), "video/mp4", "accept"),
    ("MOV extension with MP4 bytes", "demo.mov", dummy_mp4, "video/quicktime", "accept"),
    ("AVI (not supported)", "a.avi", os.urandom(10_000), "video/x-msvideo", "reject"),
    ("Over the size limit (6 MB at a 5 MB limit)", "huge.jpg", b"\xff\xd8" + os.urandom(6_000_000), "image/jpeg", "reject"),
    ("PDF (empty shell)", "spec.pdf", b"%PDF-1.4\n%%EOF\n", "application/pdf", "accept"),
    ("TXT catalogue", "cat.txt", "iQube: 3.4 kWh battery, IDC range 145 km.".encode(), "text/plain", "accept"),
    ("DOCX (zip garbage)", "a.docx", os.urandom(5_000), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "accept"),
    ("Path traversal name", "../../evil.jpg", real_webp, "image/jpeg", "accept"),
]

rows = []
d = c.post("/api/demos", json={"name": "Acceptance QA", "url": ""}).json()
i = d["id"]
accepted_names = []
for name, fn, data, mime, expect in CASES:
    if data is None:
        rows.append((name, "skip", "encoder not available", "—"))
        continue
    t0 = time.time()
    try:
        r = c.post(f"/api/demos/{i}/sources", files=[("files", (fn, data, mime))], data={"role": "product"})
        code, body = r.status_code, (r.json() if r.headers.get("content-type", "").startswith("application/json") else {"raw": r.text[:120]})
    except Exception as e:  # a crash in the app surfaces here with TestClient
        code, body = 500, {"detail": f"EXCEPTION {type(e).__name__}: {str(e)[:100]}"}
    ms = int((time.time() - t0) * 1000)
    if code == 200:
        got = "accept"
        msg = ", ".join(f"{s['kind']}:{s['name']}" for s in body.get("sources", [])[-1:])
        accepted_names.append(fn)
    else:
        got = "reject" if 400 <= code < 500 else "CRASH"
        msg = str(body.get("detail") or body)[:110]
    ok = (got == expect) or (expect == "accept" and got == "accept")
    rows.append((name, f"{code} · {got}", msg, "✅" if ok else "❌"))

# does the read stage survive whatever was accepted?
r = c.post(f"/api/demos/{i}/read")
t0 = time.time()
final = ""
while time.time() - t0 < 120:
    st = c.get(f"/api/demos/{i}").json()["demo"]
    if st["status"] in ("align", "error"):
        final = st["status"]
        break
    time.sleep(0.5)
stages = c.get(f"/api/demos/{i}").json()["demo"]["stages"]
err = (stages.get("understand") or {}).get("error")
rows.append(("READ STAGE with everything accepted above", final or "timeout", (err or "no error")[:110], "✅" if final == "align" else "❌"))
# path traversal must not escape the demo folder
import glob
escaped = glob.glob("evil.jpg") + glob.glob("../evil.jpg") + glob.glob("../../evil.jpg")
rows.append(("Path traversal stayed inside data/demos/<id>", "checked", "escaped files: " + (", ".join(escaped) or "none"), "✅" if not escaped else "❌"))

print("| Case | Result | Message | OK |")
print("|---|---|---|---|")
for name, res, msg, ok in rows:
    print(f"| {name} | {res} | {msg.replace('|', '/')} | {ok} |")
bad = [r for r in rows if r[3] == "❌"]
print(f"\n{len(rows) - len(bad)}/{len(rows)} cases behave as required" + (f" — FAILURES: {[b[0] for b in bad]}" if bad else ""))
sys.exit(1 if bad else 0)

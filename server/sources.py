"""Turn uploaded files and URLs into text (and page-located text for citations)."""
from __future__ import annotations

import re
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from . import store

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36 DemoStudio/0.1"


def pdf_pages(p: Path) -> list[str]:
    from pypdf import PdfReader
    try:
        reader = PdfReader(str(p))
        return [(page.extract_text() or "") for page in reader.pages]
    except Exception as e:  # corrupt or encrypted
        return [f"[could not read pdf: {e}]"]


def docx_text(p: Path) -> str:
    import docx
    try:
        d = docx.Document(str(p))
        parts = [para.text for para in d.paragraphs]
        for table in d.tables:
            for row in table.rows:
                parts.append(" | ".join(c.text for c in row.cells))
        return "\n".join(x for x in parts if x.strip())
    except Exception as e:
        return f"[could not read docx: {e}]"


def fetch_url(url: str) -> dict:
    """Fetch a product page → title, readable text, candidate image URLs."""
    out = {"url": url, "title": "", "text": "", "images": [], "error": None}
    try:
        with httpx.Client(follow_redirects=True, timeout=25, headers={"User-Agent": UA}) as c:
            r = c.get(url)
            r.raise_for_status()
            html = r.text
    except Exception as e:
        out["error"] = str(e)
        return out
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "svg", "iframe"]):
        t.decompose()
    out["title"] = (soup.title.string or "").strip() if soup.title else ""
    # keep headings/list structure loosely so prices and specs stay associated
    lines = []
    for el in soup.find_all(["h1", "h2", "h3", "h4", "p", "li", "td", "th", "span", "div"]):
        txt = el.get_text(" ", strip=True)
        if txt and len(txt) < 600:
            lines.append(txt)
    seen, dedup = set(), []
    for ln in lines:
        if ln not in seen:
            seen.add(ln)
            dedup.append(ln)
    out["text"] = "\n".join(dedup)[:120_000]
    imgs = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if src and not src.startswith("data:"):
            imgs.append(httpx.URL(url).join(src).__str__())
    out["images"] = list(dict.fromkeys(imgs))[:60]
    return out


def source_text(demo_id: str, src: dict) -> dict:
    """Return {'name','kind','text','pages':[...] } for a non-media source."""
    kind = src["kind"]
    if kind == "url":
        f = fetch_url(src["url"])
        txt = (f["title"] + "\n" + f["text"]).strip() if not f["error"] else f"[fetch failed: {f['error']}]"
        return {"id": src["id"], "name": src["url"], "kind": "url", "text": txt, "pages": None, "images": f["images"]}
    p = store.path(demo_id, src["path"])
    if kind == "pdf":
        pages = pdf_pages(p)
        return {"id": src["id"], "name": src["name"], "kind": "pdf", "text": "\n\n".join(f"[page {i+1}]\n{t}" for i, t in enumerate(pages)), "pages": pages}
    if kind == "doc":
        return {"id": src["id"], "name": src["name"], "kind": "doc", "text": docx_text(p), "pages": None}
    if kind == "text":
        try:
            return {"id": src["id"], "name": src["name"], "kind": "text", "text": p.read_text(errors="replace")[:200_000], "pages": None}
        except Exception as e:
            return {"id": src["id"], "name": src["name"], "kind": "text", "text": f"[could not read: {e}]", "pages": None}
    return {"id": src["id"], "name": src["name"], "kind": kind, "text": "", "pages": None}


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40]

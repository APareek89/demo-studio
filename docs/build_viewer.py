#!/usr/bin/env python3
"""Build docs/architecture-flow.html from docs/mermaid/*.mmd (Python port of power-coding's
build-html.mjs — this machine has no Node). Mermaid loads from a CDN in the browser."""
import html
import re
import sys
from pathlib import Path

mmd_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/mermaid")
out = Path(sys.argv[2] if len(sys.argv) > 2 else "docs/architecture-flow.html")
files = sorted(mmd_dir.glob("*.mmd"))
if not files:
    sys.exit(f"no .mmd files in {mmd_dir}")
sections = []
for f in files:
    code = f.read_text()
    m = re.search(r"^%%\s*(.+)$", code, re.M)
    title = (m.group(1) if m else f.name).strip()
    sections.append(f"<h2>{html.escape(title)}</h2>\n<pre class=\"mermaid\">{html.escape(code)}</pre>")
page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Architecture Flow</title>
<style>
 body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:1100px;margin:0 auto;padding:24px 20px 80px;color:#1f2937;background:#fafafa}}
 h1{{border-bottom:2px solid #e5e7eb;padding-bottom:8px}}
 h2{{margin-top:36px;border-top:1px solid #e5e7eb;padding-top:18px;color:#111827}}
 pre.mermaid{{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:16px;margin:14px 0 28px;overflow:auto;text-align:center}}
 .hint{{position:sticky;top:0;background:#fff8e1;border:1px solid #f0d264;border-radius:6px;padding:8px 12px;font-size:13px;color:#5a4a00;margin-bottom:16px}}
 .mermaid svg{{max-width:100%;height:auto}}
</style></head><body>
<div class="hint">Tip: use Ctrl/Cmd + scroll or browser zoom to enlarge a diagram. Diagrams are authored by hand — check the .mmd mtime against the code.</div>
<h1>Architecture Flow — Demo Studio</h1>
{chr(10).join(sections)}
<script type="module">
import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
mermaid.initialize({{ startOnLoad:false, securityLevel:"loose", theme:"base",
  themeVariables:{{ fontFamily:"-apple-system, Segoe UI, Roboto, sans-serif", fontSize:"14px" }} }});
await mermaid.run({{ querySelector:"pre.mermaid" }});
</script>
</body></html>"""
out.write_text(page)
print(f"wrote {out} ({len(files)} diagrams)")

"""Read-only production-Bundle image/tag continuity acceptance.

Renders every published slide and advances each recorded line through the real
renderer and walkthrough adapter, in both URL modes and two viewport sizes.
It decodes existing audio bytes without playing them. It never starts a visit,
opens a socket, calls a model, edits artifacts, or claims natural speech QA.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright


SOURCES = ("web/slide.js", "web/styles.css", "web/player/player.js",
           "web/player-ui.css", "web/player/walkthrough.js")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def speech_manifest(bundle):
    return [{"slide_id": slide["id"], "lines": [
        {key: line.get(key) for key in ("id", "text", "fact_ids", "audio", "start", "duration", "step", "delivery")}
        for line in slide.get("lines", [])]} for slide in bundle["slides"]]


SETUP = r"""async bundle => {
  const {renderSlide} = await import('/web/slide.js');
  const {createWalkthrough} = await import('/web/player/walkthrough.js');
  document.querySelector('.pl-welcome')?.remove();
  const root = document.querySelector('.pl'), stage = root.querySelector('.pl-stage');
  const stack = root.querySelector('.slide-stack'); stack.replaceChildren();
  const flag = new URL(location.href).searchParams.get('presentation') === 'walkthrough';
  const adapter = flag ? createWalkthrough({root, stage}) : null; adapter?.mount(bundle.slides);
  window.__continuity = {bundle, original: JSON.stringify(bundle), renderSlide, adapter, root, stage, stack, flag};
}"""


SHOW = r"""async ({index,line}) => {
  const s = window.__continuity, slide = s.bundle.slides[index];
  if (s.index !== index) {
    s.view?.destroy(); s.stack.replaceChildren();
    let view = s.renderSlide(slide, {fit:true, theme:s.bundle.visual_theme || 'marine', walkthrough:s.flag,
      position:{index:index+1,total:s.bundle.slides.length}});
    if (s.adapter) view = s.adapter.wrap(slide, view, {position:index});
    s.view=view; s.index=index; view.el.classList.add('on'); s.stack.append(view.el);
    await Promise.all(view.images.filter(i=>i.src).map(i=>i.decode().catch(()=>null)));
    view.layout();
  }
  s.view.setRevealed(line);
  const current = slide.lines?.[line];
  s.root.querySelector('.pl-cap .txt').textContent=current?.text || '';
  s.root.querySelector('.pl-cap .cite').textContent=(current?.fact_ids || []).join(', ');
  await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
  s.view.layout();
  return JSON.stringify(s.bundle) === s.original;
}"""


METRICS = r"""() => {
  const s=window.__continuity, el=s.view.el;
  const rect=n=>{const r=n.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height,right:r.right,bottom:r.bottom}};
  const within=(a,b)=>a.x>=b.x-1&&a.y>=b.y-1&&a.right<=b.right+1&&a.bottom<=b.bottom+1;
  const overlaps=(a,b)=>Math.min(a.right,b.right)-Math.max(a.x,b.x)>1&&Math.min(a.bottom,b.bottom)-Math.max(a.y,b.y)>1;
  const visible=n=>{
    if (!n || !n.getBoundingClientRect().width || !n.getBoundingClientRect().height) return false;
    for (let p=n;p&&p!==s.root.parentElement;p=p.parentElement) {
      const st=getComputedStyle(p);
      if(st.display==='none'||st.visibility==='hidden'||Number(st.opacity)===0) return false;
    } return true;
  };
  const sr=rect(el), heading=el.querySelector('.slide-heading'), footer=el.querySelector('.slide-foot');
  const labels=[...el.querySelectorAll('.callout,.slide-panel .item')].filter(visible).map(n=>{
    const r=rect(n), parent=n.closest('.slide-panel') || el;
    return {id:n.dataset.id,text:n.textContent,rect:r,inside:within(r,sr)&&within(r,rect(parent)),
      font:getComputedStyle(n).fontFamily, size:parseFloat(getComputedStyle(n).fontSize)};
  });
  const images=[...el.querySelectorAll('.slide-pic img')].filter(visible).map(n=>({
    image_id:n.closest('.slide-pic').dataset.imageId,src:n.getAttribute('src'),naturalWidth:n.naturalWidth,
    complete:n.complete,rect:rect(n),inside:within(rect(n),sr)}));
  const fonts=[...el.querySelectorAll('.slide-title,.slide-chapter,.slide-foot,.callout,.slide-panel .item')]
    .filter(visible).map(n=>({selector:n.className,font:getComputedStyle(n).fontFamily}));
  return {width:innerWidth,scrollWidth:document.documentElement.scrollWidth,stage:sr,
    heading:heading?rect(heading):null,footer:footer?rect(footer):null,
    headingInside:!!heading&&within(rect(heading),sr),footerInside:!!footer&&within(rect(footer),sr),
    images,labels,fonts,labelsOverlap:labels.some((a,i)=>labels.slice(i+1).some(b=>overlaps(a.rect,b.rect))),
    labelsCoverHeading:!!heading&&labels.some(l=>overlaps(l.rect,rect(heading))),
    labelsCoverFooter:!!footer&&labels.some(l=>overlaps(l.rect,rect(footer))),
    paragraphPages:el.querySelectorAll('.slide-text-card,.slide-text-line').length,
    galleryVisible:[...s.root.querySelectorAll('.wt-hall,.wt-caption')].some(visible),
    sourceUnchanged:JSON.stringify(s.bundle)===s.original};
}"""


AUDIO = r"""async urls => {
  const audio = new AudioContext(), rows=[];
  try { for (const url of urls) {
    const response=await fetch(url); if(!response.ok) throw Error('Recorded clip unavailable: '+url);
    const bytes=await response.arrayBuffer(), checksum=await crypto.subtle.digest('SHA-256',bytes);
    const buffer=await audio.decodeAudioData(bytes.slice(0));
    rows.push({url,bytes:bytes.byteLength,sha256:[...new Uint8Array(checksum)].map(x=>x.toString(16).padStart(2,'0')).join(''),
      duration:buffer.duration,sample_rate:buffer.sampleRate,channels:buffer.numberOfChannels});
  }} finally { await audio.close(); } return rows;
}"""


def run(args):
    parsed = urlsplit(args.base)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.port == 8896:
        raise ValueError("Use an owned loopback server other than protected port 8896")
    if args.did == "dm_41513908" or not args.did.startswith("dm_"):
        raise ValueError("Use a separate review demo")
    base = args.base.rstrip("/")
    out = Path(args.output).resolve(); out.mkdir(parents=True, exist_ok=True)
    if (out / "receipt.json").exists():
        raise ValueError("Use a new output directory to preserve previous evidence")
    repo = Path(__file__).resolve().parents[1]
    hashes = {name:digest((repo/name).read_bytes()) for name in SOURCES}
    errors, writes, external, websockets, rows, audio = [], [], [], [], [], []
    bundles = []; screens=[]; browser_sources={}
    baseline = json.loads(Path(args.baseline_bundle).read_text()) if args.baseline_bundle else None

    def guard(route):
        req=route.request; u=urlsplit(req.url)
        if req.method not in {"GET", "HEAD"}:
            writes.append({"method":req.method,"url":req.url}); route.abort()
        elif (u.scheme,u.hostname,u.port) != (parsed.scheme,parsed.hostname,parsed.port):
            external.append(req.url); route.abort()
        else:
            route.continue_()

    def websocket(route):
        websockets.append(route.url); route.close()

    with sync_playwright() as pw:
        chrome=os.getenv("CHROME_BIN", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        browser=pw.chromium.launch(executable_path=chrome if Path(chrome).is_file() else None,
          headless=True,args=["--mute-audio","--disable-background-networking"])
        try:
            for width,height,flag in [(1440,1000,False),(1440,1000,True),(390,844,False),(390,844,True)]:
                viewport=f'{width}-{"flag" if flag else "default"}'
                context=browser.new_context(viewport={"width":width,"height":height},reduced_motion="no-preference")
                context.route("**/*",guard); context.route_web_socket("**/*",websocket)
                context.add_init_script("""window.__playAttempts=0; HTMLMediaElement.prototype.play=function(){window.__playAttempts++;throw Error('Renderer QA never plays media')};
                  speechSynthesis.speak=function(){window.__playAttempts++;throw Error('Renderer QA never speaks')};
                  if(navigator.mediaDevices)navigator.mediaDevices.getUserMedia=async()=>{throw Error('Renderer QA never records a microphone')};""")
                page=context.new_page(); page.on("pageerror",lambda error:errors.append(str(error)))
                page.goto(base+"/?mute=1"+("&presentation=walkthrough" if flag else "")+"#/play/"+args.did)
                page.wait_for_selector(".pl-welcome",timeout=20000)
                raw=page.evaluate("async id=>{const r=await fetch('/api/demos/'+id+'/bundle');if(!r.ok)throw Error('Missing Bundle');return r.text()}",args.did)
                bundle=json.loads(raw); bundles.append(digest(raw.encode()))
                if len(bundles)==1:
                    (out/"bundle.json").write_text(raw)
                    urls=list(dict.fromkeys(l["audio"] for s in bundle["slides"] for l in s.get("lines",[]) if l.get("audio")))
                    audio=page.evaluate(AUDIO,urls)
                    for name in SOURCES:
                        text=page.evaluate("async path=>(await fetch('/'+path)).text()",name)
                        browser_sources[name]=digest(text.encode())
                page.evaluate(SETUP,bundle)
                for index,slide in enumerate(bundle["slides"]):
                    lines=slide.get("lines",[])
                    earlier=None
                    for line_index in range(len(lines)) if lines else [-1]:
                        page.evaluate(SHOW,{"index":index,"line":line_index})
                        m=page.evaluate(METRICS)
                        line=lines[line_index] if lines else None
                        # A spoken invitation/CTA need not invent a new factual
                        # label; its already-revealed reviewed tags stay visible.
                        current=[c for c in slide.get("callouts",[]) if c.get("reveal_on_line",0)==line_index
                                 or line and not line.get("fact_ids") and c.get("reveal_on_line",0)<=line_index]
                        visible_ids={l["id"] for l in m["labels"] if l["inside"]}
                        media_ids={x["image_id"] for x in slide.get("media",[])}
                        clip=next((a for a in audio if line and a["url"]==line.get("audio")),None)
                        old_labels={l["id"]:l["rect"] for l in earlier["labels"]} if earlier else {}
                        stable_labels=all(all(abs(l["rect"][key]-old_labels[l["id"]][key])<=1 for key in ("x","y","w","h"))
                                          for l in m["labels"] if l["id"] in old_labels)
                        checks={
                            "nonempty_loaded_picture":bool(m["images"]) and all(i["complete"] and i["naturalWidth"]>0 for i in m["images"]),
                            "only_reviewed_images":bool(media_ids) and all(i["image_id"] in media_ids for i in m["images"]),
                            "pictures_inside_slide":all(i["inside"] for i in m["images"]),
                            "current_line_has_visible_tag":not line or bool(current) and any(c["id"] in visible_ids for c in current),
                            "tag_text_and_citations_from_slide":all(any(c["id"]==l["id"] and c["text"] in l["text"] for c in slide.get("callouts",[])) for l in m["labels"]),
                            "no_long_paragraph_page":m["paragraphPages"]==0,
                            "no_page_overflow":m["scrollWidth"]<=width,
                            "heading_inside_slide":m["headingInside"],
                            "footer_inside_slide":m["footerInside"],
                            "labels_inside_slide":all(l["inside"] for l in m["labels"]),
                            "labels_do_not_overlap":not m["labelsOverlap"],
                            "labels_clear_heading_footer":not m["labelsCoverHeading"] and not m["labelsCoverFooter"],
                            "slide_uses_sans_font":bool(m["fonts"]) and all(not any(t in f["font"].lower() for t in ("georgia","times","source serif")) for f in m["fonts"]),
                            "no_gallery_replaces_current_slide":not m["galleryVisible"],
                            "earlier_tags_do_not_move_when_next_line_reveals":stable_labels,
                            "recorded_line_decodes_at_declared_duration":not line or bool(clip) and abs(clip["duration"]-line.get("duration",0))<=.12,
                            "published_content_unchanged":m["sourceUnchanged"],
                        }
                        m.update(viewport=viewport,slide_id=slide["id"],line_id=line.get("id") if line else None,line_index=line_index,checks=checks)
                        rows.append(m)
                        earlier=m
                        filename=f'{viewport}-{slide["id"]}-line{line_index}.png'
                        page.screenshot(path=str(out/filename)); screens.append(filename)
                if page.evaluate("window.__playAttempts"):
                    errors.append("Unexpected attempt to play audio")
                context.close()
        finally:
            browser.close()
    (out/"audio.json").write_text(json.dumps(audio,indent=2)+"\n")
    baseline_same=baseline is None or speech_manifest(baseline)==speech_manifest(bundle)
    final={name:digest((repo/name).read_bytes()) for name in SOURCES}
    failures=[{"viewport":r["viewport"],"slide":r["slide_id"],"line":r["line_id"],"check":k} for r in rows for k,v in r["checks"].items() if not v]
    invariant_checks={"nonempty_slides":bool(rows),"nonempty_recorded_audio":bool(audio),"one_unchanged_bundle":len(set(bundles))==1,
      "speech_matches_pre_restoration_bundle":baseline_same,"source_files_stable":hashes==final,
      "served_source_matches_repository":hashes==browser_sources,"no_writes":not writes,"no_websockets":not websockets,"no_browser_errors":not errors}
    failures.extend({"check":key} for key,value in invariant_checks.items() if not value)
    count=sum(len(r["checks"]) for r in rows)+len(invariant_checks)
    receipt={"scope":"Production player shell and renderSlide/createWalkthrough adapter, published Bundle, sequential per-line reveals. Existing audio decoded only. No natural playback, microphone, model, session or lead QA claim.",
      "base":base,"demo_id":args.did,"speaking_slides":sum(bool(s.get('lines')) for s in bundle['slides']),"slide_count":len(bundle['slides']),
      "renders":len(rows),"checks":count,"passed":count-len(failures),"failures":failures,"source_hashes":hashes,"served_source_hashes":browser_sources,
      "bundle_sha256":bundles[0],"baseline_bundle":args.baseline_bundle,"speech_manifest_sha256":digest(json.dumps(speech_manifest(bundle),sort_keys=True).encode()),
      "baseline_bundle_sha256":digest(Path(args.baseline_bundle).read_bytes()) if args.baseline_bundle else None,
      "invariants":invariant_checks,"errors":errors,"blocked_writes":writes,"blocked_websockets":websockets,"blocked_external":external,
      "audio_clips":len(audio),"audio_played":False,"screenshots":screens,"rows":rows}
    (out/"receipt.json").write_text(json.dumps(receipt,indent=2)+"\n")
    try:
        from PIL import Image, ImageDraw
        for viewport in ("1440-default","1440-flag","390-default","390-flag"):
            selected=[p for p in screens if p.startswith(viewport+'-')]
            cellw,cellh,cols=360,285,4
            sheet=Image.new('RGB',(cellw*cols,cellh*((len(selected)+cols-1)//cols)),"#e7ecf0")
            draw=ImageDraw.Draw(sheet)
            for i,name in enumerate(selected):
                im=Image.open(out/name).convert('RGB');im.thumbnail((cellw-8,cellh-25))
                x=(i%cols)*cellw;y=(i//cols)*cellh;sheet.paste(im,(x+(cellw-im.width)//2,y+20));draw.text((x+5,y+3),name,fill='black')
            sheet.save(out/f'{viewport}-contact.jpg',quality=90)
    except ImportError:
        pass
    print(json.dumps({k:v for k,v in receipt.items() if k not in {'rows','screenshots','source_hashes','served_source_hashes'}},indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base",required=True);parser.add_argument("--did",required=True)
    parser.add_argument("--output",required=True);parser.add_argument("--baseline-bundle")
    raise SystemExit(run(parser.parse_args()))

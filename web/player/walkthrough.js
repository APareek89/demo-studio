// Middle-slide gallery presentation. Reviewed photos/captions remain the source;
// the existing player owns narration, navigation and interruption.
const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
const number = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;

// Retained pure geometry helpers keep their native-pixel cap/clamp contract.
// The player-only adapter applies these limits without changing saved coordinates.
export function walkthroughStopGeometry(callout, naturalWidth, renderedWidth) {
  const cap = Math.min(2.2, naturalWidth > 0 && renderedWidth > 0 ? naturalWidth / renderedWidth * 1.15 : 1);
  const part = callout?.part_box;
  const span = Math.max(number(part?.w), number(part?.h));
  const requested = part && span > 0 ? Math.max(1.15, 0.45 / span) : 1.5;
  const z = callout?.placement === 'overlay' && callout.anchor ? Math.min(requested, cap) : 1;
  // For z=1 the literal formula is negative: the effective pan range is zero.
  const lim = Math.max(0, 0.5 * (1 - 1 / z) - 0.01);
  return {z, cap, x: clamp(0.5 - number(callout?.anchor?.x, .5), -lim, lim),
    y: clamp(0.5 - number(callout?.anchor?.y, .5), -lim, lim), lim};
}
export function walkthroughFit(naturalWidth, naturalHeight, width, height) {
  const nw = Math.max(1, number(naturalWidth, width)), nh = Math.max(1, number(naturalHeight, height));
  const scale = Math.min(1, Math.max(1, width) / nw, Math.max(1, height) / nh);
  return {width: nw * scale, height: nh * scale, scale};
}

// Gallery presentation lives entirely inside the native slide element. It never
// advances a route, speaks, accesses the microphone, or changes reviewed data.
export function createWalkthrough({ enabled = true } = {}) {
  let catalogue = [], current = null;
  const views = new Set();
  const photos = slide => (Array.isArray(slide.media) ? slide.media : [{image_id:slide.image_id, image_url:slide.image_url}]).slice(0,2).filter(p => p.image_url);
  return {
    mount(slides = []) { catalogue = slides; },
    wrap(slide, view, options = {}) {
      const entries = photos(slide);
      // Native hero/closing hero, no-picture and non-DOM consumers retain their
      // original view. Align never instantiates this player-only adapter.
      if (!enabled || /^(hero_open|hero_close)$/.test(slide.kind) || !entries.length || !view.el?.append) {
        current?.cancel();current=null;return view;
      }
      const previous = current?.photo();
      const continuing = current?.frame();
      current?.cancel();
      const index = catalogue.findIndex(s => s.id === slide.id);
      const next = catalogue.slice(Math.max(0,index+1)).find(s => !/^(hero_open|hero_close)$/.test(s.kind) && photos(s).length);
      const controller = galleryView(slide, view, entries, previous, next ? photos(next)[0] : null, options, continuing);
      controller.onDispose = () => views.delete(controller);
      current = controller; views.add(controller);
      return controller.view;
    },
    resize() { for (const view of views) view.resize(); },
    freeze() { for (const view of views) view.cancel(); },
    pause() { for (const view of views) view.cancel(); },
    resume() {}, // The existing player resumes at its saved line, via prepareLine.
    reset() { for (const view of views) view.cancel(); current = null; },
    destroy() { for (const view of views) view.dispose(); views.clear(); current = null; },
  };
}

function galleryView(slide, native, entries, previous, next, options, continuing) {
  const node = (tag, cls, text) => { const el = document.createElement(tag); el.className = cls; if (text !== undefined) el.textContent = text; return el; };
  const ns = 'http://www.w3.org/2000/svg';
  const svg = tag => document.createElementNS(ns,tag);
  const surface = node('div','gallery-surface');
  surface.setAttribute('aria-label','Guided product gallery');
  const hall=node('div','gallery-hall'), floor=node('div','gallery-floor'), world=node('div','gallery-world');
  hall.append(floor,world);
  const focus=node('div','gallery-focus'), camera=node('div','gallery-camera');
  let image=node('img','gallery-image');
  image.alt=slide.title || 'Product view'; image.draggable=false;
  camera.append(image);
  const pointer=svg('svg'), leader=svg('path'), dot=svg('circle'), halo=svg('circle');
  pointer.setAttribute('class','gallery-pointer'); pointer.setAttribute('aria-hidden','true');
  dot.setAttribute('r','5'); halo.setAttribute('r','11'); pointer.append(leader,halo,dot);
  const secondary=node('button','gallery-secondary');secondary.type='button';secondary.hidden=true;
  const secondaryDisclosure=node('span','gallery-secondary-disclosure','Illustration');secondaryDisclosure.hidden=true;
  let secondaryImage=node('img','gallery-secondary-image'), secondaryEntry=null;
  secondaryImage.alt='Other reviewed product photo';secondaryImage.draggable=false;secondary.append(secondaryImage,secondaryDisclosure);
  const captions=node('div','gallery-captions'), disclosure=node('span','gallery-disclosure');
  focus.append(camera,pointer,secondary,captions,disclosure); surface.append(hall,focus); native.el.append(surface); native.el.classList.add('gallery-slide');
  const reduced=typeof matchMedia==='function' ? matchMedia('(prefers-reduced-motion: reduce)') : {matches:false};
  const animations=new Set(), pending=new Set();
  let epoch=0, dead=false, active=entries[0], line=-1, prepared=-1, preparing=false, selected=null, cards=[], target=0, ready=false, settled=false, inherited=false, geometry=null, lastSize='', fallback=false;
  const allLabels=(slide.callouts || []).filter(c => typeof c.text==='string' && c.text.trim());
  const state=value => {surface.dataset.state=value;};
  const labelOwner=c => entries.find(p => p.image_id===c.image_id) || entries[0];
  const trusted=c => !!c && labelOwner(c)===active && c.placement==='overlay' && !active.proxy && c.anchor &&
    ['x','y'].every(k => Number.isFinite(c.anchor[k]) && c.anchor[k]>=0 && c.anchor[k]<=1);
  const photosFor=i => {
    const mapped=entries.find(p=>p.image_id===slide.media_by_line?.[i]);if(mapped)return [mapped];
    const eligible=entries.filter(p=>number(p.from_line)<=i), latest=Math.max(...eligible.map(p=>number(p.from_line)));
    return eligible.length?eligible.filter(p=>number(p.from_line)===latest):[entries[0]];
  };
  const photoFor=i => photosFor(i).at(-1);
  const bounds=() => ({w:surface.clientWidth || 1,h:surface.clientHeight || 1});
  const depth=() => Math.max(500,bounds().w*.56);
  const pose=(i,flat=false) => `translate(-50%,-50%) translate3d(${flat?0:(i%2?1:-1)*Math.min(265,bounds().w*.25)}px,0,${-i*depth()}px) rotateY(${flat?0:(i%2?-30:30)}deg)`;
  const worldPose=i => `translateZ(${i*depth()}px)`;
  function setPreparing(value) {
    preparing=value;secondary.disabled=value;for(const label of captions.children)label.disabled=value;
  }
  function cancel() {
    epoch++; for(const animation of animations) {
      // Preserve the displayed frame while the player pauses or takes a turn.
      try { animation.commitStyles(); } catch (_) {} animation.cancel();
    }
    animations.clear(); for(const release of [...pending]) release(false); pending.clear(); prepared=-1;setPreparing(false);
    if (!dead) state('frozen');
  }
  async function move(el,to,ms,owner) {
    if(dead || owner!==epoch)return false;
    if(reduced.matches || !el.animate) {Object.assign(el.style,to);return true;}
    const from=Object.fromEntries(Object.keys(to).map(k => [k,getComputedStyle(el)[k]]));
    const animation=el.animate([from,to],{duration:ms,easing:'cubic-bezier(.3,.7,.22,1)',fill:'forwards'});animations.add(animation);
    try {await animation.finished;if(dead || owner!==epoch)return false;Object.assign(el.style,to);return true;}
    catch (_) {return false;} finally {animations.delete(animation);animation.cancel();}
  }
  function loadPicture(entry,owner,currentImage,attach,awaitPlayback=null) {
    if(currentImage.getAttribute('src')===entry.image_url && currentImage.complete && currentImage.naturalWidth)return Promise.resolve(true);
    return new Promise(resolve => {
      // A pending photo must not replace the frozen frame after cancellation.
      // Commit the already-loaded element only while this presentation owns it.
      const candidate=node('img',currentImage.className);candidate.alt=currentImage.alt;candidate.draggable=false;
      let timer,done=false;
      const finish=async ok => {
        if(done)return;done=true;clearTimeout(timer);candidate.removeEventListener('load',loaded);candidate.removeEventListener('error',failed);pending.delete(finish);
        if(ok && awaitPlayback && !await awaitPlayback())ok=false;
        const owned=ok && owner===epoch && !dead;
        if(owned)attach(candidate);
        resolve(owned);
      };
      const loaded=()=>finish(candidate.naturalWidth>0), failed=()=>finish(false);
      pending.add(finish);candidate.addEventListener('load',loaded);candidate.addEventListener('error',failed);
      // A broken asset must never prevent narration or turn controls. This is a
      // load deadline, not an autoplay/slide-advance timer.
      timer=setTimeout(failed,2500);candidate.src=entry.image_url;
      if(candidate.complete)finish(candidate.naturalWidth>0);
    });
  }
  const loadPhoto=(entry,owner,hidePrevious=false,awaitPlayback=null)=>loadPicture(entry,owner,image,candidate=>{
    if(hidePrevious){captions.style.opacity='0';pointer.style.opacity='0';}
    camera.replaceChildren(candidate);image=candidate;
  },awaitPlayback);
  function showSecondary(i,owner,awaitPlayback=null) {
    const owners=photosFor(i);
    secondaryEntry=owners.length>1?owners.find(entry=>entry!==active) || null:null;
    secondary.hidden=!secondaryEntry;
    if(!secondaryEntry)return Promise.resolve(true);
    secondaryDisclosure.hidden=!secondaryEntry.proxy;
    secondary.dataset.imageId=secondaryEntry.image_id || '';
    secondary.setAttribute('aria-label',`Show reviewed photo ${entries.indexOf(secondaryEntry)+1}`);
    const loading=loadPicture(secondaryEntry,owner,secondaryImage,candidate=>{secondary.replaceChildren(candidate,secondaryDisclosure);secondaryImage=candidate;secondary.style.visibility='visible';},awaitPlayback);
    secondary.style.visibility=secondaryImage.getAttribute('src')===secondaryEntry.image_url?'visible':'hidden';
    return loading;
  }
  function useNativeFallback() {
    fallback=true;surface.hidden=true;native.el.classList.remove('gallery-slide');state('fallback');
  }
  function buildHall(from) {
    const sequence=[];
    if(from?.image_url && from.image_url!==active.image_url)sequence.push(from);
    target=sequence.length;sequence.push(active);
    const later=entries.find(p=>p.image_url!==active.image_url && p.image_url!==from?.image_url) || next;
    if(later?.image_url && later.image_url!==active.image_url)sequence.push(later);
    world.replaceChildren();cards=sequence.map((entry,i)=>{
      const card=node('div','gallery-frame'), mat=node('div','gallery-mat'), img=node('img','gallery-frame-image');
      img.src=entry.image_url;img.alt='';img.draggable=false;mat.append(img);card.append(mat);world.append(card);card.style.transform=pose(i,i===0&&target>0);card.style.opacity=i===target?'1':'.65';return card;
    });
    world.style.transform=worldPose(0);focus.style.opacity='0';focus.classList.remove('visible');pointer.style.opacity='0';state('gallery');
  }
  function labels(i, id=null) {
    const group=photosFor(i), owners=group.length>1?group:[active];
    const eligible=allLabels.filter(c=>owners.includes(labelOwner(c)) && number(c.reveal_on_line)<=i);
    const activeLabels=eligible.filter(c=>labelOwner(c)===active), currentLabels=activeLabels.filter(c=>number(c.reveal_on_line)===i);
    selected=activeLabels.find(c=>c.id===id) || currentLabels.find(trusted) || currentLabels.at(-1) || activeLabels.find(trusted) || activeLabels.at(-1) || null;
    captions.replaceChildren();
    for(const c of eligible) {
      const label=node('button','gallery-tag'), badge=node('span','gallery-number',String(allLabels.indexOf(c)+1)), copy=node('span','gallery-feature-copy');
      label.type='button';label.disabled=preparing;label.dataset.id=c.id;label.classList.toggle('active',c===selected);
      if(c.part && String(c.part).toLowerCase()!==c.text.toLowerCase())copy.append(node('span','gallery-part',c.part));
      copy.append(node('span','gallery-feature-text',c.text));label.append(badge,copy);
      label.addEventListener('click',()=>{if(!preparing && !dead && !fallback)highlight(c.id,line);});captions.append(label);
    }
    captions.hidden=!eligible.length;
    const currentLabel=[...captions.children].find(el=>el.dataset.id===selected?.id);
    if(currentLabel && captions.clientHeight) {
      const top=currentLabel.offsetTop, bottom=top+currentLabel.offsetHeight;
      if(bottom>captions.scrollTop+captions.clientHeight)captions.scrollTop=bottom-captions.clientHeight;
      else if(top<captions.scrollTop)captions.scrollTop=top;
    }
    disclosure.textContent=active.proxy?'Illustrative product view':''; disclosure.hidden=!active.proxy;
  }
  function fit() {
    const {w,h}=bounds();const iw=image.naturalWidth || native.images?.[entries.indexOf(active)]?.naturalWidth || w, ih=image.naturalHeight || native.images?.[entries.indexOf(active)]?.naturalHeight || h;
    const k=Math.min(1,w/iw,h/ih), pw=iw*k,ph=ih*k;
    Object.assign(camera.style,{width:pw+'px',height:ph+'px',left:(w-pw)/2+'px',top:(h-ph)/2+'px'});
    return {w,h,pw,ph,iw};
  }
  function focusGeometry() {
    const {w,h,pw,ph,iw}=fit(), anchored=trusted(selected);
    const helper=walkthroughStopGeometry(anchored?selected:null,iw,pw);
    const z=reduced.matches?1:Math.max(1,helper.z), x=anchored?selected.anchor.x:.5,y=anchored?selected.anchor.y:.5;
    let dx=anchored?w*.40-(w/2+(x-.5)*pw*z):0,dy=anchored?h*.40-(h/2+(y-.5)*ph*z):0;
    dx=clamp(dx,-Math.max(0,(pw*z-w)/2),Math.max(0,(pw*z-w)/2));dy=clamp(dy,-Math.max(0,(ph*z-h)/2),Math.max(0,(ph*z-h)/2));
    // On narrow stages reserve the on-image caption band, keeping the actual
    // anchored feature above it rather than under the label.
    if(anchored && w<620 && !captions.hidden){const py=h/2+(y-.5)*ph*z+dy;dy+=clamp(py,20,Math.max(20,captions.offsetTop-24))-py;}
    return {z,x:w/2+(x-.5)*pw*z+dx,y:h/2+(y-.5)*ph*z+dy,transform:`translate(${dx}px,${dy}px) scale(${z})`,anchored};
  }
  function drawPointer() {
    pointer.style.opacity='0';if(!geometry?.anchored || captions.hidden || !selected)return;
    const label=[...captions.children].find(el=>el.dataset.id===selected.id);if(!label)return;
    const s=surface.getBoundingClientRect(),b=label.getBoundingClientRect(),rail=captions.getBoundingClientRect(),x=geometry.x,y=geometry.y;
    if(b.bottom<=rail.top || b.top>=rail.bottom)return;
    if(x<0 || y<0 || x>s.width || y>s.height || (x>=b.left-s.left-12 && x<=b.right-s.left+12 && y>=b.top-s.top-12 && y<=b.bottom-s.top+12))return;
    const narrow=s.width<620,ex=narrow?clamp(x,b.left-s.left+12,b.right-s.left-12):b.left-s.left,ey=narrow?b.top-s.top:b.top-s.top+b.height/2;
    leader.setAttribute('d',`M ${x} ${y} L ${narrow?x:(x+ex)/2} ${narrow?(y+ey)/2:y} L ${ex} ${ey}`);
    for(const el of [dot,halo]){el.setAttribute('cx',x);el.setAttribute('cy',y);}pointer.style.opacity='1';
  }
  function frameTransform() {
    const s=surface.getBoundingClientRect(),f=cards[target]?.getBoundingClientRect();
    return f && s.width && s.height ? `translate(${f.left+f.width/2-s.left-s.width/2}px,${f.top+f.height/2-s.top-s.height/2}px) scale(${f.width/s.width},${f.height/s.height})` : 'none';
  }
  async function showInstant(i,id=null,entry=null,awaitPlayback=null) {
    const owner=epoch;
    if(awaitPlayback && !await awaitPlayback())return false;
    if(dead || owner!==epoch)return false;settled=false;inherited=false;active=entry || photoFor(i);if(id){const c=allLabels.find(c=>c.id===id);if(c)active=labelOwner(c);}
    const loading=Promise.all([loadPhoto(active,owner,false,awaitPlayback),showSecondary(i,owner,awaitPlayback)]);
    // Answer captions stay immediate; a different pending picture cannot carry
    // their pointer or inherit a previous photo while its bytes are loading.
    camera.style.visibility=image.getAttribute('src')===active.image_url?'visible':'hidden';
    line=i;surface.dataset.lineIndex=String(i);surface.dataset.imageId=active.image_id || '';labels(i,id);
    focus.style.transform='translate(0px,0px) scale(1)';focus.style.opacity='1';focus.classList.add('visible');
    captions.style.opacity='1';geometry=focusGeometry();camera.style.transform=geometry.transform;drawPointer();ready=true;state('ready');
    if(camera.style.visibility==='hidden')pointer.style.opacity='0';
    return loading.then(async results=>{
      if(awaitPlayback && !await awaitPlayback())return false;
      if(dead || owner!==epoch)return false;
      if(results.some(ok=>!ok)){
        useNativeFallback();
        return native.focusMedia?.(active.image_id,{lineIndex:i,calloutId:id,awaitPlayback}) ?? false;
      }
      camera.style.visibility='visible';geometry=focusGeometry();camera.style.transform=geometry.transform;drawPointer();settled=true;
      return true;
    });
  }
  async function prepareLine(i,awaitPlayback=null) {
    if(dead)return false;
    const from=active, wasReady=ready && focus.classList.contains('visible');
    cancel();const owner=epoch, entry=photoFor(i);line=i;settled=false;setPreparing(true);
    try {
    if(fallback)return true;
    const photoLoaded=await loadPhoto(entry,owner,true,awaitPlayback);
    if(awaitPlayback && !await awaitPlayback())return false;
    if(!photoLoaded){
      if(dead || owner!==epoch)return false;
      useNativeFallback();return true;
    }
    if(dead || owner!==epoch)return false;
    active=entry;surface.dataset.lineIndex=String(i);surface.dataset.imageId=active.image_id || '';camera.style.visibility='visible';
    const secondaryLoaded=await showSecondary(i,owner,awaitPlayback);
    if(awaitPlayback && !await awaitPlayback())return false;
    if(!secondaryLoaded){
      if(dead || owner!==epoch)return false;
      useNativeFallback();return true;
    }
    if(dead || owner!==epoch)return false;
    labels(i);inherited=false;
    const samePhoto=wasReady && from.image_url===active.image_url;
    if(!samePhoto) {
      captions.style.opacity='0';pointer.style.opacity='0';
      buildHall(wasReady?from:previous);fit();camera.style.transform='translate(0px,0px) scale(1)';
      if(target>0){state('returning');if(!await move(cards[0],{transform:pose(0)},400,owner))return false;}
      state('walking');if(!await move(world,{transform:worldPose(target)},750,owner))return false;
      state('straightening');if(!await move(cards[target],{transform:pose(target,true)},450,owner))return false;
      focus.style.transform=frameTransform();focus.style.opacity='0';focus.classList.add('visible');state('entering');
      if(!await move(focus,{transform:'translate(0px,0px) scale(1)',opacity:'1'},600,owner))return false;
    }
    const destination=focusGeometry();
    // A new sentence/slide is not a new picture. Keep the settled camera unless
    // the next reviewed feature actually needs a different focus.
    if(!samePhoto || geometry?.transform!==destination.transform) {
      captions.style.opacity='0';pointer.style.opacity='0';state('focusing');
      if(!await move(camera,{transform:destination.transform},600,owner))return false;
    }
    if(dead || owner!==epoch)return false;
    geometry=focusGeometry();camera.style.transform=geometry.transform;
    captions.style.opacity='1';drawPointer();ready=true;settled=true;prepared=i;state('ready');return true;
    } finally {if(owner===epoch)setPreparing(false);}
  }
  function layout() {
    native.layout();if(dead)return;
    const heading=native.el.querySelector('.slide-heading'),foot=native.el.querySelector('.slide-foot');
    const top=heading ? heading.offsetTop+heading.offsetHeight+12 : 12;
    const bottom=foot ? Math.max(8,native.el.clientHeight-foot.offsetTop+8) : 12;
    Object.assign(surface.style,{top:top+'px',bottom:bottom+'px'});
    surface.classList.toggle('compact',surface.clientWidth<620);
  }
  function resize() {
    if(dead || !native.el.isConnected)return;
    layout();const size=`${surface.clientWidth}:${surface.clientHeight}`;if(size===lastSize)return;lastSize=size;
    // Finish current moves into newly calculated geometry, without resolving an
    // old line as playable. The waiting prepareLine then uses current dimensions.
    for(const a of animations){try{a.finish();}catch(_) {}}
    if(ready && !inherited){geometry=focusGeometry();camera.style.transform=geometry.transform;drawPointer();}
    else {cards.forEach((c,i)=>c.style.transform=pose(i));world.style.transform=worldPose(target);}
  }
  function highlight(id,index=99) {
    native.highlight(id);if(!id || dead || fallback)return;
    cancel();showInstant(index,id);
  }
  async function focusMedia(imageId,{lineIndex=99,calloutId=null,awaitPlayback=null}={}) {
    const entry=entries.find(p=>p.image_id===imageId);
    if(!entry || dead)return Promise.resolve(false);
    const owner=epoch;
    if(awaitPlayback && !await awaitPlayback())return false;
    if(dead || owner!==epoch)return false;
    if(fallback)return Promise.resolve(native.focusMedia?.(imageId,{lineIndex,calloutId,awaitPlayback}) ?? false);
    const label=allLabels.find(c=>c.id===calloutId && labelOwner(c)===entry);
    cancel();native.setRevealed(lineIndex);native.highlight(label?.id || null);
    return showInstant(lineIndex,label?.id || null,entry,awaitPlayback);
  }
  secondary.addEventListener('click',()=>{if(preparing || !secondaryEntry || dead || fallback)return;const entry=secondaryEntry;cancel();showInstant(line,null,entry);});
  captions.addEventListener('scroll',()=>{if(!dead)drawPointer();},{passive:true});
  const ro=typeof ResizeObserver!=='undefined'?new ResizeObserver(resize):null;ro?.observe(native.el);ro?.observe(surface);
  const dispose=()=>{if(dead)return;cancel();dead=true;ro?.disconnect();surface.remove();controller.onDispose?.();};
  buildHall(previous);
  const carried=entries.find(entry=>entry.image_url===continuing?.image_url);
  if(carried) {
    // Carry only a fully loaded, settled frame from the immediately preceding
    // gallery. The old slide keeps its own image through the normal crossfade.
    active=carried;image=continuing.image.cloneNode(true);image.alt=slide.title || 'Product view';camera.replaceChildren(image);
    camera.style.cssText=continuing.cameraStyle;geometry={...continuing.geometry};
    focus.style.transform='translate(0px,0px) scale(1)';focus.style.opacity='1';focus.classList.add('visible');
    // Crossfading two copies of the same photo would briefly wash out its
    // pixels. Replace this middle slide at full opacity; new photos still fade.
    native.el.style.transition='none';native.el.style.opacity='1';
    ready=true;settled=true;inherited=true;surface.dataset.imageId=active.image_id || '';state('ready');
  }
  layout();
  const view={...native,prepareLine,layout,
    setRevealed(i){native.setRevealed(i);if(i>=0 && !fallback && !dead && prepared!==i){cancel();showInstant(i);} },
    highlight,focusMedia,
    setImage(...args){cancel();fallback=true;surface.hidden=true;native.el.classList.remove('gallery-slide');native.setImage(...args);},
    destroy(){dispose();native.destroy();},
  };
  const controller={view,cancel,dispose,resize,photo:()=>({...active}),
    frame:()=>!dead && !fallback && settled && ready && image.complete && image.naturalWidth && image.getAttribute('src')===active.image_url
      ? {image_url:active.image_url,image,cameraStyle:camera.style.cssText,geometry:{...geometry}} : null};
  return controller;
}

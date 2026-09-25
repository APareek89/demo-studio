const $ = id => document.getElementById(id);
const data = await fetch('preview.json').then(r => { if (!r.ok) throw new Error('Preview unavailable'); return r.json(); });
const scenes = data.scenes, cards = [], anims = new Set(), audio = $('audio');
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
let index = 0, epoch = 0, playing = false, paused = false, phase = 'gallery', audioDone = null, resumeAudio = null, releases = [], focusTransform = null;
let muted = new URLSearchParams(location.search).get('mute') === '1';
const cameraReview = [
  {x:.50,y:.56,z:1.72,title:'Diamond-cut alloy wheel',detail:'Wheel designs and finishes depend on the chosen trim.',note:'Confirm the equipment on your selected trim.'},
  {x:.715,y:.825,z:1.72,title:'Front headlamp',detail:'Projector or LED equipment depends on the variant.',note:'Illustration; confirm the equipment on your selected trim.'},
  {x:.52,y:.54,z:1.38,title:'60:40 split rear seat',detail:'Fold one section while the other remains available.',note:'Check the seating and luggage arrangement in person.'},
  {x:.37,y:.57,z:1.66,title:'Connected display',detail:'Wireless mirroring uses an adapter on specified trims.',note:'Confirm compatibility with your phone.'},
  {x:.664,y:.235,z:1.72,title:'Panoramic roof',detail:'Voice-enabled panoramic roof on specified trims.',note:'Illustration; availability depends on the selected trim.'},
  {x:.52,y:.53,z:1.62,title:'Wireless charging pad',detail:'For compatible smartphones, on specified trims.',note:'Check your device before choosing the feature.'}
];
const fmt = i => String(i+1).padStart(2,'0');
function dimensions(){ const r=$('stage').getBoundingClientRect(); return {w:r.width,h:r.height}; }
function pose(i,flat=false){ const {w}=dimensions(); const depth=Math.max(650,w*.56), side=Math.min(280,w*.29), sign=i%2?1:-1; return `translate3d(${flat?0:sign*side}px,0,${-i*depth}px) rotateY(${flat?0:-sign*30}deg)`; }
function worldPose(i){const {w}=dimensions();return `translateZ(${i*Math.max(650,w*.56)}px)`;}
function setPhase(value,label){phase=value;$('phase').textContent=label;document.documentElement.dataset.phase=value;document.documentElement.dataset.scene=index;}
function title(){ $('count').textContent=fmt(index);$('title').textContent=scenes[index].title;$('featureNumber').textContent=fmt(index);cards.forEach((card,i)=>card.classList.toggle('current',i===index));[...$('chapters').children].forEach((el,i)=>{el.className=i===index?'active':i<index?'done':'';el.setAttribute('aria-current',i===index?'step':'false');});}
function updateSound(){audio.muted=muted;$('sound').textContent=muted?'Sound off':'Sound on';$('sound').setAttribute('aria-label',muted?'Turn sound on':'Mute sound');$('sound').setAttribute('aria-pressed',String(!muted));}
function controls(){ $('play').textContent=playing&&!paused?'Pause':playing?'Resume':'Play';$('play').setAttribute('aria-label',playing&&!paused?'Pause preview':playing?'Resume preview':'Play preview');$('app').classList.toggle('is-paused',paused);$('statusDot').classList.toggle('on',playing&&!paused);$('status').textContent=paused?'Paused':playing?'Guiding you':'Ready to guide you'; }
function waitGate(owner){return paused?new Promise(resolve=>releases.push(()=>resolve(owner===epoch))):Promise.resolve(owner===epoch);}
async function motion(el,to,duration,owner){
  if(!await waitGate(owner))return false;
  const from=Object.fromEntries(Object.keys(to).map(k=>[k,getComputedStyle(el)[k]]));
  const a=el.animate([from,to],{duration:reduced.matches?Math.min(duration,180):duration,easing:'cubic-bezier(.3,.7,.22,1)',fill:'forwards'});anims.add(a);if(paused)a.pause();
  try{await a.finished;if(owner!==epoch)return false;Object.assign(el.style,to);return true;}catch{return false;}finally{anims.delete(a);a.cancel();}
}
function pause(){if(!playing)return;paused=!paused;for(const a of anims)paused?a.pause():a.play();if(paused)audio.pause();else{releases.splice(0).forEach(f=>f());resumeAudio?.();}controls();}
function cancel(){epoch++;playing=false;paused=false;for(const a of anims)a.cancel();anims.clear();audio.pause();audioDone?.(false);audioDone=null;resumeAudio=null;releases.splice(0).forEach(f=>f());$('audioProgress').style.width='0%';controls();}
function hideTag(){ $('featureCard').style.opacity='0';$('featureCard').classList.remove('visible');$('pointer').style.opacity='0'; }
function resetGallery(){hideTag();$('focusView').classList.remove('visible');$('focusView').style.opacity='0';$('focusView').setAttribute('aria-hidden','true');$('world').style.transform=worldPose(index);cards.forEach((c,i)=>{c.style.transform=pose(i);c.style.opacity=i<index?'0':i===index?'1':i===index+1?'.75':'.38';});title();setPhase('gallery','The gallery is ready');}
function fit(){const {w,h}=dimensions();const s=scenes[index];const scale=Math.min(w/s.width,h/s.height);const iw=s.width*scale,ih=s.height*scale;const plane=$('imagePlane');Object.assign(plane.style,{width:iw+'px',height:ih+'px',left:(w-iw)/2+'px',top:(h-ih)/2+'px'});return{w,h,iw,ih};}
function focusGeometry(){const {w,h,iw,ih}=fit(),review=cameraReview[index];const z=reduced.matches?1:Math.min(review.z,scenes[index].width/iw*1.15);const target={x:w*.40,y:h*(w<540?.30:.43)};let dx=target.x-(w/2+(review.x-.5)*iw*z),dy=target.y-(h/2+(review.y-.5)*ih*z);
 const clamp=(v,lo,hi)=>Math.max(lo,Math.min(hi,v));
 dx=clamp(dx,-Math.max(0,(iw*z-w)/2),Math.max(0,(iw*z-w)/2));dy=clamp(dy,-Math.max(0,(ih*z-h)/2),Math.max(0,(ih*z-h)/2));
 // On a phone, keep the photographed feature above the on-image caption.
 if(w<540){const limit=$('featureCard').offsetTop-24;const point=h/2+(review.y-.5)*ih*z+dy;dy+=clamp(point,24,Math.max(24,limit))-point;}
 return{z,dx,dy,x:w/2+(review.x-.5)*iw*z+dx,y:h/2+(review.y-.5)*ih*z+dy,transform:`translate(${dx}px,${dy}px) scale(${z})`};}
function drawPointer(){if(!focusTransform)return;const stage=$('stage').getBoundingClientRect(),card=$('featureCard').getBoundingClientRect(),x=focusTransform.x,y=focusTransform.y;const cx=card.left-stage.left,cy=card.top-stage.top+Math.min(43,card.height/2);const below=stage.width<540||y>card.top-stage.top-14;const endX=below?cx+card.width*.32:cx,endY=below?card.top-stage.top:cy;const elbowX=below?x:(x+endX)/2,elbowY=below?(y+endY)/2:y;
 $('leader').setAttribute('d',`M ${x} ${y} L ${elbowX} ${elbowY} L ${endX} ${endY}`);for(const id of ['point','halo']){$(id).setAttribute('cx',x);$(id).setAttribute('cy',y);}$('pointer').style.opacity='1';}
function cardTransform(){const outer=$('stage').getBoundingClientRect(),frame=cards[index].getBoundingClientRect();return `translate(${frame.left+frame.width/2-outer.left-outer.width/2}px,${frame.top+frame.height/2-outer.top-outer.height/2}px) scale(${frame.width/outer.width},${frame.height/outer.height})`;}
async function speak(line,owner){
 if(!await waitGate(owner))return false;$('speech').textContent=line.text;audio.src=line.audio;audio.muted=muted;audio.currentTime=0;
 return new Promise(resolve=>{
   let done=false;
   const finish=ok=>{if(done)return;done=true;audio.removeEventListener('ended',ended);audio.removeEventListener('error',error);if(audioDone===finish){audioDone=null;resumeAudio=null;}resolve(ok&&owner===epoch);};
   const ended=()=>finish(true);
   const error=e=>{if(done||owner!==epoch)return;if(e?.name==='AbortError'&&paused)return;finish(false);playing=false;controls();$('status').textContent='Recording unavailable';$('phase').textContent='Use Next to continue';};
   const start=()=>{if(done||owner!==epoch||paused)return;audio.play().catch(error);};
   audioDone=finish;resumeAudio=start;audio.addEventListener('ended',ended);audio.addEventListener('error',error);start();
 });
}
async function scene(owner){
 title();hideTag();setPhase('walking','Walking through the gallery');$('speech').textContent='';
 const motions=[motion($('world'),{transform:worldPose(index)},1450,owner)];cards.forEach((c,i)=>{motions.push(motion(c,{transform:pose(i),opacity:i<index?'0':i===index?'1':i===index+1?'.75':'.38'},1150,owner));});
 await Promise.all(motions);if(owner!==epoch)return false;
 setPhase('straightening','Turning to this feature');await motion(cards[index],{transform:pose(index,true)},900,owner);if(owner!==epoch)return false;
 const scene=scenes[index],image=$('focusImage');image.src=scene.image;image.alt=scene.title;try{await image.decode();}catch{}if(owner!==epoch)return false;fit();$('imagePlane').style.transform='translate(0px,0px) scale(1)';
 const fv=$('focusView');fv.style.transform=cardTransform();fv.style.opacity='0';fv.classList.add('visible');fv.setAttribute('aria-hidden','false');setPhase('entering','A closer look');await motion(fv,{transform:'translate(0px,0px) scale(1)',opacity:'1'},1000,owner);if(owner!==epoch)return false;
 const review=cameraReview[index];$('featureTitle').textContent=review.title;$('featureDetail').textContent=review.detail;$('featureNote').textContent=review.note;
 setPhase('focusing','Focusing on the feature');focusTransform=focusGeometry();await motion($('imagePlane'),{transform:focusTransform.transform},1400,owner);if(owner!==epoch)return false;
 $('featureCard').classList.add('visible');drawPointer();await motion($('featureCard'),{opacity:'1'},280,owner);if(owner!==epoch)return false;setPhase('narrating','Priya is explaining this feature');
 for(const line of scene.lines){if(!await speak(line,owner))return false;}
 hideTag();setPhase('returning','Returning to the gallery');await motion($('imagePlane'),{transform:'translate(0px,0px) scale(1)'},650,owner);if(owner!==epoch)return false;await motion(fv,{transform:cardTransform(),opacity:'0'},900,owner);fv.classList.remove('visible');fv.setAttribute('aria-hidden','true');await motion(cards[index],{transform:pose(index)},500,owner);return owner===epoch;
}
async function play(from=index){cancel();index=from;const owner=epoch;playing=true;controls();$('startCard').classList.add('hidden');resetGallery();
 while(owner===epoch&&index<scenes.length){if(!await scene(owner))return;if(index===scenes.length-1)break;index++;}
 if(owner!==epoch)return;playing=false;controls();setPhase('complete','You have reached the end of the gallery');$('status').textContent='Preview complete';$('speech').textContent='That’s the visual walkthrough. Replay it, or choose a feature to look again.';$('startCard').querySelector('h2').textContent='Take another look.';$('start').innerHTML='Replay the gallery <span>↻</span>';$('startCard').classList.remove('hidden');
}
scenes.forEach((s,i)=>{const card=document.createElement('div');card.className='frame';const mat=document.createElement('div');mat.className='mat';const img=new Image();img.src=s.image;img.alt=s.title;mat.append(img);const label=document.createElement('div');label.className='frame-label';const number=document.createElement('small');number.textContent=fmt(i);label.append(number,document.createTextNode(s.title));card.append(mat,label);$('world').append(card);cards.push(card);const button=document.createElement('button');button.title=s.title;button.setAttribute('aria-label',`View ${s.title}`);button.onclick=()=>play(i);$('chapters').append(button);});
$('start').onclick=()=>play(phase==='complete'?0:index);$('play').onclick=()=>playing?pause():play(phase==='complete'?0:index);$('next').onclick=()=>play((index+1)%scenes.length);$('previous').onclick=()=>play((index-1+scenes.length)%scenes.length);$('sound').onclick=()=>{muted=!muted;updateSound();};$('back').onclick=()=>{cancel();resetGallery();$('startCard').classList.add('hidden');$('speech').textContent='Choose a chapter, or press Play to continue the gallery.';};$('fullscreen').onclick=()=>document.fullscreenElement?document.exitFullscreen():$('app').requestFullscreen().catch(()=>{});
audio.ontimeupdate=()=>{$('audioProgress').style.width=Number.isFinite(audio.duration)&&audio.duration>0?Math.min(100,audio.currentTime/audio.duration*100)+'%':'0%';};
addEventListener('keydown',e=>{if(e.target.closest('button'))return;if(e.code==='Space'){e.preventDefault();$('play').click();}if(e.key==='ArrowRight')$('next').click();if(e.key==='ArrowLeft')$('previous').click();});
let resizeFrame=0;addEventListener('resize',()=>{cancelAnimationFrame(resizeFrame);resizeFrame=requestAnimationFrame(()=>{
 // Restart an unfinished camera move rather than committing obsolete geometry.
 if(phase!=='narrating'){const complete=phase==='complete';cancel();resetGallery();if(complete)setPhase('complete','You have reached the end of the gallery');return;}
 if(playing&&!paused)pause();
 $('world').style.transform=worldPose(index);cards.forEach((c,i)=>c.style.transform=pose(i,i===index));
 fit();$('focusView').style.transform='translate(0px,0px) scale(1)';focusTransform=focusGeometry();$('imagePlane').style.transform=focusTransform.transform;drawPointer();
});});
document.addEventListener('visibilitychange',()=>{if(document.hidden&&playing&&!paused)pause();});
updateSound();resetGallery();
// Read-only state for review/QA; does not expose controls or call the app.
Object.defineProperty(window,'galleryPreview',{value:()=>({index,phase,playing,paused,muted,audioTime:audio.currentTime,animations:anims.size,scene:scenes[index].id,focus:focusTransform,epoch})});

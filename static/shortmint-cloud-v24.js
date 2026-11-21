/* ShortMint v25 — lightweight, smoothed cloud cursor on login and workspace.
   Decorative only. Cached cloud sprites are significantly cheaper than creating
   hundreds of per-frame gradients. Never blocks pointer or keyboard input. */
(() => {
  'use strict';
  if (document.getElementById('sm24-cloud-layer')) return;
  const canvas=document.createElement('canvas');
  canvas.id='sm24-cloud-layer';canvas.setAttribute('aria-hidden','true');
  document.body.appendChild(canvas);
  const ctx=canvas.getContext('2d',{alpha:true});
  if(!ctx){canvas.remove();return;}
  const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');
  const effectsEnabled=()=>{try{return localStorage.getItem('shortmint_cloud_enabled')!=='off' && localStorage.getItem('shortmint_reduced_motion')!=='on';}catch{return true;}};
  const particles=[];
  const MAX_PARTICLES=85;
  const tintsLight=[[244,155,120],[255,185,140],[237,183,177]];
  const tintsDark=[[255,177,134],[253,198,160],[255,160,128]];
  const spriteCache=new Map();
  const pointer={x:0,y:0,targetX:0,targetY:0,hasTarget:false,lastEmitX:null,lastEmitY:null,lastEmit:0};
  let activeFrame=0,lastFrame=0,width=0,height=0,scale=1,visible=!document.hidden;
  const random=(min,max)=>min+Math.random()*(max-min);
  function resize(){
    width=Math.max(1,window.innerWidth);height=Math.max(1,window.innerHeight);
    scale=Math.min(2,window.devicePixelRatio||1);
    canvas.width=Math.round(width*scale);canvas.height=Math.round(height*scale);
    canvas.style.width=width+'px';canvas.style.height=height+'px';
    ctx.setTransform(scale,0,0,scale,0,0);
  }
  resize();window.addEventListener('resize',resize,{passive:true});
  function lightMode(){return document.body.classList.contains('light-theme') ||
    !document.getElementById('auth-view')?.classList.contains('hidden');}
  function createSprite(rgb){
    const key=rgb.join(',');if(spriteCache.has(key))return spriteCache.get(key);
    const size=128, c=document.createElement('canvas');c.width=c.height=size;
    const gctx=c.getContext('2d');
    const cloudLobes=[[.48,.53,.35,1],[.31,.50,.24,.75],[.69,.46,.27,.8],[.54,.33,.25,.55],[.57,.67,.23,.52]];
    for(const [x,y,r,a] of cloudLobes){
      const grd=gctx.createRadialGradient(x*size,y*size,r*size*.08,x*size,y*size,r*size);
      grd.addColorStop(0,`rgba(${rgb[0]},${rgb[1]},${rgb[2]},${.38*a})`);
      grd.addColorStop(.45,`rgba(${rgb[0]},${rgb[1]},${rgb[2]},${.18*a})`);
      grd.addColorStop(1,`rgba(${rgb[0]},${rgb[1]},${rgb[2]},0)`);
      gctx.fillStyle=grd;gctx.fillRect(0,0,size,size);
    }
    spriteCache.set(key,c);return c;
  }
  function spawn(x,y,burst=false){
    const colors=lightMode()?tintsLight:tintsDark;
    const rgb=colors[Math.floor(Math.random()*colors.length)];
    const rad=burst?random(31,44):random(25,37);
    particles.push({x:x+random(-7,7),y:y+random(-7,7),vx:random(-.35,.35),vy:random(-.66,-.16),r:rad,
      age:0,duration:burst?random(720,1020):random(780,1200),alpha:burst?.8:random(.55,.82),sprite:createSprite(rgb)});
    if(particles.length>MAX_PARTICLES)particles.splice(0,particles.length-MAX_PARTICLES);
    requestFrame();
  }
  function requestFrame(){if(!activeFrame && visible)activeFrame=requestAnimationFrame(draw);}
  function draw(time){
    activeFrame=0;
    const dt=lastFrame?Math.min(35,time-lastFrame):16.7;lastFrame=time;
    ctx.clearRect(0,0,width,height);
    if(!visible || !effectsEnabled()){particles.length=0;pointer.hasTarget=false;return;}
    // Exponential smoothing is independent of the monitor's refresh rate.
    if(pointer.hasTarget && !reduced.matches){
      const oldX=pointer.x,oldY=pointer.y;
      const blend=1-Math.exp(-dt/52);
      pointer.x+=(pointer.targetX-pointer.x)*blend;
      pointer.y+=(pointer.targetY-pointer.y)*blend;
      const d=Math.hypot(pointer.x-(pointer.lastEmitX??oldX),pointer.y-(pointer.lastEmitY??oldY));
      if(d>=5 && time-pointer.lastEmit>=16){
        spawn(pointer.x,pointer.y,false);
        pointer.lastEmit=time;pointer.lastEmitX=pointer.x;pointer.lastEmitY=pointer.y;
      }
      if(Math.hypot(pointer.targetX-pointer.x,pointer.targetY-pointer.y)<.55){pointer.hasTarget=false;}
    }
    const factor=dt/16.7;
    for(let i=particles.length-1;i>=0;i--){
      const p=particles[i];p.age+=dt;
      const life=1-p.age/p.duration;
      if(life<=0){particles.splice(i,1);continue;}
      p.x+=p.vx*factor;p.y+=p.vy*factor;
      p.r+=.09*factor;
      ctx.globalAlpha=Math.min(1,life*1.6)*p.alpha;
      const radius=p.r*1.6;
      ctx.drawImage(p.sprite,p.x-radius,p.y-radius,radius*2,radius*2);
    }
    ctx.globalAlpha=1;
    if(pointer.hasTarget||particles.length)requestFrame();
  }
  function pointerMove(e){
    if(!visible || !effectsEnabled() || reduced.matches || e.pointerType==='touch')return;
    pointer.targetX=e.clientX;pointer.targetY=e.clientY;
    if(pointer.lastEmitX===null){pointer.x=e.clientX;pointer.y=e.clientY;
      pointer.lastEmitX=pointer.x;pointer.lastEmitY=pointer.y;spawn(pointer.x,pointer.y,false);}
    pointer.hasTarget=true;requestFrame();
  }
  window.addEventListener('pointermove',pointerMove,{passive:true,capture:true});
  window.addEventListener('pointerdown',e=>{
    if(!visible || !effectsEnabled())return;
    for(let i=0;i<(reduced.matches?3:9);i++)spawn(e.clientX,e.clientY,true);
  },{passive:true,capture:true});
  document.addEventListener('shortmint:visual-prefs',()=>{if(!effectsEnabled()){particles.length=0;pointer.hasTarget=false;pointer.lastEmitX=null;ctx.clearRect(0,0,width,height);}});
  window.addEventListener('blur',()=>{pointer.hasTarget=false;pointer.lastEmitX=null;});
  window.addEventListener('pointerout',e=>{if(!e.relatedTarget){pointer.hasTarget=false;pointer.lastEmitX=null;}});
  document.addEventListener('visibilitychange',()=>{
    visible=!document.hidden;
    if(!visible){particles.length=0;pointer.hasTarget=false;pointer.lastEmitX=null;
      if(activeFrame)cancelAnimationFrame(activeFrame);activeFrame=0;ctx.clearRect(0,0,width,height);}
  });
  canvas.dataset.shortmintCloud='global-smooth';
})();

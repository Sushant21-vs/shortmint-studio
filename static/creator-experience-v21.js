/* ShortMint Studio 21 — progressive login motion and admin navigation. No API changes. */
(()=>{
  'use strict';
  const pass = document.getElementById('auth-password');
  const reveal = document.getElementById('sm-auth-reveal');
  if (pass && reveal) reveal.addEventListener('click',()=>{
    const show = pass.type === 'password';
    pass.type=show?'text':'password';
    reveal.setAttribute('aria-pressed',String(show));
    reveal.setAttribute('aria-label',show?'Hide password':'Show password');
    pass.focus({preventScroll:true});
  });

  // Admin shortcuts scroll to existing panels; do not reload or mutate data.
  document.querySelectorAll('[data-sm-jump]').forEach(btn=>{
    btn.addEventListener('click',()=>{
      const target=document.getElementById(btn.dataset.smJump);
      target?.scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'});
    });
  });
  const refreshed=document.getElementById('sm-admin-sync');
  const adminRefresh=document.getElementById('admin-refresh');
  if(refreshed && adminRefresh){
    adminRefresh.addEventListener('click',()=>{refreshed.textContent='Checking saved records…';});
    const total=document.getElementById('admin-members');
    if(total && typeof MutationObserver !== 'undefined')new MutationObserver(()=>{
      refreshed.textContent='Current data · '+new Date().toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
    }).observe(total,{childList:true,characterData:true,subtree:true});
  }

  // Visible but non-blocking peach cloud trail for mouse, pen and touch.
  // This feature runs only on the login screen and does not touch auth state.
  const root=document.getElementById('auth-view');
  const canvas=document.getElementById('sm-cloud-canvas');
  if (!root || !canvas || !canvas.getContext) return;
  const reduceMotion=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const ctx=canvas.getContext('2d', {alpha:true});
  if(!ctx) return;
  let particles=[],raf=0,lastX=null,lastY=null,lastTime=0, width=0,height=0;
  const MAX_PARTICLES=76;
  function isLoginVisible(){
    return !root.classList.contains('hidden') && getComputedStyle(root).display!=='none';
  }
  function resize(){
    const ratio=Math.min(window.devicePixelRatio||1,2);
    width=window.innerWidth; height=window.innerHeight;
    canvas.width=Math.round(width*ratio); canvas.height=Math.round(height*ratio);
    canvas.style.width=width+'px'; canvas.style.height=height+'px';
    ctx.setTransform(ratio,0,0,ratio,0,0);
  }
  resize();window.addEventListener('resize',resize,{passive:true});
  // Puffs are built from several soft radial lobes rather than a single faint spot.
  function puff(x,y,burst=false){
    const speed=burst?1.7:.9;
    const r=(burst?18:15)+Math.random()*(burst?17:14);
    particles.push({
      x:x+(Math.random()-.5)*14, y:y+(Math.random()-.5)*14,
      vx:(Math.random()-.5)*speed,vy:-.2-Math.random()*.8,
      r,life:1,decay:burst?.018+Math.random()*.009:.026+Math.random()*.011,
      tint:Math.random()<.22?[245,148,105]:Math.random()<.67?[247,189,166]:[217,191,217],
      spark:Math.random()<.12
    });
    if(particles.length>MAX_PARTICLES)particles.splice(0,particles.length-MAX_PARTICLES);
  }
  function paintCloud(p){
    const alpha=Math.min(1,p.life*1.5);
    const [red,green,blue]=p.tint;
    // Multiple offset lobes give the trail an actual airy cloud appearance.
    for(const [dx,dy,scale,power] of [[0,0,1,1],[-.32,-.14,.71,.75],[.31,-.22,.76,.8],[.1,.24,.65,.62]]){
      const x=p.x+dx*p.r,y=p.y+dy*p.r,r=p.r*scale;
      const g=ctx.createRadialGradient(x,y,r*.04,x,y,r);
      g.addColorStop(0,`rgba(${red},${green},${blue},${(0.35*alpha*power).toFixed(3)})`);
      g.addColorStop(.38,`rgba(${red},${green},${blue},${(0.21*alpha*power).toFixed(3)})`);
      g.addColorStop(1,`rgba(${red},${green},${blue},0)`);
      ctx.fillStyle=g;ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fill();
    }
    // Small luminous dust grains keep the effect playful without masking the form.
    if(p.spark){
      ctx.fillStyle=`rgba(255,255,255,${(0.9*alpha).toFixed(3)})`;
      ctx.beginPath();ctx.arc(p.x,p.y,1.1+alpha,0,Math.PI*2);ctx.fill();
    }
  }
  function animate(){
    raf=0;ctx.clearRect(0,0,width,height);
    if(!isLoginVisible()){particles.length=0;return;}
    for(const p of particles){
      p.x+=p.vx;p.y+=p.vy;p.vx*=.96;p.vy-=.003;
      p.r+=.38;p.life-=p.decay;
      if(p.life>0)paintCloud(p);
    }
    particles=particles.filter(p=>p.life>0);
    if(particles.length)raf=requestAnimationFrame(animate);
  }
  function schedule(){if(!raf)raf=requestAnimationFrame(animate);}
  function spawnTrail(x,y,burst=false){
    if(!isLoginVisible())return;
    const count=burst?9:2;
    for(let i=0;i<count;i++)puff(x,y,burst);
    schedule();
  }
  // Window-level capture prevents nested form controls from interrupting the trail.
  // Respect reduced-motion settings by limiting it to a tiny touch/click burst.
  window.addEventListener('pointermove',e=>{
    if(!isLoginVisible() || reduceMotion)return;
    const now=performance.now();
    const x=e.clientX,y=e.clientY;
    if(now-lastTime<18)return;
    const previousX=lastX,previousY=lastY;
    lastTime=now;lastX=x;lastY=y;
    if(previousX===null){spawnTrail(x,y,true);return;}
    const distance=Math.hypot(x-previousX,y-previousY);
    if(distance<2)return;
    const steps=Math.min(3,Math.max(1,Math.ceil(distance/24)));
    for(let i=0;i<steps;i++){
      const t=(i+1)/steps;
      spawnTrail(previousX+(x-previousX)*t,previousY+(y-previousY)*t);
    }
  },{passive:true,capture:true});
  window.addEventListener('pointerdown',e=>{
    if(!isLoginVisible())return;
    // A short cloud burst is also available on touch screens.
    spawnTrail(e.clientX,e.clientY,!reduceMotion);
  },{passive:true,capture:true});
  window.addEventListener('pointerleave',()=>{lastX=null;lastY=null;},{passive:true});
})();

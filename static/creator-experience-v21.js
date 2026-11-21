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

  // Gentle cloud-mist cursor trail. Decorative only; pointer events pass through.
  const root=document.getElementById('auth-view');
  const canvas=document.getElementById('sm-cloud-canvas');
  if(!root||!canvas||!canvas.getContext||window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const ctx=canvas.getContext('2d',{alpha:true});
  if(!ctx)return;
  let particles=[],frame=0,raf=0,lastX=null,lastY=null;
  const size=()=>{
    const ratio=Math.min(window.devicePixelRatio||1,2);
    canvas.width=Math.round(window.innerWidth*ratio);canvas.height=Math.round(window.innerHeight*ratio);
    canvas.style.width=window.innerWidth+'px';canvas.style.height=window.innerHeight+'px';
    ctx.setTransform(ratio,0,0,ratio,0,0);
  };
  size();window.addEventListener('resize',size,{passive:true});
  function spawn(x,y,count){
    for(let i=0;i<count && particles.length<65;i++){
      const a=Math.random()*Math.PI*2,v=Math.random()*1.4+.12;
      particles.push({x:x+(Math.random()-.5)*12,y:y+(Math.random()-.5)*10,vx:Math.cos(a)*v-.05,vy:Math.sin(a)*v-.42,
        r:12+Math.random()*15,life:1,decay:.026+Math.random()*.018,shade:Math.random()<.55?'255,164,111':'255,219,197'});
    }
    if(!raf)raf=requestAnimationFrame(animate);
  }
  function animate(){
    raf=0;
    ctx.clearRect(0,0,window.innerWidth,window.innerHeight);
    if(!particles.length)return;
    for(const p of particles){
      p.x+=p.vx;p.y+=p.vy;p.r+=.32;p.vx*=.988;p.life-=p.decay;
      if(p.life<=0)continue;
      const glow=ctx.createRadialGradient(p.x,p.y,0,p.x,p.y,p.r);
      const alpha=Math.max(0,p.life)*.2;
      glow.addColorStop(0,`rgba(${p.shade},${alpha})`);
      glow.addColorStop(.3,`rgba(${p.shade},${alpha*.65})`);
      glow.addColorStop(1,`rgba(${p.shade},0)`);
      ctx.fillStyle=glow;ctx.beginPath();ctx.arc(p.x,p.y,p.r,0,Math.PI*2);ctx.fill();
    }
    particles=particles.filter(p=>p.life>0);
    if(particles.length)raf=requestAnimationFrame(animate);
  }
  let lastTime=0;
  root.addEventListener('pointermove',event=>{
    if(root.classList.contains('hidden')||event.pointerType==='touch') return;
    const now=performance.now();if(now-lastTime<22)return;lastTime=now;
    const d=lastX==null?10:Math.hypot(event.clientX-lastX,event.clientY-lastY);
    lastX=event.clientX;lastY=event.clientY;
    if(d>3)spawn(event.clientX,event.clientY,Math.min(5,Math.max(2,Math.ceil(d/20))));
  },{passive:true});
  root.addEventListener('pointerdown',e=>{
    if(root.classList.contains('hidden'))return;
    spawn(e.clientX,e.clientY,e.pointerType==='touch'?14:9);
  },{passive:true});
  root.addEventListener('pointerleave',()=>{lastX=null;lastY=null;},{passive:true});
})();

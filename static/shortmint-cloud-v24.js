/* ShortMint Studio v24: soft cloud particles on every public and signed-in page.
   Runs independently from account, projects, exports and theme JavaScript. */
(() => {
  'use strict';
  if (document.getElementById('sm24-cloud-layer')) return;
  const canvas = document.createElement('canvas');
  canvas.id = 'sm24-cloud-layer';
  canvas.setAttribute('aria-hidden','true');
  document.body.appendChild(canvas);
  const ctx = canvas.getContext('2d', { alpha: true });
  if (!ctx) { canvas.remove(); return; }

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const particles = [];
  const MAX_PARTICLES = 110;
  const motion = { x: null, y: null, time: 0 };
  let frame = 0, width = 0, height = 0, pixelRatio = 1;
  let isTabVisible = !document.hidden;

  function resizeCanvas() {
    width = Math.max(1, window.innerWidth);
    height = Math.max(1, window.innerHeight);
    pixelRatio = Math.min(1.8, window.devicePixelRatio || 1);
    canvas.width = Math.round(width * pixelRatio);
    canvas.height = Math.round(height * pixelRatio);
    canvas.style.width = width + 'px';
    canvas.style.height = height + 'px';
    ctx.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
  }
  resizeCanvas();
  window.addEventListener('resize', resizeCanvas, { passive: true });

  function lightSurface() {
    const auth = document.getElementById('auth-view');
    return (auth && !auth.classList.contains('hidden')) ||
           document.body.classList.contains('light-theme');
  }
  function random(min,max){return min+Math.random()*(max-min)}
  function pushParticle(x,y,burst=false,strength=1) {
    const light = lightSurface();
    const tone = light
      ? [[255,188,147],[246,159,124],[249,179,140],[245,204,178]]
      : [[255,169,114],[255,206,164],[246,147,104],[255,228,196]];
    const c = tone[Math.floor(Math.random()*tone.length)];
    const r = burst ? random(25,43) : random(21,34);
    const puff = {
      x:x+random(-7,7), y:y+random(-7,7),
      vx:random(-.6,.6), vy:random(-1.25,-.25),
      r, life:1, rate:burst?random(.019,.027):random(.023,.032),
      rgb:c, alpha: (light ? .31 : .38)*strength, sparkle:Math.random()<.21,
      shape: random(.75,1.18)
    };
    particles.push(puff);
    if(particles.length>MAX_PARTICLES)particles.splice(0,particles.length-MAX_PARTICLES);
  }
  function emit(x,y,burst=false,strength=1) {
    if (!isTabVisible) return;
    const amount = burst ? 11 : 2;
    for(let i=0;i<amount;i++)pushParticle(x,y,burst,strength);
    if(!frame)frame=window.requestAnimationFrame(draw);
  }
  function renderPuff(p) {
    // Four overlapping blurry lobes provide a cloud shape instead of a dot.
    const fade = Math.max(0,p.life);
    const [red,green,blue] = p.rgb;
    const lobes = [[0,0,1,1],[-.32,-.13,.72,.77],[.32,-.18,.78,.8],[.07,.23,.71,.69]];
    for(const [dx,dy,scale,power] of lobes){
      const cx=p.x+dx*p.r, cy=p.y+dy*p.r, radius=p.r*scale*p.shape;
      const g=ctx.createRadialGradient(cx,cy,0,cx,cy,radius);
      g.addColorStop(0,`rgba(${red},${green},${blue},${(p.alpha*fade*power).toFixed(3)})`);
      g.addColorStop(.40,`rgba(${red},${green},${blue},${(p.alpha*fade*power*.57).toFixed(3)})`);
      g.addColorStop(1,`rgba(${red},${green},${blue},0)`);
      ctx.fillStyle=g;
      ctx.beginPath();ctx.arc(cx,cy,radius,0,Math.PI*2);ctx.fill();
    }
    if(p.spark){
      ctx.fillStyle=`rgba(255,230,190,${(.88*fade).toFixed(3)})`;
      ctx.beginPath();ctx.arc(p.x,p.y,random(0.9,1.35),0,Math.PI*2);ctx.fill();
    }
  }
  function draw() {
    frame=0;
    ctx.clearRect(0,0,width,height);
    if(!isTabVisible){particles.length=0;return;}
    for(let i=particles.length-1;i>=0;i--){
      const p=particles[i];
      p.x+=p.vx;p.y+=p.vy;p.vx*=.98;p.vy-=.004;
      p.r+=.35;p.life-=p.rate;
      if(p.life<=0){particles.splice(i,1);continue;}
      renderPuff(p);
    }
    if(particles.length)frame=window.requestAnimationFrame(draw);
  }
  function onMove(event){
    if(reducedMotion.matches || !isTabVisible || (event.pointerType==='touch' && event.buttons===0))return;
    const now=performance.now();
    const x=event.clientX,y=event.clientY;
    if(now-motion.time<17)return;
    const oldX=motion.x,oldY=motion.y;
    motion.x=x;motion.y=y;motion.time=now;
    if(oldX===null){emit(x,y,false);return;}
    const distance=Math.hypot(x-oldX,y-oldY);
    if(distance<2)return;
    const steps=Math.min(4,Math.max(1,Math.ceil(distance/27)));
    const strength = event.target?.closest?.('button,input,textarea,select,a,[role=button]') ? .64 : 1;
    for(let i=1;i<=steps;i++){
      const k=i/steps;
      emit(oldX+(x-oldX)*k,oldY+(y-oldY)*k,false,strength);
    }
  }
  window.addEventListener('pointermove',onMove,{passive:true,capture:true});
  window.addEventListener('pointerdown',(e)=>{
    emit(e.clientX,e.clientY,!reducedMotion.matches,.72);
  },{passive:true,capture:true});
  window.addEventListener('pointerout',(e)=>{
    if(!e.relatedTarget){motion.x=null;motion.y=null;}
  },{passive:true});
  window.addEventListener('blur',()=>{motion.x=null;motion.y=null;});
  document.addEventListener('visibilitychange',()=>{
    isTabVisible=!document.hidden;
    if(!isTabVisible){particles.length=0;if(frame)cancelAnimationFrame(frame);frame=0;ctx.clearRect(0,0,width,height);}
  });
  // Helpful for lightweight browser verification, not used by site logic.
  canvas.dataset.shortmintCloud = 'global';
})();

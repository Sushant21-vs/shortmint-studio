/* ShortMint Studio v30 — client-side workspace preferences. No account or credit mutation. */
(()=>{
 'use strict';
 const byId=id=>document.getElementById(id);
 const themeButton=byId('theme-toggle');
 const cloudToggle=byId('sm30-cloud-enabled');
 const motionToggle=byId('sm30-reduce-motion');
 const lightButton=byId('sm30-theme-day');
 const nightButton=byId('sm30-theme-night');
 const defaults={cloud:'on',motion:'off'};
 const get=(key,fallback)=>{try{return localStorage.getItem(key)??fallback;}catch{return fallback;}};
 const put=(key,value)=>{try{localStorage.setItem(key,value);}catch{/* private browsing may disable storage */}};
 function render(){
   const midnight=document.body.classList.contains('light-theme');
   lightButton?.setAttribute('aria-pressed',String(!midnight));
   nightButton?.setAttribute('aria-pressed',String(midnight));
   const cloud=get('shortmint_cloud_enabled',defaults.cloud)!=='off';
   const reduce=get('shortmint_reduced_motion',defaults.motion)==='on';
   document.body.classList.toggle('sm30-cloud-off',!cloud);
   document.body.classList.toggle('sm30-reduce-motion',reduce);
   if(cloudToggle)cloudToggle.checked=cloud;
   if(motionToggle)motionToggle.checked=reduce;
   document.dispatchEvent(new Event('shortmint:visual-prefs'));
 }
 function setTheme(midnight){
   if(document.body.classList.contains('light-theme')!==midnight){
     // Reuse existing ShortMint theme handler and its saved preference.
     if(themeButton)themeButton.click();
   }
   render();
 }
 lightButton?.addEventListener('click',()=>setTheme(false));
 nightButton?.addEventListener('click',()=>setTheme(true));
 themeButton?.addEventListener('click',()=>requestAnimationFrame(render));
 cloudToggle?.addEventListener('change',()=>{put('shortmint_cloud_enabled',cloudToggle.checked?'on':'off');render();});
 motionToggle?.addEventListener('change',()=>{put('shortmint_reduced_motion',motionToggle.checked?'on':'off');render();});
 byId('sm30-signout')?.addEventListener('click',()=>byId('logout-button')?.click());
 window.sm30SyncAccount=function(user){
   if(!user)return;
   const username=String(user.username||'Creator');
   const avatar=byId('sm30-avatar');if(avatar)avatar.textContent=username.slice(0,1).toUpperCase();
   const name=byId('sm30-username');if(name)name.textContent=username;
   const role=byId('sm30-role');if(role)role.textContent=user.role==='owner'?'Owner / Admin':'Member / Creator';
   const balance=byId('sm30-balance');if(balance)balance.textContent=user.role==='owner'?'∞ Unlimited credits':`${Math.max(0,Number(user.credits)||0)} credits`;
 };
 render();
})();

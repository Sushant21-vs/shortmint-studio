/* ShortMint 25 — public-within-workspace contacts, built with safe DOM APIs. */
(() => {
  'use strict';
  const panel=document.getElementById('sm25-contact-links');
  const tip=document.getElementById('sm25-contact-owner-tip');
  const app=document.getElementById('app-view');
  if (!panel || !app) return;
  const glyphs={
    email:'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 7 8 6 8-6"/>',
    phone:'<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7l.5 3a2 2 0 0 1-.6 1.8L7.1 10a16 16 0 0 0 6 6l1.5-1.9a2 2 0 0 1 1.8-.6l3 .5a2 2 0 0 1 1.6 1.9Z"/>',
    instagram:'<rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><path d="M17.4 6.6h.01"/>',
    youtube:'<rect x="2.5" y="5.5" width="19" height="13" rx="4"/><path d="m10 9 5 3-5 3V9Z"/>'
  };
  const acceptable=(link,service)=>{
    try {
      const url=new URL(link);
      if(url.protocol!=='https:')return false;
      const domain=url.hostname.toLowerCase();
      return service==='instagram' ? ['instagram.com','www.instagram.com'].includes(domain)
        : ['youtube.com','www.youtube.com','m.youtube.com'].includes(domain);
    }catch {return false;}
  };
  function addLink(type,label,detail,url){
    const a=document.createElement('a');a.className='sm25-contact-link';a.href=url;
    if(url.startsWith('https://')){a.target='_blank';a.rel='noopener noreferrer';}
    a.title=type+' — '+detail;
    const icon=document.createElement('span');icon.className='sm25-icon';
    // glyphs are static markup, never sourced from user data.
    icon.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true">'+glyphs[type]+'</svg>';
    const copy=document.createElement('span');copy.className='sm25-link-copy';
    const small=document.createElement('small');small.textContent=label;
    const strong=document.createElement('strong');strong.textContent=detail;
    copy.append(small,strong);
    const chevron=document.createElement('span');chevron.className='sm25-chevron';chevron.textContent='↗';
    a.append(icon,copy,chevron);panel.appendChild(a);
  }
  let loading=false;
  async function refresh(){
    if(loading || app.classList.contains('hidden')) return;
    loading=true;
    try{
      const response=await fetch('/api/sidebar-contact',{credentials:'same-origin',cache:'no-store'});
      if(!response.ok)throw new Error('Cannot load contacts');
      const data=await response.json(); panel.replaceChildren();
      const email=String(data.email||'').trim();
      if(/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))addLink('email','Email',email,'mailto:'+email);
      const phone=String(data.phone||'').trim();
      const digits=phone.replace(/\D/g,'');
      if(digits.length>=7 && digits.length<=15)addLink('phone','Phone',phone,'tel:'+(phone.startsWith('+')?'+':'')+digits);
      const instagram=String(data.instagram||'').trim();
      if(acceptable(instagram,'instagram')){
        let handle='Instagram profile';
        try {handle='@'+decodeURIComponent(new URL(instagram).pathname.split('/').filter(Boolean)[0]);} catch {}
        addLink('instagram','Instagram',handle,instagram);
      }
      const youtube=Array.isArray(data.youtube_channels)?data.youtube_channels:[];
      for(const row of youtube.slice(0,5)) {
        const url=String(row.url||'');
        if(acceptable(url,'youtube'))addLink('youtube','YouTube',String(row.label||'Channel').slice(0,48),url);
      }
      if(!panel.children.length){
        const empty=document.createElement('span');empty.className='sm25-contact-empty';empty.textContent='Contact details will appear here soon.';panel.appendChild(empty);
      }
      if(tip)tip.classList.toggle('hidden', !(typeof currentUser !== 'undefined' && currentUser?.role==='owner' && panel.children.length===1 && panel.firstElementChild.classList.contains('sm25-contact-empty')));
    }catch{
      panel.replaceChildren();const empty=document.createElement('span');empty.className='sm25-contact-empty';empty.textContent='Contacts temporarily unavailable.';panel.appendChild(empty);
    }finally{loading=false;}
  }
  document.addEventListener('shortmint:contact-updated',refresh);
  new MutationObserver(()=>{if(!app.classList.contains('hidden'))refresh();}).observe(app,{attributes:true,attributeFilter:['class']});
  if(!app.classList.contains('hidden'))refresh();
})();

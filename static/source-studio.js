/* ShortMint Creator Kit — no network calls; notes remain in this browser. */
'use strict';
(() => {
  const ids=['campaign-brand','campaign-hook','campaign-caption'];
  const checkIds=['campaign-rights','campaign-creative','campaign-rules'];
  const key='shortmint-campaign-kit-v8';
  const el=id=>document.getElementById(id);
  try {
    const old=JSON.parse(localStorage.getItem(key)||'{}');
    ids.forEach(id=>{if(typeof old[id]==='string' && el(id)) el(id).value=old[id];});
    checkIds.forEach(id=>{if(typeof old[id]==='boolean' && el(id)) el(id).checked=old[id];});
  }catch{}
  function save(){
    const value={};ids.forEach(id=>value[id]=el(id)?.value||'');
    checkIds.forEach(id=>value[id]=!!el(id)?.checked);
    try{localStorage.setItem(key,JSON.stringify(value));}catch{}
  }
  [...ids,...checkIds].forEach(id=>{el(id)?.addEventListener('input',save);el(id)?.addEventListener('change',save);});
  el('campaign-use-hook')?.addEventListener('click',()=>{
    const hook=(el('campaign-hook')?.value||'').trim();
    if(!hook){el('campaign-hook')?.focus();return;}
    const title=el('overlay-title');if(title){title.value=hook.slice(0,120);title.dispatchEvent(new Event('input',{bubbles:true}));title.focus();}
  });
  el('campaign-copy-caption')?.addEventListener('click',async()=>{
    const caption=(el('campaign-caption')?.value||'').trim();if(!caption){el('campaign-caption')?.focus();return;}
    try{await navigator.clipboard.writeText(caption);el('campaign-copy-caption').textContent='✓ Copied';setTimeout(()=>el('campaign-copy-caption').textContent='Copy posting caption',1800);}catch{el('campaign-caption')?.select();}
  });
})();

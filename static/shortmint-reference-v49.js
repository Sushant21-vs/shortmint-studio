/* ShortMint Studio v49 visual layer; data is from real project/order endpoints only. */
(() => {
 'use strict';
 const $ = id => document.getElementById(id);
 const escape = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
 let lastMessageLoad = 0;
 let preflightApplied = false;
 const srcs = ['/sm49-scene-1.webp','/sm49-scene-2.webp','/sm49-scene-3.webp','/sm49-scene-4.webp'];
 function syncProcessing() {
   const body = $('sm49-processing-body'), output = $('export-panel');
   if(!body || !output)return;
   const busy = !output.classList.contains('hidden');
   if(!busy){body.innerHTML='<div class="sm49-empty-status">No active export in this browser. Open Create Shorts to start a project.</div>';return;}
   const pct = Math.min(100,Math.max(0,Number(($('export-percent')?.textContent||'0').replace(/[^\d.]/g,''))||0));
   const title = $('export-title')?.textContent || 'Creating Shorts';
   const detail = $('export-message')?.textContent || 'Processing video';
   body.innerHTML = '<div class="sm49-processing-line"><span aria-hidden="true">ϟ</span><div><b>'+escape(title)+'</b><small>'+escape(detail)+' · '+pct+'%</small><span class="sm49-prog-track"><i style="width:'+pct+'%"></i></span></div></div>';
 }
 window.sm49RenderProjects = function(projects) {
   const gallery=$('sm49-shorts-gallery');if(!gallery)return;
   const done=(Array.isArray(projects)?projects:[]).filter(p=>Number(p.shorts)>0);
   if(!done.length){gallery.innerHTML='<p class="sm49-empty">No generated Shorts yet. Your completed projects will appear here after exporting.</p>';return;}
   gallery.innerHTML=done.slice(0,4).map((p,i)=>'<button class="sm49-short-tile" type="button" data-sm49-project="'+escape(p.id)+'" aria-label="Open project '+escape(p.filename)+'"><div class="sm49-short-image" style="background-image:url(\''+srcs[i%4]+'\')"></div><strong>'+escape(p.filename)+'</strong><small>'+Number(p.shorts)+' Shorts · Open project to view files</small></button>').join('');
 };
 window.sm49LoadMessages = async function(){
   const list=$('sm49-messages-list'),count=$('sm49-pending-orders'),hint=$('sm49-pending-note');
   if(!list || typeof currentUser==='undefined' || !currentUser || typeof api!=='function')return;
   const now=Date.now();if(now-lastMessageLoad<1500)return;lastMessageLoad=now;
   try{
     const data=await api('/api/messages/threads');
     if(!currentUser)return;
     const threads=Array.isArray(data.threads)?data.threads:[];
     const orders=threads.filter(t=>t.kind==='order' && t.status!=='completed');
     if(count)count.textContent=String(orders.length);
     if(hint)hint.textContent=orders.length?'Awaiting action':'No pending orders';
     const dot=$('sm49-notification-dot');if(dot)dot.classList.toggle('hidden',!(Number(data.unread)>0));
     if(!threads.length){list.innerHTML='<p class="sm49-empty">No conversations yet. Create an order or send the owner a message.</p>';return;}
     list.innerHTML=threads.slice(0,2).map(t=>'<div class="sm49-message-row"><span class="sm49-message-avatar">'+escape((currentUser.role==='owner' ? t.username : (t.kind==='order'?'O':'M') || 'M').slice(0,1).toUpperCase())+'</span><div><strong>'+escape(currentUser.role==='owner' ? t.username : t.subject)+'</strong><small>'+escape(t.preview||t.subject||'')+'</small></div><span class="sm49-msg-status">'+escape(({new:'New',in_progress:'In Progress',completed:'Completed'})[t.status]||t.status)+'</span></div>').join('');
   }catch(e){
     if(count)count.textContent='—';if(hint)hint.textContent='Open Orders to check';
     list.innerHTML='<p class="sm49-empty">Messages are unavailable right now. Use Orders &amp; Messages in the sidebar to try again.</p>';
   }
 };
 document.addEventListener('click',async e=>{
   const card=e.target.closest('[data-sm49-project]');if(card){
     const id=card.getAttribute('data-sm49-project');
     if(!id || typeof api!=='function')return;
     try{const data=await api('/api/project/'+encodeURIComponent(id));if(typeof loadProject==='function')loadProject(data);}
     catch(err){if(typeof toast==='function')toast('Could not open that project.');}
   }
 });
 function applyPreflight(){
   const editor=$('editing-area');if(!editor||editor.classList.contains('hidden')||preflightApplied)return;
   const set=(to,value)=>{const el=$(to);if(el){el.value=value;el.dispatchEvent(new Event('change',{bubbles:true}));}};
   set('clip-length',$('sm49-preflight-duration')?.value||'30');
   set('resolution',$('sm49-preflight-quality')?.value||'1080');
   const captions=$('sm33-auto-captions-export');if(captions){captions.checked=!!$('sm49-preflight-captions')?.checked;captions.dispatchEvent(new Event('change',{bubbles:true}));}
   if($('sm49-preflight-highlights')?.checked){const btn=document.querySelector('#mode-choices [data-value="montage"]');if(btn)btn.click();}
   preflightApplied=true;
 }
 $('sm49-preflight-open')?.addEventListener('click',()=> $('file-input')?.click());
 const edit=$('editing-area');if(edit){new MutationObserver(()=>{if(edit.classList.contains('hidden'))preflightApplied=false;else applyPreflight();}).observe(edit,{attributes:true,attributeFilter:['class']});}
 const exp=$('export-panel');if(exp)new MutationObserver(syncProcessing).observe(exp,{attributes:true,attributeFilter:['class']});
 const pc=$('export-percent');if(pc)new MutationObserver(syncProcessing).observe(pc,{childList:true,characterData:true,subtree:true});
 const msg=$('export-message');if(msg)new MutationObserver(syncProcessing).observe(msg,{childList:true,characterData:true,subtree:true});
 syncProcessing();
 // Visually consistent top-bar credit icon (real balance remains managed by dashboard.js).
 const credit=$('header-credit-chip');if(credit){new MutationObserver(()=>{if(credit.textContent.startsWith('✦'))credit.textContent='▤ '+credit.textContent.slice(1).trim();}).observe(credit,{childList:true});}
})();

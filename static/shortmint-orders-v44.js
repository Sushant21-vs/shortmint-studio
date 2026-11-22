/* ShortMint v44 — account-linked private orders and messages */
(() => {
  'use strict';
  const el = id => document.getElementById(id);
  let selectedId = null;
  let updating = false;
  let listing = false;
  const labels = {order:'Custom order',question:'Question',support:'Support'};
  const statuses = {new:'New',in_progress:'In progress',completed:'Completed'};
  const escapeText = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const timeText = value => new Date((Number(value)||0)*1000).toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});
  const showMessage = value => {el('sm44-feedback').textContent=value || '';};
  const isVisible = () => !!el('orders-view') && !el('orders-view').classList.contains('hidden') && !el('app-view').classList.contains('hidden');
  function showPanel(mode) {
    el('sm44-new-panel').classList.toggle('hidden',mode !== 'new');
    el('sm44-chat-panel').classList.toggle('hidden',mode !== 'chat');
    el('sm44-empty-panel').classList.toggle('hidden',mode !== 'empty');
  }
  function applyRole() {
    const owner = currentUser?.role === 'owner';
    el('sm44-new-button').classList.toggle('hidden',owner);
    el('sm44-inbox-title').textContent=owner?'Owner inbox':'Your conversations';
    el('sm44-inbox-subtitle').textContent=owner?'Private client messages and orders':'Private chats with the owner';
    el('sm44-owner-status').classList.toggle('hidden',!owner);
    if (owner && el('sm44-new-panel') && !el('sm44-new-panel').classList.contains('hidden')) showPanel('empty');
  }
  function drawThreads(threads) {
    const list=el('sm44-thread-list');
    if (!threads.length) {list.innerHTML='<p class="sm44-muted">No conversations yet. '+(currentUser?.role==='owner'?'Customer enquiries will appear here.':'Use + New to message the owner.')+'</p>';return;}
    list.innerHTML=threads.map(t=>`<button type="button" role="listitem" class="sm44-list-item ${Number(t.id)===selectedId?'active':''}" data-sm44-thread="${t.id}">
      <span class="sm44-list-top"><span>${escapeText(labels[t.kind]||t.kind)}</span><span>${escapeText(timeText(t.updated_at))}</span></span>
      <strong>${escapeText(t.subject)}</strong><span class="sm44-preview">${escapeText(t.preview)}</span>
      <span class="sm44-list-foot"><span>${currentUser?.role==='owner'?'@'+escapeText(t.username):escapeText(statuses[t.status]||t.status)}</span>
      ${t.unread?`<span class="sm44-pill">${t.unread} new</span>`:''}</span></button>`).join('');
  }
  async function fetchThreads(quiet=false) {
    if(listing || !currentUser) return;
    listing=true;
    try {
      const data=await api('/api/messages/threads');
      drawThreads(data.threads||[]);
      updateBadge(data.unread||0);
      if(!selectedId && currentUser.role==='owner')showPanel('empty');
      return data;
    } catch(error) {
      if(!quiet)showMessage('Could not load messages: '+errorMessage(error));
    } finally {listing=false;}
  }
  function updateBadge(unread) {
    const badge=el('sm44-unread-badge');
    badge.textContent=unread>99?'99+':String(unread);
    badge.classList.toggle('hidden',unread===0);
    const admin=el('sm44-admin-unread');
    admin.textContent=unread?`${unread} unread ↗`:'Open ↗';
  }
  async function openThread(id, quiet=false) {
    if(!currentUser) return;
    try {
      const data=await api('/api/messages/threads/'+encodeURIComponent(id));
      if(selectedId!==id && quiet)return;
      selectedId=id;
      const thread=data.thread;
      el('sm44-chat-type').textContent=(labels[thread.kind]||'DIRECT MESSAGE').toUpperCase();
      el('sm44-chat-title').textContent=thread.subject;
      el('sm44-chat-meta').textContent=(currentUser.role==='owner'?'Client: '+thread.username:'Direct conversation with ShortMint owner')+' · Started '+timeText(thread.created_at);
      const tag=el('sm44-status-tag');tag.dataset.status=thread.status;tag.textContent=statuses[thread.status]||thread.status;
      el('sm44-status-select').value=thread.status;
      const feed=el('sm44-message-feed');
      const atBottom=feed.scrollTop+feed.clientHeight>=feed.scrollHeight-65;
      feed.innerHTML=(data.messages||[]).map(m=>`<article class="sm44-msg ${m.mine?'mine':''}"><div class="sm44-msg-header"><strong>${m.mine?'You':currentUser.role==='owner'?escapeText(thread.username):'ShortMint owner'}</strong><span>${escapeText(timeText(m.created_at))}</span></div><div class="sm44-msg-body">${escapeText(m.body)}</div></article>`).join('')||'<p class="sm44-muted">No messages yet.</p>';
      showPanel('chat');
      if(!quiet||atBottom)feed.scrollTop=feed.scrollHeight;
      showMessage('');
      await fetchThreads(true);
    }catch(error){if(!quiet)showMessage(errorMessage(error));}
  }
  window.sm44LoadInbox=async()=>{
    applyRole();
    await fetchThreads();
    if(selectedId)await openThread(selectedId,true);
    else if(currentUser?.role==='owner')showPanel('empty');
  };
  window.sm44RefreshBadge=async()=>{
    if(!currentUser)return;
    try {const data=await api('/api/messages/threads');updateBadge(data.unread||0);}catch{}
  };
  window.sm44ClearSession=()=>{selectedId=null;el('sm44-message-feed').replaceChildren();el('sm44-thread-list').replaceChildren();el('sm44-reply').value='';showPanel('new');updateBadge(0);};
  el('sm44-thread-list').addEventListener('click',event=>{
    const target=event.target.closest('[data-sm44-thread]');if(target)openThread(Number(target.dataset.sm44Thread));
  });
  el('sm44-new-button').addEventListener('click',()=>{selectedId=null;showPanel('new');showMessage('');fetchThreads(true);});
  el('sm44-back').addEventListener('click',()=>{selectedId=null;showPanel('empty');fetchThreads(true);});
  el('sm44-refresh').addEventListener('click',async()=>{await fetchThreads();if(selectedId)await openThread(selectedId);});
  el('sm44-new-form').addEventListener('submit',async event=>{
    event.preventDefault();
    if(updating)return;updating=true;
    const button=el('sm44-send-request');button.disabled=true;
    try {
      const result=await api('/api/messages/threads',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind:el('sm44-kind').value,subject:el('sm44-subject').value.trim(),message:el('sm44-message').value.trim()})});
      el('sm44-subject').value='';el('sm44-message').value='';
      await openThread(result.id);
      toast('Your order or message was sent to the owner.',true);
    }catch(error){showMessage(errorMessage(error));}
    finally{button.disabled=false;updating=false;}
  });
  el('sm44-reply-form').addEventListener('submit',async event=>{
    event.preventDefault();if(updating||!selectedId)return;
    updating=true;const button=el('sm44-reply-send');button.disabled=true;
    try {
      await api('/api/messages/threads/'+selectedId+'/reply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:el('sm44-reply').value.trim()})});
      el('sm44-reply').value='';await openThread(selectedId);toast('Message sent.',true);
    }catch(error){showMessage(errorMessage(error));}
    finally{updating=false;button.disabled=false;}
  });
  el('sm44-update-status').addEventListener('click',async()=>{
    if(!selectedId||currentUser?.role!=='owner')return;
    try {await api('/api/admin/messages/'+selectedId+'/status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:el('sm44-status-select').value})});await openThread(selectedId);toast('Order status updated.',true);}
    catch(error){showMessage(errorMessage(error));}
  });
  // Poll only while the inbox is on screen; this is not a push notification system.
  setInterval(()=>{
    if(!currentUser||document.visibilityState!=='visible')return;
    if(isVisible()){
      fetchThreads(true);
      if(selectedId && !updating)openThread(selectedId,true);
    }
  },18000);
})();

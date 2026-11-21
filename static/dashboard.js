'use strict';
let currentUser = null;
let lastProjects = [];
let adminState = null;
let authMode = 'login';
const timeLabel = unix => {if (!unix) return 'Recently'; return new Date(unix*1000).toLocaleString(undefined,{month:'short',day:'numeric',year:'numeric'});};
const safe = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const plural = (n,s='credit') => `${n} ${s}${n===1?'':'s'}`;
const nodes = selector => Array.from(document.querySelectorAll(selector));

function showView(view) {
  if (!currentUser) return;
  if ((view === 'admin' && currentUser.role !== 'owner') || (view === 'buy' && currentUser.role === 'owner')) {toast('Admin access is for the site owner only.');return;}
  for (const name of ['dashboard','credits','buy','admin','studio']) {
    const id = name === 'studio' ? 'editor-view' : name+'-view';
    document.getElementById(id).classList.toggle('hidden',view!==name);
  }
  nodes('[data-view]').forEach(b => b.classList.toggle('active',b.dataset.view===view));
  window.scrollTo({top:0,behavior:'instant'});
  if (view==='admin') loadAdmin();
  if (view==='credits') loadCreditActivity();
  if (view==='buy') loadBuyCredits();
  if (view==='dashboard') refreshData();
}
function updateUser() {
  if (!currentUser) return;
  const owner = currentUser.role === 'owner';
  const letter = currentUser.username.charAt(0).toUpperCase();
  $('#welcome-user').textContent = currentUser.username;
  $('#welcome-copy').textContent = `Hello, ${currentUser.username}. Let's make something worth sharing.`;
  $('#welcome-role').textContent = owner ? 'Owner · Unlimited' : 'Member · Creator';
  $('#welcome-avatar').textContent = letter;
  $('#header-avatar').textContent = letter;
  $('#admin-nav').classList.toggle('hidden',!owner);
  $('#buy-nav').classList.toggle('hidden',owner);
  $('#header-credit-chip').textContent = owner ? '✦ Unlimited credits' : `✦ ${plural(currentUser.credits)}`;
  $('#metric-credits').textContent = owner ? '∞' : currentUser.credits;
  $('#metric-credits-desc').textContent = owner ? 'unlimited access' : 'available';
  $('#metric-plan').textContent = owner ? 'Owner Pro' : 'Creator';
  $('#metric-plan-desc').textContent = owner ? 'Unlimited Shorts' : '1 credit per Short';
  $('#access-heading').textContent = owner ? 'Manage Your Members' : 'Manage Credits';
  $('#access-description').textContent = owner ? 'Approve requests, issue invitation codes, and edit members’ credit balances.' : 'Get more credits from the owner when your current balance runs low.';
  $('#dashboard-manage-credits').textContent = owner ? 'Open Admin Dashboard' : 'View Credit Balance';
  $('#dashboard-secondary-action').textContent = owner ? 'Invite a Friend' : 'Buy Credits / Contact Owner';
  $('#big-credit-count').textContent = owner ? '∞' : String(currentUser.credits);
  $('#balance-info').textContent = owner ? 'Unlimited access to ShortMint exports. Your members use credits for each exported Short.' : '1 credit = 1 Short. Credits are automatically returned if an export fails or is cancelled.';
  $('#request-credit-panel').classList.toggle('hidden',owner);
  $('#owner-info-panel').classList.toggle('hidden',!owner);
  $('#editor-credit-note').textContent = owner ? 'Your owner account has unlimited Shorts' : `${plural(currentUser.credits)} remaining · 1 credit per Short`;
  updateGenerateButton();
}
async function refreshMe() {
  const result = await api('/api/me');
  currentUser = result.user;
  updateUser();
}
function renderPublicInvitePhone(phone) {
  const call = $('#invite-contact-number');
  const whatsapp = $('#invite-contact-whatsapp');
  const phoneText = $('#invite-contact-phone');
  const actions = $('#invite-contact-actions');
  const empty = $('#invite-contact-unset');
  const copy = $('#invite-contact-copy');
  const raw = String(phone ?? '').trim();
  const normalized = raw.replace(/[\s-]/g,'');
  // Public API settings are untrusted: only Nepal-format phone numbers may become links.
  if (/^\+977\d{8,10}$/.test(normalized)) {
    call.href = 'tel:' + normalized;
    phoneText.textContent = raw;
    const message = 'Hello Sushant Hero, I would like a free ShortMint Studio invitation code.';
    whatsapp.href = 'https://wa.me/' + normalized.slice(1) + '?text=' + encodeURIComponent(message);
    actions.classList.remove('hidden');
    empty.classList.add('hidden');
    copy.textContent = 'Need access? Contact Sushant Hero directly to get your free invitation code.';
  } else {
    call.removeAttribute('href');
    whatsapp.removeAttribute('href');
    phoneText.textContent = '';
    actions.classList.add('hidden');
    empty.classList.remove('hidden');
    copy.textContent = 'Contact Sushant Hero to request your free one-time registration code.';
  }
}
async function loadPublicInvitePhone() {
  try {
    const state = await api('/api/setup-state');
    renderPublicInvitePhone(state.invite_phone);
    if (!state.owner_configured) {
      $('#auth-message').textContent = 'Owner setup required. On the host computer, run start_windows.bat first.';
    }
  } catch { renderPublicInvitePhone(''); }
}
function showLogin() {
  currentUser=null;
  $('#app-view').classList.add('hidden');
  $('#auth-view').classList.remove('hidden');
  $('#auth-message').textContent='';
  loadPublicInvitePhone();
}
function showApp(user) {
  currentUser=user;
  $('#auth-view').classList.add('hidden');
  $('#app-view').classList.remove('hidden');
  updateUser();
  showView('dashboard');
}
function setAuthMode(next) {
  authMode=next;
  $('#auth-login-tab').classList.toggle('active',next==='login');
  $('#auth-register-tab').classList.toggle('active',next==='register');
  $('#auth-invite-wrap').classList.toggle('hidden',next!=='register');
  $('#auth-invite').required=next==='register';
  $('#auth-password').autocomplete=next==='login'?'current-password':'new-password';
  $('#auth-submit').textContent=next==='login'?'Sign in to your dashboard →':'Create Friend Account →';
  $('#auth-message').textContent='';
}
$('#auth-login-tab').addEventListener('click',()=>setAuthMode('login'));
$('#auth-register-tab').addEventListener('click',()=>setAuthMode('register'));
$('#auth-form').addEventListener('submit',async event=>{
  event.preventDefault();
  const username=$('#auth-username').value.trim();
  const password=$('#auth-password').value;
  const body={username,password};
  if(authMode==='register')body.invite_code=$('#auth-invite').value.trim();
  const btn=$('#auth-submit');btn.disabled=true;
  $('#auth-message').textContent='';
  try {
    if(authMode==='register') {
      const res=await api('/api/auth/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      setAuthMode('login');
      $('#auth-message').style.color='#65dfa5';
      $('#auth-message').textContent=res.message;
    } else {
      const res=await api('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      $('#auth-password').value='';
      showApp(res.user);
    }
  } catch(error) { $('#auth-message').style.color='#ffada1';$('#auth-message').textContent=errorMessage(error); }
  finally{btn.disabled=false;}
});
$('#logout-button').addEventListener('click',async()=>{
  if(activeTask && !confirm('An export is running. Logging out will not stop the export. Continue?'))return;
  try{await api('/api/auth/logout',{method:'POST'});}catch{}
  project=null;activeTask=null;lastProjects=[];
  showLogin();
});

nodes('[data-view]').forEach(button=>button.addEventListener('click',()=>showView(button.dataset.view)));
$('#dashboard-new-project').addEventListener('click',()=>startNew());
$('#dashboard-manage-credits').addEventListener('click',()=>showView(currentUser.role==='owner'?'admin':'credits'));
$('#dashboard-secondary-action').addEventListener('click',()=>showView(currentUser.role==='owner'?'admin':'buy'));
$('#refresh-projects').addEventListener('click',()=>refreshData());
$('#theme-toggle').addEventListener('click',()=>{
  const on=document.body.classList.toggle('light-theme');
  $('#theme-toggle').textContent=on?'☀':'☾';
  localStorage.setItem('shortmint_theme',on?'light':'dark');
});
if(localStorage.getItem('shortmint_theme')==='light'){$('body').classList.add('light-theme');$('#theme-toggle').textContent='☀';}

function startNew(){
  if(activeTask) {toast('Finish or cancel the current export before starting another video.');return;}
  project=null;
  localStorage.removeItem('shortmint_project');
  $('#source-video').removeAttribute('src');$('#source-video').load();
  $('#editing-area').classList.add('hidden');
  $('#results-area').classList.add('hidden');
  $('#export-panel').classList.add('hidden');
  $('#upload-panel').classList.remove('hidden');
  $('#upload-busy').classList.add('hidden');
  $('#file-input').value='';
  // Link imports removed; the upload queue remains available.
  setStep(1);showView('studio');
}
async function refreshData(){
  if(!currentUser)return;
  try{
    const [me,projects] = await Promise.all([api('/api/me'),api('/api/projects')]);
    currentUser=me.user;updateUser();
    lastProjects=projects.projects;
    if(currentUser.role==='owner'){
      try{
        const snapshot=await api('/api/admin/overview');
        const pending=snapshot.requests.filter(r=>r.status==='pending').length + (snapshot.purchase_requests||[]).filter(r=>r.status==='pending').length;
        $('#nav-request-count').textContent=pending;
        $('#nav-request-count').classList.toggle('hidden',pending===0);
        $('#dashboard-secondary-action').textContent=pending ? `Review ${plural(pending,'Request')}` : 'Invite a Friend';
      }catch{} // The admin panel independently checks access on every action.
    }
    $('#metric-projects').textContent=projects.stats.total_projects;
    $('#metric-week').textContent=projects.stats.this_week;
    $('#metric-month').textContent=projects.stats.this_month;
    $('#metric-shorts').textContent=projects.stats.total_shorts;
    const list=$('#project-list');
    if(!lastProjects.length){list.innerHTML='<div class="empty-list">No projects yet. Click New Project to create your first Short.</div>';return;}
    list.innerHTML=lastProjects.map(p=>`<div class="project-row"><div class="project-square">▣</div><div class="project-description"><b>${safe(p.filename)}</b><small>${safe(timeLabel(p.created_at))} · ${safe(fmtTime(p.duration))} · ${p.shorts} Shorts generated</small></div><div class="project-row-actions"><button type="button" class="small-btn" data-open-project="${p.id}">Open →</button><button type="button" class="small-btn danger" data-delete-project="${p.id}">Delete</button></div></div>`).join('');
  }catch(err){if(String(err.message).includes('Log in')||String(err.message).includes('expired'))showLogin();else toast('Could not refresh dashboard: '+errorMessage(err));}
}
$('#project-list').addEventListener('click',async event=>{
  const open=event.target.closest('[data-open-project]');
  const remove=event.target.closest('[data-delete-project]');
  if(open){try{const data=await api(`/api/project/${open.dataset.openProject}`);loadProject(data);}catch(err){toast(errorMessage(err));}}
  if(remove){
    if(!confirm('Permanently delete this project, its uploaded video, and all its exported Shorts?'))return;
    try{await api(`/api/project/${remove.dataset.deleteProject}`,{method:'DELETE'});
      if(project?.id===remove.dataset.deleteProject){project=null;localStorage.removeItem('shortmint_project');}
      toast('Project deleted.',true);await refreshData();
    }catch(err){toast(errorMessage(err));}
  }
});

async function loadCreditActivity(){
  try{
    await refreshMe();
    const data=await api('/api/credits/activity');
    $('#credit-history').innerHTML=data.history.length?data.history.map(h=>`<div class="history-row"><div><strong>${safe(h.reason)}</strong><small>${safe(timeLabel(h.created_at))}</small></div><b class="${h.amount>=0?'plus':'minus'}">${h.amount>0?'+':''}${h.amount}</b></div>`).join(''):'<div class="empty-list">No credit activity yet.</div>';
    $('#my-requests').innerHTML=data.requests.length?data.requests.map(r=>`<div class="history-row"><div><b>${plural(r.amount)} requested</b><small>${safe(timeLabel(r.created_at))}${r.message?' · '+safe(r.message):''}</small></div><span class="status-tag ${safe(r.status)}">${safe(r.status)}${r.status==='approved'?' · +'+r.granted:''}</span></div>`).join(''):'<div class="empty-list">No requests yet.</div>';
  }catch(err){toast(errorMessage(err));}
}
$('#request-credit-form').addEventListener('submit',async event=>{
  event.preventDefault();
  try{
    const amount=Number($('#request-amount').value);
    const message=$('#request-message').value;
    const result=await api('/api/credits/request',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({amount,message})});
    toast(result.message,true);$('#request-message').value='';loadCreditActivity();
  }catch(err){toast(errorMessage(err));}
});

async function loadAdmin(){
  if(currentUser?.role!=='owner')return;
  try{
    adminState=await api('/api/admin/overview');
    const members=adminState.users.filter(u=>u.role==='member');
    const pending=adminState.requests.filter(r=>r.status==='pending');
    const pendingPurchases=(adminState.purchase_requests||[]).filter(p=>p.status==='pending');
    const unused=adminState.invites.filter(x=>!x.used_by);
    $('#admin-members').textContent=members.length;
    $('#admin-pending').textContent=pending.length+pendingPurchases.length;
    $('#admin-invites').textContent=unused.length;
    $('#purchase-heading-count').textContent=plural(pendingPurchases.length,'pending inquiry');
    $('#nav-request-count').textContent=pending.length+pendingPurchases.length;
    $('#nav-request-count').classList.toggle('hidden',pending.length+pendingPurchases.length===0);
    $('#request-heading-count').textContent=plural(pending.length,'pending request');
    $('#starting-credits').value=adminState.starting_credits;
    $('#owner-whatsapp').value=adminState.contact_whatsapp||'';
    $('#invite-phone').value=adminState.invite_phone||'';
    $('#owner-email').value=adminState.contact_email||'';
    $('#invite-list').innerHTML=adminState.invites.length?adminState.invites.map(i=>`<div class="history-row"><div><b class="invite-code">${safe(i.code)}</b><small>${i.used_by?'Used by '+safe(i.used_by):'Unused · Share with a friend'}</small></div><div class="admin-control-group">${!i.used_by?`<button class="copy-btn" data-copy-invite="${safe(i.code)}">Copy</button><button class="copy-btn" data-revoke-invite="${safe(i.code)}">Revoke</button>`:'<span class="status-tag approved">Used</span>'}</div></div>`).join(''):'<div class="empty-list">No invitation codes yet.</div>';
    $('#admin-requests').innerHTML=pending.length?pending.map(r=>`<div class="request-row"><div><b>${safe(r.username)}</b><small>${plural(r.amount)} requested · ${safe(timeLabel(r.created_at))}</small><small>${safe(r.message||'No message')}</small></div><div class="review-actions"><label class="sr-only" for="grant-${r.id}">Credits to grant</label><input id="grant-${r.id}" type="number" min="1" max="10000" value="${r.amount}" aria-label="Credits to grant"><button class="orange-btn small-btn" data-approve-request="${r.id}">✓ Approve</button><button class="outline-btn small-btn danger" data-reject-request="${r.id}">Reject</button></div></div>`).join(''):'<div class="empty-list">All caught up! No pending requests.</div>';
    $('#admin-purchases').innerHTML=pendingPurchases.length?pendingPurchases.map(p=>`<div class="request-row"><div><b>${safe(p.username)}</b><small>${plural(p.amount)} to buy · ${safe(timeLabel(p.created_at))}</small><small>Contact: ${safe(p.contact)}</small><small>${safe(p.message||'No additional message')}</small></div><div class="review-actions"><button class="orange-btn small-btn" data-fulfill-purchase="${p.id}">✓ Mark paid & grant</button><button class="outline-btn small-btn danger" data-reject-purchase="${p.id}">Reject</button></div></div>`).join(''):'<div class="empty-list">No pending purchase inquiries.</div>';
    $('#admin-users').innerHTML=members.length?members.map(m=>`<tr><td class="member-name">${safe(m.username)}<small>Joined ${safe(timeLabel(m.created_at))}</small></td><td><b>${m.credits}</b></td><td><span class="status-tag ${m.disabled?'rejected':'approved'}">${m.disabled?'Disabled':'Active'}</span></td><td><div class="admin-control-group"><input aria-label="Credit adjustment for ${safe(m.username)}" id="adjust-${m.id}" type="number" min="1" max="100000" value="5"><button class="small-btn" data-add-user="${m.id}">+ Add</button><button class="small-btn" data-remove-user="${m.id}">− Remove</button></div></td><td><button class="small-btn ${m.disabled?'':'danger'}" data-toggle-user="${m.id}">${m.disabled?'Enable':'Disable'}</button></td></tr>`).join(''):'<tr><td colspan="5" style="text-align:center;padding:30px">No members invited yet.</td></tr>';
  }catch(err){toast('Admin panel: '+errorMessage(err));}
}
$('#admin-refresh').addEventListener('click',()=>loadAdmin());
$('#create-invite').addEventListener('click',async()=>{
  try{const result=await api('/api/admin/invites',{method:'POST'});toast(`Invite code created: ${result.code}`,true);await loadAdmin();}catch(err){toast(errorMessage(err));}
});
$('#invite-list').addEventListener('click',async event=>{
  const copy=event.target.closest('[data-copy-invite]');
  const revoke=event.target.closest('[data-revoke-invite]');
  if(copy){
    try{await navigator.clipboard.writeText(copy.dataset.copyInvite);toast('Invitation code copied!',true);}
    catch{toast('Your invite code is '+copy.dataset.copyInvite);}
  }
  if(revoke){
    if(!confirm(`Revoke unused invitation ${revoke.dataset.revokeInvite}?`))return;
    try{await api(`/api/admin/invites/${revoke.dataset.revokeInvite}`,{method:'DELETE'});toast('Invitation revoked.',true);loadAdmin();}catch(err){toast(errorMessage(err));}
  }
});
$('#admin-requests').addEventListener('click',async event=>{
  const approve=event.target.closest('[data-approve-request]');
  const reject=event.target.closest('[data-reject-request]');
  if(!approve&&!reject)return;
  const id=Number((approve||reject).dataset.approveRequest||(approve||reject).dataset.rejectRequest);
  const amount=approve?Number($(`#grant-${id}`).value):0;
  if(approve&&(!Number.isInteger(amount)||amount<1||amount>10000)){toast('Enter 1 to 10000 credits.');return;}
  try{await api(`/api/admin/requests/${id}/review`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:approve?'approve':'reject',amount})});toast(approve?`${plural(amount)} granted successfully.`:'Request rejected.',true);loadAdmin();}catch(err){toast(errorMessage(err));}
});
$('#admin-users').addEventListener('click',async event=>{
  const add=event.target.closest('[data-add-user]');
  const remove=event.target.closest('[data-remove-user]');
  const toggle=event.target.closest('[data-toggle-user]');
  if(add||remove){
    const uid=Number((add||remove).dataset.addUser||(add||remove).dataset.removeUser);
    const val=Number($(`#adjust-${uid}`).value);
    if(!Number.isInteger(val)||val<1||val>100000){toast('Enter a positive whole-number adjustment.');return;}
    const delta=add?val:-val;
    if(remove&&!confirm(`Remove ${val} credits from this member?`))return;
    try{await api(`/api/admin/users/${uid}/credits`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({delta})});toast('Credits updated.',true);loadAdmin();}catch(err){toast(errorMessage(err));}
  }
  if(toggle){
    if(!confirm('Change account access for this member?'))return;
    try{await api(`/api/admin/users/${toggle.dataset.toggleUser}/toggle`,{method:'POST'});toast('Account access updated.',true);loadAdmin();}catch(err){toast(errorMessage(err));}
  }
});
$('#starting-credit-form').addEventListener('submit',async event=>{
  event.preventDefault();
  const value=Number($('#starting-credits').value);
  if(!Number.isInteger(value)||value<0||value>1000){toast('Enter 0–1000 credits.');return;}
  try{await api('/api/admin/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({starting_credits:value})});toast('Welcome credits setting saved.',true);loadAdmin();}catch(err){toast(errorMessage(err));}
});

// Buy credits is a manual owner-contact workflow. No online payment is taken.
async function loadBuyCredits(){
  if(currentUser?.role!=='member')return;
  try{
    const data=await api('/api/credits/shop');
    $('#purchase-history').innerHTML=data.purchases.length?data.purchases.map(p=>`<div class="history-row"><div><b>${plural(p.amount)} requested</b><small>${safe(timeLabel(p.created_at))}</small></div><span class="status-tag ${p.status==='fulfilled'?'approved':p.status==='rejected'?'rejected':''}">${p.status==='fulfilled'?'Paid · Credited':safe(p.status)}</span></div>`).join(''):'<div class="empty-list">No purchase inquiries yet.</div>';
    const links=[];
    const amount=Number($('#buy-amount').value)||25;
    const message=`Hello! I'm ${currentUser.username} on ShortMint Studio. I want to buy ${amount} Shorts credits. Please tell me the price and how to pay.`;
    if(data.whatsapp){
      const digits=data.whatsapp.replace(/\D/g,'');
      if(digits)links.push(`<a target="_blank" rel="noopener noreferrer" class="secondary-btn" href="https://wa.me/${digits}?text=${encodeURIComponent(message)}">Chat with owner on WhatsApp ↗</a>`);
    }
    if(data.email){
      links.push(`<a class="outline-btn" href="mailto:${encodeURIComponent(data.email)}?subject=${encodeURIComponent('ShortMint credit purchase')}&body=${encodeURIComponent(message)}">Email owner ↗</a>`);
    }
    $('#owner-contact-links').innerHTML=links.join('');
    $('#owner-contact-links').classList.toggle('hidden',links.length===0);
  }catch(err){toast('Unable to load credit store: '+errorMessage(err));}
}
$('#shop-packs').addEventListener('click',event=>{
  const pack=event.target.closest('[data-buy-pack]');
  if(!pack)return;
  $('#buy-amount').value=pack.dataset.buyPack;
  nodes('[data-buy-pack]').forEach(node=>node.classList.toggle('selected',node===pack));
  loadBuyCredits();
  $('#buy-contact').focus({preventScroll:true});
  $('#purchase-form').scrollIntoView({behavior:'smooth',block:'center'});
});
$('#buy-amount').addEventListener('change',()=>loadBuyCredits());
$('#purchase-form').addEventListener('submit',async event=>{
  event.preventDefault();
  const amount=Number($('#buy-amount').value);
  if(!Number.isInteger(amount)||amount<1||amount>1000){toast('Choose between 1 and 1,000 credits.');return;}
  const contact=$('#buy-contact').value.trim();
  if(contact.length<5){toast('Enter your email or WhatsApp number.');return;}
  const message=$('#buy-note').value.trim();
  try{
    const res=await api('/api/credits/purchase-request',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({amount,contact,message})});
    toast(res.message,true);$('#buy-note').value='';loadBuyCredits();
  }catch(err){toast(errorMessage(err));}
});
$('#invite-phone-form').addEventListener('submit',async event=>{
  event.preventDefault();
  const invite_phone = $('#invite-phone').value.trim();
  if (invite_phone && !/^\+977(?:[ -]?\d){8,10}$/.test(invite_phone)) {
    toast('Use +977 followed by 8–10 digits, or leave the number blank.');
    return;
  }
  try {
    await api('/api/admin/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({invite_phone})});
    toast(invite_phone?'Login page contact number saved.':'Login page contact number hidden.',true);
    loadAdmin();
  } catch(err) { toast(errorMessage(err)); }
});
$('#owner-contact-form').addEventListener('submit',async event=>{
  event.preventDefault();
  try{
    await api('/api/admin/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({contact_whatsapp:$('#owner-whatsapp').value.trim(),contact_email:$('#owner-email').value.trim()})});
    toast('Owner contact details updated.',true);loadAdmin();
  }catch(err){toast(errorMessage(err));}
});
$('#admin-purchases').addEventListener('click',async event=>{
  const fulfill=event.target.closest('[data-fulfill-purchase]');
  const reject=event.target.closest('[data-reject-purchase]');
  if(!fulfill&&!reject)return;
  const id=Number(fulfill?fulfill.dataset.fulfillPurchase:reject.dataset.rejectPurchase);
  const order=(adminState?.purchase_requests||[]).find(p=>p.id===id);
  if(!order)return;
  if(fulfill && !confirm(`ONLY IF PAYMENT WAS RECEIVED AND VERIFIED: grant ${order.amount} credits to ${order.username}?`))return;
  if(reject && !confirm('Reject this purchase inquiry without granting credits?'))return;
  try{
    await api(`/api/admin/purchases/${id}/review`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:fulfill?'confirm_paid':'reject'})});
    toast(fulfill?`Payment confirmed: ${plural(order.amount)} granted to ${order.username}.`:'Purchase inquiry rejected.',true);
    loadAdmin();
  }catch(err){toast(errorMessage(err));}
});

async function bootstrap(){
  try{const response=await api('/api/me');showApp(response.user);}
  catch{ showLogin(); }
}
bootstrap();

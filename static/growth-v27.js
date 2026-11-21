'use strict';
/* ShortMint Growth: verified Google accounts, promo codes and owner prices.
   No credits are granted client-side: the server validates every action. */
(() => {
  const el = id => document.getElementById(id);
  const googleSlot = el('sm27-google-button');
  if (!googleSlot) return;
  let googleLoading = false;
  let googleConfig = null;
  const submitGoogleCredential = async response => {
    if (googleLoading) return;
    googleLoading = true;
    const message = el('sm27-google-status');
    if (message) message.textContent = 'Checking your Google account securely…';
    try {
      const promo_code = (el('sm27-google-promo').value || '').trim();
      const result = await api('/api/auth/google', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({credential: response.credential, promo_code})
      });
      showApp(result.user);
      if (result.created) toast(`Welcome! ${result.user.credits ?? 5} starter credits are ready.`, true);
      else if (result.promo_awarded) toast(`Promo applied: +${result.promo_awarded} credits.`, true);
      if (result.promo_error) toast('Promo code: ' + result.promo_error);
    } catch (err) {
      if (message) message.textContent = errorMessage(err);
    } finally { googleLoading = false; }
  };
  const initGoogle = async () => {
    try {
      googleConfig = await api('/api/auth/google-config');
      if (!googleConfig.enabled || !googleConfig.client_id) {
        googleSlot.textContent = 'Google sign-in will appear once the owner finishes Google setup.';
        googleSlot.classList.add('sm27-google-disabled');
        return;
      }
      const script = document.createElement('script');
      script.src = 'https://accounts.google.com/gsi/client';
      script.async = true;
      script.defer = true;
      script.onload = () => {
        if (!window.google?.accounts?.id) {googleSlot.textContent='Google sign-in could not load.'; return;}
        google.accounts.id.initialize({client_id:googleConfig.client_id, callback:submitGoogleCredential,auto_select:false});
        googleSlot.textContent = '';
        google.accounts.id.renderButton(googleSlot,{
          type:'standard',theme:'outline',size:'large',shape:'pill',
          text:'continue_with',logo_alignment:'left',width:Math.max(220,Math.min(350,googleSlot.clientWidth||320))
        });
      };
      script.onerror = () => {googleSlot.textContent='Google sign-in is unavailable right now. Try again later.';};
      document.head.appendChild(script);
    } catch {googleSlot.textContent='Unable to load Google sign-in.';}
  };
  initGoogle();

  const redeemForm=el('sm27-redeem-form');
  if (redeemForm) redeemForm.addEventListener('submit',async event=>{
    event.preventDefault();
    const btn=redeemForm.querySelector('button[type=submit]');btn.disabled=true;
    try {
      const code=el('sm27-redeem-code').value.trim();
      const r=await api('/api/credits/redeem', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code})});
      if (currentUser) {currentUser.credits=r.balance;updateUser();}
      el('sm27-redeem-code').value='';
      toast(`${r.credited} extra credits added!`,true);
      if (typeof loadCreditActivity==='function') loadCreditActivity();
    }catch(err){toast(errorMessage(err));}finally{btn.disabled=false;}
  });

  async function loadPromos(){
    if (!currentUser || currentUser.role!=='owner') return;
    try {
      const data=await api('/api/admin/promos');
      const root=el('sm27-promo-list');
      root.innerHTML=data.promos.length ? data.promos.map(p=>{
        const expired = p.expires_at && p.expires_at <= Date.now()/1000;
        return `<div class="sm27-promo-row"><div><strong>${safe(p.code)}</strong><small>+${p.credits} credits · ${p.used_count}/${p.max_uses} used${expired?' · Expired':''}</small></div>${p.active && !expired?`<button class="small-btn" type="button" data-sm27-disable="${safe(p.code)}">Disable</button>`:'<span class="status-tag">Inactive</span>'}</div>`;
      }).join('') : '<p class="mini-caption">No promo codes yet. Create one above.</p>';
    } catch(err){el('sm27-promo-list').textContent='Could not load promotional codes: '+errorMessage(err);}
  }
  const adminPanel = el('sm27-promos-panel');
  if (adminPanel){
    document.addEventListener('click',event=>{
      if (event.target.closest('[data-view="admin"]') || event.target.closest('#admin-refresh')) setTimeout(loadPromos,200);
    });
    el('sm27-create-promo').addEventListener('submit',async event=>{
      event.preventDefault();const btn=event.target.querySelector('button[type=submit]');btn.disabled=true;
      try{
        const payload={code:el('sm27-promo-name').value.trim(),
          credits:Number(el('sm27-promo-credits').value),max_uses:Number(el('sm27-promo-limit').value),
          expires_days:Number(el('sm27-promo-days').value)};
        const r=await api('/api/admin/promos',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
        toast(`Created promo ${r.code}: +${r.credits} credits`,true);
        el('sm27-promo-name').value=r.code;
        loadPromos();
      }catch(err){toast(errorMessage(err));}finally{btn.disabled=false;}
    });
    el('sm27-promo-list').addEventListener('click',async event=>{
      const btn=event.target.closest('[data-sm27-disable]');if(!btn)return;
      if(!confirm('Disable this promo code for future redemptions?'))return;
      try{await api('/api/admin/promos/'+encodeURIComponent(btn.dataset.sm27Disable)+'/disable',{method:'POST'});toast('Promo disabled.',true);loadPromos();}
      catch(err){toast(errorMessage(err));}
    });
    const priceForm=el('sm27-prices-form');
    if(priceForm)priceForm.addEventListener('submit',async event=>{
      event.preventDefault();const prices={};
      for(const amount of [10,25,50,100]){
        const raw=el('sm27-price-'+amount).value.trim();if(!raw)continue;
        const n=Number(raw);if(!Number.isInteger(n)||n<1||n>1000000){toast('Enter a valid NPR price for '+amount+' credits.');return;}
        prices[String(amount)]=n;
      }
      try{await api('/api/admin/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({credit_prices_json:JSON.stringify(prices)})});
          toast('Credit pack prices saved.',true);loadAdmin();}catch(err){toast(errorMessage(err));}
    });
  }

  // Update listed pack pricing whenever visitors open Buy Credits.
  document.addEventListener('click',async event=>{
    if (!event.target.closest('[data-view="buy"]'))return;
    if (!currentUser || currentUser.role!=='member')return;
    try {
      const data=await api('/api/credits/shop');
      for(const btn of document.querySelectorAll('[data-buy-pack]')){
        const price=data.prices?.[btn.dataset.buyPack];
        const bottom=btn.querySelector('b');
        if(bottom) bottom.textContent=Number.isFinite(price)&&price>0?`NPR ${price.toLocaleString()} · Ask owner →`:'Request quote →';
      }
    }catch{}
  });

  // Show honest storage state; manual SQLite backups are distinct from Neon.
  (async()=>{
    try{
      const data=await api('/api/hosting/status');
      const notice=el('sm27-storage-note');
      if (notice)notice.textContent=data.persistent_accounts
        ? 'Cloud PostgreSQL connected: member accounts and credits survive Render redeploys. Keep database backups enabled with your provider.'
        : 'Demo storage: member data will be lost when this Render server restarts. Set DATABASE_URL before inviting paying members.';
      const tools=el('sm-admin-safety-section');
      if (tools && data.persistent_accounts) {
        tools.classList.add('sm27-cloud-storage');
        const title=tools.querySelector('h2');
        const summary=tools.querySelector('p');
        if (title) title.textContent='Your members are stored in the cloud.';
        if (summary) summary.textContent='Member accounts and credits live in your PostgreSQL database, not on Render Free. To migrate older users, you can restore a trusted ShortMint SQLite backup into a NEW, EMPTY cloud database. For future backups, use your database provider.';
        const msg=document.getElementById('sm-backup-message');
        if(msg)msg.textContent='Cloud storage protects against Render redeploys, not against accidental deletion. Back up your PostgreSQL database regularly. Do not upload private backup files to GitHub.';
        const inputLabel=tools.querySelector('.sm-restore-label');
        if(inputLabel)inputLabel.textContent='↥ Import old member backup';
      }
    }catch{}
  })();
})();

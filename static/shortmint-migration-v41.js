/* ShortMint v41: Existing Google account migration, no Google login restored. */
(() => {
  'use strict';
  const el = id => document.getElementById(id);
  const panel = el('sm41-migration-panel');
  const requestForm = el('sm41-migration-request');
  const confirmForm = el('sm41-migration-confirm');
  const note = el('sm41-migration-message');
  const grouped = [el('auth-form'),el('auth-message'),el('invite-contact-box'),
                   el('sm41-migration-entry'),document.querySelector('.auth-switch'),
                   document.querySelector('.sm39-access-banner')];
  let requestedEmail = '';
  const showMigration = on => {
    panel.classList.toggle('hidden', !on);
    grouped.forEach(element => element?.classList.toggle('hidden', on));
    if (on) { requestForm.classList.remove('hidden'); confirmForm.classList.add('hidden');
      note.textContent = ''; el('sm41-migration-email').focus(); }
  };
  const status = (text, good=false) => {
    note.textContent = text;
    note.style.color = good ? '#27744d' : '#9e3b2b';
  };
  async function post(path, body) {
    const res = await fetch(path, {method:'POST',headers:{'Content-Type':'application/json',
       'X-ShortMint-Request':'1'},body:JSON.stringify(body),credentials:'same-origin'});
    const data = await res.json().catch(() => ({}));
    if(!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Please try again.');
    return data;
  }
  el('sm41-migrate-open').addEventListener('click', () => showMigration(true));
  el('sm41-migration-back').addEventListener('click', () => showMigration(false));
  el('auth-login-tab').addEventListener('click', () => showMigration(false));
  el('auth-register-tab').addEventListener('click', () => showMigration(false));
  el('sm41-migration-change').addEventListener('click', () => {
    requestForm.classList.remove('hidden'); confirmForm.classList.add('hidden');
    note.textContent = ''; el('sm41-migration-email').focus();
  });
  requestForm.addEventListener('submit', async event => {
    event.preventDefault();
    requestedEmail = el('sm41-migration-email').value.trim().toLowerCase();
    const btn = el('sm41-request-btn'); btn.disabled=true; status('');
    try {
      const res=await post('/api/auth/migrate/request', {email:requestedEmail});
      requestForm.classList.add('hidden'); confirmForm.classList.remove('hidden');
      el('sm41-migration-destination').textContent = 'If eligible, the one-time code was sent to '+requestedEmail+'.';
      status(res.message,true);
      el('sm41-migration-code').focus();
    } catch(error) {status(error.message || 'Unable to send the code.');}
    finally {btn.disabled=false;}
  });
  confirmForm.addEventListener('submit', async event => {
    event.preventDefault();
    const btn=el('sm41-confirm-btn'); btn.disabled=true; status('');
    try {
      const res=await post('/api/auth/migrate/confirm', {
        email:requestedEmail,code:el('sm41-migration-code').value.trim(),
        new_password:el('sm41-migration-password').value});
      el('sm41-migration-password').value='';el('sm41-migration-code').value='';
      showMigration(false);
      // Return users to the existing login form with their original username.
      el('auth-login-tab').click();
      el('auth-username').value=res.username;
      el('auth-password').value='';
      el('auth-message').style.color='#248651';
      el('auth-message').textContent=res.message;
      el('auth-password').focus();
    } catch(error) {status(error.message || 'Unable to verify your code.');}
    finally {btn.disabled=false;}
  });
})();

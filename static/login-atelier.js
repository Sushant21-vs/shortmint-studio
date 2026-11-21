/* Self-contained login-only microinteraction. No network calls. */
'use strict';
(() => {
  const input = document.getElementById('auth-password');
  const button = document.getElementById('sm-auth-reveal');
  if (!input || !button) return;
  button.addEventListener('click', () => {
    const revealed = input.type === 'password';
    input.type = revealed ? 'text' : 'password';
    button.setAttribute('aria-pressed', String(revealed));
    button.setAttribute('aria-label', revealed ? 'Hide password' : 'Show password');
    input.focus({preventScroll:true});
  });
})();

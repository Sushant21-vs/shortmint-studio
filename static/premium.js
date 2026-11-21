/* ShortMint Premium UI — progressive enhancement, no account/video logic duplicated. */
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const palette = $('sm-command-dialog');
  const input = $('sm-command-search');
  const sidebar = $('sm-sidebar');
  const menu = $('sm-menu-toggle');
  const scrim = $('sm-mobile-scrim');
  const page = $('sm-current-page');
  const labels = { dashboard:'Overview',studio:'Create Shorts', credits:'Credits & Requests',buy:'Buy Credits',admin:'Admin Panel'};
  let previousFocus = null;

  function closeMobile() {
    document.body.classList.remove('sm-mobile-nav-open');
    if (scrim) scrim.hidden = true;
    if (menu) { menu.setAttribute('aria-expanded','false'); menu.setAttribute('aria-label','Open navigation'); }
  }
  function toggleMobile() {
    const next = !document.body.classList.contains('sm-mobile-nav-open');
    if(next) {
      document.body.classList.add('sm-mobile-nav-open');
      if (scrim) scrim.hidden = false;
      if (menu) { menu.setAttribute('aria-expanded','true'); menu.setAttribute('aria-label','Close navigation'); }
    } else closeMobile();
  }
  menu?.addEventListener('click',toggleMobile);
  scrim?.addEventListener('click',closeMobile);
  function closePalette() {
    if (!palette || palette.classList.contains('hidden')) return;
    palette.classList.add('hidden');
    input.value='';
    filterCommands('');
    if (previousFocus?.isConnected) previousFocus.focus();
  }
  function openPalette() {
    if (!palette || $('app-view').classList.contains('hidden')) return;
    previousFocus = document.activeElement;
    closeMobile();
    palette.classList.remove('hidden');
    input.focus();
  }
  function filterCommands(value) {
    const search = (value||'').trim().toLowerCase();
    palette?.querySelectorAll('[data-command-name]').forEach(button => {
      const role = button.dataset.view;
      const owner = document.querySelector('#admin-nav:not(.hidden)') !== null;
      const unavailable = role === 'admin' ? !owner : role === 'buy' ? owner : false;
      button.classList.toggle('hidden',unavailable || !button.dataset.commandName.includes(search));
    });
  }
  $('sm-command-open')?.addEventListener('click',()=>{filterCommands('');openPalette();});
  input?.addEventListener('input', () => filterCommands(input.value));
  document.querySelectorAll('[data-command-close]').forEach(node=>node.addEventListener('click',closePalette));
  document.addEventListener('keydown',(event)=>{
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase()==='k' && !$('app-view').classList.contains('hidden')) {
      event.preventDefault();
      if (!palette.classList.contains('hidden')) closePalette(); else {filterCommands('');openPalette();}
    }
    if (event.key==='Escape') { closePalette(); closeMobile(); }
    if (!palette.classList.contains('hidden')) {
      if (event.key==='Enter' && document.activeElement===input) {
        const first = palette.querySelector('.sm-command-items button:not(.hidden)');
        if (first) { first.click();closePalette(); }
      }
      if (event.key==='Tab') {
        // Keep focus within the small command surface while it is open.
        const items=[input,...palette.querySelectorAll('.sm-command-items button:not(.hidden)')];
        const idx=items.indexOf(document.activeElement);
        if (event.shiftKey && (idx<=0)) {event.preventDefault();items[items.length-1].focus();}
        else if (!event.shiftKey && idx===items.length-1) {event.preventDefault();items[0].focus();}
      }
    }
  });
  document.querySelectorAll('[data-view]').forEach(el=>el.addEventListener('click',()=>{
    if(page && labels[el.dataset.view]) page.textContent=labels[el.dataset.view];
    closeMobile();closePalette();
  }));
  const health = $('sm-engine-status');
  async function updateHealth() {
    try {
      const response = await fetch('/api/health',{cache:'no-store',credentials:'same-origin',signal:AbortSignal.timeout(6500)});
      if (!response.ok) throw new Error('Unavailable');
      const status = await response.json();
      health?.classList.toggle('is-ready',Boolean(status.ok && status.ffmpeg && status.ffprobe));
      health?.classList.toggle('is-offline',!(status.ok && status.ffmpeg && status.ffprobe));
      const label=health?.querySelector('span');
      if(label) label.textContent = status.ok && status.ffmpeg && status.ffprobe ? 'Video engine operational' : 'Video engine unavailable';
    } catch {
      health?.classList.remove('is-ready');health?.classList.add('is-offline');
      const label=health?.querySelector('span');if(label)label.textContent='Engine status unavailable';
    }
  }
  updateHealth();
  // Keep palette role visibility fresh if an owner signs in without a reload.
  document.getElementById('sm-command-open')?.addEventListener('click',()=>filterCommands(''));
  // No polling/scroll handlers/remote libraries: editor retains its existing video logic.
})();

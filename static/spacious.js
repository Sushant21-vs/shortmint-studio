/* ShortMint v15 / progressive layout enhancement. Never edits accounts, videos or export logic. */
(()=>{
  'use strict';
  const root=document.getElementById('app-view');
  const metrics=document.getElementById('metric-grid');
  if(!root || !metrics)return;
  // Show the three metrics creators look at first. Keep secondary ones available, not removed.
  const cards=Array.from(metrics.children);
  if(cards.length>=6){
    const extra=document.createElement('details');
    extra.className='sm-extra-stats';
    extra.innerHTML='<summary>More insights <span>Weekly activity, monthly activity & plan</span></summary>';
    const grid=document.createElement('div');grid.className='sm-extra-stats-grid';
    // credits, total projects, total Shorts stay visible; all original IDs remain present.
    [cards[2],cards[3],cards[5]].forEach(card=>grid.append(card));
    extra.append(grid);
    metrics.parentNode.insertBefore(extra,metrics.nextSibling);
  }
  // Reduce dashboard density without hiding creative guidance permanently.
  const tips=root.querySelector('#dashboard-view .tips-grid');
  if(tips){
    const heading=tips.previousElementSibling;
    const drawer=document.createElement('details');drawer.className='sm-tips-accordion';
    const summary=document.createElement('summary');summary.textContent='Creator tips & inspiration';
    drawer.append(summary,tips);
    if(heading?.classList.contains('section-title-row'))heading.remove();
    const primary=root.querySelector('#dashboard-view .primary-grid');
    if(primary)primary.insertAdjacentElement('afterend',drawer);
  }
  const toggle=document.getElementById('theme-toggle');
  function syncModeIcon(){
    if(!toggle)return;
    const dark=document.body.classList.contains('light-theme');
    toggle.textContent=dark?'☀':'☾';
    toggle.setAttribute('title',dark?'Switch to daylight canvas':'Switch to midnight canvas');
    toggle.setAttribute('aria-label',dark?'Switch to daylight canvas':'Switch to midnight canvas');
  }
  // Existing dashboard script owns theme preference, this only aligns the icon with the new palette.
  syncModeIcon();toggle?.addEventListener('click',syncModeIcon);
  const sidebarCredit=document.querySelector('.sm-side-credit');
  if(sidebarCredit)sidebarCredit.setAttribute('title','Built by Sushant Hero');
})();

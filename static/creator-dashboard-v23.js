/* ShortMint Studio v23 — dashboard-only enhancement.
   Preserves existing authentication, credit, editor and admin event handlers. */
(()=>{
  'use strict';
  const recent=document.getElementById('sm23-projects-jump');
  recent?.addEventListener('click',()=>{
    document.querySelector('#dashboard-view .sm23-project-section')?.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});
  });
})();

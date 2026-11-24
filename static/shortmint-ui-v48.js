/* ShortMint Studio v48 • non-invasive UI enhancements. No backend changes. */
(() => {
  'use strict';
  const upload = document.getElementById('sm48-select-video');
  upload?.addEventListener('click', () => {
    const picker = document.getElementById('file-input');
    if (picker && !picker.disabled) picker.click();
  });
  // All other navigation, real statistics, messages and export actions are
  // provided by the established application scripts. No synthetic data.
})();

'use strict';
(() => {
  const byId = id => document.getElementById(id);
  const controls = [...document.querySelectorAll('[data-sm33-voice]')];
  const status = byId('sm33-voice-status');
  const audio = byId('sm33-voice-audio');
  const download = byId('sm33-voice-download');
  const script = byId('sm33-voice-text');
  const preview = byId('sm33-voice-preview');
  let selectedVoice = 'ava';
  let currentUrl = null;
  let busy = false;
  function setStatus(message) { if (status) status.textContent = message; }
  function clearAudio() {
    audio.pause(); audio.removeAttribute('src'); audio.hidden = true;
    download.classList.add('hidden'); download.removeAttribute('href');
    if (currentUrl) URL.revokeObjectURL(currentUrl);
    currentUrl = null;
  }
  function updateCount(){ byId('sm33-script-count').textContent = `${script.value.length.toLocaleString()} / 2,000`; }
  controls.forEach(btn => btn.addEventListener('click', () => {
    selectedVoice = btn.dataset.sm33Voice;
    controls.forEach(item => {
      const active = item === btn;
      item.classList.toggle('selected', active);
      item.setAttribute('aria-pressed',String(active));
    });
    clearAudio();
    setStatus(`${btn.querySelector('strong').textContent} selected. Play a preview to hear this voice.`);
  }));
  script.addEventListener('input', () => {updateCount();clearAudio();});
  byId('sm33-caption-to-script').addEventListener('click', () => {
    const srt = byId('caption-srt').value.trim();
    if (!srt) {setStatus('Transcribe your video or paste subtitles first.');return;}
    const lines = srt.split(/\r?\n/).map(x=>x.trim()).filter(x => x && !/^\d+$/.test(x) && !/\d{2}:\d{2}:\d{2}[,.]\d{3}\s*-->/.test(x));
    const narration = lines.join(' ').slice(0, 2000);
    script.value = narration; updateCount();clearAudio();
    byId('sm33-voice-enabled').checked = true;
    setStatus('Copied subtitle words into the narration script. Review and shorten them to fit your Short.');
  });
  byId('sm33-voice-enabled').addEventListener('change', ev => {
    setStatus(ev.target.checked ? 'Voiceover enabled for MP4 export. Preview your selection before exporting.' : 'Voiceover disabled. Video will keep its normal audio.');
  });
  preview.addEventListener('click', async () => {
    if (busy) return;
    const text = script.value.trim().slice(0,300) || 'Welcome to ShortMint Studio. Make every moment count.';
    preview.disabled = true;busy = true;clearAudio();
    const voiceName = document.querySelector('.sm33-voice-card.selected strong')?.textContent || 'Selected';
    setStatus(`Generating ${voiceName} voice preview…`);
    try {
      const res = await fetch('/api/voice/preview', {
        method: 'POST',credentials:'same-origin',
        headers: {'Content-Type':'application/json','X-ShortMint-Request':'1'},
        body: JSON.stringify({text,voice:selectedVoice})
      });
      if (!res.ok) {
        let error = 'The voice service is unavailable.';
        try { const data=await res.json();error=typeof data.detail==='string'?data.detail:error; }catch{}
        throw new Error(error);
      }
      const blob=await res.blob();
      currentUrl=URL.createObjectURL(blob);
      audio.src=currentUrl; audio.hidden=false;
      download.href=currentUrl;download.classList.remove('hidden');
      setStatus(`Ready: ${voiceName} voice. You can listen or download the preview MP3.`);
      try{await audio.play();}catch{} // Playback may require user interaction in some browsers.
    } catch(e){setStatus(e.message || 'Could not generate voice preview.');}
    finally {busy=false;preview.disabled=false;}
  });
  async function showCapabilities() {
    try {
      const result=await fetch('/api/voice/voices',{credentials:'same-origin'});
      if(!result.ok) return;
      const state=await result.json();
      if (!state.voice_available) setStatus('Voice generation is not installed on the server. Ask the owner to deploy v33 requirements.');
      const captionNote=byId('caption-note');
      if(captionNote && !state.transcription_available)
        captionNote.textContent='Auto captions require the owner to configure OPENAI_API_KEY in Render, or enable local Whisper. Manual SRT subtitles still work.';
    } catch{}
  }
  // Called from app.js after project load, when the logged-in editor is shown.
  window.sm33VoiceStudioReady=showCapabilities;
  window.sm33VoiceoverFields=() => ({
    voiceover_enabled:byId('sm33-voice-enabled').checked,
    voiceover_text:script.value.trim(),
    voiceover_voice:selectedVoice,
    voiceover_mode:byId('sm33-voice-mix').value
  });
  window.addEventListener('beforeunload',clearAudio);
})();

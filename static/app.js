'use strict';
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));
let project = null;
let mode = 'auto';
let crop = 'center';
let activeTask = null;
let pollTimer = null;
let toastTimer = null;
let captionsPending = false;

function fmtTime(seconds) {
  seconds = Math.max(0, Math.floor(Number(seconds) || 0));
  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  return (hours ? `${hours}:${String(mins).padStart(2, '0')}:` : `${String(mins).padStart(2,'0')}:`) + String(secs).padStart(2, '0');
}
function errorMessage(error) { return error?.message || 'Something went wrong. Please try again.'; }
function toast(message, success = false) {
  $('#toast-text').textContent = message;
  $('#toast-icon').textContent = success ? '✓' : '!';
  $('#toast-icon').style.background = success ? '#70e7b8' : '#f7983c';
  $('#toast').classList.remove('hidden');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $('#toast').classList.add('hidden'), 8000);
}
$('#toast-dismiss').addEventListener('click', () => $('#toast').classList.add('hidden'));
async function api(path, options) {
  options = options || {};
  if (options.method && !['GET','HEAD'].includes(options.method.toUpperCase())) {
    options.headers = {...(options.headers || {}), 'X-ShortMint-Request': '1'};
  }
  const response = await fetch(path, options);
  let data;
  try { data = await response.json(); } catch { data = null; }
  if (!response.ok) {
    const detail = data?.detail;
    throw new Error(typeof detail === 'string' ? detail : `Request failed (${response.status})`);
  }
  return data;
}
function setStep(n) {
  $$('.step').forEach(el => el.classList.toggle('active', Number(el.dataset.step) <= n));
  $('#step-counter').textContent = `STEP 0${n} / 03`;
}
function showBusy(visible, title = 'Reading your video…', message = 'Keep this browser tab open while your file is uploaded.') {
  $('#upload-panel').classList.toggle('hidden', visible || !!project);
  $('#upload-busy').classList.toggle('hidden', !visible);
  $('#upload-busy-title').textContent = title;
  $('#upload-busy-text').textContent = message;
  $('#upload-progress-fill').style.width = visible ? '6%' : '0%';
}
const socialSources = {
  youtube: {name:'YouTube',placeholder:'https://www.youtube.com/watch?v=...',note:'Paste a public YouTube video or Shorts link.'},
  tiktok: {name:'TikTok',placeholder:'https://www.tiktok.com/@creator/video/123...',note:'Paste a public TikTok video link. Private videos or links needing login may not be accessible.'},
  instagram: {name:'Instagram',placeholder:'https://www.instagram.com/reel/ABC123/',note:'Paste a public Instagram Reel or video post. Instagram may restrict automated imports.'}
};
let selectedVideoSource = 'file';
function chooseSource(source) {
  selectedVideoSource = source in socialSources ? source : 'file';
  $$('.source-tab').forEach(b => {const active=b.dataset.source === selectedVideoSource;b.classList.toggle('active',active);b.setAttribute('aria-pressed', String(active));});
  $('#file-source').classList.toggle('hidden', selectedVideoSource !== 'file');
  $('#url-source').classList.toggle('hidden', selectedVideoSource === 'file');
  if(selectedVideoSource !== 'file') {
    const item=socialSources[selectedVideoSource];
    $('#source-service-title').textContent = `Import from ${item.name}`;
    $('#source-service-pill').textContent = item.name;
    $('#source-link-label').textContent = `${item.name.toUpperCase()} VIDEO LINK`;
    $('#source-link-note').textContent = item.note;
    $('#youtube-url').placeholder = item.placeholder;
    $('#youtube-url').value='';
  }
}
$$('.source-tab').forEach(btn => btn.addEventListener('click', () => chooseSource(btn.dataset.source)));
const drop = $('#dropzone');
drop.addEventListener('click', () => $('#file-input').click());
drop.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); $('#file-input').click(); } });
['dragenter','dragover'].forEach(name => drop.addEventListener(name, event => { event.preventDefault(); drop.classList.add('dragging'); }));
['dragleave','dragend','drop'].forEach(name => drop.addEventListener(name, event => { event.preventDefault(); drop.classList.remove('dragging'); }));
drop.addEventListener('drop', event => { if (event.dataTransfer?.files?.length) uploadFile(event.dataTransfer.files[0]); });
$('#file-input').addEventListener('change', event => { if (event.target.files?.[0]) uploadFile(event.target.files[0]); event.target.value = ''; });

function uploadFile(file) {
  if (!file) return;
  if (file.size > 1024**3) { toast('Choose a video smaller than 1 GB.'); return; }
  const ext = '.' + (file.name.split('.').pop() || '').toLowerCase();
  if (!['.mp4','.mov','.mkv','.webm','.avi','.m4v'].includes(ext)) { toast('Please select an MP4, MOV, MKV, WebM, AVI or M4V video.'); return; }
  showBusy(true, 'Uploading your video…', 'Your video is uploaded to the ShortMint host computer.');
  const xhr = new XMLHttpRequest();
  xhr.open('POST','/api/upload');
  xhr.setRequestHeader('X-ShortMint-Request', '1');
  xhr.upload.onprogress = event => {
    if (event.lengthComputable) $('#upload-progress-fill').style.width = `${Math.round(event.loaded / event.total * 100)}%`;
  };
  xhr.onload = () => {
    if (xhr.status >= 200 && xhr.status < 300) {
      try { loadProject(JSON.parse(xhr.responseText)); } catch { showBusy(false); toast('Could not open the uploaded video.'); }
    } else {
      showBusy(false);
      let detail; try { detail = JSON.parse(xhr.responseText)?.detail; } catch {}
      toast(typeof detail === 'string' ? detail : `Upload failed (${xhr.status})`);
    }
  };
  xhr.onerror = () => { showBusy(false); toast('Upload could not complete. Is the local ShortMint server running?'); };
  const form = new FormData(); form.append('file', file, file.name); xhr.send(form);
}
$('#url-source').addEventListener('submit', async event => {
  event.preventDefault();
  const url = $('#youtube-url').value.trim();
  const source = selectedVideoSource;
  if (!url || !(source in socialSources)) return;
  const platformName=socialSources[source].name;
  const button=$('#social-import-button');button.disabled=true;
  showBusy(true, `Importing from ${platformName}…`, 'The source platform may restrict access. Try a direct upload if this import fails.');
  $('#upload-progress-fill').style.width = '23%';
  try {
    const data = await api('/api/import-url', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({url, platform: source})});
    loadProject(data);
    toast(`${platformName} video imported. Preview it and choose a clip.`,true);
  } catch (err) { showBusy(false); toast(errorMessage(err)); }
  finally {button.disabled=false;}
});

function getShortLength() { return Number($('#clip-length').value); }
function getStart() { return Number($('#start-range').value); }
function updateTimeline() {
  if (!project) return;
  const length = Math.min(getShortLength(), project.duration);
  const maxStart = Math.max(0, project.duration - length);
  const slider = $('#start-range');
  slider.max = String(maxStart);
  slider.value = String(Math.min(Number(slider.value) || 0, maxStart));
  const start = getStart();
  slider.style.setProperty('--range-progress', `${maxStart ? start/maxStart*100 : 0}%`);
  $('#start-value').textContent = fmtTime(start);
  $('#end-value').textContent = fmtTime(Math.min(start + length, project.duration));
  const player = $('#source-video');
  $('#time-display').textContent = `${fmtTime(player.currentTime || 0)} / ${fmtTime(project.duration)}`;
}
$('#start-range').addEventListener('input', () => { updateTimeline(); const player = $('#source-video'); if (Number.isFinite(getStart())) player.currentTime = getStart(); });
$('#playhead-button').addEventListener('click', () => { if (!project) return; const video = $('#source-video'); const max = Math.max(0, project.duration - Math.min(getShortLength(), project.duration)); $('#start-range').value = String(Math.min(max, video.currentTime)); updateTimeline(); toast('Clip start set to the current playhead.',true); });
$('#source-video').addEventListener('timeupdate', () => { if (project) $('#time-display').textContent = `${fmtTime($('#source-video').currentTime)} / ${fmtTime(project.duration)}`; });
$('#clip-length').addEventListener('change', () => { updateTimeline(); updateGenerateButton(); });
$('#clip-count').addEventListener('change', updateGenerateButton);
$('#focus-x').addEventListener('input', () => $('#focus-percent').textContent = $('#focus-x').value + '%');
$('#subtitle-file').addEventListener('change', async (event) => {
  const file = event.target.files?.[0];
  if (!file) return;
  if (file.size > 150000) { toast('Your SRT file is too large.'); return; }
  $('#caption-srt').value = await file.text();
  $('#caption-note').textContent = 'SRT loaded. Times must refer to the original long video.';
  toast('Captions loaded. Check the words and timestamps.',true);
  event.target.value = '';
});
$('#clear-captions').addEventListener('click',()=>{$('#caption-srt').value='';toast('Captions cleared.',true);});
$('#auto-caption-btn').addEventListener('click', async()=>{
  if(!project || captionsPending){toast('Upload a video first.'); return;}
  captionsPending=true;
  const button=$('#auto-caption-btn'); button.disabled=true;
  const info=$('#caption-note'); info.textContent='Preparing speech transcription…';
  try{
    const result=await api(`/api/captions/${project.id}/auto`,{method:'POST'});
    const taskId=result.task_id;
    for(let attempt=0;attempt<1000;attempt++){
      await new Promise(resolve=>setTimeout(resolve,1500));
      const state=await api(`/api/status/${taskId}`);
      info.textContent=state.message||'Transcribing…';
      if(state.state==='completed'){
        $('#caption-srt').value=state.caption_srt;
        toast('Automatic subtitles ready. Review them before export.',true);
        return;
      }
      if(state.state==='failed' || state.state==='cancelled') throw new Error(state.message);
    }
    throw new Error('Speech transcription did not finish; please retry.');
  }catch(err){info.textContent=errorMessage(err);toast(errorMessage(err));}
  finally{captionsPending=false;button.disabled=false;}
});

function pickButton(group, attribute, value) {
  document.querySelectorAll(`#${group} button`).forEach(btn => btn.classList.toggle('active', btn.dataset[attribute] === value));
}
$('#mode-choices').addEventListener('click', event => {
  const btn = event.target.closest('[data-value]'); if (!btn) return;
  mode = btn.dataset.value;
  pickButton('mode-choices','value',mode);
  $('#count-group').style.opacity = mode === 'auto' ? '1' : '.4';
  $('#clip-count').disabled = mode !== 'auto';
  $('#mode-note').textContent = mode === 'auto' ? 'Suggest sections using audio activity and pauses.' : 'Cut a clip from the start point you choose in the preview.';
  updateGenerateButton();
});
$('#crop-choices').addEventListener('click', event => {
  const btn = event.target.closest('[data-value]'); if (!btn) return;
  crop = btn.dataset.value; pickButton('crop-choices','value',crop);
});
function updateGenerateButton() {
  const count = mode === 'auto' ? Number($('#clip-count').value) : 1;
  const label = typeof currentUser !== 'undefined' && currentUser && currentUser.role === 'owner' ? 'Unlimited credits' : `${count} credit${count === 1 ? '' : 's'}`;
  $('#generate-text').textContent = `Generate ${count} Short${count === 1 ? '' : 's'} · ${label}`;
}

function loadProject(data) {
  project = data;
  localStorage.setItem('shortmint_project', data.id);
  showView('studio');
  showBusy(false);
  $('#upload-panel').classList.add('hidden');
  $('#editing-area').classList.remove('hidden');
  $('#project-filename').textContent = data.filename;
  $('#project-metadata').textContent = `${fmtTime(data.duration)} · ${data.width} × ${data.height} · ${data.has_audio ? 'Audio detected' : 'No audio track'}`;
  const source = $('#source-video');
  source.src = `${data.source_url}?v=${Date.now()}`;
  source.load();
  $('#start-range').value = '0';
  updateTimeline(); updateGenerateButton();
  renderResults(data.clips || []);
  setStep((data.clips || []).length ? 3 : 2);
  $('#editing-area').scrollIntoView({behavior:'smooth',block:'start'});
  if (typeof refreshData === 'function') refreshData();
}
async function loadSavedProject() {
  const id = localStorage.getItem('shortmint_project');
  if (!id) return;
  try { const data = await api(`/api/project/${encodeURIComponent(id)}`); loadProject(data); }
  catch { localStorage.removeItem('shortmint_project'); }
}

$('#new-project').addEventListener('click', () => startNew());

function renderResults(clips) {
  const area = $('#results-area');
  area.classList.toggle('hidden', !clips.length);
  const grid = $('#results-grid');
  grid.replaceChildren();
  if (!clips.length || !project) return;
  $('#download-all').href = `/api/download-all/${project.id}`;
  clips.forEach((clip, idx) => {
    const card = document.createElement('article'); card.className = 'result-card';
    const wrap = document.createElement('div'); wrap.className = 'result-video-wrap';
    const video = document.createElement('video'); video.controls = true; video.preload = 'metadata'; video.playsInline = true; video.src = `/api/media/${project.id}/${encodeURIComponent(clip.file)}`;
    wrap.appendChild(video);
    const details = document.createElement('div'); details.className = 'result-details';
    const title = document.createElement('h3'); title.textContent = `Short ${String(idx+1).padStart(2,'0')}`;
    const meta = document.createElement('div'); meta.className = 'result-meta';
    meta.textContent = `${fmtTime(clip.start)} – ${fmtTime(clip.start+clip.duration)} · ${clip.resolution} · ${clip.reason}`;
    const actions = document.createElement('div'); actions.className = 'result-actions';
    const ready = document.createElement('span'); ready.textContent = clip.captions ? '✓ MP4 + subtitles' : '✓ YouTube-ready MP4';
    const download = document.createElement('a'); download.className = 'download-button'; download.textContent = '↓ Download MP4';
    download.href = `/api/download/${project.id}/${encodeURIComponent(clip.file)}`;
    actions.append(ready,download);
    const publish = document.createElement('div'); publish.className='publish-tools';
    const titleInput = document.createElement('input'); titleInput.className='publish-title'; titleInput.maxLength=100;
    const defaultTitle=($('#overlay-title').value.trim() || project.filename.replace(/\.[^.]+$/,'').slice(0,75));
    titleInput.value=defaultTitle+' #Shorts'; titleInput.setAttribute('aria-label','Suggested YouTube title');
    const copy = document.createElement('button'); copy.type='button'; copy.className='small-btn'; copy.textContent='Copy title';
    copy.addEventListener('click', async()=>{try{await navigator.clipboard.writeText(titleInput.value);toast('Title copied. Paste into YouTube Studio.',true);}catch{titleInput.select();document.execCommand('copy');toast('Title selected for copying.',true);}});
    const yt = document.createElement('a'); yt.href='https://studio.youtube.com/'; yt.target='_blank'; yt.rel='noopener noreferrer';yt.className='small-btn';yt.textContent='Upload to YouTube ↗';
    publish.append(titleInput,copy,yt);
    details.append(title,meta,actions,publish); card.append(wrap,details); grid.appendChild(card);
  });
}

async function generateClips() {
  if (!project || activeTask) return;
  const body = {
    session_id: project.id, mode, clip_length: getShortLength(),
    count: mode === 'auto' ? Number($('#clip-count').value) : 1,
    start: getStart(), crop_mode: crop, resolution: $('#resolution').value,
    title: $('#overlay-title').value.trim(), title_position: $('#title-position').value,
    caption_srt: $('#caption-srt').value, watermark: $('#watermark').value.trim(),
    focus_x: Number($('#focus-x').value), normalize_audio: $('#normalize-audio').checked
  };
  $('#generate-button').disabled = true;
  $('#export-panel').classList.remove('hidden');
  $('#export-progress-fill').style.width = '0%';
  $('#export-percent').textContent = '0%';
  $('#export-message').textContent = 'Preparing video…';
  $('#export-title').textContent = 'Creating your Shorts';
  $('#cancel-button').disabled = false;
  $('#export-panel').scrollIntoView({behavior:'smooth',block:'center'});
  try {
    const result = await api('/api/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    activeTask = result.task_id;
    checkTask();
  } catch (err) {
    $('#generate-button').disabled = false;
    $('#export-panel').classList.add('hidden'); toast(errorMessage(err));
  }
}
$('#generate-button').addEventListener('click',generateClips);
async function checkTask() {
  if (!activeTask) return;
  try {
    const task = await api(`/api/status/${activeTask}`);
    $('#export-progress-fill').style.width = `${task.progress}%`;
    $('#export-percent').textContent = `${task.progress}%`;
    $('#export-message').textContent = task.message;
    if (task.state === 'completed') {
      activeTask = null;
      $('#generate-button').disabled = false;
      $('#export-panel').classList.add('hidden');
      project = await api(`/api/project/${project.id}`);
      renderResults(project.clips);
      setStep(3);
      $('#results-area').scrollIntoView({behavior:'smooth',block:'start'});
      toast('Your Shorts are ready to download!',true);
      if (typeof refreshData === 'function') refreshData();
      return;
    }
    if (task.state === 'failed' || task.state === 'cancelled') {
      activeTask = null;
      $('#generate-button').disabled = false;
      $('#export-panel').classList.add('hidden');
      toast(task.message || 'Export did not finish.');
      if (typeof refreshData === 'function') refreshData();
      return;
    }
    pollTimer = setTimeout(checkTask,1000);
  } catch (err) {
    pollTimer = setTimeout(checkTask,2000);
    toast('Checking export status: ' + errorMessage(err));
  }
}
$('#cancel-button').addEventListener('click',async () => {
  if (!activeTask) return;
  $('#cancel-button').disabled = true;
  try { await api(`/api/cancel/${activeTask}`,{method:'POST'}); }
  catch (err) { toast(errorMessage(err)); $('#cancel-button').disabled = false; }
});
window.addEventListener('beforeunload', event => { if (activeTask) { event.preventDefault(); event.returnValue = ''; } });
// Sign-in and dashboard initialization are handled by dashboard.js.

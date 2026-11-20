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
  youtube: {name:'YouTube', placeholder:'https://www.youtube.com/watch?v=...', note:'Paste a public YouTube link. If the cloud server blocks access, upload the original video file.'}
};
let selectedVideoSource = 'file';
function chooseSource(source) {
  selectedVideoSource = source in socialSources ? source : 'file';
  const switcher = $('#upload-panel');
  if (switcher) switcher.dataset.activeSource = selectedVideoSource;
  $('#sm-link-help')?.classList.remove('is-error');
  $$('.source-tab').forEach(b => {const active=b.dataset.source === selectedVideoSource;b.classList.toggle('active',active);b.setAttribute('aria-pressed', String(active));});
  $('#file-source').classList.toggle('hidden', selectedVideoSource !== 'file');
  $('#url-source').classList.toggle('hidden', selectedVideoSource === 'file');
  $('#url-source').hidden = selectedVideoSource === 'file';
  $('#file-source').hidden = selectedVideoSource !== 'file';

  if(selectedVideoSource !== 'file') {
    const item=socialSources[selectedVideoSource];
    $('#source-service-title').textContent = `Import from ${item.name}`;
    $('#source-service-pill').textContent = item.name;
    $('#source-link-label').textContent = `${item.name.toUpperCase()} VIDEO LINK`;
    $('#source-link-note').textContent = item.note;
    $('#youtube-url').placeholder = item.placeholder;
    $('#youtube-url').value='';
    $('#youtube-url').focus({preventScroll:true});
    $('#sm-link-help').textContent = `Paste your ${item.name} link here. This site imports only links the source platform makes accessible to its server.`;
  }
}
// Choose source on startup, independent of stale HTML classes.
chooseSource('file');
$('#paste-social-link').addEventListener('click', async () => {
  try {
    const text = (await navigator.clipboard.readText()).trim();
    if (!text) throw new Error('empty');
    $('#youtube-url').value = text;
    $('#youtube-url').focus();
  } catch {
    $('#youtube-url').focus();
    toast('Click in the link box and press Ctrl+V to paste. Clipboard access may be disabled.');
  }
});
$$('.source-tab').forEach(btn => btn.addEventListener('click', () => chooseSource(btn.dataset.source)));
const drop = $('#dropzone');
drop.addEventListener('click', () => $('#file-input').click());
drop.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); $('#file-input').click(); } });
['dragenter','dragover'].forEach(name => drop.addEventListener(name, event => { event.preventDefault(); drop.classList.add('dragging'); }));
['dragleave','dragend','drop'].forEach(name => drop.addEventListener(name, event => { event.preventDefault(); drop.classList.remove('dragging'); }));
// Multiple uploads use the existing authenticated /api/upload endpoint.
// Processing files sequentially is intentional: free hosting may be resource constrained.
const SM_BATCH_LIMIT = 20;
const SM_MAX_FILE_BYTES = 1024 * 1024 * 1024;
const smAllowedExts = new Set(['.mp4','.mov','.mkv','.webm','.avi','.m4v']);
let smBatch = [];
let smBatchRunning = false;
let smBatchXHR = null;
let smStopRequested = false;
let smBatchGeneration = 0;
const smQueuePanel = $('#sm-upload-queue');
const smQueueList = $('#sm-queue-list');
const smQueueSummary = $('#sm-queue-summary');
const smQueueClear = $('#sm-queue-clear');
const smQueueRetry = $('#sm-queue-retry');
function smHumanSize(value) {
  const n = Number(value) || 0;
  return n >= 1024 ** 3 ? `${(n / (1024 ** 3)).toFixed(2)} GB` : `${(n / (1024 ** 2)).toFixed(1)} MB`;
}
function smUpdateQueue() {
  if (!smBatch.length) {smQueuePanel.classList.add('hidden');smQueueRetry.classList.add('hidden');return;}
  smQueuePanel.classList.remove('hidden');
  const finished = smBatch.filter(i => i.state === 'done').length;
  const errors = smBatch.filter(i => i.state === 'failed').length;
  smQueueRetry.classList.toggle('hidden', !errors);
  smQueueRetry.disabled = smBatchRunning;
  const pending = smBatch.filter(i => i.state === 'pending' || i.state === 'uploading').length;
  $('#sm-queue-counter').textContent = `${smBatch.length} / ${SM_BATCH_LIMIT}`;
  const active = smBatch.find(i => i.state === 'uploading');
  smQueueSummary.textContent = smBatchRunning
    ? `Uploading ${active ? active.name : 'videos'} · ${finished} ready · ${pending} remaining`
    : `${finished} ready to edit${errors ? ` · ${errors} failed` : ''} · ${smBatch.length} selected`;
  smQueueClear.textContent = smBatchRunning ? 'Stop remaining' : 'Clear list';
  smQueueClear.disabled = false;
  const overall = smBatch.length ? smBatch.reduce((sum, i) => sum + (i.state === 'done' || i.state === 'failed' || i.state === 'cancelled' ? 100 : i.progress), 0) / smBatch.length : 0;
  $('#sm-queue-meter-fill').style.width = `${Math.round(overall)}%`;
  smQueueList.replaceChildren();
  smBatch.forEach((item, index) => {
    const row = document.createElement('div');row.className = 'sm-queue-item';
    row.dataset.queueState = item.state;
    const indexTag = document.createElement('span');indexTag.className='sm-queue-index';indexTag.textContent = String(index+1).padStart(2,'0');
    const details = document.createElement('div'); details.className='sm-queue-details';
    const name = document.createElement('strong');name.className='sm-queue-name';name.textContent=item.name;name.title=item.name;
    const desc = document.createElement('small'); desc.textContent = `${smHumanSize(item.size)} · ${item.message || 'Waiting to upload'}`;
    const meter=document.createElement('div');meter.className='sm-row-meter';
    const fill=document.createElement('span');fill.style.width=`${item.progress}%`;meter.append(fill);
    details.append(name,desc,meter);
    const status=document.createElement('div');status.className='sm-queue-status';
    const statusLabel=document.createElement('span');statusLabel.className='sm-queue-state';
    statusLabel.textContent = item.state === 'done' ? '✓ Ready' : item.state === 'uploading' ? `${item.progress}%` : item.state === 'failed' ? 'Failed' : item.state === 'cancelled' ? 'Stopped' : 'Queued';
    status.append(statusLabel);
    if (item.state === 'done' && item.data) {
      const edit=document.createElement('button');edit.type='button';edit.className='sm-queue-edit';edit.textContent='Edit Short ↗';
      edit.addEventListener('click', () => {
        if(activeTask){toast('Finish or cancel the current Shorts export first.');return;}
        loadProject(item.data);
      });
      status.append(edit);
    }
    row.append(indexTag,details,status);smQueueList.append(row);
  });
}
function smUploadSingle(item) {
  return new Promise(resolve => {
    const xhr=new XMLHttpRequest();smBatchXHR=xhr;
    xhr.open('POST','/api/upload');
    xhr.setRequestHeader('X-ShortMint-Request','1');
    xhr.upload.onprogress = e => {
      if (e.lengthComputable) {
        const percent = Math.round(e.loaded / e.total * 100);
        if (percent !== item.progress) {item.progress=percent;smUpdateQueue();}
      }
    };
    xhr.onload = () => {
      smBatchXHR=null;
      try {
        const response=JSON.parse(xhr.responseText);
        if(xhr.status < 200 || xhr.status >= 300) throw new Error(response.detail || `Upload failed (${xhr.status})`);
        if (!response.id || !response.filename) throw new Error('Server did not return a valid video project.');
        item.state='done';item.data=response;item.progress=100;item.message='Saved as a project';
      }catch(error){item.state='failed';item.message=String(error.message || 'Upload failed').slice(0,240);item.progress=100;}
      resolve();
    };
    xhr.onerror = () => {smBatchXHR=null;item.state='failed';item.message='Connection failed. Try a smaller file or retry later.';item.progress=100;resolve();};
    xhr.onabort = () => {smBatchXHR=null;item.state='cancelled';item.message='Upload stopped';item.progress=100;resolve();};
    const form=new FormData();form.append('file',item.file,item.name);xhr.send(form);
  });
}
async function smRunBatch() {
  if(smBatchRunning) return;
  smBatchRunning=true;smStopRequested=false;
  const generation=++smBatchGeneration;
  const hasProject=!!project;
  smUpdateQueue();
  for(const item of smBatch) {
    if(smStopRequested || generation !== smBatchGeneration) break;
    if(item.state!=='pending') continue;
    item.state='uploading';item.progress=0;item.message='Uploading securely';smUpdateQueue();
    await smUploadSingle(item);
    smUpdateQueue();
  }
  if(smStopRequested) smBatch.filter(i => i.state === 'pending').forEach(i=>{i.state='cancelled';i.progress=100;i.message='Not uploaded';});
  smBatchRunning=false;smUpdateQueue();
  const done=smBatch.filter(i=>i.state==='done');
  if(done.length) {
    if(!hasProject && !project && !activeTask) loadProject(done[0].data);
    toast(`${done.length} of ${smBatch.length} videos uploaded. Choose “Edit Short” beside any video.`,true);
  } else {
    toast('No videos uploaded. Check each error and try smaller MP4 files.');
  }
}
function smQueueFiles(fileList) {
  if(smBatchRunning){toast('Your current videos are uploading. Finish or stop this batch first.');return;}
  if(activeTask){toast('Finish or cancel the current Shorts export before uploading another batch.');return;}
  const files=Array.from(fileList || []);
  if(!files.length) return;
  if(files.length > SM_BATCH_LIMIT) toast(`You selected ${files.length} videos. Only the first ${SM_BATCH_LIMIT} will upload in this batch.`);
  smBatch=[];
  for(const file of files.slice(0,SM_BATCH_LIMIT)) {
    const ext='.'+(file.name.split('.').pop()||'').toLowerCase();
    const error = !smAllowedExts.has(ext) ? 'Unsupported file format. Use MP4, MOV, MKV, WebM, AVI, or M4V.' : file.size > SM_MAX_FILE_BYTES ? 'File exceeds the 1 GB limit.' : file.size < 1024 ? 'Video file is empty or too small.' : '';
    smBatch.push({file,name:file.name,size:file.size,progress:error?100:0,state:error?'failed':'pending',message:error,data:null});
  }
  smUpdateQueue();
  if(smBatch.some(i=>i.state==='pending')) smRunBatch();
  else toast('None of the selected files can be uploaded. Review the errors below.');
}
drop.addEventListener('drop', event => {if (event.dataTransfer?.files?.length) smQueueFiles(event.dataTransfer.files);});
$('#file-input').addEventListener('change', event => {smQueueFiles(event.target.files);event.target.value='';});
smQueueRetry.addEventListener('click', () => {
  if(smBatchRunning) return;
  let retried=0;
  smBatch.forEach(item => {
    if(item.state !== 'failed') return;
    const ext='.'+(item.name.split('.').pop()||'').toLowerCase();
    if(!smAllowedExts.has(ext) || item.size>SM_MAX_FILE_BYTES || item.size<1024) return;
    item.state='pending';item.progress=0;item.message='Retry queued';retried++;
  });
  smUpdateQueue();
  if(retried) smRunBatch();
  else toast('These files need a supported format and must be smaller than 1 GB.');
});
smQueueClear.addEventListener('click',()=>{
  if(smBatchRunning){smStopRequested=true;if(smBatchXHR)smBatchXHR.abort();smQueueClear.disabled=true;return;}
  smBatch=[];smUpdateQueue();
});
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
  } catch (err) {
    showBusy(false);
    const message = errorMessage(err);
    toast(message.length > 210 ? message.slice(0,207) + '…' : message);
    $('#sm-link-help').textContent = message;
    $('#sm-link-help').classList.add('is-error');
  }
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

'use strict';
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));
let project = null;
let mode = 'montage';
let crop = 'center';
let activeTask = null;
let pollTimer = null;
let sm38ExportPreparing = false;
let smPollErrors = 0;
let toastTimer = null;
let captionsPending = false;
// Automatic downloads are requested once per new export, not when reopening old projects.
const sm40DownloadedTaskIds = new Set();
const sm40AutoDownloadToggle = document.getElementById('sm40-auto-download');
try { sm40AutoDownloadToggle.checked = localStorage.getItem('shortmint_auto_download') !== 'off'; } catch { sm40AutoDownloadToggle.checked = true; }
sm40AutoDownloadToggle.addEventListener('change', () => {
  try { localStorage.setItem('shortmint_auto_download', sm40AutoDownloadToggle.checked ? 'on' : 'off'); } catch {}
});

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
// Single-source creator: video uploads only. Social-link import UI removed.
const drop = $('#dropzone');
drop.addEventListener('click', () => $('#file-input').click());
drop.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); $('#file-input').click(); } });
['dragenter','dragover'].forEach(name => drop.addEventListener(name, event => { event.preventDefault(); drop.classList.add('dragging'); }));
['dragleave','dragend','drop'].forEach(name => drop.addEventListener(name, event => { event.preventDefault(); drop.classList.remove('dragging'); }));
// Multiple uploads use the existing authenticated /api/upload endpoint.
// Processing files sequentially is intentional: free hosting may be resource constrained.
const SM_BATCH_LIMIT = 20;
const SM_MAX_FILE_BYTES = 1024 * 1024 * 1024;
// File extensions are not a reliable format check; the server validates with FFprobe.
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
    toast('No videos uploaded. Check each file error and try smaller, FFmpeg-readable videos.');
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
    const error = file.size > SM_MAX_FILE_BYTES ? 'File exceeds the 1 GB limit.' : file.size < 1024 ? 'Video file is empty or too small.' : ''; 
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
    if(item.size>SM_MAX_FILE_BYTES || item.size<1024) return;
    if(/not a readable video|no video track|duration must be|unable to decode/i.test(item.message)) return;
    item.state='pending';item.progress=0;item.message='Retry queued';retried++;
  });
  smUpdateQueue();
  if(retried) smRunBatch();
  else toast('Only valid, non-empty video files under 1 GB can be retried.');
});
smQueueClear.addEventListener('click',()=>{
  if(smBatchRunning){smStopRequested=true;if(smBatchXHR)smBatchXHR.abort();smQueueClear.disabled=true;return;}
  smBatch=[];smUpdateQueue();
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
async function sm33AutoTranscribeVideo(){
  if(!project || captionsPending){throw new Error('Upload a video first, or let the current transcription finish.');}
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
        return state.caption_srt;
      }
      if(state.state==='failed' || state.state==='cancelled') throw new Error(state.message);
    }
    throw new Error('Speech transcription did not finish; please retry.');
  }catch(err){info.textContent=errorMessage(err);toast(errorMessage(err));throw err;}
  finally{captionsPending=false;button.disabled=false;}
}
$('#auto-caption-btn').addEventListener('click',()=>sm33AutoTranscribeVideo().catch(()=>{}));

function pickButton(group, attribute, value) {
  document.querySelectorAll(`#${group} button`).forEach(btn => btn.classList.toggle('active', btn.dataset[attribute] === value));
}
$('#mode-choices').addEventListener('click', event => {
  const btn = event.target.closest('[data-value]'); if (!btn) return;
  mode = btn.dataset.value;
  pickButton('mode-choices','value',mode);
  const allowMultiple = mode === 'auto' || mode === 'montage';
  $('#count-group').style.opacity = allowMultiple ? '1' : '.4';
  $('#clip-count').disabled = !allowMultiple;
  $('#sm-montage-settings').classList.toggle('hidden',mode !== 'montage');
  $('#sm-cutlist-settings').classList.toggle('hidden',mode !== 'cutlist');
  $('#mode-note').textContent = mode === 'montage' ? 'One edited Short joins several different moments together. Real jump cuts, not a continuous segment.' : mode === 'cutlist' ? 'Paste or type your selected ranges and combine them into one edited Short.' : mode === 'auto' ? 'Classic excerpt chooses one uninterrupted section per Short.' : 'Cut one continuous clip from the playhead you choose.';
  updateGenerateButton();
});
$('#crop-choices').addEventListener('click', event => {
  const btn = event.target.closest('[data-value]'); if (!btn) return;
  crop = btn.dataset.value; pickButton('crop-choices','value',crop);
});
$('#sm-edit-pace').addEventListener('change', updateGenerateButton);
function updateGenerateButton() {
  const count = ['manual','cutlist'].includes(mode) ? 1 : Number($('#clip-count').value);
  const label = typeof currentUser !== 'undefined' && currentUser && currentUser.role === 'owner' ? 'Unlimited credits' : `${count} credit${count === 1 ? '' : 's'}`;
  const kind=['montage','cutlist'].includes(mode) ? 'Edited Short' : 'Short';
  $('#generate-text').textContent = `Generate ${count} ${kind}${count === 1 ? '' : 's'} · ${label}`;
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
    const editCount=Array.isArray(clip.edits)?clip.edits.length:0;
    meta.textContent = editCount ? `${editCount} real cuts · ${fmtTime(clip.duration)} finished · ${clip.resolution}` : `${fmtTime(clip.start)} – ${fmtTime(clip.start+clip.duration)} · ${clip.resolution} · ${clip.reason}`;
    if(editCount){
      const detailsToggle=document.createElement('details');detailsToggle.className='sm-cut-list';
      const summary=document.createElement('summary');summary.textContent=`View ${editCount} source cuts`;
      const list=document.createElement('ol');
      clip.edits.forEach((edit,i)=>{const row=document.createElement('li');row.textContent=`Cut ${i+1} · ${fmtTime(edit.start)} → ${fmtTime(edit.start+edit.duration)} (${edit.duration.toFixed(1)}s)`;list.append(row)});
      detailsToggle.append(summary,list);details.append(detailsToggle);
    }
    const actions = document.createElement('div'); actions.className = 'result-actions';
    const ready = document.createElement('span'); ready.textContent = clip.voiceover ? '✓ MP4 + '+clip.voiceover+' voice' + (clip.captions ? ' + captions' : '') : (clip.captions ? '✓ MP4 + subtitles' : '✓ YouTube-ready MP4');
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


// Use the new export's task result list so old Shorts are not downloaded again.
function sm40RequestAutomaticDownload(taskId, resultClips, projectId) {
  const status = document.getElementById('sm40-download-status');
  const message = document.getElementById('sm40-download-message');
  const retry = document.getElementById('sm40-download-retry');
  const clips = Array.isArray(resultClips) ? resultClips : [];
  if (!/^[a-f0-9]{32}$/.test(taskId) || !clips.length || !projectId) return;
  if (sm40DownloadedTaskIds.has(taskId)) return;
  sm40DownloadedTaskIds.add(taskId);
  const file = String(clips[0]?.file || '');
  if (clips.length === 1 && !/^short_[a-f0-9]{8}_[0-9]{2}\.mp4$/.test(file)) return;
  const url = clips.length === 1
    ? `/api/download/${encodeURIComponent(projectId)}/${encodeURIComponent(file)}`
    : `/api/download-generated/${encodeURIComponent(projectId)}/${encodeURIComponent(taskId)}`;
  retry.href = url;
  retry.textContent = clips.length === 1 ? 'Download MP4 manually' : 'Download ZIP manually';
  status.classList.remove('hidden');
  if (!sm40AutoDownloadToggle.checked) {
    message.textContent = 'Your Shorts are ready. Automatic download is turned off.';
    return;
  }
  // An attachment response triggers the browser's download handling while
  // preserving the editor and its preview. Browsers may still ask permission.
  message.textContent = 'Your ' + (clips.length === 1 ? 'MP4' : 'ZIP') + ' download was requested automatically. If it does not start, use the link here.';
  const link = document.createElement('a');
  link.href = url;
  link.download = clips.length === 1 ? file : `ShortMint_Shorts_${taskId.slice(0, 8)}.zip`;
  link.style.display = 'none';
  document.body.appendChild(link);
  try { link.click(); } catch {
    message.textContent = 'The automatic download was blocked. Please use the manual link below.';
  } finally { link.remove(); }
}

async function generateClips() {
  if (!project || activeTask) return;
  const body = {
    session_id: project.id, mode, clip_length: getShortLength(),
    count: ['manual','cutlist'].includes(mode) ? 1 : Number($('#clip-count').value),
    cuts_text: $('#sm-cuts-text').value,
    edit_pace: $('#sm-edit-pace').value,
    punch_zoom: $('#sm-punch-zoom').checked,
    start: getStart(), crop_mode: crop, resolution: $('#resolution').value,
    title: $('#overlay-title').value.trim(), title_position: $('#title-position').value,
    caption_srt: $('#caption-srt').value, watermark: $('#watermark').value.trim(),
    focus_x: Number($('#focus-x').value), normalize_audio: $('#normalize-audio').checked
  };
  sm38ExportPreparing = true;
  $('#generate-button').disabled = true;
  $('#export-panel').classList.remove('hidden');
  $('#sm40-download-status').classList.add('hidden');
  $('#export-progress-fill').style.width = '0%';
  $('#export-percent').textContent = '0%';
  $('#export-message').textContent = 'Preparing video…';
  $('#export-title').textContent = 'Creating your Shorts';
  $('#cancel-button').disabled = false;
  $('#export-panel').scrollIntoView({behavior:'smooth',block:'center'});
  try {
    if ($('#sm33-auto-captions-export')?.checked && !body.caption_srt.trim()) {
      $('#export-message').textContent = 'Transcribing the source video before exporting…';
      body.caption_srt = await sm33AutoTranscribeVideo();
    }
    const result = await api('/api/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    activeTask = result.task_id;
    sm38ExportPreparing = false;
    smPollErrors = 0;
    checkTask();
  } catch (err) {
    sm38ExportPreparing = false;
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
      const finishedTaskId = activeTask;
      activeTask = null;
      $('#generate-button').disabled = false;
      $('#export-panel').classList.add('hidden');
      project = await api(`/api/project/${project.id}`);
      renderResults(project.clips);
      setStep(3);
      $('#results-area').scrollIntoView({behavior:'smooth',block:'start'});
      sm40RequestAutomaticDownload(finishedTaskId, task.results, project.id);
      toast('Your Shorts are ready!' + (sm40AutoDownloadToggle.checked ? ' Download requested.' : ''),true);
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
    smPollErrors=0;
    pollTimer = setTimeout(checkTask,2500);
  } catch (err) {
    if (!activeTask) return;
    // 429 commonly comes from rate limiting on the hosting path; don't flood it.
    smPollErrors++;
    const wait = Math.min(30000, 2500 * (2 ** Math.min(smPollErrors,4)));
    if ($('#export-message')) $('#export-message').textContent = `Checking export progress is delayed; retrying in ${Math.round(wait/1000)}s. Do not start another export.`;
    if (smPollErrors === 3) toast('Status check is temporarily busy. ShortMint will retry automatically; keep the tab open.');
    pollTimer = setTimeout(checkTask, wait);
  }
}
$('#cancel-button').addEventListener('click',async () => {
  if (!activeTask) return;
  $('#cancel-button').disabled = true;
  try { await api(`/api/cancel/${activeTask}`,{method:'POST'}); }
  catch (err) { toast(errorMessage(err)); $('#cancel-button').disabled = false; }
});
window.addEventListener('beforeunload', event => { if (activeTask || sm38ExportPreparing) { event.preventDefault(); event.returnValue = ''; } });
// Sign-in and dashboard initialization are handled by dashboard.js.

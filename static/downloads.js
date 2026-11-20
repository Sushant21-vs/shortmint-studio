'use strict';
// This tab consumes its own daily free allowance; Shorts balances are separate.
let activeDownloadJob = null;
let downloadPollTimeout = null;

async function loadDownloads(){
  if (!currentUser) return;
  try {
    const [quota, recent] = await Promise.all([api('/api/downloads/quota'),api('/api/downloads/recent')]);
    $('#download-available').textContent = quota.unlimited ? '∞' : String(quota.remaining);
    $('#download-allowance-label').textContent = quota.unlimited ? 'Unlimited owner downloads' : 'free download credits left today';
    $('#download-usage-text').textContent = quota.unlimited ? 'Owner access has no daily credit limit.' :
      `${quota.used} of ${quota.limit} daily credits used · resets 00:00 UTC`;
    $('#download-meter-fill').style.width = quota.unlimited ? '100%' :
      `${quota.limit ? Math.max(0,100*quota.remaining/quota.limit) : 0}%`;
    $('#recent-downloads').innerHTML = recent.items.length ? recent.items.map(item => `
      <div class="download-list-item">
        <span class="download-list-icon">↓</span><div class="download-list-copy">
          <strong>${safe(item.platform)} video</strong>
          <small>${safe(timeLabel(item.created_at))} · ${item.width} × ${item.height} · ${safe(item.file.split('.').pop().toUpperCase())}</small>
        </div><a class="outline-btn" href="/api/downloads/file/${encodeURIComponent(item.job_id)}">Download again ↓</a>
      </div>`).join('') : '<div class="empty-list">No finished downloads yet. Paste a video link above to start.</div>';
  } catch (err) {
    toast('Download page: '+errorMessage(err));
  }
}

function setDownloadFeedback(state, heading, message, jobId=null){
  const panel=$('#download-feedback');
  panel.classList.remove('hidden','is-error','is-complete');
  panel.classList.toggle('is-error',state==='failed');
  panel.classList.toggle('is-complete',state==='completed');
  $('#download-status-icon').textContent=state==='completed'?'✓':state==='failed'?'!':'◉';
  $('#download-status-title').textContent=heading;
  $('#download-status-text').textContent=message;
  $('#download-file-link').classList.toggle('hidden',state!=='completed');
  $('#download-upload-fallback').classList.toggle('hidden', state!=='failed');
  if(jobId&&state==='completed')$('#download-file-link').href='/api/downloads/file/'+encodeURIComponent(jobId);
}

async function pollDownload(jobId){
  if (!currentUser || jobId !== activeDownloadJob) return;
  try {
    const result = await api(`/api/downloads/status/${encodeURIComponent(jobId)}`);
    if (result.state === 'completed') {
      activeDownloadJob=null;
      $('#start-video-download').disabled=false;
      setDownloadFeedback('completed','Your download is ready!',`${result.platform} video · ${result.result.width} × ${result.result.height}. Click Save to download it.`,jobId);
      loadDownloads();
      return;
    }
    if (result.state === 'failed') {
      activeDownloadJob=null;
      $('#start-video-download').disabled=false;
      setDownloadFeedback('failed','Download could not be completed',result.message + (currentUser?.role === 'owner' ? ' No credits were charged.' : ' Your daily download credits were refunded.'));
      loadDownloads();
      return;
    }
    setDownloadFeedback('loading','Downloading from '+result.platform, result.message || 'Keep this tab open.');
    downloadPollTimeout=setTimeout(()=>pollDownload(jobId),1700);
  } catch (err) {
    activeDownloadJob=null;
    $('#start-video-download').disabled=false;
    setDownloadFeedback('failed','Could not check download',errorMessage(err));
    loadDownloads();
  }
}

$('#video-download-form').addEventListener('submit', async event=>{
  event.preventDefault();
  if (activeDownloadJob) {toast('Finish the current download first.');return;}
  const url=$('#download-video-url').value.trim();
  const quality=$('#download-quality').value;
  const btn=$('#start-video-download');btn.disabled=true;
  setDownloadFeedback('loading','Starting download…','Checking source, requested quality and daily allowance.');
  try {
    const started=await api('/api/downloads/start',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({url,quality})
    });
    activeDownloadJob=started.job_id;
    await loadDownloads();
    pollDownload(started.job_id);
  } catch(err) {
    btn.disabled=false;
    setDownloadFeedback('failed','Download not started',errorMessage(err));
  }
});
$('#download-upload-fallback').addEventListener('click', () => {
  startNew();
  chooseSource('file');
  document.getElementById('dropzone').focus();
});
$('#refresh-download-list').addEventListener('click',()=>loadDownloads());

/* ShortMint owner-only portable backups; database still needs durable hosting. */
(() => {
  'use strict';
  const download=document.getElementById('sm-download-backup');
  const restore=document.getElementById('sm-restore-file');
  const message=document.getElementById('sm-backup-message');
  if(!download||!restore||!message) return;
  const show=(text,err=false)=>{message.textContent=text;message.style.color=err?'#c85656':'';};
  download.addEventListener('click',async()=>{
    download.disabled=true;show('Preparing your private accounts backup…');
    try{
      const response=await fetch('/api/admin/data-backup',{credentials:'same-origin',cache:'no-store'});
      if(!response.ok)throw new Error(`Backup unavailable (${response.status}). Please sign in as owner.`);
      const blob=await response.blob();
      const header=response.headers.get('Content-Disposition')||'';
      const filename=(header.match(/filename="([^"]+)"/)||[])[1] || 'ShortMint_private_accounts.sqlite3';
      const url=URL.createObjectURL(blob);
      const a=document.createElement('a');a.href=url;a.download=filename;document.body.append(a);a.click();a.remove();
      setTimeout(()=>URL.revokeObjectURL(url),2000);
      show('Backup downloaded. Keep it privately off Render and download a new copy after member or credit changes.');
    }catch(error){show(error.message,true);}finally{download.disabled=false;}
  });
  restore.addEventListener('change',async()=>{
    const file=restore.files?.[0];if(!file)return;
    if(file.size>12*1024*1024){show('Backup exceeds the 12 MB limit.',true);restore.value='';return;}
    const agreed=confirm('Restore this ShortMint backup?\n\nThis will REPLACE existing members, invitation codes, credits and requests on this server. Existing members will need to log in again. Continue only if you trust this backup.');
    if(!agreed){restore.value='';return;}
    show('Restoring accounts, credits and invitations…');download.disabled=true;restore.disabled=true;
    try{
      const body=new FormData();body.append('file',file,file.name);
      const response=await fetch('/api/admin/data-restore',{method:'POST',credentials:'same-origin',headers:{'X-ShortMint-Request':'1'},body});
      const result=await response.json().catch(()=>({}));
      if(!response.ok)throw new Error(result.detail||`Restore failed (${response.status})`);
      show(`Restored ${result.members_restored} members and ${result.invitations_restored} invitation codes. Keep external PostgreSQL backups configured if using cloud storage.`);
      if(typeof loadAdmin==='function')loadAdmin();
    }catch(error){show(String(error.message||error),true);}finally{download.disabled=false;restore.disabled=false;restore.value='';}
  });
})();

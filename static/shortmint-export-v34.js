/* ShortMint v34 — server-aware UHD choices and saved editor preferences. */
(()=>{
 'use strict';
 const $=id=>document.getElementById(id);
 const KEY='shortmint_editor_defaults_v34';
 const DEFAULTS=Object.freeze({quality:'1080',length:'30',count:'1',crop:'center',normalize:true,voice:'ava',mix:'replace',captions:false});
 const prefIds={quality:'sm34-quality',length:'sm34-length',count:'sm34-count',crop:'sm34-crop',normalize:'sm34-normalize',voice:'sm34-voice',mix:'sm34-mix',captions:'sm34-captions'};
 let capabilities=null;
 function saved(){
   try {
     const found=JSON.parse(localStorage.getItem(KEY) || '{}');
     const result={...DEFAULTS};
     for(const [key,id] of Object.entries(prefIds)){
       if(typeof found[key]==='boolean' && typeof DEFAULTS[key]==='boolean')result[key]=found[key];
       else if(typeof found[key]==='string' && [...$(id).options].some(o=>o.value===found[key]))result[key]=found[key];
     }
     return result;
   } catch {return {...DEFAULTS};}
 }
 function read(){
   const out={};
   for(const [key,id] of Object.entries(prefIds))out[key]=$(id).type==='checkbox'?$(id).checked:$(id).value;
   return out;
 }
 function setFields(values){
   for(const [key,id] of Object.entries(prefIds)){
     const ctrl=$(id);
     if(ctrl.type==='checkbox')ctrl.checked=!!values[key];
     else if([...ctrl.options].some(o=>o.value===values[key]))ctrl.value=values[key];
   }
 }
 function setMsg(message){$('sm34-prefs-status').textContent=message;}
 function setQualityMessage(){
   const quality=$('resolution').value;
   const data=capabilities?.qualities?.[quality];
   let msg=quality==='2160'?'4K (2160 × 3840) requires a higher-memory server and can render slowly.'
           :'1080p is recommended for most Shorts. 4K export increases file size and processing load.';
   if(data&&!data.available)msg=data.reason;
   msg+=' Enlarging a low-resolution source does not add real detail.';
   $('sm34-quality-hint').textContent=msg;
 }
 function applyToEditor(values,showFeedback=true){
   let quality=values.quality;
   if(capabilities?.qualities?.[quality]?.available===false){
     quality='1080';
     if(showFeedback)setMsg('Your stored high-resolution preference is not supported on this server. Applied 1080p instead.');
   }
   $('resolution').value=quality;
   $('clip-length').value=values.length;
   $('clip-count').value=values.count;
   $('normalize-audio').checked=values.normalize;
   $('sm33-auto-captions-export').checked=values.captions;
   $('sm33-voice-mix').value=values.mix;
   const voice=document.querySelector(`[data-sm33-voice="${values.voice}"]`);
   if(voice&&!voice.classList.contains('selected'))voice.click();
   const crop=document.querySelector(`#crop-choices button[data-value="${values.crop}"]`);
   if(crop&&!crop.classList.contains('active'))crop.click();
   $('clip-count').dispatchEvent(new Event('change',{bubbles:true}));
   $('clip-length').dispatchEvent(new Event('change',{bubbles:true}));
   setQualityMessage();
 }
 function persist(){
   const values=read();
   try{localStorage.setItem(KEY,JSON.stringify(values));setMsg('Saved on this device. New editor sessions will use these defaults.');}
   catch{setMsg('Browser storage is unavailable. You can still use Apply to current editor.');}
   applyToEditor(values,false);
 }
 setFields(saved());
 applyToEditor(saved(),false);
 for(const id of Object.values(prefIds))$(id).addEventListener('change',persist);
 $('sm34-save').addEventListener('click',persist);
 $('sm34-apply').addEventListener('click',()=>{applyToEditor(read());setMsg('Applied these preferences to the video editor.');});
 $('sm34-reset').addEventListener('click',()=>{
   if(!confirm('Reset saved editor defaults to 1080p, 30 seconds, normal audio and optional captions off?'))return;
   try{localStorage.removeItem(KEY);}catch{}
   setFields(DEFAULTS);applyToEditor(DEFAULTS);setMsg('Editor defaults reset on this device. Your account and projects are unchanged.');
 });
 $('sm34-credits').addEventListener('click',()=>document.querySelector('#settings-view [data-view="credits"]')?.click());
 $('resolution').addEventListener('change',setQualityMessage);
 let loading=null;
 async function checkCapabilities(){
   if(loading)return loading;
   loading=(async()=>{
     try{
       const response=await fetch('/api/export/capabilities',{credentials:'same-origin'});
       if(!response.ok)throw new Error('Log in to check server export limits.');
       capabilities=await response.json();
       for(const [quality,state] of Object.entries(capabilities.qualities||{})){
         for(const id of ['resolution','sm34-quality']){
           const option=[...$(id).options].find(o=>o.value===quality);
           if(option){option.disabled=!state.available;option.title=state.reason;}
         }
       }
       const mem=capabilities.memory_mb;
       const available=Object.values(capabilities.qualities||{}).filter(q=>q.available&&q.width>=2160).map(q=>q.label);
       $('sm34-server-note').textContent=available.length
          ?`This server supports: 1080p, ${available.join(', ')}. Reported memory: ${mem?Math.round(mem/1024*10)/10+' GB':'unknown'}. High-resolution exports are slower and may use significant storage.`
          :`4K needs a server with at least 2 GB RAM. Current server memory: ${mem?mem+' MB':'unknown'}. 1080p remains available.`;
       if(capabilities.qualities[$('resolution').value]?.available===false){
         $('resolution').value='1080';
       }
       setQualityMessage();
     } catch(err){$('sm34-server-note').textContent='Unable to check high-resolution server capacity. Export may be restricted.';}
     finally{loading=null;}
   })();
   return loading;
 }
 window.sm34RefreshCapabilities=checkCapabilities;
})();

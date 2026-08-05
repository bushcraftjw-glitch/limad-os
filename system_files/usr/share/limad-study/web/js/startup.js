'use strict';
(function(){
  const overlay=document.getElementById('startup-status');
  const detail=document.getElementById('startup-detail');
  let startupTheme='light';
  try{startupTheme=window.localStorage.getItem('limad-theme')==='dark'?'dark':'light'}catch(_error){}
  document.documentElement.dataset.theme=startupTheme;
  if(overlay){
    overlay.style.background=startupTheme==='dark'?'#17161b':'#f6f7fb';
    overlay.style.color=startupTheme==='dark'?'#eeeaf2':'#24243a';
  }
  if(detail)detail.style.color=startupTheme==='dark'?'#aaa4b0':'#666';
  const started=Date.now();
  window.__LIMAD_STUDY_BOOT={started,stage:'startup-guard-loaded'};
  function messageOf(value){
    if(value&&value.message)return String(value.message);
    if(value===undefined||value===null)return 'unbekannt';
    return String(value);
  }
  function report(state,stage,message=''){
    try{
      fetch('/api/frontend/event',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({state,stage,message}),keepalive:true}).catch(()=>{});
    }catch(_error){}
  }
  function fail(message,stage='startup'){
    if(window.__LIMAD_STUDY_READY)return;
    const text=messageOf(message);
    window.__LIMAD_STUDY_BOOT={...(window.__LIMAD_STUDY_BOOT||{}),stage:`failed:${stage}`,error:text};
    if(overlay){
      overlay.style.display='grid';
      if(detail){
        detail.textContent=`Startfehler (${stage}): ${text}`;
        detail.style.color=startupTheme==='dark'?'#ff9daa':'#b42318';
      }
    }
    report('failed',stage,text);
  }
  window.__LIMAD_STUDY_FAIL=fail;
  window.addEventListener('error',event=>fail(event.error||event.message,'window-error'));
  window.addEventListener('unhandledrejection',event=>fail(event.reason,'unhandled-rejection'));
  window.addEventListener('limad-study-ready',()=>{if(overlay)overlay.remove();});
  window.addEventListener('limad-study-failed',event=>fail(event.detail&&event.detail.message,event.detail&&event.detail.stage||'bootstrap'));
  report('starting','startup-guard');
  setTimeout(()=>{
    if(window.__LIMAD_STUDY_READY)return;
    const stage=window.__LIMAD_STUDY_BOOT&&window.__LIMAD_STUDY_BOOT.stage||'Bundle nicht geladen';
    const error=window.__LIMAD_STUDY_BOOT&&window.__LIMAD_STUDY_BOOT.error;
    fail(error||`Study konnte nicht vollständig aufgebaut werden. Status: ${stage}`,'startup-timeout');
  },12000);
})();

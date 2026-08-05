'use strict';
(function(){
  let current=null;
  let activeTab='guide';
  let lastUserTab=null;
  let requestNumber=0;
  let history=[];
  let historyIndex=-1;
  let splitEnabled=false;
  let secondaryTab=null;
  let lazyRequest=null;

  function escapeHtml(value){return String(value??'').replace(/[&<>\"]/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[char]))}
  function panel(){return document.querySelector('.bible-v2-reference')}
  function content(){return document.querySelector('#bible-reference-content')}
  function secondaryContent(){return document.querySelector('#bible-reference-content-secondary')}
  function secondaryTabsRoot(){return document.querySelector('#bible-ref-tabs-secondary')}
  function title(){return document.querySelector('#bible-reference-title')}
  function backButton(){return document.querySelector('#bible-ref-back')}
  function forwardButton(){return document.querySelector('#bible-ref-forward')}
  async function fetchJsonWithTimeout(url,options={},timeoutMs=10000){
    const controller=new AbortController();
    const timer=setTimeout(()=>controller.abort(),timeoutMs);
    try{
      const response=await fetch(url,{...options,signal:controller.signal,headers:{Accept:'application/json',...(options.headers||{})}});
      let payload={};
      try{payload=await response.json()}catch(_error){payload={}}
      if(!response.ok)throw new Error(payload.error||`HTTP ${response.status}`);
      return payload;
    }catch(error){
      if(error?.name==='AbortError')throw new Error('Zeitüberschreitung beim Laden der Quelle.');
      throw error;
    }finally{clearTimeout(timer)}
  }
  function verseParams(data,tab=''){
    const params=new URLSearchParams({
      document_id:String(data.documentId??data.document_id??0),
      verse_id:String(data.verseId??data.verse_id??data.blockIdentifier??0),
      verse_number:String(data.verseNumber??data.verse_number??0),
      verse_text:String(data.text??data.verse_text??'')
    });
    if(tab)params.set('tab',tab);
    return params;
  }
  function setLoading(data){
    const node=content();
    if(title())title().textContent=data.reference||'Bibelstelle';
    if(node)node.innerHTML='<div class="bible-reference-loading"><span></span><p>Studienmaterial wird geladen …</p></div>';
  }
  function clearWhenChapterChanged(){
    try{if(current&&typeof state!=='undefined'&&Number(state.selectedDocument||0)!==Number(current.document_id||0)){current=null;history=[];historyIndex=-1;updateHistoryButtons()}}catch(_error){}
  }
  function updateHistoryButtons(){
    const back=backButton(),forward=forwardButton();
    if(back)back.disabled=historyIndex<=0;
    if(forward)forward.disabled=historyIndex<0||historyIndex>=history.length-1;
  }
  function tabButtonMarkup(order,key,activeKey){
    const tab=current?.tabs?.[key];
    const labels={guide:'Studienleitfaden',insight:'Einsichten',cross:'Querverweise',notes:'Notizen',parallel:'Parallelübersetzungen'};
    const loading=tab?.loading?' …':'';
    return `<button data-bible-ref-tab2="${key}" class="${key===activeKey?'active':''} ${tab&&!tab.installed?'source-missing':''}">${escapeHtml(tab?.title||labels[key]||key)}${tab?` (${tab.count||0}${loading})`:''}</button>`;
  }
  function renderSplitControls(){
    const root=secondaryTabsRoot();if(!root)return;
    if(!splitEnabled||!current){root.hidden=true;root.innerHTML='';return}
    const order=Array.isArray(current.source_order)?current.source_order:['guide','insight','cross','notes','parallel'];
    if(!secondaryTab||secondaryTab===activeTab)secondaryTab=order.find(key=>key!==activeTab)||null;
    root.hidden=false;
    root.innerHTML=order.filter(key=>key!==activeTab).map(key=>tabButtonMarkup(order,key,secondaryTab)).join('');
  }
  function renderSecondary(){
    const node=secondaryContent();if(!node)return;
    if(!splitEnabled||!current||!secondaryTab){node.hidden=true;node.innerHTML='';return}
    node.hidden=false;
    const tab=current.tabs?.[secondaryTab];
    node.innerHTML=tab?.html||'<div class="bible-v2-empty">Keine Inhalte vorhanden.</div>';
  }
  function renderTab(){
    clearWhenChapterChanged();
    const root=panel(),node=content();if(!root||!node)return;
    root.querySelectorAll('[data-bible-ref-tab]').forEach(button=>{
      const key=button.dataset.bibleRefTab;
      button.classList.toggle('active',key===activeTab);
      const tab=current?.tabs?.[key];
      button.classList.toggle('source-missing',Boolean(current&&tab&&!tab.installed));
      button.dataset.count=String(tab?.count??0);
      button.title=tab&&!tab.installed?`${tab.title||button.textContent}: nicht installiert`:`${tab?.title||button.textContent}: ${tab?.count??0} Einträge`;
    });
    if(!current){
      if(title())title().textContent='Studienmaterial';
      node.innerHTML='<div class="bible-v2-empty">Tippe einen Vers an, um Studienleitfaden, Einsichten, Querverweise und Notizen anzuzeigen.</div>';
      renderSplitControls();renderSecondary();return;
    }
    const tab=current.tabs?.[activeTab];
    if(title())title().textContent=`${current.reference||'Bibelstelle'} · ${tab?.title||'Studienmaterial'}`;
    const tabHtml=tab?.loading?'<div class="bible-reference-loading"><span></span><p>Quelle wird geladen …</p></div>':(tab?.html||'<div class="bible-v2-empty">Keine Inhalte vorhanden.</div>');
    node.innerHTML=`<div class="bible-reference-selected-verse"><strong>${escapeHtml(current.reference||'Bibelstelle')}</strong>${current.verse_text?`<p>${escapeHtml(current.verse_text)}</p>`:''}</div>${tabHtml}`;
    node.scrollTop=0;
    renderSplitControls();renderSecondary();
  }
  function pushHistory(entry){
    history=history.slice(0,historyIndex+1);history.push(entry);historyIndex=history.length-1;updateHistoryButtons();
  }
  async function loadVerse(data,options={}){
    const fromHistory=Boolean(options.fromHistory),serial=++requestNumber;
    setLoading(data);
    try{
      const payload=await fetchJsonWithTimeout('/api/bibles/verse-material?'+verseParams(data).toString(),{},12000);
      if(serial!==requestNumber)return;
      current=payload;
      const ordered=Array.isArray(payload.source_order)?payload.source_order:['guide','insight','cross','notes','parallel'];
      const preferred=options.tab||lastUserTab;
      if(preferred&&payload.tabs?.[preferred]&&(Number(payload.tabs[preferred].count||0)>0||payload.tabs[preferred].installed))activeTab=preferred;
      else activeTab=ordered.find(key=>Number(payload.tabs?.[key]?.count||0)>0)||ordered.find(key=>payload.tabs?.[key]?.installed)||'guide';
      if(!fromHistory)pushHistory({...data,tab:activeTab});
      renderTab();
      if(current.tabs?.[activeTab]?.lazy)await loadLazyTab(activeTab);
    }catch(error){
      if(serial!==requestNumber)return;
      const node=content();if(node)node.innerHTML=`<div class="bible-v2-empty"><strong>Studienmaterial konnte nicht geladen werden</strong><p>${escapeHtml(error.message||String(error))}</p><button class="button" data-bible-retry>Erneut versuchen</button></div>`;
    }
  }
  async function loadLazyTab(key){
    if(!current?.tabs?.[key]?.lazy||current.tabs[key].loading)return;
    const token={};lazyRequest=token;
    current.tabs[key]={...current.tabs[key],loading:true};renderTab();
    try{
      const payload=await fetchJsonWithTimeout('/api/bibles/verse-material?'+verseParams(current,key).toString(),{},15000);
      if(lazyRequest!==token||!current)return;
      if(payload.tabs?.[key])current.tabs[key]=payload.tabs[key];
    }catch(error){
      if(lazyRequest!==token||!current)return;
      current.tabs[key]={...current.tabs[key],lazy:false,loading:false,html:`<div class="bible-v2-empty"><strong>${escapeHtml(current.tabs[key].title||'Quelle')}</strong><p>${escapeHtml(error.message||String(error))}</p></div>`};
    }
    if(lazyRequest===token){lazyRequest=null;renderTab()}
  }
  function goHistory(direction){
    const nextIndex=historyIndex+direction;if(nextIndex<0||nextIndex>=history.length)return;
    historyIndex=nextIndex;updateHistoryButtons();const entry=history[historyIndex];if(entry)loadVerse(entry,{fromHistory:true,tab:entry.tab});
  }
  function openActiveInMainWindow(){
    if(!current)return;
    const node=content(),explicit=node?.querySelector('[data-document-id]');
    const targetId=explicit?Number(explicit.dataset.documentId||0):Number(current.document_id||0);if(!targetId)return;
    try{if(explicit&&typeof state!=='undefined')state.pendingBlockIdentifier=explicit.dataset.blockIdentifier||null;if(typeof openDocument==='function')openDocument(targetId)}catch(error){if(typeof toast==='function')toast(error.message||String(error),'error')}
  }
  function ensurePreview(){
    const node=content();if(!node)return null;
    let preview=node.querySelector('#bible-reference-preview');
    if(!preview){preview=document.createElement('div');preview.id='bible-reference-preview';node.prepend(preview)}
    return preview;
  }
  function renderLocalSource(preview,result,label){
    const block=result.block_identifier;
    const query=block!==null&&block!==undefined&&block!==''?`?focus=${encodeURIComponent(block)}`:'';
    const body=result.verse_html?`<div class="context-bible-text">${result.verse_html}</div>`:`<iframe src="/api/documents/${Number(result.document.id)}/render${query}" title="Quellenvorschau"></iframe>`;
    preview.innerHTML=`<article class="bible-reference-preview-card"><header><div><small>${escapeHtml(result.document.publication_title||'Lokale Quelle')}</small><h4>${escapeHtml(result.reference||result.document.toc_title||result.document.title||label||'Quelle')}</h4></div><button class="icon-button" data-bible-preview-close title="Vorschau schließen">×</button></header>${body}<button class="button primary" data-document-id="${Number(result.document.id)}" ${block!==null&&block!==undefined&&block!==''?`data-block-identifier="${escapeHtml(block)}"`:''}>Ganz öffnen</button></article>`;
  }
  function renderOnlineSource(preview,result,label){
    const online=result.online_preview||{};
    if(!online.available||!online.html)return false;
    const image=online.image?`<img class="online-source-image" src="${escapeHtml(online.image)}" alt="">`:'';
    const external=online.url||result.external||'';
    preview.innerHTML=`<article class="bible-reference-preview-card bible-reference-online-card"><header><div><small>Offizielle Online-Quelle · jw.org</small><h4>${escapeHtml(online.title||label||'Quelle')}</h4></div><button class="icon-button" data-bible-preview-close title="Vorschau schließen">×</button></header>${image}<div class="online-source-body">${online.html}</div><div class="online-source-actions">${external?`<button class="button" data-open-bible-external="${escapeHtml(external)}">Auf jw.org öffnen</button>`:''}</div></article>`;
    return true;
  }
  function renderMissingSource(preview,result,label){
    const external=result.external||'';
    preview.innerHTML=`<article class="bible-reference-preview-card"><header><h4>${escapeHtml(label||'Quelle')}</h4><button class="icon-button" data-bible-preview-close>×</button></header><p>${escapeHtml(result.missing_message||'Diese Quelle wurde weder lokal noch online gefunden.')}</p>${external&&/^https?:/i.test(external)?`<button class="button primary" data-open-bible-external="${escapeHtml(external)}">Online öffnen</button>`:''}</article>`;
  }
  async function resolveSource(href,label){
    const preview=ensurePreview();if(!preview||!href)return;
    preview.innerHTML='<div class="bible-reference-loading compact"><span></span><p>Lokale Quelle wird gesucht …</p></div>';
    try{
      const base=`/api/resolve?link=${encodeURIComponent(href)}&label=${encodeURIComponent(label||'')}`;
      const local=await fetchJsonWithTimeout(base+'&local_only=1',{},5500);
      if(local.resolved&&local.document){renderLocalSource(preview,local,label);return}
      preview.innerHTML='<div class="bible-reference-online-status"><span></span><p>Nicht lokal gefunden. Offizielle Quelle auf jw.org wird geprüft …</p></div>';
      const result=await fetchJsonWithTimeout(base,{},11000);
      if(result.resolved&&result.document){renderLocalSource(preview,result,label);return}
      if(renderOnlineSource(preview,result,label))return;
      renderMissingSource(preview,result,label);
    }catch(error){preview.innerHTML=`<div class="bible-v2-empty"><strong>Quelle konnte nicht geladen werden</strong><p>${escapeHtml(error.message||String(error))}</p></div>`}
  }

  window.addEventListener('message',event=>{if(event.origin!==location.origin)return;const data=event.data||{};if(data.type==='limad-bible-verse-select'){const primary=document.querySelector('#reader-frame');if(primary&&event.source!==primary.contentWindow)return;loadVerse(data)}});

  document.addEventListener('click',async event=>{
    const tab=event.target.closest('[data-bible-ref-tab]');
    if(tab&&panel()?.contains(tab)){event.preventDefault();event.stopPropagation();activeTab=tab.dataset.bibleRefTab||'guide';lastUserTab=activeTab;if(history[historyIndex])history[historyIndex].tab=activeTab;renderTab();if(current?.tabs?.[activeTab]?.lazy)await loadLazyTab(activeTab);return}
    const tab2=event.target.closest('[data-bible-ref-tab2]');
    if(tab2&&panel()?.contains(tab2)){event.preventDefault();event.stopPropagation();secondaryTab=tab2.dataset.bibleRefTab2||null;renderSplitControls();renderSecondary();if(current?.tabs?.[secondaryTab]?.lazy){await loadLazyTab(secondaryTab);renderSecondary()}return}
    const retry=event.target.closest('[data-bible-retry]');
    if(retry&&history[historyIndex]){event.preventDefault();await loadVerse(history[historyIndex],{fromHistory:true,tab:history[historyIndex].tab});return}
    const back=event.target.closest('#bible-ref-back');if(back){event.preventDefault();goHistory(-1);return}
    const forward=event.target.closest('#bible-ref-forward');if(forward){event.preventDefault();goHistory(1);return}
    const openMain=event.target.closest('#bible-ref-open-main');if(openMain){event.preventDefault();openActiveInMainWindow();return}
    const mediaFullscreen=event.target.closest('[data-media-fullscreen]');
    if(mediaFullscreen&&panel()?.contains(mediaFullscreen)){event.preventDefault();const host=mediaFullscreen.closest('.bible-reference-media')||mediaFullscreen.parentElement;const target=host?.querySelector('video,img,audio')||host;try{await(target?.requestFullscreen?.()||host?.requestFullscreen?.())}catch(_error){}return}
    const mediaOpenMain=event.target.closest('[data-media-open-main]');
    if(mediaOpenMain&&panel()?.contains(mediaOpenMain)){event.preventDefault();const host=mediaOpenMain.closest('.bible-reference-media');const target=host?.querySelector('video,img,audio');const src=target?.currentSrc||target?.src;if(src)window.open(src,'_blank','noopener');return}
    const sourceButton=event.target.closest('[data-bible-source-href]');
    if(sourceButton&&panel()?.contains(sourceButton)){event.preventDefault();event.stopPropagation();await resolveSource(sourceButton.dataset.bibleSourceHref,sourceButton.textContent.trim());return}
    const sourceLink=event.target.closest('#bible-reference-content a[href]');
    if(sourceLink&&panel()?.contains(sourceLink)){
      const href=sourceLink.getAttribute('href')||'';
      if(sourceLink.closest('.bible-reference-online-card')){if(/^https?:/i.test(href)){event.preventDefault();try{await fetch('/api/open-external',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:href})})}catch(_error){}}return}
      if(/^jwpub:/i.test(href)||/^https?:/i.test(href)){event.preventDefault();event.stopPropagation();await resolveSource(href,sourceLink.textContent.trim());return}
    }
    const previewClose=event.target.closest('[data-bible-preview-close]');if(previewClose){event.preventDefault();document.querySelector('#bible-reference-preview')?.remove();return}
    const openDocumentButton=event.target.closest('#bible-reference-content [data-document-id]');
    if(openDocumentButton){event.preventDefault();const id=Number(openDocumentButton.dataset.documentId||0);if(!id)return;try{if(typeof state!=='undefined')state.pendingBlockIdentifier=openDocumentButton.dataset.blockIdentifier||null;if(typeof openDocument==='function')openDocument(id)}catch(error){if(typeof toast==='function')toast(error.message||String(error),'error')}return}
    const sourceAction=event.target.closest('[data-bible-source-action]');
    if(sourceAction&&panel()?.contains(sourceAction)){event.preventDefault();event.stopPropagation();const route=sourceAction.dataset.bibleSourceAction||'publications';try{if(typeof navigate==='function')navigate(route);else location.hash='#/'+route}catch(_error){location.hash='#/'+route}return}
    const noteButton=event.target.closest('[data-bible-create-note]');
    if(noteButton&&current){event.preventDefault();if(typeof openNoteDialog==='function')openNoteDialog({document_id:current.document_id,block_identifier:current.verse_id,content:current.verse_text||''});return}
    const external=event.target.closest('[data-open-bible-external]');
    if(external){event.preventDefault();try{await fetch('/api/open-external',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:external.dataset.openBibleExternal})})}catch(_error){}}
  },true);

  document.addEventListener('change',event=>{const splitToggle=event.target.closest('#bible-ref-split');if(splitToggle){splitEnabled=Boolean(splitToggle.checked);if(!splitEnabled)secondaryTab=null;renderSplitControls();renderSecondary()}});
  window.addEventListener('hashchange',clearWhenChapterChanged);
})();

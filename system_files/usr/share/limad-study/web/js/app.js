import{get,post,del,upload}from'./api.js';
import{icon}from'./icons.js';
import{esc,empty,formatBytes,modal,publicationCard,skeleton,toast}from'./ui.js';

const storageMemory=new Map();
function storageGet(key,fallback=''){
 try{
  const value=window.localStorage.getItem(key);
  return value===null?fallback:value;
 }catch(error){
  window.__LIMAD_STUDY_STORAGE_ERROR=(error&&error.message)||String(error);
  return storageMemory.has(key)?storageMemory.get(key):fallback;
 }
}
function storageSet(key,value){
 const text=String(value);
 storageMemory.set(key,text);
 try{window.localStorage.setItem(key,text);return true}catch(error){window.__LIMAD_STUDY_STORAGE_ERROR=(error&&error.message)||String(error);return false}
}
function applyAppearance(settings={}){
 const theme=String(settings.theme||storageGet('limad-theme','light'))==='dark'?'dark':'light';
 const fontSize=Math.min(125,Math.max(90,Number(settings.font_size||storageGet('limad-font-size','100'))||100));
 document.documentElement.dataset.theme=theme;
 document.documentElement.style.setProperty('--ui-scale',String(fontSize/100));
 storageSet('limad-theme',theme);storageSet('limad-font-size',String(fontSize));
 document.querySelectorAll('iframe.reader-frame').forEach(frame=>{try{frame.contentWindow?.postMessage({type:'limad-theme',theme},location.origin);frame.contentWindow?.postMessage({type:'limad-font',scale:readerScale()},location.origin)}catch{}});
}

function readerScale(){const value=Number(storageGet('limad-reader-scale','1'));return Math.min(1.5,Math.max(.75,Number.isFinite(value)?value:1))}
function readerQuery(extra=''){const params=new URLSearchParams(extra||'');params.set('theme',storageGet('limad-theme','light')==='dark'?'dark':'light');params.set('scale',String(readerScale()));return params.toString()}
function readerUrl(path,extra=''){const query=readerQuery(extra);return `${path}${path.includes('?')?'&':'?'}${query}`}
function setReaderScale(value,{notify=true}={}){const scale=Math.min(1.5,Math.max(.75,Math.round(Number(value)*20)/20));storageSet('limad-reader-scale',String(scale));document.querySelectorAll('[data-reader-scale-label]').forEach(node=>node.textContent=`${Math.round(scale*100)} %`);document.querySelectorAll('iframe.reader-frame').forEach(frame=>{try{frame.contentWindow?.postMessage({type:'limad-font',scale},location.origin)}catch{}});if(notify)toast(`Leseschrift ${Math.round(scale*100)} %`);return scale}
const main=document.querySelector('#main-content');
const modalRoot=document.querySelector('#modal-root');
const state={mediaCategory:'',route:'home',status:null,home:null,library:[],languageIndex:Number(storageGet('limad-language','2')),languageName:'Deutsch',selectedPublication:null,selectedDocument:null,studyTab:'notes',selection:null,meetingOffset:0,pendingBlockIdentifier:null,publicationCategory:'latest',publicationSyncing:false};
const UI_TEXT={de:{home:'Startseite',publications:'Publikationen',bible:'Bibel',video:'Video',audio:'Audio',playlists:'Playlists',downloads:'Downloads',meetings:'Zusammenkünfte',notes:'Notizen',bookmarks:'Lesezeichen',highlights:'Markierungen',tags:'Tags',backups:'Backups',settings:'Einstellungen',help:'Hilfe',dailyText:'Täglicher Text',quickAccess:'Schnellzugriff',read:'Lesen',favorites:'Favoriten',more:'Mehr anzeigen',newServer:'Neu vom Server',meetingsWeek:'Zusammenkünfte diese Woche',fullProgram:'Vollständiges Programm anzeigen',recent:'Zuletzt verwendet',publicationsTitle:'Publikationen',catalogSubtitle:'Offizieller Katalog und lokale Bibliothek',bibleTitle:'Bibel',bibleSubtitle:'Verfügbare Übersetzungen und Bibelteile',availableBibles:'Verfügbare Bibeln',searchBible:'Bibel suchen',downloaded:'Heruntergeladen',importJwpub:'.jwpub importieren'},en:{home:'Home',publications:'Publications',bible:'Bible',video:'Video',audio:'Audio',playlists:'Playlists',downloads:'Downloads',meetings:'Meetings',notes:'Notes',bookmarks:'Bookmarks',highlights:'Highlights',tags:'Tags',backups:'Backups',settings:'Settings',help:'Help',dailyText:'Daily Text',quickAccess:'Quick access',read:'Read',favorites:'Favorites',more:'Show more',newServer:'New from server',meetingsWeek:'Meetings this week',fullProgram:'View full program',recent:'Recently used',publicationsTitle:'Publications',catalogSubtitle:'Official catalog and local library',bibleTitle:'Bible',bibleSubtitle:'Available translations and Bible content',availableBibles:'Available Bibles',searchBible:'Search Bible',downloaded:'Downloaded',importJwpub:'Import .jwpub'}};
function uiLocale(){return window.LiMaDI18n?.locale||'de'}
function tr(key,fallback=''){return window.LiMaDI18n?.t(key,fallback)||UI_TEXT[uiLocale()]?.[key]||UI_TEXT.de[key]||fallback||key}
function dailyParts(daily){const fallback=String(daily.text||'').trim();if(!daily.html)return{scripture:'',comment:fallback};try{const doc=new DOMParser().parseFromString(String(daily.html),'text/html');const blocks=[...doc.querySelectorAll('p')].map(node=>node.textContent.replace(/\s+/g,' ').trim()).filter(Boolean);if(blocks.length>=2)return{scripture:blocks[0],comment:blocks.slice(1).join('\n\n')};if(blocks.length===1)return{scripture:'',comment:blocks[0]}}catch(error){}const split=fallback.split(/\n\s*\n/).map(x=>x.trim()).filter(Boolean);return split.length>1?{scripture:split[0],comment:split.slice(1).join('\n\n')}:{scripture:'',comment:fallback}}
const nav=[
 ['home','Startseite','home'],['publications','Publikationen','publications'],['bible','Bibel','bible'],['video','Video','video'],['audio','Audio','audio'],['playlists','Playlists','playlists'],['downloads','Downloads','download'],['sep','',null],['meetings','Zusammenkünfte','meetings'],['notes','Notizen','notes'],['bookmarks','Lesezeichen','bookmark'],['highlights','Markierungen','highlight'],['tags','Tags','tags'],['backups','Backups','backup'],['sep','',null],['settings','Einstellungen','settings'],['help','Hilfe','help']
];

function installChrome(){
 document.querySelector('#main-nav').innerHTML=nav.map(([route,label,name])=>route==='sep'?'<div class="nav-separator"></div>':`<button class="nav-item" data-route="${route}">${icon(name)}<span>${esc(tr(route,label))}</span></button>`).join('');
 let languageButton=document.querySelector('#global-language-button');
 if(!languageButton){
  languageButton=document.createElement('button');
  languageButton.id='global-language-button';
  languageButton.className='button app-bar-language';
  document.querySelector('#global-search').before(languageButton);
 }
 languageButton.innerHTML=`${icon('people',16)} <span>${esc(state.languageName)}</span>`;
 languageButton.onclick=openLanguage;
 document.querySelector('#global-search').innerHTML=icon('search');
 document.querySelector('#global-bookmark').innerHTML=icon('bookmark');
 document.querySelector('#global-history').innerHTML=icon('history');
 document.querySelector('#global-sync').innerHTML=icon('cloud');
 document.querySelector('#global-menu').innerHTML=icon('more');
 document.querySelector('#global-search').onclick=openSearch;
 document.querySelector('#global-bookmark').onclick=()=>navigate('bookmarks');
 document.querySelector('#global-history').onclick=()=>navigate('home');
 document.querySelector('#global-sync').onclick=syncCatalog;
 document.querySelector('#global-menu').onclick=openGlobalMenu;
 document.querySelector('#jwpub-input').onchange=event=>importFile(event.target.files[0],'jwpub');
 document.querySelector('#jwlibrary-input').onchange=event=>importFile(event.target.files[0],'jwlibrary');
 document.querySelector('#jwlplaylist-input').onchange=event=>importFile(event.target.files[0],'jwlplaylist');
}

function setActive(){document.querySelectorAll('[data-route]').forEach(node=>node.classList.toggle('active',node.dataset.route===state.route))}
async function navigate(route,params={}){if(route==='video'||route==='audio'){state.mediaCategory='';state.selectedMediaCategory='';state.mediaBreadcrumb=[];}state.route=route;Object.assign(state,params);setActive();main.classList.toggle('reader-host',route==='reader');main.scrollTop=0;main.innerHTML='<div class="page">'+skeleton(6)+'</div>';try{await render()}catch(error){main.innerHTML=`<div class="page">${empty('Ansicht konnte nicht geladen werden',error.message,`<button class="button" data-route="home">Zur Startseite</button>`)}</div>`;toast(error.message,'error')}}
async function render(){
 if(state.route==='home')return renderHome();
 if(state.route==='publications')return renderCatalogPage('publications');
 if(state.route==='bible')return renderBible();
 if(state.route==='video')return renderMedia('video');
 if(state.route==='audio')return renderMedia('audio');
 if(state.route==='playlists')return renderPlaylists();
 if(state.route==='downloads')return renderDownloads();
 if(state.route==='meetings')return renderMeetings();
 if(state.route==='notes')return renderNotes();
 if(state.route==='bookmarks')return renderBookmarks();
 if(state.route==='highlights')return renderHighlights();
 if(state.route==='tags')return renderTags();
 if(state.route==='backups')return renderBackups();
 if(state.route==='settings')return renderSettings();
 if(state.route==='help')return renderHelp();
 if(state.route==='library')return renderLibrary();
 if(state.route==='reader')return renderReader();
 return renderHome();
}
function pageHeader(title,subtitle='',actions=''){return`<header class="page-header"><div><h1>${esc(title)}</h1>${subtitle?`<p>${esc(subtitle)}</p>`:''}</div><div class="page-header-spacer"></div><button class="button global-language" data-action="language">${icon('people',18)} ${esc(state.languageName)}</button>${actions}</header>`}
function cover(item){return item.cover_url?`<img src="${esc(item.cover_url)}" alt="">`:`<span class="recent-cover"></span>`}

async function renderHome(){
 const data=await get(`/api/home?language=${state.languageIndex}`);state.home=data;
 const daily=data.daily_text||{};const day=new Date(`${daily.date}T12:00:00`);const formatted=new Intl.DateTimeFormat(uiLocale()==='en'?'en-US':'de-DE',{weekday:'long',day:'numeric',month:'long'}).format(day);const parts=dailyParts(daily);
 const fav=(data.favorites||[]).slice(0,6);
 const tools=(data.ministry_tools||[]).slice(0,6);
 const newest=(data.newest||[]).slice(0,6);
 const primary=data.meetings?.primary||{};
 const meetings=[primary.life_and_ministry,primary.watchtower].filter(Boolean);
 const dailyBody=daily.available
  ?`<div class="daily-copy"><p class="daily-scripture">${esc(parts.scripture||daily.caption||'')}</p>${parts.comment?`<p class="daily-comment">${esc(parts.comment)}</p>`:''}</div>`
  :`<div class="daily-copy unavailable"><p>${esc(daily.text||'Der Tagestext ist noch nicht lokal verfügbar.')}</p></div>`;
 const dailyAction=daily.available
  ?''
  :daily.download?.catalog_id
   ?`<button class="button primary daily-download" data-download-catalog="${daily.download.catalog_id}">${icon('download',18)} ${esc(daily.download.label||`Tagestext ${daily.download.year||''} herunterladen`)}</button>`
   :`<button class="button daily-download" data-action="sync">${icon('refresh',18)} Katalog aktualisieren</button>`;
 main.innerHTML=`<div class="page home-page">
  <section class="daily-hero daily-hero-full"><div class="calendar-icon">${icon('meetings',22)}</div><h1>${esc(formatted)}</h1>${dailyBody}${dailyAction}</section>
  <section class="section"><div class="section-heading"><h2>${esc(tr('favorites','Favoriten'))}</h2><button data-route="library">${esc(tr('more','Mehr anzeigen'))}</button></div><div class="publication-row favorites-compact">${fav.length?fav.map(item=>publicationCard({...item,cover_url:`/api/publications/${encodeURIComponent(item.id)}/cover`})).join(''):emptyInline('Noch keine Favoriten','Öffne eine Publikation und markiere sie bewusst mit dem Stern.')}</div></section>
  <section class="section ministry-tools-section"><div class="section-heading"><h2>Tools für den Predigtdienst</h2><button data-route="publications">Mehr anzeigen</button></div><div class="publication-row ministry-tools-row">${tools.length?tools.map(item=>item.installed||item.installed_id||item.id?publicationCard({...item,id:item.installed_id||item.id,cover_url:`/api/publications/${encodeURIComponent(item.installed_id||item.id)}/cover`}):publicationCard(item,{catalog:true})).join(''):emptyInline('Noch keine Predigtdienst-Tools','Katalog aktualisieren, damit die offiziellen Werkzeuge von JW.org erscheinen.')}</div></section>
  <section class="section"><div class="section-heading"><h2>${esc(tr('newServer','Neu vom Server'))}</h2><button data-action="show-new">${esc(tr('more','Mehr anzeigen'))}</button></div><div class="server-row">${newest.length?newest.map(item=>publicationCard(item,{catalog:true,compact:true})).join(''):emptyInline('Katalog nicht verfügbar','Aktualisiere den offiziellen Katalog.')}</div></section>
  <section class="panel home-meetings-compact"><div class="panel-title"><h2>${esc(tr('meetingsWeek','Zusammenkünfte diese Woche'))}</h2><button data-route="meetings">${esc(tr('fullProgram','Vollständiges Programm anzeigen'))}</button></div><div class="meeting-grid compact">${meetings.length?meetings.map(meetingItem).join(''):`<p class="unavailable">Arbeitsheft oder Wachtturm importieren beziehungsweise herunterladen.</p>`}</div></section>
 </div>`;
}
function quick(name,label,route){return`<button class="quick-card" data-route="${route}">${icon(name,30)}<span>${label}</span></button>`}
function emptyInline(title,text){return`<div class="empty-state" style="grid-column:1/-1;min-height:150px"><strong>${esc(title)}</strong><p>${esc(text)}</p></div>`}
function meetingItem(item,index){const title=cleanLabel(item.article_title||item.title||'Zusammenkunft');const detail=cleanLabel(item.article_subtitle||item.text||item.subtitle||'');const short=detail.length>150?`${detail.slice(0,147).trim()}…`:detail;return`<button class="meeting-item compact" ${item.document_id?`data-document-id="${item.document_id}"`:'data-route="publications"'}><span class="meeting-thumb">${icon(index%2?'people':'publications',25)}</span><span><strong>${esc(title)}</strong>${short?`<small>${esc(short)}</small>`:''}</span><span class="meeting-chevron">›</span></button>`}
function recentItem(item){const url=`/api/publications/${encodeURIComponent(item.id)}/cover`;return`<button class="recent-item" data-publication-id="${esc(item.id)}">${url?`<img src="${url}" alt="">`:'<span class="recent-cover"></span>'}<span><strong>${esc(item.title)}</strong><small>${esc(item.publication_type||'Publikation')}</small></span></button>`}

async function renderCatalogPage(kind){
 const isBible=kind==='bibles';
 const title=isBible?tr('bibleTitle','Bibel'):tr('publicationsTitle','Publikationen');
 if(kind==='publications'){
  const actions=`<div class="toolbar"><button class="button" data-route="downloads">${icon('download',18)} ${esc(tr('downloaded','Heruntergeladen'))}</button><button class="button" data-action="publication-refresh">${icon('refresh',18)} Aktualisieren</button><button class="button" data-action="import-jwpub">${icon('folder',18)} ${esc(tr('importJwpub','.jwpub importieren'))}</button></div>`;
  main.innerHTML=`<div class="page">${pageHeader(title,tr('catalogSubtitle','Offizieller Katalog und lokale Bibliothek'),actions)}<div class="category-grid" id="publication-categories">${publicationCategories().map(([name,label,ico])=>`<button class="category-card ${state.publicationCategory===name?'active':''}" data-catalog-kind="${name}">${icon(ico,39)}<span>${label}</span></button>`).join('')}</div><section class="section" style="margin-top:25px"><div class="section-heading"><div><h2 id="publication-result-title">Aktuelle Publikationen</h2><small id="publication-result-meta">${esc(state.languageName)} · Live-Katalog</small></div><div class="search-field">${icon('search',19)}<input id="publication-filter" placeholder="Publikationen durchsuchen"></div></div><div id="catalog-results" class="catalog-grid">${skeleton(8)}</div></section></div>`;
  await loadPublicationCategory(state.publicationCategory||'latest');
  return;
 }
 const actions=`<div class="toolbar"><button class="button" data-action="import-jwpub">${icon('folder',18)} ${esc(tr('importJwpub','.jwpub importieren'))}</button></div>`;
 main.innerHTML=`<div class="page">${pageHeader(title,tr('bibleSubtitle','Verfügbare Übersetzungen und Bibelteile'),actions)}<div class="tabs"><button class="tab active">${esc(tr('bibleTitle','Bibel').toUpperCase())}</button><button class="tab" data-route="library">${esc(tr('downloaded','Heruntergeladen').toUpperCase())}</button></div><div class="section-heading"><h2>${esc(tr('availableBibles','Verfügbare Bibeln'))}</h2><div class="page-header-spacer"></div><div class="search-field">${icon('search',19)}<input id="catalog-filter" placeholder="${esc(tr('searchBible','Bibel suchen'))}"></div></div><div id="catalog-results" class="catalog-grid">${skeleton(8)}</div></div>`;
 const items=await get(`/api/catalog/publications?language=${state.languageIndex}&kind=bibles&limit=300`);fillCatalog(items);
}
function publicationCategories(){return[
 ['latest','Aktuell','refresh'],
 ['books','Bücher','publications'],
 ['brochures','Broschüren und Booklets','notes'],
 ['tracts','Traktate und Einladungen','notes'],
 ['series','Artikelserien','publications'],
 ['watchtower-study','Wachtturm – Studienausgabe','publications'],
 ['watchtower-public','Wachtturm – Öffentlichkeitsausgabe','publications'],
 ['awake','Erwachet!','warning'],
 ['meeting-workbooks','Zusammenkunftsarbeitshefte','meetings'],
 ['kingdom-ministry','Königreichsdienst','people'],
 ['programs','Programme','clock'],
 ['index','Index und Nachschlagewerke','publications'],
 ['guidelines','Anweisungen und Richtlinien','notes']
]}
async function loadPublicationCategory(category,query=''){
 state.publicationCategory=category||'latest';
 document.querySelectorAll('[data-catalog-kind]').forEach(node=>node.classList.toggle('active',node.dataset.catalogKind===state.publicationCategory));
 const root=document.querySelector('#catalog-results');if(root)root.innerHTML=skeleton(8);
 try{
  const data=await get(`/api/publication-catalog?language=${state.languageIndex}&category=${encodeURIComponent(state.publicationCategory)}&q=${encodeURIComponent(query)}&limit=500`);
  if(state.route!=='publications')return;
  const title=document.querySelector('#publication-result-title');if(title)title.textContent=data.category_label||'Publikationen';
  const meta=document.querySelector('#publication-result-meta');if(meta)meta.textContent=`${data.language?.name||state.languageName} · ${data.count||0} Einträge · neueste zuerst`;
  fillCatalog(data.items||[]);
 }catch(error){if(root)root.innerHTML=empty('Katalog konnte nicht geladen werden',error.message);}
}
async function refreshPublicationCatalog(showMessage=true){
 if(state.publicationSyncing)return;
 state.publicationSyncing=true;
 const button=document.querySelector('[data-action="publication-refresh"]');if(button)button.disabled=true;
 try{
  await post('/api/catalog/sync',{});
  if(state.route==='publications')await loadPublicationCategory(state.publicationCategory||'latest',document.querySelector('#publication-filter')?.value||'');
  if(showMessage)toast('Publikationskatalog wurde aktualisiert.');
 }catch(error){if(showMessage)toast(`Katalogaktualisierung fehlgeschlagen: ${error.message}`,'error');}
 finally{state.publicationSyncing=false;if(button)button.disabled=false;}
}
function fillCatalog(items){const root=document.querySelector('#catalog-results');if(root)root.innerHTML=items.length?items.map(item=>publicationCard(item,{catalog:true})).join(''):empty('Keine Inhalte','Für diese Sprache und Kategorie wurden keine Inhalte gefunden.')}

function libraryGroups(items){
 const categories=new Map();
 for(const item of items){
  const key=item.library_category||'other';
  if(!categories.has(key))categories.set(key,{key,label:item.library_category_label||'Weitere Publikationen',order:Number(item.library_category_order||999),years:new Map(),count:0});
  const category=categories.get(key);const yearKey=String(Number(item.library_year||item.year||0));
  if(!category.years.has(yearKey))category.years.set(yearKey,{key:yearKey,label:item.library_year_label||(yearKey==='0'?'Ohne Jahrgang':yearKey),items:[]});
  category.years.get(yearKey).items.push(item);category.count+=1;
 }
 return[...categories.values()].sort((a,b)=>a.order-b.order||a.label.localeCompare(b.label,'de')).map(category=>({...category,years:[...category.years.values()].sort((a,b)=>Number(b.key)-Number(a.key)||a.label.localeCompare(b.label,'de')).map(year=>({...year,items:year.items.sort((a,b)=>String(a.title||'').localeCompare(String(b.title||''),'de',{numeric:true,sensitivity:'base'}))}))}));
}
function libraryTree(groups,selected){
 return`<div class="library-tree" id="library-tree">${groups.map((category,categoryIndex)=>{const categorySelected=category.years.some(year=>year.items.some(item=>String(item.id)===String(selected?.id)));return`<details class="library-category" data-library-category="${esc(category.key)}" ${(categorySelected||categoryIndex===0)?'open':''}><summary><span>${esc(category.label)}</span><b>${category.count}</b></summary><div class="library-category-body">${category.years.map((year,yearIndex)=>{const yearSelected=year.items.some(item=>String(item.id)===String(selected?.id));return`<details class="library-year" data-library-year="${esc(year.key)}" ${(yearSelected||(categoryIndex===0&&yearIndex===0))?'open':''}><summary><span>${esc(year.label)}</span><b>${year.items.length}</b></summary><div class="library-year-items">${year.items.map(item=>libraryListItem(item,String(selected?.id)===String(item.id))).join('')}</div></details>`}).join('')}</div></details>`}).join('')}</div><p class="library-filter-empty" id="library-filter-empty" hidden>Keine passende Publikation gefunden.</p>`;
}
function libraryDocumentGroups(documents){
 const groups=new Map();
 for(const item of documents){const section=Number(item.section_number||0);if(!groups.has(section))groups.set(section,[]);groups.get(section).push(item)}
 return[...groups.entries()].sort((a,b)=>a[0]-b[0]).map(([section,items])=>({section,items}));
}
function libraryToc(documents){
 const groups=libraryDocumentGroups(documents);let position=0;
 return groups.map(group=>{const showHeading=groups.length>1||group.section>0;const items=group.items.map(item=>{position+=1;const chapter=Number(item.chapter_number||0);const number=chapter>0?String(chapter).padStart(2,'0'):String(position).padStart(2,'0');const subtitle=item.subtitle||`${Number(item.paragraph_count||0)} Absätze`;return`<button class="book-toc-item" data-document-id="${item.id}"><span>${esc(number)}</span><div><strong>${esc(item.toc_title||item.title||`Kapitel ${position}`)}</strong><small>${esc(subtitle)}</small></div>${icon('arrow',18)}</button>`}).join('');return`${showHeading?`<h3 class="book-toc-section">${group.section>0?`Teil ${group.section}`:'Einleitung'}</h3>`:''}${items}`}).join('');
}
function libraryMeta(item){
 const values=[item.library_category_label,item.library_edition_label,item.language_vernacular||item.language_name,item.key_symbol?String(item.key_symbol).toUpperCase():''].filter(Boolean);
 return`<div class="book-meta">${values.map(value=>`<span>${esc(value)}</span>`).join('')}</div>`;
}
function bindLibraryFilter(){
 const input=document.querySelector('#library-filter');if(!input)return;
 input.oninput=event=>{const query=String(event.target.value||'').trim().toLocaleLowerCase('de');let visible=0;document.querySelectorAll('.library-list-item').forEach(item=>{const matches=!query||String(item.dataset.librarySearch||'').includes(query);item.hidden=!matches;if(matches)visible+=1});document.querySelectorAll('.library-year').forEach(group=>{const matches=[...group.querySelectorAll('.library-list-item')].some(item=>!item.hidden);group.hidden=!matches;if(query&&matches)group.open=true});document.querySelectorAll('.library-category').forEach(group=>{const matches=[...group.querySelectorAll('.library-list-item')].some(item=>!item.hidden);group.hidden=!matches;if(query&&matches)group.open=true});const emptyNode=document.querySelector('#library-filter-empty');if(emptyNode)emptyNode.hidden=visible>0};
}

async function renderLibrary(selectedId=null){
 state.library=await get('/api/library');
 const wanted=selectedId||state.selectedPublication;const selected=state.library.find(item=>String(item.id)===String(wanted))||state.library[0];state.selectedPublication=selected?.id||null;
 const documents=selected?await get(`/api/publications/${encodeURIComponent(selected.id)}/documents`):[];const groups=libraryGroups(state.library);const categoryCount=groups.length;
 const actions=`<button class="button" data-action="import-jwpub">${icon('folder',18)} Publikation importieren</button>`;
 const readerActions=selected?`<div class="book-pane-actions">${documents[0]?`<button class="button primary" data-document-id="${documents[0].id}">${icon('read',18)} Lesen</button>`:''}<button class="button ${selected.favorite?'favorite-active':''}" data-action="favorite" data-id="${esc(selected.id)}" data-value="${selected.favorite?0:1}">${icon('star',18)} ${selected.favorite?'Favorit entfernen':'Als Favorit'}</button><button class="button" data-remove-publication="${esc(selected.id)}">Entfernen</button></div>`:'';
 const toc=documents.length?`<div class="book-toc">${libraryToc(documents)}</div>`:empty('Kein Inhaltsverzeichnis','Diese Publikation enthält noch keine lesbaren Dokumente.');
 main.innerHTML=`<div class="page">${pageHeader('Meine Bibliothek',`${state.library.length} installierte Publikationen in ${categoryCount} Bereichen`,actions)}${state.library.length?`<div class="library-layout"><aside class="library-list"><div class="library-list-header"><div class="search-field">${icon('search',18)}<input id="library-filter" placeholder="Titel, Jahrgang oder Kategorie suchen"></div></div>${libraryTree(groups,selected)}</aside><section class="document-pane book-pane"><header class="book-pane-header">${selected?.cover_url?`<img src="${esc(selected.cover_url)}" alt="Cover von ${esc(selected.title||'Publikation')}">`:'<span class="book-pane-cover"></span>'}<div class="book-pane-title"><small>Inhaltsverzeichnis</small><h2>${esc(selected?.title||'')}</h2><p>${documents.length} ${documents.length===1?'Kapitel':'Kapitel und Themen'}</p>${selected?libraryMeta(selected):''}</div>${readerActions}</header>${toc}</section></div>`:empty('Die Bibliothek ist leer','Importiere eine .jwpub-Datei oder lade eine Publikation aus dem Katalog herunter.',`<button class="button primary" data-action="import-jwpub">.jwpub importieren</button>`)}</div>`;
 bindLibraryFilter();
}

function libraryListItem(item,active){const url=item.cover_url;const edition=item.library_edition_label||item.library_year_label||'';const details=[edition,item.language_vernacular||item.language_name||''].filter(Boolean).join(' · ');const search=String(item.library_search||[item.title,item.short_title,item.key_symbol,item.library_category_label,details].filter(Boolean).join(' ')).toLocaleLowerCase('de');return`<button class="library-list-item ${active?'active':''}" data-publication-id="${esc(item.id)}" data-library-search="${esc(search)}">${url?`<img src="${esc(url)}" alt="">`:'<span class="library-mini-cover"></span>'}<span><strong>${esc(item.title)}</strong><small>${esc(details||item.publication_type||'Publikation')}</small></span></button>`}

function documentItem(item){return`<button class="document-item" data-document-id="${item.id}"><strong>${esc(item.toc_title||item.title)}</strong><small>${esc(item.subtitle||`${item.paragraph_count||0} Absätze`)}</small></button>`}

async function renderReader(){
 main.classList.add('reader-host');
 const data=await get(`/api/documents/${state.selectedDocument}/study`);const doc=data.document;
 await post('/api/open-document',{document_id:state.selectedDocument});state.readerData=data;
 const index=data.navigation.findIndex(item=>Number(item.id)===Number(doc.id));const prev=data.navigation[index-1],next=data.navigation[index+1];
 main.innerHTML=`<div class="reader-page"><section class="reader-main"><header class="reader-toolbar"><button class="icon-button" data-route="library" title="Zurück zur Bibliothek" aria-label="Zurück zur Bibliothek">${icon('back',21)}</button><div class="reader-title"><strong>${esc(doc.publication_title)}</strong><small>${esc(doc.toc_title||doc.title)}</small></div><span class="spacer"></span><button class="icon-button" ${prev?`data-document-id="${prev.id}"`:''} title="Vorheriges Kapitel" aria-label="Vorheriges Kapitel" ${prev?'':'disabled'}>${icon('back',18)}</button><button class="icon-button" ${next?`data-document-id="${next.id}"`:''} title="Nächstes Kapitel" aria-label="Nächstes Kapitel" ${next?'':'disabled'}>${icon('forward',18)}</button><div class="reader-font-controls" role="group" aria-label="Leseschrift"><button class="reader-font-button" data-action="reader-font-down" title="Schrift verkleinern" aria-label="Schrift verkleinern">A−</button><button class="reader-font-value" data-action="reader-font-reset" title="Auf 100 Prozent zurücksetzen" data-reader-scale-label>${Math.round(readerScale()*100)} %</button><button class="reader-font-button" data-action="reader-font-up" title="Schrift vergrößern" aria-label="Schrift vergrößern">A+</button></div><button class="icon-button" data-action="new-note" title="Notiz">${icon('notes')}</button><button class="icon-button" data-action="reader-bookmark" title="Lesezeichen">${icon('bookmark')}</button><button class="icon-button" data-action="reader-toc" title="Inhalt">${icon('publications')}</button></header><iframe class="reader-frame" id="reader-frame" src="${readerUrl(`/api/documents/${doc.id}/render`)}" title="${esc(doc.title)}"></iframe></section><aside class="study-panel"><div class="study-tabs"><button class="study-tab active" data-study-tab="context">Quellen</button><button class="study-tab" data-study-tab="notes">Notizen <b>${data.notes.length}</b></button><button class="study-tab" data-study-tab="highlights">Markierungen <b>${data.marks.length}</b></button><button class="study-tab" data-study-tab="questions">Fragen <b>${data.questions.length}</b></button><button class="study-tab" data-study-tab="bookmarks">Lesezeichen <b>${data.bookmarks.length}</b></button><button class="study-tab" data-study-tab="fields">Antworten <b>${data.input_fields?.length||0}</b></button></div><div class="study-content" id="study-content">${studyPanel('context',data)}</div></aside></div>`;
}
function studyPanel(tab,data=state.readerData){if(!data)return'';if(tab==='context'){const ctx=state.readerContext||null;const footnotes=data.footnotes||[];if(ctx)return `<section class="context-panel">${(state.readerContextHistory||[]).length?`<button class="context-back" data-context-back>← Zurück</button>`:''}<div class="context-kicker">${ctx.blockIdentifier?'Absatz '+ctx.blockIdentifier:'Ausgewählte Quelle'}</div>${ctx.text?`<p class="context-verse">${esc(ctx.text)}</p>`:''}${(ctx.links||[]).length?`<div class="context-links">${ctx.links.map((x,i)=>`<button class="context-link" data-context-link="${i}">${esc(x.label||'Quelle öffnen')}</button>`).join('')}</div>`:''}<div id="context-preview"></div></section>`;return `<section class="context-panel"><h3>Quellen und Studienhinweise</h3><p>Klicke links auf eine Absatz- oder Versnummer. Bibelstellen, Fußnoten und Publikationsverweise werden hier angezeigt.</p>${footnotes.length?`<h4>Fußnoten in diesem Dokument</h4><div class="context-footnotes">${footnotes.slice(0,80).map(x=>`<article><b>${esc(x.footnote_index||x.source_footnote_id||'•')}</b><div>${x.content_html||''}</div></article>`).join('')}</div>`:''}</section>`}if(tab==='notes')return data.notes.length?data.notes.map(noteCardMini).join(''):empty('Keine Notizen','Markiere Text oder erstelle eine Notiz.',`<button class="button" data-action="new-note">Notiz erstellen</button>`);if(tab==='highlights')return data.marks.length?data.marks.map(item=>`<article class="study-note"><div class="mark-swatch mark-${Number(item.color_index||0)%5}"></div><h4>Markierung</h4><p>Absatz ${item.block_identifier??'–'}${item.start_token!=null?` · Token ${item.start_token}–${item.end_token}`:''}</p>${String(item.id).includes(':')?'':`<button class="text-button" data-delete-mark="${item.id}">Entfernen</button>`}</article>`).join(''):empty('Keine Markierungen','Wähle Text im Reader aus und lege eine Farbe fest.');if(tab==='questions')return data.questions.length?data.questions.map(item=>`<article class="study-note question-card">${item.content_html||''}</article>`).join(''):empty('Keine Studienfragen','Dieses Dokument enthält keine Fragen.');if(tab==='fields')return (data.input_fields||[]).length?data.input_fields.map(item=>`<article class="study-note"><h4>${esc(item.text_tag)}</h4><textarea data-input-field="${esc(item.text_tag)}">${esc(item.value||'')}</textarea></article>`).join(''):empty('Keine Studienantworten','Antwortfelder in unterstützten Publikationen werden automatisch gespeichert.');if(tab==='bookmarks')return data.bookmarks.length?data.bookmarks.map(item=>`<article class="study-note bookmark-card"><button class="bookmark-open" data-open-bookmark="${item.document_id||''}" data-bookmark-block="${item.block_identifier??''}"><h4>${esc(item.title||'Lesezeichen')}</h4><p>${esc(item.snippet||'')}</p></button>${item.source==='local'?`<button class="text-button" data-delete-bookmark="${item.id}">Entfernen</button>`:''}</article>`).join(''):empty('Keine Lesezeichen','Setze oben ein Lesezeichen für diese Stelle.');return''}

function normalizeContextSourceLinks(links){
 let inheritedBook='';
 let inheritedChapter='';
 return (links||[]).map(item=>{
  const copy={...item};
  const raw=String(copy.label||copy.text||'').replace(/[,;]+$/,'').trim();
  const full=raw.match(/^(.+?)\s+(\d{1,3})\s*:\s*(\d.*)$/u);
  if(full){
   inheritedBook=full[1].replace(/[;,\s]+$/,'').trim();
   inheritedChapter=full[2];
   copy.label=`${inheritedBook} ${inheritedChapter}:${full[3].trim()}`;
   copy.bibleReference=copy.label;
   return copy;
  }
  const chapterVerse=raw.match(/^(\d{1,3})\s*:\s*(\d.*)$/u);
  if(chapterVerse&&inheritedBook){
   inheritedChapter=chapterVerse[1];
   copy.label=`${inheritedBook} ${inheritedChapter}:${chapterVerse[2].trim()}`;
   copy.bibleReference=copy.label;
   return copy;
  }
  const verseOnly=raw.match(/^(\d{1,3})(?:\s*[-–—]\s*\d{1,3})?$/u);
  if(verseOnly&&inheritedBook&&inheritedChapter){
   copy.label=`${inheritedBook} ${inheritedChapter}:${raw}`;
   copy.bibleReference=copy.label;
  }
  return copy;
 });
}


function contextSourceHeader(kind,title,subtitle='',cover=''){
 return `<header class="context-source-header ${cover?'has-cover':'no-cover'}">${cover?`<img src="${esc(cover)}" alt="">`:''}<div><div class="context-source-type">${esc(kind)}</div><h4>${esc(title||'Quelle')}</h4>${subtitle?`<p>${esc(subtitle)}</p>`:''}</div></header>`
}
function contextMediaAttributes(media,kind){return `data-media-url="${esc(media.url||'')}" data-media-type="${esc(kind)}" data-media-title="${esc(media.title||'Medium')}" data-media-image="${esc(media.image||'')}" data-media-key="${esc(media.media_key||media.url||'')}" data-media-natural-key="${esc(media.natural_key||'')}" data-media-download-url="${esc(media.download_url||'')}" data-media-sources="${esc(JSON.stringify(media.sources||[]))}"`}
function onlinePreviewStatus(online){if(online.stale)return'Gespeicherte Vorschau · derzeit offline';if(online.cached)return'Aktuell geprüft · aus dem lokalen Cache';return'Aktuell von jw.org geladen'}
function renderOnlinePreview(online,candidates=[]){if(!online?.html)return'';const download=candidates.length?`<div class="context-online-download"><strong>Komplette Publikation offline verwenden</strong>${candidates.map(c=>`<button class="button" data-context-download="${c.catalog_id}">Publikation laden${c.size?` · ${formatBytes(c.size)}`:''}</button>`).join('')}</div>`:'';return `<section class="context-online-preview"><div class="context-online-meta"><span class="status-dot ${online.stale?'warning':'ok'}"></span><span>${esc(onlinePreviewStatus(online))}</span><button class="text-button" data-context-refresh>Neu prüfen</button></div>${online.image?`<img class="context-online-hero" src="${esc(online.image)}" alt="">`:''}<div class="context-online-article">${online.html}</div>${download}<div class="context-source-actions"><button class="button" data-online-large>Groß anzeigen</button>${online.url?`<button class="button" data-open-external="${esc(online.url)}">Auf jw.org öffnen</button>`:''}</div></section>`}
function openOnlinePreview(){const online=state.contextLastResult?.online_preview;if(!online?.html)return;modalRoot.innerHTML=modal({title:online.title||'Online-Quelle',wide:true,body:`<article class="online-preview-modal">${online.html}</article>`,actions:`<button class="button" data-close-modal>Schließen</button>${online.url?`<button class="button primary" data-open-external="${esc(online.url)}">Auf jw.org öffnen</button>`:''}`})}
function renderContextResult(result,item){
 const kind=result.kind||'web';state.contextLastResult=result;state.contextLastItem=item;
 if(result.resolved&&result.document){
  const document=result.document,focus=result.block_identifier||'';const preview=readerUrl(`/api/documents/${document.id}/render`,focus?`focus=${encodeURIComponent(focus)}`:'');const verse=result.verse_html?`<div class="context-bible-text">${result.verse_html}</div>`:`<iframe src="${preview}" title="Quellenvorschau" loading="lazy"></iframe>`;
  return `<article class="context-source context-source-${esc(kind)}">${contextSourceHeader(kind==='bible'?'Bibeltext':'Lokale Literatur',document.publication_title||'Quelle',result.reference||document.toc_title||document.title||'',document.cover_url||'')}${document.excerpt&&!result.verse_html?`<p class="context-excerpt">${esc(document.excerpt)}</p>`:''}${verse}<div class="context-source-actions"><button class="button primary" data-document-id="${document.id}" ${focus?`data-block-identifier="${esc(focus)}"`:''}>In der Literatur öffnen</button>${result.external&&/^https?:/i.test(result.external)?`<button class="button" data-open-external="${esc(result.external)}">Online öffnen</button>`:''}</div></article>`
 }
 if(result.media?.url){
  const media=result.media;const attrs=contextMediaAttributes(media,kind);const online=result.external&&/^https?:/i.test(result.external)?`<button class="button" data-open-external="${esc(result.external)}">Auf jw.org öffnen</button>`:'';
  if(kind==='video')return `<article class="context-source context-source-video">${contextSourceHeader('Video',media.title||item.label||'Video','',media.image||'')}<video class="context-inline-video" controls playsinline preload="metadata" ${media.image?`poster="${esc(media.image)}"`:''}><source src="${esc(media.url)}" type="${esc(media.mime_type||'video/mp4')}"></video><div class="context-video-error" hidden>Interne Wiedergabe war nicht möglich.</div><div class="context-source-actions"><button class="button" ${attrs}>Im schwebenden Player öffnen</button>${online}</div></article>`;
  if(kind==='audio')return `<article class="context-source context-source-audio">${contextSourceHeader('Audio',media.title||item.label||'Audio','',media.image||'')}<audio class="context-inline-audio" controls preload="metadata"><source src="${esc(media.url)}" type="${esc(media.mime_type||'audio/mpeg')}"></audio><div class="context-source-actions"><button class="button" ${attrs}>Im Player öffnen</button>${online}</div></article>`;
 }
 const candidates=result.catalog||[];const media=kind==='video'||kind==='audio';
 if(media)return `<article class="context-source context-source-${esc(kind)}">${contextSourceHeader(kind==='video'?'Video':'Audio',item.label||'Verknüpftes Medium',result.natural_key||'')}<div class="context-media-placeholder">${icon(kind,34)}<span>${esc(result.missing_message||'Die aktuelle Mediendatei konnte nicht geladen werden.')}</span></div>${result.resolution_error?`<div class="notice">${esc(result.resolution_error)}</div>`:''}<div class="context-source-actions">${result.external&&/^https?:/i.test(result.external)?`<button class="button primary" data-open-external="${esc(result.external)}">Auf jw.org öffnen</button>`:''}</div></article>`;
 const online=result.online_preview||null;
 return `<article class="context-source context-source-${esc(kind)}">${contextSourceHeader(online?'Online-Quelle':kind==='bible'?'Bibelstelle':'Fehlende Literatur',online?.title||item.label||'Verknüpfte Quelle',result.reference||'',online?.image||'')}${online?renderOnlinePreview(online,candidates):`<p>${esc(result.missing_message||'Diese Quelle konnte lokal noch nicht aufgelöst werden.')}</p>`}${!online&&candidates.length?`<div class="context-download-list">${candidates.map(c=>`<article><div><strong>${esc(c.title||c.short_title||'Publikation')}</strong><small>${esc([c.key_symbol,c.year,c.issue_tag].filter(Boolean).join(' · '))}${c.size?` · ${formatBytes(c.size)}`:''}</small></div><button class="button primary" data-context-download="${c.catalog_id}">Herunterladen und öffnen</button></article>`).join('')}</div>`:''}${!online&&!candidates.length?`<div class="notice">Keine direkte JWPUB-Downloadoption gefunden. Die Quelle kann weiterhin online oder über einen manuellen Import geöffnet werden.</div>`:''}<div id="context-download-progress"></div>${!online?`<div class="context-source-actions">${!candidates.length?`<button class="button" data-action="import-jwpub">JWPUB importieren</button>`:''}${result.external&&/^https?:/i.test(result.external)?`<button class="button ${candidates.length?'':'primary'}" data-open-external="${esc(result.external)}">Online öffnen</button>`:''}</div>`:''}</article>`
}
async function resolveContextItem(item,{refresh=false}={}){
 const preview=document.querySelector('#context-preview');if(preview)preview.innerHTML='<div class="context-loading">Quelle wird geladen …</div>';state.contextLastItem=item;
 try{const result=await get(`/api/resolve?link=${encodeURIComponent(item.href||'')}&label=${encodeURIComponent(item.label||'')}&language=${state.languageIndex}${refresh?'&refresh=1':''}`);if(preview)preview.innerHTML=renderContextResult(result,item);bindContextInlineMedia(preview)}catch(error){if(preview)preview.innerHTML=`<div class="notice warning"><strong>Quelle konnte nicht geladen werden</strong><span>${esc(error.message)}</span></div>`}
}
function bindContextInlineMedia(root){
 root?.querySelectorAll('video').forEach(video=>video.addEventListener('error',()=>{const error=video.parentElement?.querySelector('.context-video-error');if(error)error.hidden=false},{once:true}));
}
async function startContextDownload(catalogId){
 const item=state.contextLastItem;if(!item)return;const host=document.querySelector('#context-download-progress');if(host)host.innerHTML='<div class="context-download-status"><div class="progress"><span style="width:0"></span></div><p>Download wird vorbereitet …</p><small>0 B</small></div>';
 try{const response=await post('/api/downloads',{catalog_id:Number(catalogId),option_index:0});const jobId=response.job.id;for(let attempt=0;attempt<3600;attempt++){await new Promise(resolve=>setTimeout(resolve,700));const jobs=await get('/api/downloads');const job=jobs.find(entry=>entry.id===jobId);if(!job)continue;const node=document.querySelector('.context-download-status');if(node){const value=Math.min(100,Number(job.progress||0));node.querySelector('.progress span').style.width=`${value}%`;node.querySelector('p').textContent=job.status_label||job.status;node.querySelector('small').textContent=`${formatBytes(job.received_size)} von ${formatBytes(job.expected_size)} · ${value.toFixed(1)} %`}if(job.status==='completed'){toast('Publikation wurde importiert. Die Quelle wird geöffnet.');await new Promise(resolve=>setTimeout(resolve,450));await resolveContextItem(item);return}if(job.status==='failed'||job.status==='cancelled')throw new Error(job.error||'Download fehlgeschlagen.')}throw new Error('Zeitüberschreitung bei der Downloadüberwachung.')
 }catch(error){const host=document.querySelector('#context-download-progress');if(host)host.innerHTML=`<div class="notice warning"><strong>Download fehlgeschlagen</strong><span>${esc(error.message)}</span></div>`;toast(error.message,'error')}
}
function openReaderImage(data){
 const src=String(data?.src||'');if(!src)return;modalRoot.innerHTML=modal({title:data.caption||data.alt||'Abbildung',wide:true,body:`<div class="reader-image-viewer"><img src="${esc(src)}" alt="${esc(data.alt||'')}">${data.caption?`<p>${esc(data.caption)}</p>`:''}</div>`,actions:'<button class="button" data-close-modal>Schließen</button>'})
}

function noteCardMini(note){return`<article class="study-note"><h4>${esc(note.title||'Notiz')}</h4><p>${esc(note.content||'')}</p>${note.tags?`<small>${esc(note.tags)}</small>`:''}${note.source==='local'?`<button class="text-button" data-delete-note="${note.id}">Löschen</button>`:''}</article>`}

async function renderMedia(type){
 const title=type==='video'?'Videos':'Audio';
 const local=await get(`/api/media?type=${type}`);
 let remote={title,categories:[],media:[],category:''};let remoteError='';
 try{remote=await get(`/api/media/catalog?type=${type}&language=${state.languageIndex}&category=${encodeURIComponent(state.mediaCategory||'')}`)}catch(error){remoteError=error.message}
 const categoryCards=(remote.categories||[]).map(item=>`<article class="media-category-card"><button data-media-category="${esc(item.key)}">${item.image?`<img src="${esc(item.image)}" alt="">`:`<span class="cover-placeholder">${icon(type,38)}</span>`}<span><strong>${esc(item.title)}</strong>${item.description?`<small>${esc(item.description)}</small>`:''}</span></button></article>`).join('');
 const remoteCards=(remote.media||[]).map(item=>`<article class="publication-card"><button class="cover-button" data-media-url="${esc(item.url)}" data-media-key="${esc(item.natural_key||item.url)}" data-media-title="${esc(item.title)}" data-media-type="${type}" data-publication-id-media="" data-file-path="" data-media-image="${esc(item.image||'')}" data-media-natural-key="${esc(item.natural_key||'')}" data-media-sources="${esc(JSON.stringify(item.sources||[]))}">${item.image?`<img src="${esc(item.image)}" alt="">`:`<span class="cover-placeholder">${icon(type,40)}</span>`}</button><div class="publication-card-body"><strong>${esc(item.title)}</strong><small>${esc(item.first_published||item.mime_type||'JW.ORG')}</small></div></article>`).join('');
 const localCards=local.map(item=>`<article class="publication-card"><button class="cover-button" data-media-url="${esc(item.url)}" data-media-key="${esc(item.media_key||item.url)}" data-media-title="${esc(item.label||item.file_path)}" data-media-type="${type}" data-publication-id-media="${esc(item.publication_id||'')}" data-file-path="${esc(item.file_path||'')}">${item.preview?`<img src="${esc(item.preview)}" alt="">`:`<span class="cover-placeholder">${icon(type,40)}</span>`}</button><div class="publication-card-body"><strong>${esc(item.label||item.file_path)}</strong><small>${esc(item.publication_title||item.mime_type)}</small></div></article>`).join('');
 main.innerHTML=`<div class="page">${pageHeader(title,'Offizielle Kategorien und lokal verfügbare Medien',`<div class="toolbar"><button class="button" data-route="downloads">${icon('download',18)} Heruntergeladen</button></div>`)}${state.mediaCategory?`<button class="button media-back" data-media-back>${icon('back',18)} Zurück</button>`:''}<section class="media-section"><h2>${esc(remote.title||title)}</h2>${categoryCards?`<div class="media-category-grid">${categoryCards}</div>`:''}${remoteCards?`<div class="catalog-grid">${remoteCards}</div>`:(!categoryCards&&!remoteError?empty('Keine Medien gefunden','In dieser Kategorie sind derzeit keine Einträge vorhanden.'):'')}${remoteError?`<div class="notice warning"><strong>Online-Katalog nicht erreichbar</strong><span>${esc(remoteError)}</span></div>`:''}</section><section class="media-section"><h2>Lokal verfügbar</h2>${localCards?`<div class="catalog-grid">${localCards}</div>`:empty(`Keine lokalen ${title}`,`Importierte oder heruntergeladene ${title} erscheinen hier.`)}</section></div>`;
 document.querySelectorAll('[data-media-category]').forEach(button=>button.addEventListener('click',()=>{state.mediaCategory=button.dataset.mediaCategory;renderMedia(type)}));
 document.querySelector('[data-media-back]')?.addEventListener('click',()=>{state.mediaCategory='';renderMedia(type)});
}


const BIBLE_UI_KEY='limad-bible-workspace-v2';
function bibleUiState(){
 const fallback={tabs:[],activeTab:0,section:'books',query:'',notesOpen:false,focus:false,split:false,comparePublicationId:'',favoriteBooks:[],recent:[]};
 try{return {...fallback,...JSON.parse(storageGet(BIBLE_UI_KEY,'{}'))}}catch{return fallback}
}
function saveBibleUi(next){storageSet(BIBLE_UI_KEY,JSON.stringify(next));return next}
function bibleTabKey(tab){return `${tab.publicationId}:${tab.book}:${tab.chapter}`}
function normalizeBibleTabs(ui,primary,bookNumber,chapterNumber,bookTitle){
 const current={publicationId:primary.id,publicationTitle:primary.title,book:Number(bookNumber),chapter:Number(chapterNumber),bookTitle:String(bookTitle||'Bibel')};
 let tabs=Array.isArray(ui.tabs)?ui.tabs.filter(x=>x&&x.publicationId&&Number(x.book)>0&&Number(x.chapter)>0):[];
 if(!tabs.length)tabs=[current];
 let active=Math.min(Math.max(Number(ui.activeTab)||0,0),tabs.length-1);
 const activeItem=tabs[active];
 if(!activeItem||activeItem.publicationId!==current.publicationId||Number(activeItem.book)!==current.book||Number(activeItem.chapter)!==current.chapter){
  tabs[active]=current;
 }
 return {...ui,tabs,activeTab:active};
}
function bibleLocationLabel(tab){return `${tab.bookTitle||'Buch '+tab.book} ${tab.chapter}`}
function bibleRecentPush(ui,tab){
 const item={...tab,openedAt:new Date().toISOString()};
 const recent=[item,...(Array.isArray(ui.recent)?ui.recent:[]).filter(x=>bibleTabKey(x)!==bibleTabKey(item))].slice(0,12);
 return {...ui,recent};
}
function bibleBookFromSearch(item,books){
 const text=`${item.title||''} ${item.snippet||''}`.toLowerCase();
 const book=[...books].sort((a,b)=>String(b.title).length-String(a.title).length).find(x=>text.includes(String(x.title||'').toLowerCase()));
 if(!book)return null;
 const patterns=[new RegExp(`${String(book.title).replace(/[.*+?^${}()|[\]\\]/g,'\\$&')}\\s+(\\d{1,3})`,'i'),/kapitel\s+(\d{1,3})/i];
 let chapter=Number(item.chapter_number||0);
 for(const pattern of patterns){const match=text.match(pattern);if(match){chapter=Number(match[1]);break}}
 if(!book.chapters?.some(x=>Number(x.chapter_number)===chapter))chapter=Number(book.chapters?.[0]?.chapter_number||1);
 return {book:Number(book.book_number),chapter,bookTitle:book.title};
}
function shortBibleBookTitle(title){
 const map={'Das erste Buch Mose':'1. Mose','Das zweite Buch Mose':'2. Mose','Das dritte Buch Mose':'3. Mose','Das vierte Buch Mose':'4. Mose','Das fünfte Buch Mose':'5. Mose','Das erste Buch Samuel':'1. Samuel','Das zweite Buch Samuel':'2. Samuel','Das erste Buch der Könige':'1. Könige','Das zweite Buch der Könige':'2. Könige','Das erste Buch der Chronika':'1. Chronika','Das zweite Buch der Chronika':'2. Chronika','Der erste Brief an die Korinther':'1. Korinther','Der zweite Brief an die Korinther':'2. Korinther','Der erste Brief an die Thessalonicher':'1. Thessalonicher','Der zweite Brief an die Thessalonicher':'2. Thessalonicher','Der erste Brief an Timotheus':'1. Timotheus','Der zweite Brief an Timotheus':'2. Timotheus','Der erste Brief von Petrus':'1. Petrus','Der zweite Brief von Petrus':'2. Petrus','Der erste Brief von Johannes':'1. Johannes','Der zweite Brief von Johannes':'2. Johannes','Der dritte Brief von Johannes':'3. Johannes'};
 return map[String(title||'')]||String(title||'').replace(/^Das (erste|zweite|dritte|vierte|fünfte) Buch Mose$/i,(m,n)=>({'erste':'1.','zweite':'2.','dritte':'3.','vierte':'4.','fünfte':'5.'}[n.toLowerCase()]||n)+' Mose');
}
function bibleSidebarBookList(books,bookNumber,favorites){
 return books.map(book=>`<button class="bible-v2-book ${Number(book.book_number)===Number(bookNumber)?'active':''}" data-bible-book="${book.book_number}"><span title="${esc(book.title)}">${esc(shortBibleBookTitle(book.title))}</span><small>${book.chapter_count||book.chapters?.length||0}</small><i class="bible-v2-favorite ${favorites.includes(Number(book.book_number))?'active':''}" data-bible-favorite="${book.book_number}" title="Favorit">★</i></button>`).join('')
}
function bibleNotesPanel(study){
 if(!study)return '<div class="bible-v2-empty">Studieninformationen werden geladen.</div>';
 const notes=(study.notes||[]).map(note=>`<article><strong>${esc(note.title||'Notiz')}</strong><p>${esc(note.content||'')}</p></article>`).join('');
 const marks=(study.marks||[]).map(mark=>`<article><span class="mark-swatch mark-${Number(mark.color_index||0)%5}"></span><strong>Markierung</strong><p>Vers/Absatz ${mark.block_identifier??'–'}</p></article>`).join('');
 const bookmarks=(study.bookmarks||[]).map(item=>`<article><strong>${esc(item.title||'Lesezeichen')}</strong><p>${esc(item.snippet||'')}</p></article>`).join('');
 return `${notes||'<div class="bible-v2-empty">Noch keine Notizen in diesem Kapitel.</div>'}${marks}${bookmarks}`
}
function ensureBibleMessageBridge(){
 if(window.__LIMAD_BIBLE_BRIDGE)return;
 window.__LIMAD_BIBLE_BRIDGE=true;
 window.addEventListener('message',async event=>{
  if(event.origin!==location.origin)return;
  const data=event.data||{};
  if(data.type!=='limad-bible-verse-action')return;
  const documentId=Number(data.documentId||state.selectedDocument||0);if(!documentId)return;
  const blockIdentifier=Number(data.blockIdentifier||0)||null;
  const text=String(data.text||'').trim();
  try{
   if(data.action==='note'){openNoteDialog({document_id:documentId,block_identifier:blockIdentifier,content:text});return}
   if(data.action==='bookmark'){await post('/api/bookmarks',{document_id:documentId,title:data.reference||state.readerData?.document?.title||'Bibelstelle',snippet:text,block_identifier:blockIdentifier});toast('Bibelstelle als Lesezeichen gespeichert.');await renderBible();return}
   if(data.action==='highlight'){const response=await post('/api/marks',{document_id:documentId,block_identifier:blockIdentifier,start_token:null,end_token:null,color_index:Number(data.colorIndex||0)});const mark={...(response.mark||{}),text};if(state.readerData){const marks=state.readerData.marks||(state.readerData.marks=[]);marks.push(mark)}readerFrameMessage(event.source,'limad-mark-applied',{mark});refreshReaderMarkUi();toast('Vers markiert.');return}
   const shareText=`${data.reference||state.readerData?.document?.title||'Bibelstelle'}\n${text}`.trim();
   if(data.action==='share'&&navigator.share){await navigator.share({title:data.reference||'Bibelstelle',text:shareText});return}
   if(data.action==='copy'||data.action==='share'){await navigator.clipboard.writeText(shareText);toast('Bibelstelle kopiert.');return}
  }catch(error){toast(error.message||String(error),'error')}
 });
}

function setupBibleColumnResizing(){
 const root=document.querySelector('.bible-v2-grid');if(!root)return;
 const saved=JSON.parse(localStorage.getItem('limad-bible-column-widths')||'{}');
 if(saved.books)root.style.setProperty('--bible-books-width',saved.books+'px');
 if(saved.chapters)root.style.setProperty('--bible-chapters-width',saved.chapters+'px');
 root.querySelectorAll('[data-bible-resize]').forEach(splitter=>{
  splitter.onpointerdown=event=>{event.preventDefault();splitter.setPointerCapture(event.pointerId);const type=splitter.dataset.bibleResize;const start=event.clientX;const current=parseFloat(getComputedStyle(root).getPropertyValue(type==='books'?'--bible-books-width':'--bible-chapters-width'))||(type==='books'?220:190);
   splitter.onpointermove=move=>{const value=Math.max(type==='books'?180:150,Math.min(type==='books'?380:320,current+move.clientX-start));root.style.setProperty(type==='books'?'--bible-books-width':'--bible-chapters-width',value+'px')};
   splitter.onpointerup=()=>{const widths={books:parseFloat(getComputedStyle(root).getPropertyValue('--bible-books-width')),chapters:parseFloat(getComputedStyle(root).getPropertyValue('--bible-chapters-width'))};localStorage.setItem('limad-bible-column-widths',JSON.stringify(widths));splitter.onpointermove=null;splitter.onpointerup=null};
  };
 });
}
function renderPlaylists(){return get('/api/playlists').then(items=>{main.innerHTML=`<div class="page">${pageHeader('Playlists','Eigene Medienzusammenstellungen',`<button class="button primary" data-action="new-playlist">${icon('plus',18)} Neue Playlist</button>`)}${items.length?`<div class="playlist-grid">${items.map(item=>`<article class="panel playlist-card"><div><h2>${esc(item.title||'Playlist')}</h2><p>${esc(item.description||'')}</p><small>${(item.items||[]).length} Elemente</small></div><div class="card-actions"><button class="button" data-delete-playlist="${esc(item.id)}">Entfernen</button></div></article>`).join('')}</div>`:empty('Keine Playlists','Erstelle eine Playlist oder importiere eine .jwlplaylist-Datei.',`<button class="button primary" data-action="new-playlist">Neue Playlist</button>`)}</div>`}).catch(error=>{main.innerHTML=`<div class="page">${pageHeader('Playlists')} ${empty('Ansicht konnte nicht geladen werden',error.message||String(error))}</div>`})}

async function renderBible(){
 ensureBibleMessageBridge();
 const installed=await get(`/api/bibles?language=${state.languageIndex}`);
 const catalog=await get(`/api/catalog/publications?language=${state.languageIndex}&kind=bibles&limit=300`);
 const actions=`<div class="toolbar"><button class="button" data-action="import-jwpub">${icon('folder',18)} .jwpub importieren</button><button class="button" data-action="bible-catalog">${icon('plus',18)} Bibel hinzufügen</button></div>`;
 if(!installed.length){main.innerHTML=`<div class="page">${pageHeader('Bibel','Bibelübersetzung auswählen und herunterladen',actions)}<div class="catalog-grid">${catalog.map(item=>publicationCard(item,{catalog:true})).join('')||empty('Keine Bibel gefunden','Für diese Sprache ist keine Bibel im Katalog vorhanden.')}</div></div>`;return}
 const view=await get(`/api/bibles/view-state?language=${state.languageIndex}`);
 let ui=bibleUiState();
 if(!ui.screen)ui.screen='library';
 if(!ui.librarySection)ui.librarySection='books';
 const storedTab=ui.tabs?.[Math.min(Math.max(Number(ui.activeTab)||0,0),Math.max((ui.tabs?.length||1)-1,0))];
 const primary=installed.find(x=>x.id===(storedTab?.publicationId||view.primary_publication_id))||installed[0];
 const navigation=await get(`/api/bibles/${encodeURIComponent(primary.id)}/navigation`);
 let overview;
 try{overview=await get(`/api/bibles/${encodeURIComponent(primary.id)}/overview`)}catch{overview={sections:[],books:navigation.books||[]}}
 const books=(overview.books&&overview.books.length?overview.books:navigation.books)||[];
 const requestedBook=Number(ui.selectedBook||storedTab?.book||view.book_number||1);
 const bookNumber=books.some(x=>Number(x.book_number)===requestedBook)?requestedBook:Number(books[0]?.book_number||1);
 const selectedBook=books.find(x=>Number(x.book_number)===bookNumber)||books[0];
 const requestedChapter=Number(storedTab?.chapter||view.chapter_number||1);
 const chapterNumber=selectedBook?.chapters?.some(x=>Number(x.chapter_number)===requestedChapter)?requestedChapter:Number(selectedBook?.chapters?.[0]?.chapter_number||1);
 ui=normalizeBibleTabs(ui,primary,bookNumber,chapterNumber,selectedBook?.title);
 ui.comparePublicationId=installed.some(x=>x.id===ui.comparePublicationId)?ui.comparePublicationId:(view.compare_publication_id||installed.find(x=>x.id!==primary.id)?.id||'');
 ui.selectedBook=bookNumber;
 saveBibleUi(ui);
 const sectionLabels={introduction:'EINFÜHRUNG',books:'BÜCHER',index:'INDEX',appendix_a:'ANHANG A',appendix_b:'ANHANG B',appendix_c:'ANHANG C'};
 const sections=['introduction','books','index','appendix_a','appendix_b','appendix_c'].map(key=>(overview.sections||[]).find(item=>item.key===key)||{key,title:sectionLabels[key],items:[]});
 const codes=['1Mo','2Mo','3Mo','4Mo','5Mo','Jos','Ri','Ru','1Sa','2Sa','1Kö','2Kö','1Ch','2Ch','Esr','Ne','Est','Hi','Ps','Spr','Pr','Hoh','Jes','Jer','Klg','Hes','Da','Hos','Joel','Am','Ob','Jon','Mi','Nah','Hab','Ze','Hag','Sach','Mal','Mat','Mar','Luk','Joh','Apg','Rö','1Ko','2Ko','Gal','Eph','Php','Kol','1Th','2Th','1Ti','2Ti','Tit','Phm','Heb','Jak','1Pe','2Pe','1Jo','2Jo','3Jo','Jud','Off'];
 const bibleTabs=()=>`<nav class="bible-original-tabs" aria-label="Bibelbereiche">${sections.map(item=>`<button class="${ui.librarySection===item.key?'active':''}" data-bible-library-section="${item.key}">${esc(item.title||sectionLabels[item.key])}</button>`).join('')}</nav>`;
 const versionSelect=()=>`<select id="bible-primary" class="select bible-original-version">${installed.map(x=>`<option value="${esc(x.id)}" ${primary.id===x.id?'selected':''}>${esc(x.title)}</option>`).join('')}</select>`;
 const bookGrid=(items,testament)=>`<section class="bible-original-book-section"><h2>${testament==='hebrew'?'HEBRÄISCH-ARAMÄISCHE SCHRIFTEN':'CHRISTLICHE GRIECHISCHE SCHRIFTEN'}</h2><div class="bible-original-book-grid">${items.map(book=>`<button class="bible-original-book tone-${(Number(book.book_number)-1)%6}" data-bible-book-card="${book.book_number}" title="${esc(book.display_title||book.title)}"><strong>${esc(codes[Number(book.book_number)-1]||shortBibleBookTitle(book.title))}</strong><span>${esc(shortBibleBookTitle(book.title))}</span></button>`).join('')}</div></section>`;
 const sectionCards=(items,depth=0)=>items.map(item=>{
  const nested=item.children?.length?sectionCards(item.children,depth+1):'';
  if(!item.document_id)return `<section class="bible-original-group depth-${Math.min(depth,3)}"><h3>${esc(item.title)}</h3>${nested}</section>`;
  const image=item.thumbnail_url?`<img src="${esc(item.thumbnail_url)}" alt="">`:`<span class="bible-original-card-placeholder">${icon(item.has_video?'video':'book',30)}</span>`;
  return `<article class="bible-original-document-card depth-${Math.min(depth,3)}"><button data-bible-document="${item.document_id}" data-bible-document-title="${esc(item.title)}">${image}<span><strong>${esc(item.title)}</strong>${item.has_video?'<small>Video innerhalb von LiMaD abspielen</small>':''}</span><i>›</i></button></article>${nested}`
 }).join('');
 const referencePanel=()=>`<aside class="bible-v2-reference bible-original-reference glass-panel">
  <div class="bible-reference-toolbar"><button class="icon-button" id="bible-ref-back" title="Zurück" disabled>${icon('back',17)}</button><button class="icon-button" id="bible-ref-forward" title="Vor" disabled>${icon('forward',17)}</button><button class="icon-button" id="bible-ref-open-main" title="Im Hauptfenster öffnen">${icon('forward',17)}</button><label class="bible-ref-split-toggle"><input type="checkbox" id="bible-ref-split"> Zwei Quellen nebeneinander</label></div>
  <div class="bible-reference-tabs"><button class="active" data-count="0" data-bible-ref-tab="guide">Studienleitfaden</button><button data-count="0" data-bible-ref-tab="insight">Einsichten</button><button data-count="0" data-bible-ref-tab="cross">Querverweise</button><button data-count="0" data-bible-ref-tab="notes">Notizen</button><button data-count="0" data-bible-ref-tab="parallel">Parallelübersetzungen</button></div>
  <div class="bible-reference-tabs bible-reference-tabs-secondary" id="bible-ref-tabs-secondary" hidden></div><h3 id="bible-reference-title">Studienmaterial</h3><div id="bible-reference-content"><div class="bible-v2-empty">Tippe einen Vers an, um Studienleitfaden, Einsichten und Querverweise anzuzeigen.</div></div><div id="bible-reference-content-secondary" class="bible-reference-content-secondary" hidden></div>
 </aside>`;
 const notesPanel=study=>`<aside class="bible-v2-notes"><header><strong>Notizen & Markierungen</strong><button class="icon-button" data-bible-notes>×</button></header><div>${bibleNotesPanel(study)}</div><button class="button primary" data-action="new-note">Notiz erstellen</button></aside>`;
 const setScreen=(screen,extra={})=>{const next=bibleUiState();Object.assign(next,{screen},extra);saveBibleUi(next);renderBible()};
 const openChapter=async(book,chapter)=>{
  const targetBook=Number(book),targetChapter=Number(chapter),next=bibleUiState();
  const active=Math.min(Math.max(Number(next.activeTab)||0,0),Math.max((next.tabs?.length||1)-1,0));
  const bookItem=books.find(x=>Number(x.book_number)===targetBook);
  next.tabs=Array.isArray(next.tabs)&&next.tabs.length?next.tabs:[{}];
  next.tabs[active]={publicationId:primary.id,publicationTitle:primary.title,book:targetBook,chapter:targetChapter,bookTitle:bookItem?.title||'Bibel'};
  next.selectedBook=targetBook;next.screen='chapter';next.activeTab=active;saveBibleUi(next);
  await post('/api/bibles/view-state',{language_index:state.languageIndex,primary_publication_id:primary.id,compare_publication_id:next.comparePublicationId||null,book_number:targetBook,chapter_number:targetChapter,split_enabled:Boolean(next.split)});
  renderBible()
 };
 let screenHtml='';
 if(ui.screen==='library'){
  const section=sections.find(item=>item.key===ui.librarySection)||sections[1];
  const hebrew=books.filter(x=>x.testament==='hebrew'),greek=books.filter(x=>x.testament==='greek');
  const content=ui.librarySection==='books'?`${bookGrid(hebrew,'hebrew')}${bookGrid(greek,'greek')}`:`<div class="bible-original-document-list">${sectionCards(section.items||[])||'<div class="bible-v2-empty">In diesem Bereich wurden keine Dokumente gefunden.</div>'}</div>`;
  screenHtml=`<div class="page bible-original bible-original-library">${pageHeader('Studienbibel',primary.title,actions)}<div class="bible-original-topline">${versionSelect()}<label class="bible-original-search"><span>${icon('search',18)}</span><input id="bible-original-search" placeholder="Bibelstelle oder Begriff suchen"></label></div>${bibleTabs()}<div id="bible-original-search-results"></div><main class="bible-original-library-content">${content}</main></div>`;
 }else if(ui.screen==='chapters'){
  const chapters=selectedBook?.chapters||[];
  screenHtml=`<div class="page bible-original bible-original-chapters">${pageHeader(selectedBook?.title||'Bibel','Kapitel auswählen',actions)}<div class="bible-original-reader-toolbar"><button class="button secondary" data-bible-back="library">${icon('back',18)} Zurück</button>${versionSelect()}</div><div class="bible-original-chapter-grid">${chapters.map(item=>`<button data-bible-chapter-card="${item.chapter_number}" class="${item.available===false?'unavailable':''}">${item.chapter_number}</button>`).join('')}</div><div class="bible-original-book-extras">${selectedBook?.intro_document_id?`<button class="bible-original-extra" data-bible-document="${selectedBook.intro_document_id}" data-bible-document-title="Einführung in ${esc(shortBibleBookTitle(selectedBook.title))}" data-bible-document-return="chapters">${icon('help',24)} <span>Einführung in ${esc(shortBibleBookTitle(selectedBook.title))}</span>${selectedBook.intro_has_video?'<small>mit Video</small>':''}</button>`:''}${selectedBook?.outline_document_id?`<button class="bible-original-extra" data-bible-document="${selectedBook.outline_document_id}" data-bible-document-title="Übersicht ${esc(shortBibleBookTitle(selectedBook.title))}" data-bible-document-return="chapters">${icon('read',24)} <span>Übersicht zum Bibelbuch</span></button>`:''}</div></div>`;
 }else if(ui.screen==='document'){
  const documentId=Number(ui.documentId||0);
  let documentData=null,studyData=null;
  if(documentId){documentData=await get(`/api/documents/${documentId}`);state.selectedDocument=documentId;try{studyData=await get(`/api/documents/${documentId}/study`);state.readerData=studyData}catch{state.readerData={document:documentData}}}
  screenHtml=`<div class="page bible-original bible-original-reading">${pageHeader(ui.documentTitle||documentData?.title||'Studienbibel',primary.title,actions)}<div class="bible-original-reader-toolbar"><button class="button secondary" data-bible-back="${esc(ui.documentReturn||'library')}">${icon('back',18)} Zurück</button><span class="spacer"></span><button class="button secondary" data-bible-notes>Notizen</button></div><div class="bible-original-reading-grid"><section class="bible-v2-reader bible-original-reader glass-panel ${ui.notesOpen?'with-notes':''}">${documentId?`<iframe class="reader-frame bible-v2-frame" id="reader-frame" src="${readerUrl(`/api/documents/${documentId}/render`)}" title="${esc(ui.documentTitle||documentData?.title||'Dokument')}"></iframe>`:empty('Dokument nicht gefunden','Der ausgewählte Inhalt ist nicht verfügbar.')}${notesPanel(studyData)}</section>${referencePanel()}</div></div>`;
 }else{
  const selectedChapter=selectedBook?.chapters?.find(x=>Number(x.chapter_number)===chapterNumber);
  let chapterData=null,studyData=null;
  if(primary&&selectedChapter?.available!==false){chapterData=await get(`/api/bibles/${encodeURIComponent(primary.id)}/chapter/${bookNumber}/${chapterNumber}`);state.selectedDocument=Number(chapterData.document_id);try{studyData=await get(`/api/documents/${state.selectedDocument}/study`);state.readerData=studyData}catch{state.readerData={document:{id:state.selectedDocument,title:chapterData.title,publication_title:primary.title}}}}
  const prev=chapterNumber>Number(selectedBook?.chapters?.[0]?.chapter_number||1)?chapterNumber-1:null;
  const next=selectedBook?.chapters?.some(x=>Number(x.chapter_number)===chapterNumber+1)?chapterNumber+1:null;
  const compareId=ui.comparePublicationId;
  const compareFrame=ui.split&&compareId?`<iframe class="reader-frame bible-v2-frame" src="${readerUrl(`/api/bibles/${encodeURIComponent(compareId)}/chapter/${bookNumber}/${chapterNumber}/render`)}" title="Vergleichsansicht"></iframe>`:'';
  screenHtml=`<div class="page bible-original bible-original-reading">${pageHeader(`${selectedBook?.title||'Bibel'} ${chapterNumber}`,'Studienbibel',actions)}<div class="bible-original-reader-toolbar"><button class="button secondary" data-bible-back="chapters">${icon('back',18)} Kapitel</button><button class="icon-button" data-bible-prev ${prev?'':'disabled'} title="Vorheriges Kapitel">${icon('back',18)}</button><strong>${esc(selectedBook?.title||'')} ${chapterNumber}</strong><button class="icon-button" data-bible-next ${next?'':'disabled'} title="Nächstes Kapitel">${icon('forward',18)}</button><span class="spacer"></span>${versionSelect()}<label class="bible-v2-split-toggle"><input type="checkbox" id="bible-split" ${ui.split?'checked':''}> Vergleich</label>${ui.split?`<select id="bible-compare" class="select"><option value="">Übersetzung wählen</option>${installed.filter(x=>x.id!==primary.id).map(x=>`<option value="${esc(x.id)}" ${compareId===x.id?'selected':''}>${esc(x.title)}</option>`).join('')}</select>`:''}<button class="button secondary" data-bible-notes>Notizen</button></div><div class="bible-original-reading-grid"><section class="bible-v2-reader bible-original-reader glass-panel ${ui.notesOpen?'with-notes':''}">${primary&&selectedChapter?.available!==false?`<div class="bible-v2-reading-panes ${ui.split&&compareId?'split':''}"><iframe class="reader-frame bible-frame bible-v2-frame" id="reader-frame" src="${readerUrl(`/api/bibles/${encodeURIComponent(primary.id)}/chapter/${bookNumber}/${chapterNumber}/render`)}" title="${esc(selectedBook.title)} ${chapterNumber}"></iframe>${compareFrame}</div>`:empty('Bibeltext nicht verfügbar','Dieses Kapitel ist in der ausgewählten Übersetzung nicht vorhanden.')}${notesPanel(studyData)}</section>${referencePanel()}</div></div>`;
  ui=bibleRecentPush(ui,ui.tabs[ui.activeTab]);saveBibleUi(ui);
 }
 main.innerHTML=screenHtml;
 document.querySelectorAll('[data-bible-library-section]').forEach(button=>button.addEventListener('click',()=>setScreen('library',{librarySection:button.dataset.bibleLibrarySection})));
 document.querySelectorAll('[data-bible-book-card]').forEach(button=>button.addEventListener('click',()=>setScreen('chapters',{selectedBook:Number(button.dataset.bibleBookCard)})));
 document.querySelectorAll('[data-bible-chapter-card]').forEach(button=>button.addEventListener('click',()=>openChapter(bookNumber,Number(button.dataset.bibleChapterCard))));
 document.querySelectorAll('[data-bible-document]').forEach(button=>button.addEventListener('click',()=>setScreen('document',{documentId:Number(button.dataset.bibleDocument),documentTitle:button.dataset.bibleDocumentTitle||'',documentReturn:button.dataset.bibleDocumentReturn||'library',selectedBook:bookNumber})));
 document.querySelectorAll('[data-bible-back]').forEach(button=>button.addEventListener('click',()=>{const target=button.dataset.bibleBack;if(target==='chapters')setScreen('chapters',{selectedBook:bookNumber});else setScreen('library',{librarySection:ui.librarySection||'books'})}));
 document.querySelector('[data-bible-prev]')?.addEventListener('click',()=>{if(chapterNumber>1)openChapter(bookNumber,chapterNumber-1)});
 document.querySelector('[data-bible-next]')?.addEventListener('click',()=>{if(selectedBook?.chapters?.some(x=>Number(x.chapter_number)===chapterNumber+1))openChapter(bookNumber,chapterNumber+1)});
 document.querySelector('#bible-primary')?.addEventListener('change',async event=>{const next=bibleUiState();const target=event.target.value;const active=Math.min(Math.max(Number(next.activeTab)||0,0),Math.max((next.tabs?.length||1)-1,0));if(next.tabs?.[active])next.tabs[active].publicationId=target;saveBibleUi(next);await post('/api/bibles/view-state',{language_index:state.languageIndex,primary_publication_id:target,compare_publication_id:next.comparePublicationId||null,book_number:bookNumber,chapter_number:chapterNumber,split_enabled:Boolean(next.split)});renderBible()});
 document.querySelectorAll('[data-bible-notes]').forEach(button=>button.addEventListener('click',()=>{const next=bibleUiState();next.notesOpen=!next.notesOpen;saveBibleUi(next);renderBible()}));
 document.querySelector('#bible-split')?.addEventListener('change',async event=>{const next=bibleUiState();next.split=event.target.checked;saveBibleUi(next);await post('/api/bibles/view-state',{language_index:state.languageIndex,primary_publication_id:primary.id,compare_publication_id:next.comparePublicationId||null,book_number:bookNumber,chapter_number:chapterNumber,split_enabled:next.split});renderBible()});
 document.querySelector('#bible-compare')?.addEventListener('change',event=>{const next=bibleUiState();next.comparePublicationId=event.target.value;saveBibleUi(next);renderBible()});
 const searchInput=document.querySelector('#bible-original-search'),searchResults=document.querySelector('#bible-original-search-results');
 const runSearch=debounce(async()=>{const query=searchInput?.value.trim()||'';if(query.length<2){if(searchResults)searchResults.innerHTML='';return}searchResults.innerHTML='<div class="bible-v2-empty">Suche läuft …</div>';try{const items=await get(`/api/bibles/search?q=${encodeURIComponent(query)}&language=${state.languageIndex}&publication_id=${encodeURIComponent(primary.id)}`);searchResults.innerHTML=items.length?`<div class="bible-original-search-results">${items.slice(0,30).map((item,index)=>`<button data-bible-search-index="${index}"><strong>${esc(item.title||'Fundstelle')}</strong><span>${item.snippet||''}</span></button>`).join('')}</div>`:'<div class="bible-v2-empty">Keine Treffer gefunden.</div>';searchResults.__items=items}catch(error){searchResults.innerHTML=`<div class="bible-v2-empty">${esc(error.message)}</div>`}},250);
 searchInput?.addEventListener('input',runSearch);
 searchResults?.addEventListener('click',event=>{const button=event.target.closest('[data-bible-search-index]');if(!button)return;const item=searchResults.__items?.[Number(button.dataset.bibleSearchIndex)],location=item&&bibleBookFromSearch(item,books);if(location)openChapter(location.book,location.chapter);else if(item?.document_id)setScreen('document',{documentId:Number(item.document_id),documentTitle:item.title||'Suchergebnis',documentReturn:'library'})});
}

async function renderMediaPageFallback(){}
function formatDate(value){if(!value)return'';const date=new Date(value.length===10?`${value}T12:00:00`:value);return Number.isNaN(date.getTime())?value:new Intl.DateTimeFormat('de-DE',{day:'2-digit',month:'2-digit',year:'numeric'}).format(date)}
function cleanLabel(value){const node=document.createElement('textarea');node.innerHTML=String(value||'').replace(/<[^>]*>/g,' ');return node.value.replace(/\s+/g,' ').trim()}

const PUBLICATION_LABELS={nwtsty:'Die Bibel – Neue-Welt-Übersetzung (Studienausgabe)',nwt:'Die Bibel – Neue-Welt-Übersetzung',w:'Der Wachtturm – Studienausgabe',ws:'Der Wachtturm – Studienausgabe',wp:'Der Wachtturm – Öffentlichkeitsausgabe',mwb:'Unser Leben und Dienst als Christ – Arbeitsheft',lfb:'Was wir aus der Bibel lernen können',lff:'Glücklich – für immer',lmd:'Liebt Menschen, macht sie zu Jüngern',th:'Lesen und Lehren',sjj:'Singt voller Freude für Jehova',rr:'Die reine Anbetung Jehovas – endlich wiederhergestellt',jy:'Jesus – der Weg, die Wahrheit, das Leben',bt:'Legt gründlich Zeugnis ab für Gottes Königreich'};
function readablePublicationName(item){if(item?.publication_display)return item.publication_display;const title=String(item?.publication_title||'').trim(),symbol=String(item?.key_symbol||'').trim().toLowerCase(),base=symbol.replace(/\d{2,4}$/,'');if(title&&![symbol,base,'publikation','allgemeine notizen'].includes(title.toLowerCase()))return title;const label=PUBLICATION_LABELS[symbol]||PUBLICATION_LABELS[base];const year=String(item?.publication_year||symbol.match(/(?:19|20)\d{2}/)?.[0]||'').trim();return label?`${label}${year?` ${year}`:''}`:(title||symbol.toUpperCase()||'Nicht zugeordnete Einträge')}

async function startCatalogDownload(catalogId,button){
 const originRoute=state.route;
 try{
  await post('/api/frontend/event',{state:'catalog-download-click',stage:'button',message:String(catalogId)}).catch(()=>{});
  if(button){button.disabled=true;button.textContent='Download wird vorbereitet …'}
  const item=await get(`/api/catalog/${catalogId}/detail`);
  const response=await post('/api/downloads',{catalog_id:Number(catalogId),option_index:0});
  await post('/api/frontend/event',{state:'catalog-download-started',stage:'backend',message:String(response?.job?.id||'')}).catch(()=>{});
  await monitorDownload(response.job.id,item.title||'Publikation',originRoute);
 }catch(error){
  await post('/api/frontend/event',{state:'catalog-download-failed',stage:'error',message:error.message||String(error)}).catch(()=>{});
  if(button){button.disabled=false;button.innerHTML=icon('download',18)+' Offline speichern'}
  const node=document.querySelector('#catalog-option-status');if(node)node.textContent='Download fehlgeschlagen: '+error.message;
  toast('Download fehlgeschlagen: '+error.message,'error');
 }
}
async function monitorDownload(jobId,title='Publikation',returnRoute='library'){
 modalRoot.innerHTML=modal({title:'Offline speichern',body:`<p><strong>${esc(title)}</strong></p><div class="progress"><span id="catalog-download-progress" style="width:0"></span></div><p id="catalog-download-status">Download wird gestartet …</p><p id="catalog-download-detail">0 Bytes</p>`,actions:`<button class="button" data-close-modal>Im Hintergrund weiter</button><button class="button" data-route="downloads" data-close-modal>Downloads öffnen</button>`});
 const progress=document.querySelector('#catalog-download-progress'),status=document.querySelector('#catalog-download-status'),detail=document.querySelector('#catalog-download-detail');
 for(let attempt=0;attempt<3600;attempt++){
  await new Promise(resolve=>setTimeout(resolve,700));
  let jobs;try{jobs=await get('/api/downloads')}catch(error){if(status)status.textContent='Statusabruf fehlgeschlagen: '+error.message;continue}
  const job=jobs.find(item=>item.id===jobId);if(!job)continue;
  const value=Math.min(100,Number(job.progress||0));if(progress)progress.style.width=`${value}%`;
  if(status)status.textContent=job.status_label||job.status;
  if(detail)detail.textContent=`${formatBytes(job.received_size)} von ${formatBytes(job.expected_size)} · ${value.toFixed(1)} %${job.speed_bps?` · ${formatBytes(job.speed_bps)}/s`:''}`;
  if(job.status==='completed'){if(progress)progress.style.width='100%';if(status)status.textContent='Download, Prüfung und Import abgeschlossen.';if(detail)detail.textContent='Die Publikation ist jetzt offline verfügbar.';toast('Publikation wurde vollständig heruntergeladen und importiert.');setTimeout(()=>{closeModal();navigate(returnRoute==='meetings'?'meetings':returnRoute==='bible'?'bible':returnRoute==='home'?'home':'library')},900);return}
  if(job.status==='failed'||job.status==='cancelled'){if(status)status.textContent=job.status==='failed'?'Download fehlgeschlagen':'Download abgebrochen';if(detail)detail.textContent=job.error||'Unbekannter Fehler';toast(job.error||'Download fehlgeschlagen.','error');return}
 }
 if(status)status.textContent='Zeitüberschreitung bei der Statusüberwachung.'
}


async function openPublication(id){state.selectedPublication=id;await navigate('library',{selectedPublication:id})}
async function openDocument(id){state.selectedDocument=Number(id);await navigate('reader',{selectedDocument:Number(id)})}
async function renderDownloads(){
 const jobs=await get('/api/downloads');
 main.innerHTML=`<div class="page">${pageHeader('Downloads','Heruntergeladene Publikationen direkt öffnen',`<button class="button primary" data-route="publications">${icon('plus',18)} Inhalte suchen</button>`)}${jobs.length?`<div class="download-list">${jobs.map(job=>{const progress=Number(job.progress||0);const speed=Number(job.speed_bps||0);return`<article class="download-card"><div class="download-main"><strong>${esc(job.title)}</strong><small>${formatBytes(job.received_size)} von ${formatBytes(job.expected_size)}${speed?` · ${formatBytes(speed)}/s`:''}</small><div class="progress"><span style="width:${Math.min(100,progress)}%"></span></div></div><div class="download-status"><span class="status ${esc(job.status)}">${esc(job.status_label||job.status)}</span>${job.error?`<small>${esc(job.error)}</small>`:''}</div><div class="download-actions">${job.can_open?`<button class="button primary" data-publication-id="${esc(job.installed_id)}">${icon('read',18)} Öffnen</button>`:''}${job.can_retry?`<button class="button" data-retry-download="${job.id}">Erneut</button>`:''}${job.can_cancel?`<button class="button" data-cancel-download="${job.id}">Abbrechen</button>`:''}${job.can_remove?`<button class="button danger" data-remove-download="${job.id}">Entfernen</button>`:''}</div></article>`}).join('')}</div>`:empty('Keine Downloads','Wähle eine Publikation im offiziellen Katalog aus.')}</div>`;
 if(jobs.some(job=>['queued','downloading','verifying','importing'].includes(job.status)))setTimeout(()=>state.route==='downloads'&&renderDownloads(),900)
}
async function renderMeetings(){
 const data=await get(`/api/meetings?offset=${state.meetingOffset||0}&language=${state.languageIndex}`);
 const actions=`<div class="toolbar"><button class="button" data-meeting-offset="${data.offset-1}">${icon('back',18)} Vorherige Woche</button><button class="button" data-meeting-offset="0">Diese Woche</button><button class="button" data-meeting-offset="${data.offset+1}">Nächste Woche ${icon('forward',18)}</button></div>`;
 const primary=data.primary||{},life=primary.life_and_ministry||null;
 const isStrictWatchtower=item=>{if(!item)return false;const symbol=String(item.key_symbol||item.symbol||'').trim().toLowerCase();const typeId=Number(item.publication_type_id||item.type_id||0);const text=[item.title,item.short_title,item.display_label,item.publication_title,item.category,item.material_kind,item.issue_title].filter(Boolean).join(' ').toLowerCase();const explicitSymbol=symbol==='w'||symbol==='ws';const explicitTitle=/\b(wachtturm|watchtower)\b/.test(text);const rejected=/\b(buch|book|brosch(?:ü|u)re|brochure|arbeitsheft|workbook|gesang|songbook)\b/.test(text)&&!explicitTitle;return !rejected&&(explicitSymbol||explicitTitle)&&(typeId===0||typeId===14||explicitSymbol)};
 const watchtowerPool=[primary.watchtower,...(data.downloads||[]),...(data.additional_materials||[])].filter(isStrictWatchtower);
 const watchtower=watchtowerPool.find(item=>item.document_id)||watchtowerPool.find(item=>item.installed_id)||watchtowerPool[0]||null;
 const primaryCard=(item,label,kind)=>{if(!item)return`<article class="meeting-primary-card missing"><div class="meeting-primary-cover">${icon(kind==='watchtower'?'publications':'meetings',34)}</div><div><span class="meeting-primary-label">${esc(label)}</span><strong>Für diese Woche nicht gefunden</strong><small>Katalog aktualisieren oder passende Publikation importieren.</small></div></article>`;const attrs=item.document_id?`data-document-id="${item.document_id}"`:item.installed_id?`data-publication-id="${esc(item.installed_id)}"`:`data-meeting-download="${item.catalog_id}"`;return`<article class="meeting-primary-card" ${attrs} role="button" tabindex="0"><div class="meeting-primary-cover">${item.cover_url?`<img src="${esc(item.cover_url)}" alt="">`:icon(kind==='watchtower'?'publications':'meetings',34)}</div><div class="meeting-primary-copy"><span class="meeting-primary-label">${esc(label)}</span><small>${esc(formatDate(data.week_start))} – ${esc(formatDate(data.week_end))}</small><strong>${esc(cleanLabel(item.article_title||item.title||item.short_title||label))}</strong>${item.article_subtitle?`<p>${esc(cleanLabel(item.article_subtitle))}</p>`:''}</div><button class="icon-button meeting-more" aria-label="Weitere Optionen">•••</button></article>`};
 const selectedWatchtowerIdentity=watchtower?String(watchtower.id||watchtower.catalog_id||watchtower.installed_id||watchtower.natural_key||''):'';
 const additional=(data.additional_materials||[]).filter(item=>{if(!isStrictWatchtower(item))return true;const identity=String(item.id||item.catalog_id||item.installed_id||item.natural_key||'');return !watchtower||identity!==selectedWatchtowerIdentity}).map(item=>{const attrs=item.installed?`data-publication-id="${esc(item.id)}"`:`data-meeting-download="${item.catalog_id}"`;return`<article class="meeting-material-row" ${attrs} role="button" tabindex="0"><div class="meeting-material-cover">${item.cover_url?`<img src="${esc(item.cover_url)}" alt="">`:icon('publications',28)}</div><div><strong>${esc(item.display_label||item.title||item.short_title)}</strong><small>${esc(item.title&&item.title!==item.display_label?item.title:(item.installed?'Lokal verfügbar':'Zum Herunterladen verfügbar'))}</small></div><span class="meeting-material-state">${item.installed?'Öffnen':icon('download',22)}</span><button class="icon-button meeting-more" aria-label="Weitere Optionen">•••</button></article>`}).join('');
 const sections=(data.sections||[]).filter(section=>section.key!=='watchtower').map(section=>`<section class="meeting-section"><header><div><span class="meeting-section-kicker">${esc(cleanLabel(section.title))}</span><h2>${section.items.length} Programmpunkte</h2></div></header><div class="meeting-program">${section.items.map(item=>`<article class="meeting-program-item"><button class="meeting-open" ${item.document_id?`data-document-id="${item.document_id}"`:'data-route="publications"'}><span class="meeting-dot"></span><span><strong>${esc(cleanLabel(item.title))}</strong><small>${esc(cleanLabel(item.subtitle||item.publication||''))}</small>${item.text?`<p>${esc(cleanLabel(item.text))}</p>`:''}</span></button><div class="meeting-item-actions">${item.document_id?`<button class="icon-button" data-meeting-note="${item.document_id}" data-meeting-title="${esc(cleanLabel(item.title))}" title="Notiz">${icon('notes',18)}</button>`:''}${item.note_count?`<span class="note-badge">${item.note_count}</span>`:''}</div></article>`).join('')}</div></section>`).join('');
 main.innerHTML=`<div class="page meetings-page">${pageHeader('Zusammenkünfte',`${formatDate(data.week_start)} – ${formatDate(data.week_end)}`,actions)}<section class="meeting-overview"><div class="meeting-week-heading"><button class="icon-button" data-meeting-offset="${data.offset-1}" aria-label="Vorherige Woche">${icon('back',22)}</button><h2>${formatDate(data.week_start)} – ${formatDate(data.week_end)}${data.offset===0?' · Aktuelle Woche':''}</h2><button class="icon-button" data-meeting-offset="${data.offset+1}" aria-label="Nächste Woche">${icon('forward',22)}</button></div><div class="meeting-primary-list">${primaryCard(life,'Leben und Dienst','life')}${primaryCard(watchtower,'Wachtturm-Studium','watchtower')}</div><div class="meeting-material-divider"></div><h2 class="meeting-material-title">Andere Publikationen für die Zusammenkünfte</h2><div class="meeting-material-list">${additional||emptyInline('Keine Zusatzpublikationen gefunden','Katalog aktualisieren oder Publikationen importieren.')}</div></section>${sections?`<details class="meeting-program-details"><summary>Wochenprogramm anzeigen</summary><div>${sections}</div></details>`:''}</div>`;
}

async function renderNotes(){state.noteQuery=state.noteQuery||'';const items=await get(`/api/notes/organized?q=${encodeURIComponent(state.noteQuery)}`);const groups=Object.entries(items.reduce((acc,n)=>{const key=readablePublicationName(n);(acc[key]||(acc[key]=[])).push(n);return acc},{})).sort((a,b)=>a[0].localeCompare(b[0],'de'));main.innerHTML=`<div class="page">${pageHeader('Notizen',`${items.length} persönliche Notizen`,`<button class="button primary" data-action="new-note">${icon('plus',18)} Neue Notiz</button>`)}<div class="search-field organizer-search">${icon('search',18)}<input id="notes-filter" value="${esc(state.noteQuery)}" placeholder="Notizen oder Publikationen durchsuchen"></div>${groups.length?`<div class="organizer-groups">${groups.map(([name,notes])=>`<section class="organizer-group"><header><div><h2>${esc(name)}</h2><small>${notes.length} Notizen</small></div></header><div class="note-grid">${notes.map(note=>`<article class="note-card organizer-entry"><div ${note.document_id?`data-open-note-document="${note.document_id}" data-note-block="${note.block_identifier??''}" role="button" tabindex="0"`:''}><h3>${esc(note.title||note.document_title||'Notiz')}</h3><p>${esc(note.content||'')}</p><small>${esc(note.document_title||'Allgemeine Notiz')}</small></div><footer>${note.document_id?`<button class="button" data-open-note-document="${note.document_id}" data-note-block="${note.block_identifier??''}">${icon('read',17)} In Publikation öffnen</button>`:'<span class="status-warn">Publikation nicht installiert oder nicht zugeordnet</span>'}${note.source==='local'?`<button class="icon-button" data-delete-note="${note.id}" aria-label="Notiz löschen">${icon('close',17)}</button>`:''}</footer></article>`).join('')}</div></section>`).join('')}</div>`:empty('Keine Notizen','Erstelle im Reader eine Notiz oder importiere ein .jwlibrary-Backup.')}</div>`;let timer;document.querySelector('#notes-filter')?.addEventListener('input',e=>{clearTimeout(timer);timer=setTimeout(()=>{state.noteQuery=e.target.value.trim();renderNotes()},300)})}
async function renderBookmarks(){const items=await get('/api/bookmarks');main.innerHTML=`<div class="page">${pageHeader('Lesezeichen',`${items.length} importierte Lesezeichen`)}${items.length?`<div class="note-grid">${items.map(item=>`<article class="note-card bookmark-card"><button class="bookmark-open" ${item.source==='local'&&item.document_id?`data-open-bookmark="${item.document_id}" data-bookmark-block="${item.block_identifier??''}"`:''}><h3>${esc(item.title||'Lesezeichen')}</h3><p>${esc(item.snippet||item.location_title||'')}</p><footer><span>${esc(item.key_symbol||'Publikation')} · Platz ${item.slot??''}</span></footer></button></article>`).join('')}</div>`:empty('Keine Lesezeichen','Importiere ein .jwlibrary-Backup oder setze neue Lesezeichen im Reader.')}</div>`}
async function renderHighlights(){state.highlightOffset=0;state.highlightQuery=state.highlightQuery||'';state.highlightSort=state.highlightSort||'publication';state.highlightPublication=state.highlightPublication||'';const publications=await get('/api/marks/publications');const data=await get(`/api/marks?paged=1&limit=60&offset=0&q=${encodeURIComponent(state.highlightQuery)}&sort=${encodeURIComponent(state.highlightSort)}&publication=${encodeURIComponent(state.highlightPublication)}`);state.highlightOffset=data.items.length;const publicationOptions=publications.map(item=>`<option value="${esc(item.publication_id||item.key_symbol||'')}" ${(state.highlightPublication===String(item.publication_id||item.key_symbol||''))?'selected':''}>${esc(readablePublicationName(item))} (${item.entry_count})</option>`).join('');main.innerHTML=`<div class="page">${pageHeader('Markierungen',`${data.total} gespeicherte Markierungen`)}<div class="highlight-toolbar"><input class="input" id="highlight-search" value="${esc(state.highlightQuery)}" placeholder="Markierungen durchsuchen …"><select class="select" id="highlight-publication"><option value="">Alle Publikationen</option>${publicationOptions}</select><select class="select" id="highlight-sort"><option value="publication" ${state.highlightSort==='publication'?'selected':''}>Nach Publikation</option><option value="document" ${state.highlightSort==='document'?'selected':''}>Nach Bibeltext / Kapitel</option><option value="recent" ${state.highlightSort==='recent'?'selected':''}>Neueste zuerst</option></select><span>60 Einträge pro Seite</span></div><div class="organizer-groups" id="highlight-grid">${highlightGroups(data.items)}</div><div class="load-more-wrap" id="highlight-more">${data.has_more?`<button class="button" data-load-more-highlights>Weitere 60 laden</button>`:''}</div></div>`;let timer;document.querySelector('#highlight-search')?.addEventListener('input',e=>{clearTimeout(timer);timer=setTimeout(()=>{state.highlightQuery=e.target.value.trim();renderHighlights()},350)});document.querySelector('#highlight-sort')?.addEventListener('change',e=>{state.highlightSort=e.target.value;renderHighlights()});document.querySelector('#highlight-publication')?.addEventListener('change',e=>{state.highlightPublication=e.target.value;renderHighlights()})}
function highlightCard(item){return`<article class="note-card"><div class="mark-swatch mark-${Number(item.color_index||0)%6}"></div><h3>${esc(item.document_title||item.location_title||'Textstelle')}</h3><p>${item.block_identifier!==null&&item.block_identifier!==undefined?`Absatz / Vers ${esc(item.block_identifier)}`:'Textmarkierung'}</p><small>${item.source==='backup'?'Aus JW-Library-Backup':'In LiMaD erstellt'}</small><div class="card-actions">${item.document_id?`<button class="button primary" data-open-mark="${item.document_id}" data-mark-block="${item.block_identifier??''}">${icon('read',17)} In Publikation öffnen</button>`:'<span class="status-warn">Publikation nicht installiert oder nicht zugeordnet</span>'}<button class="button danger" data-delete-mark="${esc(item.id)}">Löschen</button></div></article>`}
function highlightGroups(items){if(!items.length)return empty('Keine Markierungen','Für diese Suche wurden keine Markierungen gefunden.');const groups=items.reduce((acc,item)=>{const key=readablePublicationName(item);(acc[key]||(acc[key]=[])).push(item);return acc},{});return Object.entries(groups).sort((a,b)=>a[0].localeCompare(b[0],'de')).map(([name,entries])=>`<section class="organizer-group"><header><div><h2>${esc(name)}</h2><small>${entries.length} geladene Einträge</small></div></header><div class="note-grid">${entries.map(highlightCard).join('')}</div></section>`).join('')}
async function loadMoreHighlights(){const data=await get(`/api/marks?paged=1&limit=60&offset=${state.highlightOffset||0}&q=${encodeURIComponent(state.highlightQuery||'')}&sort=${encodeURIComponent(state.highlightSort||'publication')}&publication=${encodeURIComponent(state.highlightPublication||'')}`);state.highlightOffset=(state.highlightOffset||0)+data.items.length;const grid=document.querySelector('#highlight-grid');if(grid&&data.items.length){const wrapper=document.createElement('div');wrapper.innerHTML=highlightGroups(data.items);while(wrapper.firstChild)grid.appendChild(wrapper.firstChild)}const more=document.querySelector('#highlight-more');if(more)more.innerHTML=data.has_more?`<button class="button" data-load-more-highlights>Weitere 60 laden</button>`:''}
async function renderTags(){const items=await get('/api/tags');main.innerHTML=`<div class="page">${pageHeader('Tags',`${items.length} Kategorien`)}${items.length?`<div class="note-grid tag-grid">${items.map(item=>`<button class="note-card tag-card" data-tag-name="${esc(item.name)}"><h3>${esc(item.name)}</h3><p>${item.usage||0} zugeordnete Einträge</p><span class="tag-open">Einträge anzeigen ${icon('forward',16)}</span></button>`).join('')}</div>`:empty('Keine Tags','Tags aus einem .jwlibrary-Backup werden hier angezeigt.')}</div>`}
async function openTag(name){const items=await get(`/api/tags/entries?name=${encodeURIComponent(name)}`);main.innerHTML=`<div class="page">${pageHeader(`Tag: ${name}`,`${items.length} zugeordnete Einträge`,`<button class="button" data-route="tags">${icon('back',17)} Alle Tags</button>`)}${items.length?`<div class="note-grid">${items.map(item=>`<article class="note-card organizer-entry" ${item.document_id?`data-open-tag-document="${item.document_id}" data-tag-block="${item.block_identifier??''}" role="button" tabindex="0"`:''}><h3>${esc(item.title||item.document_title||name)}</h3><p>${esc(item.content||'')}</p><footer><span>${esc(item.publication_title||item.document_title||item.key_symbol||'Eintrag')}</span></footer></article>`).join('')}</div>`:empty('Keine Einträge','Für diesen Tag wurden keine auflösbaren Einträge gefunden.')}</div>`}
async function renderBackups(){const items=await get('/api/backups');main.innerHTML=`<div class="page">${pageHeader('Backups','Notizen, Markierungen und Antworten geräteübergreifend sichern',`<button class="button" data-action="import-jwlibrary">${icon('folder',18)} Backup importieren</button><button class="button" data-action="reconcile-backups">${icon('refresh',18)} Quellen neu zuordnen</button><a class="button primary" href="/api/export/jwlibrary">${icon('backup',18)} Exportieren</a>`)}${items.length?`<div class="backup-grid">${items.map(item=>`<article class="backup-card"><div><strong>${esc(item.filename)}</strong><small>${formatDate(item.imported_at)}</small></div><div class="backup-stats"><span>${item.notes_count} Notizen</span><span>${item.marks_count} Markierungen</span><span>${item.tags_count} Tags</span><span>${item.bookmarks_count} Lesezeichen</span><span>${item.input_fields_count||0} Antworten</span></div><div class="resolution-line"><span class="status-ok">${item.resolved_count||0} zugeordnet</span><span class="status-warn">${item.missing_count||0} Quellen fehlen</span></div><div class="card-actions"><button class="button" data-action="backup-details" data-id="${esc(item.id)}">Details</button><a class="button" href="/api/export/jwlibrary?backup_id=${encodeURIComponent(item.id)}">Export</a></div></article>`).join('')}</div>`:empty('Kein Backup importiert','Importiere eine .jwlibrary-Datei. Notizen, Markierungen, Tags, Lesezeichen und Eingabefelder werden danach automatisch zugeordnet.',`<button class="button primary" data-action="import-jwlibrary">Backup importieren</button>`)}</div>`}
async function showBackupDetails(id){const r=await get(`/api/backups/resolution?backup_id=${encodeURIComponent(id)}`);modalRoot.innerHTML=modal({title:'Backup-Zuordnung',body:`<div class="backup-stats large"><span>${r.resolved} zugeordnet</span><span>${r.missing} fehlen</span></div>${r.missing_items.length?`<div class="missing-list">${r.missing_items.slice(0,100).map(x=>`<div><strong>${esc(x.key_symbol||'Unbekannt')}</strong><span>${esc(x.reason||'Quelle fehlt')}</span></div>`).join('')}</div>`:'<p>Alle bekannten Quellen sind zugeordnet.</p>'}`})}
async function renderSettings(){const settings=await get('/api/settings');const active=state.settingsTab||'general';const panels={general:`<div class="setting-row"><div><strong>Inhaltssprache</strong><small>Bestimmt Katalog und neue Inhalte.</small></div><button class="button" data-action="language">${esc(state.languageName)}</button></div><div class="setting-row"><div><strong>Datumsformat</strong><small>Darstellung von Datum und Uhrzeit.</small></div><select class="select setting-control" data-setting-key="date_format"><option value="de" ${settings.date_format!=='iso'?'selected':''}>Deutsch</option><option value="iso" ${settings.date_format==='iso'?'selected':''}>ISO</option></select></div>`,appearance:`<div class="setting-row"><div><strong>Darstellung</strong><small>Helles oder dunkles Farbschema.</small></div><select class="select setting-control" data-setting-key="theme"><option value="light" ${settings.theme!=='dark'?'selected':''}>Hell</option><option value="dark" ${settings.theme==='dark'?'selected':''}>Dunkel</option></select></div><div class="setting-row"><div><strong>Schriftgröße</strong><small>Größe der Bedienoberfläche.</small></div><select class="select setting-control" data-setting-key="font_size"><option value="90" ${settings.font_size==='90'?'selected':''}>90 %</option><option value="100" ${!settings.font_size||settings.font_size==='100'?'selected':''}>100 %</option><option value="110" ${settings.font_size==='110'?'selected':''}>110 %</option><option value="125" ${settings.font_size==='125'?'selected':''}>125 %</option></select></div>`,catalog:`<div class="setting-row"><div><strong>Katalog automatisch aktualisieren</strong><small>Beim Start aktuelle Inhalte laden.</small></div><select class="select setting-control" data-setting-key="catalog_autosync"><option value="1" ${settings.catalog_autosync!=='0'?'selected':''}>Aktiv</option><option value="0" ${settings.catalog_autosync==='0'?'selected':''}>Aus</option></select></div><div class="setting-row"><div><strong>Downloadordner</strong><small>Lokale Medien und Publikationen.</small></div><button class="button" data-route="downloads">Downloads öffnen</button></div><div class="setting-row"><div><strong>Offizieller Katalog</strong><small>${state.status?.counts?.catalog||0} Einträge lokal.</small></div><button class="button" data-action="sync">Jetzt aktualisieren</button></div>`,backup:`<div class="setting-row"><div><strong>JW-Library-Backup</strong><small>Notizen, Markierungen, Antworten, Tags und Lesezeichen austauschen.</small></div><button class="button" data-route="backups">Backup-Verwaltung</button></div><div class="setting-row"><div><strong>Backup importieren</strong><small>.jwlibrary-Datei auswählen.</small></div><button class="button" data-action="import-jwlibrary">Importieren</button></div><div class="setting-row"><div><strong>Backup exportieren</strong><small>Eindeutiges JW-Library-Backup mit eigener Zeitkennung erzeugen.</small></div><a class="button primary" href="/api/export/jwlibrary">Exportieren</a></div>`};main.innerHTML=`<div class="page">${pageHeader('Einstellungen','LiMaD Study konfigurieren')}<div class="settings-grid"><nav class="settings-nav"><button data-settings-tab="general" class="${active==='general'?'active':''}">Allgemein und Datum</button><button data-settings-tab="appearance" class="${active==='appearance'?'active':''}">Darstellung</button><button data-settings-tab="catalog" class="${active==='catalog'?'active':''}">Katalog und Downloads</button><button data-settings-tab="backup" class="${active==='backup'?'active':''}">Daten und Backup</button></nav><section class="settings-panel">${panels[active]||panels.general}</section></div></div>`}
function renderHelp(){const version=state.status?.version||'Version nicht verfügbar';main.innerHTML=`<div class="page">${pageHeader('Hilfe',`LiMaD Study ${version}`)}<div class="panel" style="max-width:820px"><h2>Lokale Bibliothek und Studienumgebung</h2><p>LiMaD Study verarbeitet JWPUB-Publikationen, JWL-Library-Backups, persönliche Notizen, Markierungen, Tags und Lesezeichen lokal. Installierte Publikationen werden nach Kategorie und Jahrgang geordnet und mit einem buchähnlichen Inhaltsverzeichnis geöffnet.</p><h3>Dateien importieren</h3><p>Verwende „Publikationen“ für .jwpub-Dateien und „Backups“ für .jwlibrary- oder .jwlplaylist-Dateien.</p><h3>Offline-Nutzung</h3><p>Importierte Inhalte, Covers und persönliche Daten stehen ohne Internetverbindung zur Verfügung.</p></div></div>`}
function formatDate(value){if(!value)return'';const date=new Date(value.length===10?`${value}T12:00:00`:value);return Number.isNaN(date.getTime())?value:new Intl.DateTimeFormat('de-DE',{day:'2-digit',month:'2-digit',year:'numeric'}).format(date)}
function cleanLabel(value){const node=document.createElement('textarea');node.innerHTML=String(value||'').replace(/<[^>]*>/g,' ');return node.value.replace(/\s+/g,' ').trim()}

async function openPublication(id){state.selectedPublication=id;await navigate('library',{selectedPublication:id})}
async function openDocument(id){state.selectedDocument=Number(id);await navigate('reader',{selectedDocument:Number(id)})}
async function openCatalog(id){
 let item;
 try{item=await get(`/api/catalog/${id}/detail`)}catch(error){toast(error.message,'error');return}
 const cover=item.cover_url?`<img src="${esc(item.cover_url)}" class="catalog-detail-cover" alt="Originalcover" onerror="this.closest('.catalog-cover-wrap').classList.add('cover-error');this.remove()">`:`<span class="cover-placeholder large">${icon('publications',52)}</span>`;
 const status=item.offline_available?'<span class="status-ok">Offline verfügbar</span>':'<span class="status-info">Online-Katalog</span>';
 const body=`<div class="catalog-dialog"><div class="catalog-detail-grid"><div class="catalog-cover-wrap">${cover}<span class="cover-fallback">Originalcover nicht verfügbar</span></div><div><div class="catalog-status-row">${status}</div><h3>${esc(item.title||'Publikation')}</h3><p>${esc(item.short_title||'')}</p><dl class="catalog-meta"><div><dt>Sprache</dt><dd>${esc(item.language_vernacular||item.language_name||state.languageName)}</dd></div><div><dt>Ausgabe</dt><dd>${esc(item.year||'—')}${item.issue_tag?` · ${esc(item.issue_tag)}`:''}</dd></div><div><dt>Größe</dt><dd>${formatBytes(item.size)}</dd></div><div><dt>Publikation</dt><dd>${esc(item.key_symbol||item.symbol||'—')}</dd></div></dl><div class="preview-note"><strong>Ansicht</strong><p>${esc(item.preview_message)}</p></div><p class="download-option-note" id="catalog-option-status">${item.offline_available?'Lokal importiert und lesebereit.':'Offizielle JWPUB-Downloadoption wird geprüft …'}</p></div></div></div>`;
 const actions=item.offline_available?`<button class="button" data-close-modal>Schließen</button><button class="button primary" data-publication-id="${esc(item.installed_id)}">${icon('read',18)} Öffnen</button>`:`<button class="button" data-close-modal>Schließen</button><button class="button primary" id="catalog-offline-button" disabled>${icon('download',18)} Offline speichern</button>`;
 modalRoot.innerHTML=modal({title:'Publikationsdetails',body,actions,wide:true});
 if(!item.offline_available){
  const statusNode=document.querySelector('#catalog-option-status'),button=document.querySelector('#catalog-offline-button');
  try{const options=await get(`/api/catalog/${id}/options`);if(!document.body.contains(button))return;if(options.length){statusNode.textContent=`${options.length} offizielle JWPUB-Downloadoption${options.length===1?'':'en'} verfügbar.`;button.disabled=false;button.dataset.downloadCatalog=id;button.onclick=event=>{event.preventDefault();event.stopPropagation();startCatalogDownload(id,button)}}else{statusNode.textContent='Keine offizielle JWPUB-Downloadoption gefunden. Eine lokale JWPUB-Datei kann weiterhin importiert werden.';button.disabled=false;button.dataset.action='import-jwpub';button.innerHTML='JWPUB importieren'}}catch(error){if(document.body.contains(statusNode)){statusNode.textContent=`Abruf fehlgeschlagen: ${error.message}`;button.disabled=false;button.dataset.action='import-jwpub';button.innerHTML='JWPUB importieren'}}
 }
}

async function openLanguage(){
 modalRoot.innerHTML=modal({title:'Sprache auswählen',wide:true,body:`<div class="search-field" style="margin-bottom:14px">${icon('search',18)}<input id="language-search" placeholder="Über 1.000 Sprachen durchsuchen"></div><div id="language-list" class="language-list">${skeleton(8)}</div>`});
 await loadLanguages('');document.querySelector('#language-search').oninput=debounce(event=>loadLanguages(event.target.value),250)
}
async function loadLanguages(query){const items=await get(`/api/languages?q=${encodeURIComponent(query)}&limit=2000`);document.querySelector('#language-list').innerHTML=items.map(item=>`<button class="language-item" data-language-id="${item.id}" data-language-name="${esc(item.vernacular_name||item.english_name)}"><strong>${esc(item.vernacular_name||item.english_name)}</strong><small>${esc(item.english_name)} · ${item.publication_count||0} Publikationen${item.is_sign?' · Gebärdensprache':''}</small></button>`).join('')||empty('Keine Sprache gefunden','Suche nach Name, Code oder Sprachsymbol.')}
function openSearch(){modalRoot.innerHTML=modal({title:'Bibliothek durchsuchen',wide:true,body:`<div class="search-field" style="width:100%;margin-bottom:15px">${icon('search',18)}<input id="global-search-input" autofocus placeholder="Suchbegriff eingeben"></div><div id="search-results">${empty('Gemeinsame Suche','Sucht in Bibel, Publikationen, Einsichten, Notizen und Medien.')}</div>`});const input=document.querySelector('#global-search-input');setTimeout(()=>input.focus(),30);const kindLabels={bible:'Bibel',publication:'Publikation',note:'Notiz',video:'Video',audio:'Audio',image:'Bild'};input.oninput=debounce(async event=>{const q=event.target.value.trim();const root=document.querySelector('#search-results');if(q.length<2){root.innerHTML=empty('Gemeinsame Suche','Mindestens zwei Zeichen eingeben.');return}const payload=await get(`/api/search/all?q=${encodeURIComponent(q)}`);const results=payload.results||[];root.innerHTML=results.length?`<div class="document-list">${results.map(item=>`<button class="document-item" ${item.document_id?`data-document-id="${item.document_id}"`:''} ${item.block_identifier?`data-block-identifier="${esc(item.block_identifier)}"`:''}><span class="search-result-kind">${esc(kindLabels[item.kind]||item.kind||'')}</span><strong>${esc(item.title||'')}</strong><small>${esc(item.subtitle||'')}</small><p>${item.snippet?esc(item.snippet).replace(/&lt;mark&gt;/g,'<mark>').replace(/&lt;\/mark&gt;/g,'</mark>'):''}</p></button>`).join('')}</div>`:empty('Keine Treffer',`Für „${q}“ wurden keine Treffer gefunden.`)
},250)}
function openGlobalMenu(){modalRoot.innerHTML=modal({title:'Weitere Aktionen',body:`<div style="display:grid;gap:8px"><button class="category-card" style="height:70px;border:1px solid var(--line)" data-action="import-jwpub">${icon('publications')}<span>JWPUB-Publikation importieren</span></button><button class="category-card" style="height:70px;border:1px solid var(--line)" data-action="import-jwlibrary">${icon('backup')}<span>JWL-Library-Backup importieren</span></button><button class="category-card" style="height:70px;border:1px solid var(--line)" data-action="import-jwlplaylist">${icon('playlists')}<span>JWL-Playlist importieren</span></button><button class="category-card" style="height:70px;border:1px solid var(--line)" data-action="sync">${icon('refresh')}<span>Offiziellen Katalog aktualisieren</span></button></div>`})}
function openNoteDialog(prefill={}){if(!state.selectedDocument&&!prefill.document_id){toast('Öffne zuerst ein Dokument.','error');return}modalRoot.innerHTML=modal({title:'Notiz erstellen',body:`<div class="form-field"><label>Titel</label><input id="note-title" value="${esc(prefill.title||'')}"></div><div class="form-field"><label>Notiz</label><textarea id="note-content">${esc(prefill.content||state.selection?.text||'')}</textarea></div><div class="form-field"><label>Tags</label><input id="note-tags" placeholder="z. B. Familie, Nachforschen"></div>`,actions:`<button class="button" data-close-modal>Abbrechen</button><button class="button primary" id="save-note">Speichern</button>`});const noteContent=document.querySelector('#note-content');setTimeout(()=>{noteContent?.focus();noteContent?.setSelectionRange(noteContent.value.length,noteContent.value.length)},30);document.querySelector('#save-note').onclick=async()=>{await post('/api/notes',{document_id:prefill.document_id||state.selectedDocument,title:document.querySelector('#note-title').value,content:document.querySelector('#note-content').value,block_identifier:prefill.block_identifier??state.selection?.blockIdentifier,start_token:prefill.start_token??state.selection?.startToken,end_token:prefill.end_token??state.selection?.endToken,linked_mark_id:prefill.linked_mark_id??state.selection?.markId,selection_text:prefill.selection_text??state.selection?.text??'',tags:document.querySelector('#note-tags').value.split(',').map(x=>x.trim()).filter(Boolean)});closeModal();toast('Notiz gespeichert.');if(state.route==='reader')renderReader()}}
async function syncCatalog(){toast('Katalogaktualisierung gestartet.');try{const response=await post('/api/catalog/sync',{}),result=response.result;if(result.degraded)toast(`Offline-Katalog bleibt verfügbar. ${result.errors.map(e=>e.component).join(', ')} konnte nicht aktualisiert werden.`,'error');else toast(`${result.catalog.count} Katalogeinträge und ${result.languages.count} Sprachen aktualisiert.`);state.status=await get('/api/status');
 const persistedLanguage=Number(state.status?.settings?.language_index);
 if(Number.isFinite(persistedLanguage)&&persistedLanguage>0)state.languageIndex=persistedLanguage;render()}catch(error){toast(error.message,'error')}}
async function importFile(file,type){if(!file)return;const title=type==='jwpub'?'Publikation importieren':type==='jwlplaylist'?'Playlist importieren':'Backup importieren';modalRoot.innerHTML=modal({title,body:`<p>${esc(file.name)}</p><div class="progress"><span id="upload-progress" style="width:0"></span></div><p id="upload-status">Datei wird übertragen …</p>`});try{const result=await upload(`/api/import/${type}`,file,value=>{document.querySelector('#upload-progress').style.width=`${value}%`;document.querySelector('#upload-status').textContent=`Übertragen: ${value} %`});closeModal();toast(type==='jwpub'?'Publikation wurde importiert.':type==='jwlplaylist'?'Playlist wurde importiert.':'Backup wurde importiert.');await navigate(type==='jwpub'?'library':'backups')}catch(error){closeModal();toast(error.message,'error')}finally{const input=document.querySelector(`#${type}-input`);if(input)input.value=''}}

async function openMeetingNote(documentId,title){
 const notes=await get(`/api/meetings/notes?document_id=${documentId}`),existing=notes[0]||{};
 modalRoot.innerHTML=modal({title:'Notiz zum Programmpunkt',body:`<div class="form-field"><label>Titel</label><input id="meeting-note-title" value="${esc(existing.title||title)}"></div><div class="form-field"><label>Notiz</label><textarea id="meeting-note-content">${esc(existing.content||'')}</textarea></div>`,actions:'<button class="button" data-close-modal>Abbrechen</button><button class="button primary" id="save-meeting-note">Speichern</button>'});
 document.querySelector('#save-meeting-note').onclick=async()=>{await post('/api/meetings/notes',{document_id:documentId,title:document.querySelector('#meeting-note-title').value,content:document.querySelector('#meeting-note-content').value});closeModal();toast('Zusammenkunftsnotiz gespeichert.');renderMeetings()}
}


function formatMediaTime(value){const seconds=Math.max(0,Number(value)||0);const minutes=Math.floor(seconds/60);return `${minutes}:${String(Math.floor(seconds%60)).padStart(2,'0')}`}
let floatingMediaPlayer=null;
let floatingMediaSession=0;
let floatingMediaRecoveryTimer=null;
let floatingMediaPerformanceTimer=null;
function mediaPlayerHost(){
 if(floatingMediaPlayer?.isConnected)return floatingMediaPlayer;
 floatingMediaPlayer=document.createElement('section');
 floatingMediaPlayer.id='limad-floating-player';
 floatingMediaPlayer.className='limad-floating-player hidden';
 floatingMediaPlayer.setAttribute('aria-label','Medienplayer');
 document.body.appendChild(floatingMediaPlayer);
 return floatingMediaPlayer;
}
function playerMinimumSize(host){return host.classList.contains('video')?{width:320,height:270}:{width:300,height:235}}
function playerRectSnapshot(host){const rect=host.getBoundingClientRect();return{left:rect.left,top:rect.top,width:rect.width,height:rect.height}}
function applyPlayerRect(host,rect){if(!rect)return;for(const key of ['left','top','width','height']){const value=Number(rect[key]);if(Number.isFinite(value)&&value>0)host.style[key]=`${Math.round(value)}px`}host.style.right='auto';host.style.bottom='auto'}
function clampFloatingPlayerToViewport(host){if(!host||host.classList.contains('hidden'))return;const margin=12,min=playerMinimumSize(host),rect=host.getBoundingClientRect();const maxWidth=Math.max(min.width,window.innerWidth-margin*2),maxHeight=Math.max(min.height,window.innerHeight-70);let width=Math.min(Math.max(rect.width,min.width),maxWidth),height=Math.min(Math.max(rect.height,min.height),maxHeight);if(host.classList.contains('mini')){width=rect.width;height=rect.height}if(host.classList.contains('maximized')){width=maxWidth;height=Math.max(min.height,window.innerHeight-76)}const left=Math.min(Math.max(margin,rect.left),Math.max(margin,window.innerWidth-width-margin));const top=Math.min(Math.max(58,rect.top),Math.max(58,window.innerHeight-height-margin));host.style.left=`${Math.round(left)}px`;host.style.top=`${Math.round(top)}px`;host.style.right='auto';host.style.bottom='auto';if(!host.classList.contains('mini')){host.style.width=`${Math.round(width)}px`;host.style.height=`${Math.round(height)}px`}}
function persistFloatingPlayerRect(host){if(!host||host.classList.contains('mini')||host.classList.contains('maximized'))return;const rect=playerRectSnapshot(host);storageSet('limad-player-position',JSON.stringify({left:`${Math.round(rect.left)}px`,top:`${Math.round(rect.top)}px`}));storageSet('limad-player-size',JSON.stringify({width:Math.round(rect.width),height:Math.round(rect.height)}))}
function setFloatingPlayerMode(mode){
 const host=mediaPlayerHost(),target=mode==='mini'?'mini':mode==='maximized'?'maximized':'expanded',wasMini=host.classList.contains('mini'),wasMaximized=host.classList.contains('maximized');
 if((target==='mini'||target==='maximized')&&!wasMini&&!wasMaximized)host.__restoreRect=playerRectSnapshot(host);
 host.classList.remove('mini','expanded','maximized');
 if(target==='mini'){
  host.classList.add('mini');host.style.width='';host.style.height='';
 }else if(target==='maximized'){
  host.classList.add('expanded','maximized');host.style.left='12px';host.style.top='64px';host.style.right='auto';host.style.bottom='auto';host.style.width=`${Math.max(320,window.innerWidth-24)}px`;host.style.height=`${Math.max(270,window.innerHeight-76)}px`;
 }else{
  host.classList.add('expanded');
  if((wasMini||wasMaximized)&&host.__restoreRect)applyPlayerRect(host,host.__restoreRect);
 }
 const minimize=host.querySelector('[data-player-minimize]'),maximize=host.querySelector('[data-player-maximize]');
 if(minimize){const restore=target==='mini';minimize.title=restore?'Normalgröße':'Minimieren';minimize.setAttribute('aria-label',minimize.title)}
 if(maximize){const restore=target==='maximized';maximize.title=restore?'Wiederherstellen':'Maximieren';maximize.setAttribute('aria-label',maximize.title);maximize.setAttribute('aria-pressed',restore?'true':'false')}
 storageSet('limad-player-mode',target==='mini'?'mini':'expanded');requestAnimationFrame(()=>clampFloatingPlayerToViewport(host));
}
function closeFloatingPlayer(){
 floatingMediaSession+=1;
 clearTimeout(floatingMediaRecoveryTimer);
 clearInterval(floatingMediaPerformanceTimer);
 floatingMediaPerformanceTimer=null;
 const host=mediaPlayerHost(),element=host.querySelector('audio,video');
 try{host.__cleanup?.()}catch{}
 try{element?.pause();element?.removeAttribute('src');element?.load()}catch{}
 host.innerHTML='';host.className='limad-floating-player hidden';host.removeAttribute('style');host.__restoreRect=null;host.__cleanup=null;
}
function enablePlayerDrag(host,handle){
 let active=false,startX=0,startY=0,startLeft=0,startTop=0;
 const move=event=>{if(!active)return;const point=event.touches?.[0]||event;const maxLeft=Math.max(12,window.innerWidth-host.offsetWidth-12);const maxTop=Math.max(58,window.innerHeight-host.offsetHeight-12);host.style.left=`${Math.min(maxLeft,Math.max(12,startLeft+point.clientX-startX))}px`;host.style.top=`${Math.min(maxTop,Math.max(58,startTop+point.clientY-startY))}px`;host.style.right='auto';host.style.bottom='auto';if(event.cancelable)event.preventDefault()};
 const stop=()=>{if(!active)return;active=false;document.removeEventListener('mousemove',move);document.removeEventListener('mouseup',stop);document.removeEventListener('touchmove',move);document.removeEventListener('touchend',stop);clampFloatingPlayerToViewport(host);persistFloatingPlayerRect(host)};
 const begin=event=>{if(event.target.closest('button,input,select,label,[data-player-resize]')||host.classList.contains('maximized'))return;active=true;const point=event.touches?.[0]||event;const rect=host.getBoundingClientRect();startX=point.clientX;startY=point.clientY;startLeft=rect.left;startTop=rect.top;document.addEventListener('mousemove',move);document.addEventListener('mouseup',stop);document.addEventListener('touchmove',move,{passive:false});document.addEventListener('touchend',stop);event.preventDefault()};
 handle.addEventListener('mousedown',begin);handle.addEventListener('touchstart',begin,{passive:false});
}
function enablePlayerResize(host,handle){
 let active=false,startX=0,startY=0,startWidth=0,startHeight=0,startLeft=0,startTop=0,pointerId=null;
 const move=event=>{if(!active)return;const point=event.touches?.[0]||event,min=playerMinimumSize(host),maxWidth=Math.max(min.width,window.innerWidth-startLeft-12),maxHeight=Math.max(min.height,window.innerHeight-startTop-12);const width=Math.min(maxWidth,Math.max(min.width,startWidth+point.clientX-startX)),height=Math.min(maxHeight,Math.max(min.height,startHeight+point.clientY-startY));host.style.width=`${Math.round(width)}px`;host.style.height=`${Math.round(height)}px`;if(event.cancelable)event.preventDefault()};
 const stop=()=>{if(!active)return;active=false;document.removeEventListener('mousemove',move);document.removeEventListener('mouseup',stop);document.removeEventListener('touchmove',move);document.removeEventListener('touchend',stop);try{if(pointerId!==null)handle.releasePointerCapture?.(pointerId)}catch{}pointerId=null;clampFloatingPlayerToViewport(host);persistFloatingPlayerRect(host)};
 const begin=event=>{if(host.classList.contains('mini'))setFloatingPlayerMode('expanded');if(host.classList.contains('maximized'))setFloatingPlayerMode('expanded');active=true;const point=event.touches?.[0]||event,rect=host.getBoundingClientRect();startX=point.clientX;startY=point.clientY;startWidth=rect.width;startHeight=rect.height;startLeft=rect.left;startTop=rect.top;pointerId=event.pointerId??null;try{if(pointerId!==null)handle.setPointerCapture?.(pointerId)}catch{}document.addEventListener('mousemove',move);document.addEventListener('mouseup',stop);document.addEventListener('touchmove',move,{passive:false});document.addEventListener('touchend',stop);event.preventDefault();event.stopPropagation()};
 handle.addEventListener('mousedown',begin);handle.addEventListener('touchstart',begin,{passive:false});
}
function restorePlayerPosition(host){try{const pos=JSON.parse(storageGet('limad-player-position','{}')),size=JSON.parse(storageGet('limad-player-size','{}'));if(pos.left&&pos.top){host.style.left=pos.left;host.style.top=pos.top;host.style.right='auto';host.style.bottom='auto'}if(Number(size.width)>0)host.style.width=`${Number(size.width)}px`;if(Number(size.height)>0)host.style.height=`${Number(size.height)}px`}catch{}requestAnimationFrame(()=>clampFloatingPlayerToViewport(host))}
function enablePlayerControlsAutoHide(host){
 let timer=null;
 const show=()=>{host.classList.remove('controls-hidden');clearTimeout(timer);timer=setTimeout(()=>host.classList.add('controls-hidden'),3000)};
 const keepVisible=()=>{host.classList.remove('controls-hidden');clearTimeout(timer)};
 ['mousemove','pointermove','mouseenter','touchstart'].forEach(name=>host.addEventListener(name,show,{passive:true}));
 host.addEventListener('mouseleave',()=>{clearTimeout(timer);timer=setTimeout(()=>host.classList.add('controls-hidden'),500)});
 host.addEventListener('focusin',keepVisible);
 host.addEventListener('focusout',show);
 host.querySelector('.floating-player-overlay')?.addEventListener('click',show);
 show();
}
function normalizeMediaSources(node,initialUrl,type){
 let parsed=[];try{parsed=JSON.parse(node.dataset.mediaSources||'[]')}catch{}
 const fallback={url:initialUrl,quality:'Standard',mime_type:type==='video'?'video/mp4':'audio/mpeg'};
 const values=[...(Array.isArray(parsed)?parsed:[]),fallback],seen=new Set(),result=[];
 for(const value of values){const url=String(value?.url||'').trim();if(!url||seen.has(url))continue;seen.add(url);result.push({...value,url,quality:String(value?.quality||'Standard'),mime_type:String(value?.mime_type||fallback.mime_type)})}
 return result;
}
function preferredMediaSourceIndex(sources,type,preferred){
 if(preferred!=='auto'){const exact=sources.findIndex(source=>source.quality===preferred);if(exact>=0)return exact}
 if(type==='audio'){
  let best=0,bestScore=-1;
  sources.forEach((source,index)=>{const mime=String(source.mime_type||'').toLowerCase(),url=String(source.url||'');let score=url.startsWith('/api/media/proxy?')?20:0;if(mime==='audio/mpeg'||mime.includes('mp3'))score+=12;else if(mime.includes('mp4')||mime.includes('m4a'))score+=8;else if(mime.includes('aac'))score+=5;if(score>bestScore){bestScore=score;best=index}});
  return best;
 }
 const heights=sources.map((source,index)=>({index,height:Number(source.height)||0,proxy:String(source.url||'').startsWith('/api/media/proxy?')})).filter(item=>item.height>0);
 if(heights.length){const suitable=heights.filter(item=>item.height<=720).sort((a,b)=>b.height-a.height||Number(b.proxy)-Number(a.proxy));if(suitable.length)return suitable[0].index;heights.sort((a,b)=>a.height-b.height||Number(b.proxy)-Number(a.proxy));return heights[0].index}
 const proxy=sources.findIndex(source=>String(source.url||'').startsWith('/api/media/proxy?'));return proxy>=0?proxy:Math.max(0,sources.length-1);
}
function mediaPlaybackUrl(url,attempt){
 if(!attempt)return url;
 try{const parsed=new URL(url,location.href);parsed.searchParams.set('_limad_retry',String(Date.now()));return parsed.origin===location.origin?`${parsed.pathname}${parsed.search}${parsed.hash}`:parsed.href}catch{return url}
}
function mediaSourceHeight(source){
 const direct=Number(source?.height)||0;if(direct>0)return direct;
 const match=String(source?.quality||'').match(/(\d{3,4})p/i);return match?Number(match[1]):0;
}
function videoFrameStats(element){
 try{
  if(typeof element.getVideoPlaybackQuality==='function'){const value=element.getVideoPlaybackQuality();const total=Number(value.totalVideoFrames)||0,dropped=Number(value.droppedVideoFrames)||0;if(total>=0&&dropped>=0)return{total,dropped}}
  const total=Number(element.webkitDecodedFrameCount),dropped=Number(element.webkitDroppedFrameCount);if(Number.isFinite(total)&&Number.isFinite(dropped))return{total,dropped};
 }catch{}
 return null;
}
function lowerVideoSourceIndex(sources,currentIndex){
 const currentHeight=mediaSourceHeight(sources[currentIndex]);
 const candidates=sources.map((source,index)=>({index,height:mediaSourceHeight(source)})).filter(item=>item.index!==currentIndex&&item.height>0&&(currentHeight<=0||item.height<currentHeight));
 if(!candidates.length)return-1;
 candidates.sort((a,b)=>currentHeight>0?b.height-a.height:a.height-b.height);
 return candidates[0].index;
}

let nativePlayerDisabled=false;
let nativePlayerFallbackNode=null;
function nativePlayerShellAvailable(){
 try{return !nativePlayerDisabled&&new URLSearchParams(location.search).get('native_shell')==='1'}catch{return false}
}
function nativeMediaItemFromNode(node){
 const initialUrl=node?.dataset?.mediaUrl||'';if(!initialUrl)return null;
 const type=node.dataset.mediaType==='video'?'video':'audio';
 return{type,title:node.dataset.mediaTitle||(type==='video'?'Video':'Audio'),key:node.dataset.mediaKey||initialUrl,natural_key:node.dataset.mediaNaturalKey||'',image:node.dataset.mediaImage||'',sources:normalizeMediaSources(node,initialUrl,type)};
}
async function openNativeMediaPlayer(node){
 const current=nativeMediaItemFromNode(node);if(!current)return false;
 const nodes=[...document.querySelectorAll('main [data-media-url]')].slice(0,250),playlist=nodes.map(nativeMediaItemFromNode).filter(Boolean);
 let index=playlist.findIndex(item=>item.key===current.key);if(index<0){playlist.push(current);index=playlist.length-1}
 const response=await post('/api/native-player/session',{playlist,index,autoplay:storageGet('limad-media-autoplay','1')!=='0',preferred_quality:storageGet(`limad-${current.type}-quality`,'auto')});
 if(!response?.session_id)throw new Error('Native Player-Sitzung konnte nicht erstellt werden.');
 nativePlayerFallbackNode=node;
 location.href=`limad-study://native-player/open?session=${encodeURIComponent(response.session_id)}`;
 setTimeout(()=>{if(nativePlayerFallbackNode===node)nativePlayerFallbackNode=null},15000);
 return true;
}
window.addEventListener('limad-native-player-failed',event=>{
 const node=nativePlayerFallbackNode;nativePlayerFallbackNode=null;nativePlayerDisabled=true;
 toast(`Nativer Player nicht verfügbar: ${event.detail||'unbekannter Fehler'}. Web-Player wird verwendet.`,'error');
 if(node)openMediaPlayerWeb(node);
});
async function openMediaPlayer(node){
 if(nativePlayerShellAvailable()){
  try{if(await openNativeMediaPlayer(node))return}catch(error){nativePlayerDisabled=true;toast(`Nativer Player nicht verfügbar: ${error.message}. Web-Player wird verwendet.`,'error')}
 }
 return openMediaPlayerWeb(node);
}
async function openMediaPlayerWeb(node){
 const initialUrl=node.dataset.mediaUrl||'';if(!initialUrl)return;
 const session=++floatingMediaSession;clearTimeout(floatingMediaRecoveryTimer);clearInterval(floatingMediaPerformanceTimer);floatingMediaPerformanceTimer=null;
 const type=node.dataset.mediaType==='video'?'video':'audio';
 const title=node.dataset.mediaTitle||(type==='video'?'Video':'Audio');
 const mediaKey=node.dataset.mediaKey||initialUrl;const image=node.dataset.mediaImage||'';const naturalKey=node.dataset.mediaNaturalKey||'';
 const sources=normalizeMediaSources(node,initialUrl,type);if(!sources.length)return;
 const preferred=storageGet(`limad-${type}-quality`,'auto');let sourceIndex=preferredMediaSourceIndex(sources,type,preferred),selected=sources[sourceIndex];
 const autoplayEnabled=storageGet('limad-media-autoplay','1')!=='0';
 const performanceEnabled=type==='video'&&storageGet('limad-video-performance','1')!=='0';
 const qualityOptions=sources.map((source,index)=>`<option value="${index}" ${preferred!=='auto'&&index===sourceIndex?'selected':''}>${esc(source.quality||'Standard')}</option>`).join('');
 const host=mediaPlayerHost();try{host.__cleanup?.()}catch{}host.__cleanup=null;host.className=`limad-floating-player ${type} expanded`;host.innerHTML=`<header class="floating-player-header"><div class="floating-player-window-controls" dir="ltr"><button class="floating-player-control close" data-player-close title="Schließen" aria-label="Schließen"></button><button class="floating-player-control maximize" data-player-maximize title="Maximieren" aria-label="Maximieren" aria-pressed="false"></button><button class="floating-player-control minimize" data-player-minimize title="Minimieren" aria-label="Minimieren"></button></div><strong title="${esc(title)}">${esc(title)}</strong><button class="floating-player-menu" data-player-settings title="Player-Einstellungen" aria-label="Player-Einstellungen" aria-expanded="false">•••</button></header><div class="floating-player-media">${image&&type==='audio'?`<img class="floating-player-cover" src="${esc(image)}" alt="">`:''}<${type} id="limad-media-element" src="${esc(selected.url)}" preload="auto" ${type==='video'?'playsinline webkit-playsinline':''}></${type}><div class="floating-player-overlay"><div class="floating-player-playback"><button class="floating-player-skip" data-player-previous title="Vorheriger Titel" aria-label="Vorheriger Titel">◀|</button><button class="floating-player-play" data-player-toggle title="Wiedergabe/Pause" aria-label="Wiedergabe/Pause">▶</button><button class="floating-player-skip" data-player-next title="Nächster Titel" aria-label="Nächster Titel">|▶</button></div><div class="floating-player-timeline"><span data-player-current>0:00</span><input data-player-progress type="range" min="0" max="1000" value="0" aria-label="Wiedergabeposition"><span data-player-duration>0:00</span><button class="floating-player-open" data-player-open title="${type==='video'?'Vollbild':'Normalgröße'}" aria-label="${type==='video'?'Vollbild':'Normalgröße'}">↗</button></div></div></div><div class="floating-player-details"><div class="media-player-actions"><button class="button" id="media-download-button">${icon('download',20)} Herunterladen</button><button class="button" id="media-playlist-button">${icon('playlists',20)} Zu Playlist</button></div><div class="floating-player-settings-panel" data-player-settings-panel hidden>${type==='video'&&sources.length>1?`<label class="media-quality">Qualität <select id="media-quality-select"><option value="auto" ${preferred==='auto'?'selected':''}>Automatisch</option>${qualityOptions}</select></label>`:''}<label class="media-autoplay-toggle"><input type="checkbox" id="media-autoplay-toggle" ${autoplayEnabled?'checked':''}> Automatisch weiter</label>${type==='video'?`<label class="media-performance-toggle"><input type="checkbox" id="media-performance-toggle" ${performanceEnabled?'checked':''}> Vollbild-Leistungsmodus</label><small class="media-performance-note">WebKit verwendet seine automatische Beschleunigungswahl. Bei erkannten Bildaussetzern reduziert „Automatisch“ nur so weit wie nötig.</small>`:''}<div class="media-player-status" id="media-player-status">Wird geladen …</div></div></div><button class="floating-player-resize-handle" data-player-resize title="Größe ändern" aria-label="Größe des Players ändern"></button>`;
 restorePlayerPosition(host);enablePlayerDrag(host,host.querySelector('.floating-player-header'));enablePlayerResize(host,host.querySelector('[data-player-resize]'));setFloatingPlayerMode(storageGet('limad-player-mode','expanded'));enablePlayerControlsAutoHide(host);
 const element=host.querySelector('#limad-media-element'),status=host.querySelector('#media-player-status');if(!element)return;
 const pageMedia=[...document.querySelectorAll('main [data-media-url]')];
 const currentIndex=pageMedia.findIndex(item=>(item.dataset.mediaKey||item.dataset.mediaUrl)===(mediaKey||initialUrl));
 const toggleButton=host.querySelector('[data-player-toggle]'),progress=host.querySelector('[data-player-progress]'),currentTimeNode=host.querySelector('[data-player-current]'),durationNode=host.querySelector('[data-player-duration]');
 let userPaused=false,switching=false,recoveryCount=0,lastStablePosition=0,fullscreenFrameStats=null,fullscreenDropStrikes=0,fullscreenAutoDowngrades=0;
 const active=()=>session===floatingMediaSession&&element.isConnected;
 const syncPlayerUi=()=>{const duration=Number.isFinite(element.duration)?element.duration:0;const current=Number.isFinite(element.currentTime)?element.currentTime:0;if(currentTimeNode)currentTimeNode.textContent=formatMediaTime(current);if(durationNode)durationNode.textContent=formatMediaTime(duration);if(progress)progress.value=duration?String(Math.round(current/duration*1000)):'0';if(toggleButton)toggleButton.textContent=element.paused?'▶':'Ⅱ'};
 const playElement=async(manual=false)=>{if(!active())return false;if(manual)userPaused=false;try{await element.play();if(active())status.textContent=Number.isFinite(element.duration)&&element.duration>0?`Dauer ${formatMediaTime(element.duration)}`:'Wiedergabe läuft.';return true}catch(error){if(active())status.textContent=manual?'Wiedergabe konnte nicht gestartet werden. Noch einmal klicken.':'Zum Starten auf Wiedergabe klicken.';return false}};
 const applySource=(index,position,resume,reason)=>{if(!active())return;clearTimeout(floatingMediaRecoveryTimer);sourceIndex=Math.max(0,Math.min(index,sources.length-1));selected=sources[sourceIndex];switching=true;status.textContent=reason||'Medienquelle wird geladen …';try{element.pause();element.src=mediaPlaybackUrl(selected.url,recoveryCount);element.load()}catch{}let restored=false;const restore=()=>{if(restored||!active())return;restored=true;try{if(Number.isFinite(position)&&position>0&&Number.isFinite(element.duration)&&element.duration>0)element.currentTime=Math.min(position,Math.max(0,element.duration-.25))}catch{}switching=false;if(resume&&!userPaused)playElement(false)};element.addEventListener('loadedmetadata',restore,{once:true});element.addEventListener('canplay',restore,{once:true});setTimeout(restore,2500)};
 const recover=reason=>{if(!active()||userPaused||switching)return;recoveryCount+=1;if(recoveryCount>Math.max(4,sources.length+2)){status.textContent='Wiedergabe unterbrochen. Bitte erneut auf Wiedergabe klicken.';return}const position=Number.isFinite(element.currentTime)?element.currentTime:0;const nextIndex=recoveryCount===1?sourceIndex:(sources.length>1?(sourceIndex+1)%sources.length:sourceIndex);applySource(nextIndex,position,true,recoveryCount===1?`${reason} – Verbindung wird neu aufgebaut …`:`${reason} – alternative Medienquelle wird geladen …`)};
 const scheduleRecovery=reason=>{if(userPaused||switching)return;clearTimeout(floatingMediaRecoveryTimer);const snapshot=Number.isFinite(element.currentTime)?element.currentTime:0;status.textContent='Wiedergabe wird gepuffert …';floatingMediaRecoveryTimer=setTimeout(()=>{if(!active()||userPaused||switching)return;const current=Number.isFinite(element.currentTime)?element.currentTime:0;if(current<=snapshot+.2)recover(reason)},7000)};
 const stopPerformanceMonitor=()=>{clearInterval(floatingMediaPerformanceTimer);floatingMediaPerformanceTimer=null;fullscreenFrameStats=null;fullscreenDropStrikes=0};
 const fullscreenActive=()=>host.classList.contains('maximized')||document.fullscreenElement===element||document.webkitFullscreenElement===element;
 const startPerformanceMonitor=()=>{
  stopPerformanceMonitor();
  if(type!=='video'||storageGet('limad-video-performance','1')==='0'||!fullscreenActive())return;
  fullscreenFrameStats=videoFrameStats(element);
  floatingMediaPerformanceTimer=setInterval(()=>{
   if(!active()||!fullscreenActive()||storageGet('limad-video-performance','1')==='0'){stopPerformanceMonitor();return}
   const next=videoFrameStats(element);if(!next||!fullscreenFrameStats){fullscreenFrameStats=next;return}
   const total=next.total-fullscreenFrameStats.total,dropped=next.dropped-fullscreenFrameStats.dropped;fullscreenFrameStats=next;
   if(total<20)return;
   const ratio=dropped/Math.max(1,total);fullscreenDropStrikes=ratio>=.08?fullscreenDropStrikes+1:Math.max(0,fullscreenDropStrikes-1);
   if(fullscreenDropStrikes<2||fullscreenAutoDowngrades>=2||storageGet(`limad-${type}-quality`,'auto')!=='auto')return;
   const lowerIndex=lowerVideoSourceIndex(sources,sourceIndex);fullscreenDropStrikes=0;if(lowerIndex<0){status.textContent='Vollbild-Leistungsmodus aktiv – keine leichtere Quelle verfügbar.';return}
   fullscreenAutoDowngrades+=1;const position=element.currentTime||0,playing=!element.paused;applySource(lowerIndex,position,playing,`Vollbild wird optimiert: ${sources[lowerIndex]?.quality||'leichtere Qualität'} …`);
  },2000);
 };
 const fullscreenChanged=()=>{const enabled=fullscreenActive();host.classList.toggle('fullscreen-active',enabled);if(enabled){fullscreenAutoDowngrades=0;requestAnimationFrame(startPerformanceMonitor)}else{stopPerformanceMonitor();if(active())status.textContent=Number.isFinite(element.duration)&&element.duration>0?`Dauer ${formatMediaTime(element.duration)}`:'Wiedergabe läuft.'}};
 toggleButton.onclick=async()=>{if(element.paused){userPaused=false;await playElement(true)}else{userPaused=true;clearTimeout(floatingMediaRecoveryTimer);element.pause()}syncPlayerUi()};
 progress.oninput=()=>{if(Number.isFinite(element.duration)&&element.duration>0)element.currentTime=Number(progress.value)/1000*element.duration};
 host.querySelector('[data-player-previous]').onclick=()=>{if(currentIndex>0)openMediaPlayer(pageMedia[currentIndex-1]);else element.currentTime=0};
 host.querySelector('[data-player-next]').onclick=()=>{if(currentIndex>=0&&currentIndex<pageMedia.length-1)openMediaPlayer(pageMedia[currentIndex+1]);else element.currentTime=element.duration||element.currentTime};
 host.querySelector('[data-player-open]').onclick=async()=>{if(type==='video'){const target=element;if(target.requestFullscreen){try{await target.requestFullscreen()}catch{}}else if(target.webkitRequestFullscreen){target.webkitRequestFullscreen()}}else setFloatingPlayerMode('expanded')};
 if(type==='video')element.addEventListener('dblclick',async()=>{if(element.requestFullscreen){try{await element.requestFullscreen()}catch{}}else if(element.webkitRequestFullscreen){element.webkitRequestFullscreen()}});
 if(type==='video'){document.addEventListener('fullscreenchange',fullscreenChanged);document.addEventListener('webkitfullscreenchange',fullscreenChanged);host.__cleanup=()=>{stopPerformanceMonitor();document.removeEventListener('fullscreenchange',fullscreenChanged);document.removeEventListener('webkitfullscreenchange',fullscreenChanged)}}
 element.addEventListener('loadedmetadata',()=>{if(active())status.textContent=`Dauer ${formatMediaTime(element.duration)}`});
 element.addEventListener('canplay',()=>{clearTimeout(floatingMediaRecoveryTimer);if(active()&&!userPaused&&!switching&&element.paused)playElement(false)});
 element.addEventListener('playing',()=>{clearTimeout(floatingMediaRecoveryTimer);if(active())status.textContent=Number.isFinite(element.duration)&&element.duration>0?`Dauer ${formatMediaTime(element.duration)}`:'Wiedergabe läuft.';syncPlayerUi()});
 element.addEventListener('waiting',()=>scheduleRecovery('Datenstrom unterbrochen'));
 element.addEventListener('stalled',()=>scheduleRecovery('Datenstrom reagiert nicht'));
 element.addEventListener('error',()=>{if(!switching)recover('Medienquelle fehlgeschlagen')});
 element.addEventListener('abort',()=>{if(!switching&&!userPaused)scheduleRecovery('Medienstream abgebrochen')});
 element.addEventListener('timeupdate',()=>{syncPlayerUi();const current=Number.isFinite(element.currentTime)?element.currentTime:0;if(current-lastStablePosition>=30){lastStablePosition=current;recoveryCount=0}});
 element.addEventListener('durationchange',syncPlayerUi);element.addEventListener('play',syncPlayerUi);element.addEventListener('pause',syncPlayerUi);syncPlayerUi();
 host.querySelector('[data-player-minimize]').onclick=()=>setFloatingPlayerMode(host.classList.contains('mini')?'expanded':'mini');
 host.querySelector('[data-player-maximize]').onclick=()=>{setFloatingPlayerMode(host.classList.contains('maximized')?'expanded':'maximized');requestAnimationFrame(fullscreenChanged)};
 host.querySelector('[data-player-close]').onclick=closeFloatingPlayer;
 const settingsButton=host.querySelector('[data-player-settings]'),settingsPanel=host.querySelector('[data-player-settings-panel]');
 if(settingsButton&&settingsPanel)settingsButton.onclick=()=>{const open=settingsPanel.hasAttribute('hidden');settingsPanel.toggleAttribute('hidden',!open);settingsButton.setAttribute('aria-expanded',open?'true':'false');host.classList.toggle('settings-open',open);requestAnimationFrame(()=>clampFloatingPlayerToViewport(host))};
 host.querySelector('#media-autoplay-toggle')?.addEventListener('change',event=>storageSet('limad-media-autoplay',event.target.checked?'1':'0'));
 host.querySelector('#media-performance-toggle')?.addEventListener('change',event=>{storageSet('limad-video-performance',event.target.checked?'1':'0');if(event.target.checked&&fullscreenActive())startPerformanceMonitor();else stopPerformanceMonitor()});
 element.addEventListener('ended',()=>{const duration=Number.isFinite(element.duration)?element.duration:0,current=Number.isFinite(element.currentTime)?element.currentTime:0;if(duration>0&&current<duration-1){recover('Wiedergabe vorzeitig beendet');return}if(storageGet('limad-media-autoplay','1')==='0')return;if(currentIndex<0||currentIndex>=pageMedia.length-1){status.textContent='Wiedergabe beendet.';return}status.textContent='Nächster Titel wird gestartet …';setTimeout(()=>{if(active())openMediaPlayer(pageMedia[currentIndex+1])},350)});
 host.querySelector('#media-quality-select')?.addEventListener('change',event=>{const position=element.currentTime||0,playing=!element.paused;const value=event.target.value;if(value==='auto'){storageSet(`limad-${type}-quality`,'auto');sourceIndex=preferredMediaSourceIndex(sources,type,'auto')}else{sourceIndex=Number(value)||0;storageSet(`limad-${type}-quality`,sources[sourceIndex]?.quality||'auto')}recoveryCount=0;applySource(sourceIndex,position,playing,'Qualität wird gewechselt …')});
 host.querySelector('#media-download-button').onclick=async()=>{const button=host.querySelector('#media-download-button');button.disabled=true;button.textContent='Download läuft …';try{await post('/api/media/download',{url:selected.download_url||selected.url,title,kind:type,quality:selected.quality||'',image,natural_key:naturalKey});button.textContent='Offline gespeichert';toast('Medium wurde heruntergeladen.')}catch(error){button.disabled=false;button.textContent='Herunterladen';toast(error.message,'error')}};
 host.querySelector('#media-playlist-button').onclick=async()=>{const playlists=await get('/api/playlists');if(!playlists.length){const created=await post('/api/playlists',{title:'Meine Medien'});playlists.push(created.playlist)}modalRoot.innerHTML=modal({title:'Zu Playlist hinzufügen',body:`<div class="document-list">${playlists.map(p=>`<button class="document-item" data-pick-media-playlist="${p.id}"><strong>${esc(p.title)}</strong><small>${p.items?.length||0} Elemente</small></button>`).join('')}</div>`,actions:'<button class="button" data-close-modal>Abbrechen</button>'});document.querySelectorAll('[data-pick-media-playlist]').forEach(button=>button.onclick=async()=>{await post(`/api/playlists/${button.dataset.pickMediaPlaylist}/items`,{label:title,media_url:selected.url,mime_type:selected.mime_type||'',thumbnail_path:image,source:{kind:type,quality:selected.quality,natural_key:naturalKey,sources}});closeModal();toast('Zur Playlist hinzugefügt.')})};
 try{element.load()}catch{}
 await playElement(false);
}
function closeModal(){modalRoot.innerHTML=''}
function debounce(fn,delay){let timer;return(...args)=>{clearTimeout(timer);timer=setTimeout(()=>fn(...args),delay)}}

main.addEventListener('click',async event=>{
 const route=event.target.closest('[data-route]')?.dataset.route;if(route){closeModal();navigate(route);return}
 const pub=event.target.closest('[data-publication-id]')?.dataset.publicationId;if(pub){closeModal();openPublication(pub);return}
 const docNode=event.target.closest('[data-document-id]');const doc=docNode?.dataset.documentId;if(doc){state.pendingBlockIdentifier=docNode.dataset.blockIdentifier||null;closeModal();openDocument(doc);return}
 const catalog=event.target.closest('[data-catalog-id],[data-action="catalog-open"]');if(catalog){openCatalog(catalog.dataset.catalogId||catalog.dataset.id);return}
 const meetingOffset=event.target.closest('[data-meeting-offset]')?.dataset.meetingOffset;if(meetingOffset!==undefined){state.meetingOffset=Number(meetingOffset);renderMeetings();return}
 const meetingDownload=event.target.closest('[data-meeting-download]')?.dataset.meetingDownload;if(meetingDownload){await startCatalogDownload(meetingDownload,event.target.closest('[data-meeting-download]'));return}
 const meetingNote=event.target.closest('[data-meeting-note]');if(meetingNote){openMeetingNote(Number(meetingNote.dataset.meetingNote),meetingNote.dataset.meetingTitle||'Programmpunkt');return}
 const action=event.target.closest('[data-action]')?.dataset.action;
 if(action==='language')openLanguage();
 if(action==='bible-catalog')renderCatalogPage('bibles');
 if(action==='import-jwpub')document.querySelector('#jwpub-input').click();
 if(action==='import-jwlibrary')document.querySelector('#jwlibrary-input').click();
 if(action==='import-jwlplaylist')document.querySelector('#jwlplaylist-input').click();
 if(action==='sync')syncCatalog();
 if(action==='publication-refresh')refreshPublicationCatalog(true);
 if(action==='show-new'){navigate('publications');}
 if(action==='catalog-search')navigate('publications');
 if(action==='new-note')openNoteDialog();
 if(action==='favorite'){const node=event.target.closest('[data-action="favorite"]');await post('/api/favorite',{publication_id:node.dataset.id,favorite:Number(node.dataset.value)});toast(Number(node.dataset.value)?'Zu Favoriten hinzugefügt.':'Aus Favoriten entfernt.');render()}
 if(action==='reader-bookmark'){const data=state.readerData;await post('/api/bookmarks',{document_id:state.selectedDocument,title:data.document.toc_title||data.document.title,snippet:state.selection?.text||'',block_identifier:state.selection?.blockIdentifier});toast('Lesezeichen gespeichert.');renderReader()}
 if(action==='reader-toc'){const data=state.readerData;modalRoot.innerHTML=modal({title:'Inhaltsverzeichnis',wide:true,body:`<div class="document-list">${data.navigation.map(item=>`<button class="document-item ${Number(item.id)===Number(state.selectedDocument)?'active':''}" data-document-id="${item.id}"><strong>${esc(item.toc_title||item.title)}</strong></button>`).join('')}</div>`})}
 if(action==='new-playlist'){modalRoot.innerHTML=modal({title:'Neue Playlist',body:'<div class="form-field"><label>Name</label><input id="playlist-title"></div>',actions:'<button class="button" data-close-modal>Abbrechen</button><button class="button primary" id="save-playlist">Erstellen</button>'});document.querySelector('#save-playlist').onclick=async()=>{await post('/api/playlists',{title:document.querySelector('#playlist-title').value});closeModal();renderPlaylists()}}
 const dp=event.target.closest('[data-delete-playlist]')?.dataset.deletePlaylist;if(dp){await del(`/api/playlists/${dp}`);toast('Playlist gelöscht.');renderPlaylists();return}
 if(action==='reader-font-down')setReaderScale(readerScale()-.1);if(action==='reader-font-reset')setReaderScale(1);if(action==='reader-font-up')setReaderScale(readerScale()+.1)
 const studyTab=event.target.closest('[data-study-tab]')?.dataset.studyTab;if(studyTab){state.studyTab=studyTab;document.querySelectorAll('[data-study-tab]').forEach(x=>x.classList.toggle('active',x.dataset.studyTab===studyTab));document.querySelector('#study-content').innerHTML=studyPanel(studyTab)}
 const moreHighlights=event.target.closest('[data-load-more-highlights]');if(moreHighlights){await loadMoreHighlights();return}
 const contextBack=event.target.closest('[data-context-back]');if(contextBack){const previous=(state.readerContextHistory||[]).pop();if(previous){state.readerContext=previous;const node=document.querySelector('#study-content');if(node){node.innerHTML=studyPanel('context');if((state.readerContext?.links||[]).length===1)setTimeout(()=>node.querySelector('[data-context-link]')?.click(),0)}}return}
 const contextLink=event.target.closest('[data-context-link]');if(contextLink){const item=(state.readerContext?.links||[])[Number(contextLink.dataset.contextLink)];if(item)await resolveContextItem(item);return}
 const contextRefresh=event.target.closest('[data-context-refresh]');if(contextRefresh){if(state.contextLastItem)await resolveContextItem(state.contextLastItem,{refresh:true});return}
 const onlineLarge=event.target.closest('[data-online-large]');if(onlineLarge){openOnlinePreview();return}
 const externalNode=event.target.closest('[data-open-external]');if(externalNode){try{await post('/api/open-external',{url:externalNode.dataset.openExternal});toast('Link wurde im Browser geöffnet.')}catch(error){toast(error.message,'error')}return}
 const sourceDownload=event.target.closest('[data-context-download]');if(sourceDownload){await startContextDownload(sourceDownload.dataset.contextDownload);return}
 const dm=event.target.closest('[data-delete-mark]')?.dataset.deleteMark;if(dm){await del(`/api/marks/${dm}`);toast('Markierung entfernt.');state.route==='highlights'?renderHighlights():renderReader();return}
 const openMark=event.target.closest('[data-open-mark]');if(openMark){state.pendingBlockIdentifier=openMark.dataset.markBlock||null;openDocument(openMark.dataset.openMark);return}
 const settingsTab=event.target.closest('[data-settings-tab]')?.dataset.settingsTab;if(settingsTab){state.settingsTab=settingsTab;renderSettings();return}
 const settingControl=event.target.closest('[data-setting-key]');if(settingControl&&event.type==='change'){return}
 const openBookmark=event.target.closest('[data-open-bookmark]');if(openBookmark&&openBookmark.dataset.openBookmark){state.pendingBlockIdentifier=openBookmark.dataset.bookmarkBlock||null;closeModal();openDocument(openBookmark.dataset.openBookmark);return}
 const dbm=event.target.closest('[data-delete-bookmark]')?.dataset.deleteBookmark;if(dbm){await del(`/api/bookmarks/${dbm}`);toast('Lesezeichen entfernt.');renderReader()}
 const kind=event.target.closest('[data-catalog-kind]')?.dataset.catalogKind;if(kind){await loadPublicationCategory(kind,document.querySelector('#publication-filter')?.value||'');return}
 const mediaNode=event.target.closest('[data-media-url]');if(mediaNode){openMediaPlayer(mediaNode)}
 const retry=event.target.closest('[data-retry-download]')?.dataset.retryDownload;if(retry){await post(`/api/downloads/${retry}/retry`,{});renderDownloads()} const cancel=event.target.closest('[data-cancel-download]')?.dataset.cancelDownload;if(cancel){await post(`/api/downloads/${cancel}/cancel`,{});renderDownloads()} const removeDownload=event.target.closest('[data-remove-download]')?.dataset.removeDownload;if(removeDownload){if(confirm('Download und unvollständige Restdateien wirklich entfernen?')){await post(`/api/downloads/${removeDownload}/remove`,{});renderDownloads()}}
 const removePublication=event.target.closest('[data-remove-publication]')?.dataset.removePublication;if(removePublication){const item=state.library?.find(x=>x.id===removePublication);if(window.confirm(`Publikation wirklich entfernen?\n\n${item?.title||removePublication}\n\nDie lokale Publikation und ihre importierten Inhalte werden gelöscht.`)){await del(`/api/publications/${encodeURIComponent(removePublication)}`);toast('Publikation entfernt.');state.selectedPublication=null;renderLibrary()}return}
 const tagNode=event.target.closest('[data-tag-name]');if(tagNode){await openTag(tagNode.dataset.tagName);return}
 const tagEntry=event.target.closest('[data-open-tag-document]');if(tagEntry){state.pendingBlockIdentifier=tagEntry.dataset.tagBlock||null;openDocument(tagEntry.dataset.openTagDocument);return}
 const noteEntry=event.target.closest('[data-open-note-document]');if(noteEntry&&!event.target.closest('[data-delete-note]')){state.pendingBlockIdentifier=noteEntry.dataset.noteBlock||null;openDocument(noteEntry.dataset.openNoteDocument);return}
 const remove=event.target.closest('[data-delete-note]')?.dataset.deleteNote;if(remove){await del(`/api/notes/${remove}`);toast('Notiz gelöscht.');renderNotes()}
});
main.addEventListener('error',event=>{const video=event.target.closest?.('.context-inline-video');if(video){const note=video.parentElement?.querySelector('.context-video-error');if(note)note.hidden=false}},true);
main.addEventListener('change',async event=>{const control=event.target.closest('[data-setting-key]');if(!control)return;const key=control.dataset.settingKey,value=control.value;await post('/api/settings',{[key]:value});if(key==='theme'||key==='font_size')applyAppearance({theme:key==='theme'?value:storageGet('limad-theme','light'),font_size:key==='font_size'?value:storageGet('limad-font-size','100')});toast('Einstellung gespeichert.')});
document.addEventListener('input',event=>{if(event.target.id==='publication-filter'){clearTimeout(window.__limadPublicationSearchTimer);window.__limadPublicationSearchTimer=setTimeout(()=>loadPublicationCategory(state.publicationCategory||'latest',event.target.value||''),250)}});
modalRoot.addEventListener('click',async event=>{
 if(event.target.matches('.modal-backdrop[data-close-modal]')||event.target.closest('button[data-close-modal]')){closeModal();return}
 const lang=event.target.closest('[data-language-id]');if(lang){state.languageIndex=Number(lang.dataset.languageId);state.languageName=lang.dataset.languageName;storageSet('limad-language',String(state.languageIndex));await post('/api/settings',{language_index:state.languageIndex});closeModal();document.documentElement.lang=uiLocale();installChrome();toast(`Sprache: ${state.languageName}`);render();return}
 const doc=event.target.closest('[data-document-id]')?.dataset.documentId;if(doc){closeModal();openDocument(doc);return}
 const pub=event.target.closest('[data-publication-id]')?.dataset.publicationId;if(pub){closeModal();openPublication(pub);return}
 const download=event.target.closest('[data-download-catalog]')?.dataset.downloadCatalog;if(download){await startCatalogDownload(download,event.target.closest('[data-download-catalog]'));return}
 const action=event.target.closest('[data-action]')?.dataset.action;if(action==='import-jwpub'){closeModal();document.querySelector('#jwpub-input').click()}if(action==='import-jwlibrary'){closeModal();document.querySelector('#jwlibrary-input').click()}if(action==='import-jwlplaylist'){closeModal();document.querySelector('#jwlplaylist-input').click()}if(action==='reconcile-backups'){await post('/api/backups/reconcile',{});toast('Quellen wurden neu zugeordnet.');return navigate('backups')}if(action==='backup-details'){return showBackupDetails(target.dataset.id)}if(action==='sync'){closeModal();syncCatalog()}
});
function refreshReaderMarkUi(){const marks=state.readerData?.marks||[];const badge=document.querySelector('[data-study-tab="highlights"] b');if(badge)badge.textContent=String(marks.length);if(state.route==='reader'&&state.studyTab==='highlights'){const node=document.querySelector('#study-content');if(node)node.innerHTML=studyPanel('highlights')}const bibleNotes=document.querySelector('.bible-v2-notes>div');if(bibleNotes&&state.route==='bible')bibleNotes.innerHTML=bibleNotesPanel(state.readerData)}
function readerFrameMessage(target,type,payload={}){try{target?.postMessage({type,...payload},location.origin)}catch{}}
window.addEventListener('message',async event=>{if(event.origin!==location.origin)return;const d=event.data||{};if(d.type==='limad-image'){openReaderImage(d)}if(d.type==='limad-media-error'){toast('Interne Medienwiedergabe nicht möglich. Die Online-Alternative bleibt verfügbar.','error')}if(d.type==='limad-context'){state.readerContextHistory=[];state.readerContext={blockIdentifier:d.blockIdentifier,text:d.text,links:normalizeContextSourceLinks(d.links||[])};document.querySelectorAll('.study-tab').forEach(x=>x.classList.toggle('active',x.dataset.studyTab==='context'));const node=document.querySelector('#study-content');if(node)node.innerHTML=studyPanel('context')}if(d.type==='limad-link'){const frame=document.querySelector('#reader-frame');let keepX=Number(d.readerScrollX||0),keepY=Number(d.readerScrollY||0);try{if(frame?.contentWindow){keepX=frame.contentWindow.scrollX;keepY=frame.contentWindow.scrollY}}catch{}state.readerContextHistory=state.readerContextHistory||[];if(state.readerContext)state.readerContextHistory.push(state.readerContext);state.readerContext={blockIdentifier:null,text:'',links:normalizeContextSourceLinks([{href:d.href,label:d.label||d.text||'Quelle öffnen'}])};document.querySelectorAll('.study-tab').forEach(x=>x.classList.toggle('active',x.dataset.studyTab==='context'));const node=document.querySelector('#study-content');if(node){node.innerHTML=studyPanel('context');node.querySelector('[data-context-link]')?.click()}const restore=()=>{try{frame?.contentWindow?.scrollTo(keepX,keepY)}catch{}};requestAnimationFrame(restore);setTimeout(restore,0);setTimeout(restore,100)}if(d.type==='limad-selection'){state.selection=d;openNoteDialog({document_id:d.documentId,block_identifier:d.blockIdentifier,start_token:d.startToken,end_token:d.endToken,linked_mark_id:d.markId,selection_text:d.text,content:d.text})}if(d.type==='limad-mark'){state.selection=d;const response=await post('/api/marks',{document_id:d.documentId,block_identifier:d.blockIdentifier,start_token:d.startToken,end_token:d.endToken,color_index:d.colorIndex});const mark={...(response.mark||{}),text:d.text||''};if(state.readerData){const marks=state.readerData.marks||(state.readerData.marks=[]);marks.push(mark)}readerFrameMessage(event.source,'limad-mark-applied',{mark});refreshReaderMarkUi();toast('Markierung gespeichert.')}if(d.type==='limad-mark-update'){const response=await post(`/api/marks/${encodeURIComponent(d.markId)}/update`,{color_index:d.colorIndex});const mark=response.mark||{id:d.markId,color_index:d.colorIndex};if(state.readerData){const item=(state.readerData.marks||[]).find(entry=>String(entry.id)===String(d.markId));if(item)Object.assign(item,mark)}readerFrameMessage(event.source,'limad-mark-updated',{mark});refreshReaderMarkUi();toast('Markierungsfarbe geändert.')}if(d.type==='limad-mark-delete'){await del(`/api/marks/${encodeURIComponent(d.markId)}`);if(state.readerData)state.readerData.marks=(state.readerData.marks||[]).filter(entry=>String(entry.id)!==String(d.markId));readerFrameMessage(event.source,'limad-mark-deleted',{markId:String(d.markId)});refreshReaderMarkUi();toast('Markierung entfernt.')}if(d.type==='limad-position'){post('/api/reading-position',{document_id:d.documentId,scroll_ratio:d.scrollRatio,block_identifier:d.blockIdentifier}).catch(()=>{})}if(d.type==='limad-reader-ready'){const frame=document.querySelector('#reader-frame');const source=event.source;source?.postMessage({type:'limad-font',scale:readerScale()},location.origin);source?.postMessage({type:'limad-theme',theme:storageGet('limad-theme','light')},location.origin);if(frame?.contentWindow===source){let pos=state.readerData?.position||{};if(state.route==='bible'&&state.selectedDocument){try{pos=await get(`/api/reading-position?document_id=${state.selectedDocument}`)}catch{}}const restoreBlock=state.pendingBlockIdentifier||pos.block_identifier;source?.postMessage({type:'limad-restore',scrollRatio:state.pendingBlockIdentifier?0:(pos.scroll_ratio||0),blockIdentifier:restoreBlock},location.origin);state.pendingBlockIdentifier=null}}if(d.type==='limad-input-field-saved'){if(state.readerData){const fields=state.readerData.input_fields||(state.readerData.input_fields=[]);const existing=fields.find(item=>String(item.text_tag)===String(d.textTag));if(existing)existing.value=d.value;else fields.push({text_tag:d.textTag,value:d.value});const badge=document.querySelector('[data-study-tab="fields"] b');if(badge)badge.textContent=String(fields.filter(item=>String(item.value||'').trim()).length)}}if(d.type==='limad-note-open'){openNoteDialog({document_id:state.selectedDocument,block_identifier:d.note.block_identifier,title:d.note.title,content:d.note.content})}});
document.addEventListener('click',event=>{const route=event.target.closest('[data-route]')?.dataset.route;if(route&&!main.contains(event.target)){navigate(route)}});

async function reportFrontend(stateName,stage,message=''){
 try{await fetch('/api/frontend/event',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({state:stateName,stage,message}),keepalive:true})}catch(_error){}
}
function frontendFailure(error,stage='unknown'){
 const message=(error&&error.message)||String(error||'Unbekannter Fehler');
 window.__LIMAD_STUDY_BOOT={...(window.__LIMAD_STUDY_BOOT||{}),stage:'failed:'+stage,error:message};
 reportFrontend('failed',stage,message);
 window.dispatchEvent(new CustomEvent('limad-study-failed',{detail:{stage,message}}));
 return message;
}
window.addEventListener('error',event=>frontendFailure(event.error||event.message,'window-error'));
window.addEventListener('unhandledrejection',event=>frontendFailure(event.reason,'unhandled-rejection'));
async function bootstrap(){
 window.__LIMAD_STUDY_BOOT={started:Date.now(),stage:'install-chrome'};
 await reportFrontend('starting','install-chrome');
 installChrome();
 window.__LIMAD_STUDY_BOOT.stage='status';
 await reportFrontend('starting','status');
 state.status=await get('/api/status');
 applyAppearance(state.status?.settings||{});
 const persistedLanguage=Number(state.status?.settings?.language_index);
 if(Number.isFinite(persistedLanguage)&&persistedLanguage>0)state.languageIndex=persistedLanguage;
 window.__LIMAD_STUDY_BOOT.stage='languages';
 await reportFrontend('starting','languages');
 const languages=await get(`/api/languages?q=&limit=20`);
 const current=languages.find(item=>Number(item.id)===state.languageIndex);
 if(current)state.languageName=current.vernacular_name||current.english_name;
 window.__LIMAD_STUDY_BOOT.stage='home';
 await reportFrontend('starting','home');
 await navigate('home');
 const navigation=document.querySelector('#main-nav .nav-item');
 const content=document.querySelector('#main-content');
 if(!navigation||!content||!content.children.length)throw new Error('Navigation oder Startseiteninhalt wurde nicht aufgebaut.');
 window.__LIMAD_STUDY_READY=true;
 window.__LIMAD_STUDY_BOOT.stage='ready';
 await reportFrontend('ready','ready');
 window.dispatchEvent(new Event('limad-study-ready'));
}
bootstrap().catch(error=>{const message=frontendFailure(error,window.__LIMAD_STUDY_BOOT?.stage||'bootstrap');main.innerHTML=`<div class="page">${empty('LiMaD Study konnte nicht gestartet werden',message)}</div>`;toast(message,'error')});

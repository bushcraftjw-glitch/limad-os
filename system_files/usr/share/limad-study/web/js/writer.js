(()=>{'use strict';
const DOC_KEY='limad-study-writer-v4-document';
const UI_KEY='limad-study-writer-v4-ui';
const LEGACY_KEY='limad-study-writer-v3';
const MIN_W=560;
const MIN_H=430;
const PAPER_W=794;
const PAPER_H=1123;
let win,dock,fab,editor,pageShell,titleInput,statusText,wordCount,pageCount,zoomText,saveTimer,savedRange,dragState,resizeState;
const $=(s,r=document)=>r.querySelector(s);
const $$=(s,r=document)=>[...r.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icon=(name,size=18)=>{
 const paths={
  document:'<path d="M4 1.5A1.5 1.5 0 0 1 5.5 0h5.793L16 4.707V14.5a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 4 14.5z"/><path d="M10.5 0v5H16M7 8h6M7 10.5h6M7 13h4"/>',
  minimize:'<path d="M3 8h10"/>',
  maximize:'<rect x="2.5" y="2.5" width="11" height="11" rx="1.5"/>',
  restore:'<path d="M5 2.5h7.5a1 1 0 0 1 1 1V11M3.5 5h7.5a1 1 0 0 1 1 1v7.5H4.5a1 1 0 0 1-1-1z"/>',
  close:'<path d="m3 3 10 10M13 3 3 13"/>',
  save:'<path d="M2 2.5A1.5 1.5 0 0 1 3.5 1h8L15 4.5v9A1.5 1.5 0 0 1 13.5 15h-11A1.5 1.5 0 0 1 1 13.5v-10A1.5 1.5 0 0 1 2.5 2z"/><path d="M4 1v5h7V1M4 15v-5h8v5"/>',
  print:'<path d="M4 6V1h8v5M4 12H2.5A1.5 1.5 0 0 1 1 10.5v-3A1.5 1.5 0 0 1 2.5 6h11A1.5 1.5 0 0 1 15 7.5v3a1.5 1.5 0 0 1-1.5 1.5H12"/><path d="M4 10h8v5H4z"/>',
  pdf:'<path d="M4 1.5A1.5 1.5 0 0 1 5.5 0h5L15 4.5v10A1.5 1.5 0 0 1 13.5 16h-8A1.5 1.5 0 0 1 4 14.5z"/><path d="M10 0v5h5M2 9h9v4H2z"/><path d="M3 10v2M5 10h1a1 1 0 0 1 0 2H5zM8 12v-2h2"/>',
  collapse:'<path d="m3 6 5 5 5-5"/>',
  expand:'<path d="m3 10 5-5 5 5"/>',
  quote:'<path d="M2.5 3.5h4v4h-2c0 2-1 3-2.5 3.5M9.5 3.5h4v4h-2c0 2-1 3-2.5 3.5"/>',
  link:'<path d="M6.5 10.5 5 12a3 3 0 0 1-4-4l2.5-2.5a3 3 0 0 1 4 0M9.5 5.5 11 4a3 3 0 0 1 4 4l-2.5 2.5a3 3 0 0 1-4 0M5.5 8h5"/>',
  undo:'<path d="M5 5H1V1M1 5a6 6 0 1 1 1.5 6"/>',
  redo:'<path d="M11 5h4V1M15 5a6 6 0 1 0-1.5 6"/>',
  new:'<path d="M4 1.5A1.5 1.5 0 0 1 5.5 0h5L15 4.5v10A1.5 1.5 0 0 1 13.5 16h-8A1.5 1.5 0 0 1 4 14.5z"/><path d="M10 0v5h5M8 8v5M5.5 10.5h5"/>',
  odt:'<path d="M4 1.5A1.5 1.5 0 0 1 5.5 0h5L15 4.5v10A1.5 1.5 0 0 1 13.5 16h-8A1.5 1.5 0 0 1 4 14.5z"/><path d="M10 0v5h5M3 10c0-1 .6-1.5 1.5-1.5S6 9 6 10v1.5C6 12.5 5.4 13 4.5 13S3 12.5 3 11.5zM7 8.5h4M9 8.5V13M12 8.5h2"/>',
  chevron:'<path d="m6 3 5 5-5 5"/>'
 };
 return `<svg class="writer-svg" width="${size}" height="${size}" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.45" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name]||paths.document}</svg>`;
};
function readJSON(key,fallback){try{return {...fallback,...JSON.parse(localStorage.getItem(key)||'{}')}}catch{return {...fallback}}}
function defaultDocument(){
 const legacy=localStorage.getItem(LEGACY_KEY);
 return {title:'Neue Ausarbeitung',html:legacy||'<h1>Neue Ausarbeitung</h1><p>Hier kannst du dich direkt in LiMaD Study vorbereiten.</p>',updatedAt:new Date().toISOString()};
}
function loadDocument(){return readJSON(DOC_KEY,defaultDocument())}
function loadUI(){
 const w=Math.min(820,Math.max(MIN_W,innerWidth*.56));
 const h=Math.min(680,Math.max(MIN_H,innerHeight*.72));
 return readJSON(UI_KEY,{mode:'collapsed',x:Math.max(20,(innerWidth-w)/2),y:Math.max(76,(innerHeight-h)/2),w,h,maximized:false,restore:null});
}
let docState=loadDocument();
let uiState=loadUI();
function writeJSON(key,value){try{localStorage.setItem(key,JSON.stringify(value));return true}catch{return false}}
function sanitizeFilename(value){return(String(value||'Study-Dokument').trim()||'Study-Dokument').replace(/[\\/:*?"<>|]+/g,'-').replace(/\s+/g,' ').slice(0,120)}
function countWords(){const words=(editor?.innerText.trim().match(/\S+/g)||[]).length;const pages=Math.max(1,Math.ceil(Math.max(PAPER_H,editor?.scrollHeight||PAPER_H)/PAPER_H));if(wordCount)wordCount.textContent=`${words} Wörter`;if(pageCount)pageCount.textContent=`Seite 1 von ${pages}`}
function updatePaperScale(){
 if(!win||!editor||!pageShell||win.hidden)return;
 const stage=$('.writer-stage',win);
 if(!stage)return;
 const available=Math.max(300,stage.clientWidth-34);
 const scale=Math.max(.42,Math.min(1.25,available/PAPER_W));
 const naturalHeight=Math.max(PAPER_H,editor.scrollHeight);
 editor.style.width=`${PAPER_W}px`;
 editor.style.minHeight=`${PAPER_H}px`;
 editor.style.transform=`scale(${scale})`;
 pageShell.style.width=`${Math.ceil(PAPER_W*scale)}px`;
 pageShell.style.height=`${Math.ceil(naturalHeight*scale)}px`;
 if(zoomText)zoomText.textContent=`${Math.round(scale*100)} %`;
 countWords();
}
function setStatus(text,kind=''){if(!statusText)return;statusText.textContent=text;statusText.dataset.kind=kind}
function persistDocument(immediate=false){
 if(!editor||!titleInput)return;
 docState={title:titleInput.value.trim()||'Neue Ausarbeitung',html:editor.innerHTML,updatedAt:new Date().toISOString()};
 writeJSON(DOC_KEY,docState);
 setStatus('Gespeichert','saved');
 countWords();
 updatePaperScale();
 clearTimeout(saveTimer);
 if(!immediate)saveTimer=setTimeout(()=>setStatus('Automatisch gespeichert',''),1300);
 syncLabels();
}
function scheduleSave(){setStatus('Wird gespeichert …','pending');clearTimeout(saveTimer);saveTimer=setTimeout(()=>persistDocument(),450)}
function persistUI(){
 if(win&&!win.hidden&&!uiState.maximized){const r=win.getBoundingClientRect();uiState.x=Math.round(r.left);uiState.y=Math.round(r.top);uiState.w=Math.round(r.width);uiState.h=Math.round(r.height)}
 writeJSON(UI_KEY,uiState);
}
function syncLabels(){
 $$('.writer-document-label').forEach(node=>node.textContent=docState.title||'Neue Ausarbeitung');
 $$('.writer-dirty-dot').forEach(node=>node.title=`Zuletzt gespeichert: ${new Date(docState.updatedAt).toLocaleString('de-DE')}`);
}
function applyGeometry(){
 if(!win)return;
 if(uiState.maximized){win.style.left='16px';win.style.top='76px';win.style.width=`${Math.max(MIN_W,innerWidth-32)}px`;win.style.height=`${Math.max(MIN_H,innerHeight-94)}px`;requestAnimationFrame(updatePaperScale);return}
 const w=Math.max(MIN_W,Math.min(Number(uiState.w)||760,innerWidth-24));
 const h=Math.max(MIN_H,Math.min(Number(uiState.h)||620,innerHeight-86));
 const x=Math.max(8,Math.min(Number(uiState.x)||20,innerWidth-w-8));
 const y=Math.max(68,Math.min(Number(uiState.y)||76,innerHeight-h-8));
 Object.assign(win.style,{left:`${x}px`,top:`${y}px`,width:`${w}px`,height:`${h}px`});
 requestAnimationFrame(updatePaperScale);
}
function updateMode(mode){
 uiState.mode=mode;
 if(mode==='open'){win.hidden=false;dock.hidden=true;fab.hidden=true;applyGeometry();requestAnimationFrame(()=>{updatePaperScale();editor.focus()})}
 if(mode==='dock'){win.hidden=true;dock.hidden=false;fab.hidden=true}
 if(mode==='collapsed'){win.hidden=true;dock.hidden=true;fab.hidden=false;positionFab()}
 if(mode==='closed'){win.hidden=true;dock.hidden=true;fab.hidden=true}
 persistUI();
}
function positionFab(){
 if(!fab||fab.hidden)return;
 const ai=$('#limad-ai-fab');
 if(ai&&!ai.hidden){const r=ai.getBoundingClientRect();fab.style.right=`${Math.max(14,innerWidth-r.left+10)}px`;fab.style.bottom=`${Math.max(14,innerHeight-r.bottom)}px`}
 else{fab.style.right='28px';fab.style.bottom='28px'}
}
function saveSelection(){
 const sel=getSelection();
 if(sel&&sel.rangeCount&&editor?.contains(sel.anchorNode)){savedRange=sel.getRangeAt(0).cloneRange()}
}
function restoreSelection(){
 if(!savedRange)return;
 const sel=getSelection();sel.removeAllRanges();sel.addRange(savedRange)
}
function command(name,value=null){editor.focus();restoreSelection();document.execCommand('styleWithCSS',false,true);document.execCommand(name,false,value);saveSelection();scheduleSave()}
function insertHTML(html){editor.focus();restoreSelection();document.execCommand('insertHTML',false,html);saveSelection();scheduleSave()}
function currentSource(){
 let selected='';
 const frame=$('#reader-frame');
 try{selected=frame?.contentWindow?.getSelection()?.toString().trim()||''}catch{}
 if(!selected){const sel=getSelection();if(sel&&sel.rangeCount&&!editor.contains(sel.anchorNode))selected=sel.toString().trim()}
 const publication=$('.reader-title strong')?.textContent.trim()||$('.publication-reader-header h1')?.textContent.trim()||$('.page-header h1')?.textContent.trim()||'LiMaD Study';
 const article=$('.reader-title small')?.textContent.trim()||$('.publication-hero h1')?.textContent.trim()||document.title;
 const date=$('.publication-hero time')?.textContent.trim()||$('.meeting-week-title')?.textContent.trim()||'';
 return {selected,publication,article,date};
}
function insertSource(){
 const source=currentSource();
 const quote=source.selected?`<blockquote>${esc(source.selected).replace(/\n+/g,'<br>')}</blockquote>`:'';
 const details=[source.publication,source.article,source.date].filter(Boolean).filter((v,i,a)=>a.indexOf(v)===i).join(', ');
 insertHTML(`${quote}<p class="writer-source-line"><strong>Aus der Quelle entliehen:</strong> ${esc(details)}.</p><p><br></p>`)
}
function newDocument(){
 persistDocument(true);
 const dialog=document.createElement('div');
 dialog.className='writer-dialog';
 dialog.innerHTML=`<form class="writer-dialog-card"><h3>Neues Dokument</h3><p>Das aktuelle Dokument bleibt automatisch gespeichert. Gib dem neuen Dokument einen Namen.</p><label>Dokumentname</label><input value="Neue Ausarbeitung" maxlength="120" autofocus><div><button type="button" data-cancel>Abbrechen</button><button type="submit" class="primary">Erstellen</button></div></form>`;
 win.append(dialog);
 const input=$('input',dialog);setTimeout(()=>{input.focus();input.select()},0);
 $('[data-cancel]',dialog).onclick=()=>dialog.remove();
 $('form',dialog).onsubmit=e=>{e.preventDefault();docState={title:input.value.trim()||'Neue Ausarbeitung',html:`<h1>${esc(input.value.trim()||'Neue Ausarbeitung')}</h1><p></p>`,updatedAt:new Date().toISOString()};titleInput.value=docState.title;editor.innerHTML=docState.html;writeJSON(DOC_KEY,docState);dialog.remove();countWords();syncLabels();editor.focus()}
}
function safeTitleHTML(){return esc(docState.title||'Study-Dokument')}
function printableHTML(){
 return `<!doctype html><html lang="de"><head><meta charset="utf-8"><title>${safeTitleHTML()}</title><style>@page{size:A4;margin:20mm}body{font-family:"Noto Serif",serif;color:#171717;font-size:11pt;line-height:1.55;margin:0}h1{font-size:24pt;color:#111}h2{font-size:18pt;color:#111}h3{font-size:14pt;color:#111}blockquote{border-left:4px solid #8b5cf6;margin:16px 0;padding:8px 16px;background:#f6f2ff}.writer-source-line{border-top:1px solid #ccc;padding-top:10px;color:#555}a{color:#5f36ad}img{max-width:100%}</style></head><body>${editor.innerHTML}</body></html>`;
}
function printDocument(pdf=false){
 persistDocument(true);
 const frame=document.createElement('iframe');frame.className='writer-print-frame';frame.setAttribute('aria-hidden','true');document.body.append(frame);
 const target=frame.contentDocument;target.open();target.write(printableHTML());target.close();
 setStatus(pdf?'Druckdialog: „In Datei drucken“ und PDF wählen':'Druckdialog wird geöffnet','');
 setTimeout(()=>{frame.contentWindow.focus();frame.contentWindow.print();setTimeout(()=>frame.remove(),1800)},250)
}
const u16=n=>[n&255,n>>>8&255],u32=n=>[n&255,n>>>8&255,n>>>16&255,n>>>24&255];
function crc32(a){let c=-1;for(const b of a){c^=b;for(let k=0;k<8;k++)c=(c>>>1)^((c&1)?0xedb88320:0)}return(c^-1)>>>0}
function zipStore(files){const enc=new TextEncoder(),out=[],central=[];let off=0;for(const [name,data] of files){const n=enc.encode(name),d=data instanceof Uint8Array?data:enc.encode(data),crc=crc32(d);const local=new Uint8Array([...u32(0x04034b50),...u16(20),...u16(0),...u16(0),...u16(0),...u16(0),...u32(crc),...u32(d.length),...u32(d.length),...u16(n.length),...u16(0),...n,...d]);out.push(local);central.push(new Uint8Array([...u32(0x02014b50),...u16(20),...u16(20),...u16(0),...u16(0),...u16(0),...u16(0),...u32(crc),...u32(d.length),...u32(d.length),...u16(n.length),...u16(0),...u16(0),...u16(0),...u16(0),...u32(0),...u32(off),...n]));off+=local.length}const cs=central.reduce((a,b)=>a+b.length,0),end=new Uint8Array([...u32(0x06054b50),...u16(0),...u16(0),...u16(files.length),...u16(files.length),...u32(cs),...u32(off),...u16(0)]);return new Blob([...out,...central,end],{type:'application/vnd.oasis.opendocument.text'})}
function odtInline(node){if(node.nodeType===3)return esc(node.nodeValue);if(node.nodeType!==1)return'';const tag=node.tagName.toLowerCase();const body=[...node.childNodes].map(odtInline).join('');if(tag==='br')return'<text:line-break/>';if(tag==='a')return`<text:a xlink:href="${esc(node.href)}">${body}</text:a>`;if(tag==='b'||tag==='strong')return`<text:span text:style-name="Bold">${body}</text:span>`;if(tag==='i'||tag==='em')return`<text:span text:style-name="Italic">${body}</text:span>`;if(tag==='u')return`<text:span text:style-name="Underline">${body}</text:span>`;return body}
function odtBlock(node){if(node.nodeType===3)return node.textContent.trim()?`<text:p>${esc(node.textContent)}</text:p>`:'';if(node.nodeType!==1)return'';const t=node.tagName.toLowerCase();if(/^h[1-3]$/.test(t))return`<text:h text:outline-level="${t[1]}">${odtInline(node)}</text:h>`;if(t==='ul'||t==='ol')return`<text:list>${[...node.children].filter(x=>x.tagName==='LI').map(li=>`<text:list-item><text:p>${odtInline(li)}</text:p></text:list-item>`).join('')}</text:list>`;return`<text:p>${odtInline(node)}</text:p>`}
function makeODT(){
 const body=[...editor.childNodes].map(odtBlock).join('');
 const content=`<?xml version="1.0" encoding="UTF-8"?><office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" xmlns:xlink="http://www.w3.org/1999/xlink" office:version="1.3"><office:automatic-styles><style:style style:name="Bold" style:family="text"><style:text-properties fo:font-weight="bold"/></style:style><style:style style:name="Italic" style:family="text"><style:text-properties fo:font-style="italic"/></style:style><style:style style:name="Underline" style:family="text"><style:text-properties style:text-underline-style="solid"/></style:style></office:automatic-styles><office:body><office:text>${body}</office:text></office:body></office:document-content>`;
 const styles='<?xml version="1.0" encoding="UTF-8"?><office:document-styles xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" office:version="1.3"><office:styles/></office:document-styles>';
 const manifest='<?xml version="1.0" encoding="UTF-8"?><manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.3"><manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.text"/><manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/><manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/></manifest:manifest>';
 return zipStore([['mimetype','application/vnd.oasis.opendocument.text'],['content.xml',content],['styles.xml',styles],['META-INF/manifest.xml',manifest]])
}
function downloadODT(){persistDocument(true);const a=document.createElement('a');a.href=URL.createObjectURL(makeODT());a.download=`${sanitizeFilename(docState.title)}.odt`;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1600);setStatus('OpenDocument gespeichert','saved')}
function toggleMaximize(){
 if(uiState.maximized){uiState.maximized=false;if(uiState.restore)Object.assign(uiState,uiState.restore);uiState.restore=null}
 else{const r=win.getBoundingClientRect();uiState.restore={x:r.left,y:r.top,w:r.width,h:r.height};uiState.maximized=true}
 applyGeometry();persistUI()
}
function closeWriter(){persistDocument(true);updateMode('closed')}
function buildMarkup(){
 return `<section id="study-writer-window" class="writer-window" hidden aria-label="Dokument bearbeiten">
  <header class="writer-titlebar" data-writer-drag>
   <span class="writer-window-controls" aria-label="Fenstersteuerung">
    <button class="writer-traffic-button close" data-writer-action="close" title="Schließen" aria-label="Schließen"></button>
    <button class="writer-traffic-button minimize" data-writer-action="minimize" title="In Dokumentleiste minimieren" aria-label="Minimieren"></button>
    <button class="writer-traffic-button maximize" data-writer-action="maximize" title="Maximieren oder wiederherstellen" aria-label="Maximieren oder wiederherstellen"></button>
   </span>
   <span class="writer-title-icon">${icon('document',19)}</span>
   <input class="writer-title-input" value="${esc(docState.title)}" aria-label="Dokumentname">
   <span class="writer-status">Bereit</span>
  </header>
  <nav class="writer-menubar" aria-label="Dokumentmenü">
   <button data-writer-action="new">Datei</button><button data-writer-action="save">Speichern</button><button data-writer-action="print">Drucken</button><button data-writer-action="pdf">PDF</button><button data-writer-action="source">Quelle einfügen</button>
  </nav>
  <div class="writer-toolbar" role="toolbar">
   <button data-writer-command="undo" title="Rückgängig">${icon('undo')}</button><button data-writer-command="redo" title="Wiederholen">${icon('redo')}</button><span class="separator"></span>
   <select data-writer-block title="Absatzformat"><option value="p">Absatz</option><option value="h1">Überschrift 1</option><option value="h2">Überschrift 2</option><option value="h3">Überschrift 3</option><option value="blockquote">Zitat</option></select>
   <select data-writer-font title="Schriftart"><option value="Noto Serif">Noto Serif</option><option value="Noto Sans">Noto Sans</option><option value="Liberation Serif">Liberation Serif</option><option value="Liberation Sans">Liberation Sans</option><option value="DejaVu Serif">DejaVu Serif</option><option value="DejaVu Sans">DejaVu Sans</option></select>
   <select data-writer-size title="Schriftgröße"><option value="2">10</option><option value="3">12</option><option value="4" selected>14</option><option value="5">18</option><option value="6">24</option><option value="7">32</option></select>
   <label class="writer-color" title="Textfarbe"><span>A</span><input type="color" data-writer-color value="#000000"></label>
   <label class="writer-color highlight" title="Markierfarbe"><span>▰</span><input type="color" data-writer-highlight value="#fff19c"></label><span class="separator"></span>
   <button data-writer-command="bold" title="Fett"><b>B</b></button><button data-writer-command="italic" title="Kursiv"><i>I</i></button><button data-writer-command="underline" title="Unterstrichen"><u>U</u></button><button data-writer-command="strikeThrough" title="Durchgestrichen"><s>S</s></button><span class="separator"></span>
   <button data-writer-command="insertUnorderedList" title="Aufzählung">•≡</button><button data-writer-command="insertOrderedList" title="Nummerierung">1≡</button><button data-writer-command="outdent" title="Einzug verkleinern">⇤</button><button data-writer-command="indent" title="Einzug vergrößern">⇥</button><span class="separator"></span>
   <button data-writer-command="justifyLeft" title="Linksbündig">☰</button><button data-writer-command="justifyCenter" title="Zentriert">≡</button><button data-writer-command="justifyRight" title="Rechtsbündig">☷</button><button data-writer-command="justifyFull" title="Blocksatz">▤</button><span class="separator"></span>
   <button data-writer-action="link" title="Link einfügen">${icon('link')}</button><button class="source-button" data-writer-action="source" title="Markierten Inhalt mit Quellenangabe einfügen">${icon('quote')}<span>Quelle</span></button>
  </div>
  <div class="writer-stage"><div class="writer-page-shell"><article class="writer-paper" contenteditable="true" spellcheck="true" aria-label="DIN-A4-Dokumentseite">${docState.html}</article></div></div>
  <footer class="writer-footer"><span class="writer-page-count">Seite 1 von 1</span><span class="writer-word-count">0 Wörter</span><span>Deutsch (Deutschland)</span><span class="spacer"></span><button data-writer-action="save">${icon('save',16)} ODT</button><button data-writer-action="pdf">${icon('pdf',16)} PDF</button><span class="writer-zoom">100 %</span></footer>
  ${['n','ne','e','se','s','sw','w','nw'].map(x=>`<i class="writer-resize-handle ${x}" data-writer-resize="${x}"></i>`).join('')}
 </section>
 <nav id="study-writer-dock" class="writer-dock" hidden aria-label="Minimiertes Dokument">
  <span class="writer-dock-icon">${icon('document',21)}</span><span class="writer-document-label">${esc(docState.title)}</span><i class="writer-dirty-dot"></i><span class="writer-dock-spacer"></span>
  <button data-writer-action="save" title="Als OpenDocument speichern">${icon('save',20)}</button><button data-writer-action="print" title="Drucken">${icon('print',20)}</button><button data-writer-action="pdf" title="Als PDF exportieren">${icon('pdf',20)}</button><button data-writer-action="restore" title="Dokument öffnen">${icon('expand',20)}</button><button data-writer-action="collapse" title="Neben dem KI-Assistenten einklappen">${icon('collapse',20)}</button><button data-writer-action="close" title="Schließen">${icon('close',20)}</button>
 </nav>
 <button id="study-writer-fab" class="writer-fab" hidden title="Dokument öffnen"><span>${icon('document',20)}</span><strong>Dokument</strong><i class="writer-dirty-dot"></i></button>`;
}
function openLinkDialog(){
 const dialog=document.createElement('div');dialog.className='writer-dialog';dialog.innerHTML='<form class="writer-dialog-card"><h3>Link einfügen</h3><label>Adresse</label><input type="url" placeholder="https://…" autofocus><div><button type="button" data-cancel>Abbrechen</button><button type="submit" class="primary">Einfügen</button></div></form>';win.append(dialog);const input=$('input',dialog);setTimeout(()=>input.focus(),0);$('[data-cancel]',dialog).onclick=()=>dialog.remove();$('form',dialog).onsubmit=e=>{e.preventDefault();if(input.value.trim())command('createLink',input.value.trim());dialog.remove()}
}
function handleAction(action){
 if(action==='minimize')return updateMode('dock');
 if(action==='restore')return updateMode('open');
 if(action==='collapse')return updateMode('collapsed');
 if(action==='close')return closeWriter();
 if(action==='maximize')return toggleMaximize();
 if(action==='save')return downloadODT();
 if(action==='print')return printDocument(false);
 if(action==='pdf')return printDocument(true);
 if(action==='new')return newDocument();
 if(action==='source')return insertSource();
 if(action==='link')return openLinkDialog();
}
function bindUI(){
 editor=$('.writer-paper',win);pageShell=$('.writer-page-shell',win);titleInput=$('.writer-title-input',win);statusText=$('.writer-status',win);wordCount=$('.writer-word-count',win);pageCount=$('.writer-page-count',win);zoomText=$('.writer-zoom',win);
 document.body.addEventListener('click',e=>{const button=e.target.closest('[data-writer-action]');if(button)handleAction(button.dataset.writerAction)});
 fab.addEventListener('click',()=>updateMode('open'));
 win.addEventListener('click',e=>{const button=e.target.closest('[data-writer-command]');if(button)command(button.dataset.writerCommand)});
 $('[data-writer-block]',win).addEventListener('change',e=>command('formatBlock',e.target.value));
 $('[data-writer-font]',win).addEventListener('change',e=>command('fontName',e.target.value));
 $('[data-writer-size]',win).addEventListener('change',e=>command('fontSize',e.target.value));
 $('[data-writer-color]',win).addEventListener('input',e=>command('foreColor',e.target.value));
 $('[data-writer-highlight]',win).addEventListener('input',e=>command('hiliteColor',e.target.value));
 editor.addEventListener('input',()=>{scheduleSave();requestAnimationFrame(updatePaperScale)});editor.addEventListener('keyup',saveSelection);editor.addEventListener('mouseup',saveSelection);editor.addEventListener('focus',saveSelection);
 titleInput.addEventListener('input',scheduleSave);titleInput.addEventListener('change',()=>persistDocument(true));
 const drag=$('[data-writer-drag]',win);
 drag.addEventListener('pointerdown',e=>{if(e.target.closest('button,input'))return;if(uiState.maximized)return;const r=win.getBoundingClientRect();dragState={id:e.pointerId,dx:e.clientX-r.left,dy:e.clientY-r.top};drag.setPointerCapture(e.pointerId)});
 drag.addEventListener('pointermove',e=>{if(!dragState||dragState.id!==e.pointerId)return;const r=win.getBoundingClientRect();const x=Math.max(8,Math.min(e.clientX-dragState.dx,innerWidth-r.width-8));const y=Math.max(68,Math.min(e.clientY-dragState.dy,innerHeight-r.height-8));win.style.left=`${x}px`;win.style.top=`${y}px`});
 drag.addEventListener('pointerup',e=>{if(dragState?.id===e.pointerId){dragState=null;persistUI()}});
 $$('[data-writer-resize]',win).forEach(handle=>{
  handle.addEventListener('pointerdown',e=>{if(uiState.maximized)return;const r=win.getBoundingClientRect();resizeState={id:e.pointerId,dir:handle.dataset.writerResize,startX:e.clientX,startY:e.clientY,x:r.left,y:r.top,w:r.width,h:r.height};handle.setPointerCapture(e.pointerId);e.preventDefault()});
  handle.addEventListener('pointermove',e=>{if(!resizeState||resizeState.id!==e.pointerId)return;const s=resizeState,dx=e.clientX-s.startX,dy=e.clientY-s.startY;let x=s.x,y=s.y,w=s.w,h=s.h;if(s.dir.includes('e'))w=s.w+dx;if(s.dir.includes('s'))h=s.h+dy;if(s.dir.includes('w')){w=s.w-dx;x=s.x+dx}if(s.dir.includes('n')){h=s.h-dy;y=s.y+dy}if(w<MIN_W){if(s.dir.includes('w'))x-=MIN_W-w;w=MIN_W}if(h<MIN_H){if(s.dir.includes('n'))y-=MIN_H-h;h=MIN_H}if(x<8){if(s.dir.includes('w'))w+=x-8;x=8}if(y<68){if(s.dir.includes('n'))h+=y-68;y=68}w=Math.min(w,innerWidth-x-8);h=Math.min(h,innerHeight-y-8);Object.assign(win.style,{left:`${x}px`,top:`${y}px`,width:`${w}px`,height:`${h}px`});requestAnimationFrame(updatePaperScale)});
  handle.addEventListener('pointerup',e=>{if(resizeState?.id===e.pointerId){resizeState=null;persistUI()}})
 });
 window.addEventListener('resize',()=>{applyGeometry();updatePaperScale();positionFab()});
 const ai=$('#limad-ai-fab');if(ai&&window.ResizeObserver)new ResizeObserver(positionFab).observe(ai);
 countWords();syncLabels();requestAnimationFrame(updatePaperScale);if(window.ResizeObserver)new ResizeObserver(()=>updatePaperScale()).observe(editor);
}
function installTopButton(){
 const bar=$('.app-bar');if(!bar||$('#study-writer-button'))return false;
 const b=document.createElement('button');b.id='study-writer-button';b.className='icon-button writer-launch';b.title='Dokument und Vorbereitung';b.setAttribute('aria-label','Dokument und Vorbereitung');b.innerHTML=icon('document',20);b.onclick=()=>updateMode('open');bar.insertBefore(b,$('#global-search'));return true
}
function init(){
 if(document.body.classList.contains('writer-standalone')){const root=$('#writer-standalone-root');root.innerHTML=buildMarkup();win=$('#study-writer-window');dock=$('#study-writer-dock');fab=$('#study-writer-fab');bindUI();uiState.mode='open';uiState.maximized=true;updateMode('open');return}
 document.body.insertAdjacentHTML('beforeend',buildMarkup());win=$('#study-writer-window');dock=$('#study-writer-dock');fab=$('#study-writer-fab');bindUI();updateMode(uiState.mode||'collapsed');if(!installTopButton()){const observer=new MutationObserver(()=>{if(installTopButton())observer.disconnect()});observer.observe(document.documentElement,{childList:true,subtree:true})}
}
document.readyState==='loading'?document.addEventListener('DOMContentLoaded',init):init();
})();

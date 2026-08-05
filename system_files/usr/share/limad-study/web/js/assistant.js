(()=>{
'use strict';
const state={open:false,projectId:'',projects:[],contexts:[],configured:false};
const esc=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[char]));
const q=selector=>document.querySelector(selector);
async function api(path,options={}){
 const headers={...(options.headers||{})};
 if(options.body&&typeof options.body!=='string'){headers['Content-Type']='application/json';options.body=JSON.stringify(options.body)}
 const response=await fetch(path,{...options,headers});
 const data=await response.json();
 if(!response.ok||data.ok===false)throw new Error(data.error||`HTTP ${response.status}`);
 return data;
}
function mount(){
 if(document.getElementById('limad-ai-fab'))return;
 document.body.insertAdjacentHTML('beforeend',`<button id="limad-ai-fab" class="ai-fab">✦ KI-Assistent</button><section id="limad-ai-window" class="ai-window" hidden><div class="ai-head"><span class="ai-logo">✦</span><span class="ai-title"><strong>LiMaD KI-Assistent</strong><small>Textchat · keine freie Internetsuche</small></span><button class="ai-icon" data-ai-settings title="Einstellungen">⚙</button><button class="ai-icon" data-ai-close title="Schließen">×</button></div><div class="ai-toolbar"><select id="ai-project"></select><button class="ai-btn secondary" id="ai-new-project">＋ Projekt</button></div><div id="ai-status" class="ai-status"></div><div id="ai-messages" class="ai-messages"></div><div id="ai-context" class="ai-context"></div><div class="ai-input"><textarea id="ai-text" placeholder="Frage, Disposition oder Arbeitsauftrag eingeben …"></textarea><div class="ai-actions"><button class="ai-btn secondary" id="ai-selection">Markierten Text</button><button class="ai-btn secondary" id="ai-view">Aktuelle Ansicht</button><button class="ai-btn ai-send" id="ai-send">Senden</button></div><div class="ai-note">Es werden nur deine Eingaben und bewusst hinzugefügter Study-Kontext an Gemini übertragen.</div></div><div id="ai-settings" class="ai-settings" hidden><h3>Gemini-Einstellungen</h3><p>Der API-Key wird lokal im System-Schlüsselbund gespeichert; falls dieser nicht verfügbar ist, in einer nur für deinen Benutzer lesbaren Datei.</p><label>API-Key</label><input id="ai-key" type="password" placeholder="Gemini API-Key"><label>Modell</label><input id="ai-model" value="gemini-2.5-flash"><div class="ai-actions"><button class="ai-btn secondary" id="ai-settings-close">Abbrechen</button><button class="ai-btn ai-send" id="ai-settings-save">Speichern</button></div></div><div id="ai-project-dialog" class="ai-project-dialog" hidden><form class="ai-project-card"><div class="ai-project-symbol">✦</div><h3>Neues KI-Projekt</h3><p>Vergib einen Namen für deine Ausarbeitung oder dein Studienthema.</p><label for="ai-project-name">Projektname</label><input id="ai-project-name" maxlength="120" value="Neue Ausarbeitung" autocomplete="off"><div class="ai-actions"><button type="button" class="ai-btn secondary" id="ai-project-cancel">Abbrechen</button><button type="submit" class="ai-btn ai-send">Projekt anlegen</button></div></form></div></section>`);
 bind();restore();loadState().catch(showError);
}
function bind(){
 const fab=q('#limad-ai-fab'),win=q('#limad-ai-window');
 fab.onclick=()=>toggle(true);
 q('[data-ai-close]').onclick=()=>toggle(false);
 q('[data-ai-settings]').onclick=()=>q('#ai-settings').hidden=false;
 q('#ai-settings-close').onclick=()=>q('#ai-settings').hidden=true;
 q('#ai-settings-save').onclick=saveSettings;
 q('#ai-new-project').onclick=()=>newProject(false);
 q('#ai-project').onchange=event=>{state.projectId=event.target.value;localStorage.setItem('limad.ai.project',state.projectId);loadMessages()};
 q('#ai-send').onclick=send;
 q('#ai-text').addEventListener('keydown',event=>{if(event.key==='Enter'&&(event.ctrlKey||event.metaKey)){event.preventDefault();send()}});
 q('#ai-selection').onclick=()=>addContext('Markierter Text',String(getSelection()?.toString()||'').trim());
 q('#ai-view').onclick=()=>{const main=document.getElementById('main-content');addContext(document.title||'Aktuelle Ansicht',String(main?.innerText||'').trim().slice(0,12000))};
 drag(win,q('.ai-head'));window.addEventListener('beforeunload',persist);
}
function toggle(open){state.open=open;q('#limad-ai-window').hidden=!open;persist()}
function persist(){const win=q('#limad-ai-window');if(!win)return;localStorage.setItem('limad.ai.window',JSON.stringify({open:state.open,right:win.style.right,bottom:win.style.bottom,left:win.style.left,top:win.style.top,width:win.style.width,height:win.style.height}))}
function restore(){try{const value=JSON.parse(localStorage.getItem('limad.ai.window')||'{}');state.open=!!value.open;const win=q('#limad-ai-window');for(const key of ['right','bottom','left','top','width','height'])if(value[key])win.style[key]=value[key];win.hidden=!state.open}catch{}}
function drag(element,handle){let point=null;handle.addEventListener('pointerdown',event=>{if(event.target.closest('button'))return;point={x:event.clientX,y:event.clientY,l:element.offsetLeft,t:element.offsetTop};handle.setPointerCapture(event.pointerId)});handle.addEventListener('pointermove',event=>{if(!point)return;element.style.left=Math.max(0,point.l+event.clientX-point.x)+'px';element.style.top=Math.max(0,point.t+event.clientY-point.y)+'px';element.style.right='auto';element.style.bottom='auto'});handle.addEventListener('pointerup',()=>{point=null;persist()})}
async function loadState(){
 const data=await api('/api/assistant/state');state.projects=data.projects||[];state.configured=!!data.state?.configured;q('#ai-model').value=data.state?.model||'gemini-2.5-flash';renderProjects();
 if(!state.projectId)state.projectId=localStorage.getItem('limad.ai.project')||state.projects[0]?.id||'';
 if(!state.projectId){toggle(true);await newProject(true)}else{q('#ai-project').value=state.projectId;await loadMessages()}
 setStatus(state.configured?'Gemini ist eingerichtet.':'Gemini API-Key fehlt. Öffne ⚙ Einstellungen.',!state.configured);
}
function renderProjects(){q('#ai-project').innerHTML=state.projects.length?state.projects.map(project=>`<option value="${esc(project.id)}">${esc(project.title)}</option>`).join(''):'<option value="">Noch kein Projekt</option>'}
function askProjectTitle(firstSetup=false){
 return new Promise(resolve=>{
  const dialog=q('#ai-project-dialog'),form=dialog.querySelector('form'),input=q('#ai-project-name'),cancel=q('#ai-project-cancel');
  dialog.hidden=false;input.value=firstSetup?'Meine Ausarbeitung':'Neue Ausarbeitung';requestAnimationFrame(()=>{input.focus();input.select()});
  const close=value=>{dialog.hidden=true;form.onsubmit=null;cancel.onclick=null;resolve(value)};
  form.onsubmit=event=>{event.preventDefault();close(input.value.trim()||'Neue Ausarbeitung')};
  cancel.onclick=()=>close(null);
 });
}
async function newProject(firstSetup=false){
 const title=await askProjectTitle(firstSetup);if(title===null){if(!state.projectId)setStatus('Noch kein KI-Projekt angelegt.',true);return}
 const data=await api('/api/assistant/projects',{method:'POST',body:{title}});state.projects.unshift(data.project);state.projectId=data.project.id;localStorage.setItem('limad.ai.project',state.projectId);renderProjects();q('#ai-project').value=state.projectId;renderMessages([]);
}
async function loadMessages(){if(!state.projectId)return;const data=await api(`/api/assistant/projects/${state.projectId}/messages`);renderMessages(data.messages||[])}
function renderMessages(items){const box=q('#ai-messages');box.innerHTML=items.length?items.map(message=>`<div class="ai-message ${message.role==='assistant'?'assistant':'user'}">${esc(message.content)}</div>`).join(''):`<div class="ai-empty"><strong>Bereit für deine Ausarbeitung</strong><p>Füge eine Disposition ein, stelle eine Frage oder gib markierten Study-Text als Kontext frei.</p></div>`;box.scrollTop=box.scrollHeight}
function addContext(label,text){if(!text){setStatus('Kein Text ausgewählt.',true);return}state.contexts.push({label,text:text.slice(0,20000)});renderContexts();setStatus(`${label} wurde für die nächste Nachricht hinzugefügt.`)}
function renderContexts(){q('#ai-context').innerHTML=state.contexts.map((context,index)=>`<span class="ai-chip">${esc(context.label)} <button data-remove-context="${index}">×</button></span>`).join('');document.querySelectorAll('[data-remove-context]').forEach(button=>button.onclick=()=>{state.contexts.splice(Number(button.dataset.removeContext),1);renderContexts()})}
async function send(){const input=q('#ai-text'),content=input.value.trim();if(!state.projectId){await newProject(false);if(!state.projectId)return}if(!content)return;const button=q('#ai-send');button.disabled=true;setStatus('Gemini erstellt die Antwort …');try{await api(`/api/assistant/projects/${state.projectId}/messages`,{method:'POST',body:{content,context:state.contexts}});input.value='';state.contexts=[];renderContexts();await loadMessages();setStatus('Antwort abgeschlossen.')}catch(error){showError(error)}finally{button.disabled=false}}
async function saveSettings(){const key=q('#ai-key').value.trim(),model=q('#ai-model').value.trim();const body={model};if(key)body.api_key=key;try{const data=await api('/api/assistant/settings',{method:'POST',body});state.configured=!!data.state?.configured;q('#ai-key').value='';q('#ai-settings').hidden=true;setStatus(state.configured?'Gemini-Einstellungen gespeichert.':'Kein API-Key gespeichert.',!state.configured)}catch(error){showError(error)}}
function setStatus(text,bad=false){const status=q('#ai-status');status.textContent=text;status.classList.toggle('bad',bad)}
function showError(error){setStatus(error?.message||String(error),true)}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();
})();

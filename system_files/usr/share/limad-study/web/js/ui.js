import{icon}from'./icons.js';
export const esc=value=>String(value??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
export const formatBytes=value=>{const n=Number(value||0);if(!n)return'0 B';const units=['B','KB','MB','GB'];const i=Math.min(Math.floor(Math.log(n)/Math.log(1024)),3);return`${(n/1024**i).toFixed(i?1:0)} ${units[i]}`};
export const publicationCover=item=>item.cover_url||item.installed_cover||'';
export function empty(title,text,action=''){return`<div class="empty-state">${icon('publications',42)}<h3>${esc(title)}</h3><p>${esc(text)}</p>${action}</div>`}
export function skeleton(count=6){return`<div class="skeleton-grid">${Array.from({length:count},()=>'<div class="skeleton-card"><i></i><b></b><span></span></div>').join('')}</div>`}
export function publicationCard(item,{catalog=false,compact=false}={}){
 const id=catalog?item.catalog_id:item.id;const cover=publicationCover(item);const title=item.title||item.short_title||'Publikation';const type=item.publication_type||item.short_title||item.language_name||'';
 return`<article class="publication-card ${compact?'compact':''}" data-${catalog?'catalog':'publication'}-id="${esc(id)}">
  <button class="cover-button" data-action="${catalog?'catalog-open':'publication-open'}" data-id="${esc(id)}">
   ${cover?`<img src="${esc(cover)}" alt="">`:`<span class="cover-placeholder">${icon(item.publication_type_id===1?'bible':'publications',36)}</span>`}
   ${catalog&&!item.installed?'<span class="new-pill">Neu</span>':''}
  </button>
  <div class="publication-card-body"><strong>${esc(title)}</strong><small>${esc(type)}</small></div>
  ${catalog?'':`<button class="card-star ${item.favorite?'active':''}" data-action="favorite" data-id="${esc(id)}" data-value="${item.favorite?0:1}" aria-label="Favorit">${icon('star',19)}</button>`}
 </article>`}
export function modal({title,body,actions='',wide=false,id='dialog'}){
 return`<div class="modal-backdrop" data-close-modal><section class="modal ${wide?'wide':''}" id="${id}" role="dialog" aria-modal="true"><header><h2>${esc(title)}</h2><button class="icon-button" data-close-modal>${icon('close')}</button></header><div class="modal-body">${body}</div>${actions?`<footer>${actions}</footer>`:''}</section></div>`
}
export function toast(message,type='ok'){
 const root=document.querySelector('#toast-root');const node=document.createElement('div');node.className=`toast ${type}`;node.innerHTML=`${icon(type==='error'?'warning':'check',19)}<span>${esc(message)}</span>`;root.append(node);setTimeout(()=>node.remove(),4200)
}

export async function request(path,options={}){
 const response=await fetch(path,{headers:{'Content-Type':'application/json',...(options.headers||{})},...options});
 const type=response.headers.get('content-type')||'';
 const payload=type.includes('application/json')?await response.json():await response.text();
 if(!response.ok)throw new Error(payload?.error||payload||`HTTP ${response.status}`);
 return payload;
}
export const get=path=>request(path);
export const post=(path,data={})=>request(path,{method:'POST',body:JSON.stringify(data)});
export const del=path=>request(path,{method:'DELETE'});
export async function upload(path,file,onProgress){
 return new Promise((resolve,reject)=>{
  const xhr=new XMLHttpRequest();const form=new FormData();form.append('file',file,file.name);
  xhr.open('POST',path);xhr.responseType='json';
  xhr.upload.onprogress=e=>{if(e.lengthComputable&&onProgress)onProgress(Math.round(e.loaded/e.total*100))};
  xhr.onload=()=>xhr.status>=200&&xhr.status<300?resolve(xhr.response):reject(new Error(xhr.response?.error||`HTTP ${xhr.status}`));
  xhr.onerror=()=>reject(new Error('Upload fehlgeschlagen.'));xhr.send(form);
 });
}

from __future__ import annotations
import html,json,re
from pathlib import Path
from ..database import DB,Database
from ..utils import escape
from ..study.userdata import document_marks, input_fields_for_document

READER_CSS=r'''
:root{
 --paper:#fff;--paper-2:#f7f7f8;--paper-3:#efedf2;--ink:#242329;--muted:#6b6a72;--line:#dedce3;
 --accent:#5d4b99;--accent-soft:#f3f0fa;--input:#fff;--input-hover:#faf9fc;--danger-bg:#fff1f1;--danger-text:#8d2e2e;
 --font-scale:1;color-scheme:light
}
html[data-theme=dark]{
 --paper:#17161b;--paper-2:#201e25;--paper-3:#29262f;--ink:#eceaf1;--muted:#aaa5b2;--line:#3b3743;
 --accent:#b69aef;--accent-soft:#2b243a;--input:#211f26;--input-hover:#292630;--danger-bg:#402327;--danger-text:#ffadb6;
 color-scheme:dark
}
*{box-sizing:border-box}
html{width:100%;max-width:100%;min-width:0;overflow-x:hidden;background:var(--paper);color:var(--ink);font-family:"Noto Sans","Source Sans 3",system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;line-height:1.58;scroll-behavior:auto;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
body{width:100%;max-width:880px;min-width:0;margin:0 auto;padding:30px clamp(18px,4.2vw,48px) 108px;overflow-x:hidden;background:var(--paper);color:var(--ink);font-size:calc(15.5px * var(--font-scale));font-weight:400;letter-spacing:.002em;overflow-wrap:normal;word-break:normal;hyphens:auto}
article,section,div,p,li,blockquote,table,figure,form,fieldset,main,header,footer,aside,nav,ul,ol{min-width:0;max-width:100%}
h1,h2,h3,h4,.st,.ss,.s1,.s2,.s3,.s4,.s5{color:var(--ink);line-height:1.28;letter-spacing:-.008em;text-wrap:balance}
h1,.st{font-size:1.68rem;font-weight:700;margin:.2em 0 .66em}
h2,.ss{font-size:1.24rem;font-weight:700;margin:1.38em 0 .5em}
h3,.s1{font-size:1.07rem;font-weight:680;margin:1.14em 0 .42em}
h4,.s2,.s3,.s4,.s5{font-size:1rem;font-weight:650;margin:1.02em 0 .36em}
p,.p{margin:.58em 0}.sb,.sb1,.sb2,.sb3{font-weight:650}.si{font-style:italic}.sl,.sl1,.sl2,.sl3{margin:.36em 0;padding-inline-start:1.35em}.su{font-size:.86em;vertical-align:super}.sk,.xt{font-weight:600;color:var(--accent)}.b{font-weight:700}.it{font-style:italic}
ul,ol{padding-inline-start:1.45em;margin:.55em 0}li{margin:.22em 0}
a{color:var(--accent);text-decoration:none;text-underline-offset:.14em}a:hover{text-decoration:underline}
hr{height:1px;border:0;background:var(--line);margin:1.25em 0}
details{border:1px solid var(--line);border-radius:7px;background:var(--paper-2);padding:.62em .78em;margin:.8em 0}summary{color:var(--ink);font-weight:650;cursor:pointer}
figure,.figure{position:relative;margin:1.15em auto;text-align:center;max-width:100%}
img,svg,video{max-width:100%;height:auto}
figure img,.figure img,.limad-reader-image{display:block;width:auto;max-width:100%;max-height:none;margin:0 auto;border-radius:3px;object-fit:contain;cursor:zoom-in}
figure svg,.figure svg,[class*="timeline"] svg,[class*="Timeline"] svg,.chart svg,.diagram svg{display:block;max-width:100%;height:auto;margin:auto;background:#fff;border-radius:5px;padding:.35em}
.limad-inline-media-host img[hidden]{display:none!important}
video{display:block;width:100%;background:#07080b;border-radius:8px}audio{width:100%}
figcaption,.figcaption,.caption{color:var(--muted);font-size:.84rem;line-height:1.38;margin:.42rem auto 0;max-width:78ch}
.pageNum,.pageNumRef{display:none!important}
table{width:100%;border-collapse:collapse;margin:1em 0;font-size:.92em}th,td{padding:.52em .62em;border:1px solid var(--line);vertical-align:top;color:var(--ink)}th{background:var(--accent-soft);font-weight:720}
blockquote{margin:.9em 0;padding:.66em .9em;border-inline-start:3px solid var(--accent);background:var(--accent-soft);color:var(--ink)}
.boxContent,.boxSupplement,.box,.boxTtl{border-inline-start:3px solid var(--accent);background:var(--accent-soft);color:var(--ink);padding:10px 13px;border-radius:4px;margin:.95em 0}
.studyQuestion{border-inline-start:3px solid var(--accent);background:var(--accent-soft);color:var(--ink);padding:.68em .82em;border-radius:4px;margin:.95em 0 .42em}
.groupTOC{display:grid;gap:.12rem}.groupTOC p{margin:0;padding:.32rem 0;border-bottom:1px solid var(--line)}
[class*="timeline"],[class*="Timeline"],.chart,.diagram{max-width:100%;overflow:auto}.themeScrp,.theme-scripture{font-weight:650;color:var(--accent)}
textarea,input[type="text"],input:not([type]),[contenteditable="true"]{display:block;width:100%;max-width:100%;min-height:3.5em;margin:.42em 0 .9em;padding:.68em .75em;border:1px solid var(--line);border-radius:7px;background:var(--input);color:var(--ink);caret-color:var(--accent);font:inherit;line-height:1.45;resize:vertical;outline:none}
textarea:hover,input[type="text"]:hover,input:not([type]):hover,[contenteditable="true"]:hover{background:var(--input-hover)}
textarea:focus,input[type="text"]:focus,input:not([type]):focus,[contenteditable="true"]:focus{border-color:var(--accent);box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 18%,transparent)}
textarea::placeholder,input::placeholder{color:var(--muted);opacity:.82}
input[type="checkbox"],input[type="radio"]{accent-color:var(--accent)}
[data-pid],p[id^="p"]{position:relative}.limad-note-pin{display:inline-flex;width:19px;height:19px;margin-left:6px;align-items:center;justify-content:center;border-radius:50%;background:var(--accent);color:#fff;font-size:11px;vertical-align:middle;cursor:pointer}
[data-limad-mark]{cursor:pointer;box-decoration-break:clone;-webkit-box-decoration-break:clone;padding:0;border-radius:2px;background-image:linear-gradient(176deg,transparent 5%,var(--marker) 9%,var(--marker) 88%,transparent 94%)}
[data-limad-mark="0"]{--marker:rgba(255,225,92,.72)}[data-limad-mark="1"]{--marker:rgba(118,220,168,.58)}[data-limad-mark="2"]{--marker:rgba(112,177,255,.5)}[data-limad-mark="3"]{--marker:rgba(246,149,193,.5)}[data-limad-mark="4"]{--marker:rgba(181,143,242,.48)}[data-limad-mark="5"]{--marker:rgba(255,166,91,.56)}

.reader-profile-meeting-workbook{--accent:#0b7385;--accent-soft:#edf7f8}
.reader-profile-watchtower-study{--accent:#52743f;--accent-soft:#eff5ec}
.reader-profile-insight{--accent:#966021;--accent-soft:#faf0e4}
.reader-profile-bible{--accent:#71549e;--accent-soft:#f2edf8}
html[data-theme=dark] .reader-profile-meeting-workbook{--accent:#65cbd7;--accent-soft:#17343a}
html[data-theme=dark] .reader-profile-watchtower-study{--accent:#a8d08d;--accent-soft:#263421}
html[data-theme=dark] .reader-profile-insight{--accent:#e2ae6a;--accent-soft:#3b2c1c}
html[data-theme=dark] .reader-profile-bible{--accent:#c0a5ef;--accent-soft:#302743}
.reader-profile-meeting-workbook .st,.reader-profile-meeting-workbook .ss,.reader-profile-meeting-workbook h1,.reader-profile-meeting-workbook h2,
.reader-profile-watchtower-study .st,.reader-profile-watchtower-study .ss,.reader-profile-watchtower-study h1,.reader-profile-watchtower-study h2,
.reader-profile-insight .st,.reader-profile-insight .ss,.reader-profile-insight h1,.reader-profile-insight h2{color:var(--accent)}
.reader-profile-meeting-workbook .limad-date-strip{background:var(--accent);color:#fff;padding:.42em .7em;margin:.35em 0 .85em;font-weight:760}
.reader-profile-meeting-workbook .s1,.reader-profile-meeting-workbook .s2{border-bottom:1px solid color-mix(in srgb,var(--accent) 36%,transparent);padding-bottom:.25em}
/* Wachtturm-Fragen sind häufiger und enthalten Antwortfelder. Darum kompakter als allgemeine Infoboxen. */
.reader-profile-watchtower-study .studyQuestion{background:transparent;border:0;border-inline-start:2px solid var(--accent);border-radius:0;padding:.16em 0 .16em .72em;margin:1.18em 0 .34em;color:var(--muted);font-size:.84em;font-weight:400;line-height:1.48;letter-spacing:0}
.reader-profile-watchtower-study .studyQuestion :is(.limad-question-number,.questionNumber,.question-number,.questionNum,.question-num,strong:first-child,b:first-child){color:var(--ink);font-weight:760}
.reader-profile-watchtower-study .studyQuestion .limad-question-number{display:inline;color:var(--ink);font-weight:760;margin-inline-end:.28em}
.reader-profile-watchtower-study :is(textarea,input[type="text"],input:not([type]),[contenteditable="true"]){min-height:3.35em;margin:.28em 0 .94em;background:var(--paper);border-color:color-mix(in srgb,var(--muted) 48%,var(--line));font-size:.93em}
.reader-profile-watchtower-study :is(.answer,.answerField,.answer-field,.inputField,.input-field,[class*="answerField"],[class*="inputField"]){max-width:100%;min-height:0!important;height:auto!important;background:transparent!important;color:var(--ink)!important}
.reader-profile-watchtower-study :is(article,section,div,form,fieldset,ul,ol,.studyQuestion,.boxContent,.boxSupplement,.box,.boxTtl,[style*="width"]){min-width:0!important;max-width:100%!important}
.reader-profile-watchtower-study :is(textarea,input,[contenteditable="true"]){width:100%!important;max-width:100%!important}

.limad-inline-media-host{position:relative}.limad-inline-media-play{position:absolute;inset:0;border:0;background:transparent;cursor:pointer;display:grid;place-items:center;z-index:4}.limad-inline-media-play::before{content:'▶';display:grid;place-items:center;width:64px;height:64px;border-radius:50%;background:rgba(18,18,22,.76);color:#fff;font-size:26px;padding-left:4px;box-shadow:0 4px 18px #0005}.limad-inline-media-play:hover::before{transform:scale(1.05);background:rgba(18,18,22,.88)}
.limad-inline-media-status{margin:.55em 0;padding:.65em .8em;border-radius:6px;background:var(--accent-soft);color:var(--muted)}.limad-inline-media-box{margin:.8em 0}.limad-inline-media-player{width:100%;max-height:72vh}.limad-inline-media-actions{display:flex;gap:.55rem;flex-wrap:wrap;justify-content:center;margin:.55rem 0}.limad-inline-media-actions button,.limad-inline-media-actions a{font:inherit;border:1px solid var(--line);border-radius:999px;background:var(--paper);color:var(--ink);padding:.42rem .78rem;cursor:pointer;text-decoration:none}.limad-inline-media-error{padding:.65em .8em;border-radius:6px;background:var(--danger-bg);color:var(--danger-text)}
.limad-image-badge{position:absolute;right:8px;bottom:8px;border:0;border-radius:999px;background:rgba(20,20,24,.76);color:#fff;padding:6px 9px;font-size:11px;pointer-events:none}
.limad-popover{position:fixed;z-index:50;max-width:420px;max-height:55vh;overflow:auto;background:var(--paper-2);color:var(--ink);border:1px solid var(--line);border-radius:14px;padding:16px 18px;box-shadow:0 18px 55px rgba(20,15,30,.35)}.limad-popover button{float:right;border:0;background:none;color:var(--ink);font-size:20px;cursor:pointer}
.limad-selection-menu{position:fixed;z-index:60;background:#25222c;color:white;border-radius:10px;padding:5px;box-shadow:0 10px 30px #0003;display:flex;gap:3px}.limad-selection-menu button{border:0;border-radius:7px;padding:7px 10px;background:transparent;color:white;cursor:pointer}.limad-selection-menu button:hover{background:#ffffff20}.limad-selection-menu .danger{color:#ff9b9b}.limad-selection-menu button[data-c]{width:30px;height:30px;padding:0;border:2px solid #ffffff55;border-radius:50%;font-size:0}.limad-selection-menu button[data-c="0"]{background:#ffe15c}.limad-selection-menu button[data-c="1"]{background:#76dca8}.limad-selection-menu button[data-c="2"]{background:#70b1ff}.limad-selection-menu button[data-c="3"]{background:#f695c1}.limad-selection-menu button[data-c="4"]{background:#b58ff2}.limad-selection-menu button[data-c="5"]{background:#ffa65b}
@media(max-width:700px){body{padding:22px 18px 82px;font-size:calc(15px * var(--font-scale))}h1,.st{font-size:1.52rem}.limad-inline-media-play::before{width:56px;height:56px}}
'''

INLINE_MEDIA_JS=r'''

const LIMAD_LANGUAGE_INDEX=__LANGUAGE_INDEX__;
const LIMAD_PUBLICATION_ID=__PUBLICATION_ID__;
const LIMAD_DOCUMENT_ID=__DOCUMENT_ID__;
function limadDecodeMediaValue(value){let text=String(value||'').replace(/&amp;/gi,'&');for(let i=0;i<4;i++){try{const next=decodeURIComponent(text);if(next===text)break;text=next}catch{break}}return text}
function limadMediaNaturalKey(value){return (limadDecodeMediaValue(value).match(/pub-[A-Za-z0-9_-]+_(?:VIDEO|AUDIO)/i)||[])[0]||''}
function limadMediaValue(anchor){
 const preferred=['href','xlink:href','data-lank','data-natural-key','data-naturalkey','data-media-key','data-mediakey','data-video','data-audio','data-media','data-item','data-link','data-href'];
 const values=[];for(const name of preferred){const value=anchor?.getAttribute?.(name);if(value)values.push(value)}
 for(const attr of [...(anchor?.attributes||[])]){if(/(?:lank|natural|media|video|audio|item|link|href)/i.test(attr.name)&&attr.value)values.push(attr.value)}
 for(const value of Object.values(anchor?.dataset||{})){if(value)values.push(value)}
 const text=(anchor?.textContent||anchor?.getAttribute?.('aria-label')||'').trim();if(text)values.push(text);
 return [...new Set(values.map(limadDecodeMediaValue).filter(Boolean))].join(' ')
}
function limadIsMediaAnchor(anchor){const value=limadMediaValue(anchor);return !!limadMediaNaturalKey(value)||/webpub(?:vid|aud):/i.test(value)||/(?:jwpub|jwlibrary):\/\/(?:v|a|video|audio|m)(?:\/|\?|$)/i.test(value)||/[?&](?:lank|item)=pub-[A-Za-z0-9_-]+_(?:VIDEO|AUDIO)/i.test(value)||/\.(?:mp4|m4v|webm|mov|mp3|m4a|aac|ogg|opus)(?:[?#\s]|$)/i.test(value)}
function limadNearestMediaFigure(anchor){
 const own=anchor.closest('figure,.figure');if(own?.querySelector('img'))return own;
 const section=anchor.closest('section,article,[data-pid],li')||anchor.parentElement;
 if(section){const figures=[...section.querySelectorAll('figure,.figure')].filter(node=>node.querySelector('img'));const before=figures.filter(node=>node.compareDocumentPosition(anchor)&Node.DOCUMENT_POSITION_FOLLOWING);if(before.length)return before[before.length-1];if(figures.length===1)return figures[0]}
 let node=anchor.previousElementSibling;for(let i=0;i<9&&node;i++,node=node.previousElementSibling){if(node.matches?.('figure,.figure')&&node.querySelector('img'))return node;const nested=node.querySelector?.('figure,.figure');if(nested?.querySelector('img'))return nested}
 return null;
}
function limadMediaSources(media){
 const sources=(media?.sources||[]).filter(item=>item?.url).map(item=>({...item}));if(!sources.length&&media?.url)sources.push({url:media.url,mime_type:media.mime_type||'',download_url:media.download_url||'',height:0});
 const score=item=>{const mime=String(item.mime_type||'').toLowerCase(),height=Number(item.height||0);return (mime.includes('mp4')||mime.includes('mpeg')?0:5000)+(height?Math.abs(height-720):3000)};
 return sources.sort((a,b)=>score(a)-score(b)).slice(0,4);
}
function limadOnlineAction(url,label='Auf jw.org öffnen'){if(!/^https?:/i.test(String(url||'')))return null;const link=document.createElement('a');link.href=url;link.target='_blank';link.rel='noreferrer';link.textContent=label;return link}
function limadTryMediaSource(player,source,timeoutMs=10000){return new Promise((resolve,reject)=>{let finished=false;const done=(ok,error)=>{if(finished)return;finished=true;clearTimeout(timer);player.removeEventListener('loadedmetadata',ready);player.removeEventListener('canplay',ready);player.removeEventListener('error',failed);ok?resolve(source):reject(error||new Error('Quelle konnte nicht geladen werden.'))};const ready=()=>done(true);const failed=()=>done(false,new Error(`Quelle ${source.quality||''} ist nicht abspielbar.`));const timer=setTimeout(()=>done(false,new Error(`Zeitüberschreitung bei ${source.quality||'Videoquelle'}.`)),timeoutMs);player.addEventListener('loadedmetadata',ready,{once:true});player.addEventListener('canplay',ready,{once:true});player.addEventListener('error',failed,{once:true});player.src=source.url;player.load()})}
async function limadPlayInlineMedia(anchor,event){
 event?.preventDefault();event?.stopPropagation();event?.stopImmediatePropagation();
 const reference=limadMediaValue(anchor),href=anchor.getAttribute('href')||'',label=(anchor.textContent||anchor.getAttribute('aria-label')||'Video').trim();let fallbackUrl=href;
 const figure=limadNearestMediaFigure(anchor),image=figure?.querySelector('img')||anchor.querySelector('img'),host=figure||anchor.parentElement;if(!host)return;
 host.classList.add('limad-inline-media-host');host.querySelector('.limad-inline-media-play')?.remove();host.querySelector('.limad-inline-media-status')?.remove();host.querySelector('.limad-inline-media-error')?.remove();
 const status=document.createElement('div');status.className='limad-inline-media-status';status.textContent='Aktuelle Mediendatei wird bei JW.ORG geprüft …';host.append(status);
 try{
  const params=new URLSearchParams({link:reference||href,label,language:String(LIMAD_LANGUAGE_INDEX),publication_id:String(LIMAD_PUBLICATION_ID||''),document_id:String(LIMAD_DOCUMENT_ID||'')});
  const response=await fetch(`/api/resolve?${params}`);const result=await response.json();fallbackUrl=result.external||href;if(!response.ok)throw new Error(result.error||response.statusText);if(!result.resolved||!result.media)throw new Error(result.missing_message||'Keine abspielbare Datei gefunden.');
  const sources=limadMediaSources(result.media);if(!sources.length)throw new Error('Keine abspielbare Datei gefunden.');
  const box=document.createElement('div');box.className='limad-inline-media-box';box.hidden=true;const player=document.createElement(result.kind==='audio'?'audio':'video');player.className='limad-inline-media-player';player.controls=true;player.preload='metadata';player.setAttribute('playsinline','');if(player.tagName==='VIDEO'&&(result.media.image||image?.currentSrc||image?.src))player.poster=result.media.image||image.currentSrc||image.src;box.append(player);
  const actions=document.createElement('div');actions.className='limad-inline-media-actions';const close=document.createElement('button');close.type='button';close.textContent='Bild anzeigen';close.onclick=()=>{player.pause();box.remove();if(image)image.hidden=false;limadDecorateMediaLinks()};actions.append(close);
  const original=sources[0].download_url||result.media.download_url||'';if(original){const download=document.createElement('a');download.href=original;download.target='_blank';download.rel='noreferrer';download.textContent='Herunterladen';actions.append(download)}
  const online=limadOnlineAction(result.external);if(online)actions.append(online);box.append(actions);const caption=figure?.querySelector('figcaption,.figcaption,.caption');if(caption)figure.insertBefore(box,caption);else host.append(box);
  let loaded=null,lastError=null;for(const source of sources){status.textContent=`Videoquelle ${source.quality||''} wird geladen …`;try{loaded=await limadTryMediaSource(player,source);break}catch(error){lastError=error}}
  if(!loaded){box.remove();throw lastError||new Error('Keine der verfügbaren Videoqualitäten konnte geladen werden.')}
  status.remove();box.hidden=false;if(image)image.hidden=true;try{await player.play()}catch{}
 }catch(error){status.className='limad-inline-media-error';status.textContent=`Interne Wiedergabe nicht möglich: ${error.message}`;const online=limadOnlineAction(fallbackUrl);if(online){status.append(document.createTextNode(' '),online)}if(image)image.hidden=false;limadDecorateMediaLinks()}
}
function limadDecorateMediaLinks(){
 for(const anchor of document.querySelectorAll('a,[data-video],[data-audio],[data-lank],[data-natural-key],[data-media-key]')){
  if(!limadIsMediaAnchor(anchor))continue;anchor.dataset.limadInlineMedia='1';const figure=limadNearestMediaFigure(anchor),image=figure?.querySelector('img')||anchor.querySelector('img'),mediaHost=figure||anchor;if(!image||mediaHost.querySelector('.limad-inline-media-play'))continue;mediaHost.classList.add('limad-inline-media-host');const button=document.createElement('button');button.type='button';button.className='limad-inline-media-play';button.setAttribute('aria-label','Medium hier abspielen');button.title='Medium hier abspielen';button.onclick=event=>limadPlayInlineMedia(anchor,event);mediaHost.append(button);
 }
}
window.limadInlineMedia={isMediaAnchor:limadIsMediaAnchor,play:limadPlayInlineMedia};limadDecorateMediaLinks();
document.querySelectorAll('.st,.ss').forEach(node=>{if(/\d{1,2}[.]?\s+[A-Za-zÄÖÜäöüß]+\s*[–-]\s*\d{1,2}[.]?\s+[A-Za-zÄÖÜäöüß]+/u.test((node.textContent||'').trim()))node.classList.add('limad-date-strip')});

'''


def _attribute_map(value: str) -> dict[str, str]:
    result: dict[str, str] = {}
    pattern = r"([:\w-]+)\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>]+))"
    for match in re.finditer(pattern, value or ""):
        result[match.group(1).lower()] = html.unescape(match.group(2) or match.group(3) or match.group(4) or "")
    return result


def _expand_local_video_placeholders(markup: str, doc: dict, prefix: str, database: Database) -> str:
    if "data-video" not in markup.lower():
        return markup
    media = database.rows(
        "SELECT file_path,mime_type,label,caption,source_media_id FROM media "
        "WHERE publication_id=? AND document_source_id=? ORDER BY source_media_id",
        (doc["publication_id"], doc["source_document_id"]),
    )
    videos = [row for row in media if str(row.get("mime_type") or "").startswith("video/")]
    images = [row for row in media if str(row.get("mime_type") or "").startswith("image/")]
    video_index = 0
    content_root = Path(str(doc.get("content_dir") or "")).resolve()

    def local_file_exists(file_path: object) -> bool:
        value = str(file_path or "").strip().lstrip("/")
        if not value or not content_root.is_dir():
            return False
        try:
            target = (content_root / value).resolve()
            return target.is_relative_to(content_root) and target.is_file()
        except (OSError, ValueError):
            return False

    def local_url(file_path: object) -> str:
        value = str(file_path or "").strip().lstrip("/")
        return prefix + escape(value) if value else ""

    def replace(match: re.Match) -> str:
        nonlocal video_index
        attrs_text = match.groupdict().get("attrs") or match.groupdict().get("attrs2") or ""
        attrs = _attribute_map(attrs_text)
        link = attrs.get("data-video", "")
        if not link:
            return match.group(0)
        selected = videos[min(video_index, len(videos) - 1)] if videos else None
        if selected:
            video_index += 1
        poster_name = attrs.get("data-image", "")
        poster = local_url(poster_name)
        if not poster and images:
            poster = local_url(images[min(max(video_index - 1, 0), len(images) - 1)].get("file_path"))
        label = str((selected or {}).get("label") or attrs.get("aria-label") or "Video")
        if selected and local_file_exists(selected.get("file_path")):
            source = local_url(selected.get("file_path"))
            mime = html.escape(str(selected.get("mime_type") or "video/mp4"), quote=True)
            poster_attr = f' poster="{html.escape(poster, quote=True)}"' if poster else ""
            return (
                f'<figure class="limad-native-video"><video controls preload="metadata" playsinline'
                f'{poster_attr} aria-label="{html.escape(label, quote=True)}" data-video="{html.escape(link, quote=True)}">'
                f'<source src="{html.escape(source, quote=True)}" type="{mime}"></video></figure>'
            )
        if poster:
            return (
                f'<figure class="limad-inline-media-host"><a href="{html.escape(link, quote=True)}" '
                f'data-video="{html.escape(link, quote=True)}" aria-label="{html.escape(label, quote=True)}">'
                f'<img src="{html.escape(poster, quote=True)}" alt="{html.escape(label, quote=True)}"></a></figure>'
            )
        return match.group(0)

    pattern = re.compile(r"<video\b(?P<attrs>[^>]*)>(?:\s*</video>)?|<video\b(?P<attrs2>[^>]*)/\s*>", re.I)
    return pattern.sub(replace, markup)

def _marks(db,doc):
    return document_marks(int(doc['id']), db)


def _notes(db,doc):
    local=db.rows("SELECT id,block_identifier,title,content FROM local_notes WHERE document_id=?",(doc['id'],))
    imported=db.rows('''SELECT CAST(n.note_id AS TEXT)||':'||n.backup_id AS id,n.block_identifier,n.title,n.content
        FROM notes n JOIN backup_resolution r ON r.backup_id=n.backup_id AND r.location_id=n.location_id
        WHERE r.document_row_id=? ORDER BY n.last_modified''',(doc['id'],))
    return imported+local

def render_document(document_id:int,database:Database=DB)->str:
    rows=database.rows('''SELECT d.*,p.title AS publication_title,p.content_dir,p.key_symbol,p.language_index FROM documents d JOIN publications p ON p.id=d.publication_id WHERE d.id=?''',(int(document_id),))
    if not rows: raise ValueError('Dokument wurde nicht gefunden.')
    doc=rows[0]; markup=doc['content_html'] or ''; prefix=f"/content/{escape(doc['publication_id'])}/"
    key=str(doc.get('key_symbol') or '').lower()
    label=' '.join(str(doc.get(name) or '') for name in ('publication_title','title','toc_title','class_name')).lower()
    reader_kind='general'
    if key.startswith('mwb') or 'leben und dienst' in label or 'meeting workbook' in label:
        reader_kind='meeting-workbook'
    elif key in {'w','ws'} or 'wachtturm' in label or 'watchtower' in label:
        reader_kind='watchtower-study'
    elif key == 'it' or 'einsichten' in label or 'insight' in label:
        reader_kind='insight'
    elif key.startswith(('nwt','rsg')) or 'bibel' in label or 'bible' in label:
        reader_kind='bible'
    markup=re.sub(r'''(src|poster)=(['"])jwpub-media://([^'"?#]+)(?:[^'"]*)\2''',lambda m:f'{m.group(1)}={m.group(2)}{prefix}{escape(m.group(3))}{m.group(2)}',markup,flags=re.I)
    markup=_expand_local_video_placeholders(markup,doc,prefix,database)
    marks=json.dumps(_marks(database,doc),ensure_ascii=False); notes=json.dumps(_notes(database,doc),ensure_ascii=False); input_fields=json.dumps(input_fields_for_document(int(document_id),database),ensure_ascii=False)
    footnotes=json.dumps(database.rows("SELECT source_footnote_id,footnote_index,content_html FROM footnotes WHERE publication_id=? AND document_source_id=?",(doc['publication_id'],doc['source_document_id'])),ensure_ascii=False)
    script=f'''
const DOC={int(document_id)},marks={marks},notes={notes},footnotes={footnotes},savedInputFields={input_fields};
const blockNodes=()=>[...document.querySelectorAll('[data-pid],p[id^="p"]')];
function textTokens(node){{const walker=document.createTreeWalker(node,NodeFilter.SHOW_TEXT,{{acceptNode:n=>n.parentElement?.closest('.limad-paragraph-number,.verse-number,.limad-note-pin,script,style')?NodeFilter.FILTER_REJECT:NodeFilter.FILTER_ACCEPT}});let items=[],index=0,current;while(current=walker.nextNode()){{const re=/\\S+/g;let m;while((m=re.exec(current.data)))items.push({{node:current,start:m.index,end:m.index+m[0].length,index:index++}})}}return items}}
function applyTokenMark(node,item){{const tokens=textTokens(node),start=item.start_token==null?0:Number(item.start_token),end=item.end_token==null?tokens.length-1:Number(item.end_token);const selected=tokens.filter(t=>t.index>=start&&t.index<=end);if(!selected.length)return;const groups=[];for(const token of selected){{let group=groups[groups.length-1];if(!group||group.node!==token.node){{group={{node:token.node,start:token.start,end:token.end}};groups.push(group)}}else group.end=token.end}}for(const group of groups.reverse()){{const range=document.createRange();range.setStart(group.node,group.start);range.setEnd(group.node,group.end);const span=document.createElement('span');span.dataset.limadMark=String((item.color_index||0)%6);span.dataset.markId=String(item.id||'');span.dataset.markBlock=String(item.block_identifier??'');span.dataset.markStart=String(item.start_token??'');span.dataset.markEnd=String(item.end_token??'');try{{range.surroundContents(span)}}catch{{}}}}}}
function markBlockNode(item){{const id=CSS.escape(String(item?.block_identifier??''));return document.querySelector(`.bible-verse[data-pid="${{id}}"]`)||document.querySelector(`[data-pid="${{id}}"],#p${{id}}`)}}
function unwrapMarkNode(node){{const parent=node?.parentNode;if(!parent)return;while(node.firstChild)parent.insertBefore(node.firstChild,node);node.remove();parent.normalize()}}
function markNodes(markId){{const id=CSS.escape(String(markId??''));return [...document.querySelectorAll(`[data-mark-id="${{id}}"]`)]}}
function preserveReaderViewport(item,mutator){{const x=scrollX,y=scrollY,node=markBlockNode(item),before=node?.getBoundingClientRect().top;mutator(node);const after=node?.getBoundingClientRect().top;const shift=Number.isFinite(before)&&Number.isFinite(after)?after-before:0;scrollTo({{left:x,top:y+shift,behavior:'auto'}})}}
function applyClientMark(item){{if(!item?.id)return;preserveReaderViewport(item,node=>{{for(const existing of markNodes(item.id))unwrapMarkNode(existing);if(node)applyTokenMark(node,item)}});getSelection()?.removeAllRanges()}}
function updateClientMark(item){{for(const node of markNodes(item?.id))node.dataset.limadMark=String((item.color_index||0)%6)}}
function deleteClientMark(markId){{const first=markNodes(markId)[0];const block=first?.closest('[data-pid],p[id^="p"]');const item={{block_identifier:block?.dataset?.pid||(block?.id||'').replace(/^p/,'')}};preserveReaderViewport(item,()=>{{for(const node of markNodes(markId))unwrapMarkNode(node)}})}}
for(const item of marks){{const id=CSS.escape(String(item.block_identifier??''));const node=document.querySelector(`.bible-verse[data-pid="${{id}}"]`)||document.querySelector(`[data-pid="${{id}}"],#p${{id}}`);if(node)applyTokenMark(node,item)}}
for(const item of notes){{const node=document.querySelector(`[data-pid="${{item.block_identifier}}"],#p${{item.block_identifier}}`);if(node){{const pin=document.createElement('span');pin.className='limad-note-pin';pin.textContent='N';pin.title=item.title||item.content||'Notiz';pin.onclick=e=>{{e.stopPropagation();parent.postMessage({{type:'limad-note-open',note:item}},location.origin)}};node.append(pin)}}}}
function post(type,data={{}}){{parent.postMessage({{type,...data}},location.origin)}}
let selectionMenuTimer=null;function closePop(){{clearTimeout(selectionMenuTimer);document.querySelectorAll('.limad-popover,.limad-selection-menu').forEach(n=>n.remove())}}
function armSelectionMenu(menu){{clearTimeout(selectionMenuTimer);selectionMenuTimer=setTimeout(()=>menu.remove(),4000);['pointermove','mouseenter','focusin'].forEach(type=>menu.addEventListener(type,()=>{{clearTimeout(selectionMenuTimer);selectionMenuTimer=setTimeout(()=>menu.remove(),4000)}}))}}
function positionSelectionMenu(menu,x,y){{document.body.append(menu);menu.style.left=Math.min(x,innerWidth-menu.offsetWidth-8)+'px';menu.style.top=Math.max(8,y-48)+'px';armSelectionMenu(menu)}}
function markMenu(mark,x,y){{closePop();const m=document.createElement('div');m.className='limad-selection-menu';const imported=String(mark.id||'').includes(':');m.innerHTML='<button data-c="0" title="Gelb">Gelb</button><button data-c="1" title="Grün">Grün</button><button data-c="2" title="Blau">Blau</button><button data-c="3" title="Rosa">Rosa</button><button data-c="4" title="Violett">Violett</button><button data-c="5" title="Orange">Orange</button><button data-note>Notiz</button>'+(imported?'':'<button class="danger" data-remove>Entfernen</button>');positionSelectionMenu(m,x,y);m.querySelectorAll('[data-c]').forEach(button=>button.onclick=()=>{{post('limad-mark-update',{{markId:String(mark.id),colorIndex:Number(button.dataset.c)}});m.remove()}});m.querySelector('[data-note]').onclick=()=>{{post('limad-selection',{{documentId:DOC,blockIdentifier:Number(mark.block_identifier),startToken:mark.start_token==null?null:Number(mark.start_token),endToken:mark.end_token==null?null:Number(mark.end_token),markId:String(mark.id||''),text:mark.text||''}});m.remove()}};m.querySelector('[data-remove]')?.addEventListener('click',()=>{{post('limad-mark-delete',{{markId:String(mark.id)}});m.remove()}})}}
function pop(html,x,y){{closePop();const p=document.createElement('div');p.className='limad-popover';p.innerHTML='<button aria-label="Schließen">×</button>'+html;p.querySelector('button').onclick=()=>p.remove();document.body.append(p);p.style.left=Math.min(x,innerWidth-p.offsetWidth-15)+'px';p.style.top=Math.min(y,innerHeight-p.offsetHeight-15)+'px'}}
function cleanCitationLabel(value){{return String(value||'').replace(/[;,\\s]+$/,'').trim()}}
function qualifyCitationAnchor(anchor){{
 const own=cleanCitationLabel(anchor.textContent||'');
 if(!own)return own;
 if(/^.*[A-Za-zÄÖÜäöüß]\\.?\\s+\\d{{1,3}}\\s*:\\s*\\d/u.test(own))return own;
 const container=anchor.closest('[data-pid],p[id^="p"],li,blockquote,td')||anchor.parentElement;
 const anchors=container?[...container.querySelectorAll('a')]:[anchor];
 let book='',chapter='';
 for(const item of anchors){{
  const raw=cleanCitationLabel(item.textContent||'');
  if(!raw)continue;
  const full=raw.match(/^(.+?[A-Za-zÄÖÜäöüß]\\.?)\\s+(\\d{{1,3}})\\s*:\\s*(.+)$/u);
  let qualified=raw;
  if(full){{book=cleanCitationLabel(full[1]);chapter=full[2];qualified=`${{book}} ${{chapter}}:${{cleanCitationLabel(full[3])}}`}}
  else{{
   const chapterVerse=raw.match(/^(\\d{{1,3}})\\s*:\\s*(.+)$/u);
   if(chapterVerse&&book){{chapter=chapterVerse[1];qualified=`${{book}} ${{chapter}}:${{cleanCitationLabel(chapterVerse[2])}}`}}
   else{{
    const verseOnly=raw.match(/^(\\d{{1,3}}(?:\\s*[-–—]\\s*\\d{{1,3}})?)$/u);
    if(verseOnly&&book&&chapter)qualified=`${{book}} ${{chapter}}:${{cleanCitationLabel(verseOnly[1])}}`;
   }}
  }}
  if(item===anchor)return qualified;
 }}
 return own;
}}
document.addEventListener('pointerdown',e=>{{const a=e.target.closest('a');if(!a)return;const href=a.getAttribute('href')||'';if(href.startsWith('jwpub://')||href.startsWith('jwlibrary://')||href.includes('wol.jw.org')||href.includes('jw.org')){{e.preventDefault();e.stopPropagation()}}}},true);
document.addEventListener('click',e=>{{const marked=e.target.closest('[data-mark-id]');if(marked){{e.preventDefault();e.stopPropagation();markMenu({{id:marked.dataset.markId,block_identifier:marked.dataset.markBlock,start_token:marked.dataset.markStart,end_token:marked.dataset.markEnd,text:marked.textContent||''}},e.clientX,e.clientY);return}}const a=e.target.closest('a');if(!a)return;if(window.limadInlineMedia?.isMediaAnchor(a)){{window.limadInlineMedia.play(a,e);return}}const href=a.getAttribute('href')||'';const f=/footnote|fn/i.test(href+a.className);if(f){{e.preventDefault();const num=(href.match(/\\d+/)||[])[0];const item=footnotes.find(x=>String(x.footnote_index)==num||String(x.source_footnote_id)==num);if(item)pop(item.content_html,e.clientX,e.clientY);return}}if(href.startsWith('jwpub://')||href.startsWith('jwlibrary://')||href.includes('wol.jw.org')||href.includes('jw.org')){{const keepX=scrollX,keepY=scrollY;e.preventDefault();e.stopPropagation();e.stopImmediatePropagation();const original=(a.textContent||'').trim();const qualified=qualifyCitationAnchor(a);post('limad-link',{{href,label:qualified||original,text:qualified||original,originalLabel:original,readerScrollX:keepX,readerScrollY:keepY}});requestAnimationFrame(()=>scrollTo(keepX,keepY));setTimeout(()=>scrollTo(keepX,keepY),0);setTimeout(()=>scrollTo(keepX,keepY),80)}}}},true);
document.addEventListener('mouseup',e=>{{if(document.body.dataset.limadBibleReader==='1')return;setTimeout(()=>{{const sel=getSelection();if(!sel||sel.isCollapsed)return;const node=sel.anchorNode?.parentElement?.closest('[data-pid],p[id^="p"]');if(!node)return;const block=Number(node.dataset.pid||(node.id||'').replace(/^p/,''));const text=sel.toString().trim();if(!text)return;closePop();const m=document.createElement('div');m.className='limad-selection-menu';m.innerHTML='<button data-c="0" title="Gelb">Gelb</button><button data-c="1" title="Grün">Grün</button><button data-c="2" title="Blau">Blau</button><button data-c="3" title="Rosa">Rosa</button><button data-c="4" title="Violett">Violett</button><button data-c="5" title="Orange">Orange</button><button data-note>Notiz</button>';positionSelectionMenu(m,e.clientX,e.clientY);m.querySelectorAll('[data-c]').forEach(b=>b.onclick=()=>{{(()=>{{const tokens=textTokens(node),range=sel.getRangeAt(0);let start=null,end=null;tokens.forEach(t=>{{const r=document.createRange();r.setStart(t.node,t.start);r.setEnd(t.node,t.end);if(range.compareBoundaryPoints(Range.END_TO_START,r)<0&&range.compareBoundaryPoints(Range.START_TO_END,r)>0){{if(start===null)start=t.index;end=t.index}}}});post('limad-mark',{{documentId:DOC,blockIdentifier:block,text,startToken:start,endToken:end,colorIndex:Number(b.dataset.c)}})}})();m.remove()}});m.querySelector('[data-note]').onclick=()=>{{const tokens=textTokens(node),range=sel.getRangeAt(0);let start=null,end=null;tokens.forEach(t=>{{const r=document.createRange();r.setStart(t.node,t.start);r.setEnd(t.node,t.end);if(range.compareBoundaryPoints(Range.END_TO_START,r)<0&&range.compareBoundaryPoints(Range.START_TO_END,r)>0){{if(start===null)start=t.index;end=t.index}}}});post('limad-selection',{{documentId:DOC,blockIdentifier:block,startToken:start,endToken:end,markId:null,text}});m.remove()}}}},0)}});
document.addEventListener('pointerdown',e=>{{if(!e.target.closest('.limad-selection-menu')&&!e.target.closest('[data-limad-mark]'))document.querySelectorAll('.limad-selection-menu').forEach(node=>node.remove())}},true);
document.addEventListener('keydown',e=>{{if(e.key==='Escape')closePop()}});
function normalizeWatchtowerQuestions(){{if(!document.body.classList.contains('reader-profile-watchtower-study'))return;document.querySelectorAll('.studyQuestion').forEach(node=>{{if(node.querySelector('.limad-question-number,.questionNumber,.question-number,.questionNum,.question-num'))return;const walker=document.createTreeWalker(node,NodeFilter.SHOW_TEXT);let textNode=null;while(walker.nextNode()){{if((walker.currentNode.nodeValue||'').trim()){{textNode=walker.currentNode;break}}}}if(!textNode)return;const value=textNode.nodeValue||'';const match=value.match(/^(\\s*)(\\d{{1,3}}(?:\\s*[–-]\\s*\\d{{1,3}})?\\.)(\\s*)/);if(!match)return;const before=document.createTextNode(match[1]);const number=document.createElement('span');number.className='limad-question-number';number.textContent=match[2].replace(/\\s*[–-]\\s*/,'–');const after=document.createTextNode(value.slice(match[0].length));const parent=textNode.parentNode;parent.insertBefore(before,textNode);parent.insertBefore(number,textNode);parent.insertBefore(after,textNode);parent.removeChild(textNode)}})}}
normalizeWatchtowerQuestions();
const initialFocus=new URLSearchParams(location.search).get('focus');
document.querySelectorAll('video,audio').forEach(media=>{{media.controls=true;media.preload='metadata';media.setAttribute('playsinline','');media.addEventListener('error',()=>post('limad-media-error',{{src:media.currentSrc||media.src||'',title:media.getAttribute('aria-label')||document.title}}))}});
document.querySelectorAll('img').forEach(image=>{{image.classList.add('limad-reader-image');image.tabIndex=0;const open=e=>{{if(image.hidden||image.closest('.limad-inline-media-host'))return;e.preventDefault();e.stopPropagation();const figure=image.closest('figure,.figure');const caption=figure?.querySelector('figcaption,.figcaption,.caption')?.textContent||image.getAttribute('alt')||'';post('limad-image',{{src:image.currentSrc||image.src,alt:image.getAttribute('alt')||'',caption,documentId:DOC}})}};image.addEventListener('click',open,true);image.addEventListener('keydown',e=>{{if(e.key==='Enter'||e.key===' ')open(e)}})}});
if(initialFocus)requestAnimationFrame(()=>document.querySelector(`[data-pid="${{CSS.escape(initialFocus)}}"],#p${{CSS.escape(initialFocus)}}`)?.scrollIntoView({{block:'start'}}));
const savedFieldMap=new Map(savedInputFields.map(item=>[String(item.text_tag),String(item.value||'')]));
function inputFieldTag(node,index){{const direct=node.dataset?.textTag||node.dataset?.texttag||node.dataset?.inputField||node.getAttribute('data-text-tag')||node.getAttribute('data-texttag')||node.getAttribute('data-input-field')||node.id||node.getAttribute('name');if(direct)return String(direct);const block=node.closest('[data-pid],p[id^="p"]');const blockId=block?.dataset?.pid||(block?.id||'').replace(/^p/,'')||'document';return `answer:${{blockId}}:${{index}}`}}
const answerFields=[...document.querySelectorAll('textarea,input[type="text"],input:not([type]),[contenteditable="true"]')].filter(node=>!node.closest('.limad-selection-menu,.limad-popover'));
function sizeAnswerField(node){{if(node.tagName!=='TEXTAREA')return;node.style.height='auto';node.style.height=Math.min(260,Math.max(54,node.scrollHeight+2))+'px'}}
answerFields.forEach((node,index)=>{{const tag=inputFieldTag(node,index);node.dataset.limadInputTag=tag;const saved=savedFieldMap.get(tag);if(saved!==undefined){{if(node.matches('[contenteditable]'))node.textContent=saved;else node.value=saved}}sizeAnswerField(node);let saveTimer=null;const save=()=>{{const value=node.matches('[contenteditable]')?node.innerText:String(node.value||'');fetch('/api/input-fields',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{document_id:DOC,text_tag:tag,value}}),keepalive:true}}).then(()=>post('limad-input-field-saved',{{documentId:DOC,textTag:tag,value}})).catch(()=>{{}})}};node.addEventListener('input',()=>{{sizeAnswerField(node);clearTimeout(saveTimer);saveTimer=setTimeout(save,350)}});node.addEventListener('change',save);node.addEventListener('blur',save)}});
let smoothWheelTarget=scrollY,smoothWheelFrame=0;
function cancelSmoothWheel(){{if(smoothWheelFrame)cancelAnimationFrame(smoothWheelFrame);smoothWheelFrame=0;smoothWheelTarget=scrollY}}
function animateSmoothWheel(){{const max=Math.max(0,document.documentElement.scrollHeight-innerHeight);smoothWheelTarget=Math.max(0,Math.min(max,smoothWheelTarget));const diff=smoothWheelTarget-scrollY;if(Math.abs(diff)<.55){{scrollTo({{left:scrollX,top:smoothWheelTarget,behavior:'auto'}});smoothWheelFrame=0;return}}scrollTo({{left:scrollX,top:scrollY+diff*.22,behavior:'auto'}});smoothWheelFrame=requestAnimationFrame(animateSmoothWheel)}}
addEventListener('wheel',event=>{{if(event.defaultPrevented||event.ctrlKey||event.metaKey||Math.abs(event.deltaX)>Math.abs(event.deltaY))return;if(event.target?.closest?.('textarea,input,select,[contenteditable="true"],.limad-popover,.limad-selection-menu,video,audio'))return;let delta=Number(event.deltaY||0);if(event.deltaMode===1)delta*=16;else if(event.deltaMode===2)delta*=Math.max(240,innerHeight*.75);if(!delta)return;const touchpadLike=event.deltaMode===0&&Math.abs(delta)<34;if(touchpadLike){{cancelSmoothWheel();requestAnimationFrame(()=>{{smoothWheelTarget=scrollY}});return}}event.preventDefault();const step=Math.sign(delta)*Math.min(52,Math.max(20,Math.abs(delta)*.34));if(!smoothWheelFrame)smoothWheelTarget=scrollY;const max=Math.max(0,document.documentElement.scrollHeight-innerHeight);smoothWheelTarget=Math.max(0,Math.min(max,smoothWheelTarget+step));if(!smoothWheelFrame)smoothWheelFrame=requestAnimationFrame(animateSmoothWheel)}},{{passive:false}});
window.__limadSmoothWheel={{cancel:cancelSmoothWheel,target:()=>smoothWheelTarget,active:()=>Boolean(smoothWheelFrame)}};
let timer;addEventListener('scroll',()=>{{clearTimeout(timer);timer=setTimeout(()=>{{const max=document.documentElement.scrollHeight-innerHeight;post('limad-position',{{documentId:DOC,scrollRatio:max>0?scrollY/max:0,blockIdentifier:null}})}},350)}});
addEventListener('message',e=>{{const d=e.data||{{}};if(d.type==='limad-restore'){{cancelSmoothWheel();if(d.blockIdentifier)document.querySelector(`[data-pid="${{d.blockIdentifier}}"],#p${{d.blockIdentifier}}`)?.scrollIntoView({{block:'start',behavior:'auto'}});else scrollTo({{left:0,top:(document.documentElement.scrollHeight-innerHeight)*(d.scrollRatio||0),behavior:'auto'}})}}if(d.type==='limad-mark-applied')applyClientMark(d.mark||{{}});if(d.type==='limad-mark-updated')updateClientMark(d.mark||{{}});if(d.type==='limad-mark-deleted')deleteClientMark(d.markId);if(d.type==='limad-font')document.documentElement.style.setProperty('--font-scale',String(d.scale||1));if(d.type==='limad-theme')document.documentElement.dataset.theme=d.theme==='dark'?'dark':'light'}});
post('limad-reader-ready',{{documentId:DOC}});
'''
    script += (INLINE_MEDIA_JS.replace('__LANGUAGE_INDEX__',str(int(doc.get('language_index') or 2))).replace('__PUBLICATION_ID__',json.dumps(str(doc.get('publication_id') or ''))).replace('__DOCUMENT_ID__',str(int(document_id))))
    title=escape(doc.get('title') or doc.get('publication_title') or 'LiMaD Study')
    return f'<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><base href="{prefix}"><title>{title}</title><script>(function(){{const q=new URLSearchParams(location.search);document.documentElement.dataset.theme=q.get("theme")=="dark"?"dark":"light";const v=Number(q.get("scale")||1);document.documentElement.style.setProperty("--font-scale",String(Math.min(1.5,Math.max(.75,Number.isFinite(v)?v:1))))}})();</script><style>{READER_CSS}</style></head><body class="reader-profile-{reader_kind}" data-reader-profile="{reader_kind}">{markup}<script>{script}</script></body></html>'

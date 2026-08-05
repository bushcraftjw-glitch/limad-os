from __future__ import annotations
from pathlib import Path
import hashlib
import html
import mimetypes
import os
import re
from ..database import DB,Database
from ..utils import utc_now

def _kind_clause(kind:str)->str:
    kind=(kind or '').lower()
    if kind=='video': return "(m.mime_type LIKE 'video/%' OR lower(m.file_path) GLOB '*.mp4' OR lower(m.file_path) GLOB '*.m4v' OR lower(m.file_path) GLOB '*.webm')"
    if kind=='audio': return "(m.mime_type LIKE 'audio/%' OR lower(m.file_path) GLOB '*.mp3' OR lower(m.file_path) GLOB '*.m4a' OR lower(m.file_path) GLOB '*.aac' OR lower(m.file_path) GLOB '*.opus')"
    return '1=1'

def list_media(kind:str='',publication_id:str|None=None,database:Database=DB)->list[dict]:
    clauses=["m.file_path<>''",_kind_clause(kind)];params=[]
    if publication_id: clauses.append('m.publication_id=?');params.append(publication_id)
    rows=database.rows("SELECT m.*,p.title AS publication_title,p.cover_path,p.content_dir FROM media m JOIN publications p ON p.id=m.publication_id WHERE "+' AND '.join(clauses)+" ORDER BY p.title,COALESCE(m.label,m.file_path)",params)
    result=[]
    for row in rows:
        target=(Path(row['content_dir'])/row['file_path']).resolve()
        if not target.is_file(): continue
        row['media_key']=f"{row['publication_id']}:{row['file_path']}"
        row['url']=f"/content/{row['publication_id']}/{row['file_path']}"
        row['preview']=f"/api/publications/{row['publication_id']}/cover" if row.get('cover_path') else ''
        progress=database.rows('SELECT position_seconds,duration_seconds,playback_rate,updated_at FROM media_progress WHERE media_key=?',(row['media_key'],))
        row['progress']=progress[0] if progress else {'position_seconds':0,'duration_seconds':0,'playback_rate':1}
        result.append(row)
    return result

def get_progress(media_key:str,database:Database=DB)->dict:
    rows=database.rows('SELECT * FROM media_progress WHERE media_key=?',(media_key,))
    return rows[0] if rows else {'media_key':media_key,'position_seconds':0,'duration_seconds':0,'playback_rate':1}

def save_progress(media_key:str,publication_id:str,file_path:str,position:float,duration:float,rate:float,database:Database=DB)->dict:
    position=max(0,float(position or 0));duration=max(0,float(duration or 0));rate=min(3,max(.25,float(rate or 1)))
    database.execute('''INSERT INTO media_progress(media_key,publication_id,file_path,position_seconds,duration_seconds,playback_rate,updated_at)
    VALUES(?,?,?,?,?,?,?) ON CONFLICT(media_key) DO UPDATE SET position_seconds=excluded.position_seconds,duration_seconds=excluded.duration_seconds,playback_rate=excluded.playback_rate,updated_at=excluded.updated_at''',(media_key,publication_id,file_path,position,duration,rate,utc_now()))
    return get_progress(media_key,database)

import json
import urllib.parse
import urllib.request
import urllib.error

MEDIATOR_BASE = "https://b.jw-cdn.org/apis/mediator/v1/categories"
_ALLOWED_MEDIA_HOSTS = {"b.jw-cdn.org", "cms-imgp.jw-cdn.org", "download-a.akamaihd.net", "download-a.jw-cdn.org"}

def _safe_remote_url(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        return ""
    host = parsed.hostname.lower()
    if host not in _ALLOWED_MEDIA_HOSTS and not host.endswith(".jw-cdn.org") and not host.endswith(".akamaihd.net"):
        return ""
    return value

def _pick_image(images) -> str:
    if isinstance(images, str):
        return _safe_remote_url(images)
    if isinstance(images, list):
        for item in reversed(images):
            found = _pick_image(item)
            if found:
                return found
        return ""
    if not isinstance(images, dict):
        return ""
    for shape in ("sqr", "lsr", "pnr", "cvr"):
        value = images.get(shape)
        if isinstance(value, dict):
            for size in ("xl", "lg", "md", "sm", "xs"):
                found = _safe_remote_url(value.get(size, ""))
                if found:
                    return found
        else:
            found = _pick_image(value)
            if found:
                return found
    for value in images.values():
        found = _pick_image(value)
        if found:
            return found
    return ""

def _flatten_files(files, inherited: dict | None = None) -> list[dict]:
    """Flatten JW mediator file variants while preserving parent quality metadata."""
    inherited = dict(inherited or {})
    result: list[dict] = []
    if isinstance(files, list):
        for value in files:
            result.extend(_flatten_files(value, inherited))
        return result
    if not isinstance(files, dict):
        return result
    merged = dict(inherited)
    for key, value in files.items():
        if key not in {"file", "files", "media", "items", "videos", "audio"} and not isinstance(value, (dict, list)):
            merged[key] = value
    nested_file = files.get("file")
    if isinstance(nested_file, dict):
        candidate = dict(merged)
        candidate.update(nested_file)
        result.extend(_flatten_files(candidate, merged))
    if any(key in files for key in ("progressiveDownloadURL", "url", "fileUrl")):
        candidate = dict(merged)
        candidate.update(files)
        result.append(candidate)
    for key, value in files.items():
        if key == "file":
            continue
        if isinstance(value, (dict, list)):
            result.extend(_flatten_files(value, merged))
    unique = []
    seen = set()
    for item in result:
        url = str(item.get("progressiveDownloadURL") or item.get("url") or item.get("fileUrl") or "")
        signature = (url, str(item.get("mimetype") or item.get("mimeType") or ""), str(item.get("height") or item.get("frameHeight") or item.get("verticalResolution") or ""))
        if url and signature not in seen:
            seen.add(signature)
            unique.append(item)
    return unique


def _quality_label(item: dict) -> str:
    height = item.get("height") or item.get("frameHeight") or item.get("verticalResolution")
    label = str(item.get("label") or item.get("quality") or item.get("resolution") or "").strip()
    if height:
        try:
            return f"{int(height)}p"
        except Exception:
            pass
    match = __import__("re").search(r"(\d{3,4})p", label, __import__("re").I)
    return f"{match.group(1)}p" if match else (label or "Standard")

def _pick_sources(files, kind: str) -> list[dict]:
    sources = []
    seen = set()
    for item in _flatten_files(files):
        mime = str(item.get("mimetype") or item.get("mimeType") or "").lower()
        url = _safe_remote_url(item.get("progressiveDownloadURL") or item.get("url") or item.get("fileUrl") or "")
        if not url or (kind and mime and not mime.startswith(kind + "/")) or url in seen:
            continue
        seen.add(url)
        sources.append({
            "url": url,
            "mime_type": mime,
            "duration": item.get("duration") or 0,
            "quality": _quality_label(item),
            "height": item.get("height") or item.get("frameHeight") or item.get("verticalResolution") or 0,
            "width": item.get("width") or item.get("frameWidth") or item.get("horizontalResolution") or 0,
            "filesize": item.get("filesize") or item.get("fileSize") or item.get("size") or 0,
        })
    sources.sort(key=lambda x: int(x.get("height") or 0))
    return sources

def _pick_file(files, kind: str) -> dict:
    sources = _pick_sources(files, kind)
    return sources[-1] if sources else {}

def _category_item(item: dict) -> dict:
    key = str(item.get("key") or item.get("categoryKey") or item.get("symbol") or item.get("id") or "")
    return {"key": key, "title": str(item.get("name") or item.get("title") or item.get("label") or key), "description": str(item.get("description") or ""), "image": _pick_image(item.get("images") or item.get("image") or {})}

def _media_item(item: dict, kind: str) -> dict:
    sources = _pick_sources(item.get("files") or item.get("media") or [], kind)
    file = sources[-1] if sources else {}
    return {"title": str(item.get("title") or item.get("name") or "Medium"), "description": str(item.get("description") or item.get("synopsis") or ""), "image": _pick_image(item.get("images") or item.get("image") or {}), "url": file.get("url", ""), "mime_type": file.get("mime_type", ""), "duration": file.get("duration", 0), "first_published": item.get("firstPublished") or item.get("first_published") or "", "natural_key": str(item.get("naturalKey") or item.get("guid") or item.get("key") or ""), "sources": sources}

def _load_mediator_category(language_symbol_value: str, category: str) -> dict:
    errors = []
    for base in ("https://b.jw-cdn.org/apis/mediator/v1/categories", "https://data.jw-api.org/mediator/v1/categories"):
        url = f"{base}/{urllib.parse.quote(language_symbol_value)}/{urllib.parse.quote(category)}?detailed=1"
        request = urllib.request.Request(url, headers={"User-Agent": "jwlibrary-android", "Accept": "application/json", "Accept-Encoding": "identity"})
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                raw = response.read(25_000_001)
                if len(raw) > 25_000_000:
                    raise ValueError("Medienkatalog ist zu groß.")
            return json.loads(raw.decode("utf-8-sig"))
        except urllib.error.HTTPError as error:
            errors.append(f"{category}: HTTP {error.code}")
            if error.code != 404:
                raise
        except Exception as error:
            errors.append(f"{category}: {error}")
    raise urllib.error.HTTPError("", 404, "; ".join(errors) or "Kategorie nicht gefunden", {}, None)

def mediator_catalog(kind: str, language_symbol_value: str, category: str = "") -> dict:
    kind = "video" if str(kind).lower() == "video" else "audio"
    language_symbol_value = (language_symbol_value or "X").strip()[:8]
    category = (category or "").strip().strip("/")
    if category and not all(ch.isalnum() or ch in "_-" for ch in category):
        raise ValueError("Ungültige Medienkategorie.")
    if category:
        candidates = [category]
    elif kind == "audio":
        candidates = ["Audio"]
    else:
        candidates = ["VideoOnDemand", "LatestVideos", "Videos", "Video"]
    payload = None
    selected = ""
    last_error = None
    for candidate in candidates:
        try:
            payload = _load_mediator_category(language_symbol_value, candidate)
            selected = candidate
            break
        except urllib.error.HTTPError as error:
            last_error = error
            if error.code != 404:
                raise
    if payload is None:
        raise last_error or ValueError("Medienkatalog nicht gefunden.")
    node = payload.get("category", payload) if isinstance(payload, dict) else {}
    categories = []
    for key in ("subcategories", "categories", "children"):
        value = node.get(key) if isinstance(node, dict) else None
        if isinstance(value, list):
            categories.extend(_category_item(x) for x in value if isinstance(x, dict))
    media = []
    for key in ("media", "items", "videos", "audio"):
        value = node.get(key) if isinstance(node, dict) else None
        if isinstance(value, list):
            media.extend(_media_item(x, kind) for x in value if isinstance(x, dict))
    media = [prepare_media_for_playback(item) for item in media if item.get("url")]
    media = [item for item in media if item.get("url")]
    title = str(node.get("name") or node.get("title") or ("Videos" if kind == "video" else "Audio")) if isinstance(node, dict) else kind.title()
    return {"kind": kind, "language_symbol": language_symbol_value, "category": selected, "title": title, "categories": categories, "media": media, "source": "JW.ORG Mediator"}

def language_symbol(language_index: int, database: Database = DB) -> str:
    rows = database.rows("SELECT symbol FROM languages WHERE id=?", (int(language_index),))
    return str(rows[0].get("symbol") or "X") if rows else "X"




PUB_MEDIA_BASES = (
    "https://b.jw-cdn.org/apis/pub-media/GETPUBMEDIALINKS",
    "https://pubmedia.jw-api.org/GETPUBMEDIALINKS",
)
_PUBLICATION_SYMBOL_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,40}")


def _decoded_media_values(*values: str) -> list[str]:
    decoded_values: list[str] = []
    for raw in values:
        value = html.unescape(str(raw or "")).strip()
        if not value:
            continue
        variants = [value]
        current = value
        for _ in range(4):
            try:
                decoded = urllib.parse.unquote(current)
            except Exception:
                break
            if decoded == current:
                break
            variants.append(decoded)
            current = decoded
        for variant in variants:
            variant = html.unescape(variant).replace("\\/", "/").strip()
            if variant and variant not in decoded_values:
                decoded_values.append(variant)
    return decoded_values


def extract_publication_media_reference(*values: str) -> dict:
    for value in _decoded_media_values(*values):
        candidates = [value]
        candidates.extend(re.findall(r"webpub(?:vid|aud)://[^\s\"'<>]+", value, re.I))
        for candidate in candidates:
            parsed = urllib.parse.urlparse(candidate)
            if parsed.scheme.lower() not in {"webpubvid", "webpubaud"}:
                continue
            query = urllib.parse.parse_qs(parsed.query)
            publication = str((query.get("pub") or [""])[0]).strip()
            track_value = str((query.get("track") or [""])[0]).strip()
            if not _PUBLICATION_SYMBOL_PATTERN.fullmatch(publication) or not track_value.isdigit():
                continue
            track = int(track_value)
            if track < 0 or track > 999999:
                continue
            return {
                "publication": publication,
                "track": track,
                "kind": "audio" if parsed.scheme.lower() == "webpubaud" else "video",
            }
    return {}


def _publication_media_item_from_payload(payload: dict, language_symbol_value: str, publication: str, track: int, kind: str) -> dict:
    files = payload.get("files") if isinstance(payload, dict) else None
    if not isinstance(files, dict) or not files:
        raise FileNotFoundError("Der offizielle Medienkatalog enthält keine Dateien.")
    language_node = files.get(language_symbol_value)
    if not isinstance(language_node, dict):
        language_node = next((value for value in files.values() if isinstance(value, dict)), None)
    if not isinstance(language_node, dict):
        raise FileNotFoundError("Für diese Sprache wurden keine Mediendateien gefunden.")
    formats = ("MP4", "M4V", "3GP") if kind == "video" else ("MP3", "AAC", "M4A")
    entries = []
    for file_format in formats:
        value = language_node.get(file_format)
        if isinstance(value, list):
            entries.extend(item for item in value if isinstance(item, dict))
        elif isinstance(value, dict):
            entries.append(value)
    exact = []
    for item in entries:
        try:
            item_track = int(item.get("track"))
        except (TypeError, ValueError):
            continue
        if item_track == int(track):
            exact.append(item)
    if not exact:
        raise FileNotFoundError(f"Medium {publication}, Track {track} wurde nicht gefunden.")
    sources = []
    image = ""
    title = ""
    for item in exact:
        file_node = item.get("file") if isinstance(item.get("file"), dict) else item
        url = _safe_remote_url(file_node.get("url") or file_node.get("progressiveDownloadURL") or file_node.get("fileUrl") or "")
        if not url:
            continue
        mime = str(item.get("mimetype") or file_node.get("mimetype") or file_node.get("mimeType") or ("video/mp4" if kind == "video" else "audio/mpeg")).lower()
        if not title:
            title = str(item.get("title") or payload.get("pubName") or publication)
        if not image:
            track_image = item.get("trackImage") if isinstance(item.get("trackImage"), dict) else {}
            image = _safe_remote_url(track_image.get("url") or "")
        sources.append({
            "url": url,
            "mime_type": mime,
            "duration": item.get("duration") or 0,
            "quality": _quality_label(item),
            "height": item.get("frameHeight") or item.get("height") or 0,
            "width": item.get("frameWidth") or item.get("width") or 0,
            "filesize": item.get("filesize") or item.get("fileSize") or 0,
        })
    if not sources:
        raise FileNotFoundError("Für dieses Medium wurde keine abspielbare Datei gefunden.")
    if not image:
        pub_image = payload.get("pubImage") if isinstance(payload.get("pubImage"), dict) else {}
        image = _safe_remote_url(pub_image.get("url") or "")
    sources.sort(key=lambda item: int(item.get("height") or 0))
    selected = sources[-1]
    return {
        "title": title or publication,
        "description": "",
        "image": image,
        "url": selected.get("url") or "",
        "mime_type": selected.get("mime_type") or "",
        "duration": selected.get("duration") or 0,
        "natural_key": f"pub-{publication}_{int(track):03d}_{kind.upper()}",
        "publication": publication,
        "track": int(track),
        "kind": kind,
        "sources": sources,
    }


def publication_media_item(language_symbol_value: str, publication: str, track: int, kind: str = "video") -> dict:
    language_symbol_value = str(language_symbol_value or "X").strip()
    publication = str(publication or "").strip()
    kind = "audio" if str(kind).lower() == "audio" else "video"
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,12}", language_symbol_value):
        raise ValueError("Ungültiges Sprachsymbol.")
    if not _PUBLICATION_SYMBOL_PATTERN.fullmatch(publication):
        raise ValueError("Ungültiges Mediensymbol.")
    track = int(track)
    if track < 0 or track > 999999:
        raise ValueError("Ungültige Tracknummer.")
    file_formats = "MP3,AAC,M4A" if kind == "audio" else "MP4,M4V,3GP"
    errors = []
    for base in PUB_MEDIA_BASES:
        query = urllib.parse.urlencode({
            "alllangs": "0",
            "fileformat": file_formats,
            "langwritten": language_symbol_value,
            "output": "json",
            "pub": publication,
            "track": str(track),
        })
        request = urllib.request.Request(
            f"{base}?{query}",
            headers={"User-Agent": "jwlibrary-android", "Accept": "application/json", "Accept-Encoding": "identity"},
        )
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                raw = response.read(25_000_001)
                if len(raw) > 25_000_000:
                    raise ValueError("Mediendaten sind zu groß.")
            payload = json.loads(raw.decode("utf-8-sig"))
            if not isinstance(payload, dict):
                raise ValueError("Ungültige Mediendaten.")
            return _publication_media_item_from_payload(payload, language_symbol_value, publication, track, kind)
        except Exception as error:
            errors.append(f"{base}: {error}")
    raise RuntimeError("; ".join(errors) or "Mediendaten konnten nicht geladen werden.")

MEDIA_ITEM_BASES = (
    "https://b.jw-cdn.org/apis/mediator/v1/media-items",
    "https://data.jw-api.org/mediator/v1/media-items",
)
_NATURAL_KEY_PATTERN = re.compile(r"(?P<key>pub-[A-Za-z0-9_-]+_(?:VIDEO|AUDIO))", re.I)


def extract_natural_key(*values: str) -> str:
    """Extract an exact JW media natural key from JWPUB, finder or open links."""
    for value in _decoded_media_values(*values):
        try:
            parsed = urllib.parse.urlparse(value)
            query = urllib.parse.parse_qs(parsed.query)
            candidates = []
            for key in ("lank", "item", "naturalKey", "naturalkey", "key", "media", "mediaKey"):
                candidates.extend(query.get(key) or [])
            candidates.extend((parsed.path, parsed.fragment, value))
        except Exception:
            candidates = [value]
        for candidate in candidates:
            match = _NATURAL_KEY_PATTERN.search(str(candidate or ""))
            if match:
                return match.group("key")
    return ""


def extract_media_kind(*values: str) -> str:
    publication_reference = extract_publication_media_reference(*values)
    if publication_reference:
        return str(publication_reference.get("kind") or "")
    natural_key = extract_natural_key(*values)
    if natural_key.upper().endswith("_VIDEO"):
        return "video"
    if natural_key.upper().endswith("_AUDIO"):
        return "audio"
    joined = " ".join(_decoded_media_values(*values)).lower()
    if re.search(r"(?:^|[\s\"'=(])(?:jwpub|jwlibrary)://(?:v|video)(?:/|\?|$)", joined):
        return "video"
    if re.search(r"(?:^|[\s\"'=(])(?:jwpub|jwlibrary)://(?:a|audio)(?:/|\?|$)", joined):
        return "audio"
    if re.search(r"\.(?:mp4|m4v|webm|mov)(?:[?#\s\"']|$)", joined):
        return "video"
    if re.search(r"\.(?:mp3|m4a|aac|ogg|opus)(?:[?#\s\"']|$)", joined):
        return "audio"
    return ""


def _candidate_media_nodes(value, natural_key: str) -> list[dict]:
    found: list[dict] = []
    if isinstance(value, list):
        for item in value:
            found.extend(_candidate_media_nodes(item, natural_key))
    elif isinstance(value, dict):
        own_key = str(value.get("naturalKey") or value.get("natural_key") or value.get("key") or value.get("guid") or "")
        if value.get("files") or value.get("media") or value.get("images") or value.get("title"):
            score = 3 if own_key.lower() == natural_key.lower() else (1 if extract_natural_key(own_key) == natural_key else 0)
            copy = dict(value)
            copy["__match_score"] = score
            found.append(copy)
        for item in value.values():
            if isinstance(item, (dict, list)):
                found.extend(_candidate_media_nodes(item, natural_key))
    return found


def _load_mediator_item(language_symbol_value: str, natural_key: str) -> dict:
    language_symbol_value = str(language_symbol_value or "X").strip()
    natural_key = str(natural_key or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,12}", language_symbol_value):
        raise ValueError("Ungültiges Sprachsymbol.")
    if not re.fullmatch(r"pub-[A-Za-z0-9_-]+_(?:VIDEO|AUDIO)", natural_key, re.I):
        raise ValueError("Ungültige Medienkennung.")
    errors = []
    for base in MEDIA_ITEM_BASES:
        url = f"{base}/{urllib.parse.quote(language_symbol_value)}/{urllib.parse.quote(natural_key)}"
        request = urllib.request.Request(url, headers={"User-Agent": "jwlibrary-android", "Accept": "application/json", "Accept-Encoding": "identity"})
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                raw = response.read(25_000_001)
                if len(raw) > 25_000_000:
                    raise ValueError("Mediendaten sind zu groß.")
            payload = json.loads(raw.decode("utf-8-sig"))
            if not isinstance(payload, dict):
                raise ValueError("Ungültige Mediendaten.")
            return payload
        except Exception as error:
            errors.append(f"{base}: {error}")
    raise RuntimeError("; ".join(errors) or "Mediendaten konnten nicht geladen werden.")


def mediator_media_item(language_symbol_value: str, natural_key: str) -> dict:
    """Resolve the exact current official item by natural key, without title guessing."""
    payload = _load_mediator_item(language_symbol_value, natural_key)
    candidates = _candidate_media_nodes(payload, natural_key)
    if not candidates:
        candidates = [payload]
    candidates.sort(key=lambda item: (int(item.get("__match_score") or 0), len(_pick_sources(item.get("files") or item.get("media") or item, "audio" if natural_key.upper().endswith("_AUDIO") else "video"))), reverse=True)
    kind = "audio" if natural_key.upper().endswith("_AUDIO") else "video"
    for node in candidates:
        item = _media_item(node, kind)
        if item.get("sources"):
            item["natural_key"] = str(item.get("natural_key") or natural_key)
            item["kind"] = kind
            return item
    raise FileNotFoundError("Für dieses Medium wurde keine abspielbare Datei gefunden.")


def safe_remote_media_url(url: str) -> str:
    return _safe_remote_url(url)


def media_proxy_url(url: str) -> str:
    safe = _safe_remote_url(url)
    return f"/api/media/proxy?url={urllib.parse.quote(safe, safe='')}" if safe else ""


def prepare_media_for_playback(item: dict) -> dict:
    output = dict(item or {})
    prepared = []
    for source in output.get("sources") or []:
        original = _safe_remote_url(source.get("url") or "")
        if not original:
            continue
        entry = dict(source)
        entry["download_url"] = original
        entry["url"] = media_proxy_url(original)
        prepared.append(entry)
    prepared.sort(key=lambda entry: int(entry.get("height") or 0), reverse=True)
    output["sources"] = prepared
    if prepared:
        selected = prepared[0]
        output["url"] = selected["url"]
        output["download_url"] = selected["download_url"]
        output["mime_type"] = selected.get("mime_type") or output.get("mime_type") or ""
    return output


def _media_index_path() -> Path:
    from ..config import PATHS
    return PATHS.downloads / "media-index.json"

def list_remote_downloads() -> list[dict]:
    path = _media_index_path()
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []

def download_remote_media(url: str, title: str, kind: str, quality: str = "", image: str = "", natural_key: str = "") -> dict:
    from ..config import PATHS
    url = _safe_remote_url(url)
    if not url:
        raise ValueError("Ungültige Medienadresse.")
    kind = "video" if kind == "video" else "audio"
    folder = PATHS.downloads / "media" / kind
    folder.mkdir(parents=True, exist_ok=True)
    parsed = urllib.parse.urlparse(url)
    suffix = Path(parsed.path).suffix.lower() or (".mp4" if kind == "video" else ".mp3")
    key = natural_key or hashlib.sha256(url.encode()).hexdigest()[:20]
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in key)[:80] or hashlib.sha256(url.encode()).hexdigest()[:20]
    target = folder / f"{safe}{suffix}"
    temp = target.with_suffix(target.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "jwlibrary-android", "Accept-Encoding": "identity"})
    with urllib.request.urlopen(request, timeout=45) as response, temp.open("wb") as output:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
    temp.replace(target)
    item = {"id": safe, "title": title or target.stem, "kind": kind, "quality": quality, "image": image, "natural_key": natural_key, "path": str(target), "url": f"/api/media/downloaded/{safe}", "size": target.stat().st_size, "created_at": utc_now()}
    entries = [x for x in list_remote_downloads() if x.get("id") != safe]
    entries.insert(0, item)
    _media_index_path().write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    return item

def downloaded_media_file(media_id: str) -> Path | None:
    for item in list_remote_downloads():
        if item.get("id") == media_id:
            path = Path(item.get("path") or "")
            return path if path.is_file() else None
    return None

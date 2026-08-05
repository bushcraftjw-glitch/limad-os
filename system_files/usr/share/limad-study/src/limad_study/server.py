from __future__ import annotations
import json
import os
import re
import shutil
import tempfile
import threading
import urllib.parse
import urllib.request
import urllib.error
import webbrowser
import http.client
import socket
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from . import APP_NAME, VERSION
from .backup import export_jwlibrary, reconcile_backup, resolution_report
from .catalog import catalog_status, cover_bytes, download_options, languages, publication_detail, publications as catalog_publications, sync_all
from .config import PATHS
from .database import DB
from .downloads import cancel as cancel_download, cleanup_completed as cleanup_downloads, jobs as download_jobs, remove as remove_download, retry as retry_download, start as start_download
from .importers import import_jwlibrary, import_jwpub
from .reader import render_document
from .media import list_media, get_progress, save_progress, mediator_catalog, language_symbol, list_remote_downloads, download_remote_media, downloaded_media_file, safe_remote_media_url
from .publication_catalog import live_publications
from .bible import bible_library, bible_navigation, bible_overview, bible_chapter, render_bible_chapter, bible_compare, bible_search, set_preference, save_view_state, view_state, bible_chapter_document_id
from .bible.service import BIBLE_BOOKS_DE
from .bible.references import verse_material
from .playlists import list_playlists, create_playlist, add_item, delete_playlist, reorder_items, import_jwlplaylist, export_jwlplaylist
from .resources import WEB_ROOT
from .seed_data import ensure_seed
from .study import add_mark, bookmarks, create_note, delete_note, home_payload, notes, tags, update_note, delete_mark, document_marks, create_bookmark, delete_bookmark, save_position, reading_position, add_mark_group, update_mark, delete_mark_any, document_mark_groups, save_input_field, input_fields_for_document
from .meetings import meeting_week, meeting_notes, save_meeting_note, delete_meeting_note
from .library import enrich_library_items
from .utils import mime_type, safe_identifier, utc_now
from .source_resolver import resolve_source
from .online_sources import resolve_online_source
from .assistant import assistant_state, list_projects as assistant_projects, create_project as assistant_create_project, delete_project as assistant_delete_project, project_messages as assistant_project_messages, send_message as assistant_send_message, update_settings as assistant_update_settings

MAX_JSON = 5 * 1024 * 1024
MAX_UPLOAD = 2_000_000_000


def _remove_publication(publication_id: str) -> dict[str, Any]:
    rows = DB.rows("SELECT id,title,source_path,content_dir FROM publications WHERE id=?", (publication_id,))
    if not rows:
        raise ValueError("Publikation nicht gefunden.")
    row = rows[0]
    with DB.transaction() as con:
        con.execute("DELETE FROM documents_fts WHERE publication_id=?", (publication_id,))
        con.execute("DELETE FROM publications WHERE id=?", (publication_id,))
    removed_files = 0
    for value in (row.get("content_dir"), row.get("source_path")):
        if not value:
            continue
        candidate = Path(value)
        try:
            if candidate.is_dir():
                shutil.rmtree(candidate)
                removed_files += 1
            elif candidate.is_file():
                candidate.unlink()
                removed_files += 1
        except OSError:
            pass
    return {"id": publication_id, "title": row.get("title") or "", "removed_files": removed_files}


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _as_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default




_BIBLE_ALIAS_V2 = {
    "gen": 1, "1mo": 1, "1 mo": 1, "1 mose": 1, "1 buch mose": 1, "erstes buch mose": 1,
    "ex": 2, "2mo": 2, "2 mo": 2, "2 mose": 2, "2 buch mose": 2, "zweites buch mose": 2,
    "lev": 3, "3mo": 3, "3 mo": 3, "3 mose": 3, "3 buch mose": 3, "drittes buch mose": 3,
    "num": 4, "4mo": 4, "4 mo": 4, "4 mose": 4, "4 buch mose": 4, "viertes buch mose": 4,
    "deut": 5, "5mo": 5, "5 mo": 5, "5 mose": 5, "5 buch mose": 5, "fuenftes buch mose": 5,
    "joh": 43, "jo": 43, "johannes": 43, "röm": 45, "roem": 45, "rom": 45,
    "1ko": 46, "1kor": 46, "1. kor": 46, "2ko": 47, "2kor": 47, "2. kor": 47,
    "1th": 52, "1thes": 52, "1. th": 52, "2th": 53, "2thes": 53, "2. th": 53,
    "1ti": 54, "1tim": 54, "2ti": 55, "2tim": 55, "1pe": 60, "1pet": 60,
    "2pe": 61, "2pet": 61, "1jo": 62, "1joh": 62, "2jo": 63, "2joh": 63,
    "3jo": 64, "3joh": 64, "off": 66, "offb": 66, "offenbarung": 66,
}

_PUBLICATION_SYMBOLS_V2 = (
    "mwb", "w", "ws", "wp", "g", "lfb", "lff", "th", "md", "rr", "bt", "jy",
    "ia", "cl", "kr", "od", "sjj", "lmd", "mrt", "es", "lv", "bh", "fg", "jl"
)

def _normalize_ref_v2(value: str) -> str:
    text = str(value or "").lower().replace("–", "-").replace("—", "-")
    text = text.replace("ö", "oe").replace("ä", "ae").replace("ü", "ue").replace("ß", "ss")
    text = re.sub(r"[\u00a0\t\r\n]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def _parse_verse_spec_v2(spec: str) -> list[int]:
    values=[]
    for part in re.split(r"\s*[,;]\s*", str(spec or "")):
        if not part: continue
        m=re.fullmatch(r"(\d{1,3})\s*-\s*(\d{1,3})",part)
        if m:
            a,b=int(m.group(1)),int(m.group(2))
            values.extend(range(min(a,b),max(a,b)+1))
        elif part.isdigit(): values.append(int(part))
    return list(dict.fromkeys(values))[:80]

def _parse_bible_reference_v2(label: str):
    normalized=_normalize_ref_v2(label).replace('.', '')
    book_number=None; hit=''
    # official table first
    for number,title,_chapters,_testament,aliases in BIBLE_BOOKS_DE:
        names=[title,*aliases]
        for name in sorted(names,key=len,reverse=True):
            candidate=_normalize_ref_v2(name).replace('.', '')
            if re.search(rf"(?:^|[\s(]){re.escape(candidate)}(?=\s|\d|$)",normalized):
                book_number=number;hit=candidate;break
        if book_number: break
    if not book_number:
        for alias,number in sorted(_BIBLE_ALIAS_V2.items(),key=lambda x:len(x[0]),reverse=True):
            candidate=_normalize_ref_v2(alias).replace('.', '')
            if re.search(rf"(?:^|[\s(]){re.escape(candidate)}(?=\s|\d|$)",normalized):
                book_number=number;hit=candidate;break
    if not book_number: return None
    pos=normalized.find(hit)
    tail=normalized[pos+len(hit):]
    m=re.search(r"(\d{1,3})\s*:\s*(\d{1,3}(?:\s*-\s*\d{1,3})?(?:\s*[,;]\s*\d{1,3}(?:\s*-\s*\d{1,3})?)*)",tail)
    if not m: return None
    verses=_parse_verse_spec_v2(m.group(2))
    return (book_number,int(m.group(1)),verses)

def _publication_reference_v2(label: str):
    text=_normalize_ref_v2(label)
    symbols='|'.join(sorted(_PUBLICATION_SYMBOLS_V2,key=len,reverse=True))
    m=re.search(rf"(?:^|\b)({symbols})(\d{{2}})?(?=\s|\d|\b)",text,re.I)
    if not m: return None
    symbol=m.group(1).lower(); yy=m.group(2)
    year=(2000+int(yy)) if yy and int(yy)<=40 else ((1900+int(yy)) if yy else None)
    lesson=None
    lm=re.search(r"(?:lektion|geschichte|kapitel)\s*(\d{1,4})(?:\s*[-–]\s*(\d{1,4}))?",text,re.I)
    if lm: lesson=int(lm.group(1))
    nums=[int(x) for x in re.findall(r"\d{1,4}",text)]
    paragraph=None
    pm=re.search(r"abs\.?\s*(\d{1,4})",text,re.I)
    if pm: paragraph=int(pm.group(1))
    return {"symbol":symbol,"year":year,"lesson":lesson,"numbers":nums,"paragraph":paragraph}

PUBLICATION_DISPLAY_NAMES = {
    "nwtsty": "Die Bibel – Neue-Welt-Übersetzung (Studienausgabe)",
    "nwt": "Die Bibel – Neue-Welt-Übersetzung",
    "w": "Der Wachtturm – Studienausgabe",
    "ws": "Der Wachtturm – Studienausgabe",
    "wp": "Der Wachtturm – Öffentlichkeitsausgabe",
    "mwb": "Unser Leben und Dienst als Christ – Arbeitsheft",
    "lfb": "Was wir aus der Bibel lernen können",
    "lff": "Glücklich – für immer",
    "lmd": "Liebt Menschen, macht sie zu Jüngern",
    "th": "Lesen und Lehren",
    "sjj": "Singt voller Freude für Jehova",
    "rr": "Die reine Anbetung Jehovas – endlich wiederhergestellt",
    "jy": "Jesus – der Weg, die Wahrheit, das Leben",
    "bt": "Legt gründlich Zeugnis ab für Gottes Königreich",
}

def _publication_display(title, symbol, year=None):
    title = str(title or "").strip()
    symbol = str(symbol or "").strip().lower()
    base_symbol = re.sub(r"\d{2,4}$", "", symbol)
    if title and title.lower() not in {symbol, base_symbol, "publikation", "allgemeine notizen"}:
        return title
    label = PUBLICATION_DISPLAY_NAMES.get(symbol) or PUBLICATION_DISPLAY_NAMES.get(base_symbol)
    if not label:
        return title or symbol.upper() or "Nicht zugeordnete Einträge"
    year_match = re.search(r"(19|20)\d{2}", symbol)
    display_year = str(year or "").strip() or (year_match.group(0) if year_match else "")
    return f"{label} {display_year}".strip()

class StudyServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.frontend_lock = threading.Lock()
        self.frontend_status = {
            "state": "waiting",
            "stage": "server-ready",
            "message": "",
            "updated_at": utc_now(),
        }
        self.native_player_lock = threading.Lock()
        self.native_player_sessions: dict[str, dict[str, Any]] = {}

    def set_frontend_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        state = str(payload.get("state") or "waiting")[:32]
        stage = str(payload.get("stage") or "unknown")[:128]
        message = str(payload.get("message") or "")[:4000]
        with self.frontend_lock:
            self.frontend_status = {
                "state": state,
                "stage": stage,
                "message": message,
                "updated_at": utc_now(),
            }
            return dict(self.frontend_status)

    def get_frontend_status(self) -> dict[str, Any]:
        with self.frontend_lock:
            return dict(self.frontend_status)

    def create_native_player_session(self, payload: dict[str, Any]) -> str:
        session_id = uuid.uuid4().hex
        now = time.monotonic()
        with self.native_player_lock:
            self.native_player_sessions = {
                key: value for key, value in self.native_player_sessions.items()
                if now - float(value.get("created_at", now)) < 600
            }
            if len(self.native_player_sessions) >= 24:
                oldest = sorted(self.native_player_sessions.items(), key=lambda item: float(item[1].get("created_at", now)))[:8]
                for key, _value in oldest:
                    self.native_player_sessions.pop(key, None)
            self.native_player_sessions[session_id] = {"created_at": now, "payload": payload}
        return session_id

    def take_native_player_session(self, session_id: str) -> dict[str, Any] | None:
        with self.native_player_lock:
            item = self.native_player_sessions.pop(str(session_id or ""), None)
        if not item:
            return None
        return dict(item.get("payload") or {})


class Handler(BaseHTTPRequestHandler):
    server_version = f"LiMaDStudy/{VERSION}"

    def log_message(self, fmt, *args):
        return

    def _send(self, body: bytes, content_type: str, status: int = 200, headers: dict[str, str] | None = None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store" if self.path.startswith("/api/") or self.path in {"/", "/index.html"} or self.path.startswith("/js/") or self.path.startswith("/css/") else "public,max-age=3600")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, target: Path, content_type: str | None = None, headers: dict[str, str] | None = None):
        target = Path(target)
        size = target.stat().st_size
        start, end, status = 0, max(0, size - 1), 200
        range_value = str(self.headers.get("Range") or "").strip()
        if range_value:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_value)
            if not match or size <= 0:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            first, last = match.groups()
            if first:
                start = int(first)
                end = int(last) if last else size - 1
            elif last:
                length = min(int(last), size)
                start = size - length
                end = size - 1
            if start < 0 or end < start or start >= size:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            end = min(end, size - 1)
            status = 206
        length = max(0, end - start + 1)
        self.send_response(status)
        self.send_header("Content-Type", content_type or mime_type(target))
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "private,max-age=3600")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        self.end_headers()
        if length <= 0:
            return
        with target.open("rb") as stream:
            stream.seek(start)
            remaining = length
            while remaining > 0:
                chunk = stream.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    break
                remaining -= len(chunk)


    def _proxy_remote_media(self, remote_url: str, head_only: bool = False):
        remote_url = safe_remote_media_url(remote_url)
        if not remote_url:
            raise PermissionError("Ungültige oder nicht erlaubte Medienadresse.")
        requested_range = str(self.headers.get("Range") or "").strip()
        upstream_range = requested_range or ("bytes=0-0" if head_only else "bytes=0-")

        def open_remote(range_value: str, if_range: str = ""):
            headers = {
                "User-Agent": "jwlibrary-android",
                "Accept": "*/*",
                "Accept-Encoding": "identity",
                "Connection": "close",
            }
            if range_value:
                headers["Range"] = range_value
            if if_range:
                headers["If-Range"] = if_range
            request = urllib.request.Request(remote_url, headers=headers, method="GET")
            return urllib.request.urlopen(request, timeout=60)

        try:
            response = open_remote(upstream_range)
        except urllib.error.HTTPError as error:
            if error.code == 416:
                self.send_response(416)
                self.send_header("Content-Range", error.headers.get("Content-Range") or "bytes */*")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            raise

        content_start = 0
        content_range = response.headers.get("Content-Range") or ""
        range_match = re.fullmatch(r"bytes\s+(\d+)-(\d+)/(\d+|\*)", content_range.strip(), re.I)
        total_size = int(range_match.group(3)) if range_match and range_match.group(3) != "*" else None
        if range_match:
            content_start = int(range_match.group(1))
        elif requested_range:
            requested_match = re.fullmatch(r"bytes=(\d+)-(?:\d*)", requested_range)
            if requested_match:
                content_start = int(requested_match.group(1))

        origin_etag = str(response.headers.get("ETag") or "").strip()
        origin_modified = str(response.headers.get("Last-Modified") or "").strip()
        if_range_value = origin_etag or origin_modified
        status = int(getattr(response, "status", 200) or 200)
        content_length = response.headers.get("Content-Length")
        response_content_range = content_range
        if head_only and not requested_range and range_match:
            status = 200
            content_length = range_match.group(3) if range_match.group(3) != "*" else content_length
            response_content_range = ""
        self.send_response(status)
        self.send_header("Content-Type", response.headers.get("Content-Type") or "application/octet-stream")
        if content_length is not None:
            self.send_header("Content-Length", content_length)
        if response_content_range:
            self.send_header("Content-Range", response_content_range)
        self.send_header("Accept-Ranges", "bytes")
        if origin_etag:
            self.send_header("ETag", origin_etag)
        if origin_modified:
            self.send_header("Last-Modified", origin_modified)
        self.send_header("Cache-Control", "private,max-age=1800")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Connection", "close")
        self.end_headers()
        if head_only:
            response.close()
            return

        expected_length = None
        try:
            expected_length = int(content_length) if content_length is not None else None
        except (TypeError, ValueError):
            expected_length = None

        def resume_stream(resume_at: int):
            retry = open_remote(f"bytes={resume_at}-", if_range_value)
            retry_status = int(getattr(retry, "status", 200) or 200)
            retry_range = str(retry.headers.get("Content-Range") or "")
            retry_match = re.fullmatch(r"bytes\s+(\d+)-(\d+)/(\d+|\*)", retry_range.strip(), re.I)
            valid = retry_status == 206 and retry_match and int(retry_match.group(1)) == resume_at
            retry_etag = str(retry.headers.get("ETag") or "").strip()
            retry_modified = str(retry.headers.get("Last-Modified") or "").strip()
            if origin_etag and retry_etag and retry_etag != origin_etag:
                valid = False
            if origin_modified and retry_modified and retry_modified != origin_modified:
                valid = False
            if total_size is not None and retry_match and retry_match.group(3) != "*" and int(retry_match.group(3)) != total_size:
                valid = False
            if not valid:
                retry.close()
                raise OSError("Die Medienquelle hat sich während der Wiedergabe geändert.")
            return retry

        sent = 0
        retries = 0
        stream = response
        while True:
            try:
                chunk = stream.read(256 * 1024)
                if not chunk:
                    stream.close()
                    if expected_length is None or sent >= expected_length:
                        break
                    retries += 1
                    if retries > 3:
                        self.close_connection = True
                        break
                    try:
                        stream = resume_stream(content_start + sent)
                        continue
                    except Exception:
                        self.close_connection = True
                        break
                self.wfile.write(chunk)
                sent += len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                stream.close()
                break
            except (TimeoutError, socket.timeout, http.client.IncompleteRead, urllib.error.URLError, OSError):
                stream.close()
                if expected_length is not None and sent >= expected_length:
                    break
                retries += 1
                if retries > 3:
                    self.close_connection = True
                    break
                try:
                    stream = resume_stream(content_start + sent)
                except Exception:
                    self.close_connection = True
                    break

    def do_HEAD(self):
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if parsed.path == "/api/media/proxy":
                self._proxy_remote_media((query.get("url") or [""])[0], head_only=True)
                return
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
        except Exception as exc:
            self.send_response(502)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            body = str(exc).encode("utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def _json(self, value: Any, status: int = 200):
        self._send(_json_bytes(value), "application/json; charset=utf-8", status)

    def _error(self, exc: Exception, status: int = 400):
        self._json({"ok": False, "error": str(exc), "type": exc.__class__.__name__}, status)

    def _body_json(self) -> dict:
        length = _as_int(self.headers.get("Content-Length"), 0)
        if length < 0 or length > MAX_JSON:
            raise ValueError("JSON-Anfrage ist zu groß.")
        data = self.rfile.read(length) if length else b"{}"
        return json.loads(data.decode("utf-8"))

    def _upload(self, expected_ext: str) -> tuple[Path, str]:
        content_type = self.headers.get("Content-Type", "")
        match = re.search(r"boundary=(?:\"([^\"]+)\"|([^;]+))", content_type)
        if not match:
            raise ValueError("Multipart-Grenze fehlt.")
        boundary = (match.group(1) or match.group(2)).encode("utf-8")
        length = _as_int(self.headers.get("Content-Length"), 0)
        if length <= 0 or length > MAX_UPLOAD:
            raise ValueError("Uploadgröße ist ungültig.")
        raw_fd, raw_name = tempfile.mkstemp(prefix="limad-upload-", dir=PATHS.cache)
        os.close(raw_fd)
        raw_path = Path(raw_name)
        try:
            remaining = length
            with raw_path.open("wb") as output:
                while remaining:
                    chunk = self.rfile.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise ValueError("Upload wurde vorzeitig beendet.")
                    output.write(chunk)
                    remaining -= len(chunk)
            with raw_path.open("rb") as stream:
                head = stream.read(min(length, 256 * 1024))
                split = head.find(b"\r\n\r\n")
                if split < 0:
                    raise ValueError("Uploadkopf konnte nicht gelesen werden.")
                header = head[:split].decode("utf-8", errors="replace")
                file_start = split + 4
                filename_match = re.search(r'filename="([^"]+)"', header)
                filename = Path(filename_match.group(1) if filename_match else f"upload{expected_ext}").name
                if not filename.lower().endswith(expected_ext):
                    raise ValueError(f"Erwartet wird eine {expected_ext}-Datei.")
                tail_size = min(length, len(boundary) + 65536)
                stream.seek(length - tail_size)
                tail = stream.read(tail_size)
                end_marker = b"\r\n--" + boundary
                relative_end = tail.rfind(end_marker)
                if relative_end < 0:
                    raise ValueError("Uploadende konnte nicht bestimmt werden.")
                file_end = length - tail_size + relative_end
            clean_fd, clean_name = tempfile.mkstemp(prefix="limad-file-", suffix=expected_ext, dir=PATHS.cache)
            os.close(clean_fd)
            clean_path = Path(clean_name)
            with raw_path.open("rb") as source, clean_path.open("wb") as target:
                source.seek(file_start)
                remaining = file_end - file_start
                while remaining > 0:
                    chunk = source.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    target.write(chunk)
                    remaining -= len(chunk)
            return clean_path, filename
        finally:
            raw_path.unlink(missing_ok=True)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if path == "/api/media/proxy":
                self._proxy_remote_media((query.get("url") or [""])[0])
                return
            if path == "/api/frontend/status":
                self._json({"ok": True, **self.server.get_frontend_status()})
                return
            if path == "/api/assistant/state":
                self._json({"ok": True, "state": assistant_state(), "projects": assistant_projects()})
                return
            if path == "/api/assistant/projects":
                self._json({"ok": True, "projects": assistant_projects()})
                return
            match = re.fullmatch(r"/api/assistant/projects/([a-f0-9]+)/messages", path)
            if match:
                self._json({"ok": True, "messages": assistant_project_messages(match.group(1))})
                return
            if path in {"/api/health", "/api/status"}:
                seed = ensure_seed()
                self._json({"ok": True, "app": APP_NAME, "version": VERSION, "time": utc_now(), "seed": seed, "database": str(PATHS.database), "settings": {"language_index": DB.setting("language_index", "2"), "theme": DB.setting("theme", "light"), "font_size": DB.setting("font_size", "100")}, "counts": {"languages": DB.scalar("SELECT COUNT(*) FROM languages") or 0, "catalog": DB.scalar("SELECT COUNT(*) FROM catalog_publications") or 0, "publications": DB.scalar("SELECT COUNT(*) FROM publications") or 0, "documents": DB.scalar("SELECT COUNT(*) FROM documents") or 0}})
                return
            if path == "/api/home":
                language=(query.get("language") or [None])[0]
                self._json(home_payload(language_index=_as_int(language) if language not in (None,"") else None))
                return
            if path == "/api/library":
                rows = DB.rows('''SELECT p.*,l.english_name AS language_name,l.vernacular_name AS language_vernacular,
                    (SELECT COUNT(*) FROM documents d WHERE d.publication_id=p.id) AS document_count
                    FROM publications p LEFT JOIN languages l ON l.id=p.language_index ORDER BY COALESCE(p.last_opened_at,p.installed_at) DESC''')
                for row in rows:
                    row["cover_url"] = f"/api/publications/{urllib.parse.quote(row['id'])}/cover"
                self._json(enrich_library_items(rows))
                return
            match = re.fullmatch(r"/api/publications/([^/]+)/documents", path)
            if match:
                pub_id = urllib.parse.unquote(match.group(1))
                self._json(DB.rows("SELECT id,source_document_id,meps_document_id,chapter_number,section_number,title,toc_title,subtitle,paragraph_count,sort_order FROM documents WHERE publication_id=? ORDER BY sort_order", (pub_id,)))
                return
            match = re.fullmatch(r"/api/publications/([^/]+)/cover", path)
            if match:
                pub_id = urllib.parse.unquote(match.group(1))
                rows = DB.rows("SELECT * FROM publications WHERE id=?", (pub_id,))
                if not rows:
                    raise FileNotFoundError("Publikation fehlt.")
                publication = rows[0]
                for field in ("cover_path", "thumbnail_path"):
                    cover = Path(str(publication.get(field) or ""))
                    if cover.is_file() and cover.stat().st_size > 0:
                        self._send(cover.read_bytes(), mime_type(cover), headers={"Cache-Control": "public,max-age=86400"})
                        return
                matches = DB.rows("""SELECT catalog_id FROM catalog_publications
                    WHERE key_symbol=? AND language_index=? AND year=? AND issue_tag=?
                    ORDER BY catalog_id DESC LIMIT 1""", (
                    publication.get("key_symbol") or "", int(publication.get("language_index") or 0),
                    int(publication.get("year") or 0), int(publication.get("issue_tag") or 0)
                ))
                if not matches:
                    raise FileNotFoundError("Cover fehlt.")
                body, ctype = cover_bytes(int(matches[0]["catalog_id"]))
                self._send(body, ctype, headers={"Cache-Control": "public,max-age=86400"})
                return
            match = re.fullmatch(r"/api/documents/(\d+)/render", path)
            if match:
                self._send(render_document(int(match.group(1))).encode("utf-8"), "text/html; charset=utf-8")
                return
            match = re.fullmatch(r"/api/documents/(\d+)", path)
            if match:
                rows = DB.rows('''SELECT d.id,d.publication_id,d.source_document_id,d.meps_document_id,d.title,d.toc_title,d.subtitle,d.paragraph_count,p.title AS publication_title
                    FROM documents d JOIN publications p ON p.id=d.publication_id WHERE d.id=?''', (int(match.group(1)),))
                if not rows:
                    raise FileNotFoundError("Dokument fehlt.")
                self._json(rows[0])
                return
            if path == "/api/search":
                q = (query.get("q") or [""])[0].strip()
                limit = min(_as_int((query.get("limit") or [100])[0], 100), 300)
                if not q:
                    self._json([])
                else:
                    safe = " ".join(re.findall(r"[\wÀ-ž]+", q))
                    rows = DB.rows('''SELECT f.document_id,d.title,p.title AS publication_title,snippet(documents_fts,1,'<mark>','</mark>',' … ',24) AS snippet
                        FROM documents_fts f JOIN documents d ON d.id=f.document_id JOIN publications p ON p.id=d.publication_id
                        WHERE documents_fts MATCH ? ORDER BY rank LIMIT ?''', (safe, limit))
                    self._json(rows)
                return
            if path == "/api/search/all":
                # Gemeinsame Suche über Bibel/Publikationen (bestehende FTS-Tabelle,
                # deckt Bibeltext und Einsichten ab, da beides als documents gespeichert
                # ist), sowie zusätzlich Notizen und Medien-Titel/Untertitel.
                q = (query.get("q") or [""])[0].strip()
                limit = min(_as_int((query.get("limit") or [60])[0], 60), 200)
                if len(q) < 2:
                    self._json({"query": q, "results": []})
                    return
                results: list[dict] = []
                safe = " ".join(re.findall(r"[\wÀ-ž]+", q))
                if safe:
                    for row in DB.rows(
                        '''SELECT f.document_id,d.title,p.title AS publication_title,p.key_symbol,p.category,p.publication_type,
                        snippet(documents_fts,1,'<mark>','</mark>',' … ',24) AS snippet
                        FROM documents_fts f JOIN documents d ON d.id=f.document_id JOIN publications p ON p.id=d.publication_id
                        WHERE documents_fts MATCH ? ORDER BY rank LIMIT ?''', (safe, limit),
                    ):
                        is_bible = (
                            "bible" in str(row.get("category") or "").lower()
                            or "bible" in str(row.get("publication_type") or "").lower()
                            or str(row.get("key_symbol") or "").lower() in ("nwt", "nwtsty", "bi12", "rbi8")
                        )
                        results.append({
                            "kind": "bible" if is_bible else "publication",
                            "title": row.get("title"),
                            "subtitle": row.get("publication_title"),
                            "snippet": row.get("snippet"),
                            "document_id": row.get("document_id"),
                        })
                needle = f"%{q}%"
                for row in DB.rows(
                    '''SELECT n.id,n.title,n.content,n.block_identifier,d.id AS document_id,d.title AS document_title
                    FROM local_notes n JOIN documents d ON d.id=n.document_id
                    WHERE n.title LIKE ? OR n.content LIKE ? ORDER BY n.modified_at DESC LIMIT ?''',
                    (needle, needle, limit),
                ):
                    results.append({
                        "kind": "note", "title": row.get("title") or "Notiz", "subtitle": row.get("document_title"),
                        "snippet": (row.get("content") or "")[:160], "document_id": row.get("document_id"),
                        "block_identifier": row.get("block_identifier"),
                    })
                for row in DB.rows(
                    '''SELECT n.note_id,n.backup_id,n.title,n.content,n.block_identifier,r.document_row_id AS document_id,d.title AS document_title
                    FROM notes n JOIN backup_resolution r ON r.backup_id=n.backup_id AND r.location_id=n.location_id
                    JOIN documents d ON d.id=r.document_row_id
                    WHERE n.title LIKE ? OR n.content LIKE ? ORDER BY n.last_modified DESC LIMIT ?''',
                    (needle, needle, limit),
                ):
                    results.append({
                        "kind": "note", "title": row.get("title") or "Notiz", "subtitle": row.get("document_title"),
                        "snippet": (row.get("content") or "")[:160], "document_id": row.get("document_id"),
                        "block_identifier": row.get("block_identifier"),
                    })
                for row in DB.rows(
                    '''SELECT m.id,m.label,m.caption,m.mime_type,p.title AS publication_title
                    FROM media m JOIN publications p ON p.id=m.publication_id
                    WHERE m.label LIKE ? OR m.caption LIKE ? LIMIT ?''',
                    (needle, needle, limit),
                ):
                    kind = "video" if "video" in str(row.get("mime_type") or "") else ("audio" if "audio" in str(row.get("mime_type") or "") else "image")
                    results.append({
                        "kind": kind, "title": row.get("label") or row.get("caption") or "Medium",
                        "subtitle": row.get("publication_title"), "snippet": row.get("caption") or "", "media_id": row.get("id"),
                    })
                self._json({"query": q, "results": results[: limit * 3]})
                return
            if path == "/api/languages":
                q = (query.get("q") or [""])[0]
                self._json(languages(query=q, limit=min(_as_int((query.get("limit") or [2000])[0], 2000), 5000), offset=max(_as_int((query.get("offset") or [0])[0], 0), 0), available_only=(query.get("all") or ["0"])[0] != "1"))
                return
            if path == "/api/catalog/publications":
                language = (query.get("language") or [None])[0]
                q = (query.get("q") or [""])[0]
                kind = (query.get("kind") or [""])[0]
                newest = (query.get("newest") or ["0"])[0] == "1"
                self._json(catalog_publications(language_index=_as_int(language) if language not in (None, "") else None, query=q, kind=kind, limit=min(_as_int((query.get("limit") or [300])[0], 300), 1000), offset=_as_int((query.get("offset") or [0])[0], 0), newest=newest))
                return
            if path == "/api/publication-catalog":
                language = _as_int((query.get("language") or [2])[0], 2)
                category = (query.get("category") or ["latest"])[0]
                q = (query.get("q") or [""])[0]
                self._json(live_publications(language_index=language, category=category, query=q, limit=min(_as_int((query.get("limit") or [300])[0], 300), 1000), offset=_as_int((query.get("offset") or [0])[0], 0)))
                return
            match = re.fullmatch(r"/api/catalog/(\d+)/cover", path)
            if match:
                body, ctype = cover_bytes(int(match.group(1)))
                self._send(body, ctype, headers={"Cache-Control": "public,max-age=86400"})
                return
            match = re.fullmatch(r"/api/catalog/(\d+)/options", path)
            if match:
                self._json(download_options(int(match.group(1))))
                return
            match = re.fullmatch(r"/api/catalog/(\d+)/detail", path)
            if match:
                self._json(publication_detail(int(match.group(1))))
                return
            if path == "/api/media":
                self._json(list_media((query.get("type") or [""])[0],(query.get("publication_id") or [None])[0]))
                return
            if path == "/api/media/catalog":
                kind=(query.get("type") or ["video"])[0]
                language_index=_as_int((query.get("language") or [2])[0],2)
                category=(query.get("category") or [""])[0]
                self._json(mediator_catalog(kind,language_symbol(language_index),category))
                return
            if path == "/api/media/progress":
                self._json(get_progress((query.get("media_key") or [""])[0]))
                return
            if path == "/api/media/downloads":
                self._json(list_remote_downloads())
                return
            match = re.fullmatch(r"/api/media/downloaded/([A-Za-z0-9_-]+)", path)
            if match:
                target = downloaded_media_file(match.group(1))
                if not target:
                    self._send(b"Nicht gefunden", "text/plain; charset=utf-8", 404)
                    return
                self._send_file(target)
                return
            if path == "/api/bibles":
                language=(query.get("language") or [None])[0]
                self._json(bible_library(_as_int(language) if language not in (None,"") else None))
                return
            match = re.fullmatch(r"/api/bibles/([^/]+)/navigation", path)
            if match:
                self._json(bible_navigation(urllib.parse.unquote(match.group(1))))
                return
            match = re.fullmatch(r"/api/bibles/([^/]+)/overview", path)
            if match:
                self._json(bible_overview(urllib.parse.unquote(match.group(1))))
                return
            match = re.fullmatch(r"/api/bibles/([^/]+)/chapter/(\d+)/(\d+)/render", path)
            if match:
                self._send(render_bible_chapter(urllib.parse.unquote(match.group(1)), int(match.group(2)), int(match.group(3))).encode("utf-8"), "text/html; charset=utf-8")
                return
            match = re.fullmatch(r"/api/bibles/([^/]+)/chapter/(\d+)/(\d+)", path)
            if match:
                publication_id = urllib.parse.unquote(match.group(1))
                book_number = int(match.group(2))
                chapter_number = int(match.group(3))
                data = bible_chapter(publication_id, book_number, chapter_number)
                data["document_id"] = bible_chapter_document_id(publication_id, book_number, chapter_number)
                self._json(data)
                return
            if path == "/api/bibles/compare":
                self._json(bible_compare(_as_int((query.get("language") or [2])[0], 2), _as_int((query.get("book") or [1])[0], 1), _as_int((query.get("chapter") or [1])[0], 1)))
                return
            if path == "/api/bibles/search":
                self._json(bible_search((query.get("q") or [""])[0], _as_int((query.get("language") or [2])[0], 2), (query.get("publication_id") or [None])[0]))
                return
            if path == "/api/bibles/verse-material":
                document_id = _as_int((query.get("document_id") or [0])[0], 0)
                verse_id = _as_int((query.get("verse_id") or [0])[0], 0)
                verse_number = _as_int((query.get("verse_number") or [0])[0], 0)
                verse_text = (query.get("verse_text") or [""])[0]
                requested_tab = ((query.get("tab") or [""])[0] or "").strip().lower() or None
                if document_id <= 0 or verse_id < 0:
                    raise ValueError("Bibelvers ist unvollständig.")
                self._json(verse_material(document_id, verse_id, verse_number, verse_text, requested_tab=requested_tab))
                return
            if path == "/api/bibles/view-state":
                self._json(view_state(_as_int((query.get("language") or [2])[0], 2)))
                return
            if path == "/api/playlists":
                self._json(list_playlists())
                return
            if path == "/api/catalog/status":
                self._json(catalog_status())
                return
            if path == "/api/downloads":
                self._json(download_jobs())
                return
            if path == "/api/backups":
                rows=DB.rows("SELECT b.*,COALESCE(SUM(CASE WHEN r.status LIKE 'resolved_%' THEN 1 ELSE 0 END),0) AS resolved_count,COALESCE(SUM(CASE WHEN r.status LIKE 'missing_%' THEN 1 ELSE 0 END),0) AS missing_count FROM backup_imports b LEFT JOIN backup_resolution r ON r.backup_id=b.id GROUP BY b.id ORDER BY b.imported_at DESC")
                self._json(rows)
                return
            if path == "/api/backups/resolution":
                backup_id=(query.get("backup_id") or [None])[0]
                self._json(resolution_report(backup_id))
                return
            if path == "/api/backups/exports":
                self._json(DB.rows("SELECT * FROM backup_export_runs ORDER BY created_at DESC LIMIT 100"))
                return
            match = re.fullmatch(r"/api/documents/(\d+)/study", path)
            if match:
                document_id=int(match.group(1))
                doc_rows=DB.rows("SELECT d.*,p.title AS publication_title,p.key_symbol,p.language_index FROM documents d JOIN publications p ON p.id=d.publication_id WHERE d.id=?",(document_id,))
                if not doc_rows: raise FileNotFoundError("Dokument fehlt.")
                doc=doc_rows[0]
                nav=DB.rows("SELECT id,title,toc_title,sort_order FROM documents WHERE publication_id=? ORDER BY sort_order",(doc["publication_id"],))
                related_notes=[n for n in notes(limit=2000) if int(n.get("document_id") or n.get("source_document_id") or -1) in {document_id,int(doc.get("meps_document_id") or -2),int(doc.get("source_document_id") or -3)}]
                self._json({"document":doc,"navigation":nav,"notes":related_notes,"marks":document_marks(document_id),"mark_groups":document_mark_groups(document_id),"position":reading_position(document_id),"input_fields":input_fields_for_document(document_id),"questions":DB.rows("SELECT * FROM questions WHERE publication_id=? AND document_source_id=? ORDER BY question_index",(doc["publication_id"],doc["source_document_id"])),"footnotes":DB.rows("SELECT * FROM footnotes WHERE publication_id=? AND document_source_id=? ORDER BY footnote_index",(doc["publication_id"],doc["source_document_id"])),"bookmarks":[b for b in bookmarks() if int(b.get("document_id") or -1)==document_id]})
                return
            if path == "/api/notes":
                self._json(notes(query=(query.get("q") or [""])[0]))
                return
            if path == "/api/tags":
                self._json(tags())
                return
            if path == "/api/tags/entries":
                tag_name=str((query.get("name") or [""])[0]).strip()
                if not tag_name:
                    self._json([])
                    return
                local_entries=DB.rows("""SELECT n.id,'local' AS source,n.title,n.content,n.block_identifier,n.modified_at AS modified,
                    d.id AS document_id,d.title AS document_title,p.title AS publication_title,p.key_symbol
                    FROM local_note_tags nt JOIN local_notes n ON n.id=nt.note_id
                    JOIN documents d ON d.id=n.document_id JOIN publications p ON p.id=d.publication_id
                    WHERE lower(nt.tag_name)=lower(?) ORDER BY n.modified_at DESC""",(tag_name,))
                imported_entries=DB.rows("""SELECT CAST(COALESCE(n.note_id,tm.tag_map_id) AS TEXT)||':'||tm.backup_id AS id,'backup' AS source,
                    COALESCE(NULLIF(n.title,''),NULLIF(l.title,''),t.name) AS title,COALESCE(n.content,'') AS content,
                    n.block_identifier,n.last_modified AS modified,
                    COALESCE(br.document_row_id,d.id) AS document_id,COALESCE(d.title,l.title,'') AS document_title,
                    COALESCE(p.title,l.key_symbol,'') AS publication_title,l.key_symbol
                    FROM tag_map tm JOIN tags t ON t.backup_id=tm.backup_id AND t.tag_id=tm.tag_id
                    LEFT JOIN notes n ON n.backup_id=tm.backup_id AND n.note_id=tm.note_id
                    LEFT JOIN user_locations l ON l.backup_id=tm.backup_id AND l.location_id=COALESCE(tm.location_id,n.location_id)
                    LEFT JOIN backup_resolution br ON br.backup_id=l.backup_id AND br.location_id=l.location_id
                    LEFT JOIN documents d ON d.id=br.document_row_id
                    LEFT JOIN publications p ON p.id=d.publication_id
                    WHERE lower(t.name)=lower(?) ORDER BY COALESCE(n.last_modified,n.created,'') DESC""",(tag_name,))
                entries=local_entries+imported_entries
                for item in entries:
                    item["publication_display"]=_publication_display(item.get("publication_title"),item.get("key_symbol"),item.get("publication_year"))
                self._json(entries)
                return
            if path == "/api/notes/organized":
                query_text=str((query.get("q") or [""])[0]).strip()
                needle=f"%{query_text}%"
                local_notes=DB.rows("""SELECT n.id,'local' AS source,n.title,n.content,n.block_identifier,n.created_at AS created,n.modified_at AS modified,
                    d.id AS document_id,d.title AS document_title,p.id AS publication_id,p.title AS publication_title,p.key_symbol,p.year AS publication_year
                    FROM local_notes n JOIN documents d ON d.id=n.document_id JOIN publications p ON p.id=d.publication_id
                    WHERE (?='' OR n.title LIKE ? OR n.content LIKE ? OR p.title LIKE ?) ORDER BY p.title COLLATE NOCASE,n.modified_at DESC""",
                    (query_text,needle,needle,needle))
                imported_notes=DB.rows("""SELECT CAST(n.note_id AS TEXT)||':'||n.backup_id AS id,'backup' AS source,n.title,n.content,n.block_identifier,n.created,n.last_modified AS modified,
                    COALESCE(br.document_row_id,d.id) AS document_id,COALESCE(d.title,l.title,'') AS document_title,
                    p.id AS publication_id,COALESCE(p.title,l.key_symbol,'Allgemeine Notizen') AS publication_title,l.key_symbol,p.year AS publication_year
                    FROM notes n LEFT JOIN user_locations l ON l.backup_id=n.backup_id AND l.location_id=n.location_id
                    LEFT JOIN backup_resolution br ON br.backup_id=l.backup_id AND br.location_id=l.location_id
                    LEFT JOIN documents d ON d.id=br.document_row_id
                    LEFT JOIN publications p ON p.id=d.publication_id
                    WHERE (?='' OR n.title LIKE ? OR n.content LIKE ? OR l.title LIKE ? OR p.title LIKE ?)
                    ORDER BY publication_title COLLATE NOCASE,n.last_modified DESC""",
                    (query_text,needle,needle,needle,needle))
                answer_notes=DB.rows("""SELECT 'answer:'||f.document_id||':'||f.text_tag AS id,'answer' AS source,
                    'Antwort: '||f.text_tag AS title,f.value AS content,NULL AS block_identifier,f.updated_at AS created,f.updated_at AS modified,
                    d.id AS document_id,d.title AS document_title,p.id AS publication_id,p.title AS publication_title,p.key_symbol,p.year AS publication_year
                    FROM local_input_fields f JOIN documents d ON d.id=f.document_id JOIN publications p ON p.id=d.publication_id
                    WHERE trim(COALESCE(f.value,''))<>'' AND (?='' OR f.text_tag LIKE ? OR f.value LIKE ? OR d.title LIKE ? OR p.title LIKE ?)
                    ORDER BY p.title COLLATE NOCASE,f.updated_at DESC""",
                    (query_text,needle,needle,needle,needle))
                organized=local_notes+imported_notes+answer_notes
                for item in organized:
                    item["publication_display"]=_publication_display(item.get("publication_title"),item.get("key_symbol"),item.get("publication_year"))
                self._json(organized)
                return
            if path == "/api/marks/publications":
                rows=DB.rows("""WITH all_marks AS (
                    SELECT p.id AS publication_id,p.title AS publication_title,p.key_symbol,p.year AS publication_year FROM local_marks m JOIN documents d ON d.id=m.document_id JOIN publications p ON p.id=d.publication_id
                    UNION ALL SELECT p.id,p.title,p.key_symbol,p.year FROM mark_groups g JOIN documents d ON d.id=g.document_id JOIN publications p ON p.id=d.publication_id
                    UNION ALL SELECT p.id,COALESCE(p.title,l.key_symbol,''),l.key_symbol,p.year FROM user_marks u
                    LEFT JOIN user_locations l ON l.backup_id=u.backup_id AND l.location_id=u.location_id
                    LEFT JOIN backup_resolution res ON res.backup_id=l.backup_id AND res.location_id=l.location_id
                    LEFT JOIN documents d ON d.id=res.document_row_id LEFT JOIN publications p ON p.id=d.publication_id
                    LEFT JOIN imported_mark_overrides o ON o.backup_id=u.backup_id AND o.user_mark_id=u.user_mark_id WHERE COALESCE(o.hidden,0)=0
                ) SELECT publication_id,publication_title,key_symbol,publication_year,COUNT(*) AS entry_count FROM all_marks GROUP BY publication_id,publication_title,key_symbol,publication_year ORDER BY publication_title COLLATE NOCASE""")
                for item in rows:
                    item["publication_display"]=_publication_display(item.get("publication_title"),item.get("key_symbol"),item.get("publication_year"))
                rows.sort(key=lambda item:(item.get("publication_display") or "").casefold())
                self._json(rows)
                return
            if path == "/api/marks":
                paged = (query.get("paged") or ["0"])[0] == "1"
                if not paged:
                    local = DB.rows("""SELECT m.id,'local' AS source,m.color_index,m.style_index,m.block_identifier,m.start_token,m.end_token,d.id AS document_id,d.title AS document_title,p.title AS publication_title FROM local_marks m JOIN documents d ON d.id=m.document_id JOIN publications p ON p.id=d.publication_id ORDER BY m.created_at DESC""")
                    groups = DB.rows("""SELECT g.id,'local' AS source,g.color_index,g.style_index,MIN(r.block_identifier) AS block_identifier,NULL AS start_token,NULL AS end_token,d.id AS document_id,d.title AS document_title,p.title AS publication_title FROM mark_groups g JOIN mark_group_ranges r ON r.group_id=g.id JOIN documents d ON d.id=g.document_id JOIN publications p ON p.id=d.publication_id GROUP BY g.id ORDER BY g.updated_at DESC""")
                    imported = DB.rows("""SELECT CAST(u.user_mark_id AS TEXT)||':'||u.backup_id AS id,'backup' AS source,COALESCE(o.color_index,u.color_index) AS color_index,u.style_index,MIN(br.identifier) AS block_identifier,MIN(br.start_token) AS start_token,MAX(br.end_token) AS end_token,l.document_id,l.title AS document_title,'' AS publication_title FROM user_marks u LEFT JOIN block_ranges br ON br.backup_id=u.backup_id AND br.user_mark_id=u.user_mark_id LEFT JOIN user_locations l ON l.backup_id=u.backup_id AND l.location_id=u.location_id LEFT JOIN imported_mark_overrides o ON o.backup_id=u.backup_id AND o.user_mark_id=u.user_mark_id WHERE COALESCE(o.hidden,0)=0 GROUP BY u.backup_id,u.user_mark_id ORDER BY u.user_mark_id DESC""")
                    self._json(local + groups + imported)
                    return
                limit=max(20,min(200,_as_int((query.get("limit") or [60])[0],60)))
                offset=max(0,_as_int((query.get("offset") or [0])[0],0))
                search=str((query.get("q") or [""])[0]).strip()
                sort=str((query.get("sort") or ["recent"])[0]).strip().lower()
                publication_filter=str((query.get("publication") or [""])[0]).strip()
                needle=f"%{search}%"
                DB.execute("CREATE INDEX IF NOT EXISTS idx_local_marks_created ON local_marks(created_at DESC)")
                DB.execute("CREATE INDEX IF NOT EXISTS idx_user_marks_location ON user_marks(backup_id,location_id,user_mark_id)")
                DB.execute("CREATE INDEX IF NOT EXISTS idx_block_ranges_mark ON block_ranges(backup_id,user_mark_id)")
                sql="""WITH all_marks AS (
                    SELECT m.id AS id,'local' AS source,m.color_index,m.style_index,m.block_identifier,m.start_token,m.end_token,d.id AS document_id,d.title AS document_title,p.id AS publication_id,p.title AS publication_title,p.key_symbol,p.year AS publication_year,m.created_at AS sort_key
                    FROM local_marks m JOIN documents d ON d.id=m.document_id JOIN publications p ON p.id=d.publication_id
                    UNION ALL
                    SELECT g.id,'local',g.color_index,g.style_index,MIN(r.block_identifier),NULL,NULL,d.id,d.title,p.id,p.title,p.key_symbol,p.year,g.updated_at
                    FROM mark_groups g JOIN mark_group_ranges r ON r.group_id=g.id JOIN documents d ON d.id=g.document_id JOIN publications p ON p.id=d.publication_id GROUP BY g.id
                    UNION ALL
                    SELECT CAST(u.user_mark_id AS TEXT)||':'||u.backup_id,'backup',COALESCE(o.color_index,u.color_index),u.style_index,MIN(br.identifier),MIN(br.start_token),MAX(br.end_token),
                        COALESCE(res.document_row_id,d.id,l.document_id),COALESCE(d.title,l.title,''),p.id,COALESCE(p.title,l.key_symbol,''),l.key_symbol,p.year,printf('%020d',u.user_mark_id)
                    FROM user_marks u LEFT JOIN block_ranges br ON br.backup_id=u.backup_id AND br.user_mark_id=u.user_mark_id
                    LEFT JOIN user_locations l ON l.backup_id=u.backup_id AND l.location_id=u.location_id
                    LEFT JOIN backup_resolution res ON res.backup_id=l.backup_id AND res.location_id=l.location_id
                    LEFT JOIN documents d ON d.id=res.document_row_id LEFT JOIN publications p ON p.id=d.publication_id
                    LEFT JOIN imported_mark_overrides o ON o.backup_id=u.backup_id AND o.user_mark_id=u.user_mark_id
                    WHERE COALESCE(o.hidden,0)=0 GROUP BY u.backup_id,u.user_mark_id
                ) SELECT id,source,color_index,style_index,block_identifier,start_token,end_token,document_id,document_title,publication_id,publication_title,key_symbol,publication_year FROM all_marks
                WHERE (?='' OR publication_title LIKE ? OR document_title LIKE ?) AND (?='' OR COALESCE(publication_id,'')=? OR lower(COALESCE(key_symbol,''))=lower(?))
                ORDER BY CASE WHEN ?='publication' THEN publication_title END COLLATE NOCASE, CASE WHEN ?='document' THEN document_title END COLLATE NOCASE, sort_key DESC LIMIT ? OFFSET ?"""
                count_sql="""WITH all_marks AS (
                    SELECT p.id AS publication_id,p.title AS publication_title,p.key_symbol,d.title AS document_title FROM local_marks m JOIN documents d ON d.id=m.document_id JOIN publications p ON p.id=d.publication_id
                    UNION ALL SELECT p.id,p.title,p.key_symbol,d.title FROM mark_groups g JOIN documents d ON d.id=g.document_id JOIN publications p ON p.id=d.publication_id
                    UNION ALL SELECT p.id,COALESCE(p.title,l.key_symbol,''),l.key_symbol,COALESCE(d.title,l.title,'') FROM user_marks u
                    LEFT JOIN user_locations l ON l.backup_id=u.backup_id AND l.location_id=u.location_id
                    LEFT JOIN backup_resolution res ON res.backup_id=l.backup_id AND res.location_id=l.location_id
                    LEFT JOIN documents d ON d.id=res.document_row_id LEFT JOIN publications p ON p.id=d.publication_id
                    LEFT JOIN imported_mark_overrides o ON o.backup_id=u.backup_id AND o.user_mark_id=u.user_mark_id WHERE COALESCE(o.hidden,0)=0
                ) SELECT COUNT(*) FROM all_marks WHERE (?='' OR publication_title LIKE ? OR document_title LIKE ?) AND (?='' OR COALESCE(publication_id,'')=? OR lower(COALESCE(key_symbol,''))=lower(?))"""
                items=DB.rows(sql,(search,needle,needle,publication_filter,publication_filter,publication_filter,sort,sort,limit,offset))
                total=int(DB.scalar(count_sql,(search,needle,needle,publication_filter,publication_filter,publication_filter)) or 0)
                for item in items:
                    item["publication_display"]=_publication_display(item.get("publication_title"),item.get("key_symbol"),item.get("publication_year"))
                self._json({"items":items,"total":total,"offset":offset,"limit":limit,"has_more":offset+len(items)<total})
                return
            if path == "/api/bookmarks":
                self._json(bookmarks())
                return
            if path == "/api/reading-position":
                self._json(reading_position(_as_int((query.get("document_id") or [0])[0], 0)))
                return
            if path == "/api/meetings":
                self._json(meeting_week(_as_int((query.get("offset") or [0])[0],0), language_index=_as_int((query.get("language") or [0])[0],0) or None))
                return
            if path == "/api/meetings/notes":
                document_id=(query.get("document_id") or [None])[0]
                self._json(meeting_notes(_as_int(document_id) if document_id not in (None,"") else None))
                return
            if path == "/api/settings":
                self._json({row["key"]: row["value"] for row in DB.rows("SELECT key,value FROM settings")})
                return
            if path == "/api/resolve":
                link = urllib.parse.unquote((query.get("link") or [""])[0]).strip()
                label = urllib.parse.unquote((query.get("label") or [""])[0]).strip()
                result = {"resolved": False, "kind": "web", "external": link, "label": label or link}
                try:
                    resolve_language = _as_int((query.get("language") or [DB.setting("language_index", "2")])[0], 2)
                    resolve_publication_id = urllib.parse.unquote((query.get("publication_id") or [""])[0]).strip()
                    resolve_document_id = _as_int((query.get("document_id") or [0])[0], 0) or None
                    engine_result = resolve_source(
                        label,
                        link,
                        language_index=resolve_language,
                        publication_id=resolve_publication_id,
                        document_id=resolve_document_id,
                    )
                except Exception as engine_exc:
                    engine_result = None
                    result["engine_error"] = f"{engine_exc.__class__.__name__}: {engine_exc}"
                force_online = str((query.get("refresh") or [""])[0]).lower() in {"1", "true", "yes"}
                local_only = str((query.get("local_only") or [""])[0]).lower() in {"1", "true", "yes"}
                online_preview = None
                if not local_only and (engine_result is None or (not engine_result.get("resolved") and engine_result.get("kind") in {"publication", "web"})):
                    try:
                        online_preview = resolve_online_source(link, label, resolve_language, force=force_online)
                    except Exception as online_exc:
                        online_preview = None
                        if engine_result is not None:
                            engine_result["online_error"] = f"{online_exc.__class__.__name__}: {online_exc}"
                if online_preview:
                    if engine_result is None:
                        engine_result = {"resolved": False, "kind": "publication", "label": label or link, "external": online_preview.get("url") or link}
                    engine_result["online_preview"] = online_preview
                    engine_result["external"] = online_preview.get("url") or engine_result.get("external") or link
                    engine_result.setdefault("missing_message", "Die Publikation ist nicht lokal installiert. Der aktuelle offizielle Artikel wird online angezeigt.")
                if engine_result is not None:
                    if link and not engine_result.get("external"):
                        engine_result["external"] = link
                    self._json(engine_result)
                    return
                combined_label = (label or link).strip()
                # Source Resolver V2: Bible references with comma-separated verses and ranges.
                parsed_bible_v2 = _parse_bible_reference_v2(combined_label)
                if parsed_bible_v2:
                    book_number_v2, chapter_number_v2, verse_numbers_v2 = parsed_bible_v2
                    try:
                        bibles_v2 = bible_library(2)
                        bibles_v2.sort(key=lambda item: (0 if str(item.get("key_symbol") or "").lower() == "nwtsty" else 1 if str(item.get("key_symbol") or "").lower() == "nwt" else 2, str(item.get("title") or "")))
                        if bibles_v2:
                            publication_id_v2 = str(bibles_v2[0]["id"])
                            document_id_v2 = bible_chapter_document_id(publication_id_v2, book_number_v2, chapter_number_v2)
                            chapter_v2 = bible_chapter(publication_id_v2, book_number_v2, chapter_number_v2)
                            pieces_v2=[]; first_verse_id_v2=None
                            wanted_v2=set(verse_numbers_v2)
                            for verse_v2 in chapter_v2.get("verses") or []:
                                label_v2=str(verse_v2.get("label") or "")
                                found_v2=re.match(r"^(\d{1,3})(?:\D|$)",label_v2)
                                if found_v2 and int(found_v2.group(1)) in wanted_v2:
                                    if first_verse_id_v2 is None: first_verse_id_v2=verse_v2.get("id")
                                    pieces_v2.append(f'<section class="context-bible-verse"><b>{found_v2.group(1)}</b> {verse_v2.get("content_html") or ""}</section>')
                            rows_v2=DB.rows("SELECT d.id,d.title,d.toc_title,d.subtitle,d.meps_document_id,d.source_document_id,p.id AS publication_id,p.title AS publication_title,p.key_symbol,p.language_index FROM documents d JOIN publications p ON p.id=d.publication_id WHERE d.id=?",(document_id_v2,))
                            if rows_v2:
                                result.update({"resolved":True,"kind":"bible","document":rows_v2[0],"block_identifier":first_verse_id_v2,"verse_html":"".join(pieces_v2),"reference":combined_label,"verse_numbers":verse_numbers_v2})
                                self._json(result); return
                    except Exception:
                        result["kind"]="bible"
                # Source Resolver V2: exact publication symbol/year before broad catalog fallback.
                pub_ref_v2 = _publication_reference_v2(combined_label)
                if pub_ref_v2:
                    symbol_v2=pub_ref_v2["symbol"]; year_v2=pub_ref_v2["year"]
                    result["kind"]="publication"; result["publication_symbol"]=symbol_v2
                    local_sql_v2="SELECT id,title,key_symbol,year,issue_tag FROM publications WHERE lower(key_symbol)=?"
                    args_v2=[symbol_v2]
                    if year_v2:
                        local_sql_v2+=" AND (year=? OR id LIKE ?)"; args_v2.extend([year_v2,f"%-{year_v2}-%"])
                    local_sql_v2+=" ORDER BY COALESCE(last_opened_at,installed_at) DESC"
                    local_v2=DB.rows(local_sql_v2,tuple(args_v2))
                    search_numbers_v2=[]
                    if pub_ref_v2.get("lesson"): search_numbers_v2.append(pub_ref_v2["lesson"])
                    search_numbers_v2.extend(pub_ref_v2.get("numbers") or [])
                    for publication_v2 in local_v2:
                        candidates_v2=[]
                        for number_v2 in list(dict.fromkeys(search_numbers_v2))[:6]:
                            candidates_v2=DB.rows("SELECT d.id,d.title,d.toc_title,d.subtitle,d.meps_document_id,d.source_document_id,p.id AS publication_id,p.title AS publication_title,p.key_symbol,p.language_index FROM documents d JOIN publications p ON p.id=d.publication_id WHERE p.id=? AND (d.title LIKE ? OR d.toc_title LIKE ? OR d.subtitle LIKE ? OR d.content_html LIKE ?) ORDER BY d.sort_order LIMIT 1",(publication_v2["id"],f"%{number_v2}%",f"%{number_v2}%",f"%{number_v2}%",f"%>{number_v2}<%"))
                            if candidates_v2: break
                        if not candidates_v2:
                            candidates_v2=DB.rows("SELECT d.id,d.title,d.toc_title,d.subtitle,d.meps_document_id,d.source_document_id,p.id AS publication_id,p.title AS publication_title,p.key_symbol,p.language_index FROM documents d JOIN publications p ON p.id=d.publication_id WHERE p.id=? ORDER BY d.sort_order LIMIT 1",(publication_v2["id"],))
                        if candidates_v2:
                            result.update({"resolved":True,"kind":"publication","document":candidates_v2[0],"block_identifier":str(pub_ref_v2.get("paragraph") or "") or None,"reference":combined_label})
                            self._json(result); return
                    try:
                        catalog_v2=catalog_publications(language_index=2,query=symbol_v2,kind="",limit=100,offset=0,newest=True)
                    except Exception:
                        catalog_v2=[]
                    exact_v2=[item for item in catalog_v2 if str(item.get("key_symbol") or "").lower()==symbol_v2 and (not year_v2 or int(item.get("year") or 0)==year_v2)]
                    result["catalog"]=(exact_v2 or [item for item in catalog_v2 if str(item.get("key_symbol") or "").lower()==symbol_v2])[:8]
                meps_id = None
                language_symbol_value = ""
                block_identifier = None
                match = re.search(r"jwpub://p/([^:/:]+):(\d+)(?:[/?#].*)?", link, re.I)
                if match:
                    language_symbol_value, meps_id = match.group(1), int(match.group(2))
                    result["kind"] = "publication"
                else:
                    parsed_link = urllib.parse.urlparse(link)
                    params = urllib.parse.parse_qs(parsed_link.query)
                    raw_docid = (params.get("docid") or params.get("docId") or params.get("wtlocale") or [""])[0]
                    if str(raw_docid).isdigit():
                        meps_id = int(raw_docid)
                        result["kind"] = "publication"
                    block_identifier = (params.get("par") or params.get("paragraph") or params.get("chapter") or [None])[0]
                if meps_id is not None:
                    rows = DB.rows('''SELECT d.id,d.title,d.toc_title,d.subtitle,d.meps_document_id,d.source_document_id,p.id AS publication_id,p.title AS publication_title,p.key_symbol,p.language_index
                        FROM documents d JOIN publications p ON p.id=d.publication_id
                        WHERE (d.meps_document_id=? OR d.source_document_id=?) AND (?='' OR p.language_symbol=? OR p.language_symbol IS NULL)
                        ORDER BY COALESCE(p.last_opened_at,p.installed_at) DESC LIMIT 1''', (meps_id, meps_id, language_symbol_value, language_symbol_value))
                    if rows:
                        result.update({"resolved": True, "document": rows[0], "block_identifier": block_identifier, "kind": "publication"})
                        self._json(result)
                        return
                symbol_match = re.search(r"(?:^|\b)(mwb|w|ws|lfb|lff|rr|bt|jy|ia|cl|kr|od|sjj|lmd)(?:\d{2})?(?:\b|$)", f"{label} {link}", re.I)
                symbol = symbol_match.group(1).lower() if symbol_match else ""
                catalog = []
                if symbol:
                    try:
                        catalog = catalog_publications(language_index=2, query=symbol, kind="", limit=20, offset=0, newest=True)
                    except Exception:
                        catalog = []
                    exact = [item for item in catalog if str(item.get("key_symbol") or "").lower() == symbol]
                    result["catalog"] = (exact or catalog)[:5]
                    result["publication_symbol"] = symbol
                    result["kind"] = "publication"
                lower = f"{label} {link}".lower()
                if any(token in lower for token in ("video", "whiteboard", ".mp4", ".m4v", ".webm")):
                    result["kind"] = "video"
                elif any(token in lower for token in ("audio", ".mp3", ".m4a", ".aac")):
                    result["kind"] = "audio"

                if result["kind"] in {"video", "audio"}:
                    try:
                        words = [w for w in re.findall(r"[\wÀ-ž]+", label.lower()) if len(w) > 2 and w not in {"video", "audio", "zeigen", "zeig", "das", "der", "die"}]
                        media_rows = list_media(result["kind"])
                        def media_score(item):
                            hay = f"{item.get('label','')} {item.get('file_path','')} {item.get('publication_title','')}".lower()
                            return sum(1 for word in words if word in hay)
                        media_rows = sorted(media_rows, key=media_score, reverse=True)
                        if media_rows and (not words or media_score(media_rows[0]) > 0):
                            top = media_rows[0]
                            result["media"] = {
                                "title": top.get("label") or label or ("Video" if result["kind"] == "video" else "Audio"),
                                "url": top.get("url") or "",
                                "image": top.get("preview") or "",
                                "mime_type": top.get("mime_type") or "",
                                "media_key": top.get("media_key") or "",
                                "natural_key": top.get("media_key") or "",
                                "sources": [{"url": top.get("url") or "", "quality": "Lokal", "mime_type": top.get("mime_type") or ""}],
                            }
                    except Exception:
                        pass

                bible_text = label.strip()
                parsed = urllib.parse.urlparse(link)
                params = urllib.parse.parse_qs(parsed.query)
                b_raw = (params.get("b") or params.get("book") or [None])[0]
                c_raw = (params.get("c") or params.get("chapter") or [None])[0]
                v_raw = (params.get("v") or params.get("verse") or params.get("par") or [None])[0]
                book_number = int(b_raw) if str(b_raw or "").isdigit() else None
                chapter_number = int(c_raw) if str(c_raw or "").isdigit() else None
                verse_number = int(str(v_raw).split("-")[0]) if str(v_raw or "").split("-")[0].isdigit() else None
                if book_number is None:
                    normalized = re.sub(r"\s+", " ", bible_text.lower().replace("–", "-")).strip()
                    for number, title, _chapters, _testament, aliases in BIBLE_BOOKS_DE:
                        candidates = [title.lower(), *[a.lower() for a in aliases]]
                        hit = next((name for name in sorted(candidates, key=len, reverse=True) if re.search(rf"(?:^|\s){re.escape(name)}(?:\s|$)", normalized)), None)
                        if not hit:
                            continue
                        tail = normalized[normalized.find(hit) + len(hit):]
                        m = re.search(r"(\d{1,3})\s*:\s*(\d{1,3})(?:\s*[-–]\s*(\d{1,3}))?", tail)
                        if m:
                            book_number, chapter_number, verse_number = number, int(m.group(1)), int(m.group(2))
                            break
                if book_number and chapter_number:
                    try:
                        bibles = bible_library(2)
                        bibles.sort(key=lambda item: (0 if str(item.get("key_symbol") or "").lower() == "nwtsty" else 1 if str(item.get("key_symbol") or "").lower() == "nwt" else 2, str(item.get("title") or "")))
                        if bibles:
                            publication_id = str(bibles[0]["id"])
                            document_id = bible_chapter_document_id(publication_id, book_number, chapter_number)
                            chapter = bible_chapter(publication_id, book_number, chapter_number)
                            verse_id = None
                            verse_html = ""
                            if verse_number:
                                for verse in chapter.get("verses") or []:
                                    label_value = str(verse.get("label") or "")
                                    if label_value == str(verse_number) or re.match(rf"^{verse_number}(?:\D|$)", label_value):
                                        verse_id = verse.get("id")
                                        verse_html = verse.get("content_html") or ""
                                        break
                            rows = DB.rows("SELECT d.id,d.title,d.toc_title,d.subtitle,d.meps_document_id,d.source_document_id,p.id AS publication_id,p.title AS publication_title,p.key_symbol,p.language_index FROM documents d JOIN publications p ON p.id=d.publication_id WHERE d.id=?", (document_id,))
                            if rows:
                                result.update({"resolved": True, "kind": "bible", "document": rows[0], "block_identifier": verse_id, "verse_html": verse_html, "reference": bible_text})
                                self._json(result)
                                return
                    except Exception:
                        result["kind"] = "bible"

                if symbol and not result.get("resolved"):
                    try:
                        nums = [int(x) for x in re.findall(r"\d{1,4}", label)]
                        local = DB.rows("SELECT id,title FROM publications WHERE lower(key_symbol)=? ORDER BY COALESCE(last_opened_at,installed_at) DESC LIMIT 1", (symbol,))
                        if local:
                            publication_id = local[0]["id"]
                            candidates = []
                            if nums:
                                for number in nums[:3]:
                                    candidates = DB.rows("SELECT d.id,d.title,d.toc_title,d.subtitle,d.meps_document_id,d.source_document_id,p.id AS publication_id,p.title AS publication_title,p.key_symbol,p.language_index FROM documents d JOIN publications p ON p.id=d.publication_id WHERE p.id=? AND (d.title LIKE ? OR d.toc_title LIKE ? OR d.subtitle LIKE ?) ORDER BY d.sort_order LIMIT 1", (publication_id, f"%{number}%", f"%{number}%", f"%{number}%"))
                                    if candidates:
                                        break
                            if not candidates:
                                words = [w for w in re.findall(r"[\wÀ-ž]+", label) if len(w) > 3 and not w.isdigit()]
                                for word in words[:5]:
                                    candidates = DB.rows("SELECT d.id,d.title,d.toc_title,d.subtitle,d.meps_document_id,d.source_document_id,p.id AS publication_id,p.title AS publication_title,p.key_symbol,p.language_index FROM documents d JOIN publications p ON p.id=d.publication_id WHERE p.id=? AND (d.title LIKE ? OR d.toc_title LIKE ? OR d.subtitle LIKE ?) ORDER BY d.sort_order LIMIT 1", (publication_id, f"%{word}%", f"%{word}%", f"%{word}%"))
                                    if candidates:
                                        break
                            if candidates:
                                result.update({"resolved": True, "kind": "publication", "document": candidates[0]})
                                self._json(result)
                                return
                    except Exception:
                        pass
                self._json(result)
                return
            match = re.fullmatch(r"/api/playlists/([a-f0-9]+)/export", path)
            if match:
                target=PATHS.cache/f"LiMaD-Playlist-{match.group(1)}.jwlplaylist"
                export_jwlplaylist(match.group(1),target)
                body=target.read_bytes();self._send(body,"application/octet-stream",headers={"Content-Disposition":f'attachment; filename="{target.name}"'});target.unlink(missing_ok=True);return
            if path == "/api/export/jwlibrary":
                backup_id = (query.get("backup_id") or [None])[0]
                result = export_jwlibrary(PATHS.cache, backup_id)
                target = Path(result["path"])
                body = target.read_bytes()
                self._send(body, "application/octet-stream", headers={"Content-Disposition": f'attachment; filename="{target.name}"', "Cache-Control": "no-store"})
                target.unlink(missing_ok=True)
                return
            if path.startswith("/content/"):
                parts = path.split("/", 3)
                if len(parts) < 4:
                    raise FileNotFoundError(path)
                pub_id = urllib.parse.unquote(parts[2])
                relative = urllib.parse.unquote(parts[3])
                rows = DB.rows("SELECT content_dir FROM publications WHERE id=?", (pub_id,))
                if not rows:
                    raise FileNotFoundError("Publikation fehlt.")
                root = Path(rows[0]["content_dir"]).resolve()
                target = (root / relative).resolve()
                if root not in target.parents and target != root:
                    raise PermissionError("Ungültiger Inhaltspfad.")
                if not target.is_file():
                    raise FileNotFoundError(relative)
                self._send_file(target, headers={"Cache-Control": "public,max-age=86400"})
                return
            self._static(path)
        except FileNotFoundError as exc:
            self._error(exc, 404)
        except PermissionError as exc:
            self._error(exc, 403)
        except Exception as exc:
            self._error(exc, 400)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/import/jwpub":
                upload, filename = self._upload(".jwpub")
                try:
                    self._json({"ok": True, "result": import_jwpub(upload), "filename": filename})
                finally:
                    upload.unlink(missing_ok=True)
                return
            if path == "/api/import/jwlibrary":
                upload, filename = self._upload(".jwlibrary")
                try:
                    self._json({"ok": True, "result": import_jwlibrary(upload), "filename": filename})
                finally:
                    upload.unlink(missing_ok=True)
                return
            if path == "/api/import/jwlplaylist":
                upload, filename = self._upload(".jwlplaylist")
                try:
                    self._json({"ok": True, "result": import_jwlplaylist(upload), "filename": filename})
                finally:
                    upload.unlink(missing_ok=True)
                return
            data = self._body_json()
            if path == "/api/assistant/settings":
                self._json({"ok": True, "state": assistant_update_settings(data)})
                return
            if path == "/api/assistant/projects":
                self._json({"ok": True, "project": assistant_create_project(str(data.get("title") or "Neue Ausarbeitung"))})
                return
            match = re.fullmatch(r"/api/assistant/projects/([a-f0-9]+)/messages", path)
            if match:
                self._json({"ok": True, **assistant_send_message(match.group(1), str(data.get("content") or ""), list(data.get("context") or []))})
                return
            if path == "/api/frontend/event":
                current = self.server.set_frontend_status(data)
                self._json({"ok": True, **current})
                return
            if path == "/api/native-player/session":
                playlist = data.get("playlist")
                if not isinstance(playlist, list) or not playlist:
                    raise ValueError("Für den nativen Player wurden keine Medien übergeben.")
                if len(playlist) > 250:
                    raise ValueError("Die Player-Wiedergabeliste ist zu groß.")
                session_id = self.server.create_native_player_session(data)
                self._json({"ok": True, "session_id": session_id})
                return
            if path == "/api/open-external":
                url = str(data.get("url") or "").strip()
                parsed_url = urllib.parse.urlparse(url)
                if parsed_url.scheme not in {"http", "https"}:
                    raise ValueError("Nur HTTP- und HTTPS-Adressen können extern geöffnet werden.")
                opened = bool(webbrowser.open(url, new=2, autoraise=True))
                self._json({"ok": True, "opened": opened, "url": url})
                return
            if path == "/api/catalog/sync":
                self._json({"ok": True, "result": sync_all()})
                return
            if path == "/api/backups/reconcile":
                self._json({"ok":True,"result":reconcile_backup(data.get("backup_id"))})
                return
            if path == "/api/downloads":
                self._json({"ok": True, "job": start_download(_as_int(data.get("catalog_id")), _as_int(data.get("option_index"), 0))})
                return
            match = re.fullmatch(r"/api/downloads/([a-f0-9]+)/retry", path)
            if match:
                self._json({"ok": True, "job": retry_download(match.group(1))})
                return
            match = re.fullmatch(r"/api/downloads/([a-f0-9]+)/cancel", path)
            if match:
                self._json({"ok": True, "job": cancel_download(match.group(1))})
                return
            match = re.fullmatch(r"/api/downloads/([a-f0-9]+)/remove", path)
            if match:
                self._json({"ok": True, "result": remove_download(match.group(1))})
                return
            if path == "/api/downloads/cleanup":
                self._json({"ok": True, "result": cleanup_downloads()})
                return
            if path == "/api/favorite":
                pub_id = str(data.get("publication_id") or "")
                value = 1 if data.get("favorite") else 0
                DB.execute("UPDATE publications SET favorite=? WHERE id=?", (value, pub_id))
                self._json({"ok": True, "publication_id": pub_id, "favorite": value})
                return
            if path == "/api/open-document":
                document_id = _as_int(data.get("document_id"))
                rows = DB.rows("SELECT publication_id FROM documents WHERE id=?", (document_id,))
                if rows:
                    DB.execute("UPDATE publications SET last_opened_at=? WHERE id=?", (utc_now(), rows[0]["publication_id"]))
                self._json({"ok": True})
                return
            if path == "/api/notes":
                self._json({"ok": True, "note": create_note(_as_int(data.get("document_id")), str(data.get("title") or ""), str(data.get("content") or ""), data.get("block_identifier"), data.get("tags") or [], data.get("start_token"), data.get("end_token"), str(data.get("linked_mark_id") or "") or None, str(data.get("selection_text") or "") or None)})
                return
            match = re.fullmatch(r"/api/publications/([^/]+)", path)
            if match:
                result = _remove_publication(urllib.parse.unquote(match.group(1)))
                self._json({"ok": True, "result": result})
                return
            match = re.fullmatch(r"/api/notes/([a-f0-9]+)", path)
            if match:
                self._json({"ok": True, "note": update_note(match.group(1), str(data.get("title") or ""), str(data.get("content") or ""))})
                return
            if path == "/api/marks":
                self._json({"ok": True, "mark": add_mark(_as_int(data.get("document_id")), data.get("block_identifier"), data.get("start_token"), data.get("end_token"), _as_int(data.get("color_index"), 0), _as_int(data.get("style_index"), 0))})
                return
            if path == "/api/marks/group":
                self._json({"ok": True, "mark": add_mark_group(_as_int(data.get("document_id")), list(data.get("ranges") or []), _as_int(data.get("color_index"), 0), _as_int(data.get("style_index"), 0))})
                return
            match = re.fullmatch(r"/api/marks/([A-Za-z0-9:]+)/update", path)
            if match:
                self._json({"ok": True, "mark": update_mark(match.group(1), data.get("color_index"), data.get("hidden"))})
                return
            if path == "/api/input-fields":
                self._json({"ok": True, "field": save_input_field(_as_int(data.get("document_id")), str(data.get("text_tag") or ""), str(data.get("value") or ""))})
                return
            if path == "/api/bookmarks":
                self._json({"ok":True,"bookmark":create_bookmark(_as_int(data.get("document_id")),str(data.get("title") or ""),str(data.get("snippet") or ""),data.get("block_identifier"),_as_int(data.get("slot"),0))})
                return
            if path == "/api/reading-position":
                self._json({"ok":True,"position":save_position(_as_int(data.get("document_id")),float(data.get("scroll_ratio") or 0),data.get("block_identifier"))})
                return
            if path == "/api/media/download":
                self._json({"ok": True, "item": download_remote_media(str(data.get("url") or ""), str(data.get("title") or ""), str(data.get("kind") or "audio"), str(data.get("quality") or ""), str(data.get("image") or ""), str(data.get("natural_key") or ""))})
                return
            if path == "/api/media/progress":
                self._json({"ok":True,"progress":save_progress(str(data.get("media_key") or ""),str(data.get("publication_id") or ""),str(data.get("file_path") or ""),float(data.get("position_seconds") or 0),float(data.get("duration_seconds") or 0),float(data.get("playback_rate") or 1))})
                return
            if path == "/api/bibles/preference":
                self._json({"ok":True,"preference":set_preference(_as_int(data.get("language_index")),str(data.get("publication_id") or ""),_as_int(data.get("last_document_id")) if data.get("last_document_id") is not None else None)})
                return
            if path == "/api/bibles/view-state":
                self._json({"ok": True, "state": save_view_state(_as_int(data.get("language_index"), 2), str(data.get("primary_publication_id") or ""), data.get("compare_publication_id"), data.get("book_number"), data.get("chapter_number"), bool(data.get("split_enabled")))})
                return
            if path == "/api/playlists":
                self._json({"ok":True,"playlist":create_playlist(str(data.get("title") or ""),str(data.get("description") or ""))})
                return
            match = re.fullmatch(r"/api/playlists/([a-f0-9]+)/items", path)
            if match:
                self._json({"ok":True,"item":add_item(match.group(1),str(data.get("label") or ""),str(data.get("publication_id") or ""),str(data.get("file_path") or ""),str(data.get("media_url") or ""),str(data.get("mime_type") or ""),str(data.get("thumbnail_path") or ""),float(data.get("start_seconds") or 0),float(data["end_seconds"]) if data.get("end_seconds") is not None else None,data)})
                return
            match = re.fullmatch(r"/api/playlists/([a-f0-9]+)/reorder", path)
            if match:
                self._json({"ok":True,"playlist":reorder_items(match.group(1),list(data.get("item_ids") or []))})
                return
            if path == "/api/meetings/notes":
                self._json({"ok":True,"note":save_meeting_note(_as_int(data.get("document_id")),str(data.get("title") or ""),str(data.get("content") or ""))})
                return
            if path == "/api/settings":
                for key, value in data.items():
                    if key in {"language_index", "theme", "font_size", "catalog_autosync", "date_format", "download_directory"}:
                        DB.set_setting(key, str(value))
                self._json({"ok": True})
                return
            self._error(ValueError("Unbekannte API-Aktion."), 404)
        except Exception as exc:
            self._error(exc, 400)

    def do_DELETE(self):
        path = urllib.parse.urlparse(self.path).path
        try:
            match = re.fullmatch(r"/api/assistant/projects/([a-f0-9]+)", path)
            if match:
                assistant_delete_project(match.group(1)); self._json({"ok": True}); return
            match = re.fullmatch(r"/api/publications/([^/]+)", path)
            if match:
                result = _remove_publication(urllib.parse.unquote(match.group(1)))
                self._json({"ok": True, "result": result})
                return
            match = re.fullmatch(r"/api/notes/([a-f0-9]+)", path)
            if match:
                delete_note(match.group(1))
                self._json({"ok": True})
                return
            match = re.fullmatch(r"/api/marks/([A-Za-z0-9:]+)", path)
            if match:
                delete_mark_any(match.group(1)); self._json({"ok":True}); return
            match = re.fullmatch(r"/api/playlists/([a-f0-9]+)", path)
            if match:
                delete_playlist(match.group(1));self._json({"ok":True});return
            match = re.fullmatch(r"/api/meetings/notes/([A-Za-z0-9:-]+)", path)
            if match:
                delete_meeting_note(match.group(1)); self._json({"ok":True}); return
            match = re.fullmatch(r"/api/bookmarks/([a-f0-9:]+)", path)
            if match:
                if ':' in match.group(1): raise ValueError("Importierte Lesezeichen können nicht gelöscht werden.")
                delete_bookmark(match.group(1)); self._json({"ok":True}); return
            self._error(ValueError("Unbekannte Löschaktion."), 404)
        except Exception as exc:
            self._error(exc, 400)

    def _static(self, path: str):
        relative = "index.html" if path in {"", "/"} else path.lstrip("/")
        target = (WEB_ROOT / relative).resolve()
        root = WEB_ROOT.resolve()
        if root not in target.parents and target != root:
            raise PermissionError("Ungültiger Ressourcenpfad.")
        if not target.is_file():
            target = WEB_ROOT / "index.html"
        headers = {"Content-Security-Policy": "default-src 'self'; img-src 'self' data: blob: https://*.jw-cdn.org https://*.akamaihd.net; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-src 'self'; connect-src 'self'; media-src 'self' blob: https://*.jw-cdn.org https://*.akamaihd.net;"}
        self._send(target.read_bytes(), mime_type(target), headers=headers)


def start_server(host: str = "127.0.0.1", port: int = 0) -> tuple[StudyServer, threading.Thread]:
    ensure_seed()
    server = StudyServer((host, port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="limad-study-http")
    thread.start()
    return server, thread

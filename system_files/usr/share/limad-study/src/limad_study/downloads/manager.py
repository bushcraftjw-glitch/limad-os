from __future__ import annotations
import hashlib
import os
import shutil
import threading
import time
import json
from datetime import datetime, timezone
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
import traceback
from pathlib import Path
from ..catalog.client import USER_AGENT, _is_https_url, download_options, verify_download
from ..config import PATHS
from ..database import DB, Database
from ..importers.jwpub import import_jwpub
from ..utils import safe_identifier, utc_now

_THREADS: dict[str, threading.Thread] = {}
_LOCK = threading.Lock()
CHUNK_SIZE = 1024 * 1024
MAX_ATTEMPTS = 5


def _job(database: Database, job_id: str) -> dict | None:
    rows = database.rows("SELECT * FROM download_jobs WHERE id=?", (job_id,))
    return rows[0] if rows else None


def _seconds_since(value: str) -> float:
    try:
        return max(0.0, (datetime.now(timezone.utc) - datetime.fromisoformat(str(value).replace("Z", "+00:00"))).total_seconds())
    except Exception:
        return 0.0


def _job_log_path(job_id: str) -> Path:
    PATHS.logs.mkdir(parents=True, exist_ok=True)
    return PATHS.logs / f"download-{job_id}.json"


def _write_job_log(database: Database, job_id: str, event: str, **extra) -> None:
    try:
        job = _job(database, job_id) or {"id": job_id}
        payload = {"event": event, "recorded_at": utc_now(), "job": job, **extra}
        _job_log_path(job_id).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        (PATHS.logs / "download-last.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def jobs(database: Database = DB) -> list[dict]:
    rows = database.rows("SELECT * FROM download_jobs ORDER BY created_at DESC LIMIT 200")
    labels = {"queued":"Wartet", "downloading":"Wird heruntergeladen", "verifying":"Prüfsumme wird geprüft", "importing":"Wird importiert", "completed":"Fertig", "failed":"Fehlgeschlagen", "cancelled":"Abgebrochen", "paused":"Pausiert"}
    for row in rows:
        expected = int(row.get("expected_size") or 0)
        received = int(row.get("received_size") or 0)
        elapsed = _seconds_since(row.get("created_at") or "")
        row["progress"] = round((received / expected) * 100, 1) if expected else 0
        row["speed_bps"] = int(received / elapsed) if elapsed > 0 and row.get("status") == "downloading" else 0
        row["status_label"] = labels.get(str(row.get("status") or ""), str(row.get("status") or ""))
        row["can_retry"] = row.get("status") in {"failed", "cancelled", "paused"}
        row["can_cancel"] = row.get("status") in {"queued", "downloading", "verifying", "importing"}
        row["can_remove"] = row.get("status") in {"failed", "cancelled", "completed", "paused"}
        row["installed_id"] = None
        row["can_open"] = False
        if row.get("status") == "completed":
            matches = database.rows(
                "SELECT id FROM publications WHERE catalog_id=? ORDER BY installed_at DESC LIMIT 1",
                (int(row.get("catalog_id") or 0),),
            )
            if not matches and row.get("publication_key"):
                matches = database.rows(
                    "SELECT id FROM publications WHERE key_symbol=? ORDER BY installed_at DESC LIMIT 1",
                    (str(row.get("publication_key") or ""),),
                )
            if matches:
                row["installed_id"] = matches[0]["id"]
                row["can_open"] = True
    return rows


def _update(database: Database, job_id: str, **values) -> None:
    if not values:
        return
    values["updated_at"] = utc_now()
    assignments = ",".join(f"{key}=?" for key in values)
    database.execute(f"UPDATE download_jobs SET {assignments} WHERE id=?", tuple(values.values()) + (job_id,))


def _safe_download_url(url: str) -> str:
    if not _is_https_url(url):
        raise ValueError("Es sind ausschließlich HTTPS-Downloadadressen erlaubt.")
    return url


def start(catalog_id: int, option_index: int = 0, database: Database = DB) -> dict:
    rows = database.rows("SELECT * FROM catalog_publications WHERE catalog_id=?", (int(catalog_id),))
    if not rows:
        raise ValueError("Katalogeintrag nicht gefunden.")
    catalog = rows[0]
    active = database.rows("SELECT * FROM download_jobs WHERE catalog_id=? AND status IN ('queued','downloading','verifying','importing') ORDER BY created_at DESC LIMIT 1", (int(catalog_id),))
    if active:
        return active[0]
    options = download_options(catalog_id, database)
    if not options:
        raise ValueError("Für diese Publikation wurde keine JWPUB-Datei angeboten.")
    option = options[min(max(option_index, 0), len(options) - 1)]
    url = _safe_download_url(option["url"])
    job_id = uuid.uuid4().hex
    filename = safe_identifier(option.get("filename") or f"{catalog['key_symbol']}.jwpub")
    if not filename.lower().endswith(".jwpub"):
        filename += ".jwpub"
    target = PATHS.downloads / f"{job_id}-{filename}"
    now = utc_now()
    database.execute('''INSERT INTO download_jobs(id,catalog_id,publication_key,title,url,target_path,expected_size,received_size,expected_hash,status,created_at,updated_at,error)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
        job_id, catalog_id, catalog.get("key_symbol") or "", catalog.get("title") or filename, url, str(target), int(option.get("size") or 0), 0,
        str(option.get("checksum") or ""), "queued", now, now, ""
    ))
    _write_job_log(database, job_id, "queued", option=option)
    _spawn(job_id, database)
    return _job(database, job_id) or {"id": job_id}


def _spawn(job_id: str, database: Database) -> None:
    with _LOCK:
        current = _THREADS.get(job_id)
        if current and current.is_alive():
            return
        thread = threading.Thread(target=_worker, args=(job_id, database), daemon=True, name=f"limad-download-{job_id[:8]}")
        _THREADS[job_id] = thread
        thread.start()


def _available_space(path: Path) -> int:
    return shutil.disk_usage(path.parent).free


def _validate_content_range(value: str, start: int) -> None:
    if not value:
        raise ValueError("Server bestätigte den fortgesetzten Download nicht.")
    prefix = f"bytes {start}-"
    if not value.lower().startswith(prefix.lower()):
        raise ValueError(f"Ungültiger Content-Range-Header: {value}")


def _validate_jwpub_archive(path: Path) -> None:
    if not zipfile.is_zipfile(path):
        raise ValueError("Die heruntergeladene Datei ist kein gültiges JWPUB-Archiv.")
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        if "manifest.json" not in names or "contents" not in names:
            raise ValueError("JWPUB enthält nicht die erwarteten Hauptdateien.")
        bad = archive.testzip()
        if bad:
            raise ValueError(f"JWPUB ist beschädigt: {bad}")


def _download_once(job: dict, database: Database, job_id: str, part: Path) -> None:
    received = part.stat().st_size if part.is_file() else 0
    expected_db = int(job.get("expected_size") or 0)
    reserve = max(64 * 1024 * 1024, expected_db // 10)
    required = max(expected_db - received, 0) + reserve
    if expected_db and _available_space(part) < required:
        raise ValueError("Nicht genügend freier Speicherplatz für den Download.")
    headers = {"User-Agent": USER_AGENT, "Accept": "application/octet-stream,*/*", "Accept-Encoding": "identity", "Cache-Control": "no-cache"}
    if received:
        headers["Range"] = f"bytes={received}-"
    request = urllib.request.Request(_safe_download_url(job["url"]), headers=headers)
    with urllib.request.urlopen(request, timeout=150) as response:
        final_url = response.geturl()
        _safe_download_url(final_url)
        status = getattr(response, "status", 200)
        if received and status == 206:
            _validate_content_range(response.headers.get("Content-Range", ""), received)
            mode = "ab"
        elif received and status == 200:
            received = 0
            mode = "wb"
        elif status in (200, 206):
            mode = "wb"
        else:
            raise ValueError(f"Downloadserver antwortet mit HTTP {status}.")
        content_length = int(response.headers.get("Content-Length") or 0)
        expected = received + content_length if content_length else expected_db
        if expected_db and expected and expected_db != expected and status != 206:
            expected = expected_db
        if expected and _available_space(part) < max(expected - received, 0) + reserve:
            raise ValueError("Nicht genügend freier Speicherplatz für die Serverdatei.")
        _update(database, job_id, expected_size=expected, received_size=received)
        with part.open(mode) as output:
            while True:
                latest = _job(database, job_id)
                if not latest or latest.get("status") == "cancelled":
                    return
                chunk = response.read(CHUNK_SIZE)
                if not chunk:
                    break
                output.write(chunk)
                received += len(chunk)
                _update(database, job_id, received_size=received)
            output.flush()
            os.fsync(output.fileno())


def _worker(job_id: str, database: Database) -> None:
    job = _job(database, job_id)
    if not job:
        return
    target = Path(job["target_path"])
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_suffix(target.suffix + ".part")
    try:
        _update(database, job_id, status="downloading", received_size=part.stat().st_size if part.exists() else 0, error="")
        _write_job_log(database, job_id, "download_started")
        last_error: Exception | None = None
        for attempt in range(MAX_ATTEMPTS):
            latest = _job(database, job_id)
            if not latest or latest.get("status") == "cancelled":
                return
            try:
                _download_once(latest, database, job_id, part)
                last_error = None
                break
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code not in {408, 425, 429, 500, 502, 503, 504} or attempt == MAX_ATTEMPTS - 1:
                    raise
                retry_after = int(exc.headers.get("Retry-After") or 0) if exc.headers else 0
                time.sleep(max(retry_after, min(2 ** attempt, 12)))
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
                last_error = exc
                if attempt == MAX_ATTEMPTS - 1:
                    raise
                time.sleep(min(2 ** attempt, 12))
        if last_error:
            raise last_error
        latest = _job(database, job_id)
        if not latest or latest.get("status") == "cancelled":
            return
        _update(database, job_id, status="verifying")
        _write_job_log(database, job_id, "verification_started")
        verification = verify_download(part, int(latest.get("expected_size") or 0), str(latest.get("expected_hash") or ""))
        _validate_jwpub_archive(part)
        os.replace(part, target)
        _update(database, job_id, status="importing", received_size=verification["size"])
        _write_job_log(database, job_id, "import_started", verification=verification)
        result = import_jwpub(target, database)
        publication_id = str(result.get('publication_id') or '')
        if publication_id:
            database.execute(
                "UPDATE publications SET catalog_id=? WHERE id=?",
                (int(latest.get('catalog_id') or 0), publication_id),
            )
        _update(database, job_id, status="completed", received_size=target.stat().st_size, error="")
        _write_job_log(database, job_id, "completed", verification=verification, result=result)
        database.set_setting("last_download_result", str(result))
        database.set_setting("last_download_at", utc_now())
    except Exception as exc:
        received_size = target.stat().st_size if target.is_file() else (part.stat().st_size if part.is_file() else 0)
        trace = traceback.format_exc()
        _update(database, job_id, status="failed", error=str(exc), received_size=received_size)
        _write_job_log(database, job_id, "failed", error=str(exc), error_type=type(exc).__name__, traceback=trace, downloaded_file=str(target) if target.is_file() else "")
    finally:
        with _LOCK:
            _THREADS.pop(job_id, None)


def retry(job_id: str, database: Database = DB) -> dict:
    job = _job(database, job_id)
    if not job:
        raise ValueError("Downloadauftrag fehlt.")
    _update(database, job_id, status="queued", error="")
    _spawn(job_id, database)
    return _job(database, job_id) or {}


def cancel(job_id: str, database: Database = DB) -> dict:
    job = _job(database, job_id)
    if not job:
        raise ValueError("Downloadauftrag fehlt.")
    _update(database, job_id, status="cancelled", error="Vom Benutzer abgebrochen.")
    return _job(database, job_id) or {}



def remove(job_id: str, database: Database = DB) -> dict:
    job = _job(database, job_id)
    if not job:
        raise ValueError("Downloadauftrag fehlt.")
    if str(job.get("status") or "") in {"queued", "downloading", "verifying", "importing"}:
        raise ValueError("Aktive Downloads müssen zuerst abgebrochen werden.")
    removed_files = 0
    target_value = str(job.get("target_path") or "").strip()
    if target_value:
        target = Path(target_value)
        candidates = {target, target.with_suffix(target.suffix + ".part"), target.with_suffix(target.suffix + ".partial")}
        for candidate in candidates:
            try:
                if candidate.is_file():
                    candidate.unlink()
                    removed_files += 1
            except OSError:
                pass
    log_path = _job_log_path(job_id)
    try:
        if log_path.is_file():
            log_path.unlink()
            removed_files += 1
    except OSError:
        pass
    database.execute("DELETE FROM download_jobs WHERE id=?", (job_id,))
    return {"job_id": job_id, "removed_files": removed_files}

def cleanup_completed(database: Database = DB) -> dict:
    rows = database.rows("SELECT id,target_path,status FROM download_jobs WHERE status IN ('completed','cancelled')")
    removed = 0
    for row in rows:
        path = Path(row["target_path"])
        for candidate in (path, path.with_suffix(path.suffix + ".part")):
            if candidate.is_file():
                candidate.unlink(missing_ok=True)
                removed += 1
    return {"removed_files": removed, "jobs": len(rows)}

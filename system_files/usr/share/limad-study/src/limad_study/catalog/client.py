from __future__ import annotations
import gzip
import hashlib
import json
import re
import shutil
import sqlite3
import tempfile
import urllib.parse
import urllib.request
import time
from pathlib import Path
from typing import Any, Callable
from ..config import PATHS
from ..database import DB, Database
from ..utils import mime_type, utc_now

from .. import VERSION
USER_AGENT = f"LiMaD-Study/{VERSION} Linux"
OFFICIAL_JW_USER_AGENT = "jwlibrary-android"
MANIFEST_URL = "https://app.jw-cdn.org/catalogs/publications/v4/manifest.json"
LANGUAGES_URL = "https://app.jw-cdn.org/catalogs/media/languages.json.gz"
PUB_MEDIA_URL = "https://b.jw-cdn.org/apis/pub-media/GETPUBMEDIALINKS"
COVER_BASE_URL = "https://app.jw-cdn.org/catalogs/publications/"
RequestFn = Callable[[str, int, str, int], tuple[bytes, str]]


def _is_https_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return parsed.scheme == "https" and bool(parsed.hostname)


def _request(url: str, max_bytes: int, accept: str = "application/json,*/*", timeout: int = 40) -> tuple[bytes, str]:
    if not _is_https_url(url):
        raise ValueError("Es sind ausschließlich HTTPS-Adressen erlaubt.")
    last_error = None
    parsed = urllib.parse.urlparse(url)
    official_host = str(parsed.hostname or "").lower() in {"app.jw-cdn.org", "b.jw-cdn.org"}
    headers = {
        "User-Agent": OFFICIAL_JW_USER_AGENT if official_host else USER_AGENT,
        "Accept": accept,
        "Accept-Encoding": "identity",
        "Cache-Control": "no-cache",
    }
    if official_host and parsed.hostname:
        headers["Host"] = parsed.hostname
    for attempt in range(3):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                final_url = response.geturl()
                if not _is_https_url(final_url):
                    raise ValueError("Der Server hat auf eine unsichere Adresse weitergeleitet.")
                length = int(response.headers.get("Content-Length") or 0)
                if length and length > max_bytes:
                    raise ValueError("Serverdatei ist größer als erlaubt.")
                body = response.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise ValueError("Serverantwort ist größer als erlaubt.")
                if response.status not in (200, 206):
                    raise ValueError(f"Server antwortet mit HTTP {response.status}.")
                return body, response.headers.get_content_type()
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(0.35 * (2 ** attempt))
    raise ValueError(f"Serverabruf fehlgeschlagen: {last_error}")


def _json_documents(raw: bytes) -> list[Any]:
    text = raw.decode("utf-8-sig")
    try:
        return [json.loads(text)]
    except json.JSONDecodeError:
        documents = []
        for number, line in enumerate(text.splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                documents.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSONL-Zeile {number} ist ungültig: {exc}") from exc
        if not documents:
            raise ValueError("Die Sprachdatei enthält keine JSON-Dokumente.")
        return documents


def _language_items(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        output = []
        for item in payload:
            output.extend(_language_items(item))
        return output
    if not isinstance(payload, dict):
        return []
    if payload.get("type") == "languages" and isinstance(payload.get("o"), list):
        return [item for item in payload["o"] if isinstance(item, dict)]
    for key in ("languages", "Languages", "items", "Items"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    for value in payload.values():
        if isinstance(value, (dict, list)):
            found = _language_items(value)
            if found:
                return found
    return []


def _pick(item: dict, *names: str, default: Any = "") -> Any:
    for name in names:
        if name in item and item[name] is not None:
            return item[name]
    lowered = {str(key).lower(): value for key, value in item.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value is not None:
            return value
    return default


def sync_languages(database: Database = DB, request_fn: RequestFn = _request) -> dict[str, Any]:
    body, _ = request_fn(LANGUAGES_URL, 30_000_000, "application/gzip,application/json,*/*", 60)
    raw = gzip.decompress(body) if body[:2] == b"\x1f\x8b" else body
    documents = _json_documents(raw)
    items = _language_items(documents)
    if len(items) < 100:
        raise ValueError("Die Sprachdatei enthält zu wenige Einträge.")
    detailed = [item for item in items if _pick(item, "LanguageId", "languageId", "id", default=None) not in (None, "")]
    if not detailed:
        with database.transaction() as con:
            con.execute("INSERT OR REPLACE INTO catalog_state(key,value,updated_at) VALUES('languages_last_sync',?,?)", (utc_now(), utc_now()))
            con.execute("INSERT OR REPLACE INTO catalog_state(key,value,updated_at) VALUES('languages_manifest_count',?,?)", (str(len(items)), utc_now()))
        return {"count": int(database.scalar("SELECT COUNT(*) FROM languages") or 0), "manifest_count": len(items), "synced_at": utc_now(), "preserved_metadata": True}
    count = 0
    with database.transaction() as con:
        for item in detailed:
            language_id = int(_pick(item, "LanguageId", "languageId", "id", default=-1))
            if language_id < 0:
                continue
            con.execute('''INSERT INTO languages(id,symbol,english_name,vernacular_name,iso2,iso3,ietf,is_sign,script_id,direction,source)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET symbol=excluded.symbol,english_name=excluded.english_name,vernacular_name=excluded.vernacular_name,
                iso2=excluded.iso2,iso3=excluded.iso3,ietf=excluded.ietf,is_sign=excluded.is_sign,script_id=excluded.script_id,
                direction=excluded.direction,source=excluded.source''', (
                language_id,
                str(_pick(item, "Symbol", "symbol")),
                str(_pick(item, "EnglishName", "englishName", "name")),
                str(_pick(item, "VernacularName", "vernacularName", "nativeName")),
                str(_pick(item, "IsoAlpha2Code", "isoAlpha2Code", "iso2")),
                str(_pick(item, "IsoAlpha3Code", "isoAlpha3Code", "iso3")),
                str(_pick(item, "PrimaryIetfCode", "primaryIetfCode", "ietf")),
                int(bool(_pick(item, "IsSignLanguage", "isSignLanguage", "isSign", default=0))),
                _pick(item, "ScriptId", "scriptId", default=None),
                str(_pick(item, "Direction", "direction", default="rtl" if bool(_pick(item, "IsRtl", "isRtl", default=False)) else "ltr")),
                "live",
            ))
            count += 1
        con.execute("INSERT OR REPLACE INTO catalog_state(key,value,updated_at) VALUES('languages_last_sync',?,?)", (utc_now(), utc_now()))
        con.execute("INSERT OR REPLACE INTO catalog_state(key,value,updated_at) VALUES('languages_count',?,?)", (str(count), utc_now()))
    return {"count": count, "synced_at": utc_now()}


def _parse_catalog(path: Path, database: Database, revision: str) -> int:
    source = sqlite3.connect(path)
    source.row_factory = sqlite3.Row
    language_symbols = {int(row["id"]): row["symbol"] for row in database.rows("SELECT id,symbol FROM languages")}
    tables = {row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    required = {"Publication", "PublicationAsset"}
    if not required.issubset(tables):
        raise ValueError("Katalogdatenbank hat nicht die erwartete Struktur.")
    query = '''
    SELECT p.Id AS CatalogId,p.KeySymbol,p.Symbol,p.MepsLanguageId,p.Title,p.ShortTitle,p.Year,p.IssueTagNumber,p.PublicationTypeId,
           pa.Id AS AssetId,pa.Signature,pa.Size,pa.ExpandedSize,pa.MimeType,pa.CatalogedOn,pa.LastUpdated,pa.LastModified,pa.GenerallyAvailableDate,
           (SELECT ia.NameFragment FROM PublicationAssetImageMap m JOIN ImageAsset ia ON ia.Id=m.ImageAssetId WHERE m.PublicationAssetId=pa.Id
               AND ia.NameFragment NOT LIKE '%generic_tile%'
               AND ia.NameFragment NOT LIKE '%km_tile%'
               AND ia.NameFragment NOT LIKE '%_cvr.%'
             ORDER BY CASE WHEN ia.Width=ia.Height THEN 0 WHEN ia.Height>ia.Width THEN 1 ELSE 2 END,ia.Width DESC LIMIT 1) ImageFragment,
           (SELECT ia.Width FROM PublicationAssetImageMap m JOIN ImageAsset ia ON ia.Id=m.ImageAssetId WHERE m.PublicationAssetId=pa.Id
               AND ia.NameFragment NOT LIKE '%generic_tile%'
               AND ia.NameFragment NOT LIKE '%km_tile%'
               AND ia.NameFragment NOT LIKE '%_cvr.%'
             ORDER BY CASE WHEN ia.Width=ia.Height THEN 0 WHEN ia.Height>ia.Width THEN 1 ELSE 2 END,ia.Width DESC LIMIT 1) ImageWidth,
           (SELECT ia.Height FROM PublicationAssetImageMap m JOIN ImageAsset ia ON ia.Id=m.ImageAssetId WHERE m.PublicationAssetId=pa.Id
               AND ia.NameFragment NOT LIKE '%generic_tile%'
               AND ia.NameFragment NOT LIKE '%km_tile%'
               AND ia.NameFragment NOT LIKE '%_cvr.%'
             ORDER BY CASE WHEN ia.Width=ia.Height THEN 0 WHEN ia.Height>ia.Width THEN 1 ELSE 2 END,ia.Width DESC LIMIT 1) ImageHeight,
           (SELECT ia.MimeType FROM PublicationAssetImageMap m JOIN ImageAsset ia ON ia.Id=m.ImageAssetId WHERE m.PublicationAssetId=pa.Id
               AND ia.NameFragment NOT LIKE '%generic_tile%'
               AND ia.NameFragment NOT LIKE '%km_tile%'
               AND ia.NameFragment NOT LIKE '%_cvr.%'
             ORDER BY CASE WHEN ia.Width=ia.Height THEN 0 WHEN ia.Height>ia.Width THEN 1 ELSE 2 END,ia.Width DESC LIMIT 1) ImageMime
    FROM Publication p JOIN PublicationAsset pa ON pa.PublicationId=p.Id
    WHERE lower(COALESCE(pa.MimeType,'')) IN ('application/x-jwpub','application/zip','') OR lower(COALESCE(pa.MimeType,'')) LIKE '%jwpub%'
    '''
    count = 0
    try:
        with database.transaction() as con:
            con.execute("DELETE FROM catalog_publications")
            for row in source.execute(query):
                raw = dict(row)
                language_index = int(row["MepsLanguageId"] or 0)
                con.execute('''INSERT INTO catalog_publications(
                    catalog_id,key_symbol,symbol,language_index,language_symbol,title,short_title,year,issue_tag,publication_type_id,asset_id,signature,size,expanded_size,mime_type,
                    cataloged_on,last_updated,last_modified,generally_available_date,image_fragment,image_width,image_height,image_mime,raw_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                    row["CatalogId"], row["KeySymbol"] or row["Symbol"] or "", row["Symbol"] or "", language_index, language_symbols.get(language_index, ""), row["Title"] or "", row["ShortTitle"] or "",
                    row["Year"] or 0, row["IssueTagNumber"] or 0, row["PublicationTypeId"] or 0, row["AssetId"], row["Signature"] or "", row["Size"] or 0, row["ExpandedSize"] or 0, row["MimeType"] or "",
                    row["CatalogedOn"] or "", row["LastUpdated"] or "", row["LastModified"] or "", row["GenerallyAvailableDate"] or "", row["ImageFragment"] or "", row["ImageWidth"] or 0, row["ImageHeight"] or 0, row["ImageMime"] or "", json.dumps(raw, ensure_ascii=False)
                ))
                count += 1
            con.execute("INSERT OR REPLACE INTO catalog_state(key,value,updated_at) VALUES('manifest_revision',?,?)", (revision, utc_now()))
            con.execute("INSERT OR REPLACE INTO catalog_state(key,value,updated_at) VALUES('last_sync',?,?)", (utc_now(), utc_now()))
            con.execute("INSERT OR REPLACE INTO catalog_state(key,value,updated_at) VALUES('catalog_count',?,?)", (str(count), utc_now()))
    finally:
        source.close()
    return count


def sync_catalog(database: Database = DB, request_fn: RequestFn = _request) -> dict[str, Any]:
    manifest_body, _ = request_fn(MANIFEST_URL, 1_000_000, "application/json,*/*", 40)
    manifest = json.loads(manifest_body.decode("utf-8-sig"))
    revision = str(manifest.get("current") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]{8,128}", revision):
        raise ValueError("Katalogmanifest enthält keine gültige Revision.")
    current = database.scalar("SELECT value FROM catalog_state WHERE key='manifest_revision'")
    current_count = int(database.scalar("SELECT COUNT(*) FROM catalog_publications") or 0)
    cached = PATHS.catalog / f"catalog-{revision}.db"
    if current == revision and current_count > 0:
        database.execute("INSERT OR REPLACE INTO catalog_state(key,value,updated_at) VALUES('last_sync',?,?)", (utc_now(), utc_now()))
        return {"revision": revision, "count": current_count, "path": str(cached) if cached.is_file() else "", "unchanged": True, "synced_at": utc_now()}
    variants = [
        f"https://app.jw-cdn.org/catalogs/publications/v4/{urllib.parse.quote(revision)}/catalog.db.gz",
        f"https://app.jw-cdn.org/catalogs/publications/v4/{urllib.parse.quote(revision)}/catalog.db",
    ]
    last_error = None
    with tempfile.TemporaryDirectory(prefix="limad-catalog-") as tmp:
        root = Path(tmp)
        for url in variants:
            try:
                body, _ = request_fn(url, 350_000_000, "application/octet-stream,*/*", 120)
                raw = gzip.decompress(body) if body[:2] == b"\x1f\x8b" else body
                db_path = root / "catalog.db"
                db_path.write_bytes(raw)
                check = sqlite3.connect(db_path)
                try:
                    integrity = check.execute("PRAGMA integrity_check").fetchone()[0]
                    if integrity != "ok":
                        raise ValueError("Katalogdatenbank ist beschädigt.")
                finally:
                    check.close()
                count = _parse_catalog(db_path, database, revision)
                target = PATHS.catalog / f"catalog-{revision}.db"
                shutil.copy2(db_path, target)
                return {"revision": revision, "count": count, "path": str(target), "unchanged": False, "synced_at": utc_now()}
            except Exception as exc:
                last_error = exc
    raise ValueError(f"Offizieller Katalog konnte nicht aktualisiert werden: {last_error}")


def sync_all(database: Database = DB, request_fn: RequestFn = _request) -> dict[str, Any]:
    started = utc_now()
    errors = []
    try:
        language_result = sync_languages(database, request_fn)
    except Exception as exc:
        errors.append({"component":"languages","error":str(exc)})
        language_result = {"count": int(database.scalar("SELECT COUNT(*) FROM languages") or 0), "fallback": True, "stale": True}
    try:
        catalog_result = sync_catalog(database, request_fn)
    except Exception as exc:
        errors.append({"component":"catalog","error":str(exc)})
        catalog_result = {"revision": database.scalar("SELECT value FROM catalog_state WHERE key='manifest_revision'") or database.scalar("SELECT value FROM catalog_state WHERE key='seed_revision'") or "", "count": int(database.scalar("SELECT COUNT(*) FROM catalog_publications") or 0), "fallback": True, "stale": True}
    result={"languages":language_result,"catalog":catalog_result,"errors":errors,"degraded":bool(errors),"started_at":started,"synced_at":utc_now()}
    with database.transaction() as con:
        con.execute("INSERT INTO sync_events(kind,status,started_at,finished_at,detail_json,error) VALUES(?,?,?,?,?,?)",("catalog","degraded" if errors else "ok",started,result["synced_at"],json.dumps(result,ensure_ascii=False),"; ".join(item["error"] for item in errors)))
    return result


def catalog_status(database: Database = DB) -> dict[str, Any]:
    state = {row["key"]: row["value"] for row in database.rows("SELECT key,value FROM catalog_state")}
    return {
        "revision": state.get("manifest_revision") or state.get("seed_revision") or "",
        "last_sync": state.get("last_sync") or "",
        "languages_last_sync": state.get("languages_last_sync") or "",
        "languages": int(database.scalar("SELECT COUNT(*) FROM languages") or 0),
        "publications": int(database.scalar("SELECT COUNT(*) FROM catalog_publications") or 0),
        "installed": int(database.scalar("SELECT COUNT(*) FROM publications") or 0),
        "covers_cached": sum(1 for p in PATHS.covers.glob("catalog-*") if p.is_file() and p.stat().st_size > 0),
        "last_event": (database.rows("SELECT status,started_at,finished_at,error FROM sync_events WHERE kind='catalog' ORDER BY id DESC LIMIT 1") or [{}])[0],
        "offline_ready": int(database.scalar("SELECT COUNT(*) FROM catalog_publications") or 0) > 0,
    }


def languages(database: Database = DB, query: str = "", limit: int = 2000, offset: int = 0, available_only: bool = True) -> list[dict]:
    params: list[Any] = []
    clauses = []
    if query.strip():
        needle = f"%{query.strip()}%"
        clauses.append("(l.english_name LIKE ? OR l.vernacular_name LIKE ? OR l.symbol LIKE ? OR l.ietf LIKE ? OR l.iso2 LIKE ? OR l.iso3 LIKE ?)")
        params.extend([needle] * 6)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    having = " HAVING publication_count>0" if available_only else ""
    params.extend([min(max(limit, 1), 5000), max(offset, 0)])
    return database.rows(f'''SELECT l.*,COUNT(c.catalog_id) AS publication_count FROM languages l LEFT JOIN catalog_publications c ON c.language_index=l.id
        {where} GROUP BY l.id {having} ORDER BY CASE WHEN l.id=2 THEN 0 WHEN l.id=0 THEN 1 ELSE 2 END,publication_count DESC,l.english_name LIMIT ? OFFSET ?''', tuple(params))


def _kind_clause(kind: str) -> tuple[str, list[int]]:
    mapping = {
        "bibles": [1],
        "books": [2],
        "brochures": [4],
        "periodicals": [5, 13],
        "meeting": [10],
        "reference": [17],
    }
    ids = mapping.get(kind, [])
    return (f"c.publication_type_id IN ({','.join('?' for _ in ids)})", ids) if ids else ("", [])


def publications(database: Database = DB, language_index: int | None = None, query: str = "", kind: str = "", limit: int = 300, offset: int = 0, newest: bool = False) -> list[dict]:
    clauses = []
    params: list[Any] = []
    if language_index is not None:
        clauses.append("c.language_index=?")
        params.append(int(language_index))
    if query.strip():
        clauses.append("(c.title LIKE ? OR c.short_title LIKE ? OR c.key_symbol LIKE ? OR c.symbol LIKE ?)")
        needle = f"%{query.strip()}%"
        params.extend([needle] * 4)
    kind_sql, kind_params = _kind_clause(kind)
    if kind_sql:
        clauses.append(kind_sql)
        params.extend(kind_params)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    order = "COALESCE(NULLIF(c.generally_available_date,''),NULLIF(c.last_updated,''),NULLIF(c.cataloged_on,'')) DESC,c.catalog_id DESC" if newest else "c.title COLLATE NOCASE,c.year DESC"
    params.extend([min(max(limit, 1), 2000), max(offset, 0)])
    rows = database.rows(f'''SELECT c.*,l.english_name AS language_name,l.vernacular_name AS language_vernacular,
        CASE WHEN p.id IS NULL THEN 0 ELSE 1 END AS installed,p.id AS installed_id,p.cover_path AS installed_cover,
        COALESCE(NULLIF(c.generally_available_date,''),NULLIF(c.last_updated,''),NULLIF(c.cataloged_on,'')) AS sort_date
        FROM catalog_publications c LEFT JOIN languages l ON l.id=c.language_index
        LEFT JOIN publications p ON p.key_symbol=c.key_symbol AND p.language_index=c.language_index AND p.year=c.year AND p.issue_tag=c.issue_tag
        {where} ORDER BY {order} LIMIT ? OFFSET ?''', tuple(params))
    for row in rows:
        row["cover_url"] = f"/api/catalog/{row['catalog_id']}/cover" if row.get("image_fragment") else ""
        row["downloadable"] = bool(row.get("key_symbol") and row.get("language_symbol"))
    return rows


def _extract_urls(value: Any, output: list[dict], inherited: dict | None = None) -> None:
    inherited = dict(inherited or {})
    if isinstance(value, dict):
        for key in ("checksum", "sha256", "hash", "filesize", "fileSize", "size", "modifiedDatetime", "modifiedDate", "fileName"):
            if key in value and value[key] not in (None, ""):
                inherited[key] = value[key]
        url = value.get("url") or value.get("fileUrl") or value.get("downloadUrl")
        if isinstance(url, str) and ".jwpub" in url.lower():
            output.append({
                "url": url,
                "filename": value.get("fileName") or inherited.get("fileName") or Path(urllib.parse.urlparse(url).path).name,
                "size": value.get("filesize") or value.get("fileSize") or value.get("size") or inherited.get("filesize") or inherited.get("fileSize") or inherited.get("size") or 0,
                "checksum": value.get("checksum") or value.get("sha256") or value.get("hash") or inherited.get("checksum") or inherited.get("sha256") or inherited.get("hash") or "",
                "modified": value.get("modifiedDatetime") or value.get("modifiedDate") or inherited.get("modifiedDatetime") or inherited.get("modifiedDate") or "",
                "raw": value,
            })
        for item in value.values():
            _extract_urls(item, output, inherited)
    elif isinstance(value, list):
        for item in value:
            _extract_urls(item, output, inherited)


def _media_params(item: dict) -> dict[str, str]:
    params = {
        "fileformat": "JWPUB",
        "langwritten": item.get("language_symbol") or "X",
        "output": "json",
        "pub": item.get("key_symbol") or item.get("symbol") or "",
        "txtCMSLang": item.get("language_symbol") or "X",
        "alllangs": "0",
        "jwlversion": "5",
    }
    issue = int(item.get("issue_tag") or 0)
    if issue:
        params["issue"] = str(issue)
    raw = item.get("raw_json")
    try:
        raw = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        raw = {}
    if isinstance(raw, dict):
        for source, target in (("BookNumber", "booknum"), ("Track", "track"), ("MepsDocumentId", "docid"), ("Specialty", "specialty"), ("Edition", "edition")):
            value = raw.get(source)
            if value not in (None, "", 0):
                params[target] = str(value)
    return params




def _extract_cover_urls(value: Any, output: list[str]) -> None:
    if isinstance(value, str):
        candidate = value.strip()
        path = urllib.parse.urlparse(candidate).path.lower()
        if candidate.startswith("https://") and path.endswith((".jpg", ".jpeg", ".png", ".webp", ".avif")):
            output.append(candidate)
        return
    if isinstance(value, dict):
        for item in value.values():
            _extract_cover_urls(item, output)
    elif isinstance(value, list):
        for item in value:
            _extract_cover_urls(item, output)


def _pub_media_payload(item: dict, fileformat: str, request_fn: RequestFn) -> Any:
    params = _media_params(item)
    params["fileformat"] = fileformat
    url = PUB_MEDIA_URL + "?" + urllib.parse.urlencode(params)
    body, _ = request_fn(url, 20_000_000, "application/json,text/html,text/plain,*/*", 60)
    try:
        return json.loads(body.decode("utf-8-sig"))
    except Exception:
        return body.decode("utf-8", errors="ignore")


def download_options(catalog_id: int, database: Database = DB, request_fn: RequestFn = _request) -> list[dict]:
    item = database.rows("SELECT * FROM catalog_publications WHERE catalog_id=?", (int(catalog_id),))
    if not item:
        raise ValueError("Katalogeintrag wurde nicht gefunden.")
    item = item[0]
    params = _media_params(item)
    if not params.get("pub"):
        raise ValueError("Katalogeintrag hat kein Publikationssymbol.")
    payload = _pub_media_payload(item, "JWPUB", request_fn)
    results: list[dict] = []
    try:
        if isinstance(payload, str):
            raise ValueError("text payload")
        _extract_urls(payload, results)
    except Exception:
        text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        for match in re.findall(r"https://[^\s\"'<>]+\.jwpub(?:\?[^\s\"'<>]*)?", text, re.I):
            results.append({"url": match, "filename": Path(urllib.parse.urlparse(match).path).name, "size": 0, "checksum": "", "modified": ""})
    unique: dict[str, dict] = {}
    for result in results:
        if _is_https_url(result["url"]):
            result["size"] = int(result.get("size") or 0)
            result["checksum"] = str(result.get("checksum") or "").lower()
            unique[result["url"]] = result
    options = sorted(unique.values(), key=lambda item: (item.get("modified") or "", item.get("size") or 0), reverse=True)
    if options:
        database.execute("UPDATE catalog_publications SET download_url=? WHERE catalog_id=?", (options[0]["url"], int(catalog_id)))
    return options


def _cover_cache_path(catalog_id: int, fragment: str) -> Path:
    suffix = Path(urllib.parse.urlparse(fragment).path).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".avif"}:
        suffix = ".jpg"
    return PATHS.covers / f"catalog-{catalog_id}{suffix}"


def _cover_candidates(fragment: str) -> list[str]:
    fragment = str(fragment or "").strip()
    if not fragment:
        return []
    if _is_https_url(fragment):
        return [fragment]
    safe = fragment.replace("\\", "/").lstrip("/")
    if safe.startswith("catalogs/publications/"):
        safe = safe.removeprefix("catalogs/publications/")
    if not safe.startswith("images/"):
        return []
    return [urllib.parse.urljoin(COVER_BASE_URL, safe)]


def _valid_cover(body: bytes, content_type: str) -> bool:
    if len(body) < 256 or len(body) > 15_000_000:
        return False
    ctype = str(content_type or "").lower()
    if ctype.startswith("image/"):
        return True
    return body.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"RIFF")) or body[:12].find(b"ftypavif") >= 0


def _placeholder_cover(item: dict) -> tuple[bytes, str]:
    title = str(item.get("short_title") or item.get("title") or "Publikation")[:70]
    symbol = str(item.get("key_symbol") or item.get("symbol") or "JWPUB")[:20]
    def xml(value: str) -> str:
        return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="600" height="600" viewBox="0 0 600 600">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#17112c"/><stop offset="1" stop-color="#5c3fd2"/></linearGradient></defs>
<rect width="600" height="600" rx="34" fill="url(#g)"/><circle cx="300" cy="225" r="92" fill="none" stroke="#ffffff" stroke-opacity=".28" stroke-width="8"/>
<path d="M258 225h84M300 183v84" stroke="#fff" stroke-width="12" stroke-linecap="round" opacity=".9"/>
<text x="300" y="380" text-anchor="middle" fill="#fff" font-family="sans-serif" font-size="30" font-weight="700">{xml(title)}</text>
<text x="300" y="430" text-anchor="middle" fill="#ddd7ff" font-family="sans-serif" font-size="22">{xml(symbol)}</text>
<text x="300" y="530" text-anchor="middle" fill="#c8c0ef" font-family="sans-serif" font-size="18">Cover wird online geladen</text></svg>"""
    return svg.encode("utf-8"), "image/svg+xml"


def cover_bytes(catalog_id: int, database: Database = DB, request_fn: RequestFn = _request) -> tuple[bytes, str]:
    rows = database.rows("SELECT * FROM catalog_publications WHERE catalog_id=?", (int(catalog_id),))
    if not rows:
        raise ValueError("Katalogeintrag fehlt.")
    item = rows[0]
    installed = database.rows("""SELECT cover_path,thumbnail_path FROM publications WHERE key_symbol=? AND language_index=? AND year=? AND issue_tag=? ORDER BY installed_at DESC LIMIT 1""", (
        item.get("key_symbol") or "", int(item.get("language_index") or 0), int(item.get("year") or 0), int(item.get("issue_tag") or 0)
    ))
    if installed:
        for field in ("cover_path", "thumbnail_path"):
            cover = Path(str(installed[0].get(field) or ""))
            if cover.is_file() and cover.stat().st_size > 0:
                return cover.read_bytes(), mime_type(cover)
    fragment = str(item.get("image_fragment") or "")
    cache = _cover_cache_path(int(catalog_id), fragment)
    if cache.is_file() and cache.stat().st_size > 256:
        return cache.read_bytes(), mime_type(cache)
    errors = []
    for url in _cover_candidates(fragment):
        try:
            body, ctype = request_fn(url, 15_000_000, "image/avif,image/webp,image/png,image/jpeg,image/*,*/*", 35)
            if not _valid_cover(body, ctype):
                raise ValueError("Serverantwort ist kein gültiges Bild.")
            PATHS.covers.mkdir(parents=True, exist_ok=True)
            temp = cache.with_suffix(cache.suffix + ".part")
            temp.write_bytes(body)
            temp.replace(cache)
            try:
                PATHS.logs.mkdir(parents=True, exist_ok=True)
                (PATHS.logs / "catalog-network-last.json").write_text(json.dumps({
                    "catalog_id": catalog_id, "fragment": fragment, "url": url,
                    "strategy": "apk-namefragment-root", "result": "cached",
                    "cache": str(cache), "bytes": len(body), "content_type": ctype
                }, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
            return body, ctype if str(ctype).startswith("image/") else mime_type(cache)
        except Exception as exc:
            errors.append(str(exc))
    try:
        PATHS.logs.mkdir(parents=True, exist_ok=True)
        (PATHS.logs / "catalog-network-last.json").write_text(json.dumps({
            "catalog_id": catalog_id, "fragment": fragment,
            "strategy": "apk-namefragment-root", "result": "placeholder",
            "errors": errors
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return _placeholder_cover(item)


def publication_detail(catalog_id: int, database: Database = DB, request_fn: RequestFn = _request) -> dict[str, Any]:
    rows = database.rows("""SELECT c.*,l.english_name AS language_name,l.vernacular_name AS language_vernacular,
        CASE WHEN p.id IS NULL THEN 0 ELSE 1 END AS installed,p.id AS installed_id,p.cover_path AS installed_cover
        FROM catalog_publications c LEFT JOIN languages l ON l.id=c.language_index
        LEFT JOIN publications p ON p.key_symbol=c.key_symbol AND p.language_index=c.language_index AND p.year=c.year AND p.issue_tag=c.issue_tag
        WHERE c.catalog_id=? LIMIT 1""", (int(catalog_id),))
    if not rows:
        raise ValueError("Katalogeintrag wurde nicht gefunden.")
    item = rows[0]
    item["download_options"] = ([{"url": item.get("download_url"), "filename": Path(urllib.parse.urlparse(item.get("download_url") or "").path).name, "size": int(item.get("size") or 0), "cached": True}] if item.get("download_url") else [])
    item["download_error"] = ""
    item["cover_url"] = f"/api/catalog/{int(catalog_id)}/cover" if item.get("image_fragment") else ""
    item["online_available"] = True
    item["offline_available"] = bool(item.get("installed"))
    item["preview_mode"] = "reader" if item.get("installed") else "metadata"
    item["preview_message"] = "Publikation ist offline verfügbar und kann vollständig geöffnet werden." if item.get("installed") else "Vorschau zeigt Katalogdaten und Originalcover. Zum Lesen muss die JWPUB-Datei offline gespeichert werden."
    return item

def verify_download(path: Path, expected_size: int = 0, checksum: str = "") -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size < 100:
        raise ValueError("Downloaddatei ist leer oder unvollständig.")
    size = path.stat().st_size
    if expected_size and size != int(expected_size):
        raise ValueError(f"Dateigröße stimmt nicht: erwartet {expected_size}, erhalten {size}.")
    checksum = str(checksum or "").strip().lower()
    algorithm = ""
    digest = ""
    if re.fullmatch(r"[a-f0-9]{64}", checksum):
        algorithm = "sha256"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    elif re.fullmatch(r"[a-f0-9]{40}", checksum):
        algorithm = "sha1"
        digest = hashlib.sha1(path.read_bytes()).hexdigest()
    elif re.fullmatch(r"[a-f0-9]{32}", checksum):
        algorithm = "md5"
        digest = hashlib.md5(path.read_bytes()).hexdigest()
    if algorithm and digest != checksum:
        raise ValueError(f"{algorithm.upper()}-Prüfsumme stimmt nicht.")
    return {"size": size, "checksum_algorithm": algorithm, "checksum_verified": bool(algorithm)}

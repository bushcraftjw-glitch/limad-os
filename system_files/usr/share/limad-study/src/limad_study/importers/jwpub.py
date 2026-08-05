from __future__ import annotations
import json
import os
import re
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from ..config import PATHS
from ..crypto import decrypt_html
from ..database import DB, Database, normalize_dated_value
from ..backup.reconcile import reconcile_backup
from ..utils import html_to_text, json_write, safe_extract, safe_identifier, safe_zip_members, sha256_file, utc_now


def _publication_data(manifest: dict[str, Any]) -> dict[str, Any]:
    publication = manifest.get("publication") or {}
    return {
        "database": publication.get("fileName") or "",
        "title": publication.get("title") or publication.get("displayTitle") or publication.get("symbol") or "Publikation",
        "short_title": publication.get("shortTitle") or publication.get("title") or "",
        "display_title": publication.get("displayTitle") or publication.get("title") or "",
        "symbol": publication.get("symbol") or publication.get("keySymbol") or publication.get("rootSymbol") or "publication",
        "unique_symbol": publication.get("uniqueSymbol") or publication.get("uniqueEnglishSymbol") or "",
        "language_index": int(publication.get("language") or publication.get("mepsLanguageIndex") or 0),
        "year": int(publication.get("year") or 0),
        "issue_tag": int(publication.get("issueTagNumber") or publication.get("issueId") or 0),
        "publication_type": publication.get("publicationType") or "Publication",
        "categories": publication.get("categories") or [],
        "images": publication.get("images") or [],
        "timestamp": publication.get("timestamp") or manifest.get("timestamp") or "",
        "schema_version": int(publication.get("schemaVersion") or 0),
    }


def _image_name(meta: dict[str, Any], preferred_types: tuple[str, ...], available_names: set[str] | None = None) -> str:
    images = [item for item in meta.get("images", []) if isinstance(item, dict) and item.get("fileName")]
    if not images:
        return ""
    normalized = {name.replace("\\", "/") for name in available_names} if available_names is not None else None
    ranked = []
    for item in images:
        name = str(item.get("fileName") or "").replace("\\", "/").lstrip("/")
        if not name or (normalized is not None and name not in normalized):
            continue
        image_type = str(item.get("type") or "").lower()
        try:
            preference = preferred_types.index(image_type)
        except ValueError:
            preference = len(preferred_types) + 1
        width = int(item.get("width") or 0)
        height = int(item.get("height") or 0)
        ranked.append((preference, -(width * height), name))
    ranked.sort()
    return ranked[0][2] if ranked else ""


def _cover_name(meta: dict[str, Any], available_names: set[str] | None = None) -> str:
    return _image_name(meta, ("c", "t", "pns", "pnr", "sqr", "lsr"), available_names)


def _thumbnail_name(meta: dict[str, Any], available_names: set[str] | None = None) -> str:
    return _image_name(meta, ("t", "sqr", "c", "pns", "pnr", "lsr"), available_names)


def _id(meta: dict[str, Any]) -> str:
    return safe_identifier(f"{meta['symbol']}-{meta['language_index']}-{meta['year']}-{meta['issue_tag']}")


def inspect_jwpub(path: Path) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size > 2_000_000_000:
        raise ValueError("JWPUB-Datei ist zu groß.")
    with zipfile.ZipFile(path) as outer:
        names = set(outer.namelist())
        if "manifest.json" not in names or "contents" not in names:
            raise ValueError("Ungültige JWPUB-Struktur.")
        manifest = json.loads(outer.read("manifest.json").decode("utf-8-sig"))
        meta = _publication_data(manifest)
        inner_bytes = outer.read("contents")
    with tempfile.TemporaryDirectory(prefix="limad-jwpub-inspect-") as tmp:
        inner_path = Path(tmp) / "contents.zip"
        inner_path.write_bytes(inner_bytes)
        with zipfile.ZipFile(inner_path) as inner:
            members = safe_zip_members(inner)
            names = {item.filename.replace("\\", "/") for item in members}
            database_name = meta["database"]
            if database_name not in names:
                databases = [name for name in names if name.lower().endswith(".db")]
                if len(databases) != 1:
                    raise ValueError("Publikationsdatenbank wurde nicht eindeutig gefunden.")
                database_name = databases[0]
            db_path = Path(tmp) / Path(database_name).name
            with inner.open(database_name) as source, db_path.open("wb") as target:
                shutil.copyfileobj(source, target)
        con = sqlite3.connect(db_path)
        try:
            counts = {}
            for table in ["Document", "DocumentParagraph", "Multimedia", "DocumentMultimedia", "Question", "Footnote", "Hyperlink", "BibleCitation"]:
                exists = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
                counts[table] = con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] if exists else 0
        finally:
            con.close()
    return {
        "file": path.name,
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
        "manifest": manifest,
        "publication": meta,
        "publication_id": _id(meta),
        "cover": _cover_name(meta, names),
        "thumbnail": _thumbnail_name(meta, names),
        "cover_embedded": bool(_cover_name(meta, names)),
        "counts": counts,
    }


def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def _value(row: Any, key: str, default: Any = None) -> Any:
    try:
        keys = row.keys() if hasattr(row, "keys") else ()
        return row[key] if key in keys else default
    except (IndexError, KeyError, TypeError):
        return default


def _table_columns(con: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(con, table):
        return set()
    return {str(row[1]) for row in con.execute(f'PRAGMA table_info("{table}")').fetchall()}


def _split_order_expressions(order: str) -> list[str]:
    expressions: list[str] = []
    current: list[str] = []
    depth = 0
    for character in str(order or ""):
        if character == "(":
            depth += 1
        elif character == ")" and depth:
            depth -= 1
        if character == "," and depth == 0:
            expression = "".join(current).strip()
            if expression:
                expressions.append(expression)
            current = []
        else:
            current.append(character)
    expression = "".join(current).strip()
    if expression:
        expressions.append(expression)
    return expressions


def _safe_order_clause(con: sqlite3.Connection, table: str, order: str) -> str:
    columns = _table_columns(con, table)
    if not columns or not order:
        return ""
    expressions: list[str] = []
    for expression in _split_order_expressions(order):
        identifiers = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", expression)
        referenced = [name for name in identifiers if name.upper() not in {"COALESCE", "ASC", "DESC", "NULL"}]
        if referenced and all(name in columns for name in referenced):
            expressions.append(expression)
    return ",".join(expressions)


def _rows(con: sqlite3.Connection, table: str, order: str = ""):
    if not _table_exists(con, table):
        return []
    safe_order = _safe_order_clause(con, table, order)
    sql = f'SELECT * FROM "{table}"' + (f" ORDER BY {safe_order}" if safe_order else "")
    return con.execute(sql).fetchall()


def _copy_or_link(source: Path, target: Path) -> str:
    # Keep the source JWPUB without a full duplicate copy when both paths share a filesystem.
    try:
        os.link(source, target)
        return "hardlink"
    except OSError:
        shutil.copy2(source, target)
        return "copy"


def _source_counts(con: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in ["Document", "DocumentParagraph", "Multimedia", "DocumentMultimedia", "Question", "Footnote", "Hyperlink", "BibleCitation", "DatedText"]:
        counts[table] = int(con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]) if _table_exists(con, table) else 0
    return counts


def import_jwpub(path: Path, database: Database = DB, source_sha256: str = "") -> dict[str, Any]:
    # Single-pass JWPUB import: validate, extract and import from the same staging tree.
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size > 2_000_000_000:
        raise ValueError("JWPUB-Datei ist zu groß.")

    staging_parent = PATHS.publications
    staging_parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(path) as outer:
        outer_names = set(outer.namelist())
        if "manifest.json" not in outer_names or "contents" not in outer_names:
            raise ValueError("Ungültige JWPUB-Struktur.")
        manifest = json.loads(outer.read("manifest.json").decode("utf-8-sig"))
        meta = _publication_data(manifest)
        publication_id = _id(meta)
        final_dir = PATHS.publications / publication_id

        with tempfile.TemporaryDirectory(prefix=f".{publication_id}-", dir=staging_parent) as tmp_name:
            staging = Path(tmp_name)
            content_dir = staging / "content"
            content_dir.mkdir(parents=True)
            (staging / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

            inner_path = staging / "contents.zip"
            with outer.open("contents") as source, inner_path.open("wb") as target:
                shutil.copyfileobj(source, target, 4 * 1024 * 1024)

            with zipfile.ZipFile(inner_path) as inner:
                members = safe_zip_members(inner)
                extracted_names = {item.filename.replace("\\", "/") for item in members}
                safe_extract(inner, content_dir, members)
            inner_path.unlink(missing_ok=True)

            db_name = meta["database"]
            db_path = content_dir / db_name
            if not db_path.is_file():
                candidates = list(content_dir.rglob("*.db"))
                if len(candidates) != 1:
                    raise ValueError("JWPUB-Datenbank fehlt nach dem Entpacken.")
                db_path = candidates[0]
                db_name = str(db_path.relative_to(content_dir))

            cover_name = _cover_name(meta, extracted_names)
            thumbnail_name = _thumbnail_name(meta, extracted_names)
            source_copy = staging / path.name
            source_storage = _copy_or_link(path, source_copy)

            source_con = sqlite3.connect(db_path)
            source_con.row_factory = sqlite3.Row
            source_con.execute("PRAGMA query_only=ON")
            source_con.execute("PRAGMA temp_store=MEMORY")
            imported = {"documents": 0, "media": 0, "questions": 0, "footnotes": 0, "hyperlinks": 0, "citations": 0, "dated_texts": 0}
            try:
                counts = _source_counts(source_con)
                digest = str(source_sha256 or "").strip().lower()
                if not re.fullmatch(r"[a-f0-9]{64}", digest):
                    digest = sha256_file(path)
                audit = {
                    "file": path.name,
                    "size": path.stat().st_size,
                    "sha256": digest,
                    "manifest": manifest,
                    "publication": meta,
                    "publication_id": publication_id,
                    "cover": cover_name,
                    "thumbnail": thumbnail_name,
                    "cover_embedded": bool(cover_name),
                    "counts": counts,
                    "extraction_passes": 1,
                    "source_storage": source_storage,
                }

                with database.transaction() as con:
                    con.execute("PRAGMA defer_foreign_keys=ON")
                    con.execute("DELETE FROM publications WHERE id=?", (publication_id,))
                    language_symbol_row = con.execute("SELECT symbol FROM languages WHERE id=?", (meta["language_index"],)).fetchone()
                    language_symbol = language_symbol_row[0] if language_symbol_row else ""
                    metadata_json = json.dumps({**meta, "manifest_hash": digest, "database": db_name, "cover_file": cover_name, "thumbnail_file": thumbnail_name, "import_mode": "single-pass"}, ensure_ascii=False)
                    con.execute('''INSERT INTO publications(
                        id,key_symbol,unique_symbol,language_index,language_symbol,title,short_title,display_title,year,issue_tag,
                        publication_type,category,source,source_path,content_dir,db_path,cover_path,thumbnail_path,installed_at,server_updated_at,status,metadata_json
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                        publication_id, meta["symbol"], meta["unique_symbol"], meta["language_index"], language_symbol,
                        meta["title"], meta["short_title"], meta["display_title"], meta["year"], meta["issue_tag"],
                        meta["publication_type"], ",".join(meta["categories"]), "jwpub", str(final_dir / path.name),
                        str(final_dir / "content"), str(final_dir / "content" / db_name),
                        str(final_dir / "content" / cover_name) if cover_name else "", str(final_dir / "content" / thumbnail_name) if thumbnail_name else "", utc_now(), meta["timestamp"], "installed", metadata_json
                    ))
                    con.execute("DELETE FROM documents_fts WHERE publication_id=?", (publication_id,))

                    fts_rows: list[tuple[Any, ...]] = []
                    documents = _rows(source_con, "Document", "COALESCE(SectionNumber,0),COALESCE(ChapterNumber,0),DocumentId")
                    for position, row in enumerate(documents):
                        markup = decrypt_html(_value(row, "Content"), meta["language_index"], meta["symbol"], meta["year"], meta["issue_tag"])
                        plain_text = html_to_text(markup)
                        title = _value(row, "Title") or _value(row, "TocTitle") or f"Dokument {_value(row, 'DocumentId')}"
                        cursor = con.execute('''INSERT INTO documents(
                            publication_id,source_document_id,meps_document_id,chapter_number,section_number,title,toc_title,subtitle,class_name,
                            content_html,content_text,paragraph_count,sort_order
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                            publication_id, _value(row, "DocumentId"), _value(row, "MepsDocumentId"), _value(row, "ChapterNumber"), _value(row, "SectionNumber"),
                            title, _value(row, "TocTitle") or _value(row, "Title") or "", _value(row, "Subtitle") or "", _value(row, "Class") or "",
                            markup, plain_text, int(_value(row, "ParagraphCount") or 0), position
                        ))
                        fts_rows.append((title, plain_text, publication_id, cursor.lastrowid))
                    if fts_rows:
                        con.executemany("INSERT INTO documents_fts(title,content_text,publication_id,document_id) VALUES(?,?,?,?)", fts_rows)
                    imported["documents"] = len(documents)

                    if _table_exists(source_con, "Multimedia"):
                        media_rows = source_con.execute('''SELECT m.*,dm.DocumentId AS MapDocumentId,dm.BeginParagraphOrdinal,dm.EndParagraphOrdinal
                            FROM Multimedia m LEFT JOIN DocumentMultimedia dm ON dm.MultimediaId=m.MultimediaId''').fetchall()
                        media_values = [(
                            publication_id, _value(row, "MultimediaId"), _value(row, "FilePath") or "", _value(row, "MimeType") or "",
                            _value(row, "Width"), _value(row, "Height"), _value(row, "Label") or "", _value(row, "Caption") or "",
                            _value(row, "MapDocumentId"), _value(row, "BeginParagraphOrdinal"), _value(row, "EndParagraphOrdinal")
                        ) for row in media_rows]
                        con.executemany('''INSERT OR IGNORE INTO media(publication_id,source_media_id,file_path,mime_type,width,height,label,caption,document_source_id,begin_paragraph,end_paragraph)
                            VALUES(?,?,?,?,?,?,?,?,?,?,?)''', media_values)
                        imported["media"] = len(media_values)

                    question_values = []
                    for row in _rows(source_con, "Question", "QuestionId"):
                        question_values.append((publication_id, _value(row, "QuestionId"), _value(row, "DocumentId"), _value(row, "QuestionIndex"), decrypt_html(_value(row, "Content"), meta["language_index"], meta["symbol"], meta["year"], meta["issue_tag"]), _value(row, "ParagraphOrdinal"), _value(row, "TargetParagraphOrdinal")))
                    con.executemany('''INSERT INTO questions(publication_id,source_question_id,document_source_id,question_index,content_html,paragraph_ordinal,target_paragraph) VALUES(?,?,?,?,?,?,?)''', question_values)
                    imported["questions"] = len(question_values)

                    footnote_values = []
                    for row in _rows(source_con, "Footnote", "FootnoteId"):
                        footnote_values.append((publication_id, _value(row, "FootnoteId"), _value(row, "DocumentId"), _value(row, "FootnoteIndex"), _value(row, "Type"), decrypt_html(_value(row, "Content"), meta["language_index"], meta["symbol"], meta["year"], meta["issue_tag"]), _value(row, "ParagraphOrdinal")))
                    con.executemany('''INSERT INTO footnotes(publication_id,source_footnote_id,document_source_id,footnote_index,type,content_html,paragraph_ordinal) VALUES(?,?,?,?,?,?,?)''', footnote_values)
                    imported["footnotes"] = len(footnote_values)

                    hyperlink_values = [(publication_id, _value(row, "HyperlinkId"), _value(row, "Link") or "", _value(row, "MajorType"), _value(row, "KeySymbol"), _value(row, "Track"), _value(row, "MepsDocumentId"), _value(row, "MepsLanguageIndex"), _value(row, "IssueTagNumber"), _value(row, "Specialty"), _value(row, "Edition")) for row in _rows(source_con, "Hyperlink", "HyperlinkId")]
                    con.executemany('''INSERT INTO hyperlinks(publication_id,source_hyperlink_id,link,major_type,key_symbol,track,meps_document_id,meps_language_index,issue_tag,specialty,edition) VALUES(?,?,?,?,?,?,?,?,?,?,?)''', hyperlink_values)
                    imported["hyperlinks"] = len(hyperlink_values)

                    citation_values = [(publication_id, _value(row, "BibleCitationId"), _value(row, "DocumentId"), _value(row, "BlockNumber"), _value(row, "ElementNumber"), _value(row, "ParagraphOrdinal"), _value(row, "HyperlinkId")) for row in _rows(source_con, "BibleCitation", "BibleCitationId")]
                    con.executemany('''INSERT INTO bible_citations(publication_id,source_citation_id,document_source_id,block_number,element_number,paragraph_ordinal,hyperlink_source_id) VALUES(?,?,?,?,?,?,?)''', citation_values)
                    imported["citations"] = len(citation_values)

                    dated_values = []
                    for row in _rows(source_con, "DatedText", "DatedTextId"):
                        dated_values.append((publication_id, _value(row, "DatedTextId"), _value(row, "DocumentId"), _value(row, "Class"), normalize_dated_value(_value(row, "FirstDateOffset")), normalize_dated_value(_value(row, "LastDateOffset")), _value(row, "Caption") or "", decrypt_html(_value(row, "Content"), meta["language_index"], meta["symbol"], meta["year"], meta["issue_tag"]), _value(row, "BeginParagraphOrdinal"), _value(row, "EndParagraphOrdinal")))
                    con.executemany('''INSERT INTO dated_texts(publication_id,source_dated_text_id,document_source_id,class,start_date,end_date,caption,content_html,begin_paragraph,end_paragraph) VALUES(?,?,?,?,?,?,?,?,?,?)''', dated_values)
                    imported["dated_texts"] = len(dated_values)
            finally:
                source_con.close()

            json_write(staging / "import-report.json", {"audit": audit, "imported": imported, "completed_at": utc_now()})
            if final_dir.exists():
                shutil.rmtree(final_dir)
            os.replace(staging, final_dir)

    has_backup_data = bool(database.scalar("SELECT 1 FROM backup_imports LIMIT 1"))
    resolution = reconcile_backup(None, database) if has_backup_data else {"skipped": True, "reason": "no_backup_data"}
    return {"publication_id": publication_id, "title": meta["title"], "cover": cover_name, "thumbnail": thumbnail_name, "counts": imported, "audit": audit, "backup_resolution": resolution}

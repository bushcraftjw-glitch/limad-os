from __future__ import annotations

import html
import json
import re
import sqlite3
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from ..crypto import decrypt_html
from ..database import DB, Database
from ..utils import html_to_text
from .service import bible_chapter, bible_library


class _AnchorCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._current: dict[str, Any] | None = None
        self.anchors: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs):
        if tag.lower() != "a":
            return
        values = {str(k).lower(): str(v or "") for k, v in attrs}
        self._current = {"href": values.get("href", ""), "text": ""}

    def handle_data(self, data: str):
        if self._current is not None:
            self._current["text"] += data

    def handle_endtag(self, tag: str):
        if tag.lower() == "a" and self._current is not None:
            self._current["text"] = re.sub(r"\s+", " ", self._current["text"]).strip()
            if self._current["href"]:
                self.anchors.append(self._current)
            self._current = None


def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def _source_connect(path: str | Path) -> sqlite3.Connection:
    target = Path(str(path or "")).expanduser()
    if not target.is_file():
        raise FileNotFoundError(f"Publikationsdatenbank fehlt: {target}")
    con = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _publication_meta(publication: dict[str, Any]) -> tuple[int, str, int, int]:
    metadata = {}
    try:
        metadata = json.loads(publication.get("metadata_json") or "{}")
    except Exception:
        metadata = {}
    return (
        int(publication.get("language_index") or metadata.get("language_index") or 0),
        str(publication.get("key_symbol") or metadata.get("symbol") or ""),
        int(publication.get("year") or metadata.get("year") or 0),
        int(publication.get("issue_tag") or metadata.get("issue_tag") or 0),
    )


def _safe_markup(markup: str) -> str:
    # JWPUB-Inhalte sind lokal und signiert, werden aber trotzdem ohne aktive
    # Skripte, Formulare oder Inline-Ereignisse in das Seitenpanel eingesetzt.
    text = str(markup or "")
    text = re.sub(r"<(script|style|iframe|object|embed|form)\b[^>]*>.*?</\1\s*>", "", text, flags=re.I | re.S)
    text = re.sub(r"\s+on[a-z]+\s*=\s*([\"']).*?\1", "", text, flags=re.I | re.S)
    text = re.sub(r"\s+(srcdoc|formaction)\s*=\s*([\"']).*?\2", "", text, flags=re.I | re.S)
    return text


def _resolve_media(markup: str, publication_id: str) -> str:
    # Gleiches Schema wie reader/render.py: jwpub-media:// zeigt auf die
    # statische Auslieferung unter /content/<publication_id>/<pfad>.
    prefix = f"/content/{publication_id}/"
    text = re.sub(
        r'''(src|poster)=(['"])jwpub-media://([^'"?#]+)(?:[^'"]*)\2''',
        lambda m: f'{m.group(1)}={m.group(2)}{prefix}{m.group(3)}{m.group(2)}',
        markup or "",
        flags=re.I,
    )
    # Video/Audio bekommen Bedienelemente sowie Vollbild- und
    # "Im Hauptfenster öffnen"-Schalter für das rechte Quellenfenster.
    def _video(match: "re.Match[str]") -> str:
        tag = match.group(0)
        if "controls" not in tag.lower():
            tag = tag[:-1] + ' controls playsinline' + tag[-1]
        return (
            '<div class="bible-reference-media bible-reference-media-video">' + tag +
            '<div class="bible-reference-media-actions">'
            '<button class="icon-button" data-media-fullscreen title="Vollbild">⛶</button>'
            '<button class="icon-button" data-media-open-main title="Im Hauptfenster öffnen">↗</button>'
            '</div></div>'
        )
    text = re.sub(r'<video\b[^>]*>(?:.*?</video>)?', _video, text, flags=re.I | re.S)

    def _audio(match: "re.Match[str]") -> str:
        tag = match.group(0)
        if "controls" not in tag.lower():
            tag = tag[:-1] + ' controls' + tag[-1]
        return '<div class="bible-reference-media bible-reference-media-audio">' + tag + '</div>'
    text = re.sub(r'<audio\b[^>]*>(?:.*?</audio>)?', _audio, text, flags=re.I | re.S)

    def _img(match: "re.Match[str]") -> str:
        return (
            '<figure class="bible-reference-media bible-reference-media-image">' + match.group(0) +
            '<button class="icon-button bible-reference-media-zoom" data-media-fullscreen title="Vollbild">⛶</button></figure>'
        )
    text = re.sub(r'<img\b[^>]*/?>', _img, text, flags=re.I)
    return text


def _anchors(markup: str) -> list[dict[str, str]]:
    parser = _AnchorCollector()
    try:
        parser.feed(markup or "")
        parser.close()
    except Exception:
        return []
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in parser.anchors:
        href = item.get("href", "").strip()
        label = item.get("text", "").strip() or href
        key = (href, label)
        if href and key not in seen:
            seen.add(key)
            result.append({"href": href, "label": label})
    return result


def _paragraphs_containing(markup: str, needle: str) -> list[str]:
    # Die Einträge des Studienleitfadens sind überwiegend einzelne p-Elemente.
    # Der Fallback auf Zeilen erhält auch ältere Varianten mit verschachtelten divs.
    blocks = re.findall(r"<p\b[^>]*>.*?</p\s*>", markup or "", flags=re.I | re.S)
    selected = [block for block in blocks if needle.casefold() in html_to_text(block).casefold()]
    return selected


# Einheitliche interne Bibelbuch-IDs. Sichtbare Namen und Abkürzungen werden
# nur noch für die Anzeige benutzt; Verknüpfungen laufen über Buch/Kapitel/Vers.
_BIBLE_BOOK_NAMES_DE = {
    1: "1. Mose", 2: "2. Mose", 3: "3. Mose", 4: "4. Mose", 5: "5. Mose",
    6: "Josua", 7: "Richter", 8: "Ruth", 9: "1. Samuel", 10: "2. Samuel",
    11: "1. Könige", 12: "2. Könige", 13: "1. Chronika", 14: "2. Chronika",
    15: "Esra", 16: "Nehemia", 17: "Esther", 18: "Hiob", 19: "Psalmen",
    20: "Sprüche", 21: "Prediger", 22: "Hohes Lied", 23: "Jesaja",
    24: "Jeremia", 25: "Klagelieder", 26: "Hesekiel", 27: "Daniel",
    28: "Hosea", 29: "Joel", 30: "Amos", 31: "Obadja", 32: "Jona",
    33: "Micha", 34: "Nahum", 35: "Habakuk", 36: "Zephanja",
    37: "Haggai", 38: "Sacharja", 39: "Maleachi", 40: "Matthäus",
    41: "Markus", 42: "Lukas", 43: "Johannes", 44: "Apostelgeschichte",
    45: "Römer", 46: "1. Korinther", 47: "2. Korinther", 48: "Galater",
    49: "Epheser", 50: "Philipper", 51: "Kolosser", 52: "1. Thessalonicher",
    53: "2. Thessalonicher", 54: "1. Timotheus", 55: "2. Timotheus",
    56: "Titus", 57: "Philemon", 58: "Hebräer", 59: "Jakobus",
    60: "1. Petrus", 61: "2. Petrus", 62: "1. Johannes", 63: "2. Johannes",
    64: "3. Johannes", 65: "Judas", 66: "Offenbarung",
}

def _canonical_verse_key(book_number: int, chapter_number: int, verse_number: int, verse_id: int) -> str:
    if book_number > 0 and chapter_number > 0 and verse_number > 0:
        return f"b{book_number:02d}-c{chapter_number:03d}-v{verse_number:03d}"
    return f"meps-{int(verse_id)}"

def _missing_action(title: str, message: str, action: str = "publications") -> dict[str, Any]:
    payload = _empty(title, message, installed=False)
    payload["action"] = action
    payload["html"] = (
        f'<div class="bible-v2-empty bible-source-missing"><strong>{html.escape(title)}</strong>'
        f'<p>{html.escape(message)}</p>'
        f'<button class="button primary" data-bible-source-action="{html.escape(action, quote=True)}">Importieren oder installieren</button></div>'
    )
    return payload


def _empty(title: str, message: str, *, installed: bool = False) -> dict[str, Any]:
    return {
        "title": title,
        "installed": bool(installed),
        "count": 0,
        "html": f'<div class="bible-v2-empty"><strong>{html.escape(title)}</strong><p>{html.escape(message)}</p></div>',
    }


def _guide_material(current_publication_id: str, verse_id: int, language_index: int, database: Database) -> tuple[dict[str, Any], list[dict[str, str]]]:
    # Priorität: zuerst die aktuell geöffnete Studienbibel selbst. Die nwtsty-JWPUB
    # enthält eigene VerseCommentary-Daten. Erst danach folgt der separate
    # Studienleitfaden als lokale Ergänzung.
    current_rows = database.rows(
        "SELECT * FROM publications WHERE id=? AND language_index=? LIMIT 1",
        (str(current_publication_id), language_index),
    )
    guide_rows = database.rows(
        "SELECT * FROM publications WHERE language_index=? AND id<>? "
        "AND (lower(key_symbol) LIKE 'rsg%' OR lower(title) LIKE '%studienleitfaden%') "
        "ORDER BY year DESC,installed_at DESC",
        (language_index, str(current_publication_id)),
    )
    publications = [row for row in current_rows if row.get("db_path")] + [row for row in guide_rows if row.get("db_path")]
    if not publications:
        return _missing_action("Studienleitfaden", "Weder die Studienbibel noch der Studienleitfaden enthält lokal lesbare Quelldaten.", "publications"), []

    errors: list[str] = []
    all_markup: list[str] = []
    all_links: list[dict[str, str]] = []
    source_title = publications[0].get("title") or "Studienleitfaden"
    seen_commentaries: set[tuple[int, int, int]] = set()
    for publication in publications:
        try:
            con = _source_connect(publication.get("db_path") or "")
            try:
                if not (_table_exists(con, "VerseCommentary") and _table_exists(con, "VerseCommentaryMap")):
                    continue
                rows = con.execute(
                    "SELECT vc.VerseCommentaryId,vc.CommentaryType,vc.Label,vc.Content,vc.CommentaryMepsDocumentId,"
                    "vc.BeginParagraphOrdinal,vc.EndParagraphOrdinal "
                    "FROM VerseCommentary vc JOIN VerseCommentaryMap vm ON vm.VerseCommentaryId=vc.VerseCommentaryId "
                    "WHERE vm.BibleVerseId=? ORDER BY vc.VerseCommentaryId",
                    (int(verse_id),),
                ).fetchall()
                language, symbol, year, issue = _publication_meta(publication)
                for row in rows:
                    dedup_key = (
                        int(row["CommentaryMepsDocumentId"] or 0),
                        int(row["BeginParagraphOrdinal"] or 0),
                        int(row["EndParagraphOrdinal"] or 0),
                    )
                    if dedup_key in seen_commentaries:
                        continue
                    seen_commentaries.add(dedup_key)
                    label = _safe_markup(str(row["Label"] or ""))
                    content = _resolve_media(_safe_markup(decrypt_html(row["Content"], language, symbol, year, issue)), str(publication["id"]))
                    document_rows = database.rows(
                        "SELECT id FROM documents WHERE publication_id=? AND meps_document_id=? LIMIT 1",
                        (publication["id"], row["CommentaryMepsDocumentId"]),
                    )
                    open_button = ""
                    if document_rows:
                        open_button = (
                            f'<button class="text-button" data-document-id="{int(document_rows[0]["id"])}" '
                            f'data-block-identifier="{int(row["BeginParagraphOrdinal"] or 0)}">Lokal öffnen</button>'
                        )
                    all_markup.append(
                        '<article class="bible-reference-card bible-reference-guide">'
                        f'<header><span>{html.escape(publication.get("short_title") or publication.get("title") or source_title)}</span>{open_button}</header>'
                        f'<div class="bible-reference-label">{label}</div>'
                        f'<div class="bible-reference-body">{content}</div>'
                        '</article>'
                    )
                    all_links.extend(_anchors(content))
            finally:
                con.close()
        except Exception as exc:
            errors.append(f"{publication.get('title') or publication.get('id')}: {exc}")

    if not all_markup:
        message = "Für diesen Vers enthält die installierte Studienbibel keinen Eintrag."
        if errors:
            message += " Die lokalen Quelldaten konnten teilweise nicht gelesen werden."
        return _empty("Studienleitfaden", message, installed=True), []
    return {
        "title": "Studienleitfaden",
        "installed": True,
        "count": len(all_markup),
        "html": "".join(all_markup),
        "source_title": source_title,
        "resolution_order": ["current-jwpub", "local-study-guide", "jw.org"],
    }, all_links

def _insight_fallback(verse_id: int, language_index: int, database: Database) -> list[dict[str, Any]]:
    publications = database.rows(
        "SELECT * FROM publications WHERE language_index=? AND (lower(key_symbol) LIKE 'it%' OR lower(title) LIKE 'einsichten%') "
        "ORDER BY year DESC,installed_at DESC",
        (language_index,),
    )
    hits: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for publication in publications:
        try:
            con = _source_connect(publication.get("db_path") or "")
            try:
                if not _table_exists(con, "BibleCitation"):
                    continue
                columns = {str(row[1]) for row in con.execute('PRAGMA table_info("BibleCitation")').fetchall()}
                if {"FirstBibleVerseId", "LastBibleVerseId"}.issubset(columns):
                    rows = con.execute(
                        "SELECT DocumentId,ParagraphOrdinal FROM BibleCitation "
                        "WHERE (FirstBibleVerseId<=? AND LastBibleVerseId>=?) OR BibleVerseId=? "
                        "ORDER BY DocumentId,ParagraphOrdinal LIMIT 80",
                        (verse_id, verse_id, verse_id),
                    ).fetchall()
                else:
                    rows = []
                for row in rows:
                    key = (publication["id"], int(row["DocumentId"]))
                    if key in seen:
                        continue
                    seen.add(key)
                    docs = database.rows(
                        "SELECT id,title,toc_title,content_html FROM documents WHERE publication_id=? AND source_document_id=? LIMIT 1",
                        (publication["id"], int(row["DocumentId"])),
                    )
                    if not docs:
                        continue
                    doc = docs[0]
                    ordinal = int(row["ParagraphOrdinal"] or 0)
                    pattern = rf'<(?:p|div)\b[^>]*(?:data-pid|id)=["\'](?:p)?{ordinal}["\'][^>]*>.*?</(?:p|div)\s*>'
                    match = re.search(pattern, doc.get("content_html") or "", flags=re.I | re.S)
                    snippet = _resolve_media(_safe_markup(match.group(0)), str(publication["id"])) if match else ""
                    hits.append({
                        "document_id": int(doc["id"]),
                        "block_identifier": ordinal,
                        "title": doc.get("toc_title") or doc.get("title") or publication.get("title") or "Einsichten",
                        "publication_title": publication.get("title") or "Einsichten",
                        "snippet_html": snippet,
                    })
                    if len(hits) >= 24:
                        return hits
            finally:
                con.close()
        except Exception:
            continue
    return hits


def _insight_material(guide_html: str, guide_links: list[dict[str, str]], verse_id: int, language_index: int, database: Database, *, allow_fallback: bool = True) -> dict[str, Any]:
    insight_blocks = _paragraphs_containing(guide_html, "Einsichten")
    local_publications = database.rows(
        "SELECT id,title FROM publications WHERE language_index=? AND (lower(key_symbol) LIKE 'it%' OR lower(title) LIKE 'einsichten%')",
        (language_index,),
    )
    installed = bool(local_publications)
    if insight_blocks:
        note = "" if installed else '<div class="bible-reference-hint">„Einsichten“ ist noch nicht lokal importiert. Die Verweise aus dem Studienleitfaden werden trotzdem angezeigt.</div>'
        return {
            "title": "Einsichten",
            "installed": installed,
            "count": len(insight_blocks),
            "html": note + '<article class="bible-reference-card bible-reference-insight">' + "".join(insight_blocks) + "</article>",
        }

    if not allow_fallback:
        return {
            "title": "Einsichten",
            "installed": installed,
            "count": 0,
            "lazy": True,
            "html": '<div class="bible-reference-lazy">Einsichten werden erst beim Öffnen dieser Registerkarte durchsucht.</div>',
        }

    hits = _insight_fallback(verse_id, language_index, database)
    if hits:
        cards = []
        for hit in hits:
            cards.append(
                '<article class="bible-reference-card bible-reference-insight">'
                f'<header><span>{html.escape(hit["publication_title"])}</span></header>'
                f'<h4>{html.escape(hit["title"])}</h4>'
                f'{hit["snippet_html"]}'
                f'<button class="button" data-document-id="{hit["document_id"]}" data-block-identifier="{hit["block_identifier"]}">Quelle öffnen</button>'
                '</article>'
            )
        return {"title": "Einsichten", "installed": True, "count": len(hits), "html": "".join(cards)}

    return _empty(
        "Einsichten",
        "Für diesen Vers wurde kein Einsichten-Verweis gefunden." if installed else "Importiere das Einsichtenbuch, damit die verknüpften Quellen lokal geöffnet werden können.",
        installed=installed,
    ) if installed else _missing_action("Einsichten", "Das Einsichtenbuch ist nicht installiert. Importiere die JWPUB-Ausgabe über Publikationen.", "publications")


def _cross_material(publication_id: str, book_number: int, chapter_number: int, verse_id: int, database: Database) -> dict[str, Any]:
    try:
        chapter = bible_chapter(publication_id, book_number, chapter_number, database)
    except Exception:
        return _empty("Querverweise", "Der Bibeltext konnte für die Querverweise nicht gelesen werden.")
    verse = next((item for item in chapter.get("verses") or [] if int(item.get("id") or -1) == int(verse_id)), None)
    links = [item for item in _anchors(str((verse or {}).get("content_html") or "")) if item["href"].lower().startswith("jwpub://b/")]
    unique: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in links:
        if item["href"] in seen:
            continue
        seen.add(item["href"])
        unique.append(item)
    if not unique:
        return _empty("Querverweise", "Für diesen Vers sind in der installierten Bibel keine Querverweise hinterlegt.", installed=True)
    items = "".join(
        f'<button class="bible-cross-link" data-bible-source-href="{html.escape(item["href"], quote=True)}">{html.escape(item["label"] or "Bibelstelle öffnen")}</button>'
        for item in unique
    )
    return {
        "title": "Querverweise",
        "installed": True,
        "count": len(unique),
        "html": f'<div class="bible-cross-list">{items}</div><div id="bible-reference-preview"></div>',
    }


def _notes_material(document_id: int, verse_id: int, verse_number: int, database: Database) -> dict[str, Any]:
    values = {int(verse_id)}
    if verse_number:
        values.add(int(verse_number))
    placeholders = ",".join("?" for _ in values)
    params = [int(document_id), *sorted(values)]
    local = database.rows(
        f"SELECT id,title,content,block_identifier,modified_at FROM local_notes WHERE document_id=? AND block_identifier IN ({placeholders}) ORDER BY modified_at DESC",
        tuple(params),
    )
    imported = database.rows(
        f"SELECT CAST(n.note_id AS TEXT)||':'||n.backup_id AS id,n.title,n.content,n.block_identifier,n.last_modified AS modified_at "
        f"FROM notes n JOIN backup_resolution r ON r.backup_id=n.backup_id AND r.location_id=n.location_id "
        f"WHERE r.document_row_id=? AND n.block_identifier IN ({placeholders}) ORDER BY n.last_modified DESC",
        tuple(params),
    )
    rows = local + imported
    if not rows:
        return {
            "title": "Notizen",
            "installed": True,
            "count": 0,
            "html": '<div class="bible-v2-empty"><p>Zu diesem Vers gibt es noch keine Notiz.</p><button class="button primary" data-bible-create-note>Notiz erstellen</button></div>',
        }
    cards = "".join(
        '<article class="bible-reference-card bible-reference-note">'
        f'<h4>{html.escape(row.get("title") or "Notiz")}</h4>'
        f'<p>{html.escape(row.get("content") or "")}</p>'
        '</article>'
        for row in rows
    )
    return {
        "title": "Notizen",
        "installed": True,
        "count": len(rows),
        "html": cards + '<button class="button primary" data-bible-create-note>Weitere Notiz erstellen</button>',
    }


def _parallel_material(current_publication_id: str, language_index: int, book_number: int, chapter_number: int, verse_number: int, database: Database = DB) -> dict[str, Any]:
    if not (book_number and chapter_number and verse_number):
        return _empty("Parallelübersetzungen", "Für diese Bibelstelle ist kein Versvergleich möglich.")
    cards: list[str] = []
    for publication in bible_library(language_index, database):
        if str(publication.get("id")) == str(current_publication_id):
            continue
        try:
            chapter = bible_chapter(str(publication["id"]), book_number, chapter_number, database)
        except Exception:
            continue
        match = next(
            (v for v in chapter.get("verses") or [] if str(v.get("label") or "").strip() == str(verse_number)),
            None,
        )
        if not match:
            continue
        text = html_to_text(str(match.get("content_html") or "")).strip()
        if not text:
            continue
        cards.append(
            '<article class="bible-reference-card bible-reference-parallel">'
            f'<header><span>{html.escape(str(publication.get("short_title") or publication.get("title") or ""))}</span></header>'
            f'<p>{html.escape(text)}</p>'
            '</article>'
        )
    if not cards:
        return _empty(
            "Parallelübersetzungen",
            "Keine weitere lokal installierte Bibel in dieser Sprache gefunden. Installiere eine zweite Übersetzung über Publikationen.",
        )
    return {"title": "Parallelübersetzungen", "installed": True, "count": len(cards), "html": "".join(cards)}


def verse_material(document_id: int, verse_id: int, verse_number: int = 0, verse_text: str = "", database: Database = DB, requested_tab: str | None = None) -> dict[str, Any]:
    rows = database.rows(
        "SELECT d.id,d.publication_id,d.chapter_number,d.section_number,d.title,p.title AS publication_title,p.language_index "
        "FROM documents d JOIN publications p ON p.id=d.publication_id WHERE d.id=?",
        (int(document_id),),
    )
    if not rows:
        raise ValueError("Das geöffnete Bibelkapitel wurde nicht gefunden.")
    document = rows[0]
    language_index = int(document.get("language_index") or 2)
    book_number = int(document.get("section_number") or 0)
    chapter_number = int(document.get("chapter_number") or 0)
    verse_number = int(verse_number or 0)
    book_name = _BIBLE_BOOK_NAMES_DE.get(book_number) or str(document.get("title") or "Bibelstelle")
    reference = f"{book_name} {chapter_number}:{verse_number}" if chapter_number and verse_number else str(document.get("title") or "Bibelstelle")
    canonical_key = _canonical_verse_key(book_number, chapter_number, verse_number, int(verse_id))

    guide, guide_links = _guide_material(str(document["publication_id"]), int(verse_id), language_index, database)
    guide_html = guide.get("html") or ""
    insight = _insight_material(guide_html, guide_links, int(verse_id), language_index, database, allow_fallback=requested_tab == "insight")
    cross = _cross_material(str(document["publication_id"]), book_number, chapter_number, int(verse_id), database)
    notes = _notes_material(int(document_id), int(verse_id), verse_number, database)
    parallel = _parallel_material(str(document["publication_id"]), language_index, book_number, chapter_number, verse_number, database)

    return {
        "document_id": int(document_id),
        "publication_id": str(document["publication_id"]),
        "book_number": book_number,
        "chapter_number": chapter_number,
        "verse_id": int(verse_id),
        "verse_number": verse_number,
        "verse_text": str(verse_text or ""),
        "reference": reference,
        "canonical_verse_key": canonical_key,
        # Die ersten vier Quellen bleiben in der aus preview17 bekannten festen
        # Reihenfolge; Parallelübersetzungen kommen als fünfte, optionale Quelle dazu.
        "source_order": ["guide", "insight", "cross", "notes", "parallel"],
        "tabs": {
            "guide": {**guide, "priority": 10},
            "insight": {**insight, "priority": 20},
            "cross": {**cross, "priority": 30},
            "notes": {**notes, "priority": 40},
            "parallel": {**parallel, "priority": 50},
        },
    }

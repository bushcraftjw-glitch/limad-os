from __future__ import annotations

import html
import re
import urllib.parse
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any

from .database import DB
from .catalog import publications as catalog_publications
from .media import (
    list_media, extract_natural_key, mediator_media_item, prepare_media_for_playback, language_symbol,
    extract_publication_media_reference, extract_media_kind, publication_media_item,
)
from .bible import bible_library, bible_chapter, bible_chapter_document_id
from .bible.service import BIBLE_BOOKS_DE


PUBLICATION_SYMBOLS = {
    "mwb", "km", "w", "ws", "wp", "g", "lfb", "lff", "th", "md", "rr", "bt", "jy",
    "ia", "cl", "kr", "od", "sjj", "lmd", "mrt", "es", "lv", "bh", "fg", "jl", "it",
    "nwt", "nwtsty", "rsg", "yp", "ypq", "ijw", "ijwbq", "ijwfq", "ijwcl", "ijwfg"
}

def _document_payload(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if not document:
        return document
    item = dict(document)
    publication_id = str(item.get("publication_id") or "")
    if publication_id:
        item["cover_url"] = f"/api/publications/{urllib.parse.quote(publication_id, safe='')}/cover"
    try:
        rows = DB.rows("SELECT content_text FROM documents WHERE id=?", (int(item.get("id") or 0),))
        if rows:
            text = re.sub(r"\s+", " ", str(rows[0].get("content_text") or "")).strip()
            item["excerpt"] = text[:420] + ("…" if len(text) > 420 else "")
    except Exception:
        item["excerpt"] = ""
    return item


def _finalize_result(result: dict[str, Any] | None) -> dict[str, Any] | None:
    if result is None:
        return None
    output = dict(result)
    if output.get("document"):
        output["document"] = _document_payload(output.get("document"))
    if output.get("kind") == "publication" and not output.get("resolved"):
        output.setdefault("missing_message", "Diese Literatur ist noch nicht lokal installiert.")
    if output.get("catalog"):
        normalized = []
        for candidate in output.get("catalog") or []:
            item = dict(candidate)
            catalog_id = item.get("catalog_id")
            if catalog_id:
                item.setdefault("cover_url", f"/api/catalog/{catalog_id}/cover")
            normalized.append(item)
        output["catalog"] = normalized
    return output


STOP_WORDS = {
    "video", "audio", "zeigen", "zeig", "das", "der", "die", "den", "dem", "ein", "eine",
    "einer", "eines", "und", "oder", "online", "öffnen", "oeffnen", "quelle", "lektion",
    "geschichte", "kapitel", "abs", "absatz", "seite", "s"
}


def normalize(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = text.replace("–", "-").replace("—", "-").replace("−", "-")
    text = text.replace("ö", "oe").replace("ä", "ae").replace("ü", "ue").replace("ß", "ss")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.replace("º", "").replace("°", "")
    text = re.sub(r"[\u00a0\u202f\u2007\t\r\n]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _book_aliases() -> list[tuple[str, int]]:
    aliases: list[tuple[str, int]] = []
    for number, title, _chapters, _testament, extra_aliases in BIBLE_BOOKS_DE:
        names = [title, *extra_aliases]
        for name in names:
            key = normalize(name).replace(".", "")
            if key:
                aliases.append((key, int(number)))
    manual = {
        "gen": 1, "1mo": 1, "1 mo": 1, "1 mose": 1, "1 buch mose": 1, "erstes buch mose": 1,
        "ex": 2, "2mo": 2, "2 mo": 2, "2 mose": 2, "2 buch mose": 2, "zweites buch mose": 2,
        "lev": 3, "3mo": 3, "3 mo": 3, "3 mose": 3, "3 buch mose": 3, "drittes buch mose": 3,
        "num": 4, "4mo": 4, "4 mo": 4, "4 mose": 4, "4 buch mose": 4, "viertes buch mose": 4,
        "deut": 5, "5mo": 5, "5 mo": 5, "5 mose": 5, "5 buch mose": 5, "fuenftes buch mose": 5,
        "jos": 6, "ri": 7, "rut": 8, "1sa": 9, "2sa": 10, "1koen": 11, "2koen": 12,
        "1chr": 13, "2chr": 14, "esr": 15, "neh": 16, "est": 17, "hi": 18,
        "ps": 19, "spr": 20, "pred": 21, "hl": 22, "jes": 23, "jer": 24, "kla": 25,
        "hes": 26, "dan": 27, "hos": 28, "joel": 29, "am": 30, "ob": 31, "jona": 32,
        "mi": 33, "nah": 34, "hab": 35, "zeph": 36, "hag": 37, "sach": 38, "mal": 39,
        "mat": 40, "mt": 40, "mar": 41, "mk": 41, "luk": 42, "lk": 42,
        "joh": 43, "jo": 43, "johannes": 43, "apg": 44, "roem": 45, "rom": 45,
        "1kor": 46, "1 ko": 46, "1 kor": 46, "2kor": 47, "2 ko": 47, "2 kor": 47,
        "gal": 48, "eph": 49, "php": 50, "phil": 50, "kol": 51,
        "1th": 52, "1 thes": 52, "2th": 53, "2 thes": 53,
        "1ti": 54, "1 tim": 54, "2ti": 55, "2 tim": 55, "tit": 56, "phm": 57,
        "heb": 58, "jak": 59, "1pe": 60, "1 pet": 60, "2pe": 61, "2 pet": 61,
        "1jo": 62, "1 joh": 62, "2jo": 63, "2 joh": 63, "3jo": 64, "3 joh": 64,
        "jud": 65, "off": 66, "offb": 66
    }
    aliases.extend((key, value) for key, value in manual.items())
    dedup: dict[str, int] = {}
    for key, value in aliases:
        dedup[key] = value
    return sorted(dedup.items(), key=lambda item: len(item[0]), reverse=True)


BOOK_ALIASES = _book_aliases()


def parse_verse_spec(spec: str) -> list[int]:
    values: list[int] = []
    for part in re.split(r"\s*[,;]\s*", str(spec or "")):
        part = part.strip()
        if not part:
            continue
        match = re.fullmatch(r"(\d{1,3})\s*-\s*(\d{1,3})", part)
        if match:
            start, end = int(match.group(1)), int(match.group(2))
            if abs(end - start) <= 200:
                values.extend(range(min(start, end), max(start, end) + 1))
        elif part.isdigit():
            values.append(int(part))
    return list(dict.fromkeys(values))[:200]


def parse_bible_reference(value: str) -> dict[str, Any] | None:
    text = normalize(value).replace(".", "")
    for alias, book_number in BOOK_ALIASES:
        match = re.search(rf"(?<![\w]){re.escape(alias)}(?=\s*\d|\s|$)", text)
        if not match:
            continue
        tail = text[match.end():]
        verse_match = re.search(
            r"(\d{1,3})\s*[:;,]\s*(\d{1,3}(?:\s*-\s*\d{1,3})?(?:\s*[,;]\s*\d{1,3}(?:\s*-\s*\d{1,3})?)*)",
            tail,
        )
        if not verse_match:
            continue
        verses = parse_verse_spec(verse_match.group(2))
        if verses:
            return {
                "book_number": book_number,
                "chapter": int(verse_match.group(1)),
                "verses": verses,
                "reference": value.strip(),
            }
    return None


def _preferred_bible(language_index: int) -> dict[str, Any] | None:
    items = bible_library(language_index)
    items.sort(
        key=lambda item: (
            0 if str(item.get("key_symbol") or "").lower() == "nwtsty" else
            1 if str(item.get("key_symbol") or "").lower() == "nwt" else 2,
            str(item.get("title") or ""),
        )
    )
    return items[0] if items else None



def _extract_verses_from_text(content_text: str, chapter_number: int) -> dict[int, str]:
    text = str(content_text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.split("\n") if line.strip()]
    if not lines:
        return {}

    verses: dict[int, str] = {}
    current_number: int | None = None
    current_parts: list[str] = []

    def flush() -> None:
        nonlocal current_number, current_parts
        if current_number is not None and current_parts:
            value = " ".join(part for part in current_parts if part).strip()
            if value:
                verses[current_number] = value
        current_number = None
        current_parts = []

    first = lines[0]
    chapter_prefix = re.match(rf"^{int(chapter_number)}\s+(.*)$", first)
    if chapter_prefix and chapter_prefix.group(1).strip():
        current_number = 1
        current_parts = [chapter_prefix.group(1).strip()]
        lines = lines[1:]

    for line in lines:
        marker = re.match(r"^(\d{1,3})\s+(.*)$", line)
        if marker:
            number = int(marker.group(1))
            body = marker.group(2).strip()
            if 1 <= number <= 200:
                flush()
                current_number = number
                current_parts = [body]
                continue
        if current_number is None:
            current_number = 1
            current_parts = [line]
        else:
            current_parts.append(line)
    flush()
    return verses


def _fallback_bible_verses(document_id: int, chapter_number: int, wanted: set[int]) -> tuple[list[str], int | None, list[int]]:
    rows = DB.rows("SELECT content_text FROM documents_fts WHERE document_id=? LIMIT 1", (document_id,))
    if not rows:
        return [], None, []
    verses = _extract_verses_from_text(str(rows[0].get("content_text") or ""), chapter_number)
    blocks: list[str] = []
    found: list[int] = []
    first_identifier: int | None = None
    for number in sorted(wanted):
        body = verses.get(number)
        if not body:
            continue
        if first_identifier is None:
            first_identifier = number
        found.append(number)
        blocks.append(
            f'<section class="context-bible-verse" data-verse="{number}"><b>{number}</b> {body}</section>'
        )
    return blocks, first_identifier, found

def resolve_bible(reference: dict[str, Any], language_index: int) -> dict[str, Any] | None:
    bible = _preferred_bible(language_index)
    if not bible:
        return {
            "resolved": False,
            "kind": "bible",
            "reference": reference["reference"],
            "error": "Keine Bibel lokal installiert.",
        }
    publication_id = str(bible["id"])
    document_id = bible_chapter_document_id(publication_id, reference["book_number"], reference["chapter"])
    chapter = bible_chapter(publication_id, reference["book_number"], reference["chapter"])
    wanted = set(reference["verses"])
    blocks: list[str] = []
    first_identifier = None
    found_numbers: list[int] = []
    for verse in chapter.get("verses") or []:
        label = str(verse.get("label") or "")
        number_match = re.match(r"^(\d{1,3})(?:\D|$)", label)
        if not number_match:
            continue
        number = int(number_match.group(1))
        if number not in wanted:
            continue
        if first_identifier is None:
            first_identifier = verse.get("id")
        found_numbers.append(number)
        blocks.append(
            f'<section class="context-bible-verse" data-verse="{number}"><b>{number}</b> '
            f'{verse.get("content_html") or ""}</section>'
        )
    if not blocks and document_id is not None:
        fallback_blocks, fallback_identifier, fallback_found = _fallback_bible_verses(
            int(document_id), int(reference["chapter"]), wanted
        )
        blocks = fallback_blocks
        first_identifier = fallback_identifier
        found_numbers = fallback_found

    rows = DB.rows(
        """SELECT d.id,d.title,d.toc_title,d.subtitle,d.meps_document_id,d.source_document_id,
        p.id AS publication_id,p.title AS publication_title,p.key_symbol,p.language_index
        FROM documents d JOIN publications p ON p.id=d.publication_id WHERE d.id=?""",
        (document_id,),
    )
    if not rows:
        return None
    return {
        "resolved": bool(blocks),
        "kind": "bible",
        "document": rows[0],
        "block_identifier": first_identifier,
        "verse_html": "".join(blocks),
        "reference": reference["reference"],
        "verse_numbers": reference["verses"],
        "found_verse_numbers": found_numbers,
    }


def parse_publication_reference(value: str) -> dict[str, Any] | None:
    text = normalize(value)
    symbol_pattern = "|".join(sorted(PUBLICATION_SYMBOLS, key=len, reverse=True))
    match = re.search(rf"(?<![\w])({symbol_pattern})(\d{{2}})?(?=\s|\d|\b)", text, re.I)
    if not match:
        return None
    base_symbol = match.group(1).lower()
    suffix = match.group(2)
    full_symbol = f"{base_symbol}{suffix}" if suffix else base_symbol
    year = None
    if suffix:
        numeric = int(suffix)
        year = 2000 + numeric if numeric <= 40 else 1900 + numeric
    kind_match = re.search(r"(?:lektion|geschichte|kapitel|artikel|lied)\s*(\d{1,4})(?:\s*-\s*(\d{1,4}))?", text)
    paragraph_match = re.search(r"(?:abs\.?|absatz)\s*(\d{1,4})", text)
    page_match = re.search(r"(?:^|\s)(?:s\.?|seite)\s*(\d{1,4})(?:\s*-\s*(\d{1,4}))?", text)

    # Periodical references such as "w09 1. 3. 17 Abs. 2" mean:
    # issue 1 March 2009, article/paragraph target 17/2.  The issue must be
    # selected as a whole publication; article and paragraph are navigation
    # targets only and must never be used as download identifiers.
    issue_tag = None
    issue_match = re.search(
        rf"(?<![\w]){re.escape(full_symbol)}\s+(\d{{1,2}})\s*[./-]\s*(\d{{1,2}})",
        text,
        re.I,
    )
    if issue_match and year:
        day = int(issue_match.group(1))
        month = int(issue_match.group(2))
        issue_year = year
        try:
            issue_tag = int(date(issue_year, month, day).strftime("%Y%m%d"))
        except ValueError:
            issue_tag = None

    # WOL/JW references commonly abbreviate the page as the third number,
    # e.g. ``w09 1. 3. 17 Abs. 2`` = issue 1 March 2009, page 17,
    # paragraph 2. Keep this number only as a post-import navigation target.
    inferred_page = None
    if issue_match:
        tail = text[issue_match.end():]
        inferred_match = re.match(r"\s*[.]?\s*(\d{1,4})(?=\s|$)", tail)
        if inferred_match:
            inferred_page = int(inferred_match.group(1))

    return {
        "symbol": base_symbol,
        "full_symbol": full_symbol,
        "year": year,
        "issue_tag": issue_tag,
        "target_number": int(kind_match.group(1)) if kind_match else None,
        "target_end": int(kind_match.group(2)) if kind_match and kind_match.group(2) else None,
        "paragraph": int(paragraph_match.group(1)) if paragraph_match else None,
        "page": int(page_match.group(1)) if page_match else inferred_page,
        "label": value.strip(),
    }


def _publication_candidates(reference: dict[str, Any]) -> list[dict[str, Any]]:
    symbols = [reference["full_symbol"]]
    if reference["symbol"] not in symbols:
        symbols.append(reference["symbol"])
    placeholders = ",".join("?" for _ in symbols)
    sql = f"SELECT id,title,key_symbol,year,issue_tag,last_opened_at,installed_at FROM publications WHERE lower(key_symbol) IN ({placeholders})"
    args: list[Any] = list(symbols)
    if reference.get("year"):
        sql += " AND (year=? OR id LIKE ?)"
        args.extend([reference["year"], f"%-{reference['year']}-%"])
    if reference.get("issue_tag"):
        sql += " AND issue_tag=?"
        args.append(int(reference["issue_tag"]))
    sql += " ORDER BY CASE WHEN lower(key_symbol)=? THEN 0 ELSE 1 END, COALESCE(last_opened_at,installed_at) DESC"
    args.append(reference["full_symbol"])
    rows = DB.rows(sql, tuple(args))
    seen: set[tuple[str, int, int]] = set()
    output: list[dict[str, Any]] = []
    for row in rows:
        key = (str(row.get("key_symbol") or "").lower(), int(row.get("year") or 0), int(row.get("issue_tag") or 0))
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def _find_document(publication_id: str, reference: dict[str, Any]) -> dict[str, Any] | None:
    numbers = [reference.get("target_number"), reference.get("page")]
    numbers = [int(number) for number in numbers if number]
    columns = "d.title,d.toc_title,d.subtitle,d.content_html"
    base = """SELECT d.id,d.title,d.toc_title,d.subtitle,d.meps_document_id,d.source_document_id,
        p.id AS publication_id,p.title AS publication_title,p.key_symbol,p.language_index
        FROM documents d JOIN publications p ON p.id=d.publication_id WHERE p.id=?"""
    for number in numbers:
        patterns = [f"%{number}%", f"%>{number}<%", f"% {number} %"]
        rows = DB.rows(
            base + f" AND ({columns.split(',')[0]} LIKE ? OR {columns.split(',')[1]} LIKE ? OR {columns.split(',')[2]} LIKE ? OR {columns.split(',')[3]} LIKE ?) ORDER BY d.sort_order LIMIT 1",
            (publication_id, patterns[0], patterns[0], patterns[0], patterns[1]),
        )
        if rows:
            return rows[0]
    words = [word for word in re.findall(r"[\wÀ-ž]+", reference["label"]) if len(word) > 3 and not word.isdigit()]
    words = [word for word in words if normalize(word) not in STOP_WORDS]
    for word in words[:6]:
        rows = DB.rows(
            base + " AND (d.title LIKE ? OR d.toc_title LIKE ? OR d.subtitle LIKE ?) ORDER BY d.sort_order LIMIT 1",
            (publication_id, f"%{word}%", f"%{word}%", f"%{word}%"),
        )
        if rows:
            return rows[0]
    rows = DB.rows(base + " ORDER BY d.sort_order LIMIT 1", (publication_id,))
    return rows[0] if rows else None


def resolve_publication(reference: dict[str, Any], language_index: int) -> dict[str, Any]:
    result: dict[str, Any] = {
        "resolved": False,
        "kind": "publication",
        "reference": reference["label"],
        "publication_symbol": reference["full_symbol"],
    }
    for publication in _publication_candidates(reference):
        document = _find_document(str(publication["id"]), reference)
        if document:
            result.update({
                "resolved": True,
                "document": document,
                "block_identifier": str(reference.get("paragraph") or "") or None,
            })
            return result
    # Catalog symbols do not contain the year suffix. A reference such as
    # ``w09 1. 3. 17 Abs. 2`` must therefore search for key symbol ``w`` and
    # then select the physical issue dated 1 March 2009. Querying for ``w09``
    # returns no catalog rows and was the reason the download button vanished.
    try:
        catalog = catalog_publications(
            language_index=language_index,
            query=reference["symbol"],
            kind="",
            limit=500,
            offset=0,
            newest=True,
        )
    except Exception:
        catalog = []

    allowed_symbols = {reference["symbol"], reference["full_symbol"]}
    base_matches = [
        item for item in catalog
        if str(item.get("key_symbol") or "").lower() in allowed_symbols
        and (not reference.get("year") or int(item.get("year") or 0) == int(reference["year"]))
    ]

    wanted_issue = int(reference.get("issue_tag") or 0)
    if wanted_issue:
        exact = [item for item in base_matches if int(item.get("issue_tag") or 0) == wanted_issue]
        if not exact:
            # Defensive compatibility for catalogs that encode an issue day as
            # 00 or expose the date only in metadata fields. The month and year
            # must still match; unrelated annual Watchtower entries are never
            # offered as a substitute.
            wanted_text = str(wanted_issue)
            wanted_month = wanted_text[:6]
            exact = [
                item for item in base_matches
                if str(int(item.get("issue_tag") or 0)).zfill(8)[:6] == wanted_month
                and str(int(item.get("issue_tag") or 0)).zfill(8)[6:] in {wanted_text[6:], "00"}
            ]
        if not exact:
            day = wanted_issue % 100
            month = (wanted_issue // 100) % 100
            year = wanted_issue // 10000
            date_tokens = {
                f"{year:04d}-{month:02d}-{day:02d}",
                f"{day:02d}.{month:02d}.{year:04d}",
                f"{day}.{month}.{year}",
                f"{year:04d}{month:02d}{day:02d}",
            }
            exact = []
            for item in base_matches:
                haystack = normalize(" ".join(str(item.get(key) or "") for key in (
                    "title", "short_title", "generally_available_date", "last_modified",
                    "cataloged_on", "last_updated", "raw_json",
                )))
                if any(normalize(token) in haystack for token in date_tokens):
                    exact.append(item)
        base_matches = exact

    # Never show multiple rows for the same physical issue. The download is for
    # the complete periodical; article/page/paragraph are navigation targets
    # used only after import.
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int]] = set()
    for item in base_matches:
        key = (
            str(item.get("key_symbol") or "").lower(),
            int(item.get("year") or 0),
            int(item.get("issue_tag") or 0),
        )
        if key in seen:
            continue
        seen.add(key)
        candidate = dict(item)
        if wanted_issue:
            day = wanted_issue % 100
            month = (wanted_issue // 100) % 100
            year = wanted_issue // 10000
            candidate["title"] = f"Der Wachtturm – {day:02d}.{month:02d}.{year:04d}"
            candidate["short_title"] = candidate["title"]
            candidate["requested_article"] = reference.get("page") or reference.get("target_number")
            candidate["requested_paragraph"] = reference.get("paragraph")
        deduped.append(candidate)

    result["catalog"] = deduped[:1] if wanted_issue else deduped[:8]
    result["issue_tag"] = wanted_issue or None
    result["target_number"] = reference.get("page") or reference.get("target_number")
    result["paragraph"] = reference.get("paragraph")
    return result


def _direct_publication_targets(link: str) -> list[dict[str, Any]]:
    value = urllib.parse.unquote(str(link or "").strip())
    targets: list[dict[str, Any]] = []
    # Mehrere Ziele können in JWPUB-Links mit "$" kombiniert sein. Jeder
    # exakte MEPS-Dokumentverweis wird in Reihenfolge geprüft.
    pattern = re.compile(r"(?:jwpub://p/|\$)([^:/$?#]+):(\d+)(?:/(\d+)(?:-(\d+))?)?", re.I)
    for match in pattern.finditer(value):
        targets.append({
            "language_symbol": match.group(1),
            "meps_document_id": int(match.group(2)),
            "block_identifier": int(match.group(3)) if match.group(3) else None,
            "block_end_identifier": int(match.group(4)) if match.group(4) else None,
        })
    if targets:
        return targets
    parsed = urllib.parse.urlparse(value)
    params = urllib.parse.parse_qs(parsed.query)
    raw_docid = (params.get("docid") or params.get("docId") or [""])[0]
    if not str(raw_docid).isdigit():
        return []
    raw_block = (params.get("par") or params.get("paragraph") or params.get("chapter") or [""])[0]
    block_match = re.fullmatch(r"(\d+)(?:-(\d+))?", str(raw_block or "").strip())
    return [{
        "language_symbol": str((params.get("wtlocale") or params.get("locale") or [""])[0]),
        "meps_document_id": int(raw_docid),
        "block_identifier": int(block_match.group(1)) if block_match else None,
        "block_end_identifier": int(block_match.group(2)) if block_match and block_match.group(2) else None,
    }]


def _resolve_direct_document(link: str, label: str) -> dict[str, Any] | None:
    targets = _direct_publication_targets(link)
    if not targets:
        return None
    for target in targets:
        language_symbol = str(target.get("language_symbol") or "")
        meps_id = int(target["meps_document_id"])
        rows = DB.rows(
            """SELECT d.id,d.title,d.toc_title,d.subtitle,d.meps_document_id,d.source_document_id,
            p.id AS publication_id,p.title AS publication_title,p.key_symbol,p.language_index
            FROM documents d JOIN publications p ON p.id=d.publication_id
            WHERE (d.meps_document_id=? OR d.source_document_id=?)
            AND (?='' OR p.language_symbol=? OR p.language_symbol IS NULL)
            ORDER BY COALESCE(p.last_opened_at,p.installed_at) DESC LIMIT 1""",
            (meps_id, meps_id, language_symbol, language_symbol),
        )
        if rows:
            return {
                "resolved": True,
                "kind": "publication",
                "external": link,
                "label": label or link,
                "document": rows[0],
                "block_identifier": target.get("block_identifier"),
                "block_end_identifier": target.get("block_end_identifier"),
                "meps_document_id": meps_id,
            }
    first = targets[0]
    return {
        "resolved": False,
        "kind": "publication",
        "external": link,
        "label": label or link,
        "meps_document_id": int(first["meps_document_id"]),
        "block_identifier": first.get("block_identifier"),
        "block_end_identifier": first.get("block_end_identifier"),
        "candidates": targets,
    }

def _decoded_reference_values(*values: str) -> list[str]:
    output: list[str] = []
    for raw in values:
        value = html.unescape(str(raw or "")).strip()
        if not value:
            continue
        for _ in range(4):
            if value not in output:
                output.append(value)
            try:
                decoded = urllib.parse.unquote(value)
            except Exception:
                break
            if decoded == value:
                break
            value = html.unescape(decoded).strip()
    return output


def _canonical_jw_reference(value: str) -> str:
    text = html.unescape(str(value or "")).strip().replace("\\/", "/")
    for _ in range(3):
        try:
            decoded = urllib.parse.unquote(text)
        except Exception:
            break
        if decoded == text:
            break
        text = decoded
    text = text.strip().casefold()
    text = re.sub(r"^(?:jwpub|jwlibrary)://", "", text)
    return text.rstrip("/")


def _contextual_media_reference(label: str, link: str, publication_id: str = "", document_id: int | None = None) -> dict[str, Any]:
    publication_id = str(publication_id or "").strip()
    if not publication_id and document_id:
        rows = DB.rows("SELECT publication_id FROM documents WHERE id=?", (int(document_id),))
        if rows:
            publication_id = str(rows[0].get("publication_id") or "")
    if not publication_id:
        return {}
    raw_values = _decoded_reference_values(link, label)
    canonical_values = {_canonical_jw_reference(value) for value in raw_values if value}
    source_ids: set[int] = set()
    for value in raw_values:
        for match in re.finditer(r"(?:jwpub|jwlibrary)://(?:v|a|m|video|audio)/(?:[^:/?#]+:)?(\d+)(?:[/?#]|$)", value, re.I):
            source_ids.add(int(match.group(1)))
        for match in re.finditer(r"(?:hyperlink|link)(?:id)?[=:/](\d+)", value, re.I):
            source_ids.add(int(match.group(1)))
    try:
        rows = DB.rows(
            "SELECT source_hyperlink_id,link,major_type,key_symbol,track,meps_document_id,meps_language_index,issue_tag,specialty,edition "
            "FROM hyperlinks WHERE publication_id=?",
            (publication_id,),
        )
    except Exception:
        rows = []
    best: dict[str, Any] | None = None
    best_score = 0
    direct_key = extract_natural_key(*raw_values)
    for row in rows:
        row_link = str(row.get("link") or "").strip()
        row_canonical = _canonical_jw_reference(row_link)
        row_key = extract_natural_key(row_link)
        score = 0
        source_id = int(row.get("source_hyperlink_id") or 0)
        if source_id and source_id in source_ids:
            score += 300
        if row_canonical and row_canonical in canonical_values:
            score += 240
        if row_canonical and any(row_canonical in value or value in row_canonical for value in canonical_values if len(value) >= 5):
            score += 100
        if direct_key and row_key and direct_key.casefold() == row_key.casefold():
            score += 320
        if score > best_score:
            best_score = score
            best = dict(row)
    if not best:
        return {"publication_id": publication_id, "references": raw_values}
    row_link = str(best.get("link") or "").strip()
    references = [*raw_values]
    if row_link and row_link not in references:
        references.append(row_link)
    kind = extract_media_kind(*references)
    if not kind:
        joined = " ".join(references).lower()
        if re.search(r"(?:jwpub|jwlibrary)://(?:a|audio)/", joined):
            kind = "audio"
        elif re.search(r"(?:jwpub|jwlibrary)://(?:v|video|m)/", joined):
            kind = "video"
    key_symbol = str(best.get("key_symbol") or "").strip()
    track = best.get("track")
    try:
        track_number = int(track) if track is not None else None
    except (TypeError, ValueError):
        track_number = None
    if key_symbol and track_number is not None and track_number >= 0:
        scheme = "webpubaud" if kind == "audio" else "webpubvid"
        synthetic = f"{scheme}://?pub={urllib.parse.quote(key_symbol)}&track={track_number}"
        if synthetic not in references:
            references.append(synthetic)
        kind = kind or "video"
    return {
        "publication_id": publication_id,
        "references": references,
        "kind": kind,
        "hyperlink": best,
        "matched": True,
    }


def _official_media_page(natural_key: str, language_index: int) -> str:
    if not natural_key:
        return ""
    return "https://www.jw.org/open?" + urllib.parse.urlencode({
        "lank": natural_key,
        "wtlocale": language_symbol(language_index),
    })


def resolve_media(
    label: str,
    link: str,
    language_index: int = 2,
    publication_id: str = "",
    document_id: int | None = None,
) -> dict[str, Any] | None:
    context = _contextual_media_reference(label, link, publication_id=publication_id, document_id=document_id)
    references = list(context.get("references") or _decoded_reference_values(link, label))
    if label and label not in references:
        references.append(label)
    publication_reference = extract_publication_media_reference(*references)
    natural_key = extract_natural_key(*references)
    media_type = extract_media_kind(*references) or str(context.get("kind") or "")
    combined = normalize(" ".join(references))
    if not media_type:
        if any(token in combined for token in ("video", "whiteboard", ".mp4", ".m4v", ".webm")):
            media_type = "video"
        elif any(token in combined for token in ("audio", ".mp3", ".m4a", ".aac", "lied")):
            media_type = "audio"
    if not media_type:
        return None
    external = str(link or "").strip()
    if not re.match(r"^https?://", external, re.I) and natural_key:
        external = _official_media_page(natural_key, language_index)
    result: dict[str, Any] = {
        "resolved": False,
        "kind": media_type,
        "external": external or str(link or ""),
        "label": label or link,
        "natural_key": natural_key,
        "publication_context": str(context.get("publication_id") or publication_id or ""),
    }
    resolution_errors: list[str] = []
    local_publication_id = str(context.get("publication_id") or publication_id or "").strip()
    try:
        local_rows = list_media(media_type, publication_id=local_publication_id or None)
    except Exception:
        local_rows = []
    if local_rows and document_id:
        try:
            document_rows = DB.rows("SELECT source_document_id FROM documents WHERE id=?", (int(document_id),))
            source_document_id = int(document_rows[0].get("source_document_id") or 0) if document_rows else 0
        except Exception:
            source_document_id = 0
        if source_document_id:
            scoped = [row for row in local_rows if int(row.get("document_source_id") or 0) == source_document_id]
            if scoped:
                local_rows = scoped
    local_words = [word for word in re.findall(r"[\wÀ-ž]+", normalize(label)) if len(word) > 2 and word not in STOP_WORDS]
    def local_score(item: dict[str, Any]) -> int:
        haystack = normalize(f"{item.get('label','')} {item.get('caption','')} {item.get('file_path','')} {item.get('publication_title','')}")
        score_value = sum(4 if word in haystack else 0 for word in local_words)
        if natural_key and normalize(natural_key) in haystack:
            score_value += 100
        return score_value
    local_rows = sorted(local_rows, key=local_score, reverse=True)
    if local_rows and (len(local_rows) == 1 or not local_words or local_score(local_rows[0]) > 0):
        top = local_rows[0]
        url = top.get("url") or ""
        if url:
            result.update({"resolved": True, "resolution": "local-jwpub", "media": {
                "title": top.get("label") or label or media_type.title(),
                "url": url, "download_url": url, "image": top.get("preview") or "",
                "mime_type": top.get("mime_type") or "", "media_key": top.get("media_key") or "",
                "natural_key": natural_key or top.get("media_key") or "",
                "sources": [{"url": url, "download_url": url, "quality": "Lokal", "mime_type": top.get("mime_type") or "", "height": top.get("height") or 0}],
            }})
            return result
    if natural_key:
        try:
            item = mediator_media_item(language_symbol(language_index), natural_key)
            item = prepare_media_for_playback(item)
            if item.get("url"):
                result.update({
                    "resolved": True,
                    "media": item,
                    "natural_key": item.get("natural_key") or natural_key,
                    "external": _official_media_page(natural_key, language_index),
                    "resolution": "official-natural-key",
                })
                return result
        except Exception as error:
            resolution_errors.append(f"natural-key: {error.__class__.__name__}: {error}")
    if publication_reference:
        try:
            item = publication_media_item(
                language_symbol(language_index),
                str(publication_reference["publication"]),
                int(publication_reference["track"]),
                str(publication_reference["kind"]),
            )
            item = prepare_media_for_playback(item)
            if item.get("url"):
                item_key = str(item.get("natural_key") or "")
                result.update({
                    "resolved": True,
                    "media": item,
                    "natural_key": item_key or natural_key,
                    "external": _official_media_page(item_key, language_index) if item_key else result.get("external"),
                    "resolution": "official-publication-track",
                })
                return result
        except Exception as error:
            resolution_errors.append(f"publication-track: {error.__class__.__name__}: {error}")
    parsed = urllib.parse.urlparse(str(link or ""))
    suffix = parsed.path.lower().rsplit(".", 1)[-1] if "." in parsed.path else ""
    direct_suffixes = {"video": {"mp4", "m4v", "webm"}, "audio": {"mp3", "m4a", "aac", "ogg"}}
    if parsed.scheme in {"http", "https"} and suffix in direct_suffixes.get(media_type, set()):
        mime = {"mp4": "video/mp4", "m4v": "video/mp4", "webm": "video/webm", "mp3": "audio/mpeg", "m4a": "audio/mp4", "aac": "audio/aac", "ogg": "audio/ogg"}.get(suffix, "")
        item = prepare_media_for_playback({"title": label or Path(parsed.path).name or media_type.title(), "url": link, "image": "", "mime_type": mime, "natural_key": link, "sources": [{"url": link, "quality": "Original", "mime_type": mime}]})
        if item.get("url"):
            result.update({"resolved": True, "media": item, "resolution": "direct-url"})
        return result
    words = [word for word in re.findall(r"[\wÀ-ž]+", normalize(label)) if len(word) > 2 and word not in STOP_WORDS]
    try:
        rows = list_media(media_type, publication_id=str(context.get("publication_id") or publication_id or "") or None)
    except Exception:
        rows = []
    def score(item: dict[str, Any]) -> int:
        haystack = normalize(f"{item.get('label','')} {item.get('file_path','')} {item.get('publication_title','')}")
        return sum(3 if word in haystack else 0 for word in words)
    rows = sorted(rows, key=score, reverse=True)
    if rows and (not words or score(rows[0]) > 0):
        top = rows[0]
        url = top.get("url") or ""
        result.update({"resolved": bool(url), "resolution": "local-import", "media": {
            "title": top.get("label") or label or media_type.title(),
            "url": url, "download_url": url, "image": top.get("preview") or "",
            "mime_type": top.get("mime_type") or "", "media_key": top.get("media_key") or "",
            "natural_key": top.get("media_key") or "",
            "sources": [{"url": url, "download_url": url, "quality": "Lokal", "mime_type": top.get("mime_type") or ""}],
        }})
        return result
    if resolution_errors:
        result["resolution_error"] = "; ".join(resolution_errors)
    result["missing_message"] = "Die verknüpfte Mediendatei konnte weder in der JWPUB noch im offiziellen JW.ORG-Medienkatalog geladen werden."
    return result


def _song_number(value: str) -> int | None:
    text = normalize(value)
    patterns = (
        r"\b(?:lied|song|gesang)\s*(\d{1,3})\b",
        r"\bsjj(?:[-_a-z]*)?\s*(?:lied)?\s*(\d{1,3})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            number = int(match.group(1))
            if 1 <= number <= 300:
                return number
    return None


def _song_document_score(document: dict[str, Any], number: int) -> int:
    fields = [
        str(document.get("title") or ""),
        str(document.get("toc_title") or ""),
        str(document.get("subtitle") or ""),
        str(document.get("class_name") or ""),
        str(document.get("content_probe") or ""),
    ]
    normalized_fields = [normalize(value) for value in fields]
    exact = re.compile(rf"(?:^|\b)(?:lied|song|gesang)?\s*0*{number}(?:\b|[.:)])", re.I)
    score = 0
    for index, value in enumerate(normalized_fields):
        if not value:
            continue
        weight = 520 if index < 3 else 180
        if exact.search(value):
            score += weight
        if re.match(rf"^0*{number}(?:\b|[.:)])", value):
            score += 420 if index < 3 else 120
        if f"lied {number}" in value or f"song {number}" in value:
            score += 440
    if int(document.get("chapter_number") or 0) == number:
        score += 900
    if int(document.get("section_number") or 0) == number:
        score += 780
    sort_order = int(document.get("sort_order") or 0)
    if sort_order == number:
        score += 260
    return score


def _local_song_document(number: int, language_index: int) -> dict[str, Any] | None:
    rows = DB.rows(
        """SELECT d.id,d.title,d.toc_title,d.subtitle,d.class_name,d.chapter_number,d.section_number,d.sort_order,
        substr(COALESCE(d.content_text,''),1,600) AS content_probe,d.meps_document_id,d.source_document_id,
        p.id AS publication_id,p.title AS publication_title,p.key_symbol,p.language_index,p.year,p.issue_tag
        FROM documents d JOIN publications p ON p.id=d.publication_id
        WHERE p.language_index=? AND lower(p.key_symbol) IN ('sjj','sn')
        ORDER BY CASE WHEN lower(p.key_symbol)='sjj' THEN 0 ELSE 1 END,p.year DESC,p.issue_tag DESC,d.sort_order""",
        (language_index,),
    )
    if not rows:
        return None
    scored = sorted(
        ((_song_document_score(row, number), row) for row in rows),
        key=lambda pair: (pair[0], int(pair[1].get("year") or 0), -int(pair[1].get("sort_order") or 0)),
        reverse=True,
    )
    if scored and scored[0][0] >= 500:
        return scored[0][1]
    return None


def _songbook_catalog(language_index: int) -> list[dict[str, Any]]:
    try:
        catalog = catalog_publications(language_index=language_index, query="sjj", kind="", limit=500, offset=0, newest=True)
    except Exception:
        catalog = []
    exact = [item for item in catalog if normalize(item.get("key_symbol")) == "sjj"]
    exact.sort(
        key=lambda item: (
            1 if "singt voller freude" in normalize(f"{item.get('title','')} {item.get('short_title','')}") else 0,
            int(item.get("year") or 0),
            int(item.get("issue_tag") or 0),
            int(item.get("catalog_id") or 0),
        ),
        reverse=True,
    )
    return exact[:1]


def resolve_songbook_reference(label: str, link: str, language_index: int) -> dict[str, Any] | None:
    number = _song_number(f"{label} {link}")
    if number is None:
        return None
    direct = _resolve_direct_document(link, label)
    if direct and direct.get("resolved"):
        document = direct.get("document") or {}
        symbol = normalize(document.get("key_symbol"))
        publication_title = normalize(document.get("publication_title"))
        if symbol in {"sjj", "sn"} or "singt voller freude" in publication_title:
            direct.update({"reference": f"Lied {number}", "song_number": number})
            return direct
    document = _local_song_document(number, language_index)
    if document:
        return {
            "resolved": True,
            "kind": "publication",
            "document": document,
            "reference": f"Lied {number}",
            "song_number": number,
            "external": link,
        }
    return {
        "resolved": False,
        "kind": "publication",
        "reference": f"Lied {number}",
        "song_number": number,
        "publication_symbol": "sjj",
        "catalog": _songbook_catalog(language_index),
        "external": link,
        "missing_message": "Das aktuelle Liederbuch ist noch nicht lokal installiert.",
    }

def resolve_insight_reference(label: str, link: str, language_index: int) -> dict[str, Any] | None:
    text = normalize(f"{label} {link}")
    if not re.search(r"(?:^|\s)it(?:\s|$|[,;])", text):
        return None
    quoted = re.search(r'[„\"“]([^„\"“]{2,80})[„\"“]', str(label or ''))
    term = (quoted.group(1) if quoted else '').strip()
    if term:
        rows = DB.rows("""SELECT d.id,d.title,d.toc_title,d.subtitle,d.meps_document_id,d.source_document_id,
            p.id AS publication_id,p.title AS publication_title,p.key_symbol,p.language_index
            FROM documents d JOIN publications p ON p.id=d.publication_id
            WHERE p.language_index=? AND lower(p.key_symbol)='it'
            AND (d.title LIKE ? OR d.toc_title LIKE ? OR d.content_html LIKE ?)
            ORDER BY d.sort_order LIMIT 1""", (language_index, f"%{term}%", f"%{term}%", f"%{term}%"))
        if rows:
            return {"resolved": True, "kind": "publication", "document": rows[0], "reference": label, "external": link}
    catalog = [item for item in catalog_publications(language_index=language_index, limit=500) if normalize(item.get("key_symbol")) == "it"]
    return {"resolved": False, "kind": "publication", "reference": label, "publication_symbol": "it", "catalog": catalog[:4], "external": link}


def resolve_source(label: str, link: str, language_index: int = 2, publication_id: str = "", document_id: int | None = None) -> dict[str, Any] | None:
    label = urllib.parse.unquote(str(label or "")).strip()
    link = urllib.parse.unquote(str(link or "")).strip()
    direct = _resolve_direct_document(link, label)
    if direct and direct.get("resolved"):
        return _finalize_result(direct)
    song = resolve_songbook_reference(label, link, language_index)
    if song:
        return _finalize_result(song)
    insight = resolve_insight_reference(label, link, language_index)
    if insight:
        return _finalize_result(insight)
    bible_reference = parse_bible_reference(label or link)
    if bible_reference:
        return _finalize_result(resolve_bible(bible_reference, language_index))
    media = resolve_media(label, link, language_index, publication_id=publication_id, document_id=document_id)
    if media:
        return _finalize_result(media)
    publication_reference = parse_publication_reference(label or link)
    if publication_reference:
        return _finalize_result(resolve_publication(publication_reference, language_index))
    return _finalize_result(direct)

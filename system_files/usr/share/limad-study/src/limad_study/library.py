from __future__ import annotations
import re
import unicodedata
from datetime import datetime
from typing import Any

CATEGORY_DEFINITIONS = (
    ("bibles", "Bibeln", 10),
    ("books", "Bücher", 20),
    ("brochures", "Broschüren und Booklets", 30),
    ("watchtower", "Wachtturm", 40),
    ("awake", "Erwachet!", 50),
    ("meetings", "Zusammenkünfte", 60),
    ("series", "Artikelserien", 70),
    ("tracts", "Traktate und Einladungen", 80),
    ("reference", "Programme und Nachschlagewerke", 90),
    ("periodicals", "Weitere Zeitschriften", 100),
    ("other", "Weitere Publikationen", 110),
)
CATEGORY_INDEX = {key: (label, order) for key, label, order in CATEGORY_DEFINITIONS}
BIBLE_SYMBOLS = {"nwt", "nwtsty", "bi12", "rbi8", "rnwt", "int", "by"}
WATCHTOWER_SYMBOLS = {"w", "wp", "ws"}
AWAKE_SYMBOLS = {"g", "gwp"}
MEETING_SYMBOLS = {"mwb", "km"}


def _text(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return " ".join("".join(ch for ch in normalized if not unicodedata.combining(ch)).lower().split())


def _contains(haystack: str, *needles: str) -> bool:
    return any(needle in haystack for needle in needles)


def _symbol(value: Any) -> str:
    return re.sub(r"[^a-z0-9_-]", "", _text(value))


def _issue_label(issue_tag: Any) -> str:
    try:
        number = int(issue_tag or 0)
    except Exception:
        return ""
    if number <= 0:
        return ""
    text = str(number)
    if len(text) == 8:
        try:
            return datetime.strptime(text, "%Y%m%d").strftime("%d.%m.%Y")
        except ValueError:
            pass
    if len(text) == 6:
        try:
            return datetime.strptime(text, "%Y%m").strftime("%m/%Y")
        except ValueError:
            pass
    return text


def classify_publication(item: dict[str, Any]) -> dict[str, Any]:
    symbol = _symbol(item.get("key_symbol") or item.get("unique_symbol"))
    publication_type = _text(item.get("publication_type"))
    category = _text(item.get("category"))
    title = _text(" ".join(str(item.get(key) or "") for key in ("title", "short_title", "display_title")))
    combined = " ".join((publication_type, category, title))

    if symbol in BIBLE_SYMBOLS or _contains(combined, "bible", "bibelausgabe", "bibelubersetzung", "holy scriptures"):
        key = "bibles"
    elif symbol in WATCHTOWER_SYMBOLS or _contains(combined, "watchtower", "wachtturm"):
        key = "watchtower"
    elif symbol in AWAKE_SYMBOLS or _contains(combined, "awake", "erwachet"):
        key = "awake"
    elif symbol in MEETING_SYMBOLS or symbol.startswith("mwb") or _contains(combined, "meeting workbook", "zusammenkunftsarbeitsheft", "leben und dienst", "kingdom ministry", "konigreichsdienst"):
        key = "meetings"
    elif _contains(publication_type, "brochure", "booklet") or _contains(category, "brochure", "booklet", "broschure"):
        key = "brochures"
    elif _contains(publication_type, "tract", "invitation") or _contains(category, "tract", "invitation", "einladung", "traktat") or symbol.startswith(("t-", "t_", "inv")):
        key = "tracts"
    elif _contains(publication_type, "series") or _contains(category, "series", "artikelserie"):
        key = "series"
    elif _contains(publication_type, "periodical", "magazine", "journal") or _contains(category, "periodical", "magazine", "zeitschrift"):
        key = "periodicals"
    elif _contains(publication_type, "reference", "index", "guideline", "program") or _contains(category, "reference", "index", "guideline", "program", "richtlinie", "nachschlage"):
        key = "reference"
    elif _contains(publication_type, "book") or _contains(category, "book", "buch"):
        key = "books"
    else:
        key = "other"

    label, order = CATEGORY_INDEX[key]
    try:
        year = int(item.get("year") or 0)
    except Exception:
        year = 0
    year_label = str(year) if 1800 <= year <= 3000 else "Ohne Jahrgang"
    issue_label = _issue_label(item.get("issue_tag"))
    edition_parts = [part for part in (str(year) if year else "", issue_label) if part]
    language = str(item.get("language_vernacular") or item.get("language_name") or "")
    search = " ".join(
        part for part in (
            str(item.get("title") or ""),
            str(item.get("short_title") or ""),
            str(item.get("display_title") or ""),
            str(item.get("key_symbol") or ""),
            str(item.get("publication_type") or ""),
            str(item.get("category") or ""),
            label,
            year_label,
            issue_label,
            language,
        ) if part
    )
    return {
        "library_category": key,
        "library_category_label": label,
        "library_category_order": order,
        "library_year": year if year else 0,
        "library_year_label": year_label,
        "library_issue_label": issue_label,
        "library_edition_label": " · ".join(edition_parts),
        "library_search": _text(search),
    }


def enrich_library_items(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for row in rows:
        row.update(classify_publication(row))
    return rows

from __future__ import annotations
from typing import Any
from .database import DB, Database

CATEGORY_DEFINITIONS = {
    "latest": {"label": "Aktuelle Publikationen"},
    "books": {"label": "Bücher"},
    "brochures": {"label": "Broschüren und Booklets"},
    "tracts": {"label": "Traktate und Einladungen"},
    "series": {"label": "Artikelserien"},
    "watchtower-study": {"label": "Der Wachtturm – Studienausgabe"},
    "watchtower-public": {"label": "Der Wachtturm – Öffentlichkeitsausgabe"},
    "awake": {"label": "Erwachet!"},
    "meeting-workbooks": {"label": "Zusammenkunftsarbeitshefte"},
    "kingdom-ministry": {"label": "Königreichsdienst"},
    "programs": {"label": "Programme"},
    "index": {"label": "Index und Nachschlagewerke"},
    "guidelines": {"label": "Anweisungen und Richtlinien"},
}


def _language(database: Database, language_index: int) -> dict[str, Any]:
    rows = database.rows(
        "SELECT id,symbol,english_name,vernacular_name FROM languages WHERE id=? LIMIT 1",
        (int(language_index),),
    )
    if not rows:
        raise ValueError("Die ausgewählte Sprache wurde nicht gefunden.")
    row = rows[0]
    symbol = str(row.get("symbol") or "").strip()
    if not symbol:
        raise ValueError("Die ausgewählte Sprache besitzt kein Katalogsymbol.")
    return row


def _category_clause(category: str) -> tuple[str, list[Any]]:
    key = str(category or "latest").strip().lower()
    clauses: dict[str, tuple[str, list[Any]]] = {
        "latest": ("c.publication_type_id<>1", []),
        "books": ("c.publication_type_id=2", []),
        "brochures": ("c.publication_type_id=4", []),
        "tracts": ("c.publication_type_id=10 AND upper(c.key_symbol) LIKE 'T-%'", []),
        "series": ("(lower(c.key_symbol)='mrt' OR lower(c.key_symbol) LIKE 'ijw%')", []),
        "watchtower-study": ("lower(c.key_symbol)='w' AND c.publication_type_id=14", []),
        "watchtower-public": ("lower(c.key_symbol)='wp' AND c.publication_type_id=14", []),
        "awake": ("lower(c.key_symbol)='g' AND c.publication_type_id=13", []),
        "meeting-workbooks": ("lower(c.key_symbol)='mwb' AND c.publication_type_id=30", []),
        "kingdom-ministry": ("lower(c.key_symbol)='km'", []),
        "programs": ("(c.publication_type_id=31 OR upper(c.key_symbol) LIKE 'CO-PGM%' OR upper(c.key_symbol) LIKE 'CA-%PGM%')", []),
        "index": ("(lower(c.key_symbol) LIKE 'dx%' OR lower(c.key_symbol) LIKE 'it-%' OR lower(c.key_symbol)='it')", []),
        "guidelines": ("(c.publication_type_id=17 OR upper(c.key_symbol) LIKE 'S-%') AND lower(c.key_symbol) NOT LIKE 'dx%'", []),
    }
    return clauses.get(key, ("0=1", []))


def live_publications(
    language_index: int,
    category: str = "latest",
    query: str = "",
    limit: int = 300,
    offset: int = 0,
    database: Database = DB,
) -> dict[str, Any]:
    language = _language(database, language_index)
    language_symbol = str(language.get("symbol") or "").strip()
    category_key = str(category or "latest").strip().lower()
    category_sql, category_params = _category_clause(category_key)
    clauses = ["c.language_index=?", "upper(c.language_symbol)=upper(?)", f"({category_sql})"]
    params: list[Any] = [int(language_index), language_symbol, *category_params]
    if query.strip():
        needle = f"%{query.strip()}%"
        clauses.append("(c.title LIKE ? OR c.short_title LIKE ? OR c.key_symbol LIKE ? OR c.symbol LIKE ?)")
        params.extend([needle, needle, needle, needle])
    safe_limit = min(max(int(limit), 1), 1000)
    safe_offset = max(int(offset), 0)
    params.extend([safe_limit, safe_offset])
    rows = database.rows(
        f'''SELECT c.*,l.english_name AS language_name,l.vernacular_name AS language_vernacular,
        CASE WHEN p.id IS NULL THEN 0 ELSE 1 END AS installed,p.id AS installed_id,p.cover_path AS installed_cover,
        COALESCE(NULLIF(c.generally_available_date,''),NULLIF(c.last_updated,''),NULLIF(c.cataloged_on,'')) AS sort_date
        FROM catalog_publications c
        JOIN languages l ON l.id=c.language_index
        LEFT JOIN publications p ON p.key_symbol=c.key_symbol AND p.language_index=c.language_index AND p.year=c.year AND p.issue_tag=c.issue_tag
        WHERE {' AND '.join(clauses)}
        ORDER BY c.year DESC,c.issue_tag DESC,
        COALESCE(NULLIF(c.generally_available_date,''),NULLIF(c.last_updated,''),NULLIF(c.cataloged_on,'')) DESC,
        c.title COLLATE NOCASE ASC,c.catalog_id DESC LIMIT ? OFFSET ?''',
        tuple(params),
    )
    for row in rows:
        row["cover_url"] = f"/api/catalog/{row['catalog_id']}/cover" if row.get("image_fragment") else ""
        row["downloadable"] = bool(row.get("key_symbol") and row.get("language_symbol"))
    invalid = [row for row in rows if int(row.get("language_index") or -1) != int(language_index) or str(row.get("language_symbol") or "").upper() != language_symbol.upper()]
    if invalid:
        raise RuntimeError("Der Katalog hat Datensätze aus einer anderen Sprache geliefert.")
    return {
        "category": category_key,
        "category_label": CATEGORY_DEFINITIONS.get(category_key, {}).get("label", category_key),
        "language": {
            "id": int(language.get("id") or language_index),
            "symbol": language_symbol,
            "name": language.get("vernacular_name") or language.get("english_name") or language_symbol,
        },
        "items": rows,
        "count": len(rows),
        "live": True,
    }

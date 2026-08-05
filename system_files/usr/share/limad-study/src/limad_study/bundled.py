from __future__ import annotations

from pathlib import Path
from typing import Any

from .database import DB, Database
from .importers.jwpub import import_jwpub
from .resources import SEED_ROOT
from .utils import utc_now

BUNDLED_STUDY_GUIDE = SEED_ROOT / "rsg19_X.jwpub"


def _installed_guide(database: Database) -> dict[str, Any] | None:
    rows = database.rows(
        "SELECT id,title,db_path,source_path FROM publications "
        "WHERE language_index=2 AND (lower(key_symbol) LIKE 'rsg%' OR lower(title) LIKE '%studienleitfaden%') "
        "ORDER BY year DESC,installed_at DESC LIMIT 1"
    )
    if not rows:
        return None
    row = rows[0]
    db_path = Path(str(row.get("db_path") or ""))
    return row if db_path.is_file() else None


def ensure_bundled_publications(database: Database = DB, strict: bool = False) -> dict[str, Any]:
    installed = _installed_guide(database)
    if installed:
        return {"ok": True, "installed": False, "already_present": True, "publication_id": installed["id"], "title": installed.get("title") or "Studienleitfaden"}

    if not BUNDLED_STUDY_GUIDE.is_file():
        result = {"ok": False, "installed": False, "error": f"Mitgelieferter Studienleitfaden fehlt: {BUNDLED_STUDY_GUIDE}"}
        if strict:
            raise FileNotFoundError(result["error"])
        return result

    try:
        imported = import_jwpub(BUNDLED_STUDY_GUIDE, database=database)
        database.set_setting("bundled_study_guide_installed_at", utc_now())
        return {
            "ok": True,
            "installed": True,
            "already_present": False,
            "publication_id": imported.get("publication_id"),
            "title": imported.get("title") or "Studienleitfaden",
            "counts": imported.get("counts") or {},
        }
    except Exception as exc:
        database.set_setting("bundled_study_guide_error", f"{exc.__class__.__name__}: {exc}")
        if strict:
            raise
        return {"ok": False, "installed": False, "error": f"{exc.__class__.__name__}: {exc}"}

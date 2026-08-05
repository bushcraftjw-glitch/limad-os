from __future__ import annotations

import html
import mimetypes
import os
import re
import shutil
import sqlite3
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share")) / "limad-notes"
DB_FILE = DATA_DIR / "notes.db"
ATTACHMENTS_DIR = DATA_DIR / "attachments"

def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clean_title(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    return value[:180] or "Neue Notiz"


def plain_from_html(value: str) -> str:
    value = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", value or "")
    value = re.sub(r"(?i)<br\s*/?>", "\n", value)
    value = re.sub(r"(?i)</p>|</div>|</li>|</h[1-6]>", "\n", value)
    value = re.sub(r"<[^>]+>", "", value)
    return html.unescape(value).replace("\r", "").strip()


def plain_from_rtf(value: str) -> str:
    text = value or ""
    text = re.sub(r"\\par[d]?\b ?", "\n", text)
    text = re.sub(r"\\line\b ?", "\n", text)
    text = re.sub(r"\\tab\b ?", "\t", text)
    text = re.sub(r"\\'[0-9a-fA-F]{2}", lambda match: bytes.fromhex(match.group(0)[2:]).decode("cp1252", errors="replace"), text)
    text = re.sub(r"\\u(-?\d+)\??", lambda match: chr(int(match.group(1)) % 65536), text)
    text = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", text)
    text = text.replace("{", "").replace("}", "")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


class Store:
    def __init__(self, path: Path = DB_FILE):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            PRAGMA journal_mode=WAL;
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS folders(
              id TEXT PRIMARY KEY,name TEXT NOT NULL UNIQUE,sort_order INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL,updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS notes(
              id TEXT PRIMARY KEY,folder_id TEXT REFERENCES folders(id) ON DELETE SET NULL,
              title TEXT NOT NULL DEFAULT '',body TEXT NOT NULL DEFAULT '',pinned INTEGER NOT NULL DEFAULT 0,
              deleted_at TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_notes_folder ON notes(folder_id,deleted_at,pinned DESC,updated_at DESC);
            CREATE TABLE IF NOT EXISTS attachments(
              id TEXT PRIMARY KEY,note_id TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
              name TEXT NOT NULL,path TEXT NOT NULL,mime TEXT,created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            """
        )
        self.connection.execute(
            "INSERT OR IGNORE INTO folders(id,name,sort_order,created_at,updated_at) VALUES(?,?,?,?,?)",
            ("quick", "Schnellnotizen", 0, now(), now()),
        )
        self.connection.execute(
            "INSERT OR IGNORE INTO folders(id,name,sort_order,created_at,updated_at) VALUES(?,?,?,?,?)",
            ("notes", "Notizen", 10, now(), now()),
        )
        self.connection.commit()

    def folders(self) -> list[dict]:
        return [dict(row) for row in self.connection.execute(
            "SELECT f.*,COUNT(n.id) count FROM folders f LEFT JOIN notes n ON n.folder_id=f.id AND n.deleted_at IS NULL GROUP BY f.id ORDER BY f.sort_order,f.name COLLATE NOCASE"
        )]

    def folder(self, folder_id: str) -> dict | None:
        row = self.connection.execute("SELECT * FROM folders WHERE id=?", (folder_id,)).fetchone()
        return dict(row) if row else None

    def add_folder(self, name: str) -> dict:
        name = clean_title(name)
        folder_id = str(uuid.uuid4())
        order = int(self.connection.execute("SELECT COALESCE(MAX(sort_order),0)+10 FROM folders").fetchone()[0])
        stamp = now()
        self.connection.execute("INSERT INTO folders VALUES(?,?,?,?,?)", (folder_id, name, order, stamp, stamp))
        self.connection.commit()
        return self.folder(folder_id) or {}

    def delete_folder(self, folder_id: str) -> None:
        if folder_id in {"quick", "notes"}:
            return
        self.connection.execute("UPDATE notes SET folder_id='notes' WHERE folder_id=?", (folder_id,))
        self.connection.execute("DELETE FROM folders WHERE id=?", (folder_id,))
        self.connection.commit()

    def notes(self, folder_id: str = "all", query: str = "", deleted: bool = False) -> list[dict]:
        clauses = ["n.deleted_at IS NOT NULL" if deleted else "n.deleted_at IS NULL"]
        values: list[str] = []
        if folder_id not in {"all", "deleted"}:
            clauses.append("n.folder_id=?")
            values.append(folder_id)
        if query.strip():
            clauses.append("(n.title LIKE ? OR n.body LIKE ?)")
            token = f"%{query.strip()}%"
            values.extend([token, token])
        rows = self.connection.execute(
            f"SELECT n.*,f.name folder_name,(SELECT COUNT(*) FROM attachments a WHERE a.note_id=n.id) attachment_count FROM notes n LEFT JOIN folders f ON f.id=n.folder_id WHERE {' AND '.join(clauses)} ORDER BY n.pinned DESC,n.updated_at DESC",
            values,
        )
        return [dict(row) for row in rows]

    def note(self, note_id: str) -> dict | None:
        row = self.connection.execute(
            "SELECT n.*,f.name folder_name FROM notes n LEFT JOIN folders f ON f.id=n.folder_id WHERE n.id=?", (note_id,)
        ).fetchone()
        return dict(row) if row else None

    def create_note(self, folder_id: str = "notes", title: str = "Neue Notiz", body: str = "") -> dict:
        if not self.folder(folder_id):
            folder_id = "notes"
        note_id = str(uuid.uuid4())
        stamp = now()
        self.connection.execute(
            "INSERT INTO notes(id,folder_id,title,body,pinned,deleted_at,created_at,updated_at) VALUES(?,?,?,?,0,NULL,?,?)",
            (note_id, folder_id, clean_title(title), body, stamp, stamp),
        )
        self.connection.commit()
        return self.note(note_id) or {}

    def update_note(self, note_id: str, title: str, body: str, folder_id: str | None = None) -> None:
        title = clean_title(title or next((line for line in body.splitlines() if line.strip()), "Neue Notiz"))
        if folder_id and self.folder(folder_id):
            self.connection.execute("UPDATE notes SET title=?,body=?,folder_id=?,updated_at=? WHERE id=?", (title, body, folder_id, now(), note_id))
        else:
            self.connection.execute("UPDATE notes SET title=?,body=?,updated_at=? WHERE id=?", (title, body, now(), note_id))
        self.connection.commit()

    def pin(self, note_id: str, value: bool) -> None:
        self.connection.execute("UPDATE notes SET pinned=?,updated_at=? WHERE id=?", (1 if value else 0, now(), note_id))
        self.connection.commit()

    def trash(self, note_id: str) -> None:
        self.connection.execute("UPDATE notes SET deleted_at=?,updated_at=? WHERE id=?", (now(), now(), note_id))
        self.connection.commit()

    def restore(self, note_id: str) -> None:
        self.connection.execute("UPDATE notes SET deleted_at=NULL,updated_at=? WHERE id=?", (now(), note_id))
        self.connection.commit()

    def purge(self, note_id: str) -> None:
        attachment_rows = self.connection.execute("SELECT path FROM attachments WHERE note_id=?", (note_id,)).fetchall()
        self.connection.execute("DELETE FROM notes WHERE id=?", (note_id,))
        self.connection.commit()
        for row in attachment_rows:
            try:
                Path(row[0]).unlink(missing_ok=True)
            except OSError:
                pass
        shutil.rmtree(ATTACHMENTS_DIR / note_id, ignore_errors=True)

    def attachments(self, note_id: str) -> list[dict]:
        return [dict(row) for row in self.connection.execute("SELECT * FROM attachments WHERE note_id=? ORDER BY created_at", (note_id,))]

    def add_attachment(self, note_id: str, source: Path) -> dict:
        target_dir = ATTACHMENTS_DIR / note_id
        target_dir.mkdir(parents=True, exist_ok=True)
        attachment_id = str(uuid.uuid4())
        safe_name = re.sub(r"[^\w.() -]+", "_", source.name, flags=re.UNICODE).strip() or "Anhang"
        target = target_dir / f"{attachment_id[:8]}-{safe_name}"
        shutil.copy2(source, target)
        mime = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
        self.connection.execute("INSERT INTO attachments VALUES(?,?,?,?,?,?)", (attachment_id, note_id, source.name, str(target), mime, now()))
        self.connection.commit()
        return dict(self.connection.execute("SELECT * FROM attachments WHERE id=?", (attachment_id,)).fetchone())

    def remove_attachment(self, attachment_id: str) -> None:
        row = self.connection.execute("SELECT path FROM attachments WHERE id=?", (attachment_id,)).fetchone()
        self.connection.execute("DELETE FROM attachments WHERE id=?", (attachment_id,))
        self.connection.commit()
        if row:
            try:
                Path(row[0]).unlink(missing_ok=True)
            except OSError:
                pass

    def import_file(self, path: Path, folder_id: str = "notes") -> list[dict]:
        suffix = path.suffix.lower()
        if suffix == ".enex":
            tree = ET.parse(path)
            result = []
            for item in tree.findall(".//note"):
                title = item.findtext("title") or "Importierte Notiz"
                content = item.findtext("content") or ""
                result.append(self.create_note(folder_id, title, plain_from_html(content)))
            return result
        raw = path.read_text(encoding="utf-8", errors="replace")
        body = plain_from_rtf(raw) if suffix == ".rtf" else plain_from_html(raw) if suffix in {".html", ".htm"} else raw
        title = clean_title(next((line.lstrip("# ") for line in body.splitlines() if line.strip()), path.stem))
        return [self.create_note(folder_id, title, body)]


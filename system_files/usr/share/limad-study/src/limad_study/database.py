from __future__ import annotations
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from .config import PATHS
from .utils import utc_now
from datetime import date, datetime, timedelta

SCHEMA_VERSION = 12

def normalize_dated_value(value):
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.date().isoformat()
    except Exception:
        pass
    digits = text.lstrip("-")
    try:
        number = int(float(text))
    except Exception:
        return text
    if len(digits) == 8 and 19000101 <= number <= 29991231:
        try:
            return datetime.strptime(str(number), "%Y%m%d").date().isoformat()
        except Exception:
            pass
    if 0 <= number <= 200000:
        try:
            return (date(1970, 1, 1) + timedelta(days=number)).isoformat()
        except Exception:
            pass
    if 946684800 <= number <= 4102444800000:
        try:
            seconds = number / 1000 if number > 4102444800 else number
            return datetime.utcfromtimestamp(seconds).date().isoformat()
        except Exception:
            pass
    return text


SCHEMA = r'''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS languages(
 id INTEGER PRIMARY KEY,symbol TEXT NOT NULL UNIQUE,english_name TEXT NOT NULL,vernacular_name TEXT,
 iso2 TEXT,iso3 TEXT,ietf TEXT,is_sign INTEGER NOT NULL DEFAULT 0,script_id INTEGER,direction TEXT NOT NULL DEFAULT 'ltr',source TEXT NOT NULL DEFAULT 'seed'
);
CREATE TABLE IF NOT EXISTS publications(
 id TEXT PRIMARY KEY,key_symbol TEXT NOT NULL,unique_symbol TEXT,language_index INTEGER NOT NULL,language_symbol TEXT,
 title TEXT NOT NULL,short_title TEXT,display_title TEXT,year INTEGER NOT NULL DEFAULT 0,issue_tag INTEGER NOT NULL DEFAULT 0,
 publication_type TEXT,category TEXT,source TEXT NOT NULL,source_path TEXT,content_dir TEXT,db_path TEXT,
 cover_path TEXT,thumbnail_path TEXT,installed_at TEXT,last_opened_at TEXT,favorite INTEGER NOT NULL DEFAULT 0,
 catalog_id INTEGER,catalog_asset_id INTEGER,server_updated_at TEXT,status TEXT NOT NULL DEFAULT 'installed',metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_publications_language ON publications(language_index);
CREATE INDEX IF NOT EXISTS idx_publications_symbol ON publications(key_symbol,language_index,year,issue_tag);
CREATE TABLE IF NOT EXISTS documents(
 id INTEGER PRIMARY KEY AUTOINCREMENT,publication_id TEXT NOT NULL REFERENCES publications(id) ON DELETE CASCADE,
 source_document_id INTEGER NOT NULL,meps_document_id INTEGER,chapter_number INTEGER,section_number INTEGER,
 title TEXT,toc_title TEXT,subtitle TEXT,class_name TEXT,content_html TEXT NOT NULL,content_text TEXT NOT NULL,
 paragraph_count INTEGER NOT NULL DEFAULT 0,sort_order INTEGER NOT NULL DEFAULT 0,UNIQUE(publication_id,source_document_id)
);
CREATE INDEX IF NOT EXISTS idx_documents_publication ON documents(publication_id,sort_order);
CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(title,content_text,publication_id UNINDEXED,document_id UNINDEXED,tokenize='unicode61 remove_diacritics 2');
CREATE TABLE IF NOT EXISTS media(
 id INTEGER PRIMARY KEY AUTOINCREMENT,publication_id TEXT NOT NULL REFERENCES publications(id) ON DELETE CASCADE,
 source_media_id INTEGER,file_path TEXT,mime_type TEXT,width INTEGER,height INTEGER,label TEXT,caption TEXT,
 document_source_id INTEGER,begin_paragraph INTEGER,end_paragraph INTEGER,UNIQUE(publication_id,source_media_id,document_source_id)
);
CREATE TABLE IF NOT EXISTS questions(
 id INTEGER PRIMARY KEY AUTOINCREMENT,publication_id TEXT NOT NULL REFERENCES publications(id) ON DELETE CASCADE,
 source_question_id INTEGER,document_source_id INTEGER,question_index INTEGER,content_html TEXT,paragraph_ordinal INTEGER,target_paragraph INTEGER,
 UNIQUE(publication_id,source_question_id)
);
CREATE TABLE IF NOT EXISTS footnotes(
 id INTEGER PRIMARY KEY AUTOINCREMENT,publication_id TEXT NOT NULL REFERENCES publications(id) ON DELETE CASCADE,
 source_footnote_id INTEGER,document_source_id INTEGER,footnote_index INTEGER,type INTEGER,content_html TEXT,paragraph_ordinal INTEGER,
 UNIQUE(publication_id,source_footnote_id)
);
CREATE TABLE IF NOT EXISTS hyperlinks(
 id INTEGER PRIMARY KEY AUTOINCREMENT,publication_id TEXT NOT NULL REFERENCES publications(id) ON DELETE CASCADE,
 source_hyperlink_id INTEGER,link TEXT,major_type INTEGER,key_symbol TEXT,track INTEGER,meps_document_id INTEGER,meps_language_index INTEGER,
 issue_tag INTEGER,specialty TEXT,edition TEXT,UNIQUE(publication_id,source_hyperlink_id)
);
CREATE TABLE IF NOT EXISTS bible_citations(
 id INTEGER PRIMARY KEY AUTOINCREMENT,publication_id TEXT NOT NULL REFERENCES publications(id) ON DELETE CASCADE,
 source_citation_id INTEGER,document_source_id INTEGER,block_number INTEGER,element_number INTEGER,paragraph_ordinal INTEGER,hyperlink_source_id INTEGER,
 UNIQUE(publication_id,source_citation_id)
);
CREATE TABLE IF NOT EXISTS dated_texts(
 id INTEGER PRIMARY KEY AUTOINCREMENT,publication_id TEXT NOT NULL REFERENCES publications(id) ON DELETE CASCADE,
 source_dated_text_id INTEGER,document_source_id INTEGER,class INTEGER,start_date TEXT,end_date TEXT,caption TEXT,content_html TEXT,
 begin_paragraph INTEGER,end_paragraph INTEGER,UNIQUE(publication_id,source_dated_text_id)
);
CREATE TABLE IF NOT EXISTS local_notes(
 id TEXT PRIMARY KEY,document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,title TEXT,content TEXT NOT NULL,
 block_identifier INTEGER,start_token INTEGER,end_token INTEGER,linked_mark_id TEXT,selection_text TEXT,created_at TEXT NOT NULL,modified_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS local_marks(
 id TEXT PRIMARY KEY,document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,block_identifier INTEGER,start_token INTEGER,end_token INTEGER,
 color_index INTEGER NOT NULL DEFAULT 0,style_index INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS local_note_tags(note_id TEXT NOT NULL REFERENCES local_notes(id) ON DELETE CASCADE,tag_name TEXT NOT NULL,PRIMARY KEY(note_id,tag_name));
CREATE TABLE IF NOT EXISTS backup_imports(
 id TEXT PRIMARY KEY,filename TEXT NOT NULL,source_path TEXT,raw_dir TEXT,manifest_json TEXT NOT NULL DEFAULT '{}',imported_at TEXT NOT NULL,
 locations_count INTEGER NOT NULL DEFAULT 0,notes_count INTEGER NOT NULL DEFAULT 0,marks_count INTEGER NOT NULL DEFAULT 0,
 tags_count INTEGER NOT NULL DEFAULT 0,bookmarks_count INTEGER NOT NULL DEFAULT 0,input_fields_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS user_locations(
 backup_id TEXT NOT NULL,location_id INTEGER NOT NULL,book_number INTEGER,chapter_number INTEGER,document_id INTEGER,track INTEGER,
 issue_tag INTEGER,key_symbol TEXT,meps_language INTEGER,type INTEGER,title TEXT,specialty TEXT,edition TEXT,
 PRIMARY KEY(backup_id,location_id)
);
CREATE TABLE IF NOT EXISTS notes(
 backup_id TEXT NOT NULL,note_id INTEGER NOT NULL,guid TEXT,user_mark_id INTEGER,location_id INTEGER,title TEXT,content TEXT,
 last_modified TEXT,created TEXT,block_type INTEGER,block_identifier INTEGER,PRIMARY KEY(backup_id,note_id)
);
CREATE TABLE IF NOT EXISTS user_marks(
 backup_id TEXT NOT NULL,user_mark_id INTEGER NOT NULL,color_index INTEGER,location_id INTEGER,style_index INTEGER,guid TEXT,version INTEGER,
 PRIMARY KEY(backup_id,user_mark_id)
);
CREATE TABLE IF NOT EXISTS block_ranges(
 backup_id TEXT NOT NULL,block_range_id INTEGER NOT NULL,block_type INTEGER,identifier INTEGER,start_token INTEGER,end_token INTEGER,user_mark_id INTEGER,
 PRIMARY KEY(backup_id,block_range_id)
);
CREATE TABLE IF NOT EXISTS tags(backup_id TEXT NOT NULL,tag_id INTEGER NOT NULL,type INTEGER,name TEXT,PRIMARY KEY(backup_id,tag_id));
CREATE TABLE IF NOT EXISTS tag_map(
 backup_id TEXT NOT NULL,tag_map_id INTEGER NOT NULL,playlist_item_id INTEGER,location_id INTEGER,note_id INTEGER,tag_id INTEGER,position INTEGER,
 PRIMARY KEY(backup_id,tag_map_id)
);
CREATE TABLE IF NOT EXISTS bookmarks(
 backup_id TEXT NOT NULL,bookmark_id INTEGER NOT NULL,location_id INTEGER,publication_location_id INTEGER,slot INTEGER,title TEXT,snippet TEXT,
 block_type INTEGER,block_identifier INTEGER,PRIMARY KEY(backup_id,bookmark_id)
);
CREATE TABLE IF NOT EXISTS input_fields(backup_id TEXT NOT NULL,location_id INTEGER NOT NULL,text_tag TEXT NOT NULL,value TEXT,PRIMARY KEY(backup_id,location_id,text_tag));
CREATE TABLE IF NOT EXISTS playlist_items(
 backup_id TEXT NOT NULL,playlist_item_id INTEGER NOT NULL,label TEXT,start_trim_ticks INTEGER,end_trim_ticks INTEGER,accuracy INTEGER,end_action INTEGER,thumbnail_path TEXT,
 PRIMARY KEY(backup_id,playlist_item_id)
);
CREATE TABLE IF NOT EXISTS playlist_locations(
 backup_id TEXT NOT NULL,playlist_item_id INTEGER NOT NULL,location_id INTEGER NOT NULL,major_type INTEGER,base_duration_ticks INTEGER,
 PRIMARY KEY(backup_id,playlist_item_id,location_id)
);
CREATE TABLE IF NOT EXISTS playlist_markers(
 backup_id TEXT NOT NULL,marker_id INTEGER NOT NULL,playlist_item_id INTEGER,label TEXT,start_ticks INTEGER,duration_ticks INTEGER,transition_ticks INTEGER,
 PRIMARY KEY(backup_id,marker_id)
);
CREATE TABLE IF NOT EXISTS catalog_publications(
 catalog_id INTEGER PRIMARY KEY,key_symbol TEXT,symbol TEXT,language_index INTEGER,language_symbol TEXT,title TEXT,short_title TEXT,
 year INTEGER,issue_tag INTEGER,publication_type_id INTEGER,asset_id INTEGER,signature TEXT,size INTEGER,expanded_size INTEGER,
 mime_type TEXT,cataloged_on TEXT,last_updated TEXT,last_modified TEXT,generally_available_date TEXT,
 image_fragment TEXT,image_width INTEGER,image_height INTEGER,image_mime TEXT,download_url TEXT,raw_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_catalog_language ON catalog_publications(language_index,last_updated DESC);
CREATE INDEX IF NOT EXISTS idx_catalog_symbol ON catalog_publications(key_symbol,language_index);
CREATE TABLE IF NOT EXISTS catalog_state(key TEXT PRIMARY KEY,value TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS download_jobs(
 id TEXT PRIMARY KEY,catalog_id INTEGER,publication_key TEXT,title TEXT,url TEXT,target_path TEXT,expected_size INTEGER,received_size INTEGER NOT NULL DEFAULT 0,
 expected_hash TEXT,status TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,error TEXT
);
CREATE TABLE IF NOT EXISTS home_items(id TEXT PRIMARY KEY,kind TEXT NOT NULL,title TEXT NOT NULL,subtitle TEXT,icon TEXT,route TEXT,sort_order INTEGER NOT NULL DEFAULT 0,enabled INTEGER NOT NULL DEFAULT 1);

CREATE TABLE IF NOT EXISTS local_bookmarks(
 id TEXT PRIMARY KEY,document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,block_identifier INTEGER,
 title TEXT,snippet TEXT,slot INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_local_bookmarks_document ON local_bookmarks(document_id,slot);
CREATE TABLE IF NOT EXISTS reading_positions(
 document_id INTEGER PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,scroll_ratio REAL NOT NULL DEFAULT 0,
 block_identifier INTEGER,updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS local_tags(name TEXT PRIMARY KEY,created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS backup_resolution(
 backup_id TEXT NOT NULL,location_id INTEGER NOT NULL,publication_id TEXT,document_row_id INTEGER,status TEXT NOT NULL,
 reason TEXT,resolved_at TEXT NOT NULL,PRIMARY KEY(backup_id,location_id)
);
CREATE INDEX IF NOT EXISTS idx_backup_resolution_status ON backup_resolution(status,backup_id);
CREATE TABLE IF NOT EXISTS local_input_fields(
 document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,text_tag TEXT NOT NULL,value TEXT NOT NULL,updated_at TEXT NOT NULL,
 PRIMARY KEY(document_id,text_tag)
);

CREATE TABLE IF NOT EXISTS media_progress(
 media_key TEXT PRIMARY KEY,publication_id TEXT,file_path TEXT,position_seconds REAL NOT NULL DEFAULT 0,
 duration_seconds REAL NOT NULL DEFAULT 0,playback_rate REAL NOT NULL DEFAULT 1,updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS local_playlists(
 id TEXT PRIMARY KEY,title TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',thumbnail_path TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS local_playlist_items(
 id TEXT PRIMARY KEY,playlist_id TEXT NOT NULL REFERENCES local_playlists(id) ON DELETE CASCADE,position INTEGER NOT NULL,
 label TEXT NOT NULL,publication_id TEXT,file_path TEXT,media_url TEXT,mime_type TEXT,thumbnail_path TEXT,
 start_seconds REAL NOT NULL DEFAULT 0,end_seconds REAL,source_json TEXT NOT NULL DEFAULT '{}',created_at TEXT NOT NULL,
 UNIQUE(playlist_id,position)
);
CREATE INDEX IF NOT EXISTS idx_local_playlist_items_playlist ON local_playlist_items(playlist_id,position);
CREATE TABLE IF NOT EXISTS bible_preferences(
 language_index INTEGER PRIMARY KEY,publication_id TEXT,last_document_id INTEGER,updated_at TEXT NOT NULL
);


CREATE TABLE IF NOT EXISTS meeting_notes(
 id TEXT PRIMARY KEY,document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,title TEXT NOT NULL,
 content TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL,updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_meeting_notes_document ON meeting_notes(document_id,updated_at DESC);
CREATE TABLE IF NOT EXISTS sync_events(
 id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL,status TEXT NOT NULL,started_at TEXT NOT NULL,finished_at TEXT,
 detail_json TEXT NOT NULL DEFAULT '{}',error TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS mark_groups(
 id TEXT PRIMARY KEY,document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,color_index INTEGER NOT NULL DEFAULT 0,
 style_index INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mark_group_ranges(
 group_id TEXT NOT NULL REFERENCES mark_groups(id) ON DELETE CASCADE,position INTEGER NOT NULL,block_identifier INTEGER NOT NULL,
 start_token INTEGER,end_token INTEGER,PRIMARY KEY(group_id,position)
);
CREATE INDEX IF NOT EXISTS idx_mark_group_ranges_block ON mark_group_ranges(block_identifier);
CREATE TABLE IF NOT EXISTS imported_mark_overrides(
 backup_id TEXT NOT NULL,user_mark_id INTEGER NOT NULL,hidden INTEGER NOT NULL DEFAULT 0,color_index INTEGER,updated_at TEXT NOT NULL,
 PRIMARY KEY(backup_id,user_mark_id)
);
CREATE TABLE IF NOT EXISTS bible_view_state(
 language_index INTEGER PRIMARY KEY,primary_publication_id TEXT,compare_publication_id TEXT,book_number INTEGER,chapter_number INTEGER,
 split_enabled INTEGER NOT NULL DEFAULT 0,updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS backup_export_runs(
 id TEXT PRIMARY KEY,backup_id TEXT,target_name TEXT,created_at TEXT NOT NULL,manifest_hash TEXT,db_integrity TEXT,
 notes_exported INTEGER NOT NULL DEFAULT 0,marks_exported INTEGER NOT NULL DEFAULT 0,bookmarks_exported INTEGER NOT NULL DEFAULT 0,
 tags_exported INTEGER NOT NULL DEFAULT 0,input_fields_exported INTEGER NOT NULL DEFAULT 0,report_json TEXT NOT NULL DEFAULT '{}'
);

'''

class Database:
    def __init__(self, path: Path = PATHS.database):
        self.path = path
        self._local = threading.local()
        self.initialize()
    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        return con
    @contextmanager
    def transaction(self):
        con = self.connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = self.connect()
        try:
            con.executescript(SCHEMA)
            local_note_columns = {row[1] for row in con.execute("PRAGMA table_info(local_notes)").fetchall()}
            for column, declaration in (
                ("start_token", "INTEGER"),
                ("end_token", "INTEGER"),
                ("linked_mark_id", "TEXT"),
                ("selection_text", "TEXT"),
            ):
                if column not in local_note_columns:
                    con.execute(f"ALTER TABLE local_notes ADD COLUMN {column} {declaration}")
            rows = con.execute("SELECT id,start_date,end_date FROM dated_texts").fetchall()
            for row in rows:
                start = normalize_dated_value(row[1])
                end = normalize_dated_value(row[2])
                if start != str(row[1] or "") or end != str(row[2] or ""):
                    con.execute("UPDATE dated_texts SET start_date=?,end_date=? WHERE id=?", (start,end,row[0]))
            con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version',?)", (str(SCHEMA_VERSION),))
            con.commit()
        finally:
            con.close()
    def scalar(self, sql: str, params=()):
        con = self.connect()
        try:
            row = con.execute(sql, params).fetchone()
            return row[0] if row else None
        finally:
            con.close()
    def rows(self, sql: str, params=()) -> list[dict]:
        con = self.connect()
        try:
            return [dict(row) for row in con.execute(sql, params).fetchall()]
        finally:
            con.close()
    def execute(self, sql: str, params=()) -> None:
        with self.transaction() as con:
            con.execute(sql, params)
    def setting(self, key: str, default=None):
        value = self.scalar("SELECT value FROM settings WHERE key=?", (key,))
        return default if value is None else value
    def set_setting(self, key: str, value: str) -> None:
        with self.transaction() as con:
            con.execute("INSERT INTO settings(key,value,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at", (key, value, utc_now()))

DB = Database()

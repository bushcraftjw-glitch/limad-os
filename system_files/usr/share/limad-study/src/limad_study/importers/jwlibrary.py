from __future__ import annotations
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Any
from ..config import PATHS
from ..database import DB, Database
from ..utils import safe_extract, safe_zip_members, sha256_file, utc_now
from ..backup.reconcile import reconcile_backup

TABLES = ['Location','Note','UserMark','BlockRange','Tag','TagMap','Bookmark','InputField','PlaylistItem','PlaylistItemLocationMap','PlaylistItemMarker']


def _exists(con: sqlite3.Connection, table: str) -> bool:
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def inspect_jwlibrary(path: Path) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    with tempfile.TemporaryDirectory(prefix='limad-jwlibrary-inspect-') as tmp:
        root = Path(tmp)
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            if 'userData.db' not in names or 'manifest.json' not in names:
                raise ValueError('Ungültiges JW-Library-Backup.')
            safe_extract(archive, root, safe_zip_members(archive, max_files=10000, max_size=3_000_000_000))
        manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8-sig'))
        db_path = root / 'userData.db'
        actual_hash = hashlib.sha256(db_path.read_bytes()).hexdigest()
        expected_hash = str((manifest.get('userDataBackup') or {}).get('hash') or '').lower()
        hash_match = not expected_hash or expected_hash == actual_hash
        con = sqlite3.connect(db_path)
        try:
            integrity = con.execute('PRAGMA integrity_check').fetchone()[0]
            counts = {table: con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] if _exists(con, table) else 0 for table in TABLES}
            user_version = con.execute('PRAGMA user_version').fetchone()[0]
            last_modified = con.execute('SELECT LastModified FROM LastModified LIMIT 1').fetchone()[0] if _exists(con, 'LastModified') else None
        finally:
            con.close()
    return {
        'file': path.name,
        'size': path.stat().st_size,
        'sha256': sha256_file(path),
        'database_sha256': actual_hash,
        'manifest_hash_match': hash_match,
        'manifest': manifest,
        'counts': counts,
        'integrity': integrity,
        'user_version': user_version,
        'last_modified': last_modified,
    }


def import_jwlibrary(path: Path, database: Database = DB) -> dict[str, Any]:
    path = Path(path).resolve()
    audit = inspect_jwlibrary(path)
    existing = database.rows("SELECT id,filename FROM backup_imports WHERE id LIKE ? ORDER BY imported_at DESC LIMIT 1", (audit['sha256'][:16] + '-%',))
    if existing:
        resolution = reconcile_backup(existing[0]['id'], database)
        return {
            'backup_id': existing[0]['id'],
            'filename': existing[0]['filename'],
            'counts': audit['counts'],
            'integrity': audit['integrity'],
            'user_version': audit['user_version'],
            'last_modified': audit['last_modified'],
            'resolution': resolution,
            'duplicate': True,
        }
    backup_id = f"{audit['sha256'][:16]}-{uuid.uuid4().hex[:8]}"
    final_dir = PATHS.backups / backup_id
    PATHS.backups.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f'.{backup_id}-', dir=PATHS.backups) as tmp_name:
        staging = Path(tmp_name)
        with zipfile.ZipFile(path) as archive:
            safe_extract(archive, staging, safe_zip_members(archive, max_files=10000, max_size=3_000_000_000))
        shutil.copy2(path, staging / path.name)
        source = sqlite3.connect(staging / 'userData.db')
        source.row_factory = sqlite3.Row
        counts = audit['counts']
        try:
            with database.transaction() as con:
                con.execute(
                    '''INSERT INTO backup_imports(id,filename,source_path,raw_dir,manifest_json,imported_at,locations_count,notes_count,marks_count,tags_count,bookmarks_count,input_fields_count)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (backup_id, path.name, str(final_dir / path.name), str(final_dir), json.dumps(audit['manifest'], ensure_ascii=False), utc_now(), counts['Location'], counts['Note'], counts['UserMark'], counts['Tag'], counts['Bookmark'], counts['InputField']),
                )
                if _exists(source, 'Location'):
                    for row in source.execute('SELECT * FROM Location'):
                        con.execute('INSERT INTO user_locations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)', (backup_id, row['LocationId'], row['BookNumber'], row['ChapterNumber'], row['DocumentId'], row['Track'], row['IssueTagNumber'], row['KeySymbol'], row['MepsLanguage'], row['Type'], row['Title'], row['Specialty'], row['Edition']))
                if _exists(source, 'Note'):
                    for row in source.execute('SELECT * FROM Note'):
                        con.execute('INSERT INTO notes VALUES(?,?,?,?,?,?,?,?,?,?,?)', (backup_id, row['NoteId'], row['Guid'], row['UserMarkId'], row['LocationId'], row['Title'], row['Content'], row['LastModified'], row['Created'], row['BlockType'], row['BlockIdentifier']))
                if _exists(source, 'UserMark'):
                    for row in source.execute('SELECT * FROM UserMark'):
                        con.execute('INSERT INTO user_marks VALUES(?,?,?,?,?,?,?)', (backup_id, row['UserMarkId'], row['ColorIndex'], row['LocationId'], row['StyleIndex'], row['UserMarkGuid'], row['Version']))
                if _exists(source, 'BlockRange'):
                    for row in source.execute('SELECT * FROM BlockRange'):
                        con.execute('INSERT INTO block_ranges VALUES(?,?,?,?,?,?,?)', (backup_id, row['BlockRangeId'], row['BlockType'], row['Identifier'], row['StartToken'], row['EndToken'], row['UserMarkId']))
                if _exists(source, 'Tag'):
                    for row in source.execute('SELECT * FROM Tag'):
                        con.execute('INSERT INTO tags VALUES(?,?,?,?)', (backup_id, row['TagId'], row['Type'], row['Name']))
                if _exists(source, 'TagMap'):
                    for row in source.execute('SELECT * FROM TagMap'):
                        con.execute('INSERT INTO tag_map VALUES(?,?,?,?,?,?,?)', (backup_id, row['TagMapId'], row['PlaylistItemId'], row['LocationId'], row['NoteId'], row['TagId'], row['Position']))
                if _exists(source, 'Bookmark'):
                    for row in source.execute('SELECT * FROM Bookmark'):
                        con.execute('INSERT INTO bookmarks VALUES(?,?,?,?,?,?,?,?,?)', (backup_id, row['BookmarkId'], row['LocationId'], row['PublicationLocationId'], row['Slot'], row['Title'], row['Snippet'], row['BlockType'], row['BlockIdentifier']))
                if _exists(source, 'InputField'):
                    for row in source.execute('SELECT * FROM InputField'):
                        con.execute('INSERT INTO input_fields VALUES(?,?,?,?)', (backup_id, row['LocationId'], row['TextTag'], row['Value']))
                if _exists(source, 'PlaylistItem'):
                    for row in source.execute('SELECT * FROM PlaylistItem'):
                        con.execute('INSERT INTO playlist_items VALUES(?,?,?,?,?,?,?,?,?)', (backup_id, row['PlaylistItemId'], row['Label'], row['StartTrimOffsetTicks'], row['EndTrimOffsetTicks'], row['Accuracy'], row['EndAction'], row['ThumbnailFilePath']))
                if _exists(source, 'PlaylistItemLocationMap'):
                    for row in source.execute('SELECT * FROM PlaylistItemLocationMap'):
                        con.execute('INSERT INTO playlist_locations VALUES(?,?,?,?,?)', (backup_id, row['PlaylistItemId'], row['LocationId'], row['MajorMultimediaType'], row['BaseDurationTicks']))
                if _exists(source, 'PlaylistItemMarker'):
                    for row in source.execute('SELECT * FROM PlaylistItemMarker'):
                        con.execute('INSERT INTO playlist_markers VALUES(?,?,?,?,?,?,?)', (backup_id, row['PlaylistItemMarkerId'], row['PlaylistItemId'], row['Label'], row['StartTimeTicks'], row['DurationTicks'], row['EndTransitionDurationTicks']))
        finally:
            source.close()
        if final_dir.exists():
            shutil.rmtree(final_dir)
        os.replace(staging, final_dir)
    resolution = reconcile_backup(backup_id, database)
    return {
        'backup_id': backup_id,
        'filename': path.name,
        'counts': counts,
        'integrity': audit['integrity'],
        'user_version': audit['user_version'],
        'last_modified': audit['last_modified'],
        'resolution': resolution,
        'duplicate': False,
    }

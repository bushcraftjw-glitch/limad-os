from __future__ import annotations
import base64
import hashlib
import json
import platform
import re
import shutil
import sqlite3
import tempfile
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from ..database import DB, Database
from ..utils import utc_now
from ..study.userdata import canonical_input_field_tag, migrate_local_input_fields
from .schema_v16 import INDEX_SQL, MIGRATIONS, PLAYLIST_ACCURACY, TABLE_SQL, TRIGGER_SQL

_EMPTY_THUMBNAIL = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M/wHwAFAgI/2dZlWQAAAABJRU5ErkJggg==')


def _next(con: sqlite3.Connection, table: str, column: str) -> int:
    return int(con.execute(f'SELECT COALESCE(MAX("{column}"),0)+1 FROM "{table}"').fetchone()[0])


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _reserve_export_time(database: Database) -> datetime:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    with database.transaction() as con:
        row = con.execute("SELECT value FROM settings WHERE key='backup_last_export_utc'").fetchone()
        previous = _parse_utc(row[0]) if row else None
        if previous and now <= previous:
            now = previous + timedelta(seconds=1)
        value = now.isoformat().replace('+00:00', 'Z')
        con.execute(
            "INSERT INTO settings(key,value,updated_at) VALUES('backup_last_export_utc',?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",
            (value, utc_now()),
        )
    return now


def _device_name() -> str:
    raw = platform.node().strip() or 'LiMaD'
    cleaned = re.sub(r'[^A-Za-z0-9._-]+', '-', raw).strip('.-_')[:32] or 'LiMaD'
    return f'LiMaD-{cleaned}'


def _backup_filename(moment_utc: datetime) -> str:
    local = moment_utc.astimezone()
    token = uuid.uuid4().hex[:8]
    return f'UserdataBackup_{local:%Y-%m-%d_%H-%M-%S}_{_device_name()}_{token}.jwlibrary'


def _manifest_time(moment_utc: datetime) -> str:
    return moment_utc.astimezone().strftime('%Y-%m-%dT%H:%M:%S%z')


def _db_time(moment_utc: datetime) -> str:
    return moment_utc.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')




_PERIODICAL_KEY_BASES = {"w", "wp", "g", "mwb"}


def _canonical_key_symbol(value: str | None) -> str:
    raw = str(value or "").strip()
    match = re.fullmatch(r"([A-Za-z]+)(\d{2})", raw)
    if match and match.group(1).lower() in _PERIODICAL_KEY_BASES:
        return match.group(1).lower()
    return raw


def _stable_guid(namespace: str, item_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{namespace}:{item_id}")).upper()


def _jw_uuid4_guid(item_id: str, namespace: str) -> str:
    raw = str(item_id or '').strip()
    try:
        parsed = uuid.UUID(raw)
        if parsed.version == 4:
            return str(parsed).upper()
    except (ValueError, AttributeError, TypeError):
        pass
    digest = bytearray(hashlib.sha256(f"{namespace}:{raw}".encode('utf-8')).digest()[:16])
    digest[6] = (digest[6] & 0x0F) | 0x40
    digest[8] = (digest[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(digest))).upper()


def _canonicalize_existing_locations(con: sqlite3.Connection) -> int:
    changed = 0
    for row in con.execute("SELECT LocationId,KeySymbol FROM Location WHERE KeySymbol IS NOT NULL").fetchall():
        canonical = _canonical_key_symbol(row[1])
        if canonical != str(row[1] or ""):
            con.execute("UPDATE Location SET KeySymbol=? WHERE LocationId=?", (canonical, int(row[0])))
            changed += 1
    return changed


def _jw_created_time(value: str | None) -> str:
    parsed = _parse_utc(value)
    if parsed is None:
        parsed = datetime.now(timezone.utc).replace(microsecond=0)
    return parsed.astimezone(timezone.utc).replace(microsecond=0).strftime('%Y-%m-%dT%H:%M:%SZ')


def _jw_modified_time(value: str | None) -> str:
    parsed = _parse_utc(value)
    if parsed is None:
        parsed = datetime.now(timezone.utc).replace(microsecond=0)
    return parsed.astimezone().replace(microsecond=0).strftime('%Y-%m-%dT%H:%M:%S%z')


def _jw_note_time(value: str | None) -> str:
    return _jw_modified_time(value)


def _jw_last_modified(value: str | None) -> str:
    return _jw_modified_time(value)


def _content_block_type(item: dict) -> int:
    key = _canonical_key_symbol(item.get("key_symbol")).lower()
    if key.startswith("nwt") or key in {"bi12", "by"}:
        return 2
    return 1


def _resolved_location(database: Database, document_row_id: int | None) -> dict | None:
    if document_row_id is None:
        return None
    rows = database.rows(
        """SELECT l.* FROM backup_resolution r
           JOIN user_locations l ON l.backup_id=r.backup_id AND l.location_id=r.location_id
           LEFT JOIN backup_imports b ON b.id=r.backup_id
           WHERE r.document_row_id=? AND r.status='resolved_document'
           ORDER BY COALESCE(b.imported_at,'') DESC,l.location_id DESC LIMIT 1""",
        (int(document_row_id),),
    )
    return rows[0] if rows else None


def _new_template(root: Path, moment_utc: datetime) -> None:
    db_path = root / 'userData.db'
    con = sqlite3.connect(db_path)
    try:
        con.executescript(TABLE_SQL)
        con.execute('INSERT INTO LastModified(LastModified) VALUES(?)', (_db_time(moment_utc),))
        con.executemany('INSERT INTO PlaylistItemAccuracy(PlaylistItemAccuracyId,Description) VALUES(?,?)', PLAYLIST_ACCURACY)
        con.executemany('INSERT INTO grdb_migrations(identifier) VALUES(?)', ((item,) for item in MIGRATIONS))
        con.execute('INSERT INTO android_metadata(locale) VALUES(?)', ('de_DE',))
        con.executescript(INDEX_SQL)
        con.executescript(TRIGGER_SQL)
        con.execute('PRAGMA user_version=16')
        con.commit()
    finally:
        con.close()
    (root / 'default_thumbnail.png').write_bytes(_EMPTY_THUMBNAIL)
    manifest = {
        'version': 1,
        'name': '',
        'type': 0,
        'creationDate': _manifest_time(moment_utc),
        'userDataBackup': {
            'lastModifiedDate': _manifest_time(moment_utc),
            'deviceName': _device_name(),
            'schemaVersion': 16,
            'databaseName': 'userData.db',
            'hash': '',
        },
    }
    (root / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')


def _prepare_template(root: Path, backup: dict | None, moment_utc: datetime) -> str:
    if backup:
        source_dir = Path(backup['raw_dir'])
        if (source_dir / 'userData.db').is_file() and (source_dir / 'manifest.json').is_file():
            for item in source_dir.iterdir():
                if item.is_file() and item.suffix.lower() != '.jwlibrary':
                    shutil.copy2(item, root / item.name)
            if not (root / 'default_thumbnail.png').is_file():
                (root / 'default_thumbnail.png').write_bytes(_EMPTY_THUMBNAIL)
            return 'imported-jwlibrary'
    _new_template(root, moment_utc)
    return 'generated-schema-v16'


def _ensure_location(con: sqlite3.Connection, item: dict, counters: dict) -> int:
    document_id = int(item.get('meps_document_id') or item.get('source_document_id') or 0)
    key_symbol = _canonical_key_symbol(item.get('key_symbol'))
    language_index = item.get('language_index')
    issue_tag = int(item.get('issue_tag') or 0)
    book_number = item.get('book_number')
    chapter_number = item.get('chapter_number')
    if not document_id and book_number is None:
        raise ValueError('Für die externe Backup-Zuordnung fehlt eine offizielle Dokument- oder Bibelkennung.')
    if document_id:
        row = con.execute(
            '''SELECT LocationId FROM Location
               WHERE DocumentId=? AND IssueTagNumber=? AND COALESCE(KeySymbol,'')=COALESCE(?, '')
                 AND (MepsLanguage=? OR MepsLanguage IS NULL OR ? IS NULL)
               ORDER BY CASE WHEN MepsLanguage=? THEN 0 ELSE 1 END LIMIT 1''',
            (document_id, issue_tag, key_symbol, language_index, language_index, language_index),
        ).fetchone()
        if not row:
            row = con.execute(
                '''SELECT LocationId FROM Location WHERE DocumentId=? AND IssueTagNumber=?
                   AND (MepsLanguage=? OR MepsLanguage IS NULL OR ? IS NULL)
                   ORDER BY CASE WHEN MepsLanguage=? THEN 0 ELSE 1 END LIMIT 1''',
                (document_id, issue_tag, language_index, language_index, language_index),
            ).fetchone()
        if not row:
            row = con.execute('SELECT LocationId FROM Location WHERE DocumentId=? LIMIT 1', (document_id,)).fetchone()
    else:
        row = con.execute(
            '''SELECT LocationId FROM Location WHERE BookNumber=? AND ChapterNumber=?
               AND COALESCE(KeySymbol,'')=COALESCE(?,'')
               AND (MepsLanguage=? OR MepsLanguage IS NULL OR ? IS NULL) LIMIT 1''',
            (book_number, chapter_number, key_symbol, language_index, language_index),
        ).fetchone()
    if row:
        location_id = int(row[0])
        con.execute(
            '''UPDATE Location SET KeySymbol=COALESCE(NULLIF(?,''),KeySymbol),
               MepsLanguage=COALESCE(?,MepsLanguage),IssueTagNumber=CASE WHEN ?!=0 THEN ? ELSE IssueTagNumber END,
               BookNumber=COALESCE(?,BookNumber),ChapterNumber=COALESCE(?,ChapterNumber),
               Title=COALESCE(NULLIF(?,''),Title) WHERE LocationId=?''',
            (key_symbol, language_index, issue_tag, issue_tag, book_number, chapter_number, item.get('publication_title') or '', location_id),
        )
        return location_id
    location_id = counters['Location']
    counters['Location'] += 1
    con.execute(
        '''INSERT INTO Location(LocationId,BookNumber,ChapterNumber,DocumentId,Track,IssueTagNumber,KeySymbol,MepsLanguage,Type,Title,Specialty,Edition)
           VALUES(?,?,?,?,NULL,?,?,?,?,?,NULL,NULL)''',
        (location_id, book_number, chapter_number, document_id or None, issue_tag, key_symbol or None, language_index, 0, item.get('publication_title') or ''),
    )
    return location_id



def _ensure_input_field_location(con: sqlite3.Connection, item: dict, counters: dict) -> int:
    document_id = int(item.get('meps_document_id') or item.get('source_document_id') or 0)
    if not document_id:
        raise ValueError('Für das Antwortfeld fehlt die offizielle Dokumentkennung.')
    issue_tag = int(item.get('issue_tag') or 0)
    key_symbol = _canonical_key_symbol(item.get('key_symbol'))
    row = con.execute(
        '''SELECT LocationId FROM Location
           WHERE DocumentId=? AND IssueTagNumber=? AND COALESCE(KeySymbol,'')=COALESCE(?,'')
             AND MepsLanguage IS NULL AND Title IS NULL AND Type=0
             AND BookNumber IS NULL AND ChapterNumber IS NULL
           ORDER BY LocationId LIMIT 1''',
        (document_id, issue_tag, key_symbol),
    ).fetchone()
    if row:
        return int(row[0])
    location_id = counters['Location']
    counters['Location'] += 1
    con.execute(
        '''INSERT INTO Location(LocationId,BookNumber,ChapterNumber,DocumentId,Track,IssueTagNumber,KeySymbol,MepsLanguage,Type,Title,Specialty,Edition)
           VALUES(?,NULL,NULL,?,NULL,?,?,NULL,0,NULL,NULL,NULL)''',
        (location_id, document_id, issue_tag, key_symbol or None),
    )
    return location_id


def _canonicalize_output_input_fields(con: sqlite3.Connection, database: Database, counters: dict) -> int:
    rows = con.execute(
        '''SELECT i.LocationId,i.TextTag,i.Value,l.DocumentId,l.IssueTagNumber,l.KeySymbol,l.MepsLanguage,l.Title
           FROM InputField i JOIN Location l ON l.LocationId=i.LocationId
           ORDER BY CASE WHEN l.MepsLanguage IS NULL AND l.Title IS NULL THEN 0 ELSE 1 END,i.LocationId,i.TextTag'''
    ).fetchall()
    moved = 0
    for row in rows:
        document_id = int(row['DocumentId'] or 0)
        if not document_id:
            continue
        key_symbol = _canonical_key_symbol(row['KeySymbol'])
        documents = database.rows(
            '''SELECT d.id AS document_id,d.source_document_id,d.meps_document_id,p.key_symbol,p.issue_tag
               FROM documents d JOIN publications p ON p.id=d.publication_id
               WHERE (d.meps_document_id=? OR d.source_document_id=?)
                 AND p.issue_tag=?
               ORDER BY CASE WHEN lower(p.key_symbol)=lower(?) THEN 0 ELSE 1 END,d.id LIMIT 1''',
            (document_id, document_id, int(row['IssueTagNumber'] or 0), key_symbol),
        )
        if not documents:
            continue
        item = documents[0]
        canonical = canonical_input_field_tag(int(item['document_id']), str(row['TextTag'] or ''), database)
        if not canonical:
            continue
        target_location = _ensure_input_field_location(con, item, counters)
        already_canonical = target_location == int(row['LocationId']) and canonical == str(row['TextTag'])
        if already_canonical:
            continue
        con.execute(
            'INSERT INTO InputField(LocationId,TextTag,Value) VALUES(?,?,?) ON CONFLICT(LocationId,TextTag) DO UPDATE SET Value=excluded.Value',
            (target_location, canonical, str(row['Value'] or '')),
        )
        con.execute('DELETE FROM InputField WHERE LocationId=? AND TextTag=?', (int(row['LocationId']), str(row['TextTag'])))
        moved += 1
    return moved

def _ensure_imported_location(con: sqlite3.Connection, location: dict, counters: dict) -> int:
    normalized = dict(location)
    normalized['key_symbol'] = _canonical_key_symbol(normalized.get('key_symbol'))
    document_id = normalized.get('document_id')
    row = con.execute(
        '''SELECT LocationId FROM Location WHERE COALESCE(DocumentId,-1)=COALESCE(?,-1)
           AND COALESCE(BookNumber,-1)=COALESCE(?,-1) AND COALESCE(ChapterNumber,-1)=COALESCE(?,-1)
           AND COALESCE(IssueTagNumber,0)=COALESCE(?,0) AND COALESCE(KeySymbol,'')=COALESCE(?,'')
           AND COALESCE(MepsLanguage,-1)=COALESCE(?,-1) AND COALESCE(Type,0)=COALESCE(?,0)
           ORDER BY LocationId LIMIT 1''',
        (document_id, normalized.get('book_number'), normalized.get('chapter_number'), normalized.get('issue_tag'),
         normalized.get('key_symbol'), normalized.get('meps_language'), normalized.get('type')),
    ).fetchone()
    if not row:
        row = con.execute(
            '''SELECT LocationId FROM Location WHERE COALESCE(DocumentId,-1)=COALESCE(?,-1)
               AND COALESCE(BookNumber,-1)=COALESCE(?,-1) AND COALESCE(ChapterNumber,-1)=COALESCE(?,-1)
               AND COALESCE(IssueTagNumber,0)=COALESCE(?,0)
               AND COALESCE(MepsLanguage,-1)=COALESCE(?,-1) AND COALESCE(Type,0)=COALESCE(?,0)
               ORDER BY LocationId LIMIT 1''',
            (document_id, normalized.get('book_number'), normalized.get('chapter_number'), normalized.get('issue_tag'),
             normalized.get('meps_language'), normalized.get('type')),
        ).fetchone()
    if row:
        location_id = int(row[0])
        con.execute(
            '''UPDATE Location SET KeySymbol=COALESCE(NULLIF(?,''),KeySymbol),Title=COALESCE(NULLIF(?,''),Title),
               Specialty=COALESCE(?,Specialty),Edition=COALESCE(?,Edition) WHERE LocationId=?''',
            (normalized.get('key_symbol') or '', normalized.get('title') or '', normalized.get('specialty'), normalized.get('edition'), location_id),
        )
        return location_id
    location_id = counters['Location']
    counters['Location'] += 1
    con.execute(
        '''INSERT INTO Location(LocationId,BookNumber,ChapterNumber,DocumentId,Track,IssueTagNumber,KeySymbol,MepsLanguage,Type,Title,Specialty,Edition)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
        (location_id, normalized.get('book_number'), normalized.get('chapter_number'), document_id, normalized.get('track'),
         normalized.get('issue_tag'), normalized.get('key_symbol'), normalized.get('meps_language'), normalized.get('type'),
         normalized.get('title'), normalized.get('specialty'), normalized.get('edition')),
    )
    return location_id


def _ensure_item_location(con: sqlite3.Connection, database: Database, item: dict, counters: dict) -> int:
    exact = _resolved_location(database, item.get('document_id'))
    if exact:
        return _ensure_imported_location(con, exact, counters)
    return _ensure_location(con, item, counters)



def _merge_imported_userdata(con: sqlite3.Connection, database: Database, counters: dict, report: dict, skip_backup_id: str | None = None) -> None:
    location_cache: dict[tuple[str, int], int] = {}

    def location_for(row: dict) -> int | None:
        backup_id = str(row.get('backup_id') or '')
        source_location = row.get('source_location_id')
        if not backup_id or source_location is None:
            return None
        key = (backup_id, int(source_location))
        if key in location_cache:
            return location_cache[key]
        locations = database.rows(
            'SELECT * FROM user_locations WHERE backup_id=? AND location_id=?',
            (backup_id, int(source_location)),
        )
        if not locations:
            return None
        target_location = _ensure_imported_location(con, locations[0], counters)
        location_cache[key] = target_location
        return target_location

    skip_sql = ' WHERE n.backup_id<>?' if skip_backup_id else ''
    skip_params = (skip_backup_id,) if skip_backup_id else ()
    range_where = ' WHERE backup_id<>?' if skip_backup_id else ''
    range_map: dict[tuple[str, int], list[dict]] = {}
    for item in database.rows(f'SELECT * FROM block_ranges{range_where} ORDER BY backup_id,user_mark_id,block_range_id', skip_params):
        range_map.setdefault((str(item['backup_id']), int(item['user_mark_id'])), []).append(item)
    tag_map_by_note: dict[tuple[str, int], list[str]] = {}
    tag_where = ' WHERE tm.note_id IS NOT NULL AND tm.backup_id<>?' if skip_backup_id else ' WHERE tm.note_id IS NOT NULL'
    for item in database.rows(
        f'''SELECT tm.backup_id,tm.note_id,t.name FROM tag_map tm JOIN tags t ON t.backup_id=tm.backup_id AND t.tag_id=tm.tag_id
            {tag_where} ORDER BY tm.backup_id,tm.note_id,tm.position,t.name''', skip_params
    ):
        tag_map_by_note.setdefault((str(item['backup_id']), int(item['note_id'])), []).append(str(item.get('name') or ''))
    imported_notes = database.rows(
        f'''SELECT n.*,COALESCE(n.location_id,u.location_id) AS source_location_id
           FROM notes n LEFT JOIN user_marks u ON u.backup_id=n.backup_id AND u.user_mark_id=n.user_mark_id
           {skip_sql} ORDER BY n.backup_id,n.note_id''', skip_params
    )
    for note in imported_notes:
        location_id = location_for(note)
        if location_id is None:
            continue
        guid = str(note.get('guid') or uuid.uuid5(uuid.NAMESPACE_URL, f"limad-imported-note:{note['backup_id']}:{note['note_id']}")).upper()
        old = con.execute('SELECT NoteId FROM Note WHERE lower(Guid)=lower(?)', (guid,)).fetchone()
        block_identifier = note.get('block_identifier')
        if old:
            note_id = int(old[0])
            con.execute(
                '''UPDATE Note SET LocationId=?,Title=?,Content=?,LastModified=?,Created=?,BlockType=?,BlockIdentifier=? WHERE NoteId=?''',
                (location_id, note.get('title') or '', note.get('content') or '', note.get('last_modified'), note.get('created'), int(note.get('block_type') or 0), block_identifier, note_id),
            )
        else:
            note_id = counters['Note']
            counters['Note'] += 1
            con.execute(
                '''INSERT INTO Note(NoteId,Guid,UserMarkId,LocationId,Title,Content,LastModified,Created,BlockType,BlockIdentifier)
                   VALUES(?,?,NULL,?,?,?,?,?,?,?)''',
                (note_id, guid, location_id, note.get('title') or '', note.get('content') or '', note.get('last_modified'), note.get('created'), int(note.get('block_type') or 0), block_identifier),
            )
        report['imported_notes'] += 1
        for tag_name in tag_map_by_note.get((str(note['backup_id']), int(note['note_id'])), []):
            name = str(tag_name or '').strip()
            if not name:
                continue
            found = con.execute('SELECT TagId FROM Tag WHERE Name=? AND Type=1', (name,)).fetchone()
            if found:
                tag_id = int(found[0])
            else:
                tag_id = counters['Tag']
                counters['Tag'] += 1
                con.execute('INSERT INTO Tag(TagId,Type,Name) VALUES(?,1,?)', (tag_id, name))
            if not con.execute('SELECT 1 FROM TagMap WHERE NoteId=? AND TagId=?', (note_id, tag_id)).fetchone():
                tag_map_id = counters['TagMap']
                counters['TagMap'] += 1
                position = int(con.execute('SELECT COALESCE(MAX(Position),-1)+1 FROM TagMap WHERE TagId=?', (tag_id,)).fetchone()[0])
                con.execute('INSERT INTO TagMap(TagMapId,PlaylistItemId,LocationId,NoteId,TagId,Position) VALUES(?,NULL,NULL,?,?,?)', (tag_map_id, note_id, tag_id, position))

    mark_where = ' WHERE u.backup_id<>?' if skip_backup_id else ''
    imported_marks = database.rows(
        f'''SELECT u.*,u.location_id AS source_location_id,o.hidden,o.color_index AS override_color
           FROM user_marks u LEFT JOIN imported_mark_overrides o ON o.backup_id=u.backup_id AND o.user_mark_id=u.user_mark_id
           {mark_where} ORDER BY u.backup_id,u.user_mark_id''', skip_params
    )
    for mark in imported_marks:
        if int(mark.get('hidden') or 0):
            continue
        location_id = location_for(mark)
        if location_id is None:
            continue
        guid = str(mark.get('guid') or uuid.uuid5(uuid.NAMESPACE_URL, f"limad-imported-mark:{mark['backup_id']}:{mark['user_mark_id']}")).upper()
        color = mark.get('override_color') if mark.get('override_color') is not None else mark.get('color_index')
        old = con.execute('SELECT UserMarkId FROM UserMark WHERE lower(UserMarkGuid)=lower(?)', (guid,)).fetchone()
        if old:
            mark_id = int(old[0])
            con.execute('UPDATE UserMark SET ColorIndex=?,LocationId=?,StyleIndex=?,Version=? WHERE UserMarkId=?', (int(color or 0), location_id, int(mark.get('style_index') or 0), max(1, int(mark.get('version') or 1)), mark_id))
            con.execute('DELETE FROM BlockRange WHERE UserMarkId=?', (mark_id,))
        else:
            mark_id = counters['UserMark']
            counters['UserMark'] += 1
            con.execute('INSERT INTO UserMark(UserMarkId,ColorIndex,LocationId,StyleIndex,UserMarkGuid,Version) VALUES(?,?,?,?,?,?)', (mark_id, int(color or 0), location_id, int(mark.get('style_index') or 0), guid, max(1, int(mark.get('version') or 1))))
        for item in range_map.get((str(mark['backup_id']), int(mark['user_mark_id'])), []):
            block_range_id = counters['BlockRange']
            counters['BlockRange'] += 1
            con.execute(
                'INSERT INTO BlockRange(BlockRangeId,BlockType,Identifier,StartToken,EndToken,UserMarkId) VALUES(?,?,?,?,?,?)',
                (block_range_id, int(item.get('block_type') or 1), int(item.get('identifier') or 0), item.get('start_token'), item.get('end_token'), mark_id),
            )
        report['imported_marks'] += 1

    field_where = ' WHERE f.backup_id<>?' if skip_backup_id else ''
    imported_fields = database.rows(
        f'''SELECT f.*,f.location_id AS source_location_id FROM input_fields f
           {field_where} ORDER BY f.backup_id,f.location_id,f.text_tag''', skip_params
    )
    for field in imported_fields:
        location_id = location_for(field)
        if location_id is None:
            continue
        con.execute(
            'INSERT INTO InputField(LocationId,TextTag,Value) VALUES(?,?,?) ON CONFLICT(LocationId,TextTag) DO UPDATE SET Value=excluded.Value',
            (location_id, field.get('text_tag') or '', field.get('value') or ''),
        )
        report['imported_input_fields'] += 1

    bookmark_where = ' WHERE b.backup_id<>?' if skip_backup_id else ''
    imported_bookmarks = database.rows(
        f'''SELECT b.*,b.location_id AS source_location_id FROM bookmarks b
           {bookmark_where} ORDER BY b.backup_id,b.bookmark_id''', skip_params
    )
    for bookmark in imported_bookmarks:
        location_id = location_for(bookmark)
        if location_id is None:
            continue
        old = con.execute(
            "SELECT BookmarkId FROM Bookmark WHERE LocationId=? AND Slot=? AND COALESCE(Title,'')=COALESCE(?,'')",
            (location_id, int(bookmark.get('slot') or 0), bookmark.get('title') or ''),
        ).fetchone()
        if old:
            con.execute('UPDATE Bookmark SET Snippet=?,BlockType=?,BlockIdentifier=? WHERE BookmarkId=?', (bookmark.get('snippet') or '', int(bookmark.get('block_type') or 0), bookmark.get('block_identifier'), int(old[0])))
        else:
            bookmark_id = counters['Bookmark']
            counters['Bookmark'] += 1
            con.execute(
                'INSERT INTO Bookmark(BookmarkId,LocationId,PublicationLocationId,Slot,Title,Snippet,BlockType,BlockIdentifier) VALUES(?,?,?,?,?,?,?,?)',
                (bookmark_id, location_id, location_id, int(bookmark.get('slot') or 0), bookmark.get('title') or '', bookmark.get('snippet') or '', int(bookmark.get('block_type') or 0), bookmark.get('block_identifier')),
            )
        report['imported_bookmarks'] += 1

def _integrity(db_path: Path) -> str:
    con = sqlite3.connect(db_path)
    try:
        return str(con.execute('PRAGMA integrity_check').fetchone()[0])
    finally:
        con.close()


def export_jwlibrary(target: Path, backup_id: str | None = None, database: Database = DB) -> dict:
    migrated_input_fields = migrate_local_input_fields(database)
    rows = database.rows('SELECT * FROM backup_imports WHERE id=?', (backup_id,)) if backup_id else database.rows('SELECT * FROM backup_imports ORDER BY imported_at DESC LIMIT 1')
    backup = rows[0] if rows else None
    moment_utc = _reserve_export_time(database)
    target = Path(target)
    if target.suffix.lower() != '.jwlibrary':
        target.mkdir(parents=True, exist_ok=True)
        target = target / _backup_filename(moment_utc)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
    report = {
        'notes': 0,
        'marks': 0,
        'bookmarks': 0,
        'tags': 0,
        'input_fields': 0,
        'updated_notes': 0,
        'updated_marks': 0,
        'imported_notes': 0,
        'imported_marks': 0,
        'imported_bookmarks': 0,
        'imported_input_fields': 0,
        'mark_groups': 0,
        'source_local_notes': int(database.scalar('SELECT COUNT(*) FROM local_notes') or 0),
        'source_local_marks': int(database.scalar('SELECT COUNT(*) FROM local_marks') or 0),
        'source_mark_groups': int(database.scalar('SELECT COUNT(*) FROM mark_groups') or 0),
        'source_input_fields': int(database.scalar('SELECT COUNT(*) FROM local_input_fields') or 0),
        'external_compatibility': 'pending',
        'canonicalized_locations': 0,
        'migrated_input_fields': int(migrated_input_fields),
        'canonicalized_output_input_fields': 0,
    }
    with tempfile.TemporaryDirectory(prefix='limad-export-') as tmp:
        root = Path(tmp)
        template_source = _prepare_template(root, backup, moment_utc)
        db_path = root / 'userData.db'
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        try:
            counters = {table: _next(con, table, pk) for table, pk in (
                ('Location', 'LocationId'), ('Note', 'NoteId'), ('UserMark', 'UserMarkId'),
                ('BlockRange', 'BlockRangeId'), ('Bookmark', 'BookmarkId'), ('Tag', 'TagId'), ('TagMap', 'TagMapId'),
            )}
            report['canonicalized_locations'] = _canonicalize_existing_locations(con)
            _merge_imported_userdata(con, database, counters, report, backup['id'] if backup and template_source == 'imported-jwlibrary' else None)
            pending_local_note_links = []
            local_notes = database.rows(
                '''SELECT n.*,d.source_document_id,d.meps_document_id,d.chapter_number,p.key_symbol,p.language_index,p.issue_tag,p.title AS publication_title
                   FROM local_notes n LEFT JOIN documents d ON d.id=n.document_id LEFT JOIN publications p ON p.id=d.publication_id ORDER BY n.created_at'''
            )
            for note in local_notes:
                location_id = _ensure_item_location(con, database, note, counters)
                guid = _jw_uuid4_guid(note['id'], 'limad-study-note')
                old = con.execute('SELECT NoteId FROM Note WHERE lower(Guid)=lower(?)', (guid,)).fetchone()
                block_identifier = note.get('block_identifier')
                if old:
                    note_id = int(old[0])
                    con.execute(
                        '''UPDATE Note SET UserMarkId=NULL,LocationId=?,Title=?,Content=?,LastModified=?,Created=?,BlockType=?,BlockIdentifier=? WHERE NoteId=?''',
                        (location_id, note.get('title') or note.get('selection_text') or '', note.get('content') or '', _jw_modified_time(note.get('modified_at') or note.get('created_at')), _jw_created_time(note.get('created_at') or note.get('modified_at')), _content_block_type(note) if block_identifier is not None else 0, block_identifier, note_id),
                    )
                    report['updated_notes'] += 1
                else:
                    note_id = counters['Note']
                    counters['Note'] += 1
                    con.execute(
                        '''INSERT INTO Note(NoteId,Guid,UserMarkId,LocationId,Title,Content,LastModified,Created,BlockType,BlockIdentifier)
                           VALUES(?,?,NULL,?,?,?,?,?,?,?)''',
                        (note_id, guid, location_id, note.get('title') or note.get('selection_text') or '', note.get('content') or '', _jw_modified_time(note.get('modified_at') or note.get('created_at')), _jw_created_time(note.get('created_at') or note.get('modified_at')), _content_block_type(note) if block_identifier is not None else 0, block_identifier),
                    )
                report['notes'] += 1
                pending_local_note_links.append({'note_id': note_id, 'location_id': location_id, **note})
                for tag in database.rows('SELECT tag_name FROM local_note_tags WHERE note_id=? ORDER BY tag_name', (note['id'],)):
                    name = tag['tag_name']
                    row = con.execute('SELECT TagId FROM Tag WHERE Name=? AND Type=1', (name,)).fetchone()
                    if row:
                        tag_id = int(row[0])
                    else:
                        tag_id = counters['Tag']
                        counters['Tag'] += 1
                        con.execute('INSERT INTO Tag(TagId,Type,Name) VALUES(?,1,?)', (tag_id, name))
                        report['tags'] += 1
                    if not con.execute('SELECT 1 FROM TagMap WHERE NoteId=? AND TagId=?', (note_id, tag_id)).fetchone():
                        tag_map_id = counters['TagMap']
                        counters['TagMap'] += 1
                        position = int(con.execute('SELECT COALESCE(MAX(Position),-1)+1 FROM TagMap WHERE TagId=?', (tag_id,)).fetchone()[0])
                        con.execute('INSERT INTO TagMap(TagMapId,PlaylistItemId,LocationId,NoteId,TagId,Position) VALUES(?,NULL,NULL,?,?,?)', (tag_map_id, note_id, tag_id, position))
            local_marks = database.rows(
                '''SELECT m.*,d.source_document_id,d.meps_document_id,d.chapter_number,p.key_symbol,p.language_index,p.issue_tag,p.title AS publication_title
                   FROM local_marks m LEFT JOIN documents d ON d.id=m.document_id LEFT JOIN publications p ON p.id=d.publication_id ORDER BY m.created_at'''
            )
            for mark in local_marks:
                location_id = _ensure_item_location(con, database, mark, counters)
                guid = _jw_uuid4_guid(mark['id'], 'limad-study-mark')
                old = con.execute('SELECT UserMarkId FROM UserMark WHERE lower(UserMarkGuid)=lower(?)', (guid,)).fetchone()
                if old:
                    mark_id = int(old[0])
                    con.execute('UPDATE UserMark SET ColorIndex=?,LocationId=?,StyleIndex=?,Version=Version+1 WHERE UserMarkId=?', (int(mark.get('color_index') or 0), location_id, int(mark.get('style_index') or 0), mark_id))
                    con.execute('DELETE FROM BlockRange WHERE UserMarkId=?', (mark_id,))
                    report['updated_marks'] += 1
                else:
                    mark_id = counters['UserMark']
                    counters['UserMark'] += 1
                    con.execute('INSERT INTO UserMark(UserMarkId,ColorIndex,LocationId,StyleIndex,UserMarkGuid,Version) VALUES(?,?,?,?,?,1)', (mark_id, int(mark.get('color_index') or 0), location_id, int(mark.get('style_index') or 0), guid))
                block_range_id = counters['BlockRange']
                counters['BlockRange'] += 1
                con.execute(
                    'INSERT INTO BlockRange(BlockRangeId,BlockType,Identifier,StartToken,EndToken,UserMarkId) VALUES(?,?,?,?,?,?)',
                    (block_range_id, _content_block_type(mark), int(mark.get('block_identifier') or 0), mark.get('start_token'), mark.get('end_token'), mark_id),
                )
                report['marks'] += 1
            local_groups = database.rows(
                '''SELECT g.*,d.source_document_id,d.meps_document_id,d.chapter_number,p.key_symbol,p.language_index,p.issue_tag,p.title AS publication_title
                   FROM mark_groups g LEFT JOIN documents d ON d.id=g.document_id LEFT JOIN publications p ON p.id=d.publication_id ORDER BY g.created_at'''
            )
            for group in local_groups:
                location_id = _ensure_item_location(con, database, group, counters)
                guid = _jw_uuid4_guid(group['id'], 'limad-study-mark-group')
                old = con.execute('SELECT UserMarkId FROM UserMark WHERE lower(UserMarkGuid)=lower(?)', (guid,)).fetchone()
                if old:
                    mark_id = int(old[0])
                    con.execute('UPDATE UserMark SET ColorIndex=?,LocationId=?,StyleIndex=?,Version=Version+1 WHERE UserMarkId=?', (int(group.get('color_index') or 0), location_id, int(group.get('style_index') or 0), mark_id))
                    con.execute('DELETE FROM BlockRange WHERE UserMarkId=?', (mark_id,))
                else:
                    mark_id = counters['UserMark']
                    counters['UserMark'] += 1
                    con.execute('INSERT INTO UserMark(UserMarkId,ColorIndex,LocationId,StyleIndex,UserMarkGuid,Version) VALUES(?,?,?,?,?,1)', (mark_id, int(group.get('color_index') or 0), location_id, int(group.get('style_index') or 0), guid))
                for item in database.rows('SELECT * FROM mark_group_ranges WHERE group_id=? ORDER BY position', (group['id'],)):
                    block_range_id = counters['BlockRange']
                    counters['BlockRange'] += 1
                    con.execute('INSERT INTO BlockRange(BlockRangeId,BlockType,Identifier,StartToken,EndToken,UserMarkId) VALUES(?,?,?,?,?,?)', (block_range_id, _content_block_type(group), int(item.get('block_identifier') or 0), item.get('start_token'), item.get('end_token'), mark_id))
                report['mark_groups'] += 1
                report['marks'] += 1
            local_mark_rows = database.rows("SELECT id,document_id,block_identifier,start_token,end_token FROM local_marks")
            local_mark_map = {str(item['id']): item for item in local_mark_rows}
            marks_by_block = {}
            for item in local_mark_rows:
                marks_by_block.setdefault((int(item['document_id']), item.get('block_identifier')), []).append(item)
            for note in pending_local_note_links:
                candidates = []
                linked_id = str(note.get('linked_mark_id') or '').strip()
                if linked_id and linked_id in local_mark_map:
                    candidates = [local_mark_map[linked_id]]
                if not candidates:
                    candidates = list(marks_by_block.get((int(note['document_id']), note.get('block_identifier')), []))
                start = note.get('start_token')
                end = note.get('end_token')
                if start is not None and end is not None and candidates:
                    overlaps = [item for item in candidates if item.get('start_token') is not None and item.get('end_token') is not None and not (int(item['end_token']) < int(start) or int(item['start_token']) > int(end))]
                    if overlaps:
                        candidates = sorted(overlaps, key=lambda item: abs(int(item['start_token']) - int(start)) + abs(int(item['end_token']) - int(end)))
                selected_mark_id = None
                if len(candidates) == 1 or (start is not None and end is not None and candidates):
                    selected_mark_id = str(candidates[0]['id'])
                if selected_mark_id:
                    mark_guid = _jw_uuid4_guid(selected_mark_id, 'limad-study-mark')
                    row = con.execute('SELECT UserMarkId FROM UserMark WHERE lower(UserMarkGuid)=lower(?)', (mark_guid,)).fetchone()
                    if row:
                        con.execute('UPDATE Note SET UserMarkId=? WHERE NoteId=?', (int(row[0]), int(note['note_id'])))
                        report.setdefault('linked_notes', 0)
                        report['linked_notes'] += 1
                        continue
                if start is not None and end is not None and note.get('block_identifier') is not None:
                    anchor_guid = _jw_uuid4_guid(str(note['id']), 'limad-study-note-anchor')
                    row = con.execute('SELECT UserMarkId FROM UserMark WHERE lower(UserMarkGuid)=lower(?)', (anchor_guid,)).fetchone()
                    if row:
                        anchor_mark_id = int(row[0])
                        con.execute('UPDATE UserMark SET LocationId=?,ColorIndex=1,StyleIndex=0,Version=Version+1 WHERE UserMarkId=?', (int(note['location_id']), anchor_mark_id))
                        con.execute('DELETE FROM BlockRange WHERE UserMarkId=?', (anchor_mark_id,))
                    else:
                        anchor_mark_id = counters['UserMark']
                        counters['UserMark'] += 1
                        con.execute('INSERT INTO UserMark(UserMarkId,ColorIndex,LocationId,StyleIndex,UserMarkGuid,Version) VALUES(?,1,?,0,?,1)', (anchor_mark_id, int(note['location_id']), anchor_guid))
                    block_range_id = counters['BlockRange']
                    counters['BlockRange'] += 1
                    con.execute('INSERT INTO BlockRange(BlockRangeId,BlockType,Identifier,StartToken,EndToken,UserMarkId) VALUES(?,?,?,?,?,?)', (block_range_id, _content_block_type(note), int(note['block_identifier']), int(start), int(end), anchor_mark_id))
                    con.execute('UPDATE Note SET UserMarkId=? WHERE NoteId=?', (anchor_mark_id, int(note['note_id'])))
                    report.setdefault('linked_notes', 0)
                    report.setdefault('note_anchor_marks', 0)
                    report['linked_notes'] += 1
                    report['note_anchor_marks'] += 1

            local_bookmarks = database.rows(
                '''SELECT b.*,d.source_document_id,d.meps_document_id,d.chapter_number,p.key_symbol,p.language_index,p.issue_tag,p.title AS publication_title
                   FROM local_bookmarks b LEFT JOIN documents d ON d.id=b.document_id LEFT JOIN publications p ON p.id=d.publication_id ORDER BY b.slot,b.created_at'''
            )
            for bookmark in local_bookmarks:
                location_id = _ensure_item_location(con, database, bookmark, counters)
                stable_title = '[LiMaD] ' + (bookmark.get('title') or '')
                old = con.execute('SELECT BookmarkId FROM Bookmark WHERE LocationId=? AND Slot=? AND Title=?', (location_id, int(bookmark.get('slot') or 0), stable_title)).fetchone()
                if old:
                    con.execute('UPDATE Bookmark SET Snippet=?,BlockType=?,BlockIdentifier=? WHERE BookmarkId=?', (bookmark.get('snippet') or '', 1 if bookmark.get('block_identifier') is not None else 0, bookmark.get('block_identifier'), old[0]))
                else:
                    bookmark_id = counters['Bookmark']
                    counters['Bookmark'] += 1
                    con.execute(
                        'INSERT INTO Bookmark(BookmarkId,LocationId,PublicationLocationId,Slot,Title,Snippet,BlockType,BlockIdentifier) VALUES(?,?,?,?,?,?,?,?)',
                        (bookmark_id, location_id, location_id, int(bookmark.get('slot') or 0), stable_title, bookmark.get('snippet') or '', 1 if bookmark.get('block_identifier') is not None else 0, bookmark.get('block_identifier')),
                    )
                report['bookmarks'] += 1
            local_fields = database.rows(
                '''SELECT f.*,d.source_document_id,d.meps_document_id,d.chapter_number,p.key_symbol,p.language_index,p.issue_tag,p.title AS publication_title
                   FROM local_input_fields f LEFT JOIN documents d ON d.id=f.document_id LEFT JOIN publications p ON p.id=d.publication_id ORDER BY f.document_id,f.text_tag'''
            )
            for field in local_fields:
                canonical_tag = canonical_input_field_tag(int(field['document_id']), str(field['text_tag'] or ''), database)
                if re.fullmatch(r'textarea-\d+', canonical_tag, flags=re.IGNORECASE) or canonical_tag.startswith('answer:'):
                    raise ValueError(f"Antwortfeld {field['text_tag']} konnte keiner originalen JWPUB-Kennung zugeordnet werden.")
                location_id = _ensure_input_field_location(con, field, counters)
                if canonical_tag != str(field['text_tag']):
                    con.execute(
                        '''DELETE FROM InputField WHERE TextTag=? AND LocationId IN (
                           SELECT LocationId FROM Location WHERE DocumentId=? AND IssueTagNumber=? AND COALESCE(KeySymbol,'')=COALESCE(?,'')
                        )''',
                        (str(field['text_tag']), int(field.get('meps_document_id') or field.get('source_document_id') or 0), int(field.get('issue_tag') or 0), _canonical_key_symbol(field.get('key_symbol'))),
                    )
                con.execute(
                    'INSERT INTO InputField(LocationId,TextTag,Value) VALUES(?,?,?) ON CONFLICT(LocationId,TextTag) DO UPDATE SET Value=excluded.Value',
                    (location_id, canonical_tag, field['value']),
                )
                report['input_fields'] += 1
            report['canonicalized_output_input_fields'] = _canonicalize_output_input_fields(con, database, counters)
            broken_note_links = con.execute(
                '''SELECT COUNT(*) FROM Note n LEFT JOIN UserMark u ON u.UserMarkId=n.UserMarkId
                   LEFT JOIN BlockRange b ON b.UserMarkId=u.UserMarkId
                   WHERE n.UserMarkId IS NOT NULL AND (u.UserMarkId IS NULL OR b.UserMarkId IS NULL OR u.LocationId<>n.LocationId)'''
            ).fetchone()[0]
            if broken_note_links:
                raise ValueError(f'Externer Backup-Export enthält {broken_note_links} fehlerhafte Notiz-Markierungs-Verknüpfungen.')
            local_note_ids = [int(item['note_id']) for item in pending_local_note_links]
            invalid_note_times = 0
            if local_note_ids:
                placeholders = ','.join('?' for _ in local_note_ids)
                invalid_note_times = con.execute(
                    f"SELECT COUNT(*) FROM Note WHERE NoteId IN ({placeholders}) AND (LastModified NOT GLOB '????-??-??T??:??:??[+-]????' OR Created NOT GLOB '????-??-??T??:??:??Z')",
                    tuple(local_note_ids),
                ).fetchone()[0]
            if invalid_note_times:
                raise ValueError(f'Externer Backup-Export enthält {invalid_note_times} inkompatible lokale Notiz-Zeitstempel.')
            invalid_note_guids = 0
            invalid_note_model = 0
            for note_id in local_note_ids:
                row = con.execute(
                    '''SELECT n.Guid,n.UserMarkId,n.LocationId,n.BlockType,n.BlockIdentifier,
                              u.LocationId AS MarkLocationId,b.BlockType AS RangeBlockType,b.Identifier AS RangeIdentifier
                       FROM Note n LEFT JOIN UserMark u ON u.UserMarkId=n.UserMarkId
                       LEFT JOIN BlockRange b ON b.UserMarkId=n.UserMarkId
                       WHERE n.NoteId=? ORDER BY b.BlockRangeId LIMIT 1''',
                    (note_id,),
                ).fetchone()
                try:
                    if row is None or uuid.UUID(str(row['Guid'])).version != 4:
                        invalid_note_guids += 1
                except (ValueError, AttributeError, TypeError):
                    invalid_note_guids += 1
                if row is not None and row['UserMarkId'] is not None:
                    if row['MarkLocationId'] != row['LocationId'] or row['RangeBlockType'] != row['BlockType'] or row['RangeIdentifier'] != row['BlockIdentifier']:
                        invalid_note_model += 1
            if invalid_note_guids:
                raise ValueError(f'Externer Backup-Export enthält {invalid_note_guids} lokale Notizen ohne originale UUID4-Struktur.')
            if invalid_note_model:
                raise ValueError(f'Externer Backup-Export enthält {invalid_note_model} lokale Notizen mit abweichender JW-Library-Verknüpfungsstruktur.')
            noncanonical = con.execute(
                "SELECT COUNT(*) FROM Location WHERE lower(COALESCE(KeySymbol,'')) GLOB 'w[0-9][0-9]' OR lower(COALESCE(KeySymbol,'')) GLOB 'mwb[0-9][0-9]' OR lower(COALESCE(KeySymbol,'')) GLOB 'wp[0-9][0-9]' OR lower(COALESCE(KeySymbol,'')) GLOB 'g[0-9][0-9]'"
            ).fetchone()[0]
            if noncanonical:
                raise ValueError(f'Externer Backup-Export enthält {noncanonical} nicht kanonische Publikationskennungen.')
            missing = []
            for note in local_notes:
                guid = _jw_uuid4_guid(note['id'], 'limad-study-note')
                if not con.execute('SELECT 1 FROM Note WHERE lower(Guid)=lower(?)', (guid,)).fetchone():
                    missing.append(f"Notiz {note['id']}")
            for mark in local_marks:
                guid = _jw_uuid4_guid(mark['id'], 'limad-study-mark')
                if not con.execute('SELECT 1 FROM UserMark WHERE lower(UserMarkGuid)=lower(?)', (guid,)).fetchone():
                    missing.append(f"Markierung {mark['id']}")
            for group in local_groups:
                guid = _jw_uuid4_guid(group['id'], 'limad-study-mark-group')
                if not con.execute('SELECT 1 FROM UserMark WHERE lower(UserMarkGuid)=lower(?)', (guid,)).fetchone():
                    missing.append(f"Markierungsgruppe {group['id']}")
            if missing:
                raise ValueError('Backup wurde nicht erstellt, weil lokale Daten fehlen: ' + ', '.join(missing[:12]))
            if report['notes'] != report['source_local_notes']:
                raise ValueError(f"Notizprüfung fehlgeschlagen: {report['notes']} von {report['source_local_notes']} exportiert.")
            if report['marks'] != report['source_local_marks'] + report['source_mark_groups']:
                raise ValueError(f"Markierungsprüfung fehlgeschlagen: {report['marks']} von {report['source_local_marks'] + report['source_mark_groups']} exportiert.")
            if report['input_fields'] != report['source_input_fields']:
                raise ValueError(f"Antwortfeldprüfung fehlgeschlagen: {report['input_fields']} von {report['source_input_fields']} exportiert.")
            report['external_compatibility'] = 'validated-schema16-original-note-model-inputfield-texttag'
            con.execute('UPDATE LastModified SET LastModified=?', (_db_time(moment_utc),))
            con.commit()
        finally:
            con.close()
        integrity = _integrity(db_path)
        if integrity != 'ok':
            raise ValueError(f'Exportdatenbank ist beschädigt: {integrity}')
        manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8-sig'))
        digest = hashlib.sha256(db_path.read_bytes()).hexdigest()
        manifest['name'] = target.name
        manifest['creationDate'] = _manifest_time(moment_utc)
        user_backup = manifest.setdefault('userDataBackup', {})
        user_backup['lastModifiedDate'] = _manifest_time(moment_utc)
        user_backup['deviceName'] = _device_name()
        user_backup['schemaVersion'] = int(user_backup.get('schemaVersion') or 16)
        user_backup['databaseName'] = 'userData.db'
        user_backup['hash'] = digest
        (root / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        temp = target.with_suffix(target.suffix + '.tmp')
        with zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for item in sorted(root.iterdir()):
                if item.is_file():
                    archive.write(item, item.name)
        temp.replace(target)
    export_id = uuid.uuid4().hex
    full = {
        'path': str(target),
        'filename': target.name,
        'size': target.stat().st_size,
        'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
        'backup_id': backup['id'] if backup else None,
        'template_source': template_source,
        'integrity': integrity,
        'backup_last_modified_utc': _db_time(moment_utc),
        'manifest_creation_date': _manifest_time(moment_utc),
        **report,
    }
    database.execute(
        '''INSERT INTO backup_export_runs(id,backup_id,target_name,created_at,manifest_hash,db_integrity,notes_exported,marks_exported,bookmarks_exported,tags_exported,input_fields_exported,report_json)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
        (export_id, backup['id'] if backup else None, target.name, utc_now(), digest, integrity, report['notes'], report['marks'], report['bookmarks'], report['tags'], report['input_fields'], json.dumps(full, ensure_ascii=False)),
    )
    return full

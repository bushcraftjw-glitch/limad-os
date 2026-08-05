from __future__ import annotations
import uuid
import re
from html.parser import HTMLParser
from ..database import DB, Database
from ..utils import utc_now


def notes(database: Database = DB, query: str = '', limit: int = 500) -> list[dict]:
    needle = f"%{query.strip()}%"
    local = database.rows(
        '''SELECT n.id,'local' AS source,n.title,n.content,n.block_identifier,n.created_at AS created,n.modified_at AS modified,
                  d.id AS document_id,d.title AS document_title,p.title AS publication_title,
                  COALESCE((SELECT group_concat(tag_name, ' • ') FROM local_note_tags nt WHERE nt.note_id=n.id),'') AS tags
           FROM local_notes n JOIN documents d ON d.id=n.document_id JOIN publications p ON p.id=d.publication_id
           WHERE (?='' OR n.title LIKE ? OR n.content LIKE ?) ORDER BY n.modified_at DESC LIMIT ?''',
        (query.strip(), needle, needle, limit),
    )
    imported = database.rows(
        '''SELECT CAST(n.note_id AS TEXT)||':'||n.backup_id AS id,'backup' AS source,n.title,n.content,n.block_identifier,
                  n.created,n.last_modified AS modified,l.document_id AS source_document_id,r.document_row_id AS document_id,
                  l.key_symbol,l.meps_language,l.title AS location_title,COALESCE(d.title,'') AS document_title,
                  COALESCE(p.title,'') AS publication_title,
                  COALESCE((SELECT group_concat(t.name, ' • ') FROM tag_map tm JOIN tags t ON t.backup_id=tm.backup_id AND t.tag_id=tm.tag_id
                            WHERE tm.backup_id=n.backup_id AND tm.note_id=n.note_id),'') AS tags
           FROM notes n
           LEFT JOIN user_locations l ON l.backup_id=n.backup_id AND l.location_id=n.location_id
           LEFT JOIN backup_resolution r ON r.backup_id=n.backup_id AND r.location_id=n.location_id
           LEFT JOIN documents d ON d.id=r.document_row_id
           LEFT JOIN publications p ON p.id=r.publication_id
           WHERE (?='' OR n.title LIKE ? OR n.content LIKE ?) ORDER BY n.last_modified DESC LIMIT ?''',
        (query.strip(), needle, needle, limit),
    )
    return sorted(local + imported, key=lambda item: item.get('modified') or item.get('created') or '', reverse=True)[:limit]


def create_note(document_id: int, title: str, content: str, block_identifier: int | None = None, tags: list[str] | None = None, start_token: int | None = None, end_token: int | None = None, linked_mark_id: str | None = None, selection_text: str | None = None, database: Database = DB) -> dict:
    if not database.scalar('SELECT 1 FROM documents WHERE id=?', (int(document_id),)):
        raise ValueError('Dokument wurde nicht gefunden.')
    note_id = uuid.uuid4().hex
    now = utc_now()
    with database.transaction() as con:
        con.execute('INSERT INTO local_notes(id,document_id,title,content,block_identifier,start_token,end_token,linked_mark_id,selection_text,created_at,modified_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)', (note_id, int(document_id), title.strip(), content.strip(), block_identifier, start_token, end_token, (linked_mark_id or '').strip() or None, (selection_text or '').strip() or None, now, now))
        _set_tags(con, note_id, tags or [])
    return database.rows('SELECT * FROM local_notes WHERE id=?', (note_id,))[0]


def _set_tags(con, note_id: str, tags: list[str]):
    con.execute('DELETE FROM local_note_tags WHERE note_id=?', (note_id,))
    for raw in tags:
        name = str(raw).strip()
        if not name:
            continue
        con.execute('INSERT OR IGNORE INTO local_tags(name,created_at) VALUES(?,?)', (name, utc_now()))
        con.execute('INSERT OR IGNORE INTO local_note_tags(note_id,tag_name) VALUES(?,?)', (note_id, name))


def update_note(note_id: str, title: str, content: str, tags: list[str] | None = None, database: Database = DB) -> dict:
    with database.transaction() as con:
        con.execute('UPDATE local_notes SET title=?,content=?,modified_at=? WHERE id=?', (title.strip(), content.strip(), utc_now(), note_id))
        if tags is not None:
            _set_tags(con, note_id, tags)
    rows = database.rows('SELECT * FROM local_notes WHERE id=?', (note_id,))
    if not rows:
        raise ValueError('Notiz wurde nicht gefunden.')
    return rows[0]


def delete_note(note_id: str, database: Database = DB) -> None:
    database.execute('DELETE FROM local_notes WHERE id=?', (note_id,))


def add_mark(document_id: int, block_identifier: int | None, start_token: int | None, end_token: int | None, color_index: int = 0, style_index: int = 0, database: Database = DB) -> dict:
    mark_id = uuid.uuid4().hex
    database.execute('INSERT INTO local_marks(id,document_id,block_identifier,start_token,end_token,color_index,style_index,created_at) VALUES(?,?,?,?,?,?,?,?)', (mark_id, int(document_id), block_identifier, start_token, end_token, int(color_index), int(style_index), utc_now()))
    return database.rows('SELECT * FROM local_marks WHERE id=?', (mark_id,))[0]


def delete_mark(mark_id: str, database: Database = DB) -> None:
    database.execute('DELETE FROM local_marks WHERE id=?', (mark_id,))


def document_marks(document_id: int, database: Database = DB) -> list[dict]:
    local = database.rows("SELECT id,'local' AS source,block_identifier,start_token,end_token,color_index,style_index,created_at FROM local_marks WHERE document_id=? ORDER BY created_at", (int(document_id),))
    imported = database.rows(
        '''SELECT CAST(u.user_mark_id AS TEXT)||':'||u.backup_id AS id,'backup' AS source,br.identifier AS block_identifier,
                  br.start_token,br.end_token,COALESCE(o.color_index,u.color_index) AS color_index,u.style_index,b.imported_at AS created_at
           FROM user_marks u
           JOIN block_ranges br ON br.backup_id=u.backup_id AND br.user_mark_id=u.user_mark_id
           JOIN backup_resolution r ON r.backup_id=u.backup_id AND r.location_id=u.location_id
           JOIN backup_imports b ON b.id=u.backup_id
           LEFT JOIN imported_mark_overrides o ON o.backup_id=u.backup_id AND o.user_mark_id=u.user_mark_id
           WHERE r.document_row_id=? AND COALESCE(o.hidden,0)=0
           ORDER BY b.imported_at,br.block_range_id''',
        (int(document_id),),
    )
    return imported + local


def create_bookmark(document_id: int, title: str = '', snippet: str = '', block_identifier: int | None = None, slot: int = 0, database: Database = DB) -> dict:
    if not database.scalar('SELECT 1 FROM documents WHERE id=?', (int(document_id),)):
        raise ValueError('Dokument wurde nicht gefunden.')
    bookmark_id = uuid.uuid4().hex
    now = utc_now()
    database.execute('INSERT INTO local_bookmarks(id,document_id,block_identifier,title,snippet,slot,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)', (bookmark_id, int(document_id), block_identifier, title.strip(), snippet.strip(), int(slot), now, now))
    return database.rows('SELECT * FROM local_bookmarks WHERE id=?', (bookmark_id,))[0]


def delete_bookmark(bookmark_id: str, database: Database = DB) -> None:
    database.execute('DELETE FROM local_bookmarks WHERE id=?', (bookmark_id,))


def bookmarks(database: Database = DB) -> list[dict]:
    local = database.rows(
        '''SELECT b.id,'local' AS source,b.title,b.snippet,b.slot,b.block_identifier,d.id AS document_id,d.title AS location_title,
                  p.key_symbol,p.language_index AS meps_language,p.title AS publication_title
           FROM local_bookmarks b JOIN documents d ON d.id=b.document_id JOIN publications p ON p.id=d.publication_id ORDER BY b.updated_at DESC'''
    )
    imported = database.rows(
        '''SELECT CAST(b.bookmark_id AS TEXT)||':'||b.backup_id AS id,'backup' AS source,b.*,r.document_row_id AS document_id,
                  l.key_symbol,l.meps_language,COALESCE(d.title,l.title,'') AS location_title,COALESCE(p.title,'') AS publication_title
           FROM bookmarks b
           LEFT JOIN user_locations l ON l.backup_id=b.backup_id AND l.location_id=b.location_id
           LEFT JOIN backup_resolution r ON r.backup_id=b.backup_id AND r.location_id=b.location_id
           LEFT JOIN documents d ON d.id=r.document_row_id
           LEFT JOIN publications p ON p.id=r.publication_id
           ORDER BY b.slot,b.title LIMIT 1000'''
    )
    return local + imported


def save_position(document_id: int, scroll_ratio: float, block_identifier: int | None = None, database: Database = DB) -> dict:
    ratio = max(0.0, min(1.0, float(scroll_ratio)))
    database.execute('INSERT INTO reading_positions(document_id,scroll_ratio,block_identifier,updated_at) VALUES(?,?,?,?) ON CONFLICT(document_id) DO UPDATE SET scroll_ratio=excluded.scroll_ratio,block_identifier=excluded.block_identifier,updated_at=excluded.updated_at', (int(document_id), ratio, block_identifier, utc_now()))
    return {'document_id': int(document_id), 'scroll_ratio': ratio, 'block_identifier': block_identifier}


def reading_position(document_id: int, database: Database = DB) -> dict:
    rows = database.rows('SELECT * FROM reading_positions WHERE document_id=?', (int(document_id),))
    return rows[0] if rows else {'document_id': int(document_id), 'scroll_ratio': 0, 'block_identifier': None}


def tags(database: Database = DB) -> list[dict]:
    imported = database.rows("SELECT t.name,t.type,COUNT(tm.tag_map_id) AS usage,'backup' AS source FROM tags t LEFT JOIN tag_map tm ON tm.backup_id=t.backup_id AND tm.tag_id=t.tag_id GROUP BY t.backup_id,t.tag_id")
    local = database.rows("SELECT lt.name,0 AS type,COUNT(lnt.note_id) AS usage,'local' AS source FROM local_tags lt LEFT JOIN local_note_tags lnt ON lnt.tag_name=lt.name GROUP BY lt.name")
    return sorted(imported + local, key=lambda item: (item.get('name') or '').lower())


def add_mark_group(document_id: int, ranges: list[dict], color_index: int = 0, style_index: int = 0, database: Database = DB) -> dict:
    if not ranges:
        raise ValueError('Mindestens ein Markierungsbereich ist erforderlich.')
    group_id = uuid.uuid4().hex
    now = utc_now()
    with database.transaction() as con:
        con.execute('INSERT INTO mark_groups(id,document_id,color_index,style_index,created_at,updated_at) VALUES(?,?,?,?,?,?)', (group_id, int(document_id), int(color_index), int(style_index), now, now))
        for position, item in enumerate(ranges):
            con.execute('INSERT INTO mark_group_ranges(group_id,position,block_identifier,start_token,end_token) VALUES(?,?,?,?,?)', (group_id, position, int(item['block_identifier']), item.get('start_token'), item.get('end_token')))
    return {'id': group_id, 'document_id': int(document_id), 'color_index': int(color_index), 'style_index': int(style_index), 'ranges': ranges}


def update_mark(mark_id: str, color_index: int | None = None, hidden: bool | None = None, database: Database = DB) -> dict:
    if ':' in mark_id:
        user_mark, backup = mark_id.split(':', 1)
        database.execute(
            'INSERT INTO imported_mark_overrides(backup_id,user_mark_id,hidden,color_index,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(backup_id,user_mark_id) DO UPDATE SET hidden=excluded.hidden,color_index=excluded.color_index,updated_at=excluded.updated_at',
            (backup, int(user_mark), 1 if hidden else 0, color_index, utc_now()),
        )
        return {'id': mark_id, 'source': 'backup', 'hidden': bool(hidden), 'color_index': color_index}
    if database.scalar('SELECT 1 FROM mark_groups WHERE id=?', (mark_id,)):
        if color_index is not None:
            database.execute('UPDATE mark_groups SET color_index=?,updated_at=? WHERE id=?', (int(color_index), utc_now(), mark_id))
        return database.rows('SELECT * FROM mark_groups WHERE id=?', (mark_id,))[0]
    if color_index is not None:
        database.execute('UPDATE local_marks SET color_index=? WHERE id=?', (int(color_index), mark_id))
    rows = database.rows('SELECT * FROM local_marks WHERE id=?', (mark_id,))
    if not rows:
        raise ValueError('Markierung wurde nicht gefunden.')
    return rows[0]


def delete_mark_any(mark_id: str, database: Database = DB) -> None:
    if ':' in mark_id:
        update_mark(mark_id, hidden=True, database=database)
        return
    if database.scalar('SELECT 1 FROM mark_groups WHERE id=?', (mark_id,)):
        database.execute('DELETE FROM mark_groups WHERE id=?', (mark_id,))
        return
    delete_mark(mark_id, database)


def document_mark_groups(document_id: int, database: Database = DB) -> list[dict]:
    groups = database.rows('SELECT * FROM mark_groups WHERE document_id=? ORDER BY created_at', (int(document_id),))
    for group in groups:
        group['ranges'] = database.rows('SELECT block_identifier,start_token,end_token,position FROM mark_group_ranges WHERE group_id=? ORDER BY position', (group['id'],))
    return groups


class _InputFieldTagParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.aliases: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs):
        values = {str(key).lower(): str(value or '') for key, value in attrs}
        editable = tag.lower() in {'textarea', 'input'} or values.get('contenteditable', '').lower() == 'true'
        if not editable:
            return
        preferred = values.get('data-text-tag') or values.get('data-texttag') or values.get('data-input-field')
        element_id = values.get('id', '').strip()
        name = values.get('name', '').strip()
        canonical = preferred.strip() if preferred else ''
        if not canonical and re.fullmatch(r'tt\d+', element_id, flags=re.IGNORECASE):
            canonical = element_id
        if not canonical:
            canonical = element_id or name
        if not canonical:
            return
        for alias in (canonical, preferred or '', element_id, name):
            alias = str(alias or '').strip()
            if alias:
                self.aliases[alias] = canonical


def _input_field_tag_map(document_id: int, database: Database = DB) -> dict[str, str]:
    rows = database.rows('SELECT content_html FROM documents WHERE id=?', (int(document_id),))
    if not rows:
        return {}
    parser = _InputFieldTagParser()
    parser.feed(str(rows[0].get('content_html') or ''))
    return parser.aliases


def canonical_input_field_tag(document_id: int, text_tag: str, database: Database = DB) -> str:
    raw = str(text_tag or '').strip()
    if not raw:
        return ''
    return _input_field_tag_map(int(document_id), database).get(raw, raw)


def migrate_local_input_fields(database: Database = DB, document_id: int | None = None) -> int:
    params = (int(document_id),) if document_id is not None else ()
    where = ' WHERE f.document_id=?' if document_id is not None else ''
    rows = database.rows(
        f"SELECT f.document_id,f.text_tag,f.value,f.updated_at FROM local_input_fields f{where} ORDER BY f.document_id,f.updated_at,f.text_tag",
        params,
    )
    grouped: dict[int, dict[str, dict]] = {}
    changed = 0
    for item in rows:
        doc_id = int(item['document_id'])
        canonical = canonical_input_field_tag(doc_id, str(item['text_tag']), database)
        if canonical != str(item['text_tag']):
            changed += 1
        grouped.setdefault(doc_id, {})[canonical] = {
            'value': str(item.get('value') or ''),
            'updated_at': str(item.get('updated_at') or utc_now()),
        }
    if not changed:
        return 0
    with database.transaction() as con:
        for doc_id, values in grouped.items():
            con.execute('DELETE FROM local_input_fields WHERE document_id=?', (doc_id,))
            con.executemany(
                'INSERT INTO local_input_fields(document_id,text_tag,value,updated_at) VALUES(?,?,?,?)',
                [(doc_id, tag, item['value'], item['updated_at']) for tag, item in values.items() if tag],
            )
    return changed


def save_input_field(document_id: int, text_tag: str, value: str, database: Database = DB) -> dict:
    document_id = int(document_id)
    raw_tag = str(text_tag or '').strip()
    canonical = canonical_input_field_tag(document_id, raw_tag, database)
    if not canonical:
        raise ValueError('Antwortfeld besitzt keine gültige Publikationskennung.')
    aliases = [alias for alias, target in _input_field_tag_map(document_id, database).items() if target == canonical and alias != canonical]
    now = utc_now()
    with database.transaction() as con:
        con.execute(
            'INSERT INTO local_input_fields(document_id,text_tag,value,updated_at) VALUES(?,?,?,?) ON CONFLICT(document_id,text_tag) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at',
            (document_id, canonical, str(value), now),
        )
        if aliases:
            placeholders = ','.join('?' for _ in aliases)
            con.execute(
                f'DELETE FROM local_input_fields WHERE document_id=? AND text_tag IN ({placeholders})',
                (document_id, *aliases),
            )
    return {'document_id': document_id, 'text_tag': canonical, 'value': str(value)}


def input_fields_for_document(document_id: int, database: Database = DB) -> list[dict]:
    document_id = int(document_id)
    migrate_local_input_fields(database, document_id)
    merged: dict[str, dict] = {}
    imported = database.rows(
        '''SELECT f.text_tag,f.value,'backup' AS source,f.backup_id,b.imported_at AS updated_at
           FROM input_fields f
           JOIN backup_resolution r ON r.backup_id=f.backup_id AND r.location_id=f.location_id
           JOIN backup_imports b ON b.id=f.backup_id
           WHERE r.document_row_id=? ORDER BY b.imported_at,f.text_tag''',
        (document_id,),
    )
    for item in imported:
        canonical = canonical_input_field_tag(document_id, str(item['text_tag']), database)
        entry = dict(item)
        entry['text_tag'] = canonical
        merged[canonical] = entry
    for item in database.rows("SELECT text_tag,value,'local' AS source,NULL AS backup_id,updated_at FROM local_input_fields WHERE document_id=? ORDER BY text_tag", (document_id,)):
        canonical = canonical_input_field_tag(document_id, str(item['text_tag']), database)
        entry = dict(item)
        entry['text_tag'] = canonical
        merged[canonical] = entry
    return [merged[key] for key in sorted(merged) if key]

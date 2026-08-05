from __future__ import annotations
from datetime import date, datetime, timedelta
import re
from typing import Any
import unicodedata
from .database import DB, Database
from .utils import html_to_text, utc_now



def _symbol(item: dict[str, Any]) -> str:
    return str(item.get("key_symbol") or item.get("symbol") or "").strip().lower()


def _is_watchtower_study(item: dict[str, Any]) -> bool:
    symbol = _symbol(item)
    return bool(re.fullmatch(r"w(?:\d{2,4})?", symbol))


def _is_meeting_workbook(item: dict[str, Any]) -> bool:
    symbol = _symbol(item)
    return bool(re.fullmatch(r"mwb(?:\d{2,4})?", symbol))

SECTION_MAP = {
    'treasures': ('Schätze aus Gottes Wort', ('schätze', 'treasures', 'gottes wort')),
    'ministry': ('Uns im Dienst verbessern', ('dienst verbessern', 'apply yourself', 'ministry')),
    'living': ('Unser Leben als Christ', ('leben als christ', 'living as christians', 'christian living')),
    'watchtower': ('Wachtturm-Studium', ('wachtturm', 'watchtower')),
}


def week_bounds(offset: int = 0, today: date | None = None) -> tuple[date, date]:
    current = today or date.today()
    monday = current - timedelta(days=current.weekday()) + timedelta(weeks=offset)
    return monday, monday + timedelta(days=6)


def _section_for(title: str, text: str = '') -> str:
    haystack = f'{title} {text}'.lower()
    for key, (_, needles) in SECTION_MAP.items():
        if any(needle in haystack for needle in needles):
            return key
    return 'other'


def _month_start(year: int, month: int) -> date | None:
    try:
        return date(int(year), int(month), 1)
    except Exception:
        return None


def _add_months(value: date, months: int) -> date:
    total = value.year * 12 + value.month - 1 + months
    return date(total // 12, total % 12 + 1, 1)


def _issue_month(item: dict[str, Any]) -> date | None:
    raw = ''.join(ch for ch in str(item.get('issue_tag') or '') if ch.isdigit())
    candidates: list[tuple[int, int]] = []
    if len(raw) >= 6:
        candidates.append((int(raw[:4]), int(raw[4:6])))
    title = f"{item.get('title') or ''} {item.get('short_title') or ''}".lower()
    months = {
        'januar': 1, 'februar': 2, 'märz': 3, 'maerz': 3, 'april': 4, 'mai': 5, 'juni': 6,
        'juli': 7, 'august': 8, 'september': 9, 'oktober': 10, 'november': 11, 'dezember': 12,
        'january': 1, 'february': 2, 'march': 3, 'may': 5, 'june': 6, 'july': 7,
        'october': 10, 'december': 12,
    }
    year = int(item.get('year') or 0)
    for name, month in months.items():
        if name in title and year:
            candidates.append((year, month))
            break
    for field in ('generally_available_date', 'last_modified', 'cataloged_on', 'last_updated'):
        value = str(item.get(field) or '')
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            candidates.append((parsed.year, parsed.month))
        except Exception:
            pass
    for year_value, month_value in candidates:
        result = _month_start(year_value, month_value)
        if result:
            return result
    return None


def _resolve_installed_catalog_item(database: Database, item: dict[str, Any]) -> dict[str, Any]:
    if item.get('installed_id'):
        return item
    catalog_id = int(item.get('catalog_id') or 0)
    if catalog_id:
        rows = database.rows(
            "SELECT id,key_symbol,year,issue_tag FROM publications WHERE catalog_id=? AND status='installed' ORDER BY installed_at DESC LIMIT 1",
            (catalog_id,),
        )
        if rows:
            return {**item, 'installed': 1, 'installed_id': rows[0]['id']}
    language_index = int(item.get('language_index') or 0)
    year = int(item.get('year') or 0)
    issue_tag = int(item.get('issue_tag') or 0)
    candidates = database.rows(
        "SELECT id,key_symbol,year,issue_tag FROM publications WHERE language_index=? AND year=? AND issue_tag=? AND status='installed' ORDER BY installed_at DESC",
        (language_index, year, issue_tag),
    )
    if _is_watchtower_study(item):
        match = next((row for row in candidates if _is_watchtower_study(row)), None)
    elif _is_meeting_workbook(item):
        match = next((row for row in candidates if _is_meeting_workbook(row)), None)
    else:
        catalog_symbol = _symbol(item)
        match = next((row for row in candidates if _symbol(row) == catalog_symbol), None)
    if match:
        return {**item, 'installed': 1, 'installed_id': match['id']}
    return item


def _catalog_score(item: dict[str, Any], monday: date, kind: str) -> tuple[int, int]:
    issue = _issue_month(item)
    target = date(monday.year, monday.month, 1)
    if issue is None:
        return (-10000, int(item.get('catalog_id') or 0))
    distance = abs((issue.year - target.year) * 12 + issue.month - target.month)
    if kind == 'mwb':
        covers = issue <= target <= _add_months(issue, 1)
        score = 10000 if covers else 1000 - distance * 100
    else:
        expected_issue = _add_months(target, -2)
        expected_distance = abs((issue.year - expected_issue.year) * 12 + issue.month - expected_issue.month)
        covers = issue.year == expected_issue.year and issue.month == expected_issue.month
        score = 9000 if covers else 900 - expected_distance * 100
        distance = expected_distance
    if issue > _add_months(target, 2):
        score -= 5000
    return (score, -distance)


def _meeting_rows(database: Database, monday: date, sunday: date, language_index: int | None = None) -> list[dict[str, Any]]:
    clauses = ["date(d.end_date)>=date(?)", "date(d.start_date)<=date(?)", "(lower(p.key_symbol) LIKE 'mwb%' OR lower(p.key_symbol) LIKE 'w%')"]
    params: list[Any] = [monday.isoformat(), sunday.isoformat()]
    if language_index is not None:
        clauses.append('p.language_index=?')
        params.append(int(language_index))
    rows = database.rows(f"""SELECT d.*,p.title AS publication_title,p.key_symbol,p.language_index,
        doc.id AS document_id,doc.title AS document_title,doc.subtitle AS document_subtitle,doc.sort_order
        FROM dated_texts d JOIN publications p ON p.id=d.publication_id
        LEFT JOIN documents doc ON doc.publication_id=d.publication_id AND doc.source_document_id=d.document_source_id
        WHERE {' AND '.join(clauses)}
        ORDER BY d.start_date,d.class,doc.sort_order""", tuple(params))
    return [row for row in rows if _is_meeting_workbook(row) or _is_watchtower_study(row)]


ADDITIONAL_MATERIAL_RULES = (
    ("songbook", "Singt voller Freude für Jehova", ("sjj", "singt voller freude")),
    ("ministry_book", "Liebt Menschen, macht sie zu Jüngern", ("lmd", "liebt menschen", "make disciples")),
    ("teaching", "Werde ein besserer Leser und Lehrer", ("th", "besserer leser", "reading and teaching")),
    ("instructions", "Anweisungen für die Leben-und-Dienst-Zusammenkunft", ("s-38", "anweisungen für die leben", "instructions for our christian")),
)

def _material_match(item: dict[str, Any], needles: tuple[str, ...]) -> bool:
    probe = " ".join(str(item.get(key) or "") for key in ("key_symbol", "title", "short_title", "display_title")).lower()
    symbol = str(item.get("key_symbol") or "").lower()
    return any(symbol == needle or needle in probe for needle in needles)

def _installed_materials(database: Database, language_index: int | None) -> list[dict[str, Any]]:
    clauses=["status='installed'"]
    params=[]
    if language_index is not None:
        clauses.append('language_index=?')
        params.append(int(language_index))
    rows=database.rows(f"""SELECT id,title,short_title,display_title,key_symbol,language_index,year,issue_tag,cover_path,thumbnail_path,last_opened_at
        FROM publications WHERE {' AND '.join(clauses)} ORDER BY year DESC,installed_at DESC""",tuple(params))
    result=[]
    seen=set()
    for kind,label,needles in ADDITIONAL_MATERIAL_RULES:
        match=next((row for row in rows if _material_match(row,needles)),None)
        if not match:
            continue
        seen.add(match['id'])
        result.append({**match,'material_kind':kind,'display_label':label,'installed':1,'cover_url':f"/api/publications/{match['id']}/cover"})
    return result

def _catalog_additional_materials(database: Database, language_index: int | None, installed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clauses=['1=1']
    params=[]
    if language_index is not None:
        clauses.append('language_index=?')
        params.append(int(language_index))
    rows=database.rows(f"""SELECT catalog_id,title,short_title,key_symbol,language_index,year,issue_tag,image_fragment
        FROM catalog_publications WHERE {' AND '.join(clauses)} ORDER BY year DESC,last_updated DESC""",tuple(params))
    installed_kinds={item['material_kind'] for item in installed}
    result=[]
    for kind,label,needles in ADDITIONAL_MATERIAL_RULES:
        if kind in installed_kinds:
            continue
        match=next((row for row in rows if _material_match(row,needles)),None)
        if not match:
            continue
        result.append({**match,'material_kind':kind,'display_label':label,'installed':0,'cover_url':f"/api/catalog/{match['catalog_id']}/cover" if match.get('image_fragment') else ''})
    return result



def _normal_text(value: Any) -> str:
    text = html_to_text(str(value or ""))
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _watchtower_document_probe(document: dict[str, Any]) -> str:
    return " ".join(str(document.get(key) or "") for key in ("title", "toc_title", "subtitle", "class_name", "content_text"))


def _is_watchtower_front_matter(document: dict[str, Any]) -> bool:
    probe = _normal_text(_watchtower_document_probe(document))
    title_probe = _normal_text(" ".join(str(document.get(key) or "") for key in ("title", "toc_title", "subtitle")))
    question_count = int(document.get("question_count") or 0)
    if question_count:
        return False
    if any(term in probe for term in (
        "inhaltsverzeichnis", "contents", "titelblatt", "cover", "studienausgabe mai",
        "studienausgabe juni", "studienausgabe juli", "studienausgabe august",
        "der wachtturm verkundigt jehovas konigreich studienausgabe",
    )):
        return True
    if int(document.get("sort_order") or 0) <= 1 and any(term in title_probe for term in ("studienausgabe", "wachtturm")):
        return True
    return False


def _is_watchtower_article(document: dict[str, Any]) -> bool:
    if _is_watchtower_front_matter(document):
        return False
    if int(document.get("question_count") or 0) > 0:
        return True
    probe = _normal_text(_watchtower_document_probe(document))
    return any(term in probe for term in ("studienartikel", "study article"))


def _article_title(document: dict[str, Any]) -> str:
    values = [str(document.get(key) or "").strip() for key in ("toc_title", "title", "subtitle")]
    values = [value for value in values if value]
    return max(values, key=len, default="")


def _article_number(document: dict[str, Any]) -> int | None:
    probe = _normal_text(_watchtower_document_probe(document))
    match = re.search(r"(?:studienartikel|study article)\s*(\d{1,3})(?:\D|$)", probe, re.I)
    if not match:
        match = re.search(r"(?:^|\s)(\d{1,3})(?:\s*[.:–-])", probe)
    if not match:
        return None
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return None


def _date_text(value: Any) -> str:
    return str(value or "")[:10]


def _article_match_score(document: dict[str, Any], source_probe: str, source_number: str = "") -> int:
    score = min(int(document.get("question_count") or 0), 30) * 5
    labels = [str(document.get(key) or "") for key in ("toc_title", "title", "subtitle")]
    normalized_labels = [_normal_text(label) for label in labels if label]
    for label in normalized_labels:
        if len(label) >= 10 and label in source_probe:
            score += 1200 + min(len(label), 180)
        elif len(source_probe) >= 10 and source_probe in label:
            score += 700
        words = {word for word in label.split() if len(word) >= 4}
        if words:
            overlap = len(words & set(source_probe.split()))
            score += overlap * 22
            if overlap >= max(3, len(words) - 2):
                score += 250
    if source_number:
        candidate_probe = " ".join(normalized_labels)
        if re.search(rf"(?:studienartikel|study article)\s*{re.escape(source_number)}(?:\D|$)", candidate_probe, re.I):
            score += 1500
    return score


def _weekly_date_rows(database: Database, publication_id: str) -> list[dict[str, Any]]:
    rows = database.rows(
        "SELECT source_dated_text_id,document_source_id,start_date,end_date,caption,content_html "
        "FROM dated_texts WHERE publication_id=? AND julianday(end_date)-julianday(start_date) BETWEEN 5 AND 8 "
        "ORDER BY start_date,source_dated_text_id",
        (publication_id,),
    )
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for item in rows:
        key = (str(item.get("start_date") or "")[:10], str(item.get("end_date") or item.get("start_date") or "")[:10])
        previous = unique.get(key)
        if previous is None or len(str(item.get("content_html") or "")) > len(str(previous.get("content_html") or "")):
            unique[key] = item
    return list(unique.values())


def _watchtower_article_for_week(database: Database, publication_id: str, monday: date, sunday: date, row: dict[str, Any] | None = None) -> dict[str, Any] | None:
    documents = database.rows(
        """SELECT d.id,d.source_document_id,d.title,d.toc_title,d.subtitle,d.class_name,d.sort_order,d.content_text,
        (SELECT COUNT(*) FROM questions q WHERE q.publication_id=d.publication_id AND q.document_source_id=d.source_document_id) AS question_count
        FROM documents d WHERE d.publication_id=? ORDER BY d.sort_order""",
        (publication_id,),
    )
    candidates = [item for item in documents if _is_watchtower_article(item)]
    if not candidates:
        candidates = [item for item in documents if not _is_watchtower_front_matter(item)]
    if not candidates:
        return None

    target_rows: list[dict[str, Any]] = []
    if row:
        target_rows.append(row)
    target_rows.extend(database.rows(
        "SELECT source_dated_text_id,document_source_id,start_date,end_date,caption,content_html "
        "FROM dated_texts WHERE publication_id=? AND date(end_date)>=date(?) AND date(start_date)<=date(?) "
        "ORDER BY start_date,source_dated_text_id",
        (publication_id, monday.isoformat(), sunday.isoformat()),
    ))

    seen_rows: set[tuple[Any, Any]] = set()
    filtered_rows: list[dict[str, Any]] = []
    for dated in target_rows:
        marker = (dated.get("source_dated_text_id"), dated.get("document_source_id"))
        if marker in seen_rows:
            continue
        seen_rows.add(marker)
        filtered_rows.append(dated)

    for dated in filtered_rows:
        source_id = dated.get("document_source_id")
        direct = next((item for item in candidates if source_id is not None and item.get("source_document_id") == source_id), None)
        if direct:
            return direct

    source_probe = _normal_text(" ".join(
        str(dated.get(key) or "")
        for dated in filtered_rows
        for key in ("caption", "document_title", "content_html")
    ))
    number_match = re.search(r"(?:studienartikel|study article)\s*(\d{1,3})", source_probe, re.I)
    source_number = number_match.group(1) if number_match else ""
    scored = sorted(
        ((_article_match_score(item, source_probe, source_number), item) for item in candidates),
        key=lambda pair: (pair[0], -int(pair[1].get("sort_order") or 0)),
        reverse=True,
    )
    if scored and scored[0][0] >= 260:
        return scored[0][1]

    weekly_rows = _weekly_date_rows(database, publication_id)
    week_index = next((
        index for index, item in enumerate(weekly_rows)
        if _date_text(item.get("start_date")) <= sunday.isoformat()
        and _date_text(item.get("end_date") or item.get("start_date")) >= monday.isoformat()
    ), -1)
    current_week_row = weekly_rows[week_index] if 0 <= week_index < len(weekly_rows) else None
    if current_week_row:
        source_id = current_week_row.get("document_source_id")
        direct = next((item for item in candidates if source_id is not None and item.get("source_document_id") == source_id), None)
        if direct:
            return direct
        current_probe = _normal_text(" ".join(str(current_week_row.get(key) or "") for key in ("caption", "content_html")))
        current_number_match = re.search(r"(?:studienartikel|study article)\s*(\d{1,3})", current_probe, re.I)
        if current_number_match:
            number = int(current_number_match.group(1))
            numbered = next((item for item in candidates if _article_number(item) == number), None)
            if numbered:
                return numbered

    ordered_candidates = sorted(
        candidates,
        key=lambda item: (
            _article_number(item) is None,
            _article_number(item) if _article_number(item) is not None else 10000,
            int(item.get("sort_order") or 0),
        ),
    )
    if 0 <= week_index < len(ordered_candidates):
        return ordered_candidates[week_index]

    dated_source_numbers = []
    for dated in filtered_rows:
        probe = _normal_text(" ".join(str(dated.get(key) or "") for key in ("caption", "content_html")))
        match = re.search(r"(?:studienartikel|study article)\s*(\d{1,3})", probe, re.I)
        if match:
            dated_source_numbers.append(int(match.group(1)))
    for number in dated_source_numbers:
        numbered = next((item for item in ordered_candidates if _article_number(item) == number), None)
        if numbered:
            return numbered

    if scored and scored[0][0] > 0:
        return scored[0][1]
    if len(ordered_candidates) == 1:
        return ordered_candidates[0]
    return max(ordered_candidates, key=lambda item: (int(item.get("question_count") or 0), -int(item.get("sort_order") or 0)))


def meeting_week(offset: int = 0, database: Database = DB, today: date | None = None, language_index: int | None = None) -> dict[str, Any]:
    monday, sunday = week_bounds(offset, today)
    rows = _meeting_rows(database, monday, sunday, language_index)
    sections={key:{'key':key,'title':title,'items':[]} for key,(title,_) in SECTION_MAP.items()}
    sections['other']={'key':'other','title':'Weitere Programmpunkte','items':[]}
    watchtower_articles: dict[str, list[dict[str, Any]]] = {}
    watchtower_dates: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        publication_id = str(row.get('publication_id') or '')
        key_symbol = str(row.get('key_symbol') or '').lower()
        if _is_watchtower_study(row):
            article = _watchtower_article_for_week(database, publication_id, monday, sunday, row)
            if article:
                row = {**row, 'document_id': article.get('id'), 'document_title': article.get('title') or article.get('toc_title'), 'document_subtitle': article.get('subtitle') or ''}
        title=row.get('caption') or row.get('document_title') or row.get('publication_title') or 'Programmpunkt'
        text=html_to_text(row.get('content_html') or '')[:420]
        section=_section_for(title,text)
        note_count=0
        if row.get('document_id'):
            note_count=int(database.scalar('SELECT COUNT(*) FROM meeting_notes WHERE document_id=?',(row['document_id'],)) or 0)
        sections[section]['items'].append({
            'title':title,'subtitle':row.get('document_subtitle') or row.get('publication_title') or '',
            'publication':row.get('publication_title') or '','key_symbol':row.get('key_symbol') or '',
            'start':row.get('start_date') or monday.isoformat(),'end':row.get('end_date') or sunday.isoformat(),
            'document_id':row.get('document_id'),'text':text,'note_count':note_count,'section':section,
        })
    visible=[section for section in sections.values() if section['items']]
    clauses=["(lower(c.key_symbol) LIKE 'mwb%' OR lower(c.key_symbol) LIKE 'w%')"]
    params=[]
    if language_index is not None:
        clauses.append('c.language_index=?')
        params.append(int(language_index))
    catalog=database.rows(f"""SELECT c.catalog_id,c.title,c.short_title,c.key_symbol,c.language_index,c.year,c.issue_tag,c.image_fragment,
        c.generally_available_date,c.last_updated,c.last_modified,c.cataloged_on,
        p.id AS installed_id, CASE WHEN p.id IS NULL THEN 0 ELSE 1 END installed
        FROM catalog_publications c LEFT JOIN publications p ON p.key_symbol=c.key_symbol AND p.language_index=c.language_index AND p.year=c.year AND p.issue_tag=c.issue_tag
        WHERE {' AND '.join(clauses)}""", tuple(params))
    mwb=sorted((item for item in catalog if _is_meeting_workbook(item)), key=lambda item:_catalog_score(item,monday,'mwb'), reverse=True)
    watchtower=sorted((item for item in catalog if _is_watchtower_study(item)), key=lambda item:_catalog_score(item,monday,'watchtower'), reverse=True)
    selected=[]
    for kind, items in (('mwb',mwb),('watchtower',watchtower)):
        if not items:
            continue
        item=_resolve_installed_catalog_item(database, items[0])
        score=_catalog_score(item,monday,kind)[0]
        if score < 0:
            continue
        issue=_issue_month(item)
        item['cover_url']=f"/api/catalog/{item['catalog_id']}/cover" if item.get('image_fragment') else ''
        item['material_kind']=kind
        item['issue_month']=issue.isoformat() if issue else ''
        item['selection_reason']=f"Zielwoche {monday.isoformat()} bis {sunday.isoformat()}, erkannter Ausgabemonat {issue.strftime('%m/%Y') if issue else 'unbekannt'}"
        selected.append(item)
    installed_additional=_installed_materials(database,language_index)
    additional=installed_additional+_catalog_additional_materials(database,language_index,installed_additional)
    life_item=next((item for item in selected if item.get('material_kind')=='mwb'),None)
    watchtower_item=next((item for item in selected if item.get('material_kind')=='watchtower'),None)
    watchtower_section=next((section for section in visible if section.get('key')=='watchtower'),None)
    if watchtower_item and watchtower_section and watchtower_section.get('items'):
        article=watchtower_section['items'][0]
        watchtower_item={**watchtower_item,'document_id':article.get('document_id'),'article_title':article.get('title'),'article_subtitle':article.get('subtitle')}
    if watchtower_item and not watchtower_item.get('document_id') and watchtower_item.get('installed_id'):
        publication_id=str(watchtower_item['installed_id'])
        article=_watchtower_article_for_week(database,publication_id,monday,sunday)
        if article:
            watchtower_item={**watchtower_item,'document_id':article.get('id'),'article_title':article.get('title') or article.get('toc_title'),'article_subtitle':article.get('subtitle') or ''}
    life_section=next((section for section in visible if section.get('key') in ('treasures','ministry','living')),None)
    if life_item and life_section and life_section.get('items'):
        first=life_section['items'][0]
        life_item={**life_item,'document_id':first.get('document_id'),'article_title':first.get('title'),'article_subtitle':first.get('subtitle')}
    return {
        'offset':offset,'week_start':monday.isoformat(),'week_end':sunday.isoformat(),'available':bool(visible),
        'sections':visible,'items':[i for s in visible for i in s['items']],
        'downloads':selected,'primary':{'life_and_ministry':life_item,'watchtower':watchtower_item},
        'additional_materials':additional,'offline_ready':bool(visible),
        'selection':{'requested_week_start':monday.isoformat(),'requested_week_end':sunday.isoformat(),'language_index':language_index},
    }


def meeting_notes(document_id: int | None = None, database: Database = DB) -> list[dict]:
    if document_id is None:
        return database.rows('SELECT * FROM meeting_notes ORDER BY updated_at DESC')
    return database.rows('SELECT * FROM meeting_notes WHERE document_id=? ORDER BY updated_at DESC',(document_id,))


def save_meeting_note(document_id: int, title: str, content: str, database: Database = DB) -> dict:
    if not document_id:
        raise ValueError('Programmpunkt fehlt.')
    note_id=f'meeting-{document_id}'
    now=utc_now()
    database.execute('''INSERT INTO meeting_notes(id,document_id,title,content,created_at,updated_at) VALUES(?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET title=excluded.title,content=excluded.content,updated_at=excluded.updated_at''',
        (note_id,int(document_id),title.strip() or 'Zusammenkunftsnotiz',content.strip(),now,now))
    return database.rows('SELECT * FROM meeting_notes WHERE id=?',(note_id,))[0]


def delete_meeting_note(note_id: str, database: Database = DB) -> None:
    database.execute('DELETE FROM meeting_notes WHERE id=?',(note_id,))

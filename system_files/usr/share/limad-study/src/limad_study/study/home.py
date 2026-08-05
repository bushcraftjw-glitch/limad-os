from __future__ import annotations
from datetime import date, datetime, timedelta
from ..database import DB, Database
from ..utils import html_to_text
from ..meetings import meeting_week


def daily_text(database: Database = DB, today: date | None = None, language_index: int | None = None) -> dict:
    current = (today or date.today()).isoformat()
    clauses = ["date(d.start_date)<=date(?)", "date(d.end_date)>=date(?)"]
    params = [current, current]
    if language_index is not None:
        clauses.append("p.language_index=?")
        params.append(int(language_index))
    clauses.append("(lower(trim(p.key_symbol))='es' OR lower(trim(p.key_symbol)) GLOB 'es[0-9]*')")
    rows = database.rows(f'''SELECT d.*,p.title AS publication_title,p.key_symbol,p.language_index,doc.id AS document_id,doc.title AS document_title
        FROM dated_texts d JOIN publications p ON p.id=d.publication_id
        LEFT JOIN documents doc ON doc.publication_id=d.publication_id AND doc.source_document_id=d.document_source_id
        WHERE {' AND '.join(clauses)}
        ORDER BY COALESCE(p.year,0) DESC,d.class,d.start_date LIMIT 1''',tuple(params))
    if rows:
        row=rows[0]
        return {"available":True,"date":current,"caption":row.get("caption") or row.get("document_title") or "Tagestext","text":html_to_text(row.get("content_html") or ""),"html":row.get("content_html") or "","document_id":row.get("document_id"),"publication":row.get("publication_title")}
    return {"available":False,"date":current,"caption":"Tagestext","text":"Lade die aktuelle Tagestext-Publikation herunter oder importiere sie, damit der Text hier offline erscheint.","html":"","document_id":None,"publication":""}


def meetings(database: Database = DB, today: date | None = None) -> dict:
    current=today or date.today()
    monday=current-timedelta(days=current.weekday())
    sunday=monday+timedelta(days=6)
    rows=database.rows('''SELECT d.*,p.title AS publication_title,p.key_symbol,doc.id AS document_id,doc.title AS document_title
        FROM dated_texts d JOIN publications p ON p.id=d.publication_id
        LEFT JOIN documents doc ON doc.publication_id=d.publication_id AND doc.source_document_id=d.document_source_id
        WHERE lower(p.key_symbol) LIKE 'mwb%' AND date(d.end_date)>=date(?) AND date(d.start_date)<=date(?)
        ORDER BY d.start_date,d.class''',(monday.isoformat(),sunday.isoformat()))
    items=[]
    for row in rows:
        items.append({"title":row.get("caption") or row.get("document_title") or row.get("publication_title"),"subtitle":row.get("publication_title") or "","start":row.get("start_date"),"end":row.get("end_date"),"document_id":row.get("document_id"),"text":html_to_text(row.get("content_html") or "")[:220]})
    if not items:
        pubs=database.rows("SELECT id,title,last_opened_at FROM publications WHERE lower(key_symbol) LIKE 'mwb%' ORDER BY year DESC,issue_tag DESC LIMIT 1")
        if pubs:
            docs=database.rows("SELECT id,title,subtitle FROM documents WHERE publication_id=? ORDER BY sort_order LIMIT 8",(pubs[0]["id"],))
            items=[{"title":d.get("title") or "Zusammenkunft","subtitle":d.get("subtitle") or pubs[0]["title"],"document_id":d["id"],"start":"","end":"","text":""} for d in docs]
    return {"week_start":monday.isoformat(),"week_end":sunday.isoformat(),"available":bool(items),"items":items}


MINISTRY_TOOL_RULES = (
    ("lmd", ("liebt menschen", "make disciples")),
    ("th", ("besserer leser", "reading and teaching")),
    ("lff", ("glücklich – für immer", "glücklich für immer", "enjoy life forever")),
    ("fg", ("gute botschaft", "good news from god")),
    ("bhs", ("bibel lehren", "bible teach")),
    ("bt", ("gründlich zeugnis", "bearing thorough witness")),
    ("sjj", ("singt voller freude", "sing out joyfully")),
)


def ministry_tools(database: Database, language_index: int) -> list[dict]:
    installed = database.rows(
        """SELECT id,title,short_title,display_title,publication_type,cover_path,last_opened_at,favorite,language_index,key_symbol,year,issue_tag
        FROM publications WHERE language_index=? AND status='installed' ORDER BY year DESC,installed_at DESC""",
        (int(language_index),),
    )
    catalog = database.rows(
        """SELECT catalog_id,title,short_title,key_symbol,language_index,year,issue_tag,image_fragment,last_updated,generally_available_date
        FROM catalog_publications WHERE language_index=? ORDER BY year DESC,COALESCE(generally_available_date,last_updated,cataloged_on) DESC""",
        (int(language_index),),
    )

    def probe(item: dict) -> str:
        return " ".join(str(item.get(key) or "") for key in ("key_symbol", "title", "short_title", "display_title")).lower()

    result: list[dict] = []
    used: set[str] = set()
    for symbol, needles in MINISTRY_TOOL_RULES:
        match = next((item for item in installed if str(item.get("key_symbol") or "").strip().lower() == symbol), None)
        if not match:
            match = next((item for item in installed if any(needle in probe(item) for needle in needles)), None)
        if match:
            identity = str(match.get("id") or "")
            if identity and identity not in used:
                used.add(identity)
                result.append({**match, "installed": 1, "installed_id": match.get("id"), "official_tool": 1})
            continue
        catalog_match = next((item for item in catalog if str(item.get("key_symbol") or "").strip().lower() == symbol), None)
        if not catalog_match:
            catalog_match = next((item for item in catalog if any(needle in probe(item) for needle in needles)), None)
        if catalog_match:
            identity = f"catalog:{catalog_match.get('catalog_id')}"
            if identity not in used:
                used.add(identity)
                result.append({
                    **catalog_match,
                    "installed": 0,
                    "official_tool": 1,
                    "cover_url": f"/api/catalog/{catalog_match['catalog_id']}/cover" if catalog_match.get("image_fragment") else "",
                })
        if len(result) >= 6:
            break
    return result[:6]


def home_payload(database: Database = DB, language_index: int | None = None) -> dict:
    if language_index is None:
        language_index=int(database.scalar("SELECT value FROM settings WHERE key='language_index'") or 2)
    recent=database.rows('''SELECT id,title,short_title,publication_type,cover_path,last_opened_at,favorite,language_index
        FROM publications WHERE language_index=? ORDER BY COALESCE(last_opened_at,installed_at) DESC LIMIT 8''',(int(language_index),))
    favorites=database.rows('''SELECT id,title,short_title,publication_type,cover_path,last_opened_at,favorite,language_index
        FROM publications WHERE favorite=1 AND language_index=? ORDER BY COALESCE(last_opened_at,installed_at) DESC LIMIT 8''',(int(language_index),))
    ministry_tool_items=ministry_tools(database,int(language_index))
    newest=database.rows('''SELECT c.catalog_id,c.title,c.short_title,c.key_symbol,c.language_index,c.language_symbol,c.year,c.issue_tag,c.last_updated,c.generally_available_date,c.image_fragment,
        CASE WHEN p.id IS NULL THEN 0 ELSE 1 END installed
        FROM catalog_publications c LEFT JOIN publications p ON p.key_symbol=c.key_symbol AND p.language_index=c.language_index AND p.year=c.year AND p.issue_tag=c.issue_tag
        WHERE c.language_index=?
        ORDER BY COALESCE(c.generally_available_date,c.last_updated,c.cataloged_on) DESC LIMIT 8''',(int(language_index),))
    for item in newest:
        item["cover_url"]=f"/api/catalog/{item['catalog_id']}/cover" if item.get("image_fragment") else ""
    daily=daily_text(database,language_index=language_index)
    if not daily.get("available"):
        current_year=date.today().year
        candidates=database.rows('''SELECT c.catalog_id,c.title,c.short_title,c.key_symbol,c.year,c.issue_tag,
            CASE WHEN p.id IS NULL THEN 0 ELSE 1 END AS installed,p.id AS installed_id
            FROM catalog_publications c
            LEFT JOIN publications p ON p.key_symbol=c.key_symbol AND p.language_index=c.language_index AND p.year=c.year AND p.issue_tag=c.issue_tag
            WHERE c.language_index=? AND c.year=? AND (lower(trim(c.key_symbol))='es' OR lower(trim(c.key_symbol)) GLOB 'es[0-9]*')
            ORDER BY COALESCE(c.generally_available_date,c.last_updated,c.cataloged_on) DESC LIMIT 1''',(int(language_index),current_year))
        if candidates:
            item=candidates[0]
            year=int(item.get("year") or current_year)
            daily["download"]={"catalog_id":item.get("catalog_id"),"year":year,"title":item.get("title") or item.get("short_title") or "Täglich in den Schriften forschen","label":"Tagestext herunterladen"}
        else:
            daily["download"]={"catalog_id":None,"year":current_year,"label":"Tagestext herunterladen"}
    return {
        "daily_text":daily,"meetings":meeting_week(0,database,language_index=language_index),"recent":recent,"favorites":favorites,"ministry_tools":ministry_tool_items,"newest":newest,
        "stats":{"publications":database.scalar("SELECT COUNT(*) FROM publications") or 0,"notes":(database.scalar("SELECT COUNT(*) FROM notes") or 0)+(database.scalar("SELECT COUNT(*) FROM local_notes") or 0),"marks":(database.scalar("SELECT COUNT(*) FROM user_marks") or 0)+(database.scalar("SELECT COUNT(*) FROM local_marks") or 0),"downloads":database.scalar("SELECT COUNT(*) FROM download_jobs WHERE status IN ('queued','downloading','importing')") or 0}
    }

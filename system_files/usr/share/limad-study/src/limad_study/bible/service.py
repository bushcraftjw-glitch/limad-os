from __future__ import annotations
import html
import json
import re
import sqlite3
import urllib.parse
from pathlib import Path
from ..database import DB, Database
from ..crypto import decrypt_html
from ..utils import utc_now
from ..reader.render import render_document


def _bible_clause() -> str:
    return "(lower(COALESCE(publication_type,'')) LIKE '%bible%' OR lower(COALESCE(category,'')) LIKE '%bible%' OR key_symbol IN ('nwt','nwtsty','bi12','rbi8'))"


def _plain(value: object) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    return re.sub(r"\s+", " ", text).strip()


BIBLE_BOOKS_DE = [
    (1, "1. Mose", 50, "hebrew", ["1. mose", "1 mo", "1mo", "1 buch mose", "1. buch mose", "erstes buch mose", "das 1 buch mose", "das 1. buch mose", "das erste buch mose", "genesis"]),
    (2, "2. Mose", 40, "hebrew", ["2. mose", "2 mo", "2mo", "2 buch mose", "2. buch mose", "zweites buch mose", "das 2 buch mose", "das 2. buch mose", "das zweite buch mose", "exodus"]),
    (3, "3. Mose", 27, "hebrew", ["3. mose", "3 mo", "3mo", "3 buch mose", "3. buch mose", "drittes buch mose", "das 3 buch mose", "das 3. buch mose", "das dritte buch mose", "levitikus", "leviticus"]),
    (4, "4. Mose", 36, "hebrew", ["4. mose", "4 mo", "4mo", "4 buch mose", "4. buch mose", "viertes buch mose", "das 4 buch mose", "das 4. buch mose", "das vierte buch mose", "numeri", "numbers"]),
    (5, "5. Mose", 34, "hebrew", ["5. mose", "5 mo", "5mo", "5 buch mose", "5. buch mose", "fünftes buch mose", "fuenftes buch mose", "das 5 buch mose", "das 5. buch mose", "das fünfte buch mose", "das fuenfte buch mose", "deuteronomium", "deuteronomy"]),
    (6, "Josua", 24, "hebrew", ["josua", "joshua"]),
    (7, "Richter", 21, "hebrew", ["richter", "judges"]),
    (8, "Ruth", 4, "hebrew", ["ruth"]),
    (9, "1. Samuel", 31, "hebrew", ["1. samuel", "erstes buch samuel"]),
    (10, "2. Samuel", 24, "hebrew", ["2. samuel", "zweites buch samuel"]),
    (11, "1. Könige", 22, "hebrew", ["1. könige", "1 kings", "erstes buch der könige"]),
    (12, "2. Könige", 25, "hebrew", ["2. könige", "2 kings", "zweites buch der könige"]),
    (13, "1. Chronika", 29, "hebrew", ["1. chronika", "1 chronicles"]),
    (14, "2. Chronika", 36, "hebrew", ["2. chronika", "2 chronicles"]),
    (15, "Esra", 10, "hebrew", ["esra", "ezra"]),
    (16, "Nehemia", 13, "hebrew", ["nehemia", "nehemiah"]),
    (17, "Esther", 10, "hebrew", ["esther"]),
    (18, "Hiob", 42, "hebrew", ["hiob", "job"]),
    (19, "Psalmen", 150, "hebrew", ["psalmen", "psalm", "psalms"]),
    (20, "Sprüche", 31, "hebrew", ["sprüche", "proverbs"]),
    (21, "Prediger", 12, "hebrew", ["prediger", "ecclesiastes"]),
    (22, "Hohes Lied", 8, "hebrew", ["hohes lied", "song of solomon", "song of songs"]),
    (23, "Jesaja", 66, "hebrew", ["jesaja", "isaiah"]),
    (24, "Jeremia", 52, "hebrew", ["jeremia", "jeremiah"]),
    (25, "Klagelieder", 5, "hebrew", ["klagelieder", "lamentations"]),
    (26, "Hesekiel", 48, "hebrew", ["hesekiel", "ezekiel"]),
    (27, "Daniel", 12, "hebrew", ["daniel"]),
    (28, "Hosea", 14, "hebrew", ["hosea"]),
    (29, "Joel", 3, "hebrew", ["joel"]),
    (30, "Amos", 9, "hebrew", ["amos"]),
    (31, "Obadja", 1, "hebrew", ["obadja", "obadiah"]),
    (32, "Jona", 4, "hebrew", ["jona", "jonah"]),
    (33, "Micha", 7, "hebrew", ["micha", "micah"]),
    (34, "Nahum", 3, "hebrew", ["nahum"]),
    (35, "Habakuk", 3, "hebrew", ["habakuk", "habakkuk"]),
    (36, "Zephanja", 3, "hebrew", ["zephanja", "zephaniah"]),
    (37, "Haggai", 2, "hebrew", ["haggai"]),
    (38, "Sacharja", 14, "hebrew", ["sacharja", "zechariah"]),
    (39, "Maleachi", 4, "hebrew", ["maleachi", "malachi"]),
    (40, "Matthäus", 28, "greek", ["matthäus", "matthaeus", "matthew", "evangelium nach matthäus"]),
    (41, "Markus", 16, "greek", ["markus", "mark", "evangelium nach markus"]),
    (42, "Lukas", 24, "greek", ["lukas", "luke", "evangelium nach lukas"]),
    (43, "Johannes", 21, "greek", ["johannes", "john", "evangelium nach johannes"]),
    (44, "Apostelgeschichte", 28, "greek", ["apostelgeschichte", "acts"]),
    (45, "Römer", 16, "greek", ["römer", "romans"]),
    (46, "1. Korinther", 16, "greek", ["1. korinther", "1 corinthians"]),
    (47, "2. Korinther", 13, "greek", ["2. korinther", "2 corinthians"]),
    (48, "Galater", 6, "greek", ["galater", "galatians"]),
    (49, "Epheser", 6, "greek", ["epheser", "ephesians"]),
    (50, "Philipper", 4, "greek", ["philipper", "philippians"]),
    (51, "Kolosser", 4, "greek", ["kolosser", "colossians"]),
    (52, "1. Thessalonicher", 5, "greek", ["1. thessalonicher", "1 thessalonians"]),
    (53, "2. Thessalonicher", 3, "greek", ["2. thessalonicher", "2 thessalonians"]),
    (54, "1. Timotheus", 6, "greek", ["1. timotheus", "1 timothy"]),
    (55, "2. Timotheus", 4, "greek", ["2. timotheus", "2 timothy"]),
    (56, "Titus", 3, "greek", ["titus"]),
    (57, "Philemon", 1, "greek", ["philemon"]),
    (58, "Hebräer", 13, "greek", ["hebräer", "hebrews"]),
    (59, "Jakobus", 5, "greek", ["jakobus", "james"]),
    (60, "1. Petrus", 5, "greek", ["1. petrus", "1 peter"]),
    (61, "2. Petrus", 3, "greek", ["2. petrus", "2 peter"]),
    (62, "1. Johannes", 5, "greek", ["1. johannes", "1 john"]),
    (63, "2. Johannes", 1, "greek", ["2. johannes", "2 john"]),
    (64, "3. Johannes", 1, "greek", ["3. johannes", "3 john"]),
    (65, "Judas", 1, "greek", ["judas", "jude"]),
    (66, "Offenbarung", 22, "greek", ["offenbarung", "revelation"]),
]
BOOK_BY_NUMBER = {number: (title, chapters, testament, aliases) for number, title, chapters, testament, aliases in BIBLE_BOOKS_DE}


def _normalized(value: object) -> str:
    return re.sub(r"[^a-z0-9äöüß]+", " ", _plain(value).lower()).strip()


def _book_from_doc(doc: dict) -> int | None:
    direct = int(doc.get("chapter_number") or 0)
    if direct in BOOK_BY_NUMBER:
        return direct
    label = _normalized(" ".join(str(doc.get(key) or "") for key in ("toc_title", "title", "subtitle")))
    for number, _title, _chapters, _testament, aliases in BIBLE_BOOKS_DE:
        if any(re.search(rf"(?:^|\s){re.escape(alias)}(?:\s|$)", label) for alias in aliases):
            return number
    section = int(doc.get("section_number") or 0)
    return section if section in BOOK_BY_NUMBER else None


def _chapter_from_doc(doc: dict, book_number: int) -> int | None:
    label = _plain(" ".join(str(doc.get(key) or "") for key in ("title", "toc_title", "subtitle"))).replace("\xa0", " ")
    match = re.search(r"(?:Kapitel|Chapter)\s*(\d{1,3})", label, re.I)
    if match:
        value = int(match.group(1))
        return value if 1 <= value <= BOOK_BY_NUMBER[book_number][1] else None
    if BOOK_BY_NUMBER[book_number][1] == 1 and re.search(r"Studienanmerkungen|Study Notes", label, re.I):
        return 1
    return None


def _document_score(doc: dict) -> tuple[int, int, int, int]:
    label = " ".join(_plain(doc.get(key)) for key in ("class_name", "title", "toc_title", "subtitle"))
    bad = bool(re.search(r"\b(Einführung|Übersicht|Anhang|Vorwort|Abkürzungen|Introduction|Overview|Appendix|Foreword)\b", label, re.I))
    scripture = bool(re.search(r"bible|chapter|scripture", _plain(doc.get("class_name")), re.I))
    text = _plain(doc.get("content_text"))
    verse_like = len(re.findall(r"(?:^|\s)\d{1,3}(?:\s|$)", text[:8000]))
    return (0 if bad else 1, 1 if scripture else 0, min(verse_like, 20), int(doc.get("text_length") or 0))

def bible_library(language_index: int | None = None, database: Database = DB) -> list[dict]:
    clauses = [_bible_clause()]
    params: list[object] = []
    if language_index is not None:
        clauses.append("language_index=?")
        params.append(int(language_index))
    return database.rows(
        "SELECT p.*,(SELECT COUNT(*) FROM documents d WHERE d.publication_id=p.id) AS document_count "
        "FROM publications p WHERE " + " AND ".join(clauses) + " ORDER BY favorite DESC,title",
        params,
    )


def _publication_source(publication_id: str, database: Database = DB) -> tuple[dict, sqlite3.Connection]:
    rows = database.rows(
        "SELECT id,title,key_symbol,language_index,year,issue_tag,db_path FROM publications WHERE id=?",
        (publication_id,),
    )
    if not rows:
        raise ValueError("Bibelübersetzung wurde nicht gefunden.")
    publication = rows[0]
    source_path = Path(str(publication.get("db_path") or ""))
    if not source_path.is_file():
        raise FileNotFoundError("Die Quelldatenbank der Bibel fehlt.")
    connection = sqlite3.connect(source_path)
    connection.row_factory = sqlite3.Row
    return publication, connection


def _source_table_exists(connection: sqlite3.Connection, name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _decode_bible_blob(blob: object, publication: dict) -> str:
    return decrypt_html(
        blob,
        int(publication.get("language_index") or 0),
        str(publication.get("key_symbol") or ""),
        int(publication.get("year") or 0),
        int(publication.get("issue_tag") or 0),
    )


def bible_navigation(publication_id: str, database: Database = DB) -> dict:
    publication, source = _publication_source(publication_id, database)
    try:
        if not _source_table_exists(source, "BibleBook") or not _source_table_exists(source, "BibleChapter"):
            raise ValueError("Diese Publikation enthält keine native Bibelstruktur.")
        book_rows = source.execute(
            "SELECT BibleBookId,BookDisplayTitle,ChapterDisplayTitle FROM BibleBook ORDER BY BibleBookId"
        ).fetchall()
        chapter_rows = source.execute(
            "SELECT BibleChapterId,BookNumber,ChapterNumber,FirstVerseId,LastVerseId FROM BibleChapter ORDER BY BookNumber,ChapterNumber"
        ).fetchall()
        chapters_by_book: dict[int, list[dict]] = {}
        for row in chapter_rows:
            number = int(row["BookNumber"] or 0)
            chapter = int(row["ChapterNumber"] or 0)
            if number < 1 or chapter < 1:
                continue
            chapters_by_book.setdefault(number, []).append({
                "id": int(row["BibleChapterId"]),
                "book_number": number,
                "chapter_number": chapter,
                "label": str(chapter),
                "available": True,
                "first_verse_id": row["FirstVerseId"],
                "last_verse_id": row["LastVerseId"],
            })
        books = []
        for row in book_rows:
            number = int(row["BibleBookId"] or 0)
            if number < 1:
                continue
            fallback = BOOK_BY_NUMBER.get(number, (f"Buch {number}", 0, "greek" if number >= 40 else "hebrew", []))
            title = _plain(row["ChapterDisplayTitle"] or row["BookDisplayTitle"] or fallback[0])
            chapters = chapters_by_book.get(number, [])
            books.append({
                "book_number": number,
                "title": title,
                "display_title": _plain(row["BookDisplayTitle"] or title),
                "testament": "hebrew" if number <= 39 else "greek",
                "chapter_count": len(chapters),
                "chapters": chapters,
            })
        return {
            "publication_id": publication_id,
            "source": "native-bible-tables",
            "book_count": len(books),
            "chapter_count": sum(len(item["chapters"]) for item in books),
            "books": books,
        }
    finally:
        source.close()



def bible_overview(publication_id: str, database: Database = DB) -> dict:
    publication, source = _publication_source(publication_id, database)
    try:
        navigation = bible_navigation(publication_id, database)
        document_rows = database.rows(
            "SELECT id,source_document_id,title,toc_title,subtitle FROM documents WHERE publication_id=?",
            (publication_id,),
        )
        documents_by_source = {
            int(row["source_document_id"]): row
            for row in document_rows
            if row.get("source_document_id") is not None
        }
        media_by_document: dict[int, list[dict]] = {}
        for row in database.rows(
            "SELECT source_media_id,file_path,mime_type,label,caption,document_source_id FROM media "
            "WHERE publication_id=? ORDER BY source_media_id",
            (publication_id,),
        ):
            if row.get("document_source_id") is None:
                continue
            media_by_document.setdefault(int(row["document_source_id"]), []).append(row)

        encoded_publication = urllib.parse.quote(str(publication_id), safe="")

        def media_url(file_path: object) -> str:
            value = str(file_path or "").strip().lstrip("/")
            return f"/content/{encoded_publication}/{urllib.parse.quote(value, safe='/')}" if value else ""

        def document_media(source_document_id: int | None) -> tuple[str, bool, list[dict]]:
            rows = media_by_document.get(int(source_document_id or -1), [])
            image = next((row for row in rows if str(row.get("mime_type") or "").startswith("image/")), None)
            has_video = any(str(row.get("mime_type") or "").startswith("video/") for row in rows)
            return media_url(image.get("file_path") if image else ""), has_video, rows

        view_row = source.execute(
            "SELECT PublicationViewId FROM PublicationView WHERE Symbol='jwpub' ORDER BY PublicationViewId LIMIT 1"
        ).fetchone()
        sections: list[dict] = []
        if view_row and _source_table_exists(source, "PublicationViewItem"):
            view_id = int(view_row["PublicationViewId"])
            item_rows = [dict(row) for row in source.execute(
                "SELECT PublicationViewItemId,ParentPublicationViewItemId,Title,DefaultDocumentId "
                "FROM PublicationViewItem WHERE PublicationViewId=? ORDER BY PublicationViewItemId",
                (view_id,),
            ).fetchall()]
            item_documents: dict[int, list[int]] = {}
            if _source_table_exists(source, "PublicationViewItemDocument"):
                for row in source.execute(
                    "SELECT PublicationViewItemId,DocumentId FROM PublicationViewItemDocument ORDER BY PublicationViewItemDocumentId"
                ).fetchall():
                    item_documents.setdefault(int(row["PublicationViewItemId"]), []).append(int(row["DocumentId"]))
            children: dict[int, list[dict]] = {}
            for row in item_rows:
                children.setdefault(int(row.get("ParentPublicationViewItemId") or -1), []).append(row)

            def item_payload(row: dict) -> dict:
                item_id = int(row["PublicationViewItemId"])
                default_id = int(row.get("DefaultDocumentId") or -1)
                source_document_id = default_id if default_id >= 0 else None
                if source_document_id is None and item_documents.get(item_id):
                    source_document_id = int(item_documents[item_id][0])
                main_document = documents_by_source.get(int(source_document_id)) if source_document_id is not None else None
                thumbnail_url, has_video, media_rows = document_media(source_document_id)
                nested = [item_payload(child) for child in children.get(item_id, [])]
                return {
                    "item_id": item_id,
                    "title": _plain(row.get("Title")),
                    "source_document_id": source_document_id,
                    "document_id": int(main_document["id"]) if main_document else None,
                    "thumbnail_url": thumbnail_url,
                    "has_video": has_video,
                    "media_count": len(media_rows),
                    "kind": "video" if has_video else ("document" if main_document else "group"),
                    "children": nested,
                }

            key_map = {
                "EINFÜHRUNG": "introduction",
                "BÜCHER": "books",
                "INDEX": "index",
                "ANHANG A": "appendix_a",
                "ANHANG B": "appendix_b",
                "ANHANG C": "appendix_c",
            }
            for root in children.get(-1, []):
                title = _plain(root.get("Title")).upper()
                key = key_map.get(title)
                if not key:
                    continue
                sections.append({
                    "key": key,
                    "title": title,
                    "items": [item_payload(child) for child in children.get(int(root["PublicationViewItemId"]), [])],
                })

        nav_by_number = {int(item["book_number"]): item for item in navigation.get("books", [])}
        books: list[dict] = []
        if _source_table_exists(source, "BibleBook"):
            for row in source.execute(
                "SELECT BibleBookId,BookDocumentId,IntroDocumentId,OverviewDocumentId,OutlineDocumentId,"
                "BookDisplayTitle,ChapterDisplayTitle FROM BibleBook ORDER BY BibleBookId"
            ).fetchall():
                number = int(row["BibleBookId"] or 0)
                if number < 1:
                    continue
                nav = nav_by_number.get(number, {})
                intro_source_id = int(row["IntroDocumentId"]) if row["IntroDocumentId"] is not None else None
                overview_source_id = int(row["OverviewDocumentId"]) if row["OverviewDocumentId"] is not None else None
                outline_source_id = int(row["OutlineDocumentId"]) if row["OutlineDocumentId"] is not None else None
                book_source_id = int(row["BookDocumentId"]) if row["BookDocumentId"] is not None else None
                intro_image, intro_video, _ = document_media(intro_source_id)

                def main_id(source_id: int | None) -> int | None:
                    mapped = documents_by_source.get(int(source_id)) if source_id is not None else None
                    return int(mapped["id"]) if mapped else None

                books.append({
                    "book_number": number,
                    "title": _plain(row["ChapterDisplayTitle"] or row["BookDisplayTitle"] or nav.get("title") or f"Buch {number}"),
                    "display_title": _plain(row["BookDisplayTitle"] or row["ChapterDisplayTitle"] or nav.get("title") or f"Buch {number}"),
                    "testament": "hebrew" if number <= 39 else "greek",
                    "chapter_count": int(nav.get("chapter_count") or len(nav.get("chapters") or [])),
                    "chapters": nav.get("chapters") or [],
                    "book_document_id": main_id(book_source_id),
                    "intro_document_id": main_id(intro_source_id),
                    "overview_document_id": main_id(overview_source_id),
                    "outline_document_id": main_id(outline_source_id),
                    "intro_thumbnail_url": intro_image,
                    "intro_has_video": intro_video,
                })

        expected = ["introduction", "books", "index", "appendix_a", "appendix_b", "appendix_c"]
        section_map = {item["key"]: item for item in sections}
        labels = {
            "introduction": "EINFÜHRUNG", "books": "BÜCHER", "index": "INDEX",
            "appendix_a": "ANHANG A", "appendix_b": "ANHANG B", "appendix_c": "ANHANG C",
        }
        sections = [section_map.get(key, {"key": key, "title": labels[key], "items": []}) for key in expected]
        return {
            "publication_id": publication_id,
            "title": publication.get("title") or "Studienbibel",
            "sections": sections,
            "books": books,
        }
    finally:
        source.close()

def bible_chapter(publication_id: str, book_number: int, chapter_number: int, database: Database = DB) -> dict:
    publication, source = _publication_source(publication_id, database)
    try:
        book = source.execute(
            "SELECT BibleBookId,BookDisplayTitle,ChapterDisplayTitle FROM BibleBook WHERE BibleBookId=?",
            (int(book_number),),
        ).fetchone()
        chapter = source.execute(
            "SELECT BibleChapterId,BookNumber,ChapterNumber,Content,PreContent,PostContent,FirstVerseId,LastVerseId FROM BibleChapter WHERE BookNumber=? AND ChapterNumber=?",
            (int(book_number), int(chapter_number)),
        ).fetchone()
        if not book or not chapter:
            raise ValueError("Bibelkapitel wurde nicht gefunden.")
        pre_html = _decode_bible_blob(chapter["PreContent"], publication) if chapter["PreContent"] else ""
        content_html = _decode_bible_blob(chapter["Content"], publication) if chapter["Content"] else ""
        post_html = _decode_bible_blob(chapter["PostContent"], publication) if chapter["PostContent"] else ""
        verses = []
        if _source_table_exists(source, "BibleVerse") and chapter["FirstVerseId"] is not None and chapter["LastVerseId"] is not None:
            rows = source.execute(
                "SELECT BibleVerseId,Label,Content,BeginParagraphOrdinal,EndParagraphOrdinal FROM BibleVerse WHERE BibleVerseId BETWEEN ? AND ? ORDER BY BibleVerseId",
                (int(chapter["FirstVerseId"]), int(chapter["LastVerseId"])),
            ).fetchall()
            for verse in rows:
                verses.append({
                    "id": int(verse["BibleVerseId"]),
                    "label": _plain(verse["Label"]),
                    "content_html": _decode_bible_blob(verse["Content"], publication) if verse["Content"] else "",
                    "begin_paragraph": verse["BeginParagraphOrdinal"],
                    "end_paragraph": verse["EndParagraphOrdinal"],
                })
        book_title = _plain(book["ChapterDisplayTitle"] or book["BookDisplayTitle"] or f"Buch {book_number}")
        return {
            "publication": publication,
            "book_number": int(book_number),
            "book_title": book_title,
            "chapter_number": int(chapter_number),
            "chapter_id": int(chapter["BibleChapterId"]),
            "title": f"{book_title} {int(chapter_number)}",
            "pre_content_html": pre_html,
            "content_html": content_html,
            "post_content_html": post_html,
            "verses": verses,
        }
    finally:
        source.close()



def _ensure_bible_chapter_document(chapter: dict, database: Database = DB) -> int:
    publication = chapter["publication"]
    publication_id = str(publication["id"])
    book_number = int(chapter["book_number"])
    chapter_number = int(chapter["chapter_number"])
    source_document_id = -(book_number * 1000 + chapter_number)
    paragraphs = []
    plain_parts = []
    for index, verse in enumerate(chapter.get("verses") or [], start=1):
        label = _plain(verse.get("label")) or str(index)
        content = str(verse.get("content_html") or "")
        # Native BibleVerse content can already begin with the verse label. Remove only
        # that leading visual label because LiMaD renders one canonical verse number.
        escaped_label = re.escape(label)
        content = re.sub(rf"^\s*(?:<[^>]+>\s*)*(?:{escaped_label})(?:\s|&nbsp;|&#160;)*(?:</[^>]+>\s*)?", "", content, count=1, flags=re.I)
        content = re.sub(rf"^\s*<(?:sup|span)[^>]*>\s*{escaped_label}\s*</(?:sup|span)>\s*", "", content, count=1, flags=re.I)
        block_id = int(verse.get("id") or index)
        paragraphs.append(
            f'<p class="bible-verse" id="p{block_id}" data-pid="{block_id}" data-verse-id="{block_id}" data-verse="{html.escape(label)}">'
            f'<sup class="verse-number">{html.escape(label)}</sup><span class="verse-text">{content}</span></p>'
        )
        plain_parts.append(f"{label} {_plain(content)}")
    body = "".join(paragraphs)
    if not body:
        body = str(chapter.get("content_html") or "")
    content_html = (
        str(chapter.get("pre_content_html") or "")
        + f'<section class="bible-native-chapter" data-book="{book_number}" data-chapter="{chapter_number}">{body}</section>'
        + str(chapter.get("post_content_html") or "")
    )
    content_text = "\n".join(plain_parts) or _plain(content_html)
    existing = database.rows(
        "SELECT id FROM documents WHERE publication_id=? AND source_document_id=?",
        (publication_id, source_document_id),
    )
    if existing:
        document_id = int(existing[0]["id"])
        database.execute(
            "UPDATE documents SET meps_document_id=?,chapter_number=?,section_number=?,title=?,toc_title=?,subtitle=?,class_name=?,content_html=?,content_text=?,paragraph_count=?,sort_order=? WHERE id=?",
            (
                None, chapter_number, book_number, chapter["title"], chapter["title"], "", "bible-native",
                content_html, content_text, len(chapter.get("verses") or []), book_number * 1000 + chapter_number, document_id,
            ),
        )
    else:
        database.execute(
            "INSERT INTO documents(publication_id,source_document_id,meps_document_id,chapter_number,section_number,title,toc_title,subtitle,class_name,content_html,content_text,paragraph_count,sort_order) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                publication_id, source_document_id, None, chapter_number, book_number, chapter["title"], chapter["title"], "",
                "bible-native", content_html, content_text, len(chapter.get("verses") or []), book_number * 1000 + chapter_number,
            ),
        )
        document_id = int(database.scalar(
            "SELECT id FROM documents WHERE publication_id=? AND source_document_id=?",
            (publication_id, source_document_id),
        ))
    database.execute("DELETE FROM documents_fts WHERE document_id=?", (document_id,))
    database.execute(
        "INSERT INTO documents_fts(title,content_text,publication_id,document_id) VALUES(?,?,?,?)",
        (chapter["title"], content_text, publication_id, document_id),
    )
    return document_id

BIBLE_READER_CSS = r"""
body{max-width:880px;padding:44px 64px 130px;font-family:"Noto Serif","Source Serif 4","Liberation Serif",serif;font-size:21px;font-weight:400;line-height:1.72;letter-spacing:.002em;text-rendering:optimizeLegibility;-webkit-font-smoothing:antialiased}html[data-theme="dark"] .verse-number{color:#c7a9f6}html[data-theme="dark"] [data-pid]:hover,html[data-theme="dark"] p[id^="p"]:hover{background:rgba(190,158,239,.09)}html[data-theme="dark"] .bible-verse.limad-selected-verse{background:rgba(190,158,239,.16);box-shadow:inset 3px 0 0 #b99aef}.limad-bible-verse-menu{position:fixed;z-index:90;display:flex;gap:4px;align-items:center;padding:7px;background:rgba(25,18,38,.95);color:#fff;border:1px solid rgba(180,126,255,.35);border-radius:12px;box-shadow:0 18px 50px rgba(20,10,38,.32);backdrop-filter:blur(18px)}.limad-bible-verse-menu button{border:0;border-radius:8px;background:transparent;color:#fff;padding:7px 9px;cursor:pointer;font:600 12px Inter,system-ui,sans-serif;white-space:nowrap}.limad-bible-verse-menu button:hover{background:rgba(154,77,255,.28)}.limad-bible-verse-menu .colors{display:flex;gap:4px;padding-right:4px;border-right:1px solid rgba(255,255,255,.15)}.limad-bible-verse-menu .colors button{width:24px;height:24px;padding:0;border:2px solid rgba(255,255,255,.55);border-radius:50%;font-size:0}.limad-bible-verse-menu .colors button[data-color="0"]{background:#ffe15c}.limad-bible-verse-menu .colors button[data-color="1"]{background:#76dca8}.limad-bible-verse-menu .colors button[data-color="2"]{background:#70b1ff}.limad-bible-verse-menu .colors button[data-color="3"]{background:#f695c1}.limad-bible-verse-menu .colors button[data-color="4"]{background:#b58ff2}.limad-bible-verse-menu .colors button[data-color="5"]{background:#ffa65b}[data-pid],p[id^="p"]{border-radius:8px;padding:.12em .25em;margin-left:-.25em;transition:background .15s ease}[data-pid]:hover,p[id^="p"]:hover{background:rgba(115,87,215,.055)}.bible-verse{cursor:pointer}.bible-verse.limad-selected-verse{background:rgba(145,86,235,.14);box-shadow:inset 3px 0 0 rgba(145,86,235,.85)}.verse-number{cursor:pointer;color:#5279b6;font-family:"Noto Sans",system-ui,sans-serif;font-weight:750}.bible-verse{margin:.2em 0}.bible-native-chapter{max-width:76ch;margin:auto}@media(max-width:700px){body{padding:28px 24px 100px;font-size:20px}.limad-bible-verse-menu{max-width:calc(100vw - 16px);overflow-x:auto}}
"""

BIBLE_READER_SCRIPT = r"""
(function(){
 const reference=__REFERENCE__,documentId=Number(__DOCUMENT_ID__);
 let selectionSnapshot=null;
 function closeMenu(){document.querySelectorAll('.limad-bible-verse-menu').forEach(node=>node.remove())}
 function verseNode(value){return value?.closest?.('.bible-verse,[data-verse][data-pid],p[data-verse]')||null}
 function verseMeta(node){
  const raw=String(node?.dataset?.pid||(node?.id||'').replace(/^p/,''));
  const verseId=String(node?.dataset?.verseId||raw);
  const verseLabel=String(node?.dataset?.verse||node?.querySelector?.('.verse-number')?.textContent||'').trim();
  const verseNumber=Number((verseLabel.match(/\d{1,3}/)||[])[0]||0);
  const text=String(node?.querySelector?.('.verse-text')?.innerText||node?.innerText||'').replace(/^\s*\d{1,3}\s*/, '').trim();
  return {node,raw,verseId,verseLabel,verseNumber,text};
 }
 function selectionData(){
  const sel=getSelection();if(!sel||sel.isCollapsed||!sel.rangeCount)return null;
  const text=sel.toString().trim();if(!text)return null;
  const range=sel.getRangeAt(0);
  const startElement=range.startContainer.nodeType===1?range.startContainer:range.startContainer.parentElement;
  const endElement=range.endContainer.nodeType===1?range.endContainer:range.endContainer.parentElement;
  const node=verseNode(startElement)||startElement?.closest('[data-pid],p[id^="p"]');
  if(!node||node!==(verseNode(endElement)||endElement?.closest('[data-pid],p[id^="p"]')))return null;
  const meta=verseMeta(node);
  const tokens=[];const walker=document.createTreeWalker(node,NodeFilter.SHOW_TEXT,{acceptNode:n=>n.parentElement?.closest('.verse-number,script,style')?NodeFilter.FILTER_REJECT:NodeFilter.FILTER_ACCEPT});let item,index=0;
  while((item=walker.nextNode())){for(const match of item.data.matchAll(/\S+/g)){tokens.push({node:item,start:match.index,end:match.index+match[0].length,index:index++})}}
  let startToken=null,endToken=null;
  for(const token of tokens){const tokenRange=document.createRange();tokenRange.setStart(token.node,token.start);tokenRange.setEnd(token.node,token.end);if(range.compareBoundaryPoints(Range.END_TO_START,tokenRange)<0&&range.compareBoundaryPoints(Range.START_TO_END,tokenRange)>0){if(startToken===null)startToken=token.index;endToken=token.index}}
  const rect=range.getBoundingClientRect();
  return {...meta,text,startToken,endToken,rect};
 }
 function versePayload(data){
  const suffix=data.verseLabel||data.verseNumber||'';
  return {documentId,blockIdentifier:Number(data.raw)||0,verseId:Number(data.verseId||data.raw)||0,verseNumber:Number(data.verseNumber)||0,text:data.text,reference:reference+(suffix?':'+suffix:'')}
 }
 function postAction(action,data,colorIndex){
  if(action==='highlight'){parent.postMessage({type:'limad-mark',...versePayload(data),startToken:data.startToken,endToken:data.endToken,colorIndex},location.origin);return}
  parent.postMessage({type:'limad-bible-verse-action',action,...versePayload(data),colorIndex},location.origin)
 }
 function menu(data){
  closeMenu();selectionSnapshot=data;
  const panel=document.createElement('div');panel.className='limad-bible-verse-menu';
  panel.innerHTML='<span class="colors"><button data-color="0" title="Gelb">Gelb</button><button data-color="1" title="Grün">Grün</button><button data-color="2" title="Blau">Blau</button><button data-color="3" title="Rosa">Rosa</button></span><button data-action="bookmark">Lesezeichen</button><button data-action="note">Notiz</button><button data-action="copy">Kopieren</button><button data-action="share">Teilen</button>';
  document.body.append(panel);const x=data.rect.left+data.rect.width/2-panel.offsetWidth/2,y=data.rect.top-panel.offsetHeight-10;panel.style.left=Math.max(8,Math.min(x,innerWidth-panel.offsetWidth-8))+'px';panel.style.top=Math.max(8,Math.min(y,innerHeight-panel.offsetHeight-8))+'px';
  panel.querySelectorAll('[data-color]').forEach(button=>button.onclick=()=>{postAction('highlight',selectionSnapshot,Number(button.dataset.color));closeMenu();getSelection()?.removeAllRanges()});
  panel.querySelectorAll('[data-action]').forEach(button=>button.onclick=()=>{postAction(button.dataset.action,selectionSnapshot);closeMenu();getSelection()?.removeAllRanges()});
 }
 function showForSelection(){setTimeout(()=>{const data=selectionData();if(data)menu(data);else closeMenu()},0)}
 document.addEventListener('click',event=>{
  if(event.target.closest('.limad-bible-verse-menu'))return;
  const selected=getSelection();if(selected&&!selected.isCollapsed)return;
  const node=verseNode(event.target);if(!node)return;
  const data=verseMeta(node);if(!data.raw)return;
  document.querySelectorAll('.bible-verse.limad-selected-verse').forEach(item=>item.classList.remove('limad-selected-verse'));
  node.classList.add('limad-selected-verse');
  parent.postMessage({type:'limad-bible-verse-select',...versePayload(data)},location.origin);
 },true);
 document.addEventListener('mouseup',showForSelection,true);
 document.addEventListener('touchend',showForSelection,true);
 document.addEventListener('selectionchange',()=>{const sel=getSelection();if(!sel||sel.isCollapsed)closeMenu()});
 document.addEventListener('pointerdown',event=>{if(!event.target.closest('.limad-bible-verse-menu'))closeMenu()},true);
 document.addEventListener('keydown',event=>{if(event.key==='Escape')closeMenu()});
 document.addEventListener('scroll',closeMenu,{passive:true});
 requestAnimationFrame(()=>{const node=document.querySelector('.bible-verse[data-pid]');if(!node)return;const data=verseMeta(node);if(!data.raw)return;node.classList.add('limad-selected-verse');parent.postMessage({type:'limad-bible-verse-select',...versePayload(data),automatic:true},location.origin)});
})();
"""


def render_bible_chapter(publication_id: str, book_number: int, chapter_number: int, database: Database = DB) -> str:
    chapter = bible_chapter(publication_id, book_number, chapter_number, database)
    document_id = _ensure_bible_chapter_document(chapter, database)
    html = render_document(document_id, database)
    html = html.replace("<body>", '<body data-limad-bible-reader="1">', 1)
    reference = f"{chapter.get('book_title') or 'Bibel'} {int(chapter_number)}"
    script = BIBLE_READER_SCRIPT.replace("__REFERENCE__", json.dumps(reference, ensure_ascii=False)).replace("__DOCUMENT_ID__", str(int(document_id)))
    return html.replace("</head>", f"<style>{BIBLE_READER_CSS}</style></head>", 1).replace("</body>", f"<script>{script}</script></body>", 1)

def bible_compare(language_index: int, book_number: int, chapter_number: int, database: Database = DB) -> list[dict]:
    result: list[dict] = []
    for publication in bible_library(language_index, database):
        try:
            result.append(bible_chapter(publication["id"], book_number, chapter_number, database))
        except ValueError:
            continue
    return result


def bible_search(query: str, language_index: int | None = None, publication_id: str | None = None, limit: int = 100, database: Database = DB) -> list[dict]:
    query = query.strip()
    if len(query) < 2:
        return []
    where = ["p.id=f.publication_id", _bible_clause()]
    params: list[object] = [query]
    if language_index is not None:
        where.append("p.language_index=?")
        params.append(int(language_index))
    if publication_id:
        where.append("p.id=?")
        params.append(publication_id)
    params.append(min(max(int(limit), 1), 500))
    return database.rows(
        "SELECT f.document_id,f.title,p.id AS publication_id,p.title AS publication_title,p.key_symbol,p.language_index,"
        "snippet(documents_fts,1,'<mark>','</mark>',' … ',24) AS snippet,d.chapter_number,d.section_number "
        "FROM documents_fts f JOIN publications p JOIN documents d ON d.id=f.document_id "
        "WHERE documents_fts MATCH ? AND " + " AND ".join(where) + " ORDER BY rank LIMIT ?",
        params,
    )


def set_preference(language_index: int, publication_id: str, last_document_id: int | None = None, database: Database = DB) -> dict:
    database.execute(
        "INSERT INTO bible_preferences(language_index,publication_id,last_document_id,updated_at) VALUES(?,?,?,?) "
        "ON CONFLICT(language_index) DO UPDATE SET publication_id=excluded.publication_id,last_document_id=excluded.last_document_id,updated_at=excluded.updated_at",
        (int(language_index), publication_id, last_document_id, utc_now()),
    )
    return {"language_index": int(language_index), "publication_id": publication_id, "last_document_id": last_document_id}


def save_view_state(language_index: int, primary_publication_id: str, compare_publication_id: str | None, book_number: int | None, chapter_number: int | None, split_enabled: bool, database: Database = DB) -> dict:
    database.execute(
        "INSERT INTO bible_view_state(language_index,primary_publication_id,compare_publication_id,book_number,chapter_number,split_enabled,updated_at) "
        "VALUES(?,?,?,?,?,?,?) ON CONFLICT(language_index) DO UPDATE SET primary_publication_id=excluded.primary_publication_id,"
        "compare_publication_id=excluded.compare_publication_id,book_number=excluded.book_number,chapter_number=excluded.chapter_number,"
        "split_enabled=excluded.split_enabled,updated_at=excluded.updated_at",
        (int(language_index), primary_publication_id, compare_publication_id, book_number, chapter_number, 1 if split_enabled else 0, utc_now()),
    )
    return view_state(language_index, database)


def view_state(language_index: int, database: Database = DB) -> dict:
    rows = database.rows("SELECT * FROM bible_view_state WHERE language_index=?", (int(language_index),))
    return rows[0] if rows else {
        "language_index": int(language_index),
        "primary_publication_id": None,
        "compare_publication_id": None,
        "book_number": 1,
        "chapter_number": 1,
        "split_enabled": 0,
    }


def bible_chapter_document_id(publication_id: str, book_number: int, chapter_number: int, database: Database = DB) -> int:
    chapter = bible_chapter(publication_id, book_number, chapter_number, database)
    return _ensure_bible_chapter_document(chapter, database)

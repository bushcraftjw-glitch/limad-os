from __future__ import annotations
import gzip
import json
from .database import DB, Database
from .resources import SEED_ROOT
from .utils import utc_now


def ensure_seed(database: Database = DB) -> dict:
    loaded = {"languages": 0, "catalog": 0}
    if database.scalar("SELECT COUNT(*) FROM languages") == 0:
        path = SEED_ROOT / "languages.json.gz"
        if path.is_file():
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                payload = json.load(stream)
            with database.transaction() as con:
                for item in payload.get("languages", []):
                    con.execute('''INSERT OR REPLACE INTO languages(id,symbol,english_name,vernacular_name,iso2,iso3,ietf,is_sign,script_id,direction,source)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?)''', (item.get("LanguageId"),item.get("Symbol") or "",item.get("EnglishName") or "",item.get("VernacularName") or "",item.get("IsoAlpha2Code") or "",item.get("IsoAlpha3Code") or "",item.get("PrimaryIetfCode") or "",int(item.get("IsSignLanguage") or 0),item.get("ScriptId"),item.get("Direction") or "ltr","seed"))
            loaded["languages"] = len(payload.get("languages", []))
    if database.scalar("SELECT COUNT(*) FROM catalog_publications") == 0:
        path = SEED_ROOT / "catalog.json.gz"
        if path.is_file():
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                payload = json.load(stream)
            with database.transaction() as con:
                for item in payload.get("publications", []):
                    con.execute('''INSERT OR REPLACE INTO catalog_publications(
                        catalog_id,key_symbol,symbol,language_index,language_symbol,title,short_title,year,issue_tag,publication_type_id,asset_id,signature,
                        size,expanded_size,mime_type,cataloged_on,last_updated,last_modified,generally_available_date,image_fragment,image_width,image_height,image_mime,raw_json
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                        item.get("CatalogId"),item.get("KeySymbol") or item.get("Symbol") or "",item.get("Symbol") or "",item.get("MepsLanguageId"),item.get("LanguageSymbol") or "",
                        item.get("Title") or "",item.get("ShortTitle") or "",item.get("Year") or 0,item.get("IssueTagNumber") or 0,item.get("PublicationTypeId") or 0,item.get("AssetId"),item.get("Signature") or "",
                        item.get("Size") or 0,item.get("ExpandedSize") or 0,item.get("MimeType") or "",item.get("CatalogedOn") or "",item.get("LastUpdated") or "",item.get("LastModified") or "",item.get("GenerallyAvailableDate") or "",
                        item.get("ImageFragment") or "",item.get("ImageWidth") or 0,item.get("ImageHeight") or 0,item.get("ImageMime") or "",json.dumps(item,ensure_ascii=False)
                    ))
                revision = payload.get("revision") or {}
                con.execute("INSERT OR REPLACE INTO catalog_state(key,value,updated_at) VALUES('seed_revision',?,?)", (json.dumps(revision,ensure_ascii=False),utc_now()))
            loaded["catalog"] = len(payload.get("publications", []))
    with database.transaction() as con:
        con.execute("""UPDATE publications SET language_symbol=COALESCE((SELECT symbol FROM languages WHERE languages.id=publications.language_index),'') WHERE COALESCE(language_symbol,'')=''""")
    return loaded

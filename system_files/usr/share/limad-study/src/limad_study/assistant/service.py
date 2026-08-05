from __future__ import annotations
import json
import os
import secrets
import sqlite3
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from ..config import PATHS
from ..utils import utc_now

DB_PATH = PATHS.data / "assistant.db"
KEY_FILE = PATHS.config / "assistant-gemini.key"
SERVICE_NAME = "LiMaD Study Gemini"
DEFAULT_MODEL = "gemini-2.5-flash"

SYSTEM_INSTRUCTION = """Du bist der LiMaD Study KI-Assistent. Antworte auf Deutsch, sachlich, klar und hilfreich. Du darfst in dieser Vorschau keine freie Internetsuche durchführen. Verwende nur den Text, den der Benutzer im Chat eingibt, und ausdrücklich beigefügten Study-Kontext. Behaupte niemals, eine JW.org- oder WOL-Quelle geprüft zu haben, wenn keine Quelle als Kontext geliefert wurde. Erfinde keine Quellen, Zitate, Veröffentlichungen oder Bibelstellen. Sage bei fehlender Grundlage klar, dass eine Quellenrecherche in dieser Vorschau noch nicht aktiviert ist. Unterstütze besonders beim Gliedern, Formulieren, Kürzen und Überarbeiten von Dispositionen und Vorträgen."""

def _connect():
    con=sqlite3.connect(DB_PATH)
    con.row_factory=sqlite3.Row
    con.executescript("""
    PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS projects(
      id TEXT PRIMARY KEY,title TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS messages(
      id TEXT PRIMARY KEY,project_id TEXT NOT NULL,role TEXT NOT NULL,content TEXT NOT NULL,
      context_json TEXT NOT NULL DEFAULT '[]',created_at TEXT NOT NULL,
      FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    """)
    return con

def _setting(key,default=""):
    with _connect() as con:
        row=con.execute("SELECT value FROM settings WHERE key=?",(key,)).fetchone()
        return row[0] if row else default

def _set_setting(key,value):
    with _connect() as con:
        con.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(key,str(value)))

def _secret_tool(args,input_text=None):
    try:
        return subprocess.run(["secret-tool",*args],input=input_text,text=True,capture_output=True,timeout=8,check=False)
    except (OSError, subprocess.SubprocessError):
        return None

def _get_api_key():
    result=_secret_tool(["lookup","application","limad-study","service","gemini"])
    if result and result.returncode==0 and result.stdout.strip(): return result.stdout.strip()
    try: return KEY_FILE.read_text(encoding="utf-8").strip()
    except OSError: return ""

def _set_api_key(value):
    value=str(value or "").strip()
    if not value:
        result=_secret_tool(["clear","application","limad-study","service","gemini"])
        try: KEY_FILE.unlink()
        except OSError: pass
        return
    result=_secret_tool(["store","--label",SERVICE_NAME,"application","limad-study","service","gemini"],value)
    if result and result.returncode==0:
        try: KEY_FILE.unlink()
        except OSError: pass
        return
    KEY_FILE.parent.mkdir(parents=True,exist_ok=True)
    KEY_FILE.write_text(value,encoding="utf-8")
    os.chmod(KEY_FILE,0o600)

def _row(row): return dict(row) if row else None

def assistant_state():
    return {"configured":bool(_get_api_key()),"model":_setting("model",DEFAULT_MODEL),"store_remote":False,"online_research":False}

def list_projects():
    with _connect() as con:
        return [dict(r) for r in con.execute("SELECT p.*,(SELECT COUNT(*) FROM messages m WHERE m.project_id=p.id) message_count FROM projects p ORDER BY updated_at DESC")]

def create_project(title="Neue Ausarbeitung"):
    project_id=secrets.token_hex(12); now=utc_now(); title=str(title or "Neue Ausarbeitung").strip()[:160]
    with _connect() as con: con.execute("INSERT INTO projects VALUES(?,?,?,?)",(project_id,title,now,now))
    return {"id":project_id,"title":title,"created_at":now,"updated_at":now,"message_count":0}

def delete_project(project_id):
    with _connect() as con:
        con.execute("DELETE FROM messages WHERE project_id=?",(project_id,)); con.execute("DELETE FROM projects WHERE id=?",(project_id,))

def project_messages(project_id):
    with _connect() as con:
        rows=con.execute("SELECT * FROM messages WHERE project_id=? ORDER BY created_at,id",(project_id,)).fetchall()
    result=[]
    for row in rows:
        item=dict(row)
        try:item["context"]=json.loads(item.pop("context_json") or "[]")
        except Exception:item["context"]=[]
        result.append(item)
    return result

def _save_message(project_id,role,content,context=None):
    mid=secrets.token_hex(12); now=utc_now()
    with _connect() as con:
        exists=con.execute("SELECT id FROM projects WHERE id=?",(project_id,)).fetchone()
        if not exists: raise ValueError("KI-Projekt wurde nicht gefunden.")
        con.execute("INSERT INTO messages VALUES(?,?,?,?,?,?)",(mid,project_id,role,str(content),json.dumps(context or [],ensure_ascii=False),now))
        con.execute("UPDATE projects SET updated_at=? WHERE id=?",(now,project_id))
    return {"id":mid,"project_id":project_id,"role":role,"content":str(content),"context":context or [],"created_at":now}

def update_settings(data):
    if "api_key" in data: _set_api_key(data.get("api_key"))
    if "model" in data:
        model=str(data.get("model") or DEFAULT_MODEL).strip()
        if not re_model(model): raise ValueError("Ungültiger Gemini-Modellname.")
        _set_setting("model",model)
    return assistant_state()

def re_model(value):
    import re
    return bool(re.fullmatch(r"[A-Za-z0-9._-]{3,100}",value))

def _gemini(messages,context):
    key=_get_api_key()
    if not key: raise ValueError("Gemini API-Key fehlt. Öffne die Einstellungen des KI-Assistenten.")
    model=_setting("model",DEFAULT_MODEL)
    contents=[]
    for msg in messages[-30:]:
        role="model" if msg.get("role")=="assistant" else "user"
        contents.append({"role":role,"parts":[{"text":str(msg.get("content") or "")}]})
    if context:
        context_text="\n\n".join(f"[Study-Kontext: {c.get('label','Kontext')}]\n{c.get('text','')}" for c in context if str(c.get('text') or '').strip())
        if context_text:
            contents.append({"role":"user","parts":[{"text":"Zusätzlich freigegebener Study-Kontext:\n\n"+context_text}]})
    body={"systemInstruction":{"parts":[{"text":SYSTEM_INSTRUCTION}]},"contents":contents,"generationConfig":{"temperature":0.45,"maxOutputTokens":4096}}
    req=urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",data=json.dumps(body).encode("utf-8"),headers={"Content-Type":"application/json","X-goog-api-key":key},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=90) as response: payload=json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail=exc.read().decode("utf-8","replace")[:1500]
        raise ValueError(f"Gemini-Anfrage fehlgeschlagen (HTTP {exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Gemini ist nicht erreichbar: {exc.reason}") from exc
    candidates=payload.get("candidates") or []
    if not candidates: raise ValueError("Gemini hat keine Antwort geliefert.")
    parts=((candidates[0].get("content") or {}).get("parts") or [])
    text="\n".join(str(p.get("text") or "") for p in parts if p.get("text")).strip()
    if not text: raise ValueError("Gemini hat eine leere Antwort geliefert.")
    return text

def send_message(project_id,content,context=None):
    content=str(content or "").strip()
    if not content: raise ValueError("Nachricht fehlt.")
    if len(content)>100000: raise ValueError("Nachricht ist zu lang.")
    context=list(context or [])[:12]
    _save_message(project_id,"user",content,context)
    history=project_messages(project_id)
    answer=_gemini(history,context)
    assistant=_save_message(project_id,"assistant",answer,[])
    return {"message":assistant,"state":assistant_state()}

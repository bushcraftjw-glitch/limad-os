from __future__ import annotations
import hashlib
import html
import json
import mimetypes
import os
import re
import shutil
import tempfile
import unicodedata
import zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
    def handle_data(self, data: str) -> None:
        value = " ".join(data.split())
        if value:
            self.parts.append(value)
    def text(self) -> str:
        return " ".join(self.parts)

def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            block = stream.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()

def slug(value: str, fallback: str = "item") -> str:
    normalized = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    result = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return result[:96] or fallback

def safe_identifier(value: str, fallback: str = "item") -> str:
    result = re.sub(r"[^A-Za-z0-9_.-]+", "-", value or "").strip(".-")
    return result[:120] or fallback

def html_to_text(markup: str) -> str:
    parser = TextExtractor()
    try:
        parser.feed(markup or "")
        parser.close()
    except Exception:
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", markup or "")).strip()
    return parser.text()

def json_load(path: Path, default=None):
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def json_write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)

def safe_zip_members(archive: zipfile.ZipFile, max_files: int = 25000, max_size: int = 2_500_000_000) -> list[zipfile.ZipInfo]:
    members = archive.infolist()
    if len(members) > max_files:
        raise ValueError("Archiv enthält zu viele Dateien.")
    total = 0
    for member in members:
        name = member.filename.replace("\\", "/")
        parts = Path(name).parts
        if name.startswith("/") or ".." in parts:
            raise ValueError(f"Unsicherer Archivpfad: {name}")
        total += max(0, member.file_size)
        if total > max_size:
            raise ValueError("Archiv ist entpackt zu groß.")
    return members

def safe_extract(archive: zipfile.ZipFile, destination: Path, members: Iterable[zipfile.ZipInfo] | None = None) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    for member in members or safe_zip_members(archive):
        target = (destination / member.filename).resolve()
        if root not in target.parents and target != root:
            raise ValueError("Archivpfad verlässt das Zielverzeichnis.")
        if member.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(member) as source, target.open("wb") as output:
            shutil.copyfileobj(source, output, 1024 * 1024)

def atomic_directory(target: Path):
    target.parent.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(prefix=f".{target.name}-", dir=target.parent)

def mime_type(path: str | Path) -> str:
    return mimetypes.guess_type(str(path))[0] or "application/octet-stream"

def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))

def escape(value: str) -> str:
    return html.escape(value or "", quote=True)

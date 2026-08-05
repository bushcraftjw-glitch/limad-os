from __future__ import annotations

import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from .config import PATHS
from .database import DB

USER_AGENT = "LiMaD-Study/6.4 (+https://www.jw.org/)"
MAX_SOURCE_BYTES = 5 * 1024 * 1024
ALLOWED_PAGE_HOSTS = {"jw.org", "www.jw.org", "wol.jw.org"}
DROP_TAGS = {"script", "style", "noscript", "iframe", "form", "input", "select", "option", "button", "nav", "footer", "aside", "svg", "canvas"}
ALLOWED_TAGS = {
    "article", "section", "div", "p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li",
    "blockquote", "figure", "figcaption", "img", "a", "strong", "b", "em", "i", "span", "sup", "sub",
    "table", "thead", "tbody", "tr", "th", "td", "hr", "br", "details", "summary"
}
SKIP_HINTS = {
    "share", "sharing", "download", "footer", "navigation", "pagination", "toolbar", "language", "locale",
    "related", "recommend", "social", "audio-player", "mediaplayer", "player-controls", "banner", "cookie"
}


def _host_allowed(url: str) -> bool:
    host = (urllib.parse.urlparse(url).hostname or "").lower().rstrip(".")
    return host in ALLOWED_PAGE_HOSTS or host.endswith(".jw.org")


def _language_symbol(language_index: int) -> str:
    rows = DB.rows("SELECT symbol FROM languages WHERE id=? LIMIT 1", (int(language_index),))
    return str(rows[0].get("symbol") or "X") if rows else "X"


def official_source_url(link: str, language_index: int = 2) -> str:
    value = urllib.parse.unquote(str(link or "").strip())
    if not value:
        return ""
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme in {"http", "https"} and _host_allowed(value):
        return value
    match = re.search(r"jwpub://p/([^:/:]+):(\d+)", value, re.I)
    if match:
        symbol, docid = match.group(1), match.group(2)
        return "https://www.jw.org/finder?" + urllib.parse.urlencode({"wtlocale": symbol, "docid": docid, "srcid": "share"})
    params = urllib.parse.parse_qs(parsed.query)
    raw_docid = (params.get("docid") or params.get("docId") or [""])[0]
    if str(raw_docid).isdigit():
        return "https://www.jw.org/finder?" + urllib.parse.urlencode({"wtlocale": _language_symbol(language_index), "docid": raw_docid, "srcid": "share"})
    return ""


def _absolute_url(base: str, value: str) -> str:
    target = urllib.parse.urljoin(base, html.unescape(str(value or "").strip()))
    parsed = urllib.parse.urlparse(target)
    if parsed.scheme not in {"http", "https"}:
        return ""
    host = (parsed.hostname or "").lower()
    if not (host.endswith(".jw.org") or host.endswith(".jw-cdn.org") or host.endswith(".akamaihd.net")):
        return ""
    return target


class _MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.og_title = ""
        self.og_image = ""
        self.in_title = False

    def handle_starttag(self, tag: str, attrs):
        values = {str(k).lower(): str(v or "") for k, v in attrs}
        if tag.lower() == "title":
            self.in_title = True
        if tag.lower() == "meta":
            key = (values.get("property") or values.get("name") or "").lower()
            if key == "og:title":
                self.og_title = values.get("content", "")
            elif key == "og:image":
                self.og_image = values.get("content", "")

    def handle_endtag(self, tag: str):
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str):
        if self.in_title:
            self.title += data


class _Sanitizer(HTMLParser):
    VOID_TAGS = {"img", "br", "hr", "input", "meta", "link", "source", "track", "wbr", "area", "base", "embed", "param"}

    def __init__(self, base_url: str, target: str):
        super().__init__(convert_charrefs=False)
        self.base_url = base_url
        self.target = target
        self.capture_depth = 0
        self.target_seen = False
        self.skip_depth = 0
        self.output: list[str] = []
        self.open_tags: list[str] = []

    @staticmethod
    def _hint(attrs: dict[str, str]) -> str:
        return " ".join((attrs.get("id", ""), attrs.get("class", ""), attrs.get("role", ""))).lower().replace("_", "-")

    def handle_starttag(self, tag: str, attrs):
        tag = tag.lower()
        values = {str(k).lower(): str(v or "") for k, v in attrs}
        is_void = tag in self.VOID_TAGS
        if not self.target_seen and tag == self.target:
            self.target_seen = True
            self.capture_depth = 1
            return
        if not self.capture_depth:
            return
        if self.skip_depth:
            if not is_void:
                self.skip_depth += 1
                self.capture_depth += 1
                self.open_tags.append("__skip__")
            return
        hint = self._hint(values)
        if tag in DROP_TAGS or any(word in hint for word in SKIP_HINTS):
            if not is_void:
                self.skip_depth = 1
                self.capture_depth += 1
                self.open_tags.append("__skip__")
            return

        opened = ""
        if tag in ALLOWED_TAGS:
            clean: list[tuple[str, str]] = []
            class_value = values.get("class", "")
            if class_value:
                classes = [x for x in re.split(r"\s+", class_value) if re.fullmatch(r"[A-Za-z0-9_-]{1,64}", x)]
                if classes:
                    clean.append(("class", " ".join(classes[:12])))
            if values.get("id") and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", values["id"]):
                clean.append(("id", values["id"]))
            if values.get("data-pid") and re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", values["data-pid"]):
                clean.append(("data-pid", values["data-pid"]))
            if tag == "a":
                href = _absolute_url(self.base_url, values.get("href", ""))
                if href:
                    clean.extend((("href", href), ("target", "_blank"), ("rel", "noopener noreferrer")))
            elif tag == "img":
                src = values.get("src") or values.get("data-src") or values.get("data-lazy-src") or ""
                src = _absolute_url(self.base_url, src)
                if not src:
                    return
                clean.extend((("src", src), ("loading", "lazy"), ("decoding", "async")))
                if values.get("alt"):
                    clean.append(("alt", values["alt"][:500]))
                if values.get("width", "").isdigit():
                    clean.append(("width", values["width"]))
                if values.get("height", "").isdigit():
                    clean.append(("height", values["height"]))
            rendered = "".join(f' {name}="{html.escape(value, quote=True)}"' for name, value in clean)
            self.output.append(f"<{tag}{rendered}>")
            if not is_void:
                opened = tag

        if not is_void:
            self.capture_depth += 1
            self.open_tags.append(opened)

    def handle_startendtag(self, tag: str, attrs):
        self.handle_starttag(tag, attrs)
        if tag.lower() not in self.VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if not self.capture_depth:
            return
        if tag == self.target and self.capture_depth == 1:
            self.capture_depth = 0
            return
        if self.capture_depth <= 1:
            return
        opened = self.open_tags.pop() if self.open_tags else ""
        if self.skip_depth:
            self.skip_depth -= 1
        elif opened and opened != "__skip__":
            self.output.append(f"</{opened}>")
        self.capture_depth -= 1

    def handle_data(self, data: str):
        if self.capture_depth and not self.skip_depth:
            self.output.append(html.escape(data))

    def handle_entityref(self, name: str):
        if self.capture_depth and not self.skip_depth:
            self.output.append(f"&{name};")

    def handle_charref(self, name: str):
        if self.capture_depth and not self.skip_depth:
            self.output.append(f"&#{name};")


def _sanitize_document(raw: str, base_url: str) -> dict[str, str]:
    metadata = _MetadataParser()
    metadata.feed(raw)
    body = ""
    for target in ("main", "article", "body"):
        parser = _Sanitizer(base_url, target)
        parser.feed(raw)
        candidate = "".join(parser.output).strip()
        if len(re.sub(r"<[^>]+>", "", candidate).strip()) >= 60:
            body = candidate
            break
    text = html.unescape(re.sub(r"<[^>]+>", " ", body))
    text = re.sub(r"\s+", " ", text).strip()
    title = (metadata.og_title or metadata.title or "Online-Quelle").strip()
    image = _absolute_url(base_url, metadata.og_image)
    return {"title": title, "image": image, "html": body, "excerpt": text[:420] + ("…" if len(text) > 420 else "")}


def _cache_path(url: str) -> Path:
    folder = PATHS.cache / "online-sources"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / (hashlib.sha256(url.encode("utf-8")).hexdigest() + ".json")


def _read_cache(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) and value.get("html") else None
    except Exception:
        return None


def _public_payload(value: dict[str, Any], *, cached: bool, stale: bool = False, error: str = "") -> dict[str, Any]:
    return {
        "available": True,
        "title": str(value.get("title") or "Online-Quelle"),
        "image": str(value.get("image") or ""),
        "html": str(value.get("html") or ""),
        "excerpt": str(value.get("excerpt") or ""),
        "url": str(value.get("url") or value.get("final_url") or ""),
        "fetched_at": str(value.get("fetched_at") or ""),
        "cached": bool(cached),
        "stale": bool(stale),
        "error": str(error or ""),
    }


def resolve_online_source(link: str, label: str = "", language_index: int = 2, force: bool = False) -> dict[str, Any] | None:
    target = official_source_url(link, language_index)
    if not target:
        return None
    cache_path = _cache_path(target)
    cached = _read_cache(cache_path)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
        "Accept-Language": "de,en;q=0.6",
        "Accept-Encoding": "identity",
        "Cache-Control": "no-cache",
    }
    if cached and not force:
        if cached.get("etag"):
            headers["If-None-Match"] = str(cached["etag"])
        if cached.get("last_modified"):
            headers["If-Modified-Since"] = str(cached["last_modified"])
    request = urllib.request.Request(target, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            final_url = response.geturl()
            if not _host_allowed(final_url):
                raise ValueError("Die Quelle wurde auf eine nicht erlaubte Adresse umgeleitet.")
            raw_bytes = response.read(MAX_SOURCE_BYTES + 1)
            if len(raw_bytes) > MAX_SOURCE_BYTES:
                raise ValueError("Die Online-Quelle ist ungewöhnlich groß.")
            charset = response.headers.get_content_charset() or "utf-8"
            raw = raw_bytes.decode(charset, errors="replace")
            parsed = _sanitize_document(raw, final_url)
            if not parsed.get("html"):
                raise ValueError("Die offizielle Seite enthielt keinen darstellbaren Artikeltext.")
            stored = {
                **parsed,
                "url": final_url,
                "requested_url": target,
                "etag": response.headers.get("ETag") or "",
                "last_modified": response.headers.get("Last-Modified") or "",
                "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "label": label,
            }
            cache_path.write_text(json.dumps(stored, ensure_ascii=False), encoding="utf-8")
            return _public_payload(stored, cached=False)
    except urllib.error.HTTPError as error:
        if error.code == 304 and cached:
            cached["fetched_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            try:
                cache_path.write_text(json.dumps(cached, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass
            return _public_payload(cached, cached=True)
        if cached:
            return _public_payload(cached, cached=True, stale=True, error=f"HTTP {error.code}")
    except Exception as error:
        if cached:
            return _public_payload(cached, cached=True, stale=True, error=f"{error.__class__.__name__}: {error}")
    return None

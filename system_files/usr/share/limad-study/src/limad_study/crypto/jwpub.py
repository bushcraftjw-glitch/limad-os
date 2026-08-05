from __future__ import annotations
import hashlib
import zlib
from .aes import decrypt_cbc

XOR_KEY = bytes.fromhex("11cbb5587e32846d4c26790c633da289f66fe5842a3a585ce1bc3a294af5ada7")


def publication_key(language_index: int, symbol: str, year: int, issue_tag: int = 0) -> tuple[bytes, bytes]:
    token = f"{int(language_index)}_{symbol}_{int(year)}"
    if int(issue_tag or 0):
        token += f"_{int(issue_tag)}"
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    card = bytes(a ^ b for a, b in zip(digest, XOR_KEY))
    return card[:16], card[16:]


def decrypt_html(blob: bytes | None, language_index: int, symbol: str, year: int, issue_tag: int = 0) -> str:
    if not blob:
        return ""
    key, iv = publication_key(language_index, symbol, year, issue_tag)
    raw = decrypt_cbc(bytes(blob), key, iv)
    attempts = [raw]
    pad = raw[-1] if raw else 0
    if 0 < pad <= 16 and raw.endswith(bytes([pad]) * pad):
        attempts.insert(0, raw[:-pad])
    error = None
    for candidate in attempts:
        try:
            return zlib.decompress(candidate).decode("utf-8", errors="replace")
        except Exception as exc:
            error = exc
    raise ValueError(f"JWPUB-Inhaltsblock konnte nicht dekodiert werden: {error}")

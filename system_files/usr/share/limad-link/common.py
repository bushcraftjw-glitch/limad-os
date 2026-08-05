from __future__ import annotations
import hashlib
import json
import os
import socket
import ssl
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

APP_ID = "de.limad.Link"
APP_NAME = "LiLink"
VERSION = "1.0.0-preview3"
SERVICE = "limad-link.service"
SERVICE_TYPE = "_limad-link._tcp"
DEFAULT_PORT = 47888


def runtime_file() -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    return (Path(runtime) if runtime else Path("/tmp")) / ("limad-link.json" if runtime else f"limad-link-{os.getuid()}.json")


def state_dir() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "limad-link"


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(temp, 0o600)
    os.replace(temp, path)


def certificate_fingerprint(host: str, port: int, timeout: float = 4.0) -> str:
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    with socket.create_connection((host, port), timeout=timeout) as raw:
        with context.wrap_socket(raw, server_hostname=host) as tls:
            der = tls.getpeercert(binary_form=True)
    return hashlib.sha256(der).hexdigest()


def api_request(url: str, payload=None, token: str | None = None, admin: str | None = None, timeout: float = 15.0):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if admin:
        headers["X-LiMaD-Admin"] = admin
    request = urllib.request.Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            result = json.loads(exc.read().decode("utf-8"))
            raise RuntimeError(result.get("error") or f"HTTP {exc.code}") from exc
        except json.JSONDecodeError:
            raise RuntimeError(f"HTTP {exc.code}") from exc
    if isinstance(result, dict) and result.get("ok") is False:
        raise RuntimeError(str(result.get("error") or "LiLink-Anfrage fehlgeschlagen"))
    return result


def ensure_service(timeout: float = 25.0) -> dict:
    import time
    subprocess.run(["systemctl", "--user", "start", SERVICE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = read_json(runtime_file(), None)
        if isinstance(last, dict) and last.get("adminToken") and last.get("port"):
            try:
                health = api_request(f"https://127.0.0.1:{int(last['port'])}/api/health", timeout=1.5)
                if health.get("ok") and health.get("version") == VERSION:
                    return last
            except Exception:
                pass
        time.sleep(0.25)
    raise RuntimeError(f"LiLink-Dienst {VERSION} ist nicht erreichbar. Status: {last!r}")

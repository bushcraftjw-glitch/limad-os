from __future__ import annotations
import base64
import csv
import getpass
import hashlib
import http.client
import ipaddress
import json
import mimetypes
import os
import re
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from common import APP_NAME, DEFAULT_PORT, SERVICE_TYPE, VERSION, api_request, certificate_fingerprint, runtime_file, state_dir, read_json, write_json


def xdg_download_dir(home: Path) -> Path:
    config = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config")) / "user-dirs.dirs"
    try:
        for line in config.read_text(encoding="utf-8").splitlines():
            if line.startswith("XDG_DOWNLOAD_DIR="):
                raw = line.split("=", 1)[1].strip().strip('"').replace("$HOME", str(home))
                value = Path(os.path.expandvars(os.path.expanduser(raw)))
                if value.is_absolute():
                    return value
    except OSError:
        pass
    return home / "Downloads"

STATE = state_dir()
IDENTITY_FILE = STATE / "identity.json"
PEERS_FILE = STATE / "peers.json"
SETTINGS_FILE = STATE / "settings.json"
TLS_DIR = STATE / "tls"
RECEIVE_DIR = xdg_download_dir(Path.home()) / "LiDrop"
HANDOFF_DIR = STATE / "handoff"
ADMIN_TOKEN = secrets.token_urlsafe(32)
LOCK = threading.RLock()
PAIR_CODES = {}
PAIR_ATTEMPTS = {}
ACTIVE_RDP = {"owned": False, "connections": set()}
PUBLISHER = None
PUBLISH_STOP = threading.Event()


def run(args, input_text=None, timeout=20):
    return subprocess.run(args, input=input_text, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)


def notify(title, body, urgency="normal"):
    cmd = shutil.which("notify-send")
    if cmd:
        subprocess.Popen([cmd, "-u", urgency, title, body], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def ensure_identity():
    STATE.mkdir(parents=True, exist_ok=True)
    os.chmod(STATE, 0o700)
    value = read_json(IDENTITY_FILE, {})
    if not isinstance(value, dict) or not value.get("deviceId"):
        host = socket.gethostname().split(".")[0]
        pretty = os.environ.get("LIMAD_DEVICE_NAME") or f"LiMaD {host}"
        value = {"deviceId": secrets.token_hex(16), "name": pretty, "createdAt": int(time.time())}
        write_json(IDENTITY_FILE, value)
    return value


def ensure_tls(identity):
    TLS_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(TLS_DIR, 0o700)
    key = TLS_DIR / "key.pem"
    cert = TLS_DIR / "cert.pem"
    if not key.is_file() or not cert.is_file():
        openssl = shutil.which("openssl")
        if not openssl:
            raise RuntimeError("OpenSSL fehlt; LiLink kann kein TLS-Zertifikat erzeugen.")
        name = re.sub(r"[^A-Za-z0-9 ._-]", "", identity["name"])[:64] or "LiLink"
        result = run([openssl, "req", "-x509", "-newkey", "rsa:3072", "-sha256", "-days", "1825", "-nodes", "-subj", f"/CN={name}", "-keyout", str(key), "-out", str(cert)], timeout=40)
        if result.returncode:
            raise RuntimeError(result.stdout.strip() or "TLS-Zertifikat konnte nicht erzeugt werden.")
        os.chmod(key, 0o600)
        os.chmod(cert, 0o600)
    der = ssl.PEM_cert_to_DER_cert(cert.read_text(encoding="utf-8"))
    fingerprint = hashlib.sha256(der).hexdigest()
    return key, cert, fingerprint


def peers():
    value = read_json(PEERS_FILE, {})
    return value if isinstance(value, dict) else {}


def save_peers(value):
    write_json(PEERS_FILE, value)


def settings():
    defaults = {"autoAcceptRdp": False, "disableRdpAfterUse": True, "screenPosition": "right"}
    value = read_json(SETTINGS_FILE, {})
    if isinstance(value, dict):
        defaults.update(value)
    return defaults


def save_settings(value):
    write_json(SETTINGS_FILE, value)


def local_network_source(address):
    try:
        value = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False
    if value.is_loopback or value.is_private or value.is_link_local:
        return True
    return isinstance(value, ipaddress.IPv4Address) and value in ipaddress.ip_network("100.64.0.0/10")


def local_addresses():
    values = set()
    try:
        infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for info in infos:
            address = info[4][0].split("%")[0]
            if not address.startswith("127.") and address != "::1":
                values.add(address)
    except OSError:
        pass
    return sorted(values)


def discover(identity):
    command = shutil.which("avahi-browse")
    if not command:
        return []
    result = run([command, "-rtp", SERVICE_TYPE], timeout=8)
    found = {}
    for line in result.stdout.splitlines():
        if not line.startswith("="):
            continue
        try:
            row = next(csv.reader([line], delimiter=";", escapechar="\\", quoting=csv.QUOTE_NONE))
            if len(row) < 9:
                continue
            _, interface, protocol, name, service_type, domain, host, address, port, *txt = row
            if service_type != SERVICE_TYPE:
                continue
            fields = {}
            txt_blob = ";".join(txt)
            txt_items = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', txt_blob)
            if not txt_items:
                txt_items = [item.strip('"') for item in txt]
            for item in txt_items:
                if "=" in item:
                    key, value = item.split("=", 1)
                    fields[key] = value
            device_id = fields.get("id")
            if not device_id or device_id == identity["deviceId"]:
                continue
            found[device_id] = {
                "deviceId": device_id,
                "name": fields.get("name") or name,
                "host": address or host.rstrip("."),
                "hostname": host.rstrip("."),
                "port": int(port),
                "fingerprint": fields.get("fp", ""),
                "version": fields.get("version", ""),
                "capabilities": fields.get("cap", "").split(",") if fields.get("cap") else [],
                "interface": interface,
                "protocol": protocol,
                "online": True,
            }
        except Exception:
            continue
    saved = peers()
    now = int(time.time())
    for device_id, item in found.items():
        if device_id in saved:
            saved[device_id].update({k: item[k] for k in ("name", "host", "hostname", "port", "fingerprint", "version", "capabilities")})
            saved[device_id]["lastSeen"] = now
    save_peers(saved)
    return sorted(found.values(), key=lambda item: item["name"].casefold())


def publish(identity, port, fingerprint):
    command = shutil.which("avahi-publish-service")
    if not command:
        return None
    args = [command, "-s", identity["name"], SERVICE_TYPE, str(port), f"id={identity['deviceId']}", f"name={identity['name']}", f"version={VERSION}", f"fp={fingerprint}", "cap=rdp,files,deskflow,handoff"]

    def worker():
        global PUBLISHER
        while not PUBLISH_STOP.is_set():
            try:
                PUBLISHER = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                while PUBLISHER.poll() is None and not PUBLISH_STOP.wait(1):
                    pass
                if PUBLISH_STOP.is_set() and PUBLISHER.poll() is None:
                    PUBLISHER.terminate()
                    try:
                        PUBLISHER.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        PUBLISHER.kill()
            except OSError:
                pass
            if not PUBLISH_STOP.wait(5):
                continue
        PUBLISHER = None

    thread = threading.Thread(target=worker, name="lilink-avahi", daemon=True)
    thread.start()
    return thread


def authorized_peer(handler):
    header = handler.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    token = header[7:]
    for device_id, peer in peers().items():
        if secrets.compare_digest(str(peer.get("inboundToken", "")), token):
            value = dict(peer)
            value["deviceId"] = device_id
            return value
    return None


def parse_json(handler, limit=1024 * 1024):
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length < 0 or length > limit:
        raise ValueError("Anfrage ist zu groß.")
    raw = handler.rfile.read(length) if length else b"{}"
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Ungültige Anfrage.")
    return value


def grd_status():
    command = shutil.which("grdctl")
    if not command:
        return {"available": False, "enabled": False, "remoteControl": False, "detail": "grdctl fehlt"}
    result = run([command, "status"])
    text = result.stdout.strip()
    low = text.casefold()
    return {"available": True, "enabled": "enabled" in low or "aktiviert" in low, "remoteControl": not ("view-only: yes" in low or "nur anzeigen: ja" in low), "detail": text}



def rdp_port():
    detail = str(grd_status().get("detail") or "")
    match = re.search(r"(?im)^\s*port\s*:\s*(\d{1,5})\s*$", detail)
    if match and 1 <= int(match.group(1)) <= 65535:
        return int(match.group(1))
    command = shutil.which("gsettings")
    if command:
        result = run([command, "get", "org.gnome.desktop.remote-desktop.rdp", "port"])
        match = re.search(r"\b(\d{1,5})\b", result.stdout)
        if result.returncode == 0 and match and 1 <= int(match.group(1)) <= 65535:
            return int(match.group(1))
    return 3389

def configure_rdp(peer_id):
    command = shutil.which("grdctl")
    if not command:
        raise RuntimeError("GNOME Remote Desktop ist nicht installiert.")
    before = grd_status()
    username = f"lilink-{peer_id[:8]}"
    password = secrets.token_urlsafe(24)
    result = run([command, "rdp", "set-credentials"], input_text=f"{username}\n{password}\n", timeout=20)
    if result.returncode:
        result = run([command, "rdp", "set-credentials", username, password], timeout=20)
    if result.returncode:
        raise RuntimeError(result.stdout.strip() or "RDP-Zugangsdaten konnten nicht gesetzt werden.")
    for args in ([command, "rdp", "disable-view-only"], [command, "rdp", "enable"]):
        result = run(args, timeout=20)
        if result.returncode:
            raise RuntimeError(result.stdout.strip() or f"Fehler bei {' '.join(args[1:])}")
    ACTIVE_RDP["owned"] = not before.get("enabled", False)
    ACTIVE_RDP["connections"].add(peer_id)
    return {"username": username, "password": password, "port": rdp_port(), "wasEnabled": before.get("enabled", False)}


def release_rdp(peer_id):
    ACTIVE_RDP["connections"].discard(peer_id)
    cfg = settings()
    if not ACTIVE_RDP["connections"] and ACTIVE_RDP["owned"] and cfg.get("disableRdpAfterUse"):
        command = shutil.which("grdctl")
        if command:
            run([command, "rdp", "disable"])
        ACTIVE_RDP["owned"] = False


def verify_remote(item):
    actual = certificate_fingerprint(item["host"], int(item["port"]))
    expected = str(item.get("fingerprint") or "").lower()
    if not expected or not secrets.compare_digest(actual, expected):
        raise RuntimeError("TLS-Fingerabdruck des Geräts stimmt nicht. Kopplung wurde abgebrochen.")


def remote_call(item, path, payload=None, timeout=20):
    verify_remote(item)
    return api_request(f"https://{item['host']}:{int(item['port'])}{path}", payload, token=item.get("outboundToken"), timeout=timeout)


def sha256_file(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def send_file(item, path: Path):
    if not path.is_file():
        raise RuntimeError(f"Datei fehlt: {path}")
    size = path.stat().st_size
    digest = sha256_file(path)
    begin = remote_call(item, "/api/remote/files/begin", {"name": path.name, "size": size, "sha256": digest}, timeout=30)
    transfer_id = begin["transferId"]
    offset = int(begin.get("offset", 0))
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    with path.open("rb") as source:
        source.seek(offset)
        while offset < size:
            chunk = source.read(min(4 * 1024 * 1024, size - offset))
            body = base64.b64encode(chunk).decode("ascii")
            result = remote_call(item, f"/api/remote/files/chunk", {"transferId": transfer_id, "offset": offset, "data": body}, timeout=90)
            offset = int(result["offset"])
    return remote_call(item, "/api/remote/files/finish", {"transferId": transfer_id}, timeout=90)


def safe_filename(name):
    name = Path(name).name.replace("\x00", "")
    return name[:240] or "Datei"


def launch_handoff(payload):
    application = str(payload.get("application") or "").strip()
    uri = str(payload.get("uri") or "").strip()
    files = [str(item) for item in payload.get("files", []) if item]
    commands = {
        "limad-study": ["/usr/local/bin/limad-study"],
        "limad-notes": ["/usr/local/bin/limad-notes"],
        "limad-cut": ["/usr/local/bin/limad-cut"],
        "libreoffice": ["libreoffice"],
        "zen-browser": ["flatpak", "run", "app.zen_browser.zen"],
        "media": ["xdg-open"],
    }
    command = commands.get(application)
    if command:
        args = command + ([uri] if uri else files[:1])
    elif uri:
        args = ["xdg-open", uri]
    elif files:
        args = ["xdg-open", files[0]]
    else:
        raise RuntimeError("Der Handoff enthält kein startbares Ziel.")
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class Handler(BaseHTTPRequestHandler):
    server_version = "LiLink"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def json(self, status=200, **payload):
        payload.setdefault("ok", status < 400)
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def admin(self):
        return self.client_address[0] in {"127.0.0.1", "::1"} and secrets.compare_digest(self.headers.get("X-LiMaD-Admin", ""), ADMIN_TOKEN)

    def do_GET(self):
        try:
            if not local_network_source(self.client_address[0]):
                return self.json(403, error="LiLink erlaubt nur lokale Netzwerkquellen.")
            if self.path == "/api/health":
                return self.json(version=VERSION, deviceId=self.server.identity["deviceId"], name=self.server.identity["name"], fingerprint=self.server.fingerprint, capabilities=["rdp", "files", "deskflow", "handoff"])
            if self.path == "/api/admin/state":
                if not self.admin():
                    return self.json(403, error="Lokale Administratorberechtigung fehlt.")
                discovered = discover(self.server.identity)
                paired = peers()
                now = int(time.time())
                devices = []
                discovered_map = {item["deviceId"]: item for item in discovered}
                for device_id, item in paired.items():
                    merged = dict(item)
                    merged.update({k: v for k, v in discovered_map.get(device_id, {}).items() if k not in {"outboundToken", "inboundToken"}})
                    merged["deviceId"] = device_id
                    merged["paired"] = True
                    merged["online"] = device_id in discovered_map or now - int(merged.get("lastSeen", 0)) < 30
                    merged.pop("inboundToken", None)
                    merged.pop("outboundToken", None)
                    devices.append(merged)
                for device_id, item in discovered_map.items():
                    if device_id not in paired:
                        candidate = dict(item)
                        candidate["paired"] = False
                        devices.append(candidate)
                return self.json(identity=self.server.identity, devices=sorted(devices, key=lambda x: x.get("name", "").casefold()), rdp=grd_status(), settings=settings(), deskflow=bool(shutil.which("deskflow") or shutil.which("deskflow-core")))
            if self.path == "/api/remote/status":
                peer = authorized_peer(self)
                if not peer:
                    return self.json(401, error="Gerät ist nicht gekoppelt.")
                return self.json(device=self.server.identity, rdp=grd_status(), permissions=peer.get("permissions", {}))
            return self.json(404, error="Nicht gefunden.")
        except Exception as exc:
            return self.json(500, error=str(exc))

    def do_POST(self):
        try:
            if not local_network_source(self.client_address[0]):
                return self.json(403, error="LiLink erlaubt nur lokale Netzwerkquellen.")
            if self.path.startswith("/api/admin/"):
                if not self.admin():
                    return self.json(403, error="Lokale Administratorberechtigung fehlt.")
                return self.admin_post()
            if self.path == "/api/pair/claim":
                return self.pair_claim()
            peer = authorized_peer(self)
            if not peer:
                return self.json(401, error="Gerät ist nicht gekoppelt.")
            return self.remote_post(peer)
        except ValueError as exc:
            return self.json(400, error=str(exc))
        except Exception as exc:
            return self.json(500, error=str(exc))

    def admin_post(self):
        body = parse_json(self)
        identity = self.server.identity
        if self.path == "/api/admin/pair-code":
            code = f"{secrets.randbelow(1000000):06d}"
            with LOCK:
                PAIR_CODES.clear()
                PAIR_CODES[code] = time.time() + 300
            notify("LiLink-Kopplung", f"Kopplungscode: {code[:3]} {code[3:]}\nGültig für 5 Minuten.")
            return self.json(code=code, expiresIn=300)
        if self.path == "/api/admin/pair":
            host = str(body.get("host") or "").strip()
            port = int(body.get("port") or 0)
            fingerprint = str(body.get("fingerprint") or "").lower()
            code = re.sub(r"\D", "", str(body.get("code") or ""))
            if not host or not 1 <= port <= 65535 or len(code) != 6:
                raise ValueError("Gerät, Port oder Kopplungscode ist ungültig.")
            actual = certificate_fingerprint(host, port)
            if fingerprint and not secrets.compare_digest(actual, fingerprint):
                raise RuntimeError("TLS-Fingerabdruck stimmt nicht.")
            accept_token = secrets.token_urlsafe(32)
            response = api_request(f"https://{host}:{port}/api/pair/claim", {"code": code, "device": {"deviceId": identity["deviceId"], "name": identity["name"], "host": socket.gethostname() + ".local", "port": self.server.server_address[1], "fingerprint": self.server.fingerprint, "version": VERSION}, "acceptToken": accept_token}, timeout=12)
            target = response["device"]
            device_id = target["deviceId"]
            current = peers()
            current[device_id] = {"name": target["name"], "host": host, "hostname": target.get("hostname", ""), "port": port, "fingerprint": actual, "version": target.get("version", ""), "inboundToken": accept_token, "outboundToken": response["acceptToken"], "permissions": {"screen": True, "files": True, "clipboard": True, "handoff": True}, "lastSeen": int(time.time())}
            save_peers(current)
            return self.json(deviceId=device_id, name=target["name"])
        if self.path == "/api/admin/unpair":
            device_id = str(body.get("deviceId") or "")
            current = peers()
            current.pop(device_id, None)
            save_peers(current)
            return self.json()
        if self.path == "/api/admin/settings":
            value = settings()
            for key in ("autoAcceptRdp", "disableRdpAfterUse", "screenPosition"):
                if key in body:
                    value[key] = body[key]
            save_settings(value)
            return self.json(settings=value)
        if self.path == "/api/admin/permissions":
            device_id = str(body.get("deviceId") or "")
            current = peers()
            if device_id not in current:
                raise RuntimeError("Gerät ist nicht gekoppelt.")
            requested = body.get("permissions") or {}
            permissions = current[device_id].get("permissions", {})
            for key in ("screen", "files", "clipboard", "handoff"):
                if key in requested:
                    permissions[key] = bool(requested[key])
            current[device_id]["permissions"] = permissions
            save_peers(current)
            return self.json(permissions=permissions)
        device_id = str(body.get("deviceId") or "")
        item = peers().get(device_id)
        if not item:
            raise RuntimeError("Gerät ist nicht gekoppelt.")
        if self.path == "/api/admin/rdp-prepare":
            result = remote_call(item, "/api/remote/rdp/prepare", {}, timeout=35)
            result.update({"host": item["host"], "name": item["name"], "deviceId": device_id})
            return self.json(**result)
        if self.path == "/api/admin/rdp-release":
            remote_call(item, "/api/remote/rdp/release", {}, timeout=10)
            return self.json()
        if self.path == "/api/admin/send-files":
            paths = [Path(p).expanduser().resolve() for p in body.get("paths", [])]
            results = [send_file(item, path) for path in paths]
            return self.json(results=results)
        if self.path == "/api/admin/handoff":
            handoff = dict(body.get("handoff") or {})
            uri = str(handoff.get("uri") or "").strip()
            local = Path(uri).expanduser() if uri else None
            if local and local.is_file():
                transferred = send_file(item, local.resolve())
                handoff["files"] = [transferred["path"]]
                handoff["uri"] = ""
            result = remote_call(item, "/api/remote/handoff", handoff, timeout=30)
            return self.json(result=result)
        raise RuntimeError("Unbekannte lokale Aktion.")

    def pair_claim(self):
        body = parse_json(self)
        code = re.sub(r"\D", "", str(body.get("code") or ""))
        now = time.time()
        address = self.client_address[0]
        with LOCK:
            history = [stamp for stamp in PAIR_ATTEMPTS.get(address, []) if now - stamp < 300]
            if len(history) >= 8:
                return self.json(429, error="Zu viele Kopplungsversuche. Bitte fünf Minuten warten.")
            history.append(now)
            PAIR_ATTEMPTS[address] = history
            expiry = PAIR_CODES.pop(code, 0)
        if not expiry or expiry < time.time():
            return self.json(403, error="Kopplungscode ist falsch oder abgelaufen.")
        device = body.get("device") or {}
        device_id = str(device.get("deviceId") or "")
        accept_token = str(body.get("acceptToken") or "")
        if len(device_id) < 16 or len(accept_token) < 32:
            raise ValueError("Ungültige Geräteidentität.")
        outbound = secrets.token_urlsafe(32)
        current = peers()
        current[device_id] = {"name": str(device.get("name") or "LiMaD-Gerät"), "host": self.client_address[0], "hostname": str(device.get("host") or ""), "port": int(device.get("port") or DEFAULT_PORT), "fingerprint": str(device.get("fingerprint") or ""), "version": str(device.get("version") or ""), "inboundToken": outbound, "outboundToken": accept_token, "permissions": {"screen": True, "files": True, "clipboard": True, "handoff": True}, "lastSeen": int(time.time())}
        save_peers(current)
        notify("LiLink", f"{current[device_id]['name']} wurde gekoppelt.")
        identity = self.server.identity
        return self.json(device={"deviceId": identity["deviceId"], "name": identity["name"], "hostname": socket.gethostname() + ".local", "version": VERSION}, acceptToken=outbound)

    def remote_post(self, peer):
        body = parse_json(self, limit=8 * 1024 * 1024)
        permissions = peer.get("permissions", {})
        if self.path == "/api/remote/rdp/prepare":
            if not permissions.get("screen", False):
                return self.json(403, error="Bildschirmzugriff ist für dieses Gerät nicht erlaubt.")
            cfg = settings()
            if not cfg.get("autoAcceptRdp", False):
                notify("LiLink-Bildschirmzugriff", f"{peer['name']} startet eine bestätigte LiLink-Verbindung.")
            result = configure_rdp(peer["deviceId"])
            return self.json(**result)
        if self.path == "/api/remote/rdp/release":
            release_rdp(peer["deviceId"])
            return self.json()
        if self.path == "/api/remote/files/begin":
            if not permissions.get("files", False):
                return self.json(403, error="Dateiübertragung ist nicht erlaubt.")
            name = safe_filename(str(body.get("name") or "Datei"))
            size = int(body.get("size") or 0)
            digest = str(body.get("sha256") or "").lower()
            if size < 0 or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("Ungültige Dateiinformationen.")
            RECEIVE_DIR.mkdir(parents=True, exist_ok=True)
            temp_dir = STATE / "incoming"
            temp_dir.mkdir(parents=True, exist_ok=True)
            transfer_id = hashlib.sha256(f"{peer['deviceId']}:{name}:{size}:{digest}".encode()).hexdigest()[:32]
            meta = {"name": name, "size": size, "sha256": digest, "peer": peer["deviceId"]}
            write_json(temp_dir / f"{transfer_id}.json", meta)
            part = temp_dir / f"{transfer_id}.part"
            offset = min(part.stat().st_size if part.exists() else 0, size)
            return self.json(transferId=transfer_id, offset=offset)
        if self.path == "/api/remote/files/chunk":
            transfer_id = str(body.get("transferId") or "")
            offset = int(body.get("offset") or 0)
            if not re.fullmatch(r"[0-9a-f]{32}", transfer_id):
                raise ValueError("Ungültige Übertragung.")
            temp_dir = STATE / "incoming"
            meta = read_json(temp_dir / f"{transfer_id}.json", None)
            if not meta or meta.get("peer") != peer["deviceId"]:
                raise RuntimeError("Übertragung wurde nicht begonnen.")
            part = temp_dir / f"{transfer_id}.part"
            current = part.stat().st_size if part.exists() else 0
            if current != offset:
                return self.json(offset=current)
            data = base64.b64decode(str(body.get("data") or ""), validate=True)
            if current + len(data) > int(meta["size"]):
                raise ValueError("Übertragungsgröße überschritten.")
            with part.open("ab") as target:
                target.write(data)
            return self.json(offset=current + len(data))
        if self.path == "/api/remote/files/finish":
            transfer_id = str(body.get("transferId") or "")
            temp_dir = STATE / "incoming"
            meta_path = temp_dir / f"{transfer_id}.json"
            part = temp_dir / f"{transfer_id}.part"
            meta = read_json(meta_path, None)
            if not meta or meta.get("peer") != peer["deviceId"] or not part.is_file():
                raise RuntimeError("Übertragung ist unvollständig.")
            if part.stat().st_size != int(meta["size"]):
                raise RuntimeError("Dateigröße stimmt noch nicht.")
            digest = sha256_file(part)
            if digest != meta["sha256"]:
                raise RuntimeError("SHA-256-Prüfung fehlgeschlagen.")
            target = RECEIVE_DIR / safe_filename(meta["name"])
            if target.exists():
                target = RECEIVE_DIR / f"{target.stem}-{int(time.time())}{target.suffix}"
            os.replace(part, target)
            meta_path.unlink(missing_ok=True)
            notify("LiLink-Datei empfangen", f"{target.name}\nVon {peer['name']}")
            return self.json(path=str(target), name=target.name)
        if self.path == "/api/remote/handoff":
            if not permissions.get("handoff", False):
                return self.json(403, error="Handoff ist nicht erlaubt.")
            payload = dict(body)
            payload["receivedFrom"] = peer["deviceId"]
            payload["receivedAt"] = int(time.time())
            HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
            record = HANDOFF_DIR / f"{int(time.time())}-{secrets.token_hex(4)}.json"
            write_json(record, payload)
            launch_handoff(payload)
            notify("LiLink – hier fortsetzen", f"Arbeitsstand von {peer['name']} wurde geöffnet.")
            return self.json(record=str(record))
        return self.json(404, error="Unbekannte Remote-Aktion.")


def main():
    identity = ensure_identity()
    key, cert, fingerprint = ensure_tls(identity)
    port = DEFAULT_PORT
    server = None
    for candidate in range(DEFAULT_PORT, DEFAULT_PORT + 11):
        try:
            server = Server(("", candidate), Handler)
            port = candidate
            break
        except OSError:
            continue
    if server is None:
        raise RuntimeError("Kein freier LiLink-Port verfügbar.")
    server.identity = identity
    server.fingerprint = fingerprint
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certfile=str(cert), keyfile=str(key))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    runtime = {"pid": os.getpid(), "port": port, "url": f"https://127.0.0.1:{port}", "adminToken": ADMIN_TOKEN, "version": VERSION, "deviceId": identity["deviceId"], "fingerprint": fingerprint}
    write_json(runtime_file(), runtime)
    publisher_thread = publish(identity, port, fingerprint)
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        runtime_file().unlink(missing_ok=True)
        PUBLISH_STOP.set()
        if PUBLISHER and PUBLISHER.poll() is None:
            PUBLISHER.terminate()
        if publisher_thread:
            publisher_thread.join(timeout=4)


if __name__ == "__main__":
    main()

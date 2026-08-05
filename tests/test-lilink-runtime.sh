#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
command -v openssl >/dev/null || { echo "LILINK RUNTIME FAILED: openssl fehlt" >&2; exit 1; }
python3 - <<'PY'
from pathlib import Path
import hashlib
import json
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.request

app = Path.cwd() / "system_files/usr/share/limad-link"


def request(runtime, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"X-LiMaD-Admin": runtime["adminToken"], "Content-Type": "application/json"}
    req = urllib.request.Request(
        f"https://127.0.0.1:{runtime['port']}{path}",
        data=data,
        headers=headers,
        method="POST" if data is not None else "GET",
    )
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(req, context=context, timeout=120) as response:
        result = json.loads(response.read().decode("utf-8"))
    if result.get("ok") is False:
        raise RuntimeError(result.get("error") or "LiLink request failed")
    return result


def wait_runtime(path):
    for _ in range(240):
        if path.exists():
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                if value.get("port"):
                    return value
            except Exception:
                pass
        time.sleep(0.05)
    raise RuntimeError(f"LiLink runtime file fehlt: {path}")


base = Path(tempfile.mkdtemp(prefix="lilink-runtime-"))
processes = []
try:
    runtimes = []
    homes = []
    for index, name in enumerate(("Notebook", "iMac")):
        home = base / f"home-{index}"
        runtime_dir = base / f"run-{index}"
        home.mkdir()
        runtime_dir.mkdir()
        os.chmod(runtime_dir, 0o700)
        env = os.environ.copy()
        env.update({
            "HOME": str(home),
            "XDG_RUNTIME_DIR": str(runtime_dir),
            "XDG_DATA_HOME": str(home / ".local/share"),
            "PYTHONPATH": str(app),
            "LIMAD_DEVICE_NAME": f"LiMaD {name}",
            "PATH": "/usr/bin:/bin",
            "PYTHONDONTWRITEBYTECODE": "1",
        })
        process = subprocess.Popen(
            [sys.executable, str(app / "daemon.py")],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        processes.append(process)
        runtimes.append(wait_runtime(runtime_dir / "limad-link.json"))
        homes.append(home)

    notebook, imac = runtimes
    code = request(imac, "/api/admin/pair-code", {})["code"]
    paired = request(notebook, "/api/admin/pair", {
        "host": "127.0.0.1",
        "port": imac["port"],
        "fingerprint": imac["fingerprint"],
        "code": code,
    })
    if paired.get("name") != "LiMaD iMac":
        raise RuntimeError(f"Falsches Kopplungsziel: {paired}")
    state_notebook = request(notebook, "/api/admin/state")
    state_imac = request(imac, "/api/admin/state")
    peers_notebook = [item for item in state_notebook["devices"] if item.get("paired")]
    peers_imac = [item for item in state_imac["devices"] if item.get("paired")]
    if len(peers_notebook) != 1 or len(peers_imac) != 1:
        raise RuntimeError("Gegenseitige Kopplung wurde nicht gespeichert.")

    request(notebook, "/api/admin/permissions", {
        "deviceId": peers_notebook[0]["deviceId"],
        "permissions": {"screen": False, "files": True, "clipboard": False, "handoff": True},
    })
    updated = next(item for item in request(notebook, "/api/admin/state")["devices"] if item.get("paired"))
    if updated.get("permissions") != {"screen": False, "files": True, "clipboard": False, "handoff": True}:
        raise RuntimeError("Geräteberechtigungen wurden nicht korrekt gespeichert.")

    source = homes[0] / "continuity-test.bin"
    source.write_bytes(os.urandom(3 * 1024 * 1024 + 17))
    request(notebook, "/api/admin/send-files", {
        "deviceId": peers_notebook[0]["deviceId"],
        "paths": [str(source)],
    })
    target = homes[1] / "Downloads" / "LiDrop" / source.name
    if not target.is_file():
        raise RuntimeError("Übertragene Datei fehlt.")
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    target_hash = hashlib.sha256(target.read_bytes()).hexdigest()
    if source_hash != target_hash:
        raise RuntimeError("SHA-256 nach Übertragung stimmt nicht.")

    request(notebook, "/api/admin/unpair", {"deviceId": peers_notebook[0]["deviceId"]})
    if [item for item in request(notebook, "/api/admin/state")["devices"] if item.get("paired")]:
        raise RuntimeError("Kopplung wurde lokal nicht widerrufen.")

    print(f"LiLink two-device TLS pairing, permissions, mutual trust, {source.stat().st_size}-byte transfer, SHA-256 and unpair: PASS")
finally:
    for process in processes:
        process.terminate()
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    shutil.rmtree(base, ignore_errors=True)
PY

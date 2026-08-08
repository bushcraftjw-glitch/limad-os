#!/usr/bin/python3
from __future__ import annotations
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def runtime_file():
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    return Path(runtime) / "limad-drop.json" if runtime else Path("/tmp") / f"limad-drop-{os.getuid()}.json"


def runtime():
    subprocess.run(["systemctl", "--user", "start", "limad-drop.service"], check=False)
    for _ in range(60):
        try: return json.loads(runtime_file().read_text(encoding="utf-8"))
        except Exception: time.sleep(.25)
    raise RuntimeError("LiDrop-Dienst ist nicht erreichbar")


def stage(paths):
    info = runtime()
    data = json.dumps({"paths": [str(Path(p).expanduser().resolve()) for p in paths]}).encode()
    request = urllib.request.Request(f"http://127.0.0.1:{info['port']}/api/admin/stage-paths", data=data, method="POST", headers={"Content-Type": "application/json", "X-LiMaD-Admin": info["adminToken"]})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode())
    if not payload.get("ok"): raise RuntimeError(payload.get("error", "Dateien konnten nicht vorgemerkt werden"))
    subprocess.Popen(["/usr/local/bin/limad-drop"])


if __name__ == "__main__":
    if len(sys.argv) < 2: raise SystemExit("Keine Datei ausgewählt")
    stage(sys.argv[1:])

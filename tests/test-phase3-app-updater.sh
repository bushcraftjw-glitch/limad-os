#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."

python3 - <<'PY'
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path.cwd()
sf = root / "system_files"

def fail(message):
    raise SystemExit(f"PHASE 3 FAILED: {message}")

version=(root / "VERSION").read_text().strip()
if not version.startswith(("2.6.", "2.7.", "2.8.")):
    fail("VERSION liegt vor Phase 3")
versions = (root / "build_files/versions.env").read_text()
if 'LIMAD_OS_VERSION=' not in versions or not any(marker in versions for marker in ('phase3-app-updater', 'phase4-release-audit', 'phase4-fix9', 'phase4-fix10', 'phase4-fix12', 'phase4-fix13', 'phase4-fix14', 'phase4-fix15', 'phase4-fix16', 'phase4-fix17', 'phase4-fix18', 'phase4-fix19', 'phase4-fix20', 'phase4-fix21', 'phase4-fix22', 'phase4-fix27', 'phase4-fix28', 'phase4-fix29', 'phase4-fix30', 'phase4-fix31', 'phase4-fix32', 'phase4-fix35', 'phase4-fix36', 'phase4-fix37', 'phase4-fix39', 'phase4-fix41', 'phase4-fix43', 'phase4-fix44', 'phase4-fix45', 'phase4-fix47', 'phase4-fix48', 'phase4-fix49', 'phase4-fix50', 'gnome-rc2-build4', 'gnome-rc2-build5')):
    fail("Phase-3/4-Versionskennung fehlt")

required = [
    sf / "usr/share/limad-updater/backend.py",
    sf / "usr/share/limad-updater/updater.py",
    sf / "usr/share/limad-updater/check.py",
    sf / "usr/local/bin/limad-app-update-check",
    sf / "usr/lib/systemd/user/limad-app-update-check.service",
    sf / "usr/lib/systemd/user/limad-app-update-check.timer",
    root / "PHASE-3-APP-UPDATER-PRUEFUNG.md",
]
for path in required:
    if not path.is_file():
        fail(f"{path} fehlt")

config = json.loads((sf / "usr/share/limad-updater/apps.json").read_text())
if config.get("format_version") != 2:
    fail("apps.json verwendet nicht Format 2")
for app in config["apps"]:
    if not app.get("launcher"):
        fail(f"Launcher fehlt für {app['app_id']}")

for app_id in ["Cut", "Study", "Drop", "AnycubicSlicerNext"]:
    desktop = (sf / f"usr/share/applications/de.limad.{app_id}.desktop").read_text()
    if "Name=Nach Updates suchen" not in desktop:
        fail(f"Update-Aktion fehlt für {app_id}")

backend_text = (sf / "usr/share/limad-updater/backend.py").read_text()
for token in ["MAX_UNCOMPRESSED_BYTES", "scan_updates", "discover_packages", "launch_app", "Prüfsumme stimmt nicht"]:
    if token not in backend_text:
        fail(f"Backend-Schutz oder Funktion fehlt: {token}")

with tempfile.TemporaryDirectory() as td:
    temp = Path(td)
    payload = temp / "payload"
    payload.mkdir()
    (payload / "native_shell.py").write_text("print('phase3')\n")
    (payload / "VERSION").write_text("1.1.0\n")
    downloads = temp / "Downloads"
    downloads.mkdir()
    system_version = temp / "SYSTEM_VERSION"
    system_version.write_text("1.0.0\n")
    fake_config = temp / "apps.json"
    fake_config.write_text(json.dumps({
        "format_version": 2,
        "apps": [{
            "app_id": "de.limad.Cut",
            "name": "LiMaD Cut",
            "launcher": "/bin/true",
            "system_root": "/tmp/not-used",
            "system_version_file": str(system_version),
            "required": ["native_shell.py", "VERSION"],
            "restart_user_services": [],
        }],
    }))
    package = downloads / "LiMaD-Cut-1.1.0.limad-update.zip"
    subprocess.run([
        sys.executable,
        str(root / "tools/build-limad-update.py"),
        "--app-id", "de.limad.Cut",
        "--version", "1.1.0",
        "--payload", str(payload),
        "--output", str(package),
    ], check=True, stdout=subprocess.DEVNULL)
    os.environ["XDG_DATA_HOME"] = str(temp / "data")
    os.environ["XDG_STATE_HOME"] = str(temp / "state")
    os.environ["LIMAD_UPDATER_CONFIG"] = str(fake_config)
    os.environ["LIMAD_UPDATE_SEARCH_DIRS"] = str(downloads)
    sys.path.insert(0, str(sf / "usr/share/limad-updater"))
    import backend
    candidates = backend.scan_updates()
    candidate = candidates.get("de.limad.Cut")
    if not candidate or candidate["version"] != "1.1.0":
        fail("automatische lokale Updatesuche erkennt das Paket nicht")
    installed = backend.install_package(package, "de.limad.Cut")
    if installed["active_version"] != "1.1.0":
        fail("gefundenes Paket wird nicht aktiviert")
    if backend.scan_updates().get("de.limad.Cut") is not None:
        fail("bereits aktive Version wird weiterhin als neuer erkannt")

print("Phase 3 app updater, local scan, atomic failed-install recovery and system-version restore: PASS")
PY

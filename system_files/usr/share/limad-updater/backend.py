#!/usr/bin/env python3
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath

FORMAT = "org.limad.app-update"
VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+~-]{0,95}$")
APP_RE = re.compile(r"^de\.limad\.[A-Za-z0-9]+$")
MAX_ARCHIVE_BYTES = 2 * 1024 * 1024 * 1024
MAX_FILES = 20000
MAX_FILE_BYTES = 2 * 1024 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 8 * 1024 * 1024 * 1024
MAX_MANIFEST_BYTES = 128 * 1024
MAX_SUMS_BYTES = 4 * 1024 * 1024
MAX_SCAN_FILES = 600
QUALIFIERS = {
    "dev": 0,
    "alpha": 1,
    "a": 1,
    "beta": 2,
    "b": 2,
    "preview": 3,
    "pre": 3,
    "rc": 4,
    "final": 5,
    "stable": 5,
    "post": 6,
}


def data_home():
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))


def state_home():
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))


def config_path():
    return Path(os.environ.get("LIMAD_UPDATER_CONFIG", "/usr/share/limad-updater/apps.json"))


def load_config():
    data = json.loads(config_path().read_text(encoding="utf-8"))
    return {item["app_id"]: item for item in data["apps"]}


def log(message):
    path = state_home() / "limad-updater" / "updater.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {message}\n")


def app_base(app_id):
    return data_home() / "limad-updater" / "apps" / app_id


def current_link(app_id):
    return app_base(app_id) / "current"


def active_root(app_id):
    link = current_link(app_id)
    if link.is_symlink() or link.exists():
        root = link / "payload"
        if root.exists():
            return root
    return None


def read_text(path, fallback="Unbekannt"):
    try:
        value = Path(path).read_text(encoding="utf-8").strip()
        return value or fallback
    except OSError:
        return fallback


def system_version(app):
    if app.get("system_version_file"):
        return read_text(app["system_version_file"])
    return app.get("system_version", "Unbekannt")


def active_version(app_id):
    root = active_root(app_id)
    if not root:
        return None
    manifest = current_link(app_id) / "limad-update.json"
    try:
        return json.loads(manifest.read_text(encoding="utf-8"))["version"]
    except (OSError, KeyError, json.JSONDecodeError):
        return "Unbekannt"


def version_key(version):
    parts = re.findall(r"\d+|[A-Za-z]+", version.lower())
    result = []
    has_qualifier = False
    for part in parts:
        if part.isdigit():
            result.append((2, int(part), ""))
        elif part in QUALIFIERS:
            has_qualifier = True
            result.append((1, QUALIFIERS[part], ""))
        else:
            result.append((1, 7, part))
    if not has_qualifier:
        result.append((1, QUALIFIERS["final"], ""))
    return tuple(result)


def is_newer(candidate, current):
    if current in {"", "Unbekannt", None}:
        return True
    try:
        return version_key(candidate) > version_key(current)
    except TypeError:
        return candidate != current


def status(app_id):
    apps = load_config()
    app = apps[app_id]
    user_version = active_version(app_id)
    return {
        "app_id": app_id,
        "name": app["name"],
        "system_version": system_version(app),
        "active_version": user_version or system_version(app),
        "source": "Benutzer-Update" if user_version else "Systemversion",
        "can_restore": bool(user_version),
        "launcher": app.get("launcher"),
    }


def safe_member(name):
    if not name or "\x00" in name:
        return False
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts and "" not in path.parts


def is_symlink(info):
    return ((info.external_attr >> 16) & 0o170000) == 0o120000


def read_limited(zf, name, limit):
    info = zf.getinfo(name)
    if info.file_size > limit:
        raise ValueError(f"{name} ist ungewöhnlich groß.")
    return zf.read(info)


def parse_sums(text):
    result = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        match = re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?(.+)", line)
        if not match:
            raise ValueError("SHA256SUMS enthält eine ungültige Zeile.")
        name = match.group(2)
        if name in result:
            raise ValueError("SHA256SUMS enthält einen Dateinamen mehrfach.")
        result[name] = match.group(1).lower()
    return result


def inspect_package(zip_path):
    path = Path(zip_path)
    if not path.is_file():
        raise ValueError("Die ausgewählte ZIP-Datei wurde nicht gefunden.")
    if path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("Das Update-Paket ist größer als die zulässige Höchstgröße.")
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            if "limad-update.json" not in names or "SHA256SUMS" not in names:
                raise ValueError("Das ZIP ist kein LiMaD-Update-Paket.")
            manifest = json.loads(read_limited(zf, "limad-update.json", MAX_MANIFEST_BYTES).decode("utf-8"))
    except zipfile.BadZipFile as exc:
        raise ValueError("Das Update-ZIP ist beschädigt.") from exc
    validate_manifest(manifest)
    return manifest


def validate_manifest(manifest, expected_app=None):
    if manifest.get("format") != FORMAT or manifest.get("format_version") != 1:
        raise ValueError("Nicht unterstütztes LiMaD-Update-Format.")
    app_id = manifest.get("app_id", "")
    version = manifest.get("version", "")
    if not APP_RE.fullmatch(app_id):
        raise ValueError("Ungültige App-ID im Update-Paket.")
    if not VERSION_RE.fullmatch(version):
        raise ValueError("Ungültige Versionsnummer im Update-Paket.")
    apps = load_config()
    if app_id not in apps:
        raise ValueError("Dieses Update gehört nicht zu einer unterstützten LiMaD-App.")
    if expected_app and app_id != expected_app:
        raise ValueError(f"Dieses ZIP ist für {apps[app_id]['name']} bestimmt.")
    return apps[app_id], app_id, version


def verify_archive(zf):
    infos = zf.infolist()
    if len(infos) > MAX_FILES:
        raise ValueError("Das Update-Paket enthält zu viele Dateien.")
    names = [info.filename for info in infos]
    if len(names) != len(set(names)):
        raise ValueError("Das Update-Paket enthält Dateinamen mehrfach.")
    allowed = {"limad-update.json", "SHA256SUMS"}
    total = 0
    for info in infos:
        if not safe_member(info.filename):
            raise ValueError("Das Update-Paket enthält einen unsicheren Dateipfad.")
        if info.flag_bits & 0x1:
            raise ValueError("Verschlüsselte Dateien sind in Update-Paketen nicht erlaubt.")
        if is_symlink(info):
            raise ValueError("Symbolische Links sind in Update-Paketen nicht erlaubt.")
        if info.is_dir():
            continue
        if not info.filename.startswith("payload/") and info.filename not in allowed:
            raise ValueError(f"Unerwartete Datei im Update-Paket: {info.filename}")
        if info.file_size > MAX_FILE_BYTES:
            raise ValueError(f"Datei im Update-Paket ist zu groß: {info.filename}")
        total += info.file_size
        if total > MAX_UNCOMPRESSED_BYTES:
            raise ValueError("Das entpackte Update-Paket überschreitet die zulässige Höchstgröße.")
        if info.compress_size and info.file_size > 64 * 1024 * 1024 and info.file_size / info.compress_size > 300:
            raise ValueError("Das Update-Paket weist ein unsicheres Kompressionsverhältnis auf.")
    sums = parse_sums(read_limited(zf, "SHA256SUMS", MAX_SUMS_BYTES).decode("utf-8"))
    payload_files = sorted(info.filename for info in infos if not info.is_dir() and info.filename.startswith("payload/"))
    if not payload_files:
        raise ValueError("Das Update-Paket enthält keine App-Dateien.")
    if set(payload_files) != set(sums):
        raise ValueError("Die Prüfsummenliste deckt die App-Dateien nicht exakt ab.")
    for name in payload_files:
        digest = hashlib.sha256()
        with zf.open(name) as source:
            while True:
                block = source.read(1024 * 1024)
                if not block:
                    break
                digest.update(block)
        if digest.hexdigest() != sums[name]:
            raise ValueError(f"Prüfsumme stimmt nicht: {name}")


def validate_payload(app, payload):
    for rel in app.get("required", []):
        if not (payload / rel).exists():
            raise ValueError(f"Erforderliche App-Datei fehlt: {rel}")
    for rel in app.get("executables", []):
        target = payload / rel
        if not target.is_file():
            raise ValueError(f"Ausführbare App-Datei fehlt: {rel}")
        target.chmod(target.stat().st_mode | 0o755)


def swap_current(base, release):
    base.mkdir(parents=True, exist_ok=True)
    temp_link = base / ".current-new"
    temp_link.unlink(missing_ok=True)
    temp_link.symlink_to(os.path.relpath(release, base))
    os.replace(temp_link, base / "current")


def run_post_install(app, payload):
    if app.get("post_install") != "study-prepare":
        return
    env = os.environ.copy()
    env["LIMAD_STUDY_RESOURCE_ROOT"] = str(payload)
    env["PYTHONPATH"] = str(payload / "src") + (":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    result = subprocess.run(
        ["/usr/bin/python3", "-m", "limad_study", "--prepare-only"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        tail = "\n".join(result.stdout.splitlines()[-12:])
        raise RuntimeError("LiMaD Study konnte die mitgelieferten Daten nicht vorbereiten.\n" + tail)


def restart_services(app):
    services = app.get("restart_user_services", [])
    if not services or not shutil.which("systemctl"):
        return
    subprocess.run(["systemctl", "--user", "daemon-reload"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for service in services:
        subprocess.run(["systemctl", "--user", "restart", service], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def cleanup_releases(base, current_name, keep=3):
    releases = base / "releases"
    if not releases.is_dir():
        return
    entries = sorted((path for path in releases.iterdir() if path.is_dir()), key=lambda path: path.stat().st_mtime, reverse=True)
    kept = 0
    for entry in entries:
        if entry.name == current_name or kept < keep - 1:
            kept += 1
            continue
        shutil.rmtree(entry, ignore_errors=True)


def install_package(zip_path, expected_app=None):
    path = Path(zip_path).expanduser().resolve()
    manifest = inspect_package(path)
    app, app_id, version = validate_manifest(manifest, expected_app)
    previous_status = status(app_id)
    try:
        with zipfile.ZipFile(path) as zf:
            verify_archive(zf)
            base = app_base(app_id)
            releases = base / "releases"
            releases.mkdir(parents=True, exist_ok=True)
            previous = None
            link = current_link(app_id)
            if link.is_symlink():
                previous = os.readlink(link)
            with tempfile.TemporaryDirectory(prefix=".install-", dir=releases) as tmp:
                temp = Path(tmp)
                for info in zf.infolist():
                    if info.filename.startswith("payload/") and not info.is_dir():
                        target = temp / info.filename
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(info) as source, target.open("wb") as destination:
                            shutil.copyfileobj(source, destination, length=1024 * 1024)
                payload = temp / "payload"
                validate_payload(app, payload)
                (temp / "limad-update.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                release = releases / f"{version}-{time.time_ns()}"
                os.replace(temp, release)
            try:
                swap_current(base, release)
                run_post_install(app, release / "payload")
                restart_services(app)
            except Exception:
                if previous:
                    old = base / previous
                    if old.exists():
                        swap_current(base, old)
                else:
                    link.unlink(missing_ok=True)
                shutil.rmtree(release, ignore_errors=True)
                raise
            cleanup_releases(base, release.name)
    except Exception as exc:
        log(f"FAIL app={app_id} package={path} error={exc}")
        raise
    result = status(app_id)
    result["previous_version"] = previous_status["active_version"]
    result["package"] = str(path)
    log(f"OK app={app_id} version={version} package={path}")
    return result


def restore_system(app_id):
    apps = load_config()
    if app_id not in apps:
        raise ValueError("Unbekannte App-ID.")
    current_link(app_id).unlink(missing_ok=True)
    restart_services(apps[app_id])
    result = status(app_id)
    log(f"RESTORE app={app_id} version={result['system_version']}")
    return result


def xdg_search_dirs():
    result = []
    override = os.environ.get("LIMAD_UPDATE_SEARCH_DIRS")
    if override:
        result.extend(Path(value).expanduser() for value in override.split(os.pathsep) if value)
    else:
        result.extend([Path.home() / "Downloads", Path.home() / "Desktop", Path.home() / "Schreibtisch"])
        user_dirs = Path.home() / ".config/user-dirs.dirs"
        if user_dirs.is_file():
            for line in user_dirs.read_text(encoding="utf-8", errors="ignore").splitlines():
                match = re.match(r'XDG_(?:DOWNLOAD|DESKTOP)_DIR="(.+)"', line)
                if match:
                    result.append(Path(match.group(1).replace("$HOME", str(Path.home()))).expanduser())
    unique = []
    seen = set()
    for path in result:
        resolved = path.resolve(strict=False)
        if resolved not in seen and resolved.is_dir():
            seen.add(resolved)
            unique.append(resolved)
    return unique


def discover_packages(search_dirs=None):
    apps = load_config()
    found = []
    checked = 0
    directories = search_dirs or xdg_search_dirs()
    for directory in directories:
        candidates = list(directory.glob("*.limad-update.zip"))
        candidates.extend(directory.glob("*/*.limad-update.zip"))
        for path in sorted(set(candidates), key=lambda item: item.stat().st_mtime, reverse=True):
            checked += 1
            if checked > MAX_SCAN_FILES:
                break
            try:
                manifest = inspect_package(path)
                app, app_id, version = validate_manifest(manifest)
                current = status(app_id)["active_version"]
                found.append({
                    "app_id": app_id,
                    "name": app["name"],
                    "version": version,
                    "path": str(path),
                    "mtime": path.stat().st_mtime,
                    "current_version": current,
                    "is_newer": is_newer(version, current),
                })
            except Exception:
                continue
        if checked > MAX_SCAN_FILES:
            break
    found.sort(key=lambda item: (item["app_id"], version_key(item["version"]), item["mtime"]), reverse=True)
    return found


def scan_updates(search_dirs=None):
    result = {app_id: None for app_id in load_config()}
    for candidate in discover_packages(search_dirs):
        if not candidate["is_newer"]:
            continue
        current = result[candidate["app_id"]]
        if current is None or version_key(candidate["version"]) > version_key(current["version"]):
            result[candidate["app_id"]] = candidate
    return result


def launch_app(app_id):
    app = load_config().get(app_id)
    if not app:
        raise ValueError("Unbekannte App-ID.")
    launcher = app.get("launcher")
    if not launcher or not Path(launcher).is_file():
        raise ValueError("Der App-Starter wurde nicht gefunden.")
    subprocess.Popen([launcher], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    log(f"LAUNCH app={app_id} launcher={launcher}")

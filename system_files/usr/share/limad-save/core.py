from __future__ import annotations

import configparser
import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

VERSION = "1.0.0-preview3"
APP_ID = "de.limad.Save"
HOME = Path.home()
CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config"))
DATA_HOME = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share"))
STATE_HOME = Path(os.environ.get("XDG_STATE_HOME", HOME / ".local/state"))
CACHE_HOME = Path(os.environ.get("XDG_CACHE_HOME", HOME / ".cache"))
CONFIG_DIR = CONFIG_HOME / "limad-save"
CONFIG_FILE = CONFIG_DIR / "config.json"
STATE_DIR = STATE_HOME / "limad-save"
REPORT_DIR = STATE_DIR / "reports"
SNAPSHOT_STAGE = STATE_DIR / "snapshots"
DEFAULT_CATEGORIES = {
    "documents": True,
    "zen": True,
    "mail": True,
    "study": True,
    "notes": True,
    "windows": True,
    "windows_full": False,
    "settings": True,
    "appsettings": True,
}


class LiSaveError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run(args: list[str], *, input_text: str | None = None, env: dict | None = None, check: bool = False, timeout: int | None = None) -> subprocess.CompletedProcess:
    result = subprocess.run(args, input=input_text, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, timeout=timeout, check=False)
    if check and result.returncode:
        raise LiSaveError(result.stdout.strip() or f"Befehl fehlgeschlagen: {' '.join(args)}")
    return result


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_config() -> dict:
    value = load_json(CONFIG_FILE, {})
    if not isinstance(value, dict):
        value = {}
    value.setdefault("categories", dict(DEFAULT_CATEGORIES))
    value.setdefault("automatic", False)
    value.setdefault("before_update", True)
    value.setdefault("retention", {"daily": 7, "weekly": 4, "monthly": 6})
    return value


def save_config(value: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    save_json(CONFIG_FILE, value)
    os.chmod(CONFIG_FILE, 0o600)


def xdg_user_dir(key: str, fallback: str) -> Path:
    config = CONFIG_HOME / "user-dirs.dirs"
    try:
        for line in config.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"XDG_{key}_DIR="):
                raw = line.split("=", 1)[1].strip().strip('"').replace("$HOME", str(HOME))
                value = Path(os.path.expandvars(os.path.expanduser(raw)))
                if value.is_absolute():
                    return value
    except OSError:
        pass
    return HOME / fallback


def bundle_path(target: Path) -> Path:
    target = Path(target).expanduser().resolve()
    if target.name.endswith(".lisavebackup"):
        return target
    name = socket.gethostname().split(".")[0] or "LiMaD"
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in name).strip("-") or "LiMaD"
    return target / f"{safe}.lisavebackup"


def repository_path(bundle: Path) -> Path:
    return bundle / "repository"


def ensure_external_target(bundle: Path) -> None:
    resolved_home = HOME.resolve()
    resolved_bundle = bundle.resolve()
    try:
        resolved_bundle.relative_to(resolved_home)
    except ValueError:
        return
    raise LiSaveError("Das LiSave-Ziel darf nicht im Benutzerordner liegen. Bitte ein zweites Laufwerk, eine USB-SSD oder einen USB-Stick auswählen.")


def repo_id(bundle: Path) -> str:
    return hashlib.sha256(str(bundle.resolve()).encode("utf-8")).hexdigest()


def ensure_dependencies() -> None:
    for command in ("restic", "flatpak", "dconf"):
        if not shutil.which(command):
            raise LiSaveError(f"Erforderliches Programm fehlt: {command}")


def secret_store(bundle: Path, password: str) -> None:
    tool = shutil.which("secret-tool")
    if not tool:
        raise LiSaveError("GNOME-Schlüsselbund ist nicht verfügbar; automatische Sicherung kann das Passwort nicht speichern.")
    result = run([tool, "store", "--label=LiSave Backup", "application", APP_ID, "repository", repo_id(bundle)], input_text=password)
    if result.returncode:
        raise LiSaveError(result.stdout.strip() or "Backup-Passwort konnte nicht im GNOME-Schlüsselbund gespeichert werden.")


def secret_lookup(bundle: Path) -> str:
    tool = shutil.which("secret-tool")
    if not tool:
        return ""
    result = run([tool, "lookup", "application", APP_ID, "repository", repo_id(bundle)])
    return result.stdout.rstrip("\n") if result.returncode == 0 else ""


def password_file(password: str):
    class PasswordContext:
        def __enter__(self):
            runtime = Path(os.environ.get("XDG_RUNTIME_DIR", tempfile.gettempdir()))
            runtime.mkdir(parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(prefix="lisave-password-", dir=runtime)
            os.write(fd, (password + "\n").encode("utf-8"))
            os.close(fd)
            os.chmod(name, 0o600)
            self.path = Path(name)
            return self.path

        def __exit__(self, *_):
            try:
                self.path.unlink()
            except OSError:
                pass
    return PasswordContext()


def restic(bundle: Path, password: str, arguments: list[str], *, check: bool = True, timeout: int | None = None) -> subprocess.CompletedProcess:
    repo = repository_path(bundle)
    with password_file(password) as password_path:
        args = ["restic", "-r", str(repo), "--password-file", str(password_path), *arguments]
        return run(args, check=check, timeout=timeout)


def ensure_repository(bundle: Path, password: str) -> None:
    bundle.mkdir(parents=True, exist_ok=True)
    repo = repository_path(bundle)
    if not (repo / "config").is_file():
        repo.mkdir(parents=True, exist_ok=True)
        restic(bundle, password, ["init"])
    else:
        restic(bundle, password, ["snapshots", "--json"], timeout=120)


ANALYSIS_EXCLUDED_DIR_NAMES = {
    "cache", "Cache", ".cache", "startupCache", "crashes",
    "shader-cache", "GPUCache", "Code Cache",
}
STUDY_EXCLUDED_DIR_NAMES = {"publications", "downloads", "catalog", "covers"}


def analysis_excluded_directory(path: Path, categories: dict) -> bool:
    if path.name in ANALYSIS_EXCLUDED_DIR_NAMES:
        return True
    parts = path.parts
    for index, part in enumerate(parts[:-1]):
        child = parts[index + 1]
        if part == "limad-study" and child in STUDY_EXCLUDED_DIR_NAMES:
            return True
        if part == "limad-windows":
            if child in {"prefix", "cache"} and not categories.get("windows_full", False):
                return True
            if child == "apps" and not categories.get("windows_full", False):
                tail = parts[index + 2:]
                if len(tail) >= 2 and tail[1] == "prefix":
                    return True
    if not categories.get("windows_full", False):
        marker = ("com.usebottles.bottles", "data", "bottles", "bottles")
        if any(parts[index:index + len(marker)] == marker for index in range(max(0, len(parts) - len(marker) + 1))):
            return True
    return False


def directory_size(path: Path, categories: dict | None = None) -> int:
    categories = {**DEFAULT_CATEGORIES, **(categories or {})}
    if not path.exists() or path.is_symlink():
        return 0
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    for root, dirs, files in os.walk(path, followlinks=False):
        root_path = Path(root)
        kept = []
        for name in dirs:
            candidate = root_path / name
            if not analysis_excluded_directory(candidate, categories):
                kept.append(name)
        dirs[:] = kept
        for name in files:
            candidate = root_path / name
            if analysis_excluded_directory(candidate.parent, categories):
                continue
            try:
                total += candidate.stat().st_size
            except OSError:
                pass
    return total


def zen_roots() -> list[Path]:
    return [HOME / ".var/app/app.zen_browser.zen/zen", HOME / ".var/app/io.github.zen_browser.zen/zen", HOME / ".zen"]


def mail_roots() -> list[Path]:
    return [
        HOME / ".var/app/org.mozilla.thunderbird_esr/.thunderbird",
        HOME / ".var/app/org.mozilla.thunderbird/.thunderbird",
        HOME / ".var/app/org.mozilla.Thunderbird/.thunderbird",
        HOME / ".thunderbird",
    ]


def category_sources(categories: dict) -> dict[str, list[Path]]:
    documents = xdg_user_dir("DOCUMENTS", "Documents")
    desktop = xdg_user_dir("DESKTOP", "Desktop")
    downloads = xdg_user_dir("DOWNLOAD", "Downloads")
    sources: dict[str, list[Path]] = {key: [] for key in DEFAULT_CATEGORIES}
    if categories.get("documents", True):
        sources["documents"] = [documents, desktop, downloads / "LiDrop", documents / "LiLink Sync"]
    if categories.get("zen", True):
        sources["zen"] = zen_roots()
    if categories.get("mail", True):
        sources["mail"] = mail_roots()
    if categories.get("study", True):
        sources["study"] = [DATA_HOME / "limad-study", CONFIG_HOME / "limad-study"]
    if categories.get("notes", True):
        sources["notes"] = [DATA_HOME / "limad-notes", CONFIG_HOME / "limad-notes"]
    if categories.get("windows", True):
        sources["windows"] = [DATA_HOME / "limad-windows"]
    if categories.get("settings", True):
        sources["settings"] = [CONFIG_HOME / "limad", CONFIG_HOME / "gtk-3.0", CONFIG_HOME / "gtk-4.0", DATA_HOME / "applications", DATA_HOME / "fonts"]
    if categories.get("appsettings", True):
        sources["appsettings"] = [
            HOME / ".var/app/org.libreoffice.LibreOffice/config/libreoffice",
            HOME / ".var/app/com.github.wwmm.easyeffects/config/easyeffects",
            CONFIG_HOME / "libreoffice",
            CONFIG_HOME / "easyeffects",
            CONFIG_HOME / "autostart",
        ]
    return {key: [path for path in values if path.exists()] for key, values in sources.items()}


def analyze(categories: dict | None = None) -> dict:
    categories = {**DEFAULT_CATEGORIES, **(categories or {})}
    sources = category_sources(categories)
    sizes = {key: sum(directory_size(path, categories) for path in values) for key, values in sources.items()}
    return {
        "categories": sizes,
        "total": sum(sizes.values()),
        "sources": {key: [str(path) for path in values] for key, values in sources.items()},
        "backup_exclusions_applied": True,
    }


def command_json(args: list[str], default):
    result = run(args)
    if result.returncode:
        return default
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return default


def flatpak_manifest() -> list[dict]:
    result = run(["flatpak", "list", "--app", "--columns=application,origin,version,installation"])
    apps = []
    if result.returncode:
        return apps
    for line in result.stdout.splitlines():
        fields = line.split("\t")
        if not fields or not fields[0].strip():
            continue
        apps.append({
            "id": fields[0].strip(),
            "origin": fields[1].strip() if len(fields) > 1 and fields[1].strip() else "flathub",
            "version": fields[2].strip() if len(fields) > 2 else "",
            "installation": fields[3].strip() if len(fields) > 3 else "user",
        })
    return apps


def dconf_exports(folder: Path) -> list[dict]:
    paths = [
        "/org/gnome/desktop/interface/",
        "/org/gnome/desktop/wm/preferences/",
        "/org/gnome/shell/",
        "/org/gnome/nautilus/preferences/",
        "/org/gnome/terminal/",
    ]
    folder.mkdir(parents=True, exist_ok=True)
    exported = []
    for index, dconf_path in enumerate(paths):
        result = run(["dconf", "dump", dconf_path])
        if result.returncode:
            continue
        target = folder / f"{index:02d}.ini"
        target.write_text(result.stdout, encoding="utf-8")
        exported.append({"path": dconf_path, "file": target.name})
    return exported


def study_root() -> Path:
    system = Path("/usr/share/limad-study")
    user = DATA_HOME / "limad-updater/apps/de.limad.Study/current/payload"
    selector = Path("/usr/local/libexec/limad-select-app-root")
    if selector.is_file():
        result = run([str(selector), str(system), str(user), "VERSION"])
        candidate = Path(result.stdout.strip()) if result.returncode == 0 else system
        if candidate.is_dir():
            return candidate
    return user if (user / "src").is_dir() else system


def export_study_backup(folder: Path) -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    root = study_root()
    source = root / "src"
    if not source.is_dir():
        return {"ok": False, "error": "LiMaD-Study-Quellpfad fehlt"}
    sys.path.insert(0, str(source))
    try:
        from limad_study.backup import export_jwlibrary
        result = export_jwlibrary(folder)
        return {"ok": True, "result": result}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        try:
            sys.path.remove(str(source))
        except ValueError:
            pass


def sanitize_lilink(stage: Path) -> None:
    settings = STATE_HOME / "limad-link/settings.json"
    if settings.is_file():
        value = load_json(settings, {})
        if isinstance(value, dict):
            save_json(stage / "lilink-settings.json", value)


def create_stage(categories: dict) -> tuple[Path, dict]:
    token = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + hashlib.sha256(os.urandom(32)).hexdigest()[:8]
    stage = SNAPSHOT_STAGE / token
    stage.mkdir(parents=True, exist_ok=False)
    sources = category_sources(categories)
    manifest = {
        "format": 1,
        "lisaveVersion": VERSION,
        "createdAt": now_iso(),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "home": str(HOME),
        "user": os.environ.get("USER", HOME.name),
        "categories": categories,
        "sources": {key: [str(path) for path in values] for key, values in sources.items()},
        "flatpaks": flatpak_manifest(),
        "aptManual": run(["apt-mark", "showmanual"]).stdout.splitlines() if shutil.which("apt-mark") else [],
        "osRelease": Path("/etc/os-release").read_text(encoding="utf-8", errors="replace") if Path("/etc/os-release").is_file() else "",
    }
    save_json(stage / "manifest.json", manifest)
    save_json(stage / "restore-plan.json", {"steps": ["system-update", "flatpaks", "user-data", "study", "settings", "verification"]})
    save_json(stage / "flatpaks.json", manifest["flatpaks"])
    dconf = dconf_exports(stage / "dconf") if categories.get("settings", True) else []
    save_json(stage / "dconf.json", dconf)
    if categories.get("study", True):
        save_json(stage / "study-export.json", export_study_backup(stage / "study"))
    if categories.get("windows", True):
        registry = DATA_HOME / "limad-windows/apps.json"
        if registry.is_file():
            (stage / "windows").mkdir(parents=True, exist_ok=True)
            shutil.copy2(registry, stage / "windows/apps.json")
    sanitize_lilink(stage)
    return stage, manifest


def exclusions(categories: dict, target: Path) -> list[str]:
    values = [
        str(target),
        "**/.cache/**",
        "**/cache/**",
        "**/Cache/**",
        "**/startupCache/**",
        "**/crashes/**",
        "**/shader-cache/**",
        "**/GPUCache/**",
        "**/Code Cache/**",
        "**/limad-study/publications/**",
        "**/limad-study/downloads/**",
        "**/limad-study/catalog/**",
        "**/limad-study/covers/**",
    ]
    if not categories.get("windows_full", False):
        values.extend([
            "**/limad-windows/prefix/**",
            "**/limad-windows/apps/*/prefix/**",
            "**/.var/app/com.usebottles.bottles/data/bottles/bottles/**",
            "**/limad-windows/cache/**",
        ])
    return values


def backup(target: Path, password: str, categories: dict | None = None, progress: Callable[[str], None] | None = None) -> dict:
    ensure_dependencies()
    if len(password) < 10:
        raise LiSaveError("Das Backup-Passwort muss mindestens zehn Zeichen lang sein.")
    categories = {**DEFAULT_CATEGORIES, **(categories or {})}
    bundle = bundle_path(target)
    ensure_external_target(bundle)
    if progress:
        progress("Backup-Ziel wird vorbereitet …")
    ensure_repository(bundle, password)
    stage, manifest = create_stage(categories)
    sources = category_sources(categories)
    all_sources = [path for values in sources.values() for path in values]
    all_sources.append(stage)
    exclude_file = stage / "exclude.txt"
    exclude_file.write_text("\n".join(exclusions(categories, bundle)) + "\n", encoding="utf-8")
    if progress:
        progress("Persönliche Daten und Einstellungen werden verschlüsselt gesichert …")
    try:
        result = restic(bundle, password, [
            "backup", "--json", "--tag", "lisave", "--tag", f"lisave-{VERSION}",
            "--exclude-file", str(exclude_file), *[str(path) for path in all_sources]
        ], timeout=None)
        retention = load_config().get("retention", {"daily": 7, "weekly": 4, "monthly": 6})
        if progress:
            progress("Alte Sicherungsstände werden nach der Aufbewahrungsregel bereinigt …")
        restic(bundle, password, [
            "forget", "--tag", "lisave",
            "--keep-daily", str(int(retention.get("daily", 7))),
            "--keep-weekly", str(int(retention.get("weekly", 4))),
            "--keep-monthly", str(int(retention.get("monthly", 6))),
            "--prune"
        ], timeout=None)
        metadata = {
            "format": 1,
            "name": bundle.name,
            "lastBackup": now_iso(),
            "hostname": manifest["hostname"],
            "lisaveVersion": VERSION,
            "categories": categories,
        }
        save_json(bundle / "lisave.json", metadata)
        os.chmod(bundle / "lisave.json", 0o600)
        report = {
            "ok": True,
            "bundle": str(bundle),
            "createdAt": metadata["lastBackup"],
            "output": result.stdout,
            "analysis": analyze(categories),
        }
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        save_json(REPORT_DIR / f"backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json", report)
        return report
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def snapshot_list(bundle: Path, password: str) -> list[dict]:
    result = restic(bundle, password, ["snapshots", "--json", "--tag", "lisave"])
    try:
        values = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise LiSaveError("Sicherungsstände konnten nicht gelesen werden.") from exc
    return values if isinstance(values, list) else []


def latest_snapshot(bundle: Path, password: str) -> dict:
    snapshots = snapshot_list(bundle, password)
    if not snapshots:
        raise LiSaveError("Im ausgewählten LiSave-Backup wurde kein Sicherungsstand gefunden.")
    return max(snapshots, key=lambda item: item.get("time", ""))


def copy_item(source: Path, destination: Path) -> None:
    if source.is_dir() and not source.is_symlink():
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination, dirs_exist_ok=True, symlinks=True)
    elif source.exists() or source.is_symlink():
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and destination.is_dir():
            shutil.rmtree(destination)
        elif destination.exists() or destination.is_symlink():
            destination.unlink()
        if source.is_symlink():
            destination.symlink_to(os.readlink(source))
        else:
            shutil.copy2(source, destination)


def install_flatpaks(apps: list[dict], progress: Callable[[str], None] | None = None) -> list[dict]:
    failures = []
    if not shutil.which("flatpak"):
        return [{"id": item.get("id", ""), "error": "Flatpak fehlt"} for item in apps]
    remotes = run(["flatpak", "remotes", "--user", "--columns=name"]).stdout.splitlines()
    if "flathub" not in remotes:
        run(["flatpak", "remote-add", "--user", "--if-not-exists", "flathub", "https://dl.flathub.org/repo/flathub.flatpakrepo"])
    for item in apps:
        app_id = str(item.get("id") or "").strip()
        if not app_id:
            continue
        if progress:
            progress(f"Programm wird aus dem Internet installiert: {app_id}")
        if run(["flatpak", "info", "--user", app_id]).returncode == 0 or run(["flatpak", "info", "--system", app_id]).returncode == 0:
            continue
        remote = str(item.get("origin") or "flathub")
        result = run(["flatpak", "install", "--user", "--noninteractive", "-y", remote, app_id])
        if result.returncode:
            result = run(["flatpak", "install", "--user", "--noninteractive", "-y", "flathub", app_id])
        if result.returncode:
            failures.append({"id": app_id, "error": result.stdout.strip()})
    return failures


def stop_apps() -> None:
    for app_id in ("app.zen_browser.zen", "io.github.zen_browser.zen", "org.mozilla.thunderbird_esr", "org.mozilla.thunderbird", "org.mozilla.Thunderbird"):
        run(["flatpak", "kill", app_id])
    run(["pkill", "-f", "limad-study"])
    run(["pkill", "-f", "limad-notes"])


def restore_dconf(stage: Path) -> list[str]:
    failures = []
    entries = load_json(stage / "dconf.json", [])
    for item in entries if isinstance(entries, list) else []:
        path = str(item.get("path") or "")
        source = stage / str(item.get("file") or "")
        if not path.startswith("/") or not source.is_file():
            continue
        result = run(["dconf", "load", path], input_text=source.read_text(encoding="utf-8"))
        if result.returncode:
            failures.append(path)
    return failures


def find_stage(restore_root: Path) -> Path:
    matches = []
    for candidate in restore_root.rglob("manifest.json"):
        parts = candidate.parts
        marker = (".local", "state", "limad-save", "snapshots")
        if any(tuple(parts[index:index + len(marker)]) == marker for index in range(len(parts) - len(marker) + 1)):
            matches.append(candidate)
    if not matches:
        raise LiSaveError("Das LiSave-Manifest fehlt im Sicherungsstand.")
    return max(matches, key=lambda path: path.stat().st_mtime).parent


def restore(target: Path, password: str, categories: dict | None = None, progress: Callable[[str], None] | None = None) -> dict:
    ensure_dependencies()
    bundle = bundle_path(target)
    if not (repository_path(bundle) / "config").is_file():
        raise LiSaveError("Der ausgewählte Ordner ist kein gültiges LiSave-Backup.")
    snapshot = latest_snapshot(bundle, password)
    categories = {**DEFAULT_CATEGORIES, **(categories or {})}
    if progress:
        progress("Backup wird geprüft und temporär entschlüsselt …")
    with tempfile.TemporaryDirectory(prefix="lisave-restore-") as temporary:
        restore_root = Path(temporary)
        restic(bundle, password, ["restore", str(snapshot["id"]), "--target", str(restore_root)], timeout=None)
        stage = find_stage(restore_root)
        manifest = load_json(stage / "manifest.json", {})
        old_home = Path(str(manifest.get("home") or ""))
        if not old_home.is_absolute() or old_home == Path("/"):
            raise LiSaveError("Ungültiger Benutzerpfad im LiSave-Manifest.")
        restored_home = restore_root / old_home.relative_to("/")
        apps = manifest.get("flatpaks", []) if isinstance(manifest, dict) else []
        flatpak_failures = install_flatpaks(apps if isinstance(apps, list) else [], progress)
        stop_apps()
        restored = []
        source_map = manifest.get("sources", {}) if isinstance(manifest, dict) else {}
        for category, enabled in categories.items():
            if not enabled or category == "windows_full":
                continue
            for original in source_map.get(category, []) if isinstance(source_map, dict) else []:
                original_path = Path(str(original))
                try:
                    relative = original_path.relative_to(old_home)
                except ValueError:
                    continue
                source = restored_home / relative
                destination = HOME / relative
                if source.exists() or source.is_symlink():
                    if progress:
                        progress(f"Wird wiederhergestellt: {destination}")
                    copy_item(source, destination)
                    restored.append(str(destination))
        dconf_failures = restore_dconf(stage) if categories.get("settings", True) else []
        study_import = ""
        if categories.get("study", True) and not (DATA_HOME / "limad-study/study.db").is_file():
            backups = list((stage / "study").glob("*.jwlibrary"))
            if backups:
                result = run(["/usr/local/bin/limad-study", str(backups[-1]), "--prepare-only"], timeout=None)
                if result.returncode:
                    study_import = result.stdout.strip()
        if Path("/usr/local/bin/limad-user-folders-setup").is_file():
            run(["/usr/local/bin/limad-user-folders-setup"])
        if Path("/usr/local/bin/limad-zen-deutsch-setup").is_file():
            run(["/usr/local/bin/limad-zen-deutsch-setup"])
        windows_pending = []
        windows_file = stage / "windows/apps.json"
        if categories.get("windows", True) and windows_file.is_file():
            values = load_json(windows_file, [])
            if isinstance(values, list):
                windows_pending = [str(item.get("name") or item.get("exe") or "Windows-Programm") for item in values if isinstance(item, dict)]
        report = {
            "ok": True,
            "restoredAt": now_iso(),
            "snapshot": snapshot.get("id"),
            "restored": restored,
            "flatpakFailures": flatpak_failures,
            "dconfFailures": dconf_failures,
            "studyImportError": study_import,
            "windowsProgramsPrepared": windows_pending,
        }
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        report_path = REPORT_DIR / f"restore-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        save_json(report_path, report)
        report["report"] = str(report_path)
        return report


def verify(target: Path, password: str, full: bool = False) -> dict:
    bundle = bundle_path(target)
    args = ["check"]
    if full:
        args.append("--read-data")
    result = restic(bundle, password, args, timeout=None)
    return {"ok": True, "output": result.stdout}


def configure_automatic(target: Path, password: str, categories: dict, enabled: bool, before_update: bool = True) -> dict:
    bundle = bundle_path(target)
    ensure_external_target(bundle)
    ensure_repository(bundle, password)
    config = load_config()
    config.update({
        "bundle": str(bundle),
        "categories": {**DEFAULT_CATEGORIES, **categories},
        "automatic": bool(enabled),
        "before_update": bool(before_update),
        "updatedAt": now_iso(),
    })
    save_config(config)
    if enabled or before_update:
        secret_store(bundle, password)
    if enabled:
        run(["systemctl", "--user", "daemon-reload"])
        result = run(["systemctl", "--user", "enable", "--now", "limad-save.timer"])
        if result.returncode:
            raise LiSaveError(result.stdout.strip() or "Automatische Sicherung konnte nicht aktiviert werden.")
    else:
        run(["systemctl", "--user", "disable", "--now", "limad-save.timer"])
    return config


def scheduled(mode: str = "timer", progress: Callable[[str], None] | None = None) -> dict:
    config = load_config()
    if mode == "timer" and not config.get("automatic"):
        return {"ok": True, "skipped": "automatic-disabled"}
    if mode == "pre-update" and not config.get("before_update", True):
        return {"ok": True, "skipped": "pre-update-disabled"}
    bundle_value = str(config.get("bundle") or "")
    if not bundle_value:
        return {"ok": True, "skipped": "not-configured"}
    bundle = Path(bundle_value)
    parent = bundle.parent
    if not parent.exists():
        return {"ok": True, "skipped": "target-not-connected"}
    password = secret_lookup(bundle)
    if not password:
        raise LiSaveError("Das LiSave-Passwort ist im GNOME-Schlüsselbund nicht verfügbar.")
    return backup(bundle, password, config.get("categories", {}), progress)

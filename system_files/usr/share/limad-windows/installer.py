#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import tarfile
import tempfile
import sys
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import asdict
from pathlib import Path, PureWindowsPath
from typing import Callable

from recipe_engine import PROFILES, Plan, analyze, dependency_label

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk

APP_ID = "de.limad.WindowsApps"
APP_NAME = "Windows-Programme"
APP_VERSION = "2.2.6"
FALLBACK_ICON = "de.limad.WindowsApps"
HOME = Path(GLib.get_home_dir())
DATA_HOME = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share"))
WIN_HOME = DATA_HOME / "limad-windows"
APPS_HOME = WIN_HOME / "apps"
CACHE_HOME = WIN_HOME / "cache"
REGISTRY = WIN_HOME / "apps.json"
SETTINGS_FILE = WIN_HOME / "settings.json"
GLOBAL_LOG = WIN_HOME / "install.log"
ICON_DIR = WIN_HOME / "icons"
DESKTOP_DIR = DATA_HOME / "applications"
LAUNCHER_DIR = WIN_HOME / "launchers"
LEGACY_PREFIX = WIN_HOME / "prefix"

BOTTLES_APP_ID = "com.usebottles.bottles"
BOTTLES_HOST_DATA = HOME / ".var/app" / BOTTLES_APP_ID / "data"
BOTTLES_STAGE_HOST = WIN_HOME / "bottles-backend"
BOTTLES_BOTTLES_HOST = BOTTLES_HOST_DATA / "bottles" / "bottles"
BOTTLES_RUNNERS_HOST = BOTTLES_HOST_DATA / "bottles" / "runners"
TOOLS_HOME = WIN_HOME / "tools"
WINETRICKS_VERSION = "20260125"
WINETRICKS_ARCHIVE_URL = "https://github.com/Winetricks/winetricks/archive/refs/tags/20260125.tar.gz"
WINETRICKS_ARCHIVE_SHA256 = "2890bd9fbbade4638e58b4999a237273192df03b58516ae7b8771e09c22d2f56"

BOTTLES_DEPENDENCY_MAP = {
    "vcrun2005": "vcredist2005",
    "vcrun2008": "vcredist2008",
    "vcrun2010": "vcredist2010",
    "vcrun2012": "vcredist2012",
    "vcrun2013": "vcredist2013",
    "vcrun2015": "vcredist2015",
    "vcrun2019": "vcredist2019",
    "vcrun2022": "vcredist2022",
    "dotnet35": "dotnet35",
    "dotnet40": "dotnet40",
    "dotnet46": "dotnet46",
    "dotnet48": "dotnet48",
    "d3dx9": "d3dx9",
    "d3dcompiler_47": "d3dcompiler_47",
    "riched20": "riched20",
    "msxml6": "msxml6",
    "allfonts": "allfonts",
    "corefonts": "corefonts",
}


SKIP_PATTERNS = re.compile(
    r"(unins|uninstall|setup|installer|updater|update|crashpad|crashreport|"
    r"vcredist|dotnet|repair|helper|service|daemon|report|debug)",
    re.IGNORECASE,
)

DEFAULT_SETTINGS = {
    "install_optional_dependencies": True,
    "continue_after_dependency_error": True,
    "create_shortcuts": True,
    "keep_installer_copy": False,
    "dependency_retries": 2,
    "auto_install_bottles": True,
    "prefer_bottles": True,
}

WINETRICKS_DEPENDENCIES = {
    "vcrun2005", "vcrun2008", "vcrun2010", "vcrun2012", "vcrun2013",
    "vcrun2015", "vcrun2019", "dotnet35", "dotnet40",
    "dotnet46", "d3dx9", "d3dcompiler_47", "dxvk", "vkd3d",
    "riched20", "msxml6",
}

RUNTIME_DOWNLOADS = {
    "dotnet48": {
        "win32": "https://download.visualstudio.microsoft.com/download/pr/7afca223-55d2-470a-8edc-6a1739ae3252/abd170b4b0ec15ad0222a809b761a036/ndp48-x86-x64-allos-enu.exe",
        "win64": "https://download.visualstudio.microsoft.com/download/pr/7afca223-55d2-470a-8edc-6a1739ae3252/abd170b4b0ec15ad0222a809b761a036/ndp48-x86-x64-allos-enu.exe",
        "args": ["/q", "/norestart"],
        "filename": "ndp48-x86-x64-allos-enu.exe",
    },
    "vcrun2022": {
        "win32": "https://aka.ms/vs/17/release/vc_redist.x86.exe",
        "win64": "https://aka.ms/vs/17/release/vc_redist.x64.exe",
        "args": ["/install", "/quiet", "/norestart"],
        "filename_win32": "vc_redist_2022_x86.exe",
        "filename_win64": "vc_redist_2022_x64.exe",
    },
    "webview2": {
        "win32": "https://go.microsoft.com/fwlink/p/?LinkId=2124703",
        "win64": "https://go.microsoft.com/fwlink/p/?LinkId=2124703",
        "args": ["/silent", "/install"],
        "filename": "MicrosoftEdgeWebview2Setup.exe",
    },
    "dotnetdesktop6": {
        "win32": "https://aka.ms/dotnet/6.0/windowsdesktop-runtime-win-x86.exe",
        "win64": "https://aka.ms/dotnet/6.0/windowsdesktop-runtime-win-x64.exe",
        "args": ["/install", "/quiet", "/norestart"],
        "filename": "windowsdesktop-runtime-6.exe",
    },
    "dotnetdesktop8": {
        "win32": "https://aka.ms/dotnet/8.0/windowsdesktop-runtime-win-x86.exe",
        "win64": "https://aka.ms/dotnet/8.0/windowsdesktop-runtime-win-x64.exe",
        "args": ["/install", "/quiet", "/norestart"],
        "filename": "windowsdesktop-runtime-8.exe",
    },
    "dotnetdesktop9": {
        "win32": "https://aka.ms/dotnet/9.0/windowsdesktop-runtime-win-x86.exe",
        "win64": "https://aka.ms/dotnet/9.0/windowsdesktop-runtime-win-x64.exe",
        "args": ["/install", "/quiet", "/norestart"],
        "filename": "windowsdesktop-runtime-9.exe",
    },
}

MANUAL_DEPENDENCIES = {
    "java": "Java muss vom jeweiligen Programm mitgeliefert oder als separater Installer ausgewählt werden.",
    "access2016": "Die passende 32-/64-Bit-Version der Access Database Engine muss separat bereitgestellt werden.",
    "localdb": "SQL Server LocalDB ist unter Wine nicht zuverlässig automatisierbar.",
}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def ensure_dirs() -> None:
    for path in (WIN_HOME, APPS_HOME, CACHE_HOME, ICON_DIR, DESKTOP_DIR, LAUNCHER_DIR):
        path.mkdir(parents=True, exist_ok=True)


def log(message: str, log_file: Path | None = None) -> None:
    ensure_dirs()
    line = f"{now()} {message}\n"
    with GLOBAL_LOG.open("a", encoding="utf-8") as handle:
        handle.write(line)
    if log_file and log_file != GLOBAL_LOG:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(line)


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def load_settings() -> dict:
    data = load_json(SETTINGS_FILE, {})
    return {**DEFAULT_SETTINGS, **data}


def save_settings(settings: dict) -> None:
    save_json(SETTINGS_FILE, settings)



def use_bottles_backend(plan: Plan) -> bool:
    settings = load_settings()
    if not settings.get("prefer_bottles", True):
        return False
    return plan.profile != "minimal" or bool(plan.dependencies or plan.optional_dependencies)


def bottle_name_for(environment: str) -> str:
    return f"LiMaD-{environment}"[:62]


def bottles_flatpak_installed() -> bool:
    if shutil.which("flatpak") is None:
        return False
    result = subprocess.run(
        ["flatpak", "info", BOTTLES_APP_ID],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def run_host_process(args: list[str], log_file: Path, timeout: int | None = None) -> tuple[int, str]:
    log("run host: " + " ".join(shlex.quote(part) for part in args), log_file)
    try:
        proc = subprocess.run(
            args,
            timeout=timeout,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        if output:
            log(output[-120000:], log_file)
        log("host process timeout", log_file)
        return 124, output
    except OSError as exc:
        log(f"host process error: {exc}", log_file)
        return 127, str(exc)
    output = proc.stdout or ""
    if output:
        log(output[-120000:], log_file)
    log(f"host return code: {proc.returncode}", log_file)
    return proc.returncode, output


def ensure_bottles(log_file: Path, progress: Callable[[str, float], None] | None = None) -> tuple[bool, str]:
    if shutil.which("flatpak") is None:
        return False, "Flatpak ist nicht installiert. Bottles kann daher nicht eingerichtet werden."
    if bottles_flatpak_installed():
        return True, ""
    if not load_settings().get("auto_install_bottles", True):
        return False, "Bottles ist nicht installiert. Aktiviere die automatische Installation in den Einstellungen."
    if progress:
        progress("Flathub wird vorbereitet", 0.03)
    code, output = run_host_process(
        ["flatpak", "remote-add", "--user", "--if-not-exists", "flathub", "https://flathub.org/repo/flathub.flatpakrepo"],
        log_file,
        300,
    )
    if code != 0:
        return False, "Flathub konnte nicht eingerichtet werden. Details stehen im Protokoll."
    if progress:
        progress("Bottles wird aus Flathub installiert", 0.08)
    code, output = run_host_process(
        ["flatpak", "install", "--user", "-y", "flathub", BOTTLES_APP_ID],
        log_file,
        3600,
    )
    if code != 0 or not bottles_flatpak_installed():
        return False, "Bottles konnte nicht aus Flathub installiert werden. Details stehen im Protokoll."
    return True, ""


def stage_bottles_installer(path: Path, environment: str) -> Path:
    host_dir = BOTTLES_STAGE_HOST / "installers" / environment
    host_dir.mkdir(parents=True, exist_ok=True)
    host_path = host_dir / path.name
    if path.resolve() != host_path.resolve():
        shutil.copy2(path, host_path)
    return host_path


def bottles_dependencies(plan: Plan, include_optional: bool = True) -> list[str]:
    requested = list(plan.dependencies)
    if include_optional:
        requested.extend(plan.optional_dependencies)
    supported = {
        "vcrun2005", "vcrun2008", "vcrun2010", "vcrun2012", "vcrun2013",
        "vcrun2015", "vcrun2019", "vcrun2022", "dotnet35", "dotnet40",
        "dotnet46", "dotnet48", "d3dx9", "d3dcompiler_47", "riched20",
        "msxml6", "allfonts", "corefonts", "dxvk", "vkd3d",
    }
    return [item for item in dict.fromkeys(requested) if item in supported]


def _prefix_is_ready(prefix: Path) -> bool:
    drive_c = prefix / "drive_c"
    if not drive_c.is_dir():
        return False
    metadata = (prefix / "bottle.yml").is_file() or (prefix / "bottle.yaml").is_file()
    registry = (prefix / "system.reg").is_file() or (prefix / "user.reg").is_file()
    windows = (drive_c / "windows").is_dir()
    return metadata or registry or windows


def bottle_is_ready(bottle: str) -> bool:
    return _prefix_is_ready(bottles_host_prefix("", bottle))


def _runner_executable_host(runner: str) -> Path | None:
    directory = BOTTLES_RUNNERS_HOST / runner / "bin"
    for name in ("wine", "wine64"):
        candidate = directory / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def _scan_managed_runners() -> list[str]:
    if not BOTTLES_RUNNERS_HOST.is_dir():
        return []
    runners = []
    for directory in sorted(BOTTLES_RUNNERS_HOST.iterdir()):
        if directory.is_dir() and _runner_executable_host(directory.name):
            runners.append(directory.name)
    return runners


def _official_cli_runners(log_file: Path) -> list[str]:
    code, output = run_host_process(
        [
            "flatpak", "run", "--command=bottles-cli", BOTTLES_APP_ID,
            "--json", "list", "components", "-f", "category:runners",
        ],
        log_file,
        90,
    )
    if code != 0:
        return []
    candidates = []
    for line in reversed(output.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        raw = data.get("runners") if isinstance(data, dict) else None
        if isinstance(raw, list):
            candidates = [str(item) for item in raw if item]
            break
    valid = []
    for runner in candidates:
        if runner.startswith("sys-"):
            continue
        if _runner_executable_host(runner):
            valid.append(runner)
    return valid


def _preferred_runner(runners: list[str]) -> str:
    def score(name: str) -> tuple[int, str]:
        lower = name.lower()
        if lower.startswith("caffe-"):
            return (0, lower)
        if lower.startswith("soda-"):
            return (1, lower)
        if lower.startswith("vaniglia-"):
            return (2, lower)
        return (3, lower)
    return sorted(runners, key=score)[0] if runners else ""


def bootstrap_bottles_components(
    log_file: Path,
    progress: Callable[[str, float], None] | None = None,
) -> tuple[bool, str, str]:
    runners = list(dict.fromkeys(_official_cli_runners(log_file) + _scan_managed_runners()))
    if runners:
        runner = _preferred_runner(runners)
        if progress:
            progress(f"Bottles ist mit {runner} bereit", 0.12)
        return True, "", runner

    if progress:
        progress("Bottles wird einmalig vorbereitet", 0.08)
    log("No managed Bottles runner found; launching official Bottles first-run UI.", log_file)
    try:
        subprocess.Popen(
            ["flatpak", "run", BOTTLES_APP_ID],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        return False, f"Bottles konnte zur Erstvorbereitung nicht geöffnet werden: {exc}", ""

    deadline = time.monotonic() + 900
    next_cli_check = 0.0
    while time.monotonic() < deadline:
        runners = _scan_managed_runners()
        if time.monotonic() >= next_cli_check:
            runners = list(dict.fromkeys(runners + _official_cli_runners(log_file)))
            next_cli_check = time.monotonic() + 30
        if runners:
            runner = _preferred_runner(runners)
            run_host_process(["flatpak", "kill", BOTTLES_APP_ID], log_file, 30)
            if progress:
                progress(f"Wine-Runner {runner} ist bereit", 0.12)
            return True, "", runner
        elapsed = 900 - max(0, int(deadline - time.monotonic()))
        if progress:
            progress(
                "Bottles lädt beim ersten Start seine Grundkomponenten. Das Bottles-Fenster geöffnet lassen.",
                min(0.115, 0.08 + 0.035 * elapsed / 900),
            )
        time.sleep(5)

    return False, (
        "Bottles hat innerhalb von 15 Minuten keinen verwalteten Wine-Runner bereitgestellt. "
        "Bitte Internetverbindung prüfen und den ersten Bottles-Start vollständig abschließen."
    ), ""


def _winetricks_script(log_file: Path, progress: Callable[[str, float], None] | None = None) -> tuple[bool, str, Path | None]:
    target = TOOLS_HOME / f"winetricks-{WINETRICKS_VERSION}"
    if target.is_file():
        try:
            head = target.read_text(encoding="utf-8", errors="ignore")[:4096]
            if f"WINETRICKS_VERSION={WINETRICKS_VERSION}" in head:
                return True, "", target
        except OSError:
            pass

    TOOLS_HOME.mkdir(parents=True, exist_ok=True)
    if progress:
        progress(f"Winetricks {WINETRICKS_VERSION} wird geprüft", 0.16)
    archive = TOOLS_HOME / f"winetricks-{WINETRICKS_VERSION}.tar.gz"
    try:
        request = urllib.request.Request(WINETRICKS_ARCHIVE_URL, headers={"User-Agent": "LiMaD-Windows-Programme/2.2.2"})
        with urllib.request.urlopen(request, timeout=60) as response, archive.open("wb") as handle:
            shutil.copyfileobj(response, handle)
    except Exception as exc:
        return False, f"Winetricks konnte nicht von GitHub geladen werden: {exc}", None
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest.lower() != WINETRICKS_ARCHIVE_SHA256.lower():
        archive.unlink(missing_ok=True)
        return False, "Die SHA-256-Prüfsumme des Winetricks-Archivs stimmt nicht.", None
    try:
        with tempfile.TemporaryDirectory(prefix="limad-winetricks-") as temp:
            with tarfile.open(archive, "r:gz") as tar:
                try:
                    tar.extractall(temp, filter="data")
                except TypeError:
                    tar.extractall(temp)
            candidates = list(Path(temp).glob("winetricks-*/src/winetricks"))
            if not candidates:
                raise FileNotFoundError("src/winetricks fehlt im Archiv")
            shutil.copy2(candidates[0], target)
            target.chmod(0o755)
    except Exception as exc:
        return False, f"Winetricks konnte nicht vorbereitet werden: {exc}", None
    finally:
        archive.unlink(missing_ok=True)
    return True, "", target


def _sandbox_bottles_root() -> Path:
    return BOTTLES_HOST_DATA / "bottles"


def _run_winetricks_dependency(
    bottle: str,
    runner: str,
    dependency: str,
    script: Path,
    log_file: Path,
) -> tuple[bool, str]:
    runner_exe = _runner_executable_host(runner)
    if runner_exe is None:
        return False, f"Der Bottles-Runner {runner} ist nicht vollständig installiert."
    host_root = BOTTLES_HOST_DATA / "bottles"
    try:
        relative_runner = runner_exe.relative_to(host_root)
    except ValueError:
        return False, f"Der Runner-Pfad liegt außerhalb des Bottles-Datenverzeichnisses: {runner_exe}"
    sandbox_root = _sandbox_bottles_root()
    sandbox_wine = sandbox_root / relative_runner
    sandbox_wineserver = sandbox_wine.with_name("wineserver")
    host_prefix = bottles_host_prefix("", bottle)
    try:
        relative_prefix = host_prefix.relative_to(host_root)
    except ValueError:
        return False, f"Der Bottle-Pfad liegt außerhalb des Bottles-Datenverzeichnisses: {host_prefix}"
    sandbox_prefix = sandbox_root / relative_prefix

    base_args = [
        "flatpak", "run",
        f"--filesystem={script.parent}:ro",
        f"--env=WINEPREFIX={sandbox_prefix}",
        f"--env=WINE={sandbox_wine}",
        f"--env=WINESERVER={sandbox_wineserver}",
        "--env=WINEARCH=win64",
        "--env=WINEDEBUG=-all",
        "--env=WINETRICKS_SUPER_QUIET=1",
    ]

    def reset_wineserver() -> None:
        reset_args = base_args + [
            "--command=sh", BOTTLES_APP_ID,
            "-lc", '"$WINESERVER" -k >/dev/null 2>&1 || true; sleep 2',
        ]
        run_host_process(reset_args, log_file, 30)

    ignored = (
        'F: Not sharing "/usr/share/themes"',
        'F: Not sharing "/usr/share/icons"',
    )
    last_code = 1
    last_output = ""
    for attempt in range(1, 3):
        if attempt > 1:
            log(f"retry winetricks dependency after wineserver reset: {dependency}", log_file)
            reset_wineserver()
        args = base_args + [
            "--command=sh", BOTTLES_APP_ID,
            str(script), "-q", dependency,
        ]
        last_code, last_output = run_host_process(args, log_file, 7200)
        if last_code == 0:
            reset_wineserver()
            return True, ""
        text = last_output.lower()
        transient = any(marker in text for marker in (
            "recvmsg", "connection reset", "verbindung wurde vom kommunikationspartner zurückgesetzt",
            "wineserver", "wine client error",
        ))
        if attempt == 1 and (transient or dependency in {"corefonts", "allfonts"}):
            continue
        break

    meaningful = [
        line.strip() for line in last_output.splitlines()
        if line.strip() and not line.strip().startswith(ignored)
    ]
    tail = " ".join(meaningful[-20:])
    detail = f" Letzte Ausgabe: {tail[:1400]}" if tail else ""
    return False, f"Winetricks-Abhängigkeit {dependency} ist mit Code {last_code} fehlgeschlagen.{detail}"


def prepare_bottle_dependencies(
    bottle: str,
    runner: str,
    dependencies: list[str],
    log_file: Path,
    progress: Callable[[str, float], None] | None = None,
) -> tuple[bool, str, dict]:
    ok, error, script = _winetricks_script(log_file, progress)
    if not ok or script is None:
        return False, error, {}
    state_file = BOTTLES_STAGE_HOST / "state" / f"{bottle}.json"
    state = load_json(state_file, {"bottle": bottle, "dependencies": []})
    installed = set(state.get("dependencies", [])) if isinstance(state, dict) else set()
    requested = list(dict.fromkeys(dependencies))
    for index, dependency in enumerate(requested, start=1):
        if dependency in installed:
            if progress:
                progress(f"{dependency} ist bereits vorbereitet", 0.18 + 0.30 * index / max(1, len(requested)))
            continue
        if progress:
            progress(
                f"{dependency} wird in der Bottles-Umgebung installiert",
                0.18 + 0.30 * (index - 1) / max(1, len(requested)),
            )
        success, message = _run_winetricks_dependency(bottle, runner, dependency, script, log_file)
        if not success:
            return False, message, {"installed_dependencies": sorted(installed)}
        installed.add(dependency)
        save_json(state_file, {"bottle": bottle, "runner": runner, "dependencies": sorted(installed)})
    return True, "", {
        "bottle": bottle,
        "bottle_path": str(bottles_host_prefix("", bottle)),
        "installed_dependencies": sorted(installed),
        "runner": runner,
    }


def ensure_bottle_cli(
    bottle: str,
    runner: str,
    log_file: Path,
    progress: Callable[[str, float], None] | None = None,
) -> tuple[bool, str]:
    if bottle_is_ready(bottle):
        return True, ""
    expected = bottles_host_prefix("", bottle)
    if expected.exists() and not _prefix_is_ready(expected):
        has_payload = any(expected.iterdir()) if expected.is_dir() else True
        if has_payload:
            return False, (
                f"Die vorhandene Bottles-Umgebung ist unvollständig und wurde aus Sicherheitsgründen nicht gelöscht: {expected}. "
                "Bitte im Bereich Umgebungen reparieren oder gezielt entfernen."
            )
        expected.rmdir()
    state_file = BOTTLES_STAGE_HOST / "state" / f"{bottle}.json"
    state_file.unlink(missing_ok=True)
    if progress:
        progress("Eigene Bottles-Umgebung wird angelegt", 0.14)
    args = [
        "flatpak", "run", "--command=bottles-cli", BOTTLES_APP_ID,
        "new", "--bottle-name", bottle, "--environment", "application",
        "--arch", "win64", "--runner", runner,
    ]
    code, output = run_host_process(args, log_file, 3600)
    for _ in range(90):
        if bottle_is_ready(bottle):
            return True, ""
        time.sleep(1)
    lowered = output.lower()
    if "fail to install components" in lowered or "no managed runners found" in lowered:
        reason = "Bottles konnte die Bottle trotz vorhandenem Runner nicht vollständig anlegen."
    elif code == 0:
        reason = "Bottles meldete Erfolg, aber die Wine-Umgebung wurde nicht vollständig angelegt."
    else:
        reason = f"Bottles beendete die Bottle-Erstellung mit Code {code}."
    tail = " ".join(line.strip() for line in output.splitlines()[-12:] if line.strip())
    detail = f" Letzte Bottles-Ausgabe: {tail[:900]}" if tail else ""
    return False, reason + detail


def _normalized_bottle_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def bottles_host_prefix(bottle_path: str, bottle_name: str) -> Path:
    path = bottle_path.strip() if bottle_path else ""
    if path and Path(path).is_absolute():
        marker = "/.local/share/bottles/bottles/"
        if marker in path:
            suffix = path.split(marker, 1)[1].lstrip("/")
            candidate = BOTTLES_BOTTLES_HOST / suffix
            if candidate.exists():
                return candidate
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", bottle_name).strip("-")
    candidates = [BOTTLES_BOTTLES_HOST / sanitized, BOTTLES_BOTTLES_HOST / bottle_name]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    wanted = _normalized_bottle_name(bottle_name)
    if BOTTLES_BOTTLES_HOST.is_dir() and wanted:
        for candidate in sorted(BOTTLES_BOTTLES_HOST.iterdir()):
            if candidate.is_dir() and _normalized_bottle_name(candidate.name) == wanted:
                return candidate
    return candidates[0]


def bottles_windows_path(exe: Path, prefix: Path) -> str:
    drive_c = prefix / "drive_c"
    try:
        relative = exe.resolve().relative_to(drive_c.resolve())
    except (OSError, ValueError):
        return str(exe)
    return "C:\\" + str(relative).replace("/", "\\")


def run_bottles_executable(bottle: str, executable: str, log_file: Path | None = None, timeout: int | None = None) -> int:
    selected_log = log_file or GLOBAL_LOG
    exe_path = Path(executable)
    args = [
        "flatpak", "run", f"--filesystem={exe_path.parent}:ro",
        "--command=bottles-cli", BOTTLES_APP_ID,
        "run", "-b", bottle, "-e", str(exe_path),
    ]
    code, _ = run_host_process(args, selected_log, timeout)
    return code


def refresh_desktop_database() -> None:
    command = shutil.which("update-desktop-database")
    if command:
        subprocess.run([command, str(DESKTOP_DIR)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def bottles_launcher_path(name: str, environment: str) -> Path:
    return LAUNCHER_DIR / f"limad-win-{slugify(f'{name}-{environment}')}.sh"


def write_bottles_launcher(name: str, exe_windows: str, bottle: str, environment: str) -> Path:
    """Create a per-program shell launcher so Desktop Entry quoting never touches a Windows path."""
    LAUNCHER_DIR.mkdir(parents=True, exist_ok=True)
    path = bottles_launcher_path(name, environment)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "#!/usr/bin/env bash\n"
        "set -Eeuo pipefail\n"
        "exec flatpak run --command=bottles-cli com.usebottles.bottles run "
        f"-b {shlex.quote(bottle)} -e {shlex.quote(exe_windows)}\n",
        encoding="utf-8",
    )
    temporary.chmod(0o755)
    temporary.replace(path)
    return path


def desktop_text(value: str) -> str:
    return str(value).replace("\r", " ").replace("\n", " ").strip()


def write_bottles_desktop_entry(name: str, exe_windows: str, icon: str, bottle: str, environment: str) -> Path:
    DESKTOP_DIR.mkdir(parents=True, exist_ok=True)
    slug = slugify(f"{name}-{environment}")
    path = DESKTOP_DIR / f"limad-win-{slug}.desktop"
    launcher = write_bottles_launcher(name, exe_windows, bottle, environment)
    wm_class = desktop_text(PureWindowsPath(exe_windows).name or name)
    metadata_exe = desktop_text(exe_windows.replace("\\", "/"))
    path.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Version=1.0\n"
        f"Name={desktop_text(name)}\n"
        "Comment=Windows-Programm über Bottles in LiMaD OS\n"
        f"Exec={launcher}\n"
        f"TryExec={launcher}\n"
        f"Icon={desktop_text(icon)}\n"
        "Terminal=false\n"
        "Categories=Utility;\n"
        "StartupNotify=true\n"
        f"StartupWMClass={wm_class}\n"
        f"X-GNOME-WMClass={wm_class}\n"
        f"X-LiMaD-Bottles-Name={desktop_text(bottle)}\n"
        f"X-LiMaD-Windows-Exe={metadata_exe}\n"
        f"X-LiMaD-Windows-Environment={desktop_text(environment)}\n"
        f"X-LiMaD-Launcher={launcher}\n",
        encoding="utf-8",
    )
    path.chmod(0o644)
    refresh_desktop_database()
    return path


def shell_settings() -> Gio.Settings | None:
    source = Gio.SettingsSchemaSource.get_default()
    schema = source.lookup("org.gnome.shell", True) if source else None
    return Gio.Settings.new_full(schema, None, None) if schema is not None else None


def is_desktop_entry_pinned(desktop_path: Path) -> bool:
    try:
        settings = shell_settings()
        return bool(settings and desktop_path.name in settings.get_strv("favorite-apps"))
    except Exception:
        return False


def pin_desktop_entry_to_dock(desktop_path: Path) -> bool:
    """Pin a registered user Desktop Entry to the GNOME dock without duplicating it."""
    desktop_id = desktop_path.name
    try:
        # Force a fresh desktop-app lookup before writing favorite-apps.
        refresh_desktop_database()
        for _ in range(15):
            if Gio.DesktopAppInfo.new(desktop_id) is not None:
                break
            time.sleep(0.1)
        settings = shell_settings()
        if settings is None:
            log(f"GNOME dock schema unavailable; could not pin {desktop_id}")
            return False
        favorites = list(settings.get_strv("favorite-apps"))
        if desktop_id not in favorites:
            favorites.append(desktop_id)
            if not settings.set_strv("favorite-apps", favorites):
                log(f"GNOME dock rejected favorite {desktop_id}")
                return False
            Gio.Settings.sync()
        verified = desktop_id in settings.get_strv("favorite-apps")
        log(f"GNOME dock favorite {'ready' if verified else 'verification failed'}: {desktop_id}")
        return verified
    except Exception as exc:
        log(f"GNOME dock pin failed for {desktop_id}: {exc}")
        return False


def unpin_desktop_entry_from_dock(desktop_path: Path) -> None:
    desktop_id = desktop_path.name
    try:
        settings = shell_settings()
        if settings is None:
            return
        favorites = list(settings.get_strv("favorite-apps"))
        if desktop_id in favorites:
            settings.set_strv("favorite-apps", [item for item in favorites if item != desktop_id])
            Gio.Settings.sync()
    except Exception as exc:
        log(f"GNOME dock unpin failed for {desktop_id}: {exc}")


def choose_primary_program(programs: list[Path], installer: Path | None) -> Path:
    """Choose the most likely main executable for automatic menu and dock integration."""
    installer_tokens = set()
    if installer is not None:
        installer_tokens = {token for token in re.split(r"[^a-z0-9]+", installer.stem.lower()) if len(token) >= 3}
        installer_tokens -= {"setup", "installer", "install", "desktop", "windows"}

    def score(exe: Path) -> tuple[float, int, str]:
        stem = exe.stem.lower()
        tokens = {token for token in re.split(r"[^a-z0-9]+", stem) if len(token) >= 3}
        overlap = len(tokens & installer_tokens)
        value = overlap * 20.0
        if "desktop" in stem:
            value += 7.0
        if "program files" in str(exe).lower():
            value += 4.0
        try:
            value += min(exe.stat().st_size / (1024 * 1024), 20.0) / 10.0
        except OSError:
            pass
        return value, -len(exe.parts), str(exe).lower()

    return max(programs, key=score)


def load_registry() -> list[dict]:
    data = load_json(REGISTRY, {"version": 2, "applications": []})
    entries = data.get("applications", []) if isinstance(data, dict) else []
    changed = False
    for entry in entries:
        backend = entry.get("backend")
        if backend == "bottles":
            bottle = entry.get("bottle_name", "")
            environment = entry.get("environment_id", "")
            # 2.2.3 accidentally marked Bottles entries without a system-Wine prefix as legacy.
            if (not environment or environment == "legacy") and bottle.startswith("LiMaD-"):
                entry["environment_id"] = bottle.removeprefix("LiMaD-")
                changed = True
            if "prefix" in entry:
                entry.pop("prefix", None)
                changed = True
            continue
        if backend is None:
            entry["backend"] = "system-wine"
            changed = True
        if "prefix" not in entry:
            entry["prefix"] = str(LEGACY_PREFIX)
            changed = True
        if not entry.get("environment_id"):
            entry["environment_id"] = "legacy"
            changed = True
    if changed:
        save_registry(entries)
    return entries


def save_registry(entries: list[dict]) -> None:
    save_json(REGISTRY, {"version": 2, "applications": entries})


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "programm"


def environment_id(path: Path, plan: Plan) -> str:
    digest = hashlib.sha256(f"{path.resolve()}|{path.stat().st_size}|{plan.profile}".encode()).hexdigest()[:8]
    return f"{slugify(path.stem)[:38]}-{digest}"


def env_root(environment: str) -> Path:
    return APPS_HOME / environment


def prefix_for(environment: str) -> Path:
    return env_root(environment) / "prefix"


def state_file(environment: str) -> Path:
    return env_root(environment) / "state.json"


def environment_log(environment: str) -> Path:
    return env_root(environment) / "install.log"


def load_state(environment: str) -> dict:
    return load_json(state_file(environment), {
        "version": 2,
        "environment_id": environment,
        "status": "new",
        "completed_steps": [],
        "dependency_status": {},
        "warnings": [],
        "created": now(),
    })


def save_state(environment: str, state: dict) -> None:
    state["updated"] = now()
    save_json(state_file(environment), state)


def prefix_architecture_file(prefix: Path) -> Path:
    return prefix.parent / "architecture"


def set_prefix_architecture(prefix: Path, architecture: str) -> None:
    value = "win64"
    prefix.parent.mkdir(parents=True, exist_ok=True)
    prefix_architecture_file(prefix).write_text(value + "\n", encoding="utf-8")


def get_prefix_architecture(prefix: Path) -> str:
    marker = prefix_architecture_file(prefix)
    if marker.is_file():
        value = marker.read_text(encoding="utf-8", errors="replace").strip().lower()
        if value in {"win32", "win64"}:
            return value
    return "win64"


def wine_env(prefix: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["WINEPREFIX"] = str(prefix)
    env["WINEARCH"] = get_prefix_architecture(prefix)
    env.setdefault("WINEDEBUG", "-all")
    return env


def have_wine() -> bool:
    return shutil.which("wine") is not None


def prefix_ready(prefix: Path) -> bool:
    return (
        (prefix / "system.reg").is_file()
        and (prefix / "user.reg").is_file()
        and (prefix / "drive_c/windows/system32").is_dir()
    )


def run_process(
    args: list[str],
    prefix: Path,
    log_file: Path,
    timeout: int | None = None,
    cwd: Path | None = None,
) -> int:
    log("run: " + " ".join(shlex.quote(part) for part in args), log_file)
    try:
        proc = subprocess.run(
            args,
            env=wine_env(prefix),
            cwd=str(cwd) if cwd else None,
            timeout=timeout,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
        )
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        if output:
            log(output[-12000:], log_file)
        log("timeout", log_file)
        return 124
    except OSError as exc:
        log(f"process error: {exc}", log_file)
        return 127
    if proc.stdout:
        log(proc.stdout[-12000:], log_file)
    log(f"return code: {proc.returncode}", log_file)
    return proc.returncode


def run_wine(args: list[str], timeout: int | None = None, prefix: Path | None = None, log_file: Path | None = None) -> int:
    selected_prefix = prefix or LEGACY_PREFIX
    selected_log = log_file or GLOBAL_LOG
    return run_process(args, selected_prefix, selected_log, timeout)


def health_check(prefix: Path, log_file: Path) -> bool:
    code = run_process(["wine", "cmd", "/c", "echo LIMAD_WINE_OK"], prefix, log_file, 120)
    return code == 0


def init_prefix(prefix: Path, log_file: Path) -> tuple[bool, str]:
    if not have_wine():
        return False, "Wine ist im Systemabbild nicht installiert."
    prefix.parent.mkdir(parents=True, exist_ok=True)
    if not prefix_ready(prefix):
        code = run_process(["wineboot", "--init"], prefix, log_file, 900)
        wait = run_process(["wineserver", "-w"], prefix, log_file, 900)
        if code != 0 or wait != 0 or not prefix_ready(prefix):
            return False, "Die Wine-WoW64-Umgebung konnte nicht vollständig erstellt werden."
    if not health_check(prefix, log_file):
        return False, "Der Wine-Starttest mit echo LIMAD_WINE_OK ist fehlgeschlagen."
    return True, ""


def dotnet48_ready(prefix: Path) -> bool:
    framework = prefix / "drive_c/windows/Microsoft.NET"
    return any((framework / branch / "v4.0.30319/mscorlib.dll").is_file() for branch in ("Framework64", "Framework"))


def download_runtime(dependency: str, plan: Plan, log_file: Path) -> tuple[bool, str, Path | None]:
    spec = RUNTIME_DOWNLOADS.get(dependency)
    if not spec:
        return False, "Kein automatischer Downloadanbieter vorhanden.", None
    architecture = "win32" if plan.architecture == "win32" else "win64"
    url = spec[architecture]
    filename = spec.get(f"filename_{architecture}") or spec.get("filename")
    if not filename:
        return False, f"Für {dependency} ist kein Dateiname für {architecture} definiert.", None
    destination = CACHE_HOME / filename
    try:
        log(f"download {url} -> {destination}", log_file)
        request = urllib.request.Request(url, headers={"User-Agent": f"LiMaD-Windows/{APP_VERSION}"})
        with urllib.request.urlopen(request, timeout=90) as response, destination.open("wb") as output:
            shutil.copyfileobj(response, output)
        if destination.stat().st_size < 100_000:
            raise RuntimeError("Download ist unerwartet klein")
    except Exception as exc:
        destination.unlink(missing_ok=True)
        return False, f"Download fehlgeschlagen: {exc}", None
    return True, "", destination


def append_runtime_logs(prefix: Path, dependency: str, log_file: Path) -> list[str]:
    candidates: list[Path] = []
    patterns = {
        "dotnet48": ["**/*dotnet*.log", "**/*ndp48*.log", "**/dd_*.txt", "**/dd_*.log"],
        "vcrun2022": ["**/*vc_redist*.log", "**/*dd_vcredist*.txt", "**/*dd_vcredist*.log"],
    }
    for pattern in patterns.get(dependency, ["**/*.log"]):
        candidates.extend(prefix.glob(pattern))
    unique = sorted({path for path in candidates if path.is_file()}, key=lambda path: path.stat().st_mtime, reverse=True)
    copied: list[str] = []
    for path in unique[:8]:
        try:
            content = path.read_text(errors="replace")
        except OSError:
            continue
        if not content.strip():
            continue
        log(f"runtime log begin: {path}", log_file)
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(content[-120000:])
            if not content.endswith("\n"):
                handle.write("\n")
        log(f"runtime log end: {path}", log_file)
        copied.append(str(path))
    return copied


def install_dependency(dependency: str, plan: Plan, prefix: Path, log_file: Path, retries: int = 2) -> tuple[str, str]:
    if dependency == "dotnet48" and dotnet48_ready(prefix):
        return "ok", "bereits vorhanden"
    if dependency in MANUAL_DEPENDENCIES:
        return "deferred", MANUAL_DEPENDENCIES[dependency]
    attempts = max(1, retries)
    if dependency in WINETRICKS_DEPENDENCIES:
        if shutil.which("winetricks") is None:
            return "warning", "Winetricks fehlt im Systemabbild."
        for attempt in range(1, attempts + 1):
            code = run_process(["winetricks", "-q", dependency], prefix, log_file, 5400)
            if code == 0:
                return "ok", f"Versuch {attempt} erfolgreich"
            run_process(["wineserver", "-k"], prefix, log_file, 60)
            time.sleep(1)
        return "warning", f"Winetricks-Komponente {dependency} ist nach {attempts} Versuchen fehlgeschlagen."
    if dependency in RUNTIME_DOWNLOADS:
        ok, error, installer = download_runtime(dependency, plan, log_file)
        if not ok or installer is None:
            return "warning", error
        spec = RUNTIME_DOWNLOADS[dependency]
        runtime_args = list(spec["args"])
        if dependency == "dotnet48":
            run_process(["wine", "winecfg", "-v", "win7"], prefix, log_file, 300)
            runtime_args.extend(["/log", r"C:\windows\temp\LiMaD-dotnet48.log"])
        code = run_process(["wine", str(installer), *runtime_args], prefix, log_file, 5400, installer.parent)
        run_process(["wineserver", "-w"], prefix, log_file, 900)
        if dependency == "dotnet48":
            append_runtime_logs(prefix, dependency, log_file)
            run_process(["wine", "winecfg", "-v", plan.windows_version], prefix, log_file, 300)
        if code in (0, 3010, 1641):
            return "ok", "Offizieller Runtime-Installer abgeschlossen"
        return "warning", f"Offizieller Runtime-Installer endete mit Wine-Code {code}; Details wurden ins Programmprotokoll übernommen."
    return "deferred", "Für diese Komponente ist kein sicherer automatischer Anbieter definiert."


def apply_plan(
    plan: Plan,
    prefix: Path | None = None,
    environment: str = "legacy",
    progress: Callable[[str, float], None] | None = None,
) -> tuple[bool, str]:
    selected_prefix = prefix or LEGACY_PREFIX
    log_file = environment_log(environment) if environment != "legacy" else GLOBAL_LOG
    settings = load_settings()
    state = load_state(environment) if environment != "legacy" else {"completed_steps": [], "dependency_status": {}, "warnings": []}
    completed = set(state.get("completed_steps", []))
    dependency_status = dict(state.get("dependency_status", {}))
    warnings = list(state.get("warnings", []))
    hard_failures: list[str] = []
    all_dependencies = list(plan.dependencies)
    if settings.get("install_optional_dependencies", True):
        all_dependencies.extend(plan.optional_dependencies)
    total = max(1, len(all_dependencies) + 2)

    def emit(text: str, position: int) -> None:
        if progress:
            progress(text, min(1.0, position / total))

    emit(f"Windows-Modus {plan.windows_version} wird gesetzt", 0)
    version_step = f"winver:{plan.windows_version}"
    if version_step not in completed:
        code = run_process(["wine", "winecfg", "-v", plan.windows_version], selected_prefix, log_file, 900)
        if code == 0:
            completed.add(version_step)
        else:
            warnings.append(f"Windows-Modus {plan.windows_version} konnte nicht gesetzt werden.")

    for index, dependency in enumerate(all_dependencies, start=1):
        step = f"dependency:{dependency}"
        if step in completed and dependency_status.get(dependency, {}).get("status") == "ok":
            emit(f"{dependency_label(dependency)} ist bereits eingerichtet", index)
            continue
        emit(f"{dependency_label(dependency)} wird eingerichtet", index)
        status, detail = install_dependency(
            dependency,
            plan,
            selected_prefix,
            log_file,
            int(settings.get("dependency_retries", 2)),
        )
        dependency_status[dependency] = {"status": status, "detail": detail, "updated": now()}
        if status == "ok":
            completed.add(step)
        else:
            warnings.append(f"{dependency_label(dependency)}: {detail}")
            if dependency in plan.dependencies:
                hard_failures.append(dependency)
        if environment != "legacy":
            state.update({"completed_steps": sorted(completed), "dependency_status": dependency_status, "warnings": list(dict.fromkeys(warnings))})
            save_state(environment, state)

    emit("Windows-Modus wird bestätigt", len(all_dependencies) + 1)
    code = run_process(["wine", "winecfg", "-v", plan.windows_version], selected_prefix, log_file, 900)
    if code != 0:
        warnings.append(f"Windows-Modus {plan.windows_version} konnte abschließend nicht bestätigt werden.")
    if "dotnet48" in plan.dependencies and not dotnet48_ready(selected_prefix):
        warnings.append("Microsoft .NET Framework 4.8 wurde nicht vollständig erkannt; der Hauptinstaller wird trotzdem gestartet.")

    if environment != "legacy":
        state.update({"completed_steps": sorted(completed), "dependency_status": dependency_status, "warnings": list(dict.fromkeys(warnings))})
        save_state(environment, state)
    message = "\n".join(list(dict.fromkeys(warnings)))
    can_continue = not hard_failures
    return can_continue, message


def wait_for_installer_processes(prefix: Path | None = None, log_file: Path | None = None, max_seconds: int = 120) -> None:
    selected_prefix = prefix or LEGACY_PREFIX
    selected_log = log_file or GLOBAL_LOG
    code = run_process(["wineserver", "-w"], selected_prefix, selected_log, max_seconds)
    if code == 124:
        log("installer left Wine processes running; continuing after bounded wait", selected_log)


def program_roots(prefix: Path) -> list[Path]:
    drive_c = prefix / "drive_c"
    roots: list[Path] = []
    for name in ("Program Files", "Program Files (x86)"):
        candidate = drive_c / name
        if candidate.is_dir():
            roots.append(candidate)
    users = drive_c / "users"
    if users.is_dir():
        for user in users.iterdir():
            if not user.is_dir():
                continue
            for rel in (
                Path("AppData/Local/Programs"),
                Path("AppData/Roaming/Microsoft/Windows/Start Menu/Programs"),
                Path("Desktop"),
            ):
                candidate = user / rel
                if candidate.is_dir():
                    roots.append(candidate)
    return roots


def scan_executables(prefix: Path) -> set[Path]:
    found: set[Path] = set()
    for root in program_roots(prefix):
        try:
            for path in root.rglob("*.exe"):
                if path.is_file():
                    found.add(path)
        except OSError:
            continue
    return found


def nice_name(exe: Path) -> str:
    base = exe.stem.replace("_", " ").replace("-", " ").strip()
    return base[:1].upper() + base[1:] if base else exe.stem


def nearby_program_icon(exe: Path) -> Path | None:
    names = (exe.stem, "app", "application", "icon", "logo")
    for name in names:
        for suffix in (".png", ".svg", ".ico"):
            candidate = exe.parent / f"{name}{suffix}"
            if candidate.is_file():
                return candidate
    return None


def extract_icon(exe: Path, slug: str) -> str:
    existing = nearby_program_icon(exe)
    if existing is not None:
        return str(existing)
    if not shutil.which("wrestool"):
        return FALLBACK_ICON
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    temporary = ICON_DIR / f"{slug}.ico.tmp"
    try:
        with temporary.open("wb") as handle:
            result = subprocess.run(["wrestool", "-x", "-t", "14", str(exe)], stdout=handle, stderr=subprocess.DEVNULL, timeout=30)
        if result.returncode != 0 or temporary.stat().st_size == 0:
            return FALLBACK_ICON
        if not shutil.which("icotool"):
            final_ico = ICON_DIR / f"{slug}.ico"
            temporary.replace(final_ico)
            return str(final_ico)
        subprocess.run(["icotool", "-x", "-w", "256", "-o", str(ICON_DIR), str(temporary)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, check=True)
        candidates = sorted(ICON_DIR.glob(f"{slug}*.png"), key=lambda item: item.stat().st_size)
        if not candidates:
            final_ico = ICON_DIR / f"{slug}.ico"
            temporary.replace(final_ico)
            return str(final_ico)
        final = ICON_DIR / f"{slug}.png"
        candidates[-1].replace(final)
        for leftover in ICON_DIR.glob(f"{slug}*.png"):
            if leftover != final:
                leftover.unlink(missing_ok=True)
        return str(final)
    except Exception as exc:
        log(f"icon extraction failed for {exe}: {exc}")
        return FALLBACK_ICON
    finally:
        temporary.unlink(missing_ok=True)


def write_desktop_entry(name: str, exe: Path, icon: str, prefix: Path, environment: str) -> Path:
    DESKTOP_DIR.mkdir(parents=True, exist_ok=True)
    slug = slugify(f"{name}-{environment}")
    path = DESKTOP_DIR / f"limad-win-{slug}.desktop"
    path.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={name}\n"
        "Comment=Windows-Programm in LiMaD OS\n"
        f"Exec=/usr/local/bin/limad-winrun --prefix \"{prefix}\" --exe \"{exe}\"\n"
        f"Icon={icon}\n"
        "Terminal=false\n"
        "Categories=Utility;\n"
        "StartupNotify=true\n"
        f"X-LiMaD-Windows-Exe={exe}\n"
        f"X-LiMaD-Windows-Prefix={prefix}\n"
        f"X-LiMaD-Windows-Environment={environment}\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    refresh_desktop_database()
    return path


def rebuild_registered_shortcut(entry: dict, pin: bool | None = None) -> Path | None:
    exe_value = entry.get("exe")
    if not exe_value:
        return None
    exe = Path(exe_value)
    if not exe.is_file():
        log(f"shortcut repair skipped; executable missing: {exe}")
        return None
    name = entry.get("name") or nice_name(exe)
    environment = entry.get("environment_id", "legacy")
    icon = entry.get("icon", FALLBACK_ICON)
    icon_valid = isinstance(icon, str) and ((icon.startswith("/") and Path(icon).is_file()) or not icon.startswith("/"))
    if icon == FALLBACK_ICON or not icon_valid:
        icon = extract_icon(exe, slugify(f"{name}-{environment}"))
    old_desktop_value = entry.get("desktop")
    old_desktop = Path(old_desktop_value) if old_desktop_value else None
    was_pinned = bool(entry.get("dock_pinned")) or bool(old_desktop and is_desktop_entry_pinned(old_desktop))
    if entry.get("backend") == "bottles":
        bottle = entry.get("bottle_name") or bottle_name_for(environment)
        state = load_state(environment)
        prefix = Path(state.get("bottle_path", "")) if state.get("bottle_path") else bottles_host_prefix("", bottle)
        exe_windows = entry.get("exe_windows") or bottles_windows_path(exe, prefix)
        desktop = write_bottles_desktop_entry(name, exe_windows, icon, bottle, environment)
        entry.update({
            "name": name,
            "exe_windows": exe_windows,
            "bottle_name": bottle,
            "icon": icon,
            "desktop": str(desktop),
            "launcher": str(bottles_launcher_path(name, environment)),
        })
    else:
        prefix = Path(entry.get("prefix", str(LEGACY_PREFIX)))
        desktop = write_desktop_entry(name, exe, icon, prefix, environment)
        entry.update({"name": name, "icon": icon, "desktop": str(desktop)})
    if old_desktop is not None and old_desktop != desktop:
        unpin_desktop_entry_from_dock(old_desktop)
        old_desktop.unlink(missing_ok=True)
    should_pin = was_pinned if pin is None else pin
    entry["dock_pinned"] = pin_desktop_entry_to_dock(desktop) if should_pin else False
    return desktop


def repair_registered_shortcuts() -> tuple[int, int]:
    entries = load_registry()
    repaired = 0
    pinned = 0
    changed = False
    for entry in entries:
        old = json.dumps(entry, sort_keys=True, ensure_ascii=False)
        desktop = rebuild_registered_shortcut(entry)
        if desktop is not None:
            repaired += 1
            if entry.get("dock_pinned"):
                pinned += 1
        if json.dumps(entry, sort_keys=True, ensure_ascii=False) != old:
            changed = True
    if changed:
        save_registry(entries)
    return repaired, pinned


def remove_entry_files(entry: dict) -> None:
    desktop_value = entry.get("desktop")
    if desktop_value:
        desktop = Path(desktop_value)
        unpin_desktop_entry_from_dock(desktop)
        desktop.unlink(missing_ok=True)
    launcher_value = entry.get("launcher")
    if launcher_value:
        Path(launcher_value).unlink(missing_ok=True)
    elif entry.get("backend") == "bottles" and entry.get("name"):
        bottles_launcher_path(entry["name"], entry.get("environment_id", "legacy")).unlink(missing_ok=True)


def remove_environment(environment: str, entries: list[dict]) -> list[dict]:
    state = load_state(environment)
    if state.get("backend") == "bottles":
        bottle = state.get("bottle_name", bottle_name_for(environment))
        if bottle.startswith("LiMaD-"):
            prefix = bottles_host_prefix("", bottle)
            if prefix.exists():
                run_host_process(["flatpak", "kill", BOTTLES_APP_ID], environment_log(environment), 30)
                shutil.rmtree(prefix, ignore_errors=True)
            (BOTTLES_STAGE_HOST / "state" / f"{bottle}.json").unlink(missing_ok=True)
    else:
        prefix = prefix_for(environment)
        run_process(["wineserver", "-k"], prefix, environment_log(environment), 60)
    remaining = []
    for entry in entries:
        if entry.get("environment_id") == environment:
            remove_entry_files(entry)
        else:
            remaining.append(entry)
    shutil.rmtree(env_root(environment), ignore_errors=True)
    return remaining


def environment_records() -> list[dict]:
    records: list[dict] = []
    if not APPS_HOME.is_dir():
        return records
    for directory in sorted(APPS_HOME.iterdir()):
        if not directory.is_dir():
            continue
        state = load_state(directory.name)
        if state.get("backend") == "bottles":
            prefix = Path(state.get("bottle_path", ""))
            state["prefix"] = str(prefix)
            state["ready"] = bool(state.get("bottle_name")) and prefix.is_dir()
        else:
            prefix = prefix_for(directory.name)
            state["prefix"] = str(prefix)
            state["ready"] = prefix_ready(prefix)
        records.append(state)
    return records


class InstallerWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application, initial_file: Path | None = None) -> None:
        super().__init__(application=app, title=APP_NAME)
        self.set_default_size(980, 720)
        self.set_size_request(760, 560)
        self.busy = False
        self.pending_file: Path | None = None
        self.pending_plan: Plan | None = None
        self.pending_environment: str | None = None
        self.new_programs: list[Path] = []
        self.install_warnings: list[str] = []

        self.toasts = Adw.ToastOverlay()
        self.stack = Adw.ViewStack()
        header = Adw.HeaderBar()
        self.switcher = Adw.ViewSwitcher(stack=self.stack, policy=Adw.ViewSwitcherPolicy.WIDE)
        header.set_title_widget(self.switcher)
        self.choose_button = Gtk.Button(label="EXE / MSI auswählen")
        self.choose_button.add_css_class("suggested-action")
        self.choose_button.connect("clicked", self.on_choose_file)
        header.pack_start(self.choose_button)
        self.version_label = Gtk.Label(label=f"Installer {APP_VERSION}")
        self.version_label.add_css_class("dim-label")
        header.pack_end(self.version_label)

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(header)
        toolbar.set_content(self.toasts)
        self.toasts.set_child(self.stack)
        self.set_content(toolbar)

        self.stack.add_titled_with_icon(self.build_install_page(), "install", "Installieren", "document-open-symbolic")
        self.stack.add_titled_with_icon(self.build_programs_page(), "programs", "Meine Programme", "view-grid-symbolic")
        self.stack.add_titled_with_icon(self.build_repair_page(), "repair", "Reparieren", "emblem-system-symbolic")
        self.stack.add_titled_with_icon(self.build_environments_page(), "environments", "Umgebungen", "drive-harddisk-symbolic")
        self.stack.add_titled_with_icon(self.build_log_page(), "log", "Protokoll", "text-x-generic-symbolic")
        self.stack.add_titled_with_icon(self.build_settings_page(), "settings", "Einstellungen", "emblem-system-symbolic")

        self.refresh_all()
        if initial_file:
            GLib.idle_add(self.start_install, initial_file)

    def build_install_page(self) -> Gtk.Widget:
        page = Adw.PreferencesPage()
        self.install_group = Adw.PreferencesGroup(
            title="Windows-Programm installieren",
            description="LiMaD analysiert die Datei, erstellt eine eigene verwaltete Programmumgebung und führt alle Schritte in diesem Fenster aus.",
        )
        self.file_row = Adw.ActionRow(title="Keine Datei ausgewählt", subtitle="EXE oder MSI auswählen")
        self.file_row.add_prefix(Gtk.Image.new_from_icon_name("application-x-executable-symbolic"))
        self.install_group.add(self.file_row)
        self.profile_row = Adw.ActionRow(title="Profil", subtitle="Noch nicht analysiert")
        self.install_group.add(self.profile_row)
        self.arch_row = Adw.ActionRow(title="Architektur", subtitle="Noch nicht analysiert")
        self.install_group.add(self.arch_row)
        self.dependencies_row = Adw.ActionRow(title="Abhängigkeiten", subtitle="Noch nicht analysiert")
        self.dependencies_row.set_subtitle_lines(4)
        self.install_group.add(self.dependencies_row)
        self.compatibility_row = Adw.ActionRow(title="Kompatibilität", subtitle="Noch nicht analysiert")
        self.compatibility_row.set_subtitle_lines(4)
        self.install_group.add(self.compatibility_row)
        page.add(self.install_group)

        action_group = Adw.PreferencesGroup(title="Ablauf")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        self.progress_label = Gtk.Label(label="Bereit", xalign=0)
        self.progress_label.set_wrap(True)
        self.progress_bar = Gtk.ProgressBar(show_text=True)
        self.progress_bar.set_fraction(0)
        self.progress_bar.set_text("0 %")
        self.install_action = Gtk.Button(label="Installation starten")
        self.install_action.add_css_class("suggested-action")
        self.install_action.set_sensitive(False)
        self.install_action.connect("clicked", self.on_install_clicked)
        box.append(self.progress_label)
        box.append(self.progress_bar)
        box.append(self.install_action)
        action_group.add(box)
        page.add(action_group)
        return page

    def build_programs_page(self) -> Gtk.Widget:
        page = Adw.PreferencesPage()
        self.programs_group = Adw.PreferencesGroup(
            title="Installierte Windows-Programme",
            description="Jedes Programm verwendet eine getrennte Umgebung und besitzt einen eigenen Menüeintrag.",
        )
        page.add(self.programs_group)
        return page

    def build_repair_page(self) -> Gtk.Widget:
        page = Adw.PreferencesPage()
        self.repair_group = Adw.PreferencesGroup(
            title="Reparieren",
            description="Fehlgeschlagene oder übersprungene Abhängigkeiten erneut ausführen, ohne das Programm zu löschen.",
        )
        page.add(self.repair_group)
        return page

    def build_environments_page(self) -> Gtk.Widget:
        page = Adw.PreferencesPage()
        self.environments_group = Adw.PreferencesGroup(
            title="Getrennte Programmumgebungen",
            description="Ein Problem in einer Anwendung beeinflusst keine anderen installierten Windows-Programme.",
        )
        page.add(self.environments_group)
        return page

    def build_log_page(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        refresh = Gtk.Button(label="Aktualisieren", icon_name="view-refresh-symbolic")
        refresh.connect("clicked", lambda _button: self.refresh_log())
        clear = Gtk.Button(label="Leeren", icon_name="edit-clear-all-symbolic")
        clear.connect("clicked", self.on_clear_log)
        toolbar.append(refresh)
        toolbar.append(clear)
        self.log_view = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        scroller = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        scroller.set_child(self.log_view)
        box.append(toolbar)
        box.append(scroller)
        return box

    def build_settings_page(self) -> Gtk.Widget:
        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup(title="Installationsverhalten")
        settings = load_settings()
        self.setting_widgets: dict[str, Gtk.Switch] = {}
        options = (
            ("prefer_bottles", "Bottles für komplexe Programme verwenden", ".NET-, DirectX-, Office- und ähnliche Programme erhalten eine verwaltete Bottle."),
            ("auto_install_bottles", "Bottles automatisch installieren", "Fehlt Bottles, wird die offizielle Flatpak-Version aus Flathub eingerichtet."),
            ("install_optional_dependencies", "Optionale Abhängigkeiten installieren", "Zusätzliche erkannte Runtimes automatisch versuchen."),
            ("continue_after_dependency_error", "Bei Abhängigkeitsfehlern fortfahren", "Der Hauptinstaller startet trotz einer fehlgeschlagenen Runtime."),
            ("create_shortcuts", "Menüeinträge automatisch anbieten", "Nach der Installation gefundene Programme zum GNOME-Menü hinzufügen."),
            ("keep_installer_copy", "Installer in der Umgebung behalten", "Die ausgewählte EXE/MSI für spätere Reparaturen kopieren."),
        )
        for key, title, subtitle in options:
            row = Adw.ActionRow(title=title, subtitle=subtitle)
            switch = Gtk.Switch(active=bool(settings.get(key, DEFAULT_SETTINGS[key])), valign=Gtk.Align.CENTER)
            switch.connect("notify::active", self.on_setting_changed, key)
            row.add_suffix(switch)
            row.set_activatable_widget(switch)
            group.add(row)
            self.setting_widgets[key] = switch
        page.add(group)

        info = Adw.PreferencesGroup(title="Technische Grenzen")
        row = Adw.ActionRow(
            title="Nicht vollständig automatisierbar",
            subtitle="Kernel-Treiber, Anti-Cheat, USB-Dongle-Treiber, Microsoft Store/UWP/MSIX, tiefes DRM und einige Windows-Dienste benötigen echtes Windows.",
        )
        row.set_subtitle_lines(4)
        info.add(row)
        page.add(info)
        return page

    def toast(self, text: str) -> None:
        self.toasts.add_toast(Adw.Toast(title=text, timeout=5))

    def set_busy(self, busy: bool) -> None:
        self.busy = busy
        self.choose_button.set_sensitive(not busy)
        self.install_action.set_sensitive(not busy and self.pending_file is not None)

    def set_progress(self, text: str, fraction: float) -> None:
        def update() -> bool:
            self.progress_label.set_label(text)
            self.progress_bar.set_fraction(max(0, min(1, fraction)))
            self.progress_bar.set_text(f"{round(max(0, min(1, fraction)) * 100)} %")
            return False
        GLib.idle_add(update)

    def clear_group(self, group: Adw.PreferencesGroup, attribute: str) -> None:
        for row in getattr(self, attribute, []):
            group.remove(row)
        setattr(self, attribute, [])

    def refresh_all(self) -> None:
        self.refresh_programs()
        self.refresh_repair()
        self.refresh_environments()
        self.refresh_log()

    def refresh_programs(self) -> None:
        self.clear_group(self.programs_group, "_program_rows")
        rows = []
        entries = load_registry()
        if not entries:
            row = Adw.ActionRow(title="Noch keine Windows-Programme", subtitle="Über Installieren eine EXE- oder MSI-Datei auswählen.")
            self.programs_group.add(row)
            rows.append(row)
        for entry in entries:
            subtitle = f"{entry.get('profile', 'Standard')} · {entry.get('exe', '')}"
            row = Adw.ActionRow(title=entry.get("name", "Windows-Programm"), subtitle=subtitle)
            row.set_subtitle_lines(2)
            icon = entry.get("icon", FALLBACK_ICON)
            image = Gtk.Image.new_from_file(icon) if isinstance(icon, str) and icon.startswith("/") and Path(icon).is_file() else Gtk.Image.new_from_icon_name(FALLBACK_ICON)
            image.set_pixel_size(36)
            row.add_prefix(image)
            start = Gtk.Button(icon_name="media-playback-start-symbolic", tooltip_text="Starten", valign=Gtk.Align.CENTER)
            start.add_css_class("flat")
            start.connect("clicked", self.on_start_program, entry)
            desktop_path = Path(entry.get("desktop", "")) if entry.get("desktop") else None
            pinned = bool(desktop_path and is_desktop_entry_pinned(desktop_path))
            dock = Gtk.Button(
                icon_name="emblem-favorite-symbolic",
                tooltip_text="Vom Dock lösen" if pinned else "Zum Dock hinzufügen",
                valign=Gtk.Align.CENTER,
            )
            dock.add_css_class("flat")
            dock.connect("clicked", self.on_toggle_program_dock, entry)
            repair = Gtk.Button(icon_name="emblem-system-symbolic", tooltip_text="Reparieren", valign=Gtk.Align.CENTER)
            repair.add_css_class("flat")
            repair.connect("clicked", self.on_repair_program, entry)
            remove = Gtk.Button(icon_name="user-trash-symbolic", tooltip_text="Entfernen", valign=Gtk.Align.CENTER)
            remove.add_css_class("flat")
            remove.connect("clicked", self.on_remove_program, entry)
            row.add_suffix(start)
            row.add_suffix(dock)
            row.add_suffix(repair)
            row.add_suffix(remove)
            self.programs_group.add(row)
            rows.append(row)
        self._program_rows = rows

    def refresh_repair(self) -> None:
        self.clear_group(self.repair_group, "_repair_rows")
        rows = []
        records = environment_records()
        if not records:
            row = Adw.ActionRow(title="Keine Umgebung vorhanden", subtitle="Nach der ersten Installation erscheinen hier Reparaturoptionen.")
            self.repair_group.add(row)
            rows.append(row)
        for record in records:
            warnings = record.get("warnings", [])
            status = "Bereit" if record.get("ready") else "Unvollständig"
            if warnings:
                status += f" · {len(warnings)} Warnung(en)"
            row = Adw.ActionRow(title=record.get("display_name", record.get("environment_id", "Umgebung")), subtitle=status)
            button = Gtk.Button(label="Prüfen und reparieren", valign=Gtk.Align.CENTER)
            button.add_css_class("pill")
            button.connect("clicked", self.on_repair_environment, record.get("environment_id"))
            row.add_suffix(button)
            self.repair_group.add(row)
            rows.append(row)
        self._repair_rows = rows

    def refresh_environments(self) -> None:
        self.clear_group(self.environments_group, "_environment_rows")
        rows = []
        records = environment_records()
        if not records:
            row = Adw.ActionRow(title="Keine getrennten Umgebungen", subtitle="Jede neue Installation erhält automatisch eine eigene Umgebung.")
            self.environments_group.add(row)
            rows.append(row)
        for record in records:
            prefix = Path(record.get("prefix", ""))
            size = self.directory_size(prefix)
            subtitle = f"{'Bereit' if record.get('ready') else 'Unvollständig'} · {size} · {prefix}"
            row = Adw.ActionRow(title=record.get("display_name", record.get("environment_id", "Umgebung")), subtitle=subtitle)
            row.set_subtitle_lines(2)
            reset = Gtk.Button(icon_name="edit-delete-symbolic", tooltip_text="Umgebung löschen", valign=Gtk.Align.CENTER)
            reset.add_css_class("flat")
            reset.connect("clicked", self.on_delete_environment, record.get("environment_id"))
            row.add_suffix(reset)
            self.environments_group.add(row)
            rows.append(row)
        self._environment_rows = rows

    def refresh_log(self) -> None:
        text = GLOBAL_LOG.read_text(encoding="utf-8", errors="replace")[-150_000:] if GLOBAL_LOG.is_file() else "Noch kein Installationsprotokoll vorhanden."
        self.log_view.get_buffer().set_text(text)

    @staticmethod
    def directory_size(path: Path) -> str:
        total = 0
        try:
            for item in path.rglob("*"):
                if item.is_file():
                    total += item.stat().st_size
        except OSError:
            pass
        units = ("B", "KB", "MB", "GB")
        value = float(total)
        for unit in units:
            if value < 1024 or unit == units[-1]:
                return f"{value:.1f} {unit}"
            value /= 1024
        return f"{total} B"

    def on_setting_changed(self, switch: Gtk.Switch, _param, key: str) -> None:
        settings = load_settings()
        settings[key] = switch.get_active()
        save_settings(settings)

    def on_clear_log(self, _button: Gtk.Button) -> None:
        GLOBAL_LOG.unlink(missing_ok=True)
        self.refresh_log()
        self.toast("Protokoll wurde geleert")

    def on_choose_file(self, _button: Gtk.Button) -> None:
        file_filter = Gtk.FileFilter()
        file_filter.set_name("Windows-Programme (EXE, MSI)")
        for pattern in ("*.exe", "*.EXE", "*.msi", "*.MSI"):
            file_filter.add_pattern(pattern)
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(file_filter)
        dialog = Gtk.FileDialog(title="Windows-Datei auswählen", filters=filters, default_filter=file_filter)
        dialog.open(self, None, self.on_file_chosen)

    def on_file_chosen(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            gfile = dialog.open_finish(result)
        except GLib.Error:
            return
        if gfile and gfile.get_path():
            self.start_install(Path(gfile.get_path()))

    def start_install(self, path: Path) -> bool:
        if self.busy:
            return False
        if not path.is_file() or path.suffix.lower() not in {".exe", ".msi"}:
            self.toast("Nur vorhandene EXE- und MSI-Dateien werden unterstützt.")
            return False
        try:
            plan = analyze(path)
        except ValueError as exc:
            self.toast(str(exc))
            return False
        environment = environment_id(path, plan)
        self.pending_file = path
        self.pending_plan = plan
        self.pending_environment = environment
        self.file_row.set_title(path.name)
        self.file_row.set_subtitle(str(path.parent))
        profile_names = {
            "standard": "Standard", "dotnet": ".NET-Anwendung", "office": "Office",
            "cad": "CAD/3D", "creative": "Grafik/Adobe", "gaming": "Spiel/Launcher",
            "legacy": "Älteres Programm", "minimal": "Minimal", "nws": "NWS / .NET-Anwendung",
        }
        backend_label = "Bottles-Backend" if use_bottles_backend(plan) else "System-Wine"
        self.profile_row.set_subtitle(f"{profile_names.get(plan.profile, plan.profile)} · {backend_label} · Windows-Modus {plan.windows_version} · Sicherheit {plan.confidence} %")
        self.arch_row.set_subtitle(("64-Bit-Anwendung" if plan.architecture == "win64" else "32-Bit-Anwendung") + (" · 64-Bit-Bottle" if use_bottles_backend(plan) else " · System-Wine"))
        required = [dependency_label(item) for item in plan.dependencies]
        optional = [dependency_label(item) for item in plan.optional_dependencies]
        text = "Erforderlich: " + (", ".join(required) if required else "keine")
        if optional:
            text += "\nOptional: " + ", ".join(optional)
        self.dependencies_row.set_subtitle(text)
        compatibility = "Keine bekannte harte Wine-Grenze erkannt."
        if plan.blockers:
            compatibility = "\n".join(plan.blockers)
        self.compatibility_row.set_subtitle(compatibility)
        self.install_action.set_sensitive(True)
        self.progress_label.set_label("Installationsplan ist bereit.")
        self.progress_bar.set_fraction(0)
        self.progress_bar.set_text("0 %")
        self.stack.set_visible_child_name("install")
        return False

    def on_install_clicked(self, _button: Gtk.Button) -> None:
        if not self.pending_file or not self.pending_plan or not self.pending_environment:
            return
        plan = self.pending_plan
        dependencies = [dependency_label(item) for item in plan.dependencies]
        optional = [dependency_label(item) for item in plan.optional_dependencies]
        body = (
            f"Datei: {self.pending_file.name}\n"
            f"Eigene Umgebung: {self.pending_environment}\n"
            f"Backend: {'Bottles' if use_bottles_backend(plan) else 'System-Wine'}\n"
            f"Profil: {plan.profile}\n"
            f"Abhängigkeiten: {', '.join(dependencies) if dependencies else 'keine'}"
        )
        if optional:
            body += f"\nOptional: {', '.join(optional)}"
        body += "\n\nKomplexe Abhängigkeiten werden mit einer geprüften Winetricks-Version direkt in der Bottles-Umgebung installiert."
        if plan.blockers:
            body += "\n\nAchtung: " + " · ".join(plan.blockers)
        dialog = Adw.MessageDialog(transient_for=self, heading="Installationsplan prüfen", body=body)
        dialog.add_response("cancel", "Abbrechen")
        dialog.add_response("install", "Installieren")
        dialog.set_response_appearance("install", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("install")
        dialog.connect("response", self.on_plan_response)
        dialog.present()

    def on_plan_response(self, dialog: Adw.MessageDialog, response: str) -> None:
        dialog.close()
        if response == "install":
            self.run_task(self.task_install)

    def run_task(self, task: Callable[[], str]) -> None:
        self.set_busy(True)
        threading.Thread(target=self._thread_wrapper, args=(task,), daemon=True).start()

    def _thread_wrapper(self, task: Callable[[], str]) -> None:
        try:
            message = task()
        except Exception as exc:
            log(f"task failed: {exc}")
            message = f"Fehlgeschlagen: {exc}"
        GLib.idle_add(self._task_done, message)

    def _task_done(self, message: str) -> bool:
        self.set_busy(False)
        self.refresh_all()
        self.refresh_log()
        if message:
            self.toast(message)
        if self.new_programs:
            self.present_new_programs()
        return False

    def task_install(self) -> str:
        assert self.pending_file and self.pending_plan and self.pending_environment
        if use_bottles_backend(self.pending_plan):
            return self.task_install_bottles()
        return self.task_install_system()

    def task_install_bottles(self) -> str:
        assert self.pending_file and self.pending_plan and self.pending_environment
        path = self.pending_file
        plan = self.pending_plan
        environment = self.pending_environment
        log_file = environment_log(environment)
        state = load_state(environment)
        bottle = bottle_name_for(environment)
        state.update({
            "display_name": path.stem,
            "source_file": str(path),
            "plan": asdict(plan),
            "status": "preparing-bottles",
            "backend": "bottles",
            "bottle_name": bottle,
        })
        save_state(environment, state)

        self.set_progress("Bottles-Backend wird geprüft", 0.03)
        ok, error = ensure_bottles(log_file, self.set_progress)
        if not ok:
            state["status"] = "bottles-missing"
            state.setdefault("warnings", []).append(error)
            save_state(environment, state)
            return error

        ok, error, runner = bootstrap_bottles_components(log_file, self.set_progress)
        if not ok:
            state["status"] = "bottles-components-failed"
            state.setdefault("warnings", []).append(error)
            save_state(environment, state)
            return error
        state["bottles_runner"] = runner
        save_state(environment, state)

        ok, error = ensure_bottle_cli(bottle, runner, log_file, self.set_progress)
        if not ok:
            state["status"] = "bottles-create-failed"
            state.setdefault("warnings", []).append(error)
            save_state(environment, state)
            return error

        dependencies = bottles_dependencies(plan, load_settings().get("install_optional_dependencies", True))
        self.set_progress("Windows-Komponenten werden in Bottles vorbereitet", 0.18)
        ok, error, prepared = prepare_bottle_dependencies(
            bottle,
            runner,
            dependencies,
            log_file,
            lambda text, fraction: self.set_progress(text, min(0.50, fraction)),
        )
        if not ok:
            state["status"] = "bottles-prepare-failed"
            state.setdefault("warnings", []).append(error)
            save_state(environment, state)
            return error

        bottle_path = bottles_host_prefix(str(prepared.get("bottle_path", "")), bottle)
        state.update({
            "status": "installer",
            "bottle_path": str(bottle_path),
            "installed_dependencies": prepared.get("installed_dependencies", []),
        })
        save_state(environment, state)

        host_installer = stage_bottles_installer(path, environment)
        state["staged_installer"] = str(host_installer)
        save_state(environment, state)
        self.set_progress("Windows-Installer wird in Bottles gestartet", 0.58)
        before = scan_executables(bottle_path) if bottle_path.exists() else set()
        code = run_bottles_executable(bottle, str(host_installer), log_file, 10800)
        self.set_progress("Installierte Programme werden erkannt", 0.84)
        after = scan_executables(bottle_path) if bottle_path.exists() else set()
        candidates = [exe for exe in sorted(after - before) if not SKIP_PATTERNS.search(exe.name)]
        known = {entry.get("exe") for entry in load_registry()}
        self.new_programs = [exe for exe in candidates if str(exe) not in known]
        state = load_state(environment)
        state["installer_code"] = code
        state["status"] = "installed" if code in (0, 1641, 3010) else "installer-warning"
        if code not in (0, 1641, 3010):
            state.setdefault("warnings", []).append(f"Bottles-Installer endete mit Code {code}.")
        save_state(environment, state)
        self.set_progress("Installation abgeschlossen", 1.0)
        if self.new_programs:
            return ""
        if code == 124:
            return "Der Installer lief länger als das Zeitlimit. Die Bottle bleibt erhalten."
        if code not in (0, 1641, 3010):
            return f"Der Installer endete mit Code {code}. Die Bottle und das Protokoll bleiben erhalten."
        return "Installation abgeschlossen. Es wurde noch kein eindeutiges Startprogramm erkannt."

    def task_install_system(self) -> str:
        assert self.pending_file and self.pending_plan and self.pending_environment
        path = self.pending_file
        plan = self.pending_plan
        environment = self.pending_environment
        root = env_root(environment)
        prefix = prefix_for(environment)
        log_file = environment_log(environment)
        state = load_state(environment)
        state.update({
            "display_name": path.stem,
            "source_file": str(path),
            "plan": asdict(plan),
            "status": "preparing",
        })
        save_state(environment, state)
        set_prefix_architecture(prefix, plan.architecture)
        log(f"application architecture: {plan.architecture}", log_file)
        log(f"prefix architecture: {get_prefix_architecture(prefix)}", log_file)
        self.set_progress("Eigene Wine-Umgebung wird erstellt", 0.05)
        ok, error = init_prefix(prefix, log_file)
        if not ok:
            state["status"] = "prefix-failed"
            state.setdefault("warnings", []).append(error)
            save_state(environment, state)
            return error

        settings = load_settings()
        if settings.get("keep_installer_copy", False):
            installer_dir = root / "installer"
            installer_dir.mkdir(parents=True, exist_ok=True)
            copy = installer_dir / path.name
            shutil.copy2(path, copy)
            path = copy
            state["source_file"] = str(copy)
            save_state(environment, state)

        state["status"] = "dependencies"
        save_state(environment, state)
        self.install_warnings = []

        def progress(text: str, fraction: float) -> None:
            self.set_progress(text, 0.1 + fraction * 0.45)

        runtime_ok, warnings = apply_plan(plan, prefix, environment, progress)
        if warnings:
            self.install_warnings = warnings.splitlines()
        if not runtime_ok:
            state = load_state(environment)
            state["status"] = "dependency-stopped"
            save_state(environment, state)
            return "Eine erforderliche Abhängigkeit ist fehlgeschlagen. In Einstellungen ist Fortfahren deaktiviert."

        self.set_progress("Windows-Installer wird gestartet", 0.58)
        before = scan_executables(prefix)
        if path.suffix.lower() == ".msi":
            code = run_process(["wine", "msiexec", "/i", str(path)], prefix, log_file, 10800, path.parent)
        else:
            code = run_process(["wine", str(path)], prefix, log_file, 10800, path.parent)
        wait_for_installer_processes(prefix, log_file)
        self.set_progress("Installierte Programme werden erkannt", 0.82)
        after = scan_executables(prefix)
        candidates = [exe for exe in sorted(after - before) if not SKIP_PATTERNS.search(exe.name)]
        if not candidates and path.suffix.lower() == ".exe" and code == 0 and not SKIP_PATTERNS.search(path.name):
            candidates.append(path)
            log("portable application detected", log_file)
        known = {entry.get("exe") for entry in load_registry()}
        self.new_programs = [exe for exe in candidates if str(exe) not in known]
        state = load_state(environment)
        state["installer_code"] = code
        state["status"] = "installed" if code in (0, 1641, 3010) else "installer-warning"
        state["warnings"] = list(dict.fromkeys(state.get("warnings", []) + self.install_warnings + ([] if code in (0, 1641, 3010) else [f"Hauptinstaller endete mit Wine-Code {code}."])))
        save_state(environment, state)
        self.set_progress("Installation abgeschlossen", 1.0)
        if self.new_programs:
            return ""
        if code == 124:
            return "Der Installer lief länger als das Zeitlimit. Die Umgebung bleibt zur Reparatur erhalten."
        if code not in (0, 1641, 3010):
            return f"Der Installer endete mit Wine-Code {code}. Die Umgebung und das Protokoll bleiben erhalten."
        return "Installation beendet; es wurde noch kein eindeutiges Startprogramm erkannt."

    def add_program_entry(self, exe: Path, environment: str, prefix: Path, pin_to_dock: bool = False) -> dict:
        name = nice_name(exe)
        icon = extract_icon(exe, slugify(f"{name}-{environment}"))
        state = load_state(environment)
        backend = state.get("backend", "system-wine")
        if backend == "bottles":
            bottle = state.get("bottle_name", bottle_name_for(environment))
            exe_windows = bottles_windows_path(exe, prefix)
            desktop = write_bottles_desktop_entry(name, exe_windows, icon, bottle, environment)
            entry = {
                "id": hashlib.sha256(f"{environment}|{exe}".encode()).hexdigest()[:16],
                "name": name,
                "exe": str(exe),
                "exe_windows": exe_windows,
                "backend": "bottles",
                "bottle_name": bottle,
                "environment_id": environment,
                "icon": icon,
                "desktop": str(desktop),
                "launcher": str(bottles_launcher_path(name, environment)),
                "profile": self.pending_plan.profile if self.pending_plan else "standard",
                "installed_at": now(),
            }
        else:
            desktop = write_desktop_entry(name, exe, icon, prefix, environment)
            entry = {
                "id": hashlib.sha256(f"{environment}|{exe}".encode()).hexdigest()[:16],
                "name": name,
                "exe": str(exe),
                "prefix": str(prefix),
                "backend": "system-wine",
                "environment_id": environment,
                "icon": icon,
                "desktop": str(desktop),
                "profile": self.pending_plan.profile if self.pending_plan else "standard",
                "installed_at": now(),
            }
        if pin_to_dock:
            entry["dock_pinned"] = pin_desktop_entry_to_dock(desktop)
        return entry

    def present_new_programs(self) -> None:
        programs = self.new_programs
        self.new_programs = []
        if not programs:
            return
        environment = self.pending_environment or "unknown"
        state = load_state(environment)
        backend = state.get("backend", "system-wine")
        prefix = Path(state.get("bottle_path", "")) if backend == "bottles" else prefix_for(environment)

        primary = choose_primary_program(programs, self.pending_file)
        entries = load_registry()
        entry = self.add_program_entry(primary, environment, prefix, pin_to_dock=True)
        entries.append(entry)
        save_registry(entries)
        self.refresh_all()
        self.stack.set_visible_child_name("programs")
        if entry.get("dock_pinned"):
            self.toast(f"{entry['name']} wurde installiert und automatisch zum Dock hinzugefügt")
        else:
            self.toast(f"{entry['name']} wurde installiert und zum GNOME-Menü hinzugefügt")

        remaining = [exe for exe in programs if exe != primary]
        if not remaining:
            return
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Weitere Windows-Programme gefunden",
            body="Das Hauptprogramm wurde bereits automatisch zum Dock hinzugefügt. Zusätzliche Programme können noch zum GNOME-Menü hinzugefügt werden.",
        )
        group = Adw.PreferencesGroup()
        checks: list[tuple[Gtk.CheckButton, Path]] = []
        for exe in remaining[:19]:
            row = Adw.ActionRow(title=nice_name(exe), subtitle=str(exe))
            row.set_subtitle_lines(2)
            check = Gtk.CheckButton(active=False, valign=Gtk.Align.CENTER)
            row.add_prefix(check)
            row.set_activatable_widget(check)
            group.add(row)
            checks.append((check, exe))
        scroller = Gtk.ScrolledWindow(propagate_natural_height=True, max_content_height=400)
        scroller.set_child(group)
        dialog.set_extra_child(scroller)
        dialog.add_response("skip", "Fertig")
        dialog.add_response("add", "Auswahl zum Menü hinzufügen")
        dialog.connect("response", self.on_new_programs_response, checks, environment, prefix)
        dialog.present()

    def on_new_programs_response(self, dialog: Adw.MessageDialog, response: str, checks, environment: str, prefix: Path) -> None:
        dialog.close()
        if response != "add":
            return
        entries = load_registry()
        added = 0
        for check, exe in checks:
            if not check.get_active():
                continue
            entries.append(self.add_program_entry(exe, environment, prefix, pin_to_dock=False))
            added += 1
        save_registry(entries)
        self.refresh_all()
        self.stack.set_visible_child_name("programs")
        self.toast(f"{added} zusätzliche(s) Programm(e) zum Menü hinzugefügt")

    def on_toggle_program_dock(self, _button: Gtk.Button, entry: dict) -> None:
        desktop_value = entry.get("desktop")
        desktop = Path(desktop_value) if desktop_value else rebuild_registered_shortcut(entry, pin=False)
        if desktop is None or not desktop.is_file():
            desktop = rebuild_registered_shortcut(entry, pin=False)
        if desktop is None:
            self.toast("Der Programmstarter konnte nicht erstellt werden")
            return
        pinned = is_desktop_entry_pinned(desktop)
        if pinned:
            unpin_desktop_entry_from_dock(desktop)
            entry["dock_pinned"] = False
            message = f"{entry.get('name', 'Programm')} wurde vom Dock gelöst"
        else:
            entry["dock_pinned"] = pin_desktop_entry_to_dock(desktop)
            message = (
                f"{entry.get('name', 'Programm')} wurde zum Dock hinzugefügt"
                if entry["dock_pinned"] else
                "GNOME konnte den Dock-Eintrag noch nicht übernehmen"
            )
        entries = load_registry()
        for item in entries:
            if item.get("id") == entry.get("id"):
                item.update(entry)
                break
        save_registry(entries)
        self.refresh_programs()
        self.toast(message)

    def on_start_program(self, _button: Gtk.Button, entry: dict) -> None:
        if entry.get("backend") == "bottles":
            subprocess.Popen([
                "/usr/local/bin/limad-bottles-run",
                "--bottle", entry.get("bottle_name", ""),
                "--exe", entry.get("exe_windows", entry.get("exe", "")),
            ])
        else:
            subprocess.Popen(["/usr/local/bin/limad-winrun", "--prefix", entry.get("prefix", str(LEGACY_PREFIX)), "--exe", entry["exe"]])
        self.toast(f"{entry.get('name', 'Programm')} wird gestartet")

    def on_repair_program(self, _button: Gtk.Button, entry: dict) -> None:
        self.stack.set_visible_child_name("repair")
        self.repair_environment(entry.get("environment_id", "legacy"))

    def on_repair_environment(self, _button: Gtk.Button, environment: str) -> None:
        self.repair_environment(environment)

    def repair_environment(self, environment: str) -> None:
        if self.busy:
            return
        state = load_state(environment)
        plan_data = state.get("plan")
        if not plan_data:
            self.toast("Für diese alte Umgebung ist kein Installationsplan gespeichert.")
            return
        try:
            plan = Plan(
                recipe=plan_data["recipe"],
                profile=plan_data["profile"],
                windows_version=plan_data["windows_version"],
                architecture=plan_data["architecture"],
                dependencies=tuple(plan_data.get("dependencies", [])),
                optional_dependencies=tuple(plan_data.get("optional_dependencies", [])),
                warnings=tuple(plan_data.get("warnings", [])),
                blockers=tuple(plan_data.get("blockers", [])),
                reasons=tuple(plan_data.get("reasons", [])),
                confidence=int(plan_data.get("confidence", 0)),
            )
        except (KeyError, TypeError, ValueError):
            self.toast("Gespeicherter Installationsplan ist beschädigt.")
            return
        self.repair_target = (environment, plan)
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Umgebung reparieren?",
            body="LiMaD prüft die Programmumgebung und richtet fehlende Abhängigkeiten erneut ein. Das installierte Programm bleibt erhalten.",
        )
        dialog.add_response("cancel", "Abbrechen")
        dialog.add_response("repair", "Reparieren")
        dialog.set_response_appearance("repair", Adw.ResponseAppearance.SUGGESTED)
        dialog.connect("response", self.on_repair_response)
        dialog.present()

    def on_repair_response(self, dialog: Adw.MessageDialog, response: str) -> None:
        dialog.close()
        if response == "repair":
            self.run_task(self.task_repair)

    def task_repair(self) -> str:
        environment, plan = self.repair_target
        log_file = environment_log(environment)
        state = load_state(environment)
        if state.get("backend") == "bottles" or use_bottles_backend(plan):
            self.set_progress("Bottles-Backend wird geprüft", 0.1)
            ok, error = ensure_bottles(log_file, self.set_progress)
            if not ok:
                return error
            bottle = state.get("bottle_name", bottle_name_for(environment))
            ok, error, runner = bootstrap_bottles_components(log_file, self.set_progress)
            if not ok:
                return error
            ok, error = ensure_bottle_cli(bottle, runner, log_file, self.set_progress)
            if not ok:
                return error
            dependencies = bottles_dependencies(plan, load_settings().get("install_optional_dependencies", True))
            ok, error, prepared = prepare_bottle_dependencies(
                bottle, runner, dependencies, log_file,
                lambda text, fraction: self.set_progress(text, min(0.9, fraction)),
            )
            if not ok:
                return error
            state.update({
                "backend": "bottles",
                "bottle_name": bottle,
                "bottle_path": str(bottles_host_prefix(str(prepared.get("bottle_path", "")), bottle)),
                "installed_dependencies": prepared.get("installed_dependencies", []),
                "status": "ready",
            })
            save_state(environment, state)
            self.set_progress("Reparatur abgeschlossen", 1.0)
            return "Bottles-Umgebung wurde geprüft und repariert."
        prefix = prefix_for(environment)
        set_prefix_architecture(prefix, plan.architecture)
        log(f"prefix architecture: {get_prefix_architecture(prefix)}", log_file)
        self.set_progress("Wine-Umgebung wird geprüft", 0.1)
        ok, error = init_prefix(prefix, log_file)
        if not ok:
            return error
        state["completed_steps"] = [item for item in state.get("completed_steps", []) if not item.startswith("dependency:")]
        save_state(environment, state)
        _, warnings = apply_plan(plan, prefix, environment, lambda text, fraction: self.set_progress(text, 0.2 + fraction * 0.7))
        self.set_progress("Reparatur abgeschlossen", 1.0)
        return "Reparatur abgeschlossen" + (" – Warnungen stehen im Protokoll." if warnings else ".")

    def on_remove_program(self, _button: Gtk.Button, entry: dict) -> None:
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=f"{entry.get('name', 'Programm')} entfernen?",
            body="Der Menüeintrag wird entfernt. Wenn dies das letzte Programm der Umgebung ist, kann die gesamte Programmumgebung ebenfalls gelöscht werden.",
        )
        dialog.add_response("cancel", "Abbrechen")
        dialog.add_response("menu", "Nur Menüeintrag")
        dialog.add_response("all", "Programm und Umgebung")
        dialog.set_response_appearance("all", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", self.on_remove_response, entry)
        dialog.present()

    def on_remove_response(self, dialog: Adw.MessageDialog, response: str, entry: dict) -> None:
        dialog.close()
        if response == "cancel":
            return
        entries = load_registry()
        if response == "menu":
            remove_entry_files(entry)
            entries = [item for item in entries if item.get("id") != entry.get("id")]
        else:
            entries = remove_environment(entry.get("environment_id", "legacy"), entries)
        save_registry(entries)
        self.refresh_all()
        self.toast("Windows-Programm wurde entfernt")

    def on_delete_environment(self, _button: Gtk.Button, environment: str) -> None:
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Programmumgebung löschen?",
            body="Alle Programme, Einstellungen und Daten in dieser Umgebung werden endgültig gelöscht.",
        )
        dialog.add_response("cancel", "Abbrechen")
        dialog.add_response("delete", "Löschen")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", self.on_delete_environment_response, environment)
        dialog.present()

    def on_delete_environment_response(self, dialog: Adw.MessageDialog, response: str, environment: str) -> None:
        dialog.close()
        if response != "delete":
            return
        save_registry(remove_environment(environment, load_registry()))
        self.refresh_all()
        self.toast("Programmumgebung wurde gelöscht")


class InstallerApplication(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self.window: InstallerWindow | None = None

    def do_activate(self) -> None:
        self.ensure_window().present()

    def do_open(self, files, n_files, hint) -> None:
        target = None
        if n_files:
            path = files[0].get_path()
            if path:
                target = Path(path)
        window = self.ensure_window()
        window.present()
        if target:
            GLib.idle_add(window.start_install, target)

    def ensure_window(self) -> InstallerWindow:
        if self.window is None:
            self.window = InstallerWindow(self)
        return self.window


def main() -> int:
    ensure_dirs()
    if "--repair-shortcuts" in sys.argv:
        repaired, pinned = repair_registered_shortcuts()
        print(f"LiMaD-Programmstarter repariert: {repaired}; Dock-Einträge bestätigt: {pinned}")
        return 0
    try:
        repair_registered_shortcuts()
    except Exception as exc:
        log(f"automatic shortcut migration failed: {exc}")
    return InstallerApplication().run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Runtime helpers for LiMaD Klang.

The module has no GTK dependency so it can be exercised by the offline test
suite.  EasyEffects 8.2.8 offers two useful control paths:

* the local ``EasyEffectsServer`` Unix socket for immediate live control;
* the normal EasyEffects command line for loading a rewritten LiMaD preset.

The second path is an intentional compatibility fallback.  It keeps the LiMaD
sliders useful even if the local server is disabled or is exposed in a
Flatpak-specific runtime subdirectory.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import socket
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

EE_ID = "com.github.wwmm.easyeffects"
MIN_VERSION = (8, 2, 8)
PRESET_NAME = "LiMaD Klang"
BANDS: dict[str, tuple[int, ...]] = {
    "bass": (0, 1, 2),
    "mid": (3, 4, 5, 6),
    "treble": (7, 8, 9),
}


@dataclass(frozen=True)
class EasyEffectsInstall:
    installed: bool
    version: tuple[int, int, int] | None
    version_text: str | None
    source: str


@dataclass(frozen=True)
class CliResult:
    ok: bool
    detail: str


def run_quiet(
    args: list[str],
    *,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
            env=os.environ.copy(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(args, 124, "", str(exc))


def _normalise_version(value: str) -> tuple[int, int, int] | None:
    numbers = [int(item) for item in re.findall(r"\d+", value)[:3]]
    if not numbers:
        return None
    return tuple((numbers + [0, 0, 0])[:3])  # type: ignore[return-value]


def parse_flatpak_list(output: str, app_id: str = EE_ID) -> tuple[str, tuple[int, int, int]] | None:
    """Parse ``flatpak list --columns=application,version`` output."""
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "\t" in line:
            application, version_text = (part.strip() for part in line.split("\t", 1))
        else:
            parts = line.split(None, 1)
            if len(parts) != 2:
                continue
            application, version_text = parts
        if application != app_id or not version_text:
            continue
        version = _normalise_version(version_text)
        if version is not None:
            return version_text, version
    return None


def parse_flatpak_info(output: str) -> tuple[str, tuple[int, int, int]] | None:
    """Fallback parser for the human-readable ``flatpak info`` output."""
    for raw_line in output.splitlines():
        match = re.match(r"^\s*(?:Version|Versione|Versión):\s*(\S.*?)\s*$", raw_line)
        if not match:
            continue
        version_text = match.group(1)
        version = _normalise_version(version_text)
        if version is not None:
            return version_text, version
    return None


def detect_easyeffects() -> EasyEffectsInstall:
    flatpak = shutil.which("flatpak")
    if not flatpak:
        return EasyEffectsInstall(False, None, None, "flatpak-missing")

    listing = run_quiet([flatpak, "list", "--app", "--columns=application,version"])
    parsed = parse_flatpak_list(listing.stdout)
    if parsed is not None:
        version_text, version = parsed
        return EasyEffectsInstall(True, version, version_text, "flatpak-list")

    info = run_quiet([flatpak, "info", EE_ID])
    if info.returncode != 0:
        return EasyEffectsInstall(False, None, None, "flatpak-info")
    parsed = parse_flatpak_info(info.stdout)
    if parsed is None:
        return EasyEffectsInstall(True, None, None, "flatpak-info-no-version")
    version_text, version = parsed
    return EasyEffectsInstall(True, version, version_text, "flatpak-info")


def version_supported(version: tuple[int, int, int] | None) -> bool | None:
    if version is None:
        return None
    return version >= MIN_VERSION


def first_float(value: str) -> float | None:
    match = re.search(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", value)
    return float(match.group(0)) if match else None


def version_string(version: tuple[int, int, int] | None, raw: str | None = None) -> str:
    if raw:
        return raw
    if version is None:
        return "unbekannt"
    return ".".join(str(item) for item in version)


def runtime_dir() -> Path:
    return Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))


def _walk_named_socket(root: Path, max_depth: int = 5) -> Iterable[Path]:
    if not root.is_dir():
        return
    root_depth = len(root.parts)
    for current, dirs, files in os.walk(root):
        current_path = Path(current)
        depth = len(current_path.parts) - root_depth
        if depth >= max_depth:
            dirs[:] = []
        if "EasyEffectsServer" in files:
            yield current_path / "EasyEffectsServer"


def socket_candidates(base: Path | None = None) -> list[Path]:
    base = base or runtime_dir()
    candidates: list[Path] = []
    override = os.environ.get("LIMAD_EASYEFFECTS_SOCKET", "").strip()
    if override:
        candidates.append(Path(override))
    candidates.extend(
        [
            base / "EasyEffectsServer",
            base / "app" / EE_ID / "EasyEffectsServer",
            base / ".flatpak" / EE_ID / "EasyEffectsServer",
        ]
    )
    candidates.extend(_walk_named_socket(base))

    unique: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def usable_socket(path: Path) -> bool:
    try:
        info = path.stat()
    except OSError:
        return False
    return stat.S_ISSOCK(info.st_mode) and info.st_uid == os.getuid()


def find_easyeffects_socket(base: Path | None = None) -> Path | None:
    for path in socket_candidates(base):
        if usable_socket(path):
            return path
    return None


def send_socket_command(path: Path, command: str, timeout: float = 1.5) -> str:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        client.connect(str(path))
        client.sendall((command + "\n").encode("utf-8"))
        try:
            data = client.recv(4096)
        except (socket.timeout, ConnectionResetError):
            data = b""
    return data.decode("utf-8", errors="replace").strip()


def preset_targets(home: Path | None = None) -> list[Path]:
    home = home or Path.home()
    data_home = Path(os.environ.get("XDG_DATA_HOME", home / ".local/share"))
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    app_root = home / ".var/app" / EE_ID
    candidates = [
        app_root / "data/easyeffects/output" / f"{PRESET_NAME}.json",
        app_root / "config/easyeffects/output" / f"{PRESET_NAME}.json",
        data_home / "easyeffects/output" / f"{PRESET_NAME}.json",
        config_home / "easyeffects/output" / f"{PRESET_NAME}.json",
    ]
    result: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key not in seen:
            seen.add(key)
            result.append(path)
    return result


def _normalised_values(values: Mapping[str, float]) -> dict[str, float]:
    return {
        key: max(-12.0, min(12.0, round(float(values.get(key, 0.0)) * 2.0) / 2.0))
        for key in BANDS
    }


def render_preset(values: Mapping[str, float], source: Path) -> dict[str, object]:
    payload = json.loads(source.read_text(encoding="utf-8"))
    eq = payload["output"]["equalizer#0"]
    normal = _normalised_values(values)
    for section, bands in BANDS.items():
        for channel in ("left", "right"):
            for band in bands:
                eq[channel][f"band{band}"]["gain"] = normal[section]
    eq["bypass"] = False
    eq["output-gain"] = round(-0.75 * max(0.0, *normal.values()), 2)
    return payload


def write_user_preset(
    values: Mapping[str, float],
    *,
    source: Path | None = None,
    targets: Iterable[Path] | None = None,
) -> list[Path]:
    source = source or Path("/usr/share/limad-klang") / f"{PRESET_NAME}.json"
    if not source.is_file():
        raise FileNotFoundError(source)
    payload = render_preset(values, source)
    serialised = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    written: list[Path] = []
    for target in list(targets) if targets is not None else preset_targets():
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            delete=False,
        ) as handle:
            handle.write(serialised)
            temp_path = Path(handle.name)
        os.chmod(temp_path, 0o644)
        temp_path.replace(target)
        written.append(target)
    return written


def _flatpak_action(arguments: list[str], timeout: float = 8.0) -> CliResult:
    flatpak = shutil.which("flatpak")
    if not flatpak:
        return CliResult(False, "flatpak fehlt")
    command = [flatpak, "run", EE_ID, *arguments]
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
            env=os.environ.copy(),
        )
    except OSError as exc:
        return CliResult(False, str(exc))
    try:
        _, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        # A newly started EasyEffects service intentionally remains alive.  The
        # command was accepted, so a still-running process is not an error.
        return CliResult(True, "EasyEffects läuft")
    if process.returncode == 0:
        return CliResult(True, "OK")
    return CliResult(False, (stderr or f"Exit {process.returncode}").strip())


def start_hidden_cli() -> CliResult:
    # The documented short option is used first.  The long spelling remains a
    # compatibility fallback for older Flatpak builds.
    result = _flatpak_action(["-w"], timeout=5.0)
    if result.ok:
        return result
    return _flatpak_action(["--hide-window"], timeout=5.0)


def load_preset_cli() -> CliResult:
    # Loading a local preset does not depend on the optional local socket
    # server.  This is the reliable control path on every supported build.
    result = _flatpak_action(["-l", PRESET_NAME], timeout=8.0)
    if result.ok:
        return result
    return _flatpak_action(["--load-preset", PRESET_NAME], timeout=8.0)


def set_bypass_cli(bypass: bool) -> CliResult:
    # EasyEffects CLI: 1 enables bypass, 2 disables bypass.
    value = "1" if bypass else "2"
    result = _flatpak_action(["--bypass", value], timeout=5.0)
    if result.ok:
        return result
    return _flatpak_action(["-b", value], timeout=5.0)

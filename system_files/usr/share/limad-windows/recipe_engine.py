#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Plan:
    recipe: str
    profile: str
    windows_version: str
    architecture: str
    dependencies: tuple[str, ...]
    optional_dependencies: tuple[str, ...]
    warnings: tuple[str, ...]
    blockers: tuple[str, ...]
    reasons: tuple[str, ...]
    confidence: int


PROFILES = {
    "standard": ("win10", ("vcrun2022",), ()),
    "dotnet": ("win11", ("dotnet48",), ("vcrun2022",)),
    "office": ("win10", ("riched20", "msxml6", "vcrun2022"), ("access2016",)),
    "cad": ("win10", ("vcrun2022", "dxvk"), ("d3dcompiler_47",)),
    "creative": ("win10", ("vcrun2022", "dxvk"), ("webview2",)),
    "gaming": ("win10", ("vcrun2022", "dxvk", "vkd3d"), ("d3dcompiler_47",)),
    "legacy": ("win7", ("vcrun2010", "d3dx9"), ("dotnet35",)),
    "minimal": ("win10", (), ()),
    "nws": ("win10", ("dotnet48", "d3dx9", "d3dcompiler_47", "corefonts"), ()),
}

RECIPES = (
    ("nws", re.compile(r"(nws[-_ ]?desktop|new[-_ ]?world[-_ ]?scheduler|jw[-_ ]?scheduler)", re.I), "nws"),
    ("office", re.compile(r"(office|microsoft[ _-]?365|m365|winword|excel|powerpoint|access)", re.I), "office"),
    ("adobe", re.compile(r"(photoshop|illustrator|lightroom|adobe|creative[ _-]?cloud)", re.I), "creative"),
    ("gaming", re.compile(r"(battle[._ -]?net|epic[ _-]?games|gog|ubisoft|ea[ _-]?app|game|launcher)", re.I), "gaming"),
    ("cad", re.compile(r"(autocad|solidworks|fusion[ _-]?360|cad|cam|slicer)", re.I), "cad"),
    ("legacy", re.compile(r"(setup32|win32|legacy|classic|old)", re.I), "legacy"),
)

SIGNALS = (
    (re.compile(r"webview2|msedgewebview2", re.I), "webview2", "Microsoft Edge WebView2 erkannt"),
    (re.compile(r"\.net desktop runtime 9|windowsdesktop-runtime-9", re.I), "dotnetdesktop9", ".NET Desktop Runtime 9 erkannt"),
    (re.compile(r"\.net desktop runtime 8|windowsdesktop-runtime-8", re.I), "dotnetdesktop8", ".NET Desktop Runtime 8 erkannt"),
    (re.compile(r"\.net desktop runtime 6|windowsdesktop-runtime-6", re.I), "dotnetdesktop6", ".NET Desktop Runtime 6 erkannt"),
    (re.compile(r"d3dcompiler_47|d3dcompiler47", re.I), "d3dcompiler_47", "DirectX-Compiler erkannt"),
    (re.compile(r"d3dx9|directx 9", re.I), "d3dx9", "DirectX 9 erkannt"),
    (re.compile(r"java runtime|jre|javaw\.exe", re.I), "java", "Java-Laufzeit erkannt"),
    (re.compile(r"access database engine|aceoledb|microsoft\.ace\.oledb", re.I), "access2016", "Access Database Engine erkannt"),
)

BLOCKERS = (
    (re.compile(r"kernel driver|device driver|\.sys\b|windows driver package", re.I), "Geräte- oder Kerneltreiber erkannt"),
    (re.compile(r"easyanticheat|battleye|vanguard|anti[- ]?cheat", re.I), "Anti-Cheat-Treiber erkannt"),
    (re.compile(r"hasp|sentinel ldk|usb dongle", re.I), "USB-Dongle- oder Lizenztreiber erkannt"),
    (re.compile(r"microsoft store|uwp|appx|msix", re.I), "Microsoft-Store-, UWP- oder MSIX-Komponente erkannt"),
    (re.compile(r"sql server express localdb|sqllocaldb", re.I), "SQL Server LocalDB erkannt"),
)

DEPENDENCY_LABELS = {
    "vcrun2022": "Microsoft Visual C++ 2015–2022",
    "vcrun2019": "Microsoft Visual C++ 2019",
    "vcrun2015": "Microsoft Visual C++ 2015",
    "vcrun2013": "Microsoft Visual C++ 2013",
    "vcrun2012": "Microsoft Visual C++ 2012",
    "vcrun2010": "Microsoft Visual C++ 2010",
    "vcrun2008": "Microsoft Visual C++ 2008",
    "vcrun2005": "Microsoft Visual C++ 2005",
    "dotnet35": ".NET Framework 3.5",
    "dotnet40": ".NET Framework 4.0",
    "dotnet46": ".NET Framework 4.6",
    "dotnet48": ".NET Framework 4.8",
    "dotnetdesktop6": ".NET Desktop Runtime 6",
    "dotnetdesktop8": ".NET Desktop Runtime 8",
    "dotnetdesktop9": ".NET Desktop Runtime 9",
    "webview2": "Microsoft Edge WebView2",
    "d3dx9": "DirectX 9 DLLs",
    "d3dcompiler_47": "DirectX Compiler 47",
    "dxvk": "DXVK",
    "vkd3d": "VKD3D",
    "riched20": "RichEdit 2.0",
    "msxml6": "MSXML 6",
    "java": "Java Runtime",
    "access2016": "Access Database Engine",
    "allfonts": "Alle Microsoft-Schriftarten",
    "corefonts": "Microsoft Core Fonts",
}


def dependency_label(name: str) -> str:
    return DEPENDENCY_LABELS.get(name, name)


def detect_architecture(path: Path) -> str:
    if shutil.which("file") is None or not path.is_file():
        return "win64"
    try:
        result = subprocess.run(
            ["file", "-b", str(path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "win64"
    text = result.stdout.lower()
    if "pe32+" in text or "x86-64" in text or "aarch64" in text:
        return "win64"
    if "pe32" in text or "80386" in text:
        return "win32"
    return "win64"


def inspect_strings(path: Path) -> str:
    if shutil.which("strings") is None or not path.is_file():
        return path.name
    try:
        result = subprocess.run(
            ["strings", "-a", "-n", "6", str(path)],
            check=False,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=25,
        )
    except (OSError, subprocess.TimeoutExpired):
        return path.name
    return f"{path.name}\n{result.stdout[:2_000_000]}"


def unique(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def analyze(path: Path, forced_profile: str | None = None) -> Plan:
    suffix = path.suffix.lower()
    if suffix not in {".exe", ".msi"}:
        raise ValueError("Nur EXE- und MSI-Dateien werden unterstützt.")
    if forced_profile is not None and forced_profile not in PROFILES:
        raise ValueError(f"Unbekanntes Profil: {forced_profile}")

    architecture = detect_architecture(path)
    evidence = inspect_strings(path)
    recipe = "generic"
    profile = forced_profile or "standard"
    reasons: list[str] = []
    warnings: list[str] = []
    blockers: list[str] = []
    confidence = 45

    if forced_profile is None:
        for candidate, pattern, detected_profile in RECIPES:
            if pattern.search(evidence):
                recipe = candidate
                profile = detected_profile
                reasons.append(f"Dateiinhalt oder Dateiname passt zum Rezept {candidate}")
                confidence = 82
                break
    else:
        recipe = "manual"
        reasons.append(f"Profil {forced_profile} wurde manuell gewählt")
        confidence = 100

    windows_version, required, optional = PROFILES[profile]
    required_list = list(required)
    optional_list = list(optional)

    for pattern, dependency, reason in SIGNALS:
        if pattern.search(evidence):
            if dependency not in required_list:
                optional_list.append(dependency)
            reasons.append(reason)
            confidence = min(98, confidence + 4)

    for pattern, warning in BLOCKERS:
        if pattern.search(evidence):
            blockers.append(warning)

    if recipe == "nws":
        blockers.clear()
        reasons.append("Bekanntes NWS-Installationsprofil verwendet; allgemeine Installer-Stringtreffer werden nicht als Blocker gewertet")
        confidence = max(confidence, 95)
    elif blockers:
        warnings.append("Die Anwendung verwendet möglicherweise Windows-Komponenten, die Wine nicht bereitstellen kann.")
        confidence = min(confidence, 35)

    reasons.append("MSI-Paket erkannt" if suffix == ".msi" else "EXE-Datei erkannt")
    reasons.append(f"{architecture}-Architektur erkannt oder als sicherer Standard gewählt")
    warnings.append("Automatische Erkennung ist eine technische Einschätzung und keine Kompatibilitätsgarantie.")

    return Plan(
        recipe=recipe,
        profile=profile,
        windows_version=windows_version,
        architecture=architecture,
        dependencies=unique(required_list),
        optional_dependencies=unique(optional_list),
        warnings=unique(warnings),
        blockers=unique(blockers),
        reasons=unique(reasons),
        confidence=confidence,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("file", type=Path)
    parser.add_argument("--profile", choices=sorted(PROFILES))
    args = parser.parse_args()
    try:
        plan = analyze(args.file, args.profile)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(asdict(plan), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

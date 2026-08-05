#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath

FORMAT = "org.limad.app-update"
KNOWN_APPS = {
    "de.limad.Cut": "LiMaDCut",
    "de.limad.Study": "LiMaD Study",
    "de.limad.Drop": "LiDrop",
    "de.limad.Link": "LiLink",
    "de.limad.Notes": "LiNotes",
    "de.limad.Save": "LiSave",
    "de.limad.ScreenShare": "LiMaD auf TV übertragen",
    "de.limad.AnycubicSlicerNext": "Anycubic Slicer Next",
    "de.limad.WindowsApps": "Windows-Programme",
}
VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+~-]{0,95}$")


def files(root):
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise SystemExit(f"Symbolische Links sind nicht erlaubt: {path}")
        if path.is_file():
            yield path


def zip_info(name, executable=False):
    info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
    mode = 0o755 if executable else 0o644
    info.external_attr = (stat.S_IFREG | mode) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def main():
    parser = argparse.ArgumentParser(description="Erzeugt ein LiMaD-App-Update-ZIP.")
    parser.add_argument("--app-id", required=True, choices=sorted(KNOWN_APPS))
    parser.add_argument("--version", required=True)
    parser.add_argument("--payload", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--name")
    args = parser.parse_args()
    if not VERSION_RE.fullmatch(args.version):
        raise SystemExit("Ungültige Versionsnummer.")
    payload = args.payload.resolve()
    if not payload.is_dir():
        raise SystemExit(f"Payload-Ordner fehlt: {payload}")
    output = args.output.resolve()
    if output.suffix != ".zip" or not output.name.endswith(".limad-update.zip"):
        raise SystemExit("Der Dateiname muss auf .limad-update.zip enden.")
    manifest = {
        "format": FORMAT,
        "format_version": 1,
        "app_id": args.app_id,
        "name": args.name or KNOWN_APPS[args.app_id],
        "version": args.version,
    }
    payload_entries = []
    sums = []
    for path in files(payload):
        rel = PurePosixPath(path.relative_to(payload).as_posix())
        archive_name = f"payload/{rel}"
        content = path.read_bytes()
        payload_entries.append((archive_name, content, os.access(path, os.X_OK)))
        sums.append(f"{hashlib.sha256(content).hexdigest()}  {archive_name}")
    if not payload_entries:
        raise SystemExit("Der Payload-Ordner ist leer.")
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(output.suffix + ".tmp")
    with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr(zip_info("limad-update.json"), json.dumps(manifest, ensure_ascii=False, indent=2).encode() + b"\n")
        zf.writestr(zip_info("SHA256SUMS"), ("\n".join(sums) + "\n").encode())
        for name, content, executable in payload_entries:
            zf.writestr(zip_info(name, executable), content)
    os.replace(temp, output)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    print(f"Erstellt: {output}")
    print(f"SHA256:  {digest}")


if __name__ == "__main__":
    main()

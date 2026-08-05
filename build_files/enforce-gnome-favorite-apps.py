#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

SECTION = "org.gnome.shell"
KEY = "favorite-apps"
REQUIRED = [
    'app.zen_browser.zen.desktop',
    'de.limad.Mail.desktop',
    'de.limad.Cut.desktop',
    'de.limad.Study.desktop',
    'de.limad.Notes.desktop',
    'de.limad.Drop.desktop',
    'de.limad.Link.desktop',
    'de.limad.Save.desktop',
    'de.limad.WindowsApps.desktop',
    'de.limad.Updater.desktop',
    'de.limad.AnycubicSlicerNext.desktop',
    'us.zoom.Zoom.desktop',
    'app.ytmdesktop.ytmdesktop.desktop',
    'org.libreoffice.LibreOffice.desktop',
    'de.limad.Klang.desktop',
    'de.limad.Terminal.desktop',
    'io.github.kolunmi.Bazaar.desktop',
    'org.gnome.Nautilus.desktop',
]

def desired_value() -> str:
    return repr(REQUIRED)


def normalize_override(path: Path) -> bool:
    lines = path.read_text(encoding="utf-8").splitlines()
    changed = False
    section: str | None = None
    output: list[str] = []
    for line in lines:
        match = re.match(r"^\s*\[([^]]+)]\s*$", line)
        if match:
            section = match.group(1)
            output.append(line)
            continue
        if section == SECTION:
            key_match = re.match(r"^(\s*)favorite-apps\s*=\s*(.*)$", line)
            if key_match:
                replacement = f"{key_match.group(1)}{KEY}={desired_value()}"
                if replacement != line:
                    changed = True
                output.append(replacement)
                continue
        output.append(line)
    if changed:
        path.write_text("\n".join(output) + "\n", encoding="utf-8")
    return changed


def write_canonical(path: Path) -> None:
    path.write_text(f"[{SECTION}]\n{KEY}={desired_value()}\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("schema_dir", type=Path)
    parser.add_argument("--canonical-name", default="zzzzzzzzzzzz-limad-favorite-apps.gschema.override")
    args = parser.parse_args()
    schema_dir = args.schema_dir.resolve()
    if not schema_dir.is_dir():
        raise SystemExit(f"schema directory missing: {schema_dir}")

    canonical = schema_dir / args.canonical_name
    write_canonical(canonical)
    changed: list[str] = []
    for override in sorted(schema_dir.glob("*.gschema.override")):
        if normalize_override(override):
            changed.append(override.name)

    print(f"canonical dock favorites override: {canonical.name}")
    if changed:
        print("normalized conflicting favorite-apps override files:")
        for name in changed:
            print(f"  {name}")
    else:
        print("no conflicting favorite-apps override values found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

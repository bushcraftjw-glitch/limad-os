#!/usr/bin/env python3
from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

VALUES = {
    "custom-icon-path": "'/usr/share/icons/LiMaD/64x64/apps/limad-start.png'",
    "menu-button-icon-image": "0",
    "menu-button-icon-size": "24",
    "symbolic-icon": "false",
    "hide-icon-shadow": "true",
    "show-activities-button": "false",
    "use-custom-icon": "true",
    "custom-icon": "true",
}


def patch_schema_directory(schema_dir: Path) -> set[str]:
    found: set[str] = set()
    schemas = sorted(schema_dir.glob("*.gschema.xml"))
    if not schemas:
        raise SystemExit("FATAL: Logo Menu schemas directory contains no .gschema.xml file")
    for path in schemas:
        tree = ET.parse(path)
        changed = False
        for key in tree.getroot().iter("key"):
            name = key.get("name", "")
            if name not in VALUES:
                continue
            default = key.find("default")
            if default is None:
                continue
            default.text = VALUES[name]
            found.add(name)
            changed = True
        if changed:
            tree.write(path, encoding="utf-8", xml_declaration=True)
    if "custom-icon-path" not in found:
        raise SystemExit("FATAL: Logo Menu schema has no custom-icon-path key")
    if not ({"use-custom-icon", "custom-icon"} & found):
        raise SystemExit("FATAL: Logo Menu schema has no custom icon enable switch")
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("schema_dir", type=Path)
    args = parser.parse_args()
    if not args.schema_dir.is_dir():
        raise SystemExit(f"FATAL: Logo Menu schema directory missing: {args.schema_dir}")
    found = patch_schema_directory(args.schema_dir)
    print("   Logo Menu LiMaD defaults patched: " + ", ".join(sorted(found)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

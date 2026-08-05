#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

TARGETS = {
    "org.gnome.desktop.background": {
        "picture-uri": None,
        "picture-uri-dark": None,
        "picture-options": "'zoom'",
    },
    "org.gnome.desktop.screensaver": {
        "picture-uri": None,
        "picture-options": "'zoom'",
    },
}


def rewrite_override(path: Path, wallpaper_uri: str) -> bool:
    lines = path.read_text(encoding="utf-8").splitlines()
    changed = False
    current_section: str | None = None
    seen: dict[str, set[str]] = {name: set() for name in TARGETS}
    output: list[str] = []

    def append_missing(section: str | None) -> None:
        nonlocal changed
        if section not in TARGETS:
            return
        values = dict(TARGETS[section])
        values["picture-uri"] = f"'{wallpaper_uri}'"
        if section == "org.gnome.desktop.background":
            values["picture-uri-dark"] = f"'{wallpaper_uri}'"
        for key, value in values.items():
            if key not in seen[section]:
                output.append(f"{key}={value}")
                changed = True

    for line in lines:
        section_match = re.match(r"^\s*\[([^]]+)]\s*$", line)
        if section_match:
            append_missing(current_section)
            current_section = section_match.group(1)
            output.append(line)
            continue

        if current_section in TARGETS:
            key_match = re.match(r"^(\s*)(picture-uri-dark|picture-uri|picture-options)\s*=.*$", line)
            if key_match:
                key = key_match.group(2)
                if key in TARGETS[current_section]:
                    value = f"'{wallpaper_uri}'" if key.startswith("picture-uri") else "'zoom'"
                    replacement = f"{key_match.group(1)}{key}={value}"
                    if replacement != line:
                        changed = True
                    output.append(replacement)
                    seen[current_section].add(key)
                    continue

        output.append(line)

    append_missing(current_section)

    if changed:
        path.write_text("\n".join(output) + "\n", encoding="utf-8")
    return changed


def write_canonical(path: Path, wallpaper_uri: str) -> None:
    path.write_text(
        "\n".join(
            [
                "[org.gnome.desktop.background]",
                f"picture-uri='{wallpaper_uri}'",
                f"picture-uri-dark='{wallpaper_uri}'",
                "picture-options='zoom'",
                "",
                "[org.gnome.desktop.screensaver]",
                f"picture-uri='{wallpaper_uri}'",
                "picture-options='zoom'",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("schema_dir", type=Path)
    parser.add_argument("wallpaper", type=Path)
    parser.add_argument(
        "--canonical-name",
        default="zzzzzzzzzz-limad-wallpaper.gschema.override",
    )
    args = parser.parse_args()

    schema_dir = args.schema_dir.resolve()
    wallpaper = args.wallpaper.resolve()
    if not schema_dir.is_dir():
        raise SystemExit(f"schema directory missing: {schema_dir}")
    if not wallpaper.is_file():
        raise SystemExit(f"wallpaper missing: {wallpaper}")

    wallpaper_uri = f"file://{wallpaper}"
    canonical = schema_dir / args.canonical_name
    write_canonical(canonical, wallpaper_uri)

    changed: list[str] = []
    for override in sorted(schema_dir.glob("*.gschema.override")):
        if rewrite_override(override, wallpaper_uri):
            changed.append(override.name)

    print(f"canonical wallpaper override: {canonical.name}")
    if changed:
        print("normalized conflicting override files:")
        for name in changed:
            print(f"  {name}")
    else:
        print("no conflicting wallpaper override values found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

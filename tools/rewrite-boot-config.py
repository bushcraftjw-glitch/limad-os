#!/usr/bin/env python3
import re
import sys
from pathlib import Path


def replace_visible_branding(line: str, version: str) -> str:
    visible = re.compile(r"Bazzite(?: Linux)?(?: [0-9][^\n\"']*)?|Fedora(?: Linux)?(?: [0-9][^\n\"']*)?", re.I)
    stripped = line.lstrip().lower()
    if stripped.startswith(("menuentry ", "submenu ", "menu label ", "menu title ", "title ")):
        return visible.sub(f"LiMaD OS {version}", line)
    return line


def replace_option_value(line: str, pattern: str, volume_id: str) -> str:
    def replacement(match: re.Match[str]) -> str:
        quote = match.group(2) or match.group(4)
        return f"{match.group(1)}{quote}{volume_id}{quote}"

    return re.sub(pattern, replacement, line)


def rewrite_label_variables(line: str, volume_id: str) -> str:
    return re.sub(
        r"^(\s*set\s+(?:iso_?label|isolabel|volume_?id|volid|cdlabel)\s*=\s*)([\"']?)([^\s\"']+)([\"']?)(\s*)$",
        lambda match: f"{match.group(1)}{match.group(2) or match.group(4)}{volume_id}{match.group(4) or match.group(2)}{match.group(5)}",
        line,
        flags=re.I,
    )


def rewrite_search_fs_label(line: str, volume_id: str) -> str:
    return re.sub(
        r"^(\s*search\.fs_label\s+)([\"']?)([^\s\"']+)([\"']?)(.*)$",
        lambda match: f"{match.group(1)}{match.group(2) or match.group(4)}{volume_id}{match.group(4) or match.group(2)}{match.group(5)}",
        line,
        flags=re.I,
    )


def rewrite_label_references(line: str, volume_id: str) -> str:
    patterns = (
        r"(inst\.stage2=hd:LABEL=)([^:\s\"']+)",
        r"(inst\.ks=hd:LABEL=)([^:\s\"']+)",
        r"(root=live:CDLABEL=)([^\s\"']+)",
        r"(root=live:LABEL=)([^\s\"']+)",
        r"(live:CDLABEL=)([^\s\"']+)",
    )
    for pattern in patterns:
        line = re.sub(pattern, lambda match: match.group(1) + volume_id, line)

    line = rewrite_label_variables(line, volume_id)
    line = rewrite_search_fs_label(line, volume_id)

    line = replace_option_value(
        line,
        r"((?:--label|--fs-label)(?:=|\s+))([\"']?)([^\s\"']+)([\"']?)",
        volume_id,
    )

    if re.match(r"^\s*search(?:\.file|\.fs_uuid|\.fs_label)?\b", line):
        line = replace_option_value(
            line,
            r"((?<!\S)-[lL](?:=|\s+))([\"']?)([^\s\"']+)([\"']?)",
            volume_id,
        )

    return line


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit("usage: rewrite-boot-config.py FILE VERSION VOLUME_ID")
    path = Path(sys.argv[1])
    version = sys.argv[2]
    volume_id = sys.argv[3]
    text = path.read_text(errors="replace")
    rewritten = []
    for line in text.splitlines(keepends=True):
        line = rewrite_label_references(line, volume_id)
        line = replace_visible_branding(line, version)
        rewritten.append(line)
    path.write_text("".join(rewritten))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

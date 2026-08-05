#!/usr/bin/env python3
import re
import sys
from pathlib import Path


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit('usage: audit-boot-config.py FILE EXPECTED_LABEL CONTEXT')

    path = Path(sys.argv[1])
    expected = sys.argv[2]
    context = sys.argv[3]
    text = path.read_text(errors='replace')

    variables: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r'^\s*set\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$', line)
        if match:
            variables[match.group(1)] = unquote(match.group(2))

    def resolve(value: str) -> str:
        value = unquote(value)
        match = re.fullmatch(r'\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))', value)
        if match:
            name = match.group(1) or match.group(2)
            if name not in variables:
                raise SystemExit(f'ISO CHECK FAILED: unresolved label variable {value!r} in {context}')
            return variables[name]
        return value

    visible_lines = [
        line for line in text.splitlines()
        if line.lstrip().lower().startswith(('menuentry ', 'submenu ', 'menu label ', 'menu title ', 'title '))
    ]
    for line in visible_lines:
        stripped = line.lstrip()
        visible_text = stripped
        if stripped.lower().startswith(('menuentry ', 'submenu ')):
            match = re.match(r"^(?:menuentry|submenu)\s+(?:'([^']*)'|\"([^\"]*)\"|([^\s{]+))", stripped, re.I)
            if match:
                visible_text = next((group for group in match.groups() if group is not None), stripped)
        else:
            visible_text = re.sub(r'^(?:menu label|menu title|title)\s+', '', stripped, flags=re.I)
        if re.search(r'Bazzite|Fedora', visible_text, re.I):
            raise SystemExit(f'ISO CHECK FAILED: upstream brand remains in visible boot title in {context}: {visible_text}')

    label_patterns = (
        r'inst\.stage2=hd:LABEL=([^:\s"\']+)',
        r'inst\.ks=hd:LABEL=([^:\s"\']+)',
        r'root=live:CDLABEL=([^\s"\']+)',
        r'root=live:LABEL=([^\s"\']+)',
        r'live:CDLABEL=([^\s"\']+)',
    )
    for pattern in label_patterns:
        for value in re.findall(pattern, text):
            actual = resolve(value)
            if actual != expected:
                raise SystemExit(f'ISO CHECK FAILED: label reference {actual!r} != {expected!r} in {context}')

    relevant_variables = re.compile(r'^(?:iso_?label|isolabel|volume_?id|volid|cdlabel)$', re.I)
    for name, value in variables.items():
        if relevant_variables.match(name) and resolve(value) != expected:
            raise SystemExit(f'ISO CHECK FAILED: label variable {name}={value!r} != {expected!r} in {context}')

    search_values: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r'^search(?:\.file|\.fs_uuid|\.fs_label)?\b', stripped, re.I):
            for pattern in (
                r'(?:--label|--fs-label)(?:=|\s+)(["\']?[^\s"\']+["\']?)',
                r'(?<!\S)-[lL](?:=|\s+)(["\']?[^\s"\']+["\']?)',
            ):
                search_values.extend(re.findall(pattern, stripped))
            match = re.match(r'^search\.fs_label\s+(["\']?[^\s"\']+["\']?)', stripped, re.I)
            if match:
                search_values.append(match.group(1))

    for value in search_values:
        actual = resolve(value)
        if actual != expected:
            raise SystemExit(f'ISO CHECK FAILED: GRUB search label {actual!r} != {expected!r} in {context}')

    seen: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        match = re.match(r'^(?:linux|linuxefi|linux16|initrd|initrdefi|initrd16)\s+([^\s]+)', stripped, re.I)
        if not match:
            continue
        value = unquote(match.group(1))
        if value.startswith('/') and value not in seen:
            seen.add(value)
            print(value)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())

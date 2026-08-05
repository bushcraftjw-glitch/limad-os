#!/usr/bin/env python3
import hashlib
import re
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    if len(sys.argv) < 3:
        raise SystemExit('usage: update-treeinfo-checksums.py TREEINFO ISO_PATH=LOCAL_FILE [...]')

    treeinfo = Path(sys.argv[1])
    replacements: dict[str, str] = {}
    for item in sys.argv[2:]:
        iso_path, separator, local_path = item.partition('=')
        if not separator or not iso_path or not local_path:
            raise SystemExit(f'invalid mapping: {item!r}')
        key = iso_path.lstrip('/')
        local = Path(local_path)
        if not local.is_file() or local.stat().st_size == 0:
            raise SystemExit(f'cannot checksum missing or empty file: {local}')
        replacements[key] = f'sha256:{sha256(local)}'

    lines = treeinfo.read_text(errors='strict').splitlines()
    output: list[str] = []
    section = ''
    seen: set[str] = set()
    checksums_seen = False

    for line in lines:
        section_match = re.match(r'^\s*\[([^]]+)]\s*$', line)
        if section_match:
            if section.lower() == 'checksums':
                for key, value in replacements.items():
                    if key not in seen:
                        output.append(f'{key} = {value}')
                        seen.add(key)
            section = section_match.group(1)
            if section.lower() == 'checksums':
                checksums_seen = True
            output.append(line)
            continue

        if section.lower() == 'checksums':
            match = re.match(r'^(\s*)([^=]+?)(\s*=\s*)(\S+)(\s*)$', line)
            if match:
                key = match.group(2).strip()
                if key in replacements:
                    output.append(f'{match.group(1)}{key}{match.group(3)}{replacements[key]}{match.group(5)}')
                    seen.add(key)
                    continue
        output.append(line)

    if section.lower() == 'checksums':
        for key, value in replacements.items():
            if key not in seen:
                output.append(f'{key} = {value}')
                seen.add(key)

    if not checksums_seen:
        if output and output[-1] != '':
            output.append('')
        output.append('[checksums]')
        for key, value in replacements.items():
            output.append(f'{key} = {value}')
            seen.add(key)

    missing = set(replacements) - seen
    if missing:
        raise SystemExit(f'failed to update treeinfo checksum(s): {sorted(missing)}')

    treeinfo.write_text('\n'.join(output) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

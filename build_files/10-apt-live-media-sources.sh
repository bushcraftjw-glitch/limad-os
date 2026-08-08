#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${1:-/}"
APT_ETC="${ROOT%/}/etc/apt"
[[ "$ROOT" == "/" ]] && APT_ETC="/etc/apt"

mkdir -p "$APT_ETC/sources.list.d"

python3 - "$APT_ETC" <<'PY'
from pathlib import Path
import re
import sys

apt_etc = Path(sys.argv[1])

def is_media_uri(token: str) -> bool:
    t = token.strip().lower()
    return t.startswith('cdrom:') or t.startswith('file:/cdrom') or t.startswith('file:///cdrom')

# Legacy one-line sources: comment out active CD/DVD/live-media entries.
for path in [apt_etc / 'sources.list', *sorted((apt_etc / 'sources.list.d').glob('*.list'))]:
    if not path.exists():
        continue
    out = []
    changed = False
    for line in path.read_text(errors='surrogateescape').splitlines(True):
        stripped = line.lstrip()
        if stripped and not stripped.startswith('#') and re.match(r'^deb(?:-src)?\s', stripped, re.I):
            low = stripped.lower()
            if 'cdrom:' in low or 'file:/cdrom' in low or 'file:///cdrom' in low:
                prefix = line[:len(line)-len(stripped)]
                newline = '\n' if line.endswith('\n') else ''
                body = stripped.rstrip('\n')
                line = f'{prefix}# disabled by LiMaD OS build: {body}{newline}'
                changed = True
        out.append(line)
    if changed:
        path.write_text(''.join(out), errors='surrogateescape')

# deb822 .sources files: remove only live-media URIs. If a stanza contains no
# usable URI afterwards, drop that stanza entirely. Network mirrors are kept.
for path in sorted((apt_etc / 'sources.list.d').glob('*.sources')):
    text = path.read_text(errors='surrogateescape')
    blocks = re.split(r'\n[ \t]*\n', text)
    kept_blocks = []
    changed = False
    for block in blocks:
        if not block.strip():
            continue
        lines = block.splitlines()
        new_lines = []
        saw_uris = False
        kept_uri = False
        drop_block = False
        for line in lines:
            m = re.match(r'^(\s*URIs\s*:\s*)(.*)$', line, re.I)
            if m:
                saw_uris = True
                uris = m.group(2).split()
                filtered = [u for u in uris if not is_media_uri(u)]
                if len(filtered) != len(uris):
                    changed = True
                if filtered:
                    kept_uri = True
                    new_lines.append(m.group(1) + ' '.join(filtered))
                else:
                    drop_block = True
                continue
            new_lines.append(line)
        # A stanza explicitly pointing only at the live ISO must disappear.
        if drop_block and saw_uris and not kept_uri:
            changed = True
            continue
        # Defensive fallback for unusual deb822 media stanzas.
        low = block.lower()
        if ('cdrom:' in low or 'file:/cdrom' in low or 'file:///cdrom' in low) and not kept_uri:
            changed = True
            continue
        kept_blocks.append('\n'.join(new_lines))
    new_text = ('\n\n'.join(kept_blocks) + ('\n' if kept_blocks else ''))
    if changed or new_text != text:
        path.write_text(new_text, errors='surrogateescape')

# Hard safety gate: no active APT source may still reference the live medium.
problems = []
for path in [apt_etc / 'sources.list', *sorted((apt_etc / 'sources.list.d').glob('*.list'))]:
    if not path.exists():
        continue
    for no, line in enumerate(path.read_text(errors='surrogateescape').splitlines(), 1):
        s = line.lstrip()
        if s.startswith('#'):
            continue
        low = s.lower()
        if (low.startswith('deb ') or low.startswith('deb-src ')) and ('cdrom:' in low or 'file:/cdrom' in low or 'file:///cdrom' in low):
            problems.append(f'{path}:{no}:{line}')
for path in sorted((apt_etc / 'sources.list.d').glob('*.sources')):
    for no, line in enumerate(path.read_text(errors='surrogateescape').splitlines(), 1):
        low = line.strip().lower()
        if low.startswith('uris:') and ('cdrom:' in low or 'file:/cdrom' in low or 'file:///cdrom' in low):
            problems.append(f'{path}:{no}:{line}')
if problems:
    raise SystemExit('FATAL: aktive Live-Medium-APT-Quelle blieb erhalten:\n' + '\n'.join(problems))
PY

echo 'APT Live-Medium-Quellen deaktiviert; Netzwerkquellen bleiben aktiv.'

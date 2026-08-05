#!/usr/bin/env bash
# The LiMaD icon theme must contain the complete size ladder for every own
# application - and nothing else.
set -Eeuo pipefail
cd "$(dirname "$0")/.."

python3 - <<'PY'
import json, sys
from pathlib import Path
from configparser import RawConfigParser

root = Path('system_files/usr/share/icons/LiMaD')
manifest = json.loads(Path('system_files/usr/share/limad/limad-icons.manifest.json').read_text())
sizes = [16, 22, 24, 32, 48, 64, 128, 256, 512]

def fail(msg):
    sys.exit(f'ICON AUDIT FAILED: {msg}')

# 1. index.theme is consistent with what is actually on disk.
cfg = RawConfigParser()
cfg.optionxform = str
cfg.read(root / 'index.theme')
if cfg['Icon Theme']['Name'] != 'LiMaD':
    fail('theme name is not LiMaD')
inherits = cfg['Icon Theme']['Inherits'].split(',')
if inherits[0] != 'WhiteSur-dark':
    fail('LiMaD must inherit WhiteSur-dark first')
if 'hicolor' not in inherits:
    fail('hicolor fallback missing from Inherits')

declared = [d.strip() for d in cfg['Icon Theme']['Directories'].split(',')]
on_disk = sorted(
    str(p.relative_to(root)) for p in root.rglob('*') if p.is_dir() and any(p.iterdir())
)
on_disk = [d for d in on_disk if '/' in d]
if sorted(declared) != sorted(on_disk):
    fail(f'Directories mismatch: declared={sorted(declared)} on_disk={on_disk}')
for d in declared:
    if d not in cfg:
        fail(f'directory {d} has no section in index.theme')
    if cfg[d]['Context'] != 'Applications':
        fail(f'{d} is not an Applications context')

# 2. Scope: only application icons, never generic ones.
for p in root.rglob('*'):
    if p.is_dir() and p.name in {'places', 'mimetypes', 'devices', 'status', 'actions',
                                 'categories', 'emblems', 'panel'}:
        fail(f'generic icon directory present: {p} - those belong to WhiteSur')

# 3. Every declared application has the full ladder and correct pixel sizes.
try:
    from PIL import Image
except ImportError:
    Image = None
    print('note: Pillow not installed - pixel dimensions are not verified locally')
for name, spec in manifest['applications'].items():
    if not spec['sizes']:
        svg = root / 'scalable' / 'apps' / f'{name}.svg'
        if not svg.is_file():
            fail(f'{name}: declared scalable-only but SVG missing')
        continue
    for s in sizes:
        icon = root / f'{s}x{s}' / 'apps' / f'{name}.png'
        if not icon.is_file():
            fail(f'{name}: missing {s}px icon')
        if Image is not None:
            w, h = Image.open(icon).size
            if (w, h) != (s, s):
                fail(f'{name}: {s}px icon is {w}x{h}')
        for alias in spec.get('aliases', []):
            a = root / f'{s}x{s}' / 'apps' / f'{alias}.png'
            if not a.is_file():
                fail(f'{alias}: missing {s}px alias icon')
            if a.read_bytes() != icon.read_bytes():
                fail(f'{alias} at {s}px is not byte-identical to {name}')
    if spec['scalable'] and not (root / 'scalable' / 'apps' / f'{name}.svg').is_file():
        fail(f'{name}: declared scalable but SVG missing')

# 4. No stray files that belong to no declared application.
known = set()
for name, spec in manifest['applications'].items():
    known.add(name)
    known.update(spec.get('aliases', []))
for p in root.rglob('*.png'):
    if p.stem not in known:
        fail(f'undeclared icon file: {p}')
for p in root.rglob('*.svg'):
    if p.stem not in known:
        fail(f'undeclared icon file: {p}')

total = sum(1 for p in root.rglob('*') if p.is_file())
print(f'LiMaD own-application icon audit: PASS '
      f'({len(manifest["applications"])} applications, {total} files)')
PY

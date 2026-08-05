#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
from pathlib import Path
import hashlib
import struct

root=Path('.')
canonical=root/'system_files/usr/share/limad-drop/web/assets/icon-512.png'
if not canonical.is_file():
    raise SystemExit('LiDrop exact icon test: canonical app asset missing')
canonical_hash=hashlib.sha256(canonical.read_bytes()).hexdigest()
exact_paths=[
    root/'system_files/usr/share/limad-drop/branding/lidrop-app-icon.png',
    root/'system_files/usr/share/icons/LiMaD/512x512/apps/de.limad.Drop.png',
    root/'system_files/usr/share/icons/LiMaD/512x512/apps/limad-drop.png',
    root/'system_files/usr/share/icons/hicolor/512x512/apps/de.limad.Drop.png',
    root/'system_files/usr/share/icons/hicolor/512x512/apps/limad-drop.png',
]
for path in exact_paths:
    if not path.is_file():
        raise SystemExit(f'LiDrop exact icon test: missing {path}')
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != canonical_hash:
        raise SystemExit(f'LiDrop exact icon test: checksum mismatch {path}')

def png_size(path):
    data=path.read_bytes()[:24]
    if data[:8] != b'\x89PNG\r\n\x1a\n' or data[12:16] != b'IHDR':
        raise SystemExit(f'LiDrop exact icon test: invalid PNG {path}')
    return struct.unpack('>II', data[16:24])

for theme in ('LiMaD','hicolor'):
    base=root/f'system_files/usr/share/icons/{theme}'
    for size_dir in base.iterdir():
        if not size_dir.is_dir() or 'x' not in size_dir.name:
            continue
        try:
            size=int(size_dir.name.split('x')[0])
        except ValueError:
            continue
        for name in ('de.limad.Drop.png','limad-drop.png'):
            path=size_dir/'apps'/name
            if path.is_file() and png_size(path)!=(size,size):
                raise SystemExit(f'LiDrop exact icon test: wrong dimensions {path}: {png_size(path)}')

desktop=(root/'system_files/usr/share/applications/de.limad.Drop.desktop').read_text()
if desktop.count('Icon=de.limad.Drop') != 3:
    raise SystemExit('LiDrop exact icon test: desktop launcher does not consistently use de.limad.Drop')
css=(root/'system_files/usr/share/limad-drop/web/styles.css').read_text()
if 'background:url("/assets/icon-512.png") center/cover no-repeat' not in css:
    raise SystemExit('LiDrop exact icon test: app header does not use canonical icon asset')
print(f'LiDrop app/dock exact icon checksum: PASS ({canonical_hash})')
PY

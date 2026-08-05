#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."

python3 - <<'PY'
from pathlib import Path
import struct
import sys

sf = Path('system_files')
theme = sf / 'usr/share/plymouth/themes/limad'

def fail(message):
    raise SystemExit(f'PLYMOUTH FAILED: {message}')

for name in ['limad.plymouth', 'limad.script', 'boot-splash.png'] + [f'spinner-{i:02d}.png' for i in range(12)]:
    if not (theme / name).is_file():
        fail(f'{name} fehlt')
image = (theme / 'boot-splash.png').read_bytes()
if image[:8] != b'\x89PNG\r\n\x1a\n':
    fail('Bootbild ist keine PNG-Datei')
width, height = struct.unpack('>II', image[16:24])
if (width, height) != (1920, 1080):
    fail(f'Bootbild hat {width}x{height} statt 1920x1080')
for index in range(12):
    frame = (theme / f'spinner-{index:02d}.png').read_bytes()
    if frame[:8] != b'\x89PNG\r\n\x1a\n':
        fail(f'Spinner-Frame {index:02d} ist keine PNG-Datei')
    frame_width, frame_height = struct.unpack('>II', frame[16:24])
    if (frame_width, frame_height) != (96, 96):
        fail(f'Spinner-Frame {index:02d} hat {frame_width}x{frame_height} statt 96x96')
script = (theme / 'limad.script').read_text()
for needle in ['boot-splash.png', 'spinner-00.png', 'spinner-11.png', 'SetRefreshFunction', 'SetDisplayPasswordFunction', 'SetDisplayMessageFunction']:
    if needle not in script:
        fail(f'Plymouth-Skript enthält {needle} nicht')
conf = (sf / 'etc/plymouth/plymouthd.conf').read_text()
if 'Theme=limad' not in conf:
    fail('LiMaD ist nicht als Plymouth-Thema gewählt')
dracut = (sf / 'etc/dracut.conf.d/99-limad-plymouth.conf').read_text()
if 'plymouth' not in dracut or 'boot-splash.png' not in dracut:
    fail('Plymouth-Dateien werden nicht ins Initramfs übernommen')
step = Path('build_files/55-plymouth.sh').read_text()
if 'plymouth-set-default-theme limad' not in step:
    fail('Build-Schritt aktiviert das LiMaD-Thema nicht')
packages = Path('build_files/10-packages.sh').read_text()
for package in ['plymouth', 'plymouth-plugin-script']:
    if package not in packages:
        fail(f'Paket {package} fehlt')
print('LiMaD Plymouth boot splash: PASS')
PY

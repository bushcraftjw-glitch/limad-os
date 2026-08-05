#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY_TEST'
from pathlib import Path
import base64, hashlib, re
root=Path('.')
packages=(root/'build_files/10-packages.sh').read_text()
for name in ('gstreamer1','python3-gstreamer1','gstreamer1-plugin-gtk4','gstreamer1-plugins-base','gstreamer1-plugins-good','gstreamer1-plugins-bad-free','gstreamer1-plugins-ugly-free','gstreamer1-plugin-openh264','gstreamer1-plugin-libav','pipewire-gstreamer'):
    if name not in packages:
        raise SystemExit(f'missing mandatory package: {name}')
if 'FATAL: mandatory GStreamer runtime could not be installed' not in packages:
    raise SystemExit('GStreamer packages can still be silently skipped')
build=(root/'build_files/build.sh').read_text()
if '11-gstreamer-runtime.sh' not in build or build.index('11-gstreamer-runtime.sh') > build.index('20-mactahoe-gtk.sh'):
    raise SystemExit('GStreamer validation is not at the beginning of the build')
validator=(root/'build_files/11-gstreamer-runtime.sh').read_text()
for token in ('gtk4paintablesink','python3-gstreamer1','gstreamer1-plugin-gtk4','Gst.ElementFactory.find'):
    if token not in validator:
        raise SystemExit(f'GStreamer validator missing {token}')
source=(root/'system_files/usr/share/icons/LiMaD/512x512/apps/de.limad.WindowsApps.png').read_bytes()
svgs=[root/'system_files/usr/share/icons/LiMaD/scalable/apps/de.limad.WindowsApps.svg',root/'system_files/usr/share/icons/hicolor/scalable/apps/de.limad.WindowsApps.svg']
if svgs[0].read_bytes()!=svgs[1].read_bytes():
    raise SystemExit('scalable Windows icons differ')
for svg in svgs:
    m=re.search(r'href="data:image/png;base64,([A-Za-z0-9+/=]+)"',svg.read_text())
    if not m or base64.b64decode(m.group(1))!=source:
        raise SystemExit(f'{svg}: embedded artwork differs from approved 512px icon')
for size in (16,22,24,32,48,64,128,256,512):
    a=root/f'system_files/usr/share/icons/LiMaD/{size}x{size}/apps/de.limad.WindowsApps.png'
    b=root/f'system_files/usr/share/icons/LiMaD/{size}x{size}/apps/windows-apps.png'
    if a.read_bytes()!=b.read_bytes():
        raise SystemExit(f'Windows icon aliases differ at {size}px')
print('GStreamer base installation and Windows icon consistency: PASS')
PY_TEST

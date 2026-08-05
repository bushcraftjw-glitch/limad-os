#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."

python3 - <<'PY'
import ast
import json
import re
import stat
import sys
from pathlib import Path


def fail(message):
    raise SystemExit(f'SCREEN SHARE FAILED: {message}')

root = Path('.')
sf = root / 'system_files'
env = dict(re.findall(r'^([A-Z0-9_]+)=\"?([^\"\n]*)\"?$', (root / 'build_files/versions.env').read_text(), re.M))

expected = {
    'LIMAD_BUILD_REVISION': 'gnome-rc2-build5',
    'LIMAD_SCREEN_SHARE_VERSION': '1.0.1',
    'DOUBLETAKE_REPO': 'https://github.com/omarroth/doubletake.git',
    'DOUBLETAKE_TAG': 'v0.4.0',
    'DOUBLETAKE_COMMIT': '364ea84247ce17a084ae15b9011409910e823e34',
}
for key, value in expected.items():
    if env.get(key) != value:
        fail(f'{key} mismatch: {env.get(key)!r}')

required = [
    root / 'build_files/67-screen-share.sh',
    sf / 'usr/local/bin/limad-screen-share',
    sf / 'usr/local/bin/limad-screen-share-firewall',
    sf / 'usr/share/limad-screen-share/app.py',
    sf / 'usr/share/limad-screen-share/VERSION',
    sf / 'usr/share/applications/de.limad.ScreenShare.desktop',
    sf / 'usr/share/polkit-1/rules.d/49-limad-screen-share.rules',
    sf / 'usr/share/icons/LiMaD/scalable/apps/de.limad.ScreenShare.svg',
    sf / 'usr/share/icons/LiMaD/scalable/apps/limad-screen-share.svg',
]
for path in required:
    if not path.is_file() or path.stat().st_size == 0:
        fail(f'missing file: {path}')
for path in required[:3]:
    if not path.stat().st_mode & stat.S_IXUSR:
        fail(f'not executable: {path}')

packages = (root / 'build_files/10-packages.sh').read_text()
for package in (
    'golang', 'gnome-network-displays', 'gstreamer1-plugin-openh264',
    'gstreamer1-plugin-libav', 'pipewire-gstreamer', 'pulseaudio-utils'
):
    if package not in packages:
        fail(f'package not wired: {package}')

build = (root / 'build_files/67-screen-share.sh').read_text()
for needle in (
    'git clone --quiet --depth=1 --branch "$DOUBLETAKE_TAG"',
    'actual_commit="$(git -C "$work/source" rev-parse HEAD)"',
    '[[ "$actual_commit" == "$DOUBLETAKE_COMMIT" ]]',
    'make -C "$work/source" test',
    'bin/doubletake-ctl',
    'COPYING.GPL',
    'security_status=experimental',
    'gst-inspect-1.0',
):
    if needle not in build:
        fail(f'build step missing {needle}')

orchestrator = (root / 'build_files/build.sh').read_text()
positions = [orchestrator.index(name) for name in ('65-airdrop-compat.sh', '67-screen-share.sh', '70-limad-apps.sh')]
if positions != sorted(positions):
    fail('screen-share build step is in the wrong position')

app_path = sf / 'usr/share/limad-screen-share/app.py'
app = app_path.read_text()
ast.parse(app, filename=str(app_path))
for needle in (
    'gnome-network-displays', 'doubletake-ctl', 'AirPlay · Experimentell',
    'Google Cast', 'Miracast', 'Apple TV', '60000-60010',
    'pkexec', 'Audio mit übertragen', 'Übertragung stoppen'
):
    if needle not in app:
        fail(f'GUI missing {needle}')
if 'uxplay' in app.lower():
    fail('UxPlay is a receiver and must not be used as the sender')

firewall = (sf / 'usr/local/bin/limad-screen-share-firewall').read_text()
for needle in ('60000-60010', '--add-port=', '--remove-port=', '--on-active=2h', 'EUID'):
    if needle not in firewall:
        fail(f'firewall helper missing {needle}')
if '--permanent' in firewall:
    fail('AirPlay firewall rules must never be permanent')

polkit = (sf / 'usr/share/polkit-1/rules.d/49-limad-screen-share.rules').read_text()
if '/usr/local/bin/limad-screen-share-firewall' not in polkit or 'subject.local && subject.active' not in polkit:
    fail('Polkit rule is too broad or incomplete')

desktop = (sf / 'usr/share/applications/de.limad.ScreenShare.desktop').read_text()
for needle in (
    'Exec=/usr/local/bin/limad-screen-share', 'Icon=limad-screen-share',
    'Actions=Update;', '--app de.limad.ScreenShare', 'AirPlay;Apple TV;Chromecast'
):
    if needle not in desktop:
        fail(f'desktop entry missing {needle}')

config = json.loads((sf / 'usr/share/limad-updater/apps.json').read_text())
entry = next((item for item in config['apps'] if item['app_id'] == 'de.limad.ScreenShare'), None)
if not entry or entry.get('system_root') != '/usr/share/limad-screen-share' or entry.get('required') != ['app.py', 'VERSION']:
    fail('updater configuration is incomplete')
if '"de.limad.ScreenShare": "LiMaD auf TV übertragen"' not in (root / 'tools/build-limad-update.py').read_text():
    fail('update package builder does not support screen sharing')

manifest = json.loads((sf / 'usr/share/limad/limad-icons.manifest.json').read_text())
spec = manifest['applications'].get('de.limad.ScreenShare')
if spec != {'scalable': True, 'sizes': [], 'aliases': ['limad-screen-share']}:
    fail('icon manifest entry mismatch')

print('LiMaD auf TV übertragen with Google Cast, Miracast and experimental AirPlay: PASS')
PY

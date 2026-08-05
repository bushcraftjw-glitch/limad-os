#!/usr/bin/env bash
# The native LiMaD applications and the Wine based Windows installer must
# be complete, wired up and free of desktop-environment specific dependencies.
set -Eeuo pipefail
cd "$(dirname "$0")/.."

python3 - <<'PY'
import re, subprocess, sys
from pathlib import Path

env = dict(re.findall(r'^([A-Z0-9_]+)="([^"]*)"$', Path('build_files/versions.env').read_text(), re.M))
sf = Path('system_files')

def fail(msg):
    sys.exit(f'APPLICATION AUDIT FAILED: {msg}')

# 1. Payloads and launchers.
apps = {
    'LiMaDCut':       ('usr/local/bin/limad-cut', 'usr/share/limad-cut/native_shell.py',
                       'de.limad.Cut'),
    'LiMaD Study':    ('usr/local/bin/limad-study', 'usr/share/limad-study/src/limad_study/__main__.py',
                       'de.limad.Study'),
    'LiDrop':         ('usr/local/bin/limad-drop', 'usr/share/limad-drop/limad_dropd.py',
                       'de.limad.Drop'),
    'LiLink':         ('usr/local/bin/lilink', 'usr/share/limad-link/daemon.py',
                       'de.limad.Link'),
    'LiNotes':        ('usr/local/bin/limad-notes', 'usr/share/limad-notes/app.py',
                       'de.limad.Notes'),
    'LiSave':         ('usr/local/bin/limad-save', 'usr/share/limad-save/app.py',
                       'de.limad.Save'),
    'Anycubic':       ('usr/bin/anycubicslicernext', None, 'de.limad.AnycubicSlicerNext'),
    'LiMaD Bildschirm': ('usr/local/bin/limad-screen-share', 'usr/share/limad-screen-share/app.py',
                         'de.limad.ScreenShare'),
    'LiMaD Windows':  ('usr/local/bin/limad-windows-setup', 'usr/share/limad-windows/installer.py',
                       'de.limad.WindowsApps'),
}
for name, (launcher, payload, desktop_id) in apps.items():
    if not (sf / launcher).is_file():
        fail(f'{name}: launcher {launcher} missing')
    if payload and not (sf / payload).is_file():
        fail(f'{name}: payload {payload} missing')
    entry = sf / 'usr/share/applications' / f'{desktop_id}.desktop'
    if not entry.is_file():
        fail(f'{name}: desktop entry {desktop_id}.desktop missing')

# 2. Every desktop entry points at something this repository actually ships,
#    and uses an icon the LiMaD icon theme provides.
icons = {p.stem for p in Path('system_files/usr/share/icons/LiMaD').rglob('*') if p.is_file()}
for entry in (sf / 'usr/share/applications').glob('*.desktop'):
    text = entry.read_text()
    exec_line = re.search(r'^Exec=(\S+)', text, re.M)
    icon_line = re.search(r'^Icon=(\S+)', text, re.M)
    if not exec_line or not icon_line:
        fail(f'{entry.name}: Exec or Icon missing')
    target = exec_line.group(1)
    if target.startswith('/') and not (sf / target.lstrip('/')).exists():
        # Anycubic's binary is produced during the build from the vendored DEB.
        if 'anycubic' not in target.lower():
            fail(f'{entry.name}: {target} is not shipped')
    if icon_line.group(1) not in icons:
        fail(f'{entry.name}: icon {icon_line.group(1)} is not in the LiMaD icon theme')

# 3. No KDE/Plasma dependency may have come along with the applications.
bad = subprocess.run(
    ['grep', '-rIl', '-E', '(^|[^[:alnum:]_])(kdialog|kwriteconfig|qdbus|kioclient|plasmashell)([^[:alnum:]_]|$)',
     'system_files'], capture_output=True, text=True).stdout.strip()
if bad:
    fail(f'KDE-specific calls in the application payloads: {bad}')

# 4. Python payloads must compile.
import tempfile, py_compile
with tempfile.TemporaryDirectory() as tmp:
    for i, py in enumerate(sorted(sf.rglob('*.py'))):
        if '__pycache__' in py.parts:
            continue
        try:
            py_compile.compile(str(py), doraise=True, cfile=f'{tmp}/{i}.pyc')
        except py_compile.PyCompileError as exc:
            fail(f'{py}: {exc.msg.splitlines()[0]}')

# 5. Anycubic: pinned version, split parts, checksum list, build step wiring.
vendor = Path('build_files/vendor/anycubic')
parts = sorted(vendor.glob(f'anycubicslicernext_{env["ANYCUBIC_DEB_VERSION"]}_amd64.deb.part[0-9][0-9]'))
if len(parts) != 2:
    fail('Anycubic package parts missing')
sums = (vendor / 'SHA256SUMS').read_text()
for part in parts:
    if part.name not in sums:
        fail(f'{part.name} is not covered by SHA256SUMS')
if env['ANYCUBIC_SOURCE_SHA256'] not in (vendor / 'PACKAGE-SHA256').read_text():
    fail('ANYCUBIC_SOURCE_SHA256 does not match PACKAGE-SHA256')
build = Path('build_files/60-anycubic-slicer.sh').read_text()
for needle in ['sha256sum -c SHA256SUMS', 'ANYCUBIC_SOURCE_SHA256', 'ar x']:
    if needle not in build:
        fail(f'Anycubic build step is missing `{needle}`')

# 6. Wine installer wiring.
wine_step = Path('build_files/80-wine-installer.sh').read_text()
if 'LIMAD_INSTALL_WINE' not in env and 'LIMAD_INSTALL_WINE' not in wine_step:
    fail('Wine feature switch missing')
runner = (sf / 'usr/local/bin/limad-winrun').read_text()
if 'wine-env.sh' not in runner or 'msiexec' not in runner:
    fail('limad-winrun does not handle the Wine environment and MSI files')
mime_entry = (sf / 'usr/share/applications/de.limad.WindowsRun.desktop').read_text()
for mime in ['application/x-ms-dos-executable', 'application/x-msi']:
    if mime not in mime_entry:
        fail(f'{mime} is not routed to the Windows installer')
if 'NoDisplay=true' not in mime_entry:
    fail('the file-type handler must not appear as a separate menu entry')
installer = (sf / 'usr/share/limad-windows/installer.py').read_text()
for needle in ['wineboot', 'write_desktop_entry', 'scan_executables', 'Adw.Application', 'AppData/Local/Programs']:
    if needle not in installer:
        fail(f'Windows installer is missing `{needle}`')

# 7. LiDrop services.
for unit in ['usr/lib/systemd/user/limad-drop.service',
             'usr/lib/systemd/user/limad-airdrop.timer',
             'usr/lib/firewalld/services/limad-drop.xml']:
    if not (sf / unit).is_file():
        fail(f'LiDrop: {unit} missing')


# 8. Graphical per-user updater for all update-capable integrated applications.
updater = sf / 'usr/local/bin/limad-updater'
if not updater.is_file():
    fail('LiMaD updater launcher missing')
updater_config = sf / 'usr/share/limad-updater/apps.json'
if not updater_config.is_file():
    fail('LiMaD updater configuration missing')
import json
supported = {item['app_id'] for item in json.loads(updater_config.read_text())['apps']}
expected_updates = {'de.limad.Cut', 'de.limad.Study', 'de.limad.Drop', 'de.limad.Link', 'de.limad.Notes', 'de.limad.Save', 'de.limad.ScreenShare', 'de.limad.AnycubicSlicerNext', 'de.limad.WindowsApps'}
if supported != expected_updates:
    fail(f'updater app set mismatch: {supported}')
for app_id in expected_updates:
    entry = (sf / 'usr/share/applications' / f'{app_id}.desktop').read_text()
    if 'Actions=Update;' not in entry or f'--app {app_id}' not in entry:
        fail(f'{app_id}: graphical update action missing')

print('LiMaD applications and Windows installer: PASS '
      f'({len(apps)} applications)')
PY

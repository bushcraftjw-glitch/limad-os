#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."

python3 - <<'PY'
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path.cwd()
sf = root / 'system_files'

def fail(message):
    raise SystemExit(f'APP UPDATER FAILED: {message}')

required = [
    sf / 'usr/local/bin/limad-updater',
    sf / 'usr/share/limad-updater/backend.py',
    sf / 'usr/share/limad-updater/updater.py',
    sf / 'usr/share/limad-updater/apps.json',
    sf / 'usr/share/applications/de.limad.Updater.desktop',
    sf / 'usr/share/mime/packages/de.limad.Update.xml',
    root / 'tools/build-limad-update.py',
    root / 'UPDATE-PAKET-SPEZIFIKATION.md',
]
for path in required:
    if not path.is_file():
        fail(f'{path} fehlt')

config = json.loads((sf / 'usr/share/limad-updater/apps.json').read_text())
expected = {
    'de.limad.Cut',
    'de.limad.Study',
    'de.limad.Drop',
    'de.limad.Link',
    'de.limad.Notes',
    'de.limad.Save',
    'de.limad.ScreenShare',
    'de.limad.AnycubicSlicerNext',
    'de.limad.WindowsApps',
}
if {app['app_id'] for app in config['apps']} != expected:
    fail('die neun unterstützten App-IDs stimmen nicht')

for app_id, launcher in {
    'de.limad.Cut': 'usr/local/bin/limad-cut',
    'de.limad.Study': 'usr/local/bin/limad-study',
    'de.limad.Drop': 'usr/local/bin/limad-drop',
    'de.limad.Link': 'usr/local/bin/lilink',
    'de.limad.Notes': 'usr/local/bin/limad-notes',
    'de.limad.Save': 'usr/local/bin/limad-save',
    'de.limad.ScreenShare': 'usr/local/bin/limad-screen-share',
    'de.limad.AnycubicSlicerNext': 'usr/bin/anycubicslicernext',
    'de.limad.WindowsApps': 'usr/local/bin/limad-windows-setup',
}.items():
    text = (sf / launcher).read_text()
    if f'limad-updater/apps/{app_id}/current/payload' not in text:
        fail(f'{launcher} verwendet Benutzer-Updates nicht')
    desktop = (sf / f'usr/share/applications/{app_id}.desktop').read_text()
    if 'Actions=Update;' not in desktop or f'--app {app_id}' not in desktop:
        fail(f'{app_id}.desktop hat keine Update-Aktion')

mime = (sf / 'usr/share/mime/packages/de.limad.Update.xml').read_text()
if '*.limad-update.zip' not in mime:
    fail('Dateiendung .limad-update.zip ist nicht registriert')

with tempfile.TemporaryDirectory() as td:
    temp = Path(td)
    payload = temp / 'payload'
    payload.mkdir()
    (payload / 'native_shell.py').write_text('print("update works")\n')
    system_version = temp / 'SYSTEM_VERSION'
    system_version.write_text('1.0.0\n')
    fake_config = temp / 'apps.json'
    fake_config.write_text(json.dumps({
        'format_version': 1,
        'apps': [{
            'app_id': 'de.limad.Cut',
            'name': 'LiMaDCut',
            'system_root': '/usr/share/limad-cut',
            'system_version_file': str(system_version),
            'required': ['native_shell.py'],
            'restart_user_services': [],
        }],
    }))
    package = temp / 'LiMaDCut-1.1.0.limad-update.zip'
    subprocess.run([
        sys.executable, str(root / 'tools/build-limad-update.py'),
        '--app-id', 'de.limad.Cut', '--version', '1.1.0',
        '--payload', str(payload), '--output', str(package),
    ], check=True, stdout=subprocess.DEVNULL)
    os.environ['XDG_DATA_HOME'] = str(temp / 'data')
    os.environ['LIMAD_UPDATER_CONFIG'] = str(fake_config)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(sf / 'usr/share/limad-updater'))
    import backend
    installed = backend.install_package(package, 'de.limad.Cut')
    if installed['active_version'] != '1.1.0' or installed['source'] != 'Benutzer-Update':
        fail('Test-Update wurde nicht aktiviert')
    active = backend.active_root('de.limad.Cut')
    if not active or (active / 'native_shell.py').read_text() != 'print("update works")\n':
        fail('aktiver Payload ist nicht erreichbar')
    restored = backend.restore_system('de.limad.Cut')
    if restored['active_version'] != '1.0.0' or restored['can_restore']:
        fail('Rückkehr zur Systemversion funktioniert nicht')

print('Grafischer LiMaD-App-Updater und Paketformat: PASS')
PY

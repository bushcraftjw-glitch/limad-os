#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
from pathlib import Path
import gettext, sys
sf=Path('system_files')
def fail(m): sys.exit('DESKTOP POLISH FAILED: '+m)
first=sf/'usr/local/bin/limad-first-login-setup'
for p in [first,sf/'etc/xdg/autostart/limad-first-login.desktop',sf/'usr/share/icons/LiMaD/64x64/apps/limad-start.png',sf/'usr/share/gnome-shell/extensions/logomenu@aryan_k/locale/de/LC_MESSAGES/logo-menu.mo']:
    if not p.is_file(): fail(f'{p} missing')
mo=sf/'usr/share/gnome-shell/extensions/logomenu@aryan_k/locale/de/LC_MESSAGES/logo-menu.mo'
with mo.open('rb') as handle:
    catalogue=gettext.GNUTranslations(handle)
if catalogue.gettext('App Grid') != 'Anwendungen': fail('German logo-menu catalogue is invalid')
text=first.read_text()
for needle in ['close,maximize,minimize:','dock-fixed true','autohide false','custom-icon-path','64x64/apps/limad-start.png','menu-button-icon-image 0','limad-start.png','logomenu@aryan_k','LiMaD-Wallpaper-02-Logo-Zentriert-4K.png']:
    if needle not in text: fail('first-login setup missing '+needle)
for size in [16,22,24,32,48,64,128,256,512]:
    for name in ['de.limad.StartButton.png','limad-start.png']:
        if not (sf/f'usr/share/icons/LiMaD/{size}x{size}/apps/{name}').is_file(): fail(f'{size}px {name} missing')
print('Desktop first-login, dock and original LiMaD L: PASS')
PY

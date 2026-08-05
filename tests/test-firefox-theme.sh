#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
from pathlib import Path
import py_compile,tempfile,sys
sf=Path('system_files')
def fail(m): sys.exit('FIREFOX THEME FAILED: '+m)
for rel in ['usr/share/limad/firefox/chrome/userChrome.css','usr/share/limad/firefox/chrome/userContent.css','usr/local/bin/limad-firefox-theme-setup','etc/xdg/autostart/limad-firefox-theme.desktop']:
    if not (sf/rel).is_file(): fail(rel+' missing')
setup=(sf/'usr/local/bin/limad-firefox-theme-setup').read_text()
for needle in ['.mozilla/firefox','.var/app/org.mozilla.firefox','toolkit.legacyUserProfileCustomizations.stylesheets','userChrome.css']:
    if needle not in setup: fail('setup missing '+needle)
css=(sf/'usr/share/limad/firefox/chrome/userChrome.css').read_text()
for needle in ['#navigator-toolbox','#17111f','#a978ff','.tabbrowser-tab']:
    if needle not in css: fail('CSS missing '+needle)
with tempfile.TemporaryDirectory() as d: py_compile.compile(str(sf/'usr/local/bin/limad-firefox-theme-setup'),cfile=d+'/x.pyc',doraise=True)
print('Firefox native + Flatpak LiMaD theme: PASS')
PY

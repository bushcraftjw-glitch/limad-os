#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
from pathlib import Path
import sys
sf=Path('system_files')
def fail(m): sys.exit('WINE INTEGRATION FAILED: '+m)
build=Path('build_files/80-wine-installer.sh').read_text()
for pkg in ['wine-mono','mingw32-wine-gecko','mingw64-wine-gecko','wine-pulseaudio','wine-winefonts','xorg-x11-server-Xvfb']:
    if pkg not in build: fail('required package missing: '+pkg)
for needle in ['xvfb-run -a wineboot --init','WINEARCH=wow64','echo LIMAD_WINE_OK','wine-smoke-test.txt']:
    if needle not in build: fail('build smoke missing: '+needle)
env=(sf/'usr/share/limad-windows/wine-env.sh').read_text()
if 'WINEDLLOVERRIDES' in env: fail('Wine Mono/Gecko are still disabled')
if 'DISPLAY="${DISPLAY:-:0}"' in env: fail('DISPLAY is still forced')
installer=(sf/'usr/share/limad-windows/installer.py').read_text()
for needle in ['AppData/Local/Programs','Wine-Code','echo LIMAD_WINE_OK','portable application']:
    if needle not in installer: fail('installer missing: '+needle)
if 'WINEDLLOVERRIDES' in installer: fail('installer still disables Mono/Gecko')

if 'env["WINEARCH"] = get_prefix_architecture(prefix)' not in installer: fail('installer does not select the per-environment Wine architecture')
if 'drive_c/windows/system32' not in installer or 'user.reg' not in installer: fail('installer does not validate initialized prefix')
recipe=(sf/'usr/share/limad-windows/recipe_engine.py').read_text()
if '"standard": ("win10", ("vcrun2022",), ())' not in recipe: fail('standard profile changed unexpectedly')
if '"nws": ("win10", ("dotnet48", "d3dx9", "d3dcompiler_47", "corefonts"), ())' not in recipe: fail('NWS compatibility profile is incomplete')
if not (sf/'usr/local/bin/limad-wine-diagnose').is_file(): fail('diagnose helper missing')
print('Wine packages, prefix smoke and installer detection: PASS')
PY

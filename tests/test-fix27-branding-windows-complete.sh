#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."

python3 - <<'PY'
from pathlib import Path
import hashlib
import re
import struct
import sys


def fail(message):
    raise SystemExit('FIX27 INTEGRATION FAILED: ' + message)

root = Path('.')
sf = root / 'system_files'
versions = (root / 'build_files/versions.env').read_text()
if 'LIMAD_BUILD_REVISION="gnome-rc2-build5"' not in versions and not any(f'LIMAD_BUILD_REVISION="gnome42-phase4-fix{n}"' in versions for n in (32, 35, 36, 37, 38, 39, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50)):
    fail('wrong build revision')
if 'LIMAD_IMAGE_NAME="limad-os-gnome-280"' not in versions:
    fail('known public GHCR package name was changed')

# Confirm the full user-approved boot screen is unchanged and the spinner is separate.
theme = sf / 'usr/share/plymouth/themes/limad'
boot = theme / 'boot-splash.png'
if hashlib.sha256(boot.read_bytes()).hexdigest() != 'cdd81f11c806d5cee160994eaca89d26f3ee1d3adbadc7e7ae3a22dde5ddf3b6':
    fail('approved LiMaD boot screen changed')
script = (theme / 'limad.script').read_text()
for index in range(12):
    frame = theme / f'spinner-{index:02d}.png'
    if not frame.is_file():
        fail(f'spinner frame missing: {frame.name}')
for needle in ['spinner_sprite', 'Plymouth.SetRefreshFunction(refresh_callback)', 'boot-splash.png']:
    if needle not in script:
        fail(f'Plymouth integration missing {needle}')

# System/About logo and fine menu L must be transparent RGBA PNGs.
def png_info(path: Path):
    data = path.read_bytes()
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        fail(f'{path} is not PNG')
    width, height = struct.unpack('>II', data[16:24])
    color_type = data[25]
    return width, height, color_type

system_logo = sf / 'usr/share/icons/LiMaD/512x512/apps/de.limad.Logo.png'
if png_info(system_logo) != (512, 512, 6):
    fail('system information logo is not a 512px transparent RGBA PNG')
for size in [16, 22, 24, 32, 48, 64, 128, 256, 512]:
    icon = sf / f'usr/share/icons/LiMaD/{size}x{size}/apps/limad-start.png'
    if png_info(icon) != (size, size, 6):
        fail(f'menu L is not a transparent {size}px RGBA PNG')

brand = (root / 'build_files/52-branding.sh').read_text()
for needle in [
    "'NAME': '\"LiMaD OS\"'",
    "'PRETTY_NAME': f'\"LiMaD OS {version}\"'",
    "'LOGO': 'de.limad.Logo'",
    'for branding_id in limad bazzite fedora',
    '/usr/share/cockpit/static/branding.css',
]:
    if needle not in brand:
        fail(f'system branding missing {needle}')
iso = (root / 'tools/brand-installer-iso.sh').read_text()
for needle in ['Product=LiMaD OS', 'for id in limad bazzite fedora', 'sidebar-logo.png']:
    if needle not in iso:
        fail(f'installer branding missing {needle}')

# Logo Menu custom path is patched into the actual pinned schema and installed globally.
logo_step = (root / 'build_files/45-logomenu-extension.sh').read_text()
for needle in ['patch-logomenu-schema.py', '/usr/share/glib-2.0/schemas/95-limad-logomenu-']:
    if needle not in logo_step:
        fail(f'Logo Menu hardening missing {needle}')

# Exact FIX22 window design and requested dock applications.
override = (sf / 'usr/share/glib-2.0/schemas/zzzzzzzzzz-limad-defaults.gschema.override').read_text()
if "button-layout='close,maximize,minimize:'" not in override:
    fail('FIX22 left-side window buttons changed')
favorites = re.search(r"^favorite-apps=(.*)$", override, re.M)
if not favorites:
    fail('favorite-apps default missing')
for desktop in [
    'de.limad.Cut.desktop',
    'de.limad.Drop.desktop',
    'de.limad.WindowsApps.desktop',
    'de.limad.AnycubicSlicerNext.desktop',
]:
    if desktop not in favorites.group(1):
        fail(f'requested dock favorite missing: {desktop}')

# Auto installer, recipes and required runtime tools.
recipe = sf / 'usr/share/limad-windows/recipe_engine.py'
installer = sf / 'usr/share/limad-windows/installer.py'
for path in [recipe, installer]:
    compile(path.read_text(), str(path), 'exec')
recipe_text = recipe.read_text()
installer_text = installer.read_text()
for needle in ['"nws"', '"office"', '"cad"', '"creative"', '"gaming"', '"legacy"', '"dotnet48"']:
    if needle not in recipe_text:
        fail(f'Windows recipe engine missing {needle}')
for needle in ['def apply_plan', 'Installationsplan prüfen', 'winetricks', 'wait_for_installer_processes']:
    if needle not in installer_text:
        fail(f'Windows auto installer missing {needle}')
packages = (root / 'build_files/80-wine-installer.sh').read_text()
for package in ['winetricks', 'cabextract', 'samba-winbind-clients', 'icoutils', 'xorg-x11-server-Xvfb']:
    if package not in packages:
        fail(f'Windows runtime dependency missing: {package}')

print('FIX27 requested branding, FIX22 design and Windows Auto-Installer: PASS')
PY

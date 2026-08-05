#!/usr/bin/env bash
# The shipped GNOME defaults must reference exactly the themes and extensions
# the build actually produces or installs.
set -Eeuo pipefail
cd "$(dirname "$0")/.."

python3 - <<'PY'
import re, sys
from pathlib import Path

override_path = Path('system_files/usr/share/glib-2.0/schemas/zzzzzzzzzz-limad-defaults.gschema.override')
override = override_path.read_text()

# GLib key files accept only '#' as a comment marker. A single '//' line makes
# glib-compile-schemas discard the entire file - silently, apart from one
# warning - so every default would be lost.
import configparser
for number, line in enumerate(override.splitlines(), 1):
    stripped = line.strip()
    if not stripped or stripped.startswith('#') or stripped.startswith('['):
        continue
    if '=' not in stripped:
        raise SystemExit(
            f'GNOME DEFAULTS FAILED: {override_path}:{number} is neither a group, '
            f"a '#' comment nor a key=value pair: {stripped!r}")
parser = configparser.RawConfigParser(strict=True, comment_prefixes=('#',))
parser.optionxform = str
try:
    parser.read_string(override)
except configparser.Error as exc:
    raise SystemExit(f'GNOME DEFAULTS FAILED: override is not a valid key file: {exc}')
env = dict(re.findall(r'^([A-Z0-9_]+)="([^"]*)"$', Path('build_files/versions.env').read_text(), re.M))
packages = Path('build_files/10-packages.sh').read_text()
defaults = Path('build_files/50-gnome-defaults.sh').read_text()

def fail(msg):
    sys.exit(f'GNOME DEFAULTS FAILED: {msg}')

def value(group, key):
    m = re.search(rf'^\[{re.escape(group)}\]$(.*?)(?=^\[|\Z)', override, re.M | re.S)
    if not m:
        fail(f'group [{group}] missing')
    m2 = re.search(rf'^{re.escape(key)}=(.*)$', m.group(1), re.M)
    if not m2:
        fail(f'{group}/{key} missing')
    return m2.group(1).strip()

# 1. Themes referenced must be the ones the build creates.
if value('org.gnome.desktop.interface', 'gtk-theme') != f"'{env['LIMAD_GTK_THEME_VARIANT']}'":
    fail('gtk-theme does not match LIMAD_GTK_THEME_VARIANT')
if value('org.gnome.desktop.interface', 'icon-theme') != f"'{env['LIMAD_ICON_THEME_NAME']}'":
    fail('icon-theme does not match LIMAD_ICON_THEME_NAME')
if value('org.gnome.shell.extensions.user-theme', 'name') != f"'{env['LIMAD_SHELL_THEME_VARIANT']}'":
    fail('shell theme does not match LIMAD_SHELL_THEME_VARIANT')
if value('org.gnome.desktop.interface', 'color-scheme') != "'prefer-dark'":
    fail('LiMaD is a dark desktop; color-scheme must be prefer-dark')

# 2. macOS-like window buttons on the left, no appmenu on the right.
buttons = value('org.gnome.desktop.wm.preferences', 'button-layout')
if buttons != "'close,maximize,minimize:'":
    fail(f'window buttons are not macOS-like: {buttons}')

# 3. Every enabled extension must actually be installed by the package step
#    (or, for logomenu, by the dedicated GitHub-release build step: Fedora
#    44 stable does not build gnome-shell-extension-logo-menu, only Rawhide,
#    see build_files/45-logomenu-extension.sh).
ext_uuid_to_pkg = {
    'user-theme@gnome-shell-extensions.gcampax.github.com': 'gnome-shell-extension-user-theme',
    'dash-to-dock@micxgx.gmail.com': 'gnome-shell-extension-dash-to-dock',
    'blur-my-shell@aunetx': 'gnome-shell-extension-blur-my-shell',
    'logomenu@aryan_k': None,
    'lidrop@limad.local': None,
    'lilink@limad.local': None,
}
enabled = re.findall(r"'([^']+)'", value('org.gnome.shell', 'enabled-extensions'))
if not enabled:
    fail('no extensions enabled')
for uuid in enabled:
    if uuid not in ext_uuid_to_pkg:
        fail(f'extension {uuid} is enabled but unknown to this test')
    pkg = ext_uuid_to_pkg[uuid]
    if pkg is not None and pkg not in packages:
        fail(f'extension {uuid} is enabled but {pkg} is never installed')

if 'lidrop@limad.local' in enabled:
    extension = Path('system_files/usr/share/gnome-shell/extensions/lidrop@limad.local')
    for required in ['metadata.json', 'extension.js', 'icons/lidrop-symbolic.svg']:
        if not (extension / required).is_file():
            fail(f'LiDrop status extension missing {required}')

if 'lilink@limad.local' in enabled:
    extension = Path('system_files/usr/share/gnome-shell/extensions/lilink@limad.local')
    for required in ['metadata.json', 'extension.js', 'icons/lilink-symbolic.svg']:
        if not (extension / required).is_file():
            fail(f'LiLink status extension missing {required}')

if 'logomenu@aryan_k' in enabled:
    logomenu_step = Path('build_files/45-logomenu-extension.sh')
    if not logomenu_step.is_file():
        fail('logomenu@aryan_k is enabled but build_files/45-logomenu-extension.sh is missing')
    logomenu_text = logomenu_step.read_text()
    for needle in ['logomenu@aryan_k', 'metadata.json', 'FATAL']:
        if needle not in logomenu_text:
            fail(f'logomenu install step looks incomplete: missing {needle}')
    if '45-logomenu-extension.sh' not in Path('build_files/build.sh').read_text():
        fail('45-logomenu-extension.sh exists but is not called from build.sh')
    if 'gnome-shell-extension-logo-menu' in packages:
        fail('gnome-shell-extension-logo-menu should not be dnf-installed anymore, it is not built for Fedora 44 stable')

# 4. Real first-login defaults: fixed dock and the original LiMaD L launcher.
for key, expected in [('dock-fixed', 'true'), ('autohide', 'false'), ('intellihide', 'false')]:
    if value('org.gnome.shell.extensions.dash-to-dock', key) != expected:
        fail(f'dock {key} must be {expected}')
# Logo Menu keys are intentionally not put in the GLib override because
# upstream changes their names between releases. The dconf layer, dynamic
# first-login migration and asset replacement provide the robust route.
if '[org.gnome.shell.extensions.logo-menu]' in override:
    fail('version-sensitive Logo Menu keys must not be in the GLib override')
first_login = Path('system_files/usr/local/bin/limad-first-login-setup').read_text()
for needle in ['custom-icon-path', 'menu-button-icon-image 0', 'use-custom-icon true', 'custom-icon true']:
    if needle not in first_login:
        fail(f'first-login Logo Menu migration missing {needle}')
for needle in ['/etc/dconf/db/local.d/zzzzzzzzzz-limad-branding', 'UPSTREAM_LOGOS', 'limad-start.png']:
    if needle not in defaults:
        fail(f'robust Logo Menu default missing {needle}')

# 5. Native LiMaD favourites must have a desktop launcher whose declared icon
#    exists in the LiMaD icon overlay. The desktop ID and icon name need not be
#    identical (for example de.limad.Updater intentionally uses limad-store).
manifest_icons = {p.stem for p in Path('system_files/usr/share/icons/LiMaD').rglob('*') if p.is_file()}
for fav in re.findall(r"'([^']+)\.desktop'", value('org.gnome.shell', 'favorite-apps')):
    if not fav.startswith('de.limad.'):
        continue
    desktop = Path('system_files/usr/share/applications') / f'{fav}.desktop'
    if not desktop.is_file():
        fail(f'favourite {fav} has no desktop entry')
    match = re.search(r'^Icon=(.+)$', desktop.read_text(), re.M)
    if not match:
        fail(f'favourite {fav} desktop entry has no Icon key')
    icon = match.group(1).strip()
    if icon not in manifest_icons:
        fail(f'favourite {fav} declares missing LiMaD icon {icon}')

# 6. The wallpaper override is generated at build time, never shipped stale.
if Path('system_files/usr/share/glib-2.0/schemas/zzzzzzzzzz-limad-wallpaper.gschema.override').exists():
    fail('wallpaper override must be generated during the build, not shipped')
if 'glib-compile-schemas' not in defaults:
    fail('schemas are never compiled')
if 'cursor-theme' in override and 'WhiteSur-cursors' in override and 'Adwaita' not in defaults:
    fail('cursor fallback is not handled in the build step')

# 7. Wallpapers: every file listed in the Settings registry must be shipped,
#    and the configured default must be one of them.
import xml.etree.ElementTree as ET
reg = Path('system_files/usr/share/gnome-background-properties/limad-wallpapers.xml')
if not reg.is_file():
    fail('wallpaper registry for Settings missing')
listed = [e.text for e in ET.parse(reg).getroot().iter('filename')]
if not listed:
    fail('wallpaper registry lists nothing')
for path in listed:
    if not Path('system_files' + path).is_file():
        fail(f'wallpaper listed but not shipped: {path}')
default = env.get('LIMAD_DEFAULT_WALLPAPER', '')
if not default:
    fail('LIMAD_DEFAULT_WALLPAPER is not set')
if not any(p.endswith('/' + default) for p in listed):
    fail(f'default wallpaper {default} is not one of the registered ones')

print(f'GNOME default settings and {len(listed)} wallpapers: PASS')
PY

#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY5'
from pathlib import Path
import re,sys

def fail(x): raise SystemExit('PHASE 1 BRANDING FAILED: '+x)
env=Path('build_files/versions.env').read_text()
m=re.search(r'LIMAD_OS_VERSION="([0-9]+\.[0-9]+\.[0-9]+)(?:-[^"]+)?"', env)
if not m or tuple(map(int,m.group(1).split('.'))) < (2,6,0): fail('version below 2.6.0')
build=Path('build_files/build.sh').read_text()
for step in ['50-gnome-defaults.sh','52-branding.sh','55-plymouth.sh']:
    if step not in build: fail(step+' not wired')
if build.index('50-gnome-defaults.sh') > build.index('52-branding.sh') or build.index('52-branding.sh') > build.index('55-plymouth.sh'): fail('branding order wrong')
brand=Path('build_files/52-branding.sh').read_text()
for n in ['NAME', 'PRETTY_NAME', 'BOOTLOADER_NAME', 'de.limad.Logo', 'branding.css']:
    if n not in brand: fail('core identity missing '+n)
ply=Path('build_files/55-plymouth.sh').read_text()
for n in ['default.plymouth','plymouth-set-default-theme limad','readlink -f']:
    if n not in ply: fail('Plymouth hardening missing '+n)
defaults=Path('build_files/50-gnome-defaults.sh').read_text()
for n in ['/etc/dconf/db/local.d/zzzzzzzzzz-limad-branding','picture-uri-dark','UPSTREAM_LOGOS','limad-logo.png']:
    if n not in defaults: fail('desktop branding missing '+n)
first=Path('system_files/usr/local/bin/limad-first-login-setup').read_text()
for n in ['VERSION="2.8.0-rc2-build5"','custom-icon true','use-custom-icon true','LiMaD-Wallpaper-02-Logo-Zentriert-4K.png']:
    if n not in first: fail('first login missing '+n)
iso=Path('tools/brand-installer-iso.sh').read_text()
for n in ['product.img','.buildstamp','IsFinal=True','for id in limad bazzite fedora','boot_image any replay','limad_iso_volume_id','rewrite-boot-config.py','update-treeinfo-checksums.py','implantisomd5']:
    if n not in iso: fail('ISO branding missing '+n)
verify=Path('tools/verify-branded-iso.sh').read_text()
audit=Path('tools/audit-boot-config.py').read_text()
for n in ['Product=LiMaD OS','IsFinal=True','volume id','boot config','checkisomd5','treeinfo']:
    if n not in verify: fail('ISO verification missing '+n)
for n in ['upstream brand remains','label reference','GRUB search label']:
    if n not in audit: fail('boot configuration audit missing '+n)
workflow=Path('.github/workflows/build.yml').read_text()
for n in ['xorriso','brand-installer-iso.sh','verify-branded-iso.sh','BRANDED_ISO']:
    if n not in workflow: fail('workflow missing '+n)
print('Phase 1 boot, wallpaper, menu and installer branding: PASS')
PY5

#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
fail() { echo "FATAL: $*" >&2; exit 1; }

echo '[1/16] Shell/Python syntax'
while IFS= read -r -d '' f; do bash -n "$f" || fail "Shell syntax: $f"; done < <(find build_files tools -type f -name '*.sh' -print0)
bash -n START-GITHUB-BUILD-LINUX.sh
bash -n START-GITHUB-BUILD-MAC.command
python3 - <<'PYSYNTAX'
from pathlib import Path
files=[Path('tools/build-limad-update.py'), *Path('build_files').glob('*.py')]
for p in files:
    compile(p.read_text(encoding='utf-8'), str(p), 'exec')
PYSYNTAX

echo '[2/16] Ubuntu 26.04 source lock'
grep -q 'UBUNTU_VERSION="26.04"' build_files/versions.env || fail 'Ubuntu version lock missing'
grep -q 'UBUNTU_CODENAME="resolute"' build_files/versions.env || fail 'Ubuntu codename lock missing'
grep -q '487f87faaf547ea30e0aba4d5b53346292571256b25333a978db1692bcee9dd2' build_files/versions.env || fail 'Ubuntu ISO SHA256 missing'
grep -q 'casper/minimal.standard.squashfs' build_files/versions.env || fail 'Ubuntu standard squashfs layer missing'
grep -q "'/casper/minimal.squashfs'" build_files/build-iso.sh || fail 'Ubuntu minimal base layer wiring missing'
grep -q 'lowerdir=\$BASE_ROOT,upperdir=\$STANDARD_UPPER' build_files/build-iso.sh || fail 'Ubuntu layered overlay wiring missing'

echo '[3/16] APT live-media source safety'
[[ -x build_files/10-apt-live-media-sources.sh ]] || fail 'APT live-media sanitizer missing'
python3 - <<'PYTEST'
from pathlib import Path
import subprocess, tempfile
with tempfile.TemporaryDirectory() as td:
    root=Path(td)
    (root/'etc/apt/sources.list.d').mkdir(parents=True)
    (root/'etc/apt/sources.list').write_text('deb cdrom:[Ubuntu]/ resolute main restricted\ndeb http://archive.ubuntu.com/ubuntu resolute main\n')
    (root/'etc/apt/sources.list.d/ubuntu.sources').write_text('Types: deb\nURIs: file:/cdrom\nSuites: resolute\nComponents: main restricted\n\nTypes: deb\nURIs: http://archive.ubuntu.com/ubuntu\nSuites: resolute resolute-updates\nComponents: main restricted universe multiverse\n')
    subprocess.run(['bash','build_files/10-apt-live-media-sources.sh',str(root)], check=True, stdout=subprocess.DEVNULL)
    merged='\n'.join(p.read_text() for p in [root/'etc/apt/sources.list', root/'etc/apt/sources.list.d/ubuntu.sources'])
    active='\n'.join(line for line in merged.splitlines() if not line.lstrip().startswith('#'))
    if 'file:/cdrom' in active.lower() or 'cdrom:' in active.lower():
        raise SystemExit('live-media source survived sanitizer')
    if 'archive.ubuntu.com' not in active:
        raise SystemExit('network source was accidentally removed')
PYTEST
grep -n '10-apt-live-media-sources.sh' build_files/customize-rootfs.sh | head -1 >/dev/null || fail 'APT sanitizer not wired into rootfs customization'
SAN_LINE=$(grep -n '10-apt-live-media-sources.sh' build_files/customize-rootfs.sh | head -1 | cut -d: -f1)
APT_LINE=$(grep -n '^apt-get update$' build_files/customize-rootfs.sh | head -1 | cut -d: -f1)
[[ "$SAN_LINE" -lt "$APT_LINE" ]] || fail 'APT sanitizer must run before apt-get update'

echo '[4/16] Theme/Plymouth byte lock'
sha256sum -c tests/theme-lock.sha256 >/dev/null
echo 'cdd81f11c806d5cee160994eaca89d26f3ee1d3adbadc7e7ae3a22dde5ddf3b6  system_files/usr/share/plymouth/themes/limad/boot-splash.png' | sha256sum -c - >/dev/null

echo '[5/16] No legacy immutable runtime path'
if grep -RInE 'rpm-ostree|bootc|dnf5?|/ctx/build_files|BASE_IMAGE_REF' \
  system_files/usr/local/bin system_files/usr/share/limad-save build_files \
  --include='*.sh' --include='*.py' 2>/dev/null | grep -Ev '^[^:]+:[0-9]+:[[:space:]]*#' ; then
  fail 'Bazzite/Fedora runtime command survived the Ubuntu port'
fi

echo '[6/16] Installer contrast safety'
find system_files -type f -iname '*anaconda*.css' -print -quit | grep -q . && fail 'Legacy Anaconda CSS is present'
grep -q 'Do not apply a global text color' build_files/72-installer-safety.sh || fail 'Installer contrast policy missing'

echo '[7/16] Independent updater coverage'
python3 - <<'PY'
import json
from pathlib import Path
apps=json.loads(Path('system_files/usr/share/limad-updater/apps.json').read_text())['apps']
ids={a['app_id'] for a in apps}
required={
'de.limad.Cut','de.limad.Study','de.limad.Drop','de.limad.Link','de.limad.Notes','de.limad.Save',
'de.limad.ScreenShare','de.limad.Mail','de.limad.Klang','de.limad.AnycubicSlicerNext','de.limad.WindowsApps'}
missing=required-ids
if missing: raise SystemExit('Updater IDs missing: '+', '.join(sorted(missing)))
print(f'Updater apps: {len(apps)}')
PY
grep -q 'de.limad.Mail' tools/build-limad-update.py || fail 'Mail update packaging missing'
grep -q 'de.limad.Klang' tools/build-limad-update.py || fail 'Klang update packaging missing'
grep -qx '0.12.0-preview8' system_files/usr/share/limad-drop/VERSION || fail 'LiDrop preview8 payload missing'
grep -q 'LIDROP_VERSION="0.12.0-preview8"' build_files/versions.env || fail 'LiDrop preview8 version lock missing'
[[ -s updates/LiDrop-0.12.0-preview8.limad-update.zip ]] || fail 'Standalone LiDrop preview8 update package missing'
grep -qx '1.0.0-preview3' system_files/usr/share/limad-save/VERSION || fail 'LiSave preview3 payload missing'
grep -q 'LISAVE_VERSION="1.0.0-preview3"' build_files/versions.env || fail 'LiSave preview3 version lock missing'
[[ -s updates/LiSave-1.0.0-preview3.limad-update.zip ]] || fail 'Standalone LiSave preview3 update package missing'

echo '[8/16] Gaming/Deskflow stack'
for pkg in steam-installer steam-devices lutris gamemode gamescope libvulkan1:i386 mesa-vulkan-drivers:i386; do grep -Fxq "$pkg" build_files/packages-required.txt || fail "Gaming package missing: $pkg"; done
grep -q 'org.deskflow.deskflow' system_files/usr/local/bin/limad-install-default-flatpaks || fail 'Deskflow provisioning missing'
grep -q 'net.davidotek.pupgui2' system_files/usr/local/bin/limad-install-default-flatpaks || fail 'ProtonUp-Qt provisioning missing'

echo '[9/16] Mail/Klang user-update launchers'
grep -q 'de.limad.Mail/current/payload' system_files/usr/local/bin/limad-mail || fail 'Mail user update root missing'
grep -q 'de.limad.Klang/current/payload' system_files/usr/local/bin/limad-klang || fail 'Klang user update root missing'
[[ -s system_files/usr/share/limad-klang/VERSION ]] || fail 'Klang packaging VERSION missing'

echo '[10/16] Update ZIP builder smoke test'
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/payload"; printf 'ok\n' > "$TMP/payload/test.txt"
python3 tools/build-limad-update.py --app-id de.limad.Mail --version 1.8 --payload "$TMP/payload" --output "$TMP/Mail-1.8.limad-update.zip" >/dev/null
python3 - "$TMP/Mail-1.8.limad-update.zip" <<'PY'
import json,sys,zipfile
with zipfile.ZipFile(sys.argv[1]) as z:
    m=json.loads(z.read('limad-update.json'))
    assert m['app_id']=='de.limad.Mail'
    assert 'payload/test.txt' in z.namelist()
PY

echo '[11/16] Ubuntu 26.04 required-package compatibility guards'
grep -Fxq 'gnome-shell-ubuntu-extensions' build_files/packages-required.txt || fail 'Ubuntu 26.04 dock provider missing'
if grep -Fxq 'gnome-shell-extension-dash-to-dock' build_files/packages-required.txt; then fail 'Removed dash-to-dock package name survived'; fi
grep -q 'ubuntu-dock@ubuntu.com' system_files/usr/share/glib-2.0/schemas/zzzzzzzzzz-limad-defaults.gschema.override || fail 'Ubuntu Dock UUID missing from GNOME defaults'
if grep -q 'dash-to-dock@micxgx.gmail.com' system_files/usr/share/glib-2.0/schemas/zzzzzzzzzz-limad-defaults.gschema.override; then fail 'Upstream Dash-to-Dock UUID survived Ubuntu 26.04 port'; fi
[[ -x build_files/11-apt-required-preflight.sh ]] || fail 'APT required-package preflight missing'
grep -q '11-apt-required-preflight.sh' build_files/customize-rootfs.sh || fail 'APT required-package preflight not wired'

echo '[12/16] GDM usr-merge/display-manager safety'
grep -q 'GDM_UNIT="$(readlink -f "$candidate")"' build_files/20-mactahoe-gtk.sh || fail 'GDM service path is not canonicalized for usr-merge'
grep -q 'display manager link was not set to canonical GDM service' build_files/20-mactahoe-gtk.sh || fail 'Canonical GDM display-manager verification missing'
if grep -q '\[\[ "\$ACTIVE_DM" == "\$GDM_UNIT" \]\]' build_files/20-mactahoe-gtk.sh; then fail 'Legacy raw GDM path comparison survived'; fi

echo '[13/16] GDM resource target detection safety'
grep -q 'GDM_RESOURCE_CANDIDATES=(' build_files/20-mactahoe-gtk.sh || fail 'GDM resource candidate detection missing'
grep -q '/usr/share/gnome-shell/theme/Yaru/gnome-shell-theme.gresource' build_files/20-mactahoe-gtk.sh || fail 'Ubuntu Yaru GDM resource candidate missing'
grep -q 'Branded GDM resource:' build_files/20-mactahoe-gtk.sh || fail 'Changed GDM resource is not reported'
if grep -q 'GDM_RESOURCE="/usr/share/gnome-shell/gnome-shell-theme.gresource"' build_files/20-mactahoe-gtk.sh; then fail 'Legacy fixed generic GDM resource check survived'; fi

echo '[14/16] GitHub build wiring'
grep -q 'build_files/build-iso.sh' .github/workflows/build-limad-os.yml || fail 'ISO workflow wiring missing'
[[ -x tests/validate-apps.sh ]] || fail 'App/update preflight script missing'
grep -q 'name: Validate LiMaD apps & updates' .github/workflows/build-limad-os.yml || fail 'Three-stage app/update job missing'
grep -q 'needs: validate_apps' .github/workflows/build-limad-os.yml || fail 'ISO build does not depend on app/update validation'
grep -q 'out/updates/' .github/workflows/build-limad-os.yml || fail 'App update artifact wiring missing'
[[ -x START-GITHUB-BUILD-LINUX.sh && -x START-GITHUB-BUILD-MAC.command ]] || fail 'Starter executables missing'
grep -q 'gh auth login' tools/github-starter.sh || fail 'Persistent GitHub CLI login wiring missing'
grep -q 'git commit-tree' tools/github-starter.sh || fail 'Existing remote history preservation missing'
if grep -q 'GitHub Token (wird nicht gespeichert)' tools/github-starter.sh; then fail 'Legacy per-run token prompt survived'; fi
grep -q '3.0.0-starter1-fix9' VERSION || fail 'FIX9 version marker missing'
grep -A3 '"app_id": "de.limad.Save"' RELEASE-MANIFEST.json | grep -q '1.0.0-preview3' || fail 'LiSave preview3 release manifest missing'


echo '[15/16] Ubuntu live-layer consistency safety'
grep -q 'UBUNTU_LIVE_SQUASHFS="casper/minimal.standard.live.squashfs"' build_files/versions.env || fail 'Ubuntu live layer lock missing'
grep -q 'sync-live-shadow.py' build_files/build-iso.sh || fail 'Live-layer shadow reconciliation not wired'
grep -q 'Live-GDM: Ubuntu Stock-Ressource geschützt' build_files/build-iso.sh || fail 'Stock live GDM guard missing'
grep -q 'ubuntu-desktop-installer.service' build_files/build-iso.sh || fail 'Live installer service verification missing'
grep -q 'NEW_LIVE_SQUASH' build_files/build-iso.sh || fail 'Live squashfs is not rebuilt'
grep -q '"/$UBUNTU_LIVE_SQUASHFS"' build_files/build-iso.sh || fail 'Rebuilt live squashfs is not mapped into ISO'
[[ -x tools/sync-live-shadow.py ]] || fail 'Live shadow synchronizer missing'
python3 -m py_compile tools/sync-live-shadow.py tools/patch-ubuntu-grub.py

echo '[16/16] Visible boot menu and Safe Graphics'
[[ -x tools/patch-ubuntu-grub.py ]] || fail 'GRUB patcher missing'
TMPGRUB="$(mktemp -d)"
cat > "$TMPGRUB/grub.cfg" <<'CFG'
set timeout=0
menuentry "Try or Install Ubuntu" {
    set gfxpayload=keep
    linux /casper/vmlinuz layerfs-path=minimal.standard.live.squashfs --- quiet splash
    initrd /casper/initrd
}
CFG
python3 tools/patch-ubuntu-grub.py "$TMPGRUB/grub.cfg"
grep -q 'set timeout_style=menu' "$TMPGRUB/grub.cfg" || fail 'GRUB menu style not forced visible'
grep -q 'set timeout=10' "$TMPGRUB/grub.cfg" || fail 'GRUB 10-second timeout missing'
grep -q 'LiMaD OS starten oder installieren' "$TMPGRUB/grub.cfg" || fail 'Normal LiMaD boot entry missing'
grep -q 'LiMaD OS - Safe Graphics' "$TMPGRUB/grub.cfg" || fail 'Safe Graphics entry missing'
awk '/LiMaD OS - Safe Graphics/{f=1} f&&/linux \/casper\/vmlinuz/{print;exit}' "$TMPGRUB/grub.cfg" | grep -q 'nomodeset' || fail 'Safe Graphics lacks nomodeset'
rm -rf "$TMPGRUB"
grep -q 'finales ISO GRUB fehlt' build_files/build-iso.sh || fail 'Final ISO boot-config verification missing'

echo 'OK: LiMaD OS 3.0 starter source validation passed.'

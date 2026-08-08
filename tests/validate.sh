#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
fail() { echo "FATAL: $*" >&2; exit 1; }

echo '[1/10] Shell/Python syntax'
while IFS= read -r -d '' f; do bash -n "$f" || fail "Shell syntax: $f"; done < <(find build_files tools -type f -name '*.sh' -print0)
bash -n START-GITHUB-BUILD-LINUX.sh
bash -n START-GITHUB-BUILD-MAC.command
python3 -m py_compile tools/build-limad-update.py build_files/*.py

echo '[2/10] Ubuntu 26.04 source lock'
grep -q 'UBUNTU_VERSION="26.04"' build_files/versions.env || fail 'Ubuntu version lock missing'
grep -q 'UBUNTU_CODENAME="resolute"' build_files/versions.env || fail 'Ubuntu codename lock missing'
grep -q '487f87faaf547ea30e0aba4d5b53346292571256b25333a978db1692bcee9dd2' build_files/versions.env || fail 'Ubuntu ISO SHA256 missing'
grep -q 'casper/minimal.standard.squashfs' build_files/versions.env || fail 'Ubuntu standard squashfs layer missing'
grep -q "'/casper/minimal.squashfs'" build_files/build-iso.sh || fail 'Ubuntu minimal base layer wiring missing'
grep -q 'lowerdir=\$BASE_ROOT,upperdir=\$STANDARD_UPPER' build_files/build-iso.sh || fail 'Ubuntu layered overlay wiring missing'

echo '[3/10] Theme/Plymouth byte lock'
sha256sum -c tests/theme-lock.sha256 >/dev/null
echo 'cdd81f11c806d5cee160994eaca89d26f3ee1d3adbadc7e7ae3a22dde5ddf3b6  system_files/usr/share/plymouth/themes/limad/boot-splash.png' | sha256sum -c - >/dev/null

echo '[4/10] No legacy immutable runtime path'
if grep -RInE 'rpm-ostree|bootc|dnf5?|/ctx/build_files|BASE_IMAGE_REF' \
  system_files/usr/local/bin system_files/usr/share/limad-save build_files \
  --include='*.sh' --include='*.py' 2>/dev/null | grep -Ev '^[^:]+:[0-9]+:[[:space:]]*#' ; then
  fail 'Bazzite/Fedora runtime command survived the Ubuntu port'
fi

echo '[5/10] Installer contrast safety'
find system_files -type f -iname '*anaconda*.css' -print -quit | grep -q . && fail 'Legacy Anaconda CSS is present'
grep -q 'Do not apply a global text color' build_files/72-installer-safety.sh || fail 'Installer contrast policy missing'

echo '[6/10] Independent updater coverage'
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

echo '[7/10] Gaming/Deskflow stack'
for pkg in steam-installer steam-devices lutris gamemode gamescope libvulkan1:i386 mesa-vulkan-drivers:i386; do grep -Fxq "$pkg" build_files/packages-required.txt || fail "Gaming package missing: $pkg"; done
grep -q 'org.deskflow.deskflow' system_files/usr/local/bin/limad-install-default-flatpaks || fail 'Deskflow provisioning missing'
grep -q 'net.davidotek.pupgui2' system_files/usr/local/bin/limad-install-default-flatpaks || fail 'ProtonUp-Qt provisioning missing'

echo '[8/10] Mail/Klang user-update launchers'
grep -q 'de.limad.Mail/current/payload' system_files/usr/local/bin/limad-mail || fail 'Mail user update root missing'
grep -q 'de.limad.Klang/current/payload' system_files/usr/local/bin/limad-klang || fail 'Klang user update root missing'
[[ -s system_files/usr/share/limad-klang/VERSION ]] || fail 'Klang packaging VERSION missing'

echo '[9/10] Update ZIP builder smoke test'
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

echo '[10/10] GitHub build wiring'
grep -q 'build_files/build-iso.sh' .github/workflows/build-limad-os.yml || fail 'ISO workflow wiring missing'
grep -q 'out/updates/' .github/workflows/build-limad-os.yml || fail 'App update artifact wiring missing'
[[ -x START-GITHUB-BUILD-LINUX.sh && -x START-GITHUB-BUILD-MAC.command ]] || fail 'Starter executables missing'
grep -q 'gh auth login' tools/github-starter.sh || fail 'Persistent GitHub CLI login wiring missing'
grep -q 'git commit-tree' tools/github-starter.sh || fail 'Existing remote history preservation missing'
if grep -q 'GitHub Token (wird nicht gespeichert)' tools/github-starter.sh; then fail 'Legacy per-run token prompt survived'; fi
grep -q '3.0.0-starter1-fix4' VERSION || fail 'FIX4 version marker missing'
grep -A3 '"app_id": "de.limad.Save"' RELEASE-MANIFEST.json | grep -q '1.0.0-preview3' || fail 'LiSave preview3 release manifest missing'

echo 'OK: LiMaD OS 3.0 starter source validation passed.'

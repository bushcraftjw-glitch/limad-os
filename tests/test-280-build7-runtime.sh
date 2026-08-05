#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
fail() { echo "2.8.0 BUILD 8 RUNTIME FAILED: $*" >&2; exit 1; }

REVISION='gnome-rc2-build5'
grep -Fqx "LIMAD_BUILD_REVISION=\"${REVISION}\"" build_files/versions.env || fail "build revision is not 2.8.0 RC1 Build 8"
grep -Fq 'VERSION="2.8.0-rc2-build5"' system_files/usr/local/bin/limad-first-login-setup || fail "first-login marker mismatch"
grep -Fq 'default-flatpaks-rc2-build5.done' system_files/usr/local/bin/limad-install-default-flatpaks || fail "Flatpak marker mismatch"
grep -Fq 'plymouth-initramfs-280-rc2-build1.done' system_files/usr/local/sbin/limad-plymouth-initramfs || fail "Plymouth marker mismatch"
if grep -IEq 'gnome42-phase4-fix(37|38|39|40|41|42|43|44|45|46|47|48)|2.7.0-rc1-fix(37|38|39|40|41|42|43|44|45|46|47|48)|default-flatpaks-fix(37|38|39|40|41|42|43|44|45|46|47|48)\.done|plymouth-initramfs-fix(37|38|39|40|41|42|43|44|45|46|47|48)\.(done|log)' \
  build_files/versions.env \
  system_files/usr/local/bin/limad-first-login-setup \
  system_files/usr/local/bin/limad-install-default-flatpaks \
  system_files/usr/local/sbin/limad-plymouth-initramfs \
  system_files/usr/lib/systemd/system/limad-plymouth-initramfs.service \
  START-GITHUB-BUILD-MAC.command START-GITHUB-BUILD-LINUX.sh; then
  fail "active files still contain an older build marker"
fi

# Installer: official Anaconda WebUI wrapper plus documented GTK classes.
GEN=tools/build-installer-theme.py
BRAND=tools/brand-installer-iso.sh
[[ -x "$GEN" ]] || fail "installer theme generator missing"
[[ -x "$BRAND" ]] || fail "ISO brander missing"
for needle in \
  '.anaconda {' \
  '.anaconda .logo' \
  ':not(.pf-v6-theme-dark) .anaconda' \
  '.pf-v6-theme-dark .anaconda' \
  '.logo-sidebar' \
  'AnacondaSpokeWindow #nav-box' \
  'limad-anaconda.css'; do
  grep -Fq "$needle" "$GEN" || fail "theme generator missing $needle"
done
for needle in \
  'usr/share/anaconda/pixmaps/limad.css' \
  'usr/share/anaconda/pixmaps/limad-os.css' \
  'usr/share/anaconda/pixmaps/bazzite.css' \
  'usr/share/anaconda/pixmaps/fedora.css' \
  'usr/share/cockpit/branding/limad/branding.css' \
  'usr/share/cockpit/branding/bazzite/branding.css' \
  'usr/share/cockpit/branding/fedora/branding.css' \
  'unsquashfs -ll "$TMP/product.img"'; do
  grep -Fq "$needle" "$BRAND" || fail "installer brander missing $needle"
done
if grep -Fq 'custom_stylesheet =' "$BRAND"; then
  fail "undocumented Anaconda custom_stylesheet option returned"
fi
if grep -Fq 'install -m 0644 "$INSTALLER_THEME/anaconda-gtk.css" "$PRODUCT/usr/share/anaconda/anaconda-gtk.css"' "$BRAND"; then
  fail "installer still replaces Anaconda base CSS"
fi
grep -Fq 'python3-pil' .github/workflows/build.yml || fail "GitHub ISO job lacks Pillow"

if [[ "${LIMAD_TEST_FORCE_NO_PIL:-0}" != "1" ]] && python3 -c 'from PIL import Image' >/dev/null 2>&1; then
  TMP_THEME="$(mktemp -d)"
  trap 'rm -rf "$TMP_THEME"' EXIT
  python3 "$GEN" \
    system_files/usr/share/limad/branding/LiMaD-System-Logo-512.png \
    system_files/usr/share/backgrounds/limad/LiMaD-Wallpaper-03-Wellen-Emblem-4K.png \
    "$TMP_THEME"
  python3 - "$TMP_THEME" <<'PYASSET'
from pathlib import Path
from PIL import Image
import sys
root=Path(sys.argv[1])
expected={
  'sidebar-logo.png':(300,150),
  'product-logo.png':(320,128),
  'logo.png':(512,512),
  'sidebar-bg.png':(384,1080),
  'topbar-bg.png':(1920,112),
}
for name, size in expected.items():
    path=root/name
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit(f'missing generated installer asset: {name}')
    if Image.open(path).size != size:
        raise SystemExit(f'{name}: wrong dimensions')
for name in ('branding.css','limad-anaconda.css','anaconda-gtk.css'):
    if not (root/name).is_file() or not (root/name).read_text().strip():
        raise SystemExit(f'missing generated stylesheet: {name}')
PYASSET
else
  echo "note: Pillow not installed locally - validating installer sources without rendering"
  python3 - <<'PYSOURCE'
from pathlib import Path
import struct

def png_size(path: str) -> tuple[int, int]:
    data=Path(path).read_bytes()[:24]
    if len(data) != 24 or data[:8] != b'\x89PNG\r\n\x1a\n' or data[12:16] != b'IHDR':
        raise SystemExit(f'{path}: invalid PNG source')
    return struct.unpack('>II', data[16:24])
for path in (
    'system_files/usr/share/limad/branding/LiMaD-System-Logo-512.png',
    'system_files/usr/share/backgrounds/limad/LiMaD-Wallpaper-03-Wellen-Emblem-4K.png',
):
    width, height=png_size(path)
    if width < 256 or height < 256:
        raise SystemExit(f'{path}: source image too small ({width}x{height})')
source=Path('tools/build-installer-theme.py').read_text()
for token in ('(300, 150)', '(320, 128)', '(512, 512)', '(384, 1080)', '(1920, 112)',
              'branding.css', 'limad-anaconda.css', '.logo-sidebar', '.anaconda {'):
    if token not in source:
        raise SystemExit(f'installer generator missing {token}')
PYSOURCE
fi

# Plymouth: exact immutable-system path confirmed on real LiMaD hardware.
PLY=system_files/usr/local/sbin/limad-plymouth-initramfs
[[ -x "$PLY" ]] || fail "Plymouth runtime repair missing"
for needle in \
  'cat > /etc/plymouth/plymouthd.conf' \
  'Theme=limad' \
  'ShowDelay=0' \
  'rpm-ostree kargs --append-if-missing=rhgb' \
  'rpm-ostree kargs --append-if-missing=quiet' \
  'rpm-ostree initramfs --enable --reboot' \
  'touch "$MARKER"' \
  '[[ -e /run/ostree-booted ]]'; do
  grep -Fq "$needle" "$PLY" || fail "Plymouth runtime missing $needle"
done
if grep -Eq 'rm .*usr/share/plymouth|ln .*usr/share/plymouth|dracut[[:space:]]+--force' "$PLY"; then
  fail "immutable /usr mutation or unsafe dracut command returned"
fi
grep -Fq 'ConditionKernelCommandLine=!rd.live.image' system_files/usr/lib/systemd/system/limad-plymouth-initramfs.service || fail "live ISO kernel guard missing"
grep -Fq 'ConditionPathExists=!/run/initramfs/live' system_files/usr/lib/systemd/system/limad-plymouth-initramfs.service || fail "live ISO path guard missing"
grep -Fq 'ConditionPathExists=!/var/lib/limad/plymouth-initramfs-280-rc2-build1.done' system_files/usr/lib/systemd/system/limad-plymouth-initramfs.service || fail "Build 8 Plymouth guard missing"
grep -Fq 'OnBootSec=120s' system_files/usr/lib/systemd/system/limad-plymouth-initramfs.timer || fail "Plymouth first-boot timer mismatch"

# Audio: real Flatpak version query and an executable parser test.  The invalid
# flatpak info --show-version option must never return.
KLANG=system_files/usr/share/limad-klang/limad_klang.py
BACKEND=system_files/usr/share/limad-klang/limad_klang_backend.py
[[ -f "$KLANG" && -f "$BACKEND" ]] || fail "LiMaD Klang files missing"
if grep -R -- '--show-version' "$KLANG" "$BACKEND" >/dev/null; then
  fail "invalid Flatpak --show-version option still present"
fi
for needle in \
  'flatpak, "list", "--app", "--columns=application,version"' \
  'parse_flatpak_list' \
  'flatpak-info-no-version' \
  'base / "app" / EE_ID / "EasyEffectsServer"' \
  'write_user_preset' \
  'load_preset_cli' \
  'start_hidden_cli'; do
  grep -Fq "$needle" "$BACKEND" || fail "audio backend missing $needle"
done
for needle in \
  'get_property:output:equalizer:0:left:band0Gain' \
  'get_property:output:equalizer:0:left:band9Gain' \
  'EasyEffects hat die Werte bestätigt'; do
  grep -Fq "$needle" "$KLANG" || fail "LiMaD Klang runtime verification missing $needle"
done
if grep -R -- '--gapplication-service' "$KLANG" system_files/usr/local/bin/limad-easyeffects-service >/dev/null; then
  fail "obsolete GTK EasyEffects startup option returned"
fi
grep -Fq -- '--hide-window' system_files/usr/local/bin/limad-easyeffects-service || fail "Qt EasyEffects background startup missing"
grep -Fq 'Preset-Steuerung aktiv' "$KLANG" || fail "audio preset-first mode missing"
grep -Fq 'Preset wurde sofort neu geladen' "$KLANG" || fail "audio fallback result missing"

TMP_FAKE="$(mktemp -d)"
# macOS uses a small sockaddr_un path limit. Its default TMPDIR under
# /var/folders/... can make the synthetic EasyEffects socket exceed that
# limit even though the application path on LiMaD OS is valid. Use a short,
# explicit /tmp directory only for the AF_UNIX runtime test.
TMP_SOCKET="$(mktemp -d /tmp/lm280.XXXXXX)"
trap 'rm -rf "${TMP_THEME:-}" "$TMP_FAKE" "$TMP_SOCKET"' EXIT
cat > "$TMP_FAKE/flatpak" <<'FAKE'
#!/usr/bin/env sh
if [ "$1" = list ]; then
  printf 'com.github.wwmm.easyeffects\t8.2.8\n'
  exit 0
fi
if [ "$1" = info ]; then
  printf 'EasyEffects\nVersion: 8.2.8\n'
  exit 0
fi
if [ "$1" = run ]; then
  printf '%s\n' "$*" >> "${LIMAD_FAKE_FLATPAK_LOG:?}"
  exit 0
fi
exit 1
FAKE
chmod +x "$TMP_FAKE/flatpak"
PATH="$TMP_FAKE:$PATH" PYTHONPATH="system_files/usr/share/limad-klang" python3 - <<'PYBACKEND'
from limad_klang_backend import detect_easyeffects, first_float, version_supported
result=detect_easyeffects()
assert result.installed is True, result
assert result.version == (8, 2, 8), result
assert version_supported(result.version) is True
assert first_float('value: -1.50 dB') == -1.5
PYBACKEND

FAKE_LOG="$TMP_FAKE/flatpak-run.log"
: > "$FAKE_LOG"
PATH="$TMP_FAKE:$PATH" LIMAD_FAKE_FLATPAK_LOG="$FAKE_LOG" PYTHONPATH="system_files/usr/share/limad-klang" python3 - <<'PYCLI'
from limad_klang_backend import load_preset_cli, start_hidden_cli
assert load_preset_cli().ok
assert start_hidden_cli().ok
PYCLI
grep -Fqx 'run com.github.wwmm.easyeffects -l LiMaD Klang' "$FAKE_LOG" || fail "preset CLI does not use the reliable -l path"
grep -Fqx 'run com.github.wwmm.easyeffects -w' "$FAKE_LOG" || fail "hidden startup does not use the reliable -w path"
python3 - <<'PYPRESETFIRST'
from pathlib import Path
text=Path('system_files/usr/share/limad-klang/limad_klang.py').read_text()
start=text.index('def start_easyeffects')
end=text.index('class KlangWindow', start)
body=text[start:end]
if body.index('write_user_preset(PROFILES["Neutral"])') > body.index('if not socket_ready()'):
    raise SystemExit('preset control is not established before optional socket discovery')
if 'steuerungsserver ist nicht erreichbar' in body.lower():
    raise SystemExit('missing optional socket is still presented as a fatal application error')
PYPRESETFIRST

PYTHONPATH="system_files/usr/share/limad-klang" python3 - "$TMP_SOCKET" <<'PYCONTROL'
from pathlib import Path
import json
import socket
import sys
from limad_klang_backend import EE_ID, find_easyeffects_socket, write_user_preset

root=Path(sys.argv[1])
runtime=root/'runtime'
socket_path=runtime/'app'/EE_ID/'EasyEffectsServer'
socket_path.parent.mkdir(parents=True)
server=socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
server.bind(str(socket_path))
try:
    assert find_easyeffects_socket(runtime) == socket_path
finally:
    server.close()

template=Path('system_files/usr/share/limad-klang/LiMaD Klang.json')
target=root/'preset'/'LiMaD Klang.json'
write_user_preset({'bass':4.0,'mid':1.5,'treble':3.0}, source=template, targets=[target])
data=json.loads(target.read_text())
eq=data['output']['equalizer#0']
assert eq['left']['band0']['gain'] == 4.0
assert eq['left']['band4']['gain'] == 1.5
assert eq['right']['band9']['gain'] == 3.0
assert eq['output-gain'] == -3.0
PYCONTROL

PRESET_HOME="$TMP_FAKE/home"
mkdir -p "$PRESET_HOME"
LIMAD_KLANG_PRESET_SOURCE="$PWD/system_files/usr/share/limad-klang/LiMaD Klang.json" HOME="$PRESET_HOME" XDG_DATA_HOME="$PRESET_HOME/data" XDG_CONFIG_HOME="$PRESET_HOME/config" \
  system_files/usr/local/bin/limad-install-klang-preset
PRESET_TARGET="$PRESET_HOME/.var/app/com.github.wwmm.easyeffects/data/easyeffects/output/LiMaD Klang.json"
printf 'user-change\n' > "$PRESET_TARGET"
LIMAD_KLANG_PRESET_SOURCE="$PWD/system_files/usr/share/limad-klang/LiMaD Klang.json" HOME="$PRESET_HOME" XDG_DATA_HOME="$PRESET_HOME/data" XDG_CONFIG_HOME="$PRESET_HOME/config" \
  system_files/usr/local/bin/limad-install-klang-preset
grep -Fqx 'user-change' "$PRESET_TARGET" || fail "preset helper overwrote LiMaD slider values"

grep -Fq '${APP_ROOT}/data/easyeffects/output' system_files/usr/local/bin/limad-install-klang-preset || fail "current Flatpak preset path missing"
grep -Fq 'flatpak update --user --noninteractive -y "com.github.wwmm.easyeffects"' system_files/usr/local/bin/limad-install-default-flatpaks || fail "EasyEffects update step missing"

bash -n "$BRAND" \
  "$PLY" \
  system_files/usr/local/sbin/limad-plymouth-reboot-cleanup \
  system_files/usr/local/bin/limad-plymouth-notify \
  system_files/usr/local/bin/limad-install-klang-preset \
  system_files/usr/local/bin/limad-easyeffects-service \
  build_files/55-plymouth.sh \
  system_files/usr/local/bin/limad-install-default-flatpaks
python3 -m py_compile "$GEN" "$KLANG" "$BACKEND"

for launcher in START-GITHUB-BUILD-MAC.command START-GITHUB-BUILD-LINUX.sh; do
  grep -Fq 'GITHUB_OWNER_DEFAULT="bushcraftjw-glitch"' "$launcher" || fail "$launcher has wrong GitHub owner"
  grep -Fq 'GITHUB_REPO_DEFAULT="limad-os"' "$launcher" || fail "$launcher has wrong GitHub repository"
  grep -Fq 'Sicherheitsmodus: Das Repository wird niemals automatisch geloescht.' "$launcher" || fail "$launcher lacks repository deletion guard"
  if grep -Eq 'api[[:space:]]+DELETE|delete_repo|Zum Bestaetigen.*LOESCHEN' "$launcher"; then
    fail "$launcher can still delete a remote repository"
  fi
done

echo "LiMaD OS 2.8.0 RC1 Build 8 installer, Plymouth, Klang and inherited runtime checks: PASS"

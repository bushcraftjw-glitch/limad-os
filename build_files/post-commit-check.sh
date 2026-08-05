#!/usr/bin/env bash
# Runs in the finished image, after `ostree container commit`.
# The image entrypoint is bypassed by the workflow so rpm-ostree is not invoked
# inside a plain Podman container.
set -Eeuo pipefail

echo ":: Inspecting committed LiMaD image"
ls /usr/share/themes
ls -d /usr/share/icons/LiMaD /usr/share/icons/WhiteSur-dark

grep -q '^ID=fedora$' /usr/lib/os-release || { echo "POST-COMMIT FAILED: Fedora compatibility ID missing" >&2; exit 1; }
grep -q '^NAME="LiMaD OS"$' /usr/lib/os-release || { echo "POST-COMMIT FAILED: visible OS name is not LiMaD" >&2; exit 1; }
grep -q '^BOOTLOADER_NAME="LiMaD OS ' /usr/lib/os-release || { echo "POST-COMMIT FAILED: bootloader name is not LiMaD" >&2; exit 1; }
grep -q '^Theme=limad$' /etc/plymouth/plymouthd.conf || { echo "POST-COMMIT FAILED: Plymouth is not LiMaD" >&2; exit 1; }
test "$(readlink -f /usr/share/plymouth/themes/default.plymouth)" = /usr/share/plymouth/themes/limad/limad.plymouth || { echo "POST-COMMIT FAILED: default Plymouth link is not LiMaD" >&2; exit 1; }
test -s /usr/share/backgrounds/limad/LiMaD-Wallpaper-02-Logo-Zentriert-4K.png || { echo "POST-COMMIT FAILED: default wallpaper missing" >&2; exit 1; }
grep -q 'LiMaD-Wallpaper-02-Logo-Zentriert-4K.png' /etc/dconf/db/local.d/zzzzzzzzzz-limad-branding || { echo "POST-COMMIT FAILED: wallpaper dconf default missing" >&2; exit 1; }
test -s /usr/share/icons/LiMaD/64x64/apps/limad-start.png || { echo "POST-COMMIT FAILED: menu logo missing" >&2; exit 1; }
test -s /usr/share/pixmaps/de.limad.Logo.png || { echo "POST-COMMIT FAILED: system information logo missing" >&2; exit 1; }
for frame in /usr/share/plymouth/themes/limad/spinner-{00..11}.png; do
  test -s "$frame" || { echo "POST-COMMIT FAILED: Plymouth spinner frame missing: $frame" >&2; exit 1; }
done
for branding_id in limad bazzite fedora; do
  test -s "/usr/share/cockpit/branding/${branding_id}/branding.css"     || { echo "POST-COMMIT FAILED: installer branding source missing for ${branding_id}" >&2; exit 1; }
done
test -f /usr/lib/systemd/system/gdm.service || { echo "POST-COMMIT FAILED: gdm.service missing" >&2; exit 1; }
test "$(readlink -f /etc/systemd/system/display-manager.service || true)" = /usr/lib/systemd/system/gdm.service \
  || { echo "POST-COMMIT FAILED: Bazzite GNOME display manager is not GDM" >&2; exit 1; }
test -s /usr/share/limad/gdm-branding.env || { echo "POST-COMMIT FAILED: GDM branding record missing" >&2; exit 1; }
source /usr/share/limad/gdm-branding.env
test -s "$LIMAD_GDM_RESOURCE" || { echo "POST-COMMIT FAILED: branded GDM resource missing" >&2; exit 1; }
test "$(sha256sum "$LIMAD_GDM_RESOURCE" | awk '{print $1}')" = "$LIMAD_GDM_BRANDED_SHA256" \
  || { echo "POST-COMMIT FAILED: branded GDM resource hash mismatch" >&2; exit 1; }
test "$LIMAD_GDM_BRANDED_SHA256" != "$LIMAD_GDM_ORIGINAL_SHA256" \
  || { echo "POST-COMMIT FAILED: GDM resource was not changed" >&2; exit 1; }
export HOME=/tmp/limad-postcommit-gsettings/home
export XDG_CACHE_HOME=/tmp/limad-postcommit-gsettings/cache
export XDG_RUNTIME_DIR=/tmp/limad-postcommit-gsettings/run
export GSETTINGS_BACKEND=memory
install -d -m 0700 "$HOME" "$XDG_CACHE_HOME/dconf" "$XDG_RUNTIME_DIR"
button_layout="$(gsettings --schemadir /usr/share/glib-2.0/schemas get org.gnome.desktop.wm.preferences button-layout 2>/dev/null || echo '?')"
test "$button_layout" = "'close,maximize,minimize:'"   || { echo "POST-COMMIT FAILED: FIX22 left-side window buttons changed: $button_layout" >&2; exit 1; }
favorites="$(gsettings --schemadir /usr/share/glib-2.0/schemas get org.gnome.shell favorite-apps 2>/dev/null || echo '?')"
for desktop in de.limad.Cut.desktop de.limad.Drop.desktop de.limad.WindowsApps.desktop de.limad.AnycubicSlicerNext.desktop; do
  case "$favorites" in
    *"'$desktop'"*) ;;
    *) echo "POST-COMMIT FAILED: requested dock favorite missing: $desktop" >&2; exit 1 ;;
  esac
done

test -f /usr/share/limad-windows/installer.py || { echo "POST-COMMIT FAILED: Windows installer missing" >&2; exit 1; }
test -f /usr/share/limad-windows/recipe_engine.py || { echo "POST-COMMIT FAILED: Windows recipe engine missing" >&2; exit 1; }
python3 -c 'from pathlib import Path; import sys; [compile(Path(p).read_text(encoding="utf-8"), p, "exec") for p in sys.argv[1:]]' /usr/share/limad-windows/installer.py /usr/share/limad-windows/recipe_engine.py || { echo "POST-COMMIT FAILED: Windows installer Python validation failed" >&2; exit 1; }

echo "Committed branding identity, GDM, Plymouth, FIX22 buttons, dock and menu logo verified."

source /etc/os-release
releasever="${VERSION_ID%%.*}"
immutable_key="/usr/share/limad/repo-keys/RPM-GPG-KEY-terra${releasever}-mesa"

test -s "$immutable_key" || {
  echo "POST-COMMIT FAILED: immutable Terra key missing: $immutable_key" >&2
  find /usr/share/limad/repo-keys /usr/share/distribution-gpg-keys \
    -type f -iname '*terra*mesa*' -print 2>/dev/null || true
  exit 1
}

python3 - <<'PY'
import configparser
import glob
import os
import platform
import re
import sys

IMMUTABLE_KEY_DIR = '/usr/share/limad/repo-keys'
REPO_DIRS = (
    '/etc/yum.repos.d',
    '/usr/etc/yum.repos.d',
    '/etc/distro.repos.d',
    '/usr/share/dnf5/repos.d',
)

releasever = ''
with open('/etc/os-release', encoding='utf-8') as handle:
    for line in handle:
        if line.startswith('VERSION_ID='):
            releasever = line.split('=', 1)[1].strip().strip('"')
            break
basearch = platform.machine()


def expand(value: str) -> str:
    value = value.replace('${releasever}', releasever)
    value = re.sub(r'\$releasever(?![A-Za-z0-9_])', releasever, value)
    value = value.replace('${basearch}', basearch)
    value = re.sub(r'\$basearch(?![A-Za-z0-9_])', basearch, value)
    return value


broken = []
terra_found = False
repo_files = []
for directory in REPO_DIRS:
    if os.path.isdir(directory):
        repo_files.extend(sorted(glob.glob(os.path.join(directory, '*.repo'))))

for repo_file in repo_files:
    parser = configparser.RawConfigParser(interpolation=None)
    parser.optionxform = str
    try:
        parser.read(repo_file)
    except configparser.Error as exc:
        broken.append(f'{repo_file}: cannot parse: {exc}')
        continue

    for section in parser.sections():
        if parser.get(section, 'enabled', fallback='1').strip() != '1':
            continue
        tokens = parser.get(section, 'gpgkey', fallback='').split()
        if section == 'terra-mesa':
            terra_found = True
            local_paths = [expand(t[len('file://'):]) for t in tokens if t.startswith('file://')]
            if not local_paths:
                broken.append(f'terra-mesa in {repo_file}: no file:// key')
            for path in local_paths:
                if not path.startswith(IMMUTABLE_KEY_DIR + '/'):
                    broken.append(
                        f'terra-mesa in {repo_file}: mutable key path {path}'
                    )

        for token in tokens:
            if not token.startswith('file://'):
                continue
            resolved = expand(token[len('file://'):])
            if '$' not in resolved and (
                not os.path.isfile(resolved) or os.path.getsize(resolved) == 0
            ):
                broken.append(f'{section} in {repo_file} -> {resolved}')

if not terra_found:
    broken.append('enabled terra-mesa definition not found after commit')
if broken:
    for entry in broken:
        print(f'POST-COMMIT BROKEN: {entry}', file=sys.stderr)
    sys.exit('POST-COMMIT FAILED: repository key audit failed')

print('Committed repository definitions use readable local keys.')
PY

if dnf5 makecache --refresh >/tmp/limad-postcommit-makecache.log 2>&1; then
  echo "Post-commit repository metadata check passed."
else
  echo "POST-COMMIT FAILED: repository metadata cannot be refreshed" >&2
  tail -n 40 /tmp/limad-postcommit-makecache.log >&2
  exit 1
fi

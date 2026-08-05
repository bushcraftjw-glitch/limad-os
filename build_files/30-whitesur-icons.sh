#!/usr/bin/env bash
# Installs the WhiteSur icon theme from the pinned upstream tag.
# WhiteSur provides every generic icon: folders, mimetypes, devices, actions,
# status symbols and third-party applications. LiMaD adds only its own
# application icons on top (see 40-limad-icons.sh).
set -Eeuo pipefail

# shellcheck source=/dev/null
source /ctx/build_files/versions.env

readonly WORK="/tmp/limad-build/whitesur-icons"
readonly SRC_SHARE="/usr/share/limad-source/whitesur-icon-theme"

# Same container-safe identity as for MacTahoe: no login session exists here.
export USER="root"
export LOGNAME="root"
export SUDO_USER="root"
export HOME="${HOME:-/root}"

# A container build has no terminal; the same shims as in the MacTahoe step
# keep cosmetic terminal commands from aborting the run. Removed at the end.
export TERM="${TERM:-xterm-256color}"
readonly SHIM_DIR="/tmp/limad-build/shim-icons"
install -d "$SHIM_DIR"
printf '%s\n' '#!/usr/bin/env bash' \
  'while [[ $# -gt 0 ]]; do case "$1" in -v|-n|-E|-H|-k|-S|-i|-s) shift;; -u|-g|-p) shift 2;; --) shift; break;; -*) shift;; *) break;; esac; done' \
  '(($# == 0)) && exit 0' \
  'exec "$@"' > "${SHIM_DIR}/sudo"
for cosmetic in setterm clear reset; do
  printf '%s\n' '#!/usr/bin/env bash' 'exit 0' > "${SHIM_DIR}/${cosmetic}"
done
printf '%s\n' '#!/usr/bin/env bash' \
  'case "${1:-}" in cols) echo 100;; lines) echo 40;; esac' \
  'exit 0' > "${SHIM_DIR}/tput"
chmod 0755 "${SHIM_DIR}"/*
export PATH="${SHIM_DIR}:${PATH}"

echo ":: Cloning WhiteSur icon theme ${WHITESUR_ICONS_TAG}"
rm -rf "$WORK"
mkdir -p "$(dirname "$WORK")"
git clone --depth 1 --branch "$WHITESUR_ICONS_TAG" "$WHITESUR_ICONS_REPO" "$WORK"

pushd "$WORK" >/dev/null

# Guard against the same logname trap as in the MacTahoe step.
if grep -rqn '\blogname\b' . --include='*.sh' 2>/dev/null; then
  find . -type f -name '*.sh' -print0 | xargs -0 --no-run-if-empty sed -i 's/\blogname\b/id -un/g'
  echo "   replaced logname with 'id -un'"
fi

CHECKED_OUT="$(git describe --tags --exact-match 2>/dev/null || true)"
if [[ "$CHECKED_OUT" != "$WHITESUR_ICONS_TAG" ]]; then
  echo "FATAL: expected tag ${WHITESUR_ICONS_TAG}, got '${CHECKED_OUT}'" >&2
  exit 1
fi
COMMIT="$(git rev-parse HEAD)"
echo "   commit ${COMMIT}"

# -d  system-wide destination
# -a  alternative (macOS-like) folder icons
# -b  bold panel icons, better readable on the taller LiMaD top bar
# -t purple  accent colour matching the LiMaD brand
./install.sh -d /usr/share/icons -a -b -t purple

install -d "$SRC_SHARE"
for f in COPYING LICENSE README.md; do
  [[ -f "$f" ]] && install -m 0644 "$f" "$SRC_SHARE/"
done
cat > "$SRC_SHARE/PROVENANCE.txt" <<EOF
WhiteSur Icon Theme
Upstream: ${WHITESUR_ICONS_REPO}
Tag:      ${WHITESUR_ICONS_TAG}
Commit:   ${COMMIT}
License:  ${WHITESUR_ICONS_LICENSE}
Author:   Vinceliuice and contributors
Provides all generic and third-party icons for LiMaD OS.
EOF

popd >/dev/null
rm -rf "$WORK" "$SHIM_DIR"

# ---------------------------------------------------------------------------
# Determine the name that was actually produced.
#
# With an accent colour the installer creates "WhiteSur-<accent>-dark" instead
# of "WhiteSur-dark", and the exact naming changes between releases. The name
# is therefore read from disk and handed on to the following steps, exactly as
# the MacTahoe step does for the GTK theme.
# ---------------------------------------------------------------------------
echo ":: Determining the installed icon theme"
ICON_THEME_ACTUAL=""
for candidate in "WhiteSur-${WHITESUR_ACCENT}-dark" "WhiteSur-dark"; do
  if [[ -f "/usr/share/icons/${candidate}/index.theme" ]]; then
    ICON_THEME_ACTUAL="$candidate"
    break
  fi
done
if [[ -z "$ICON_THEME_ACTUAL" ]]; then
  ICON_THEME_ACTUAL="$(find /usr/share/icons -mindepth 1 -maxdepth 1 -type d \
    -name 'WhiteSur*-dark' -printf '%f\n' 2>/dev/null | sort | head -n 1)"
fi
if [[ -z "$ICON_THEME_ACTUAL" ]]; then
  echo "FATAL: no dark WhiteSur icon theme was installed" >&2
  ls -1 /usr/share/icons >&2 || true
  exit 1
fi
echo "   ${ICON_THEME_ACTUAL}"

install -d /usr/share/limad
if [[ -f /usr/share/limad/theme-names.env ]]; then
  sed -i '/^LIMAD_WHITESUR_ICON_ACTUAL=/d' /usr/share/limad/theme-names.env
fi
printf 'LIMAD_WHITESUR_ICON_ACTUAL="%s"\n' "$ICON_THEME_ACTUAL" \
  >> /usr/share/limad/theme-names.env

# Compatibility name for anything that still expects the plain "WhiteSur-dark".
if [[ "$ICON_THEME_ACTUAL" != "WhiteSur-dark" && ! -e /usr/share/icons/WhiteSur-dark ]]; then
  ln -sfn "$ICON_THEME_ACTUAL" /usr/share/icons/WhiteSur-dark
  echo "   compatibility link WhiteSur-dark -> ${ICON_THEME_ACTUAL}"
fi

# The LiMaD overlay must inherit the theme that really exists.
LIMAD_INDEX="/usr/share/icons/${LIMAD_ICON_THEME_NAME}/index.theme"
if [[ -f "$LIMAD_INDEX" ]]; then
  sed -i "s|^Inherits=.*|Inherits=${ICON_THEME_ACTUAL},WhiteSur,Adwaita,hicolor|" "$LIMAD_INDEX"
  echo "   LiMaD icon theme now inherits ${ICON_THEME_ACTUAL}"
fi

echo ":: WhiteSur icon step done"

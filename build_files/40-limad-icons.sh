#!/usr/bin/env bash
# Activates the LiMaD icon theme.
#
# The theme itself ships as plain files in system_files/usr/share/icons/LiMaD
# and contains ONLY icons for LiMaD's own applications. Everything else is
# inherited from WhiteSur-dark, so this step just validates the overlay and
# refreshes the icon caches.
set -Eeuo pipefail

# shellcheck source=/dev/null
source /ctx/build_files/versions.env

# Step 30 recorded which WhiteSur theme really exists.
if [[ -f /usr/share/limad/theme-names.env ]]; then
  # shellcheck source=/dev/null
  source /usr/share/limad/theme-names.env
fi
LIMAD_WHITESUR_ICON_NAME="${LIMAD_WHITESUR_ICON_ACTUAL:-$LIMAD_WHITESUR_ICON_NAME}"

readonly THEME_DIR="/usr/share/icons/${LIMAD_ICON_THEME_NAME}"

echo ":: Validating LiMaD icon overlay"
[[ -f "${THEME_DIR}/index.theme" ]] || { echo "FATAL: ${THEME_DIR}/index.theme missing" >&2; exit 1; }

grep -q "^Inherits=${LIMAD_WHITESUR_ICON_NAME}" "${THEME_DIR}/index.theme" || {
  echo "FATAL: LiMaD icon theme does not inherit ${LIMAD_WHITESUR_ICON_NAME}" >&2
  exit 1
}

# The overlay must stay small and application-only. A generic icon leaking in
# here would silently override WhiteSur for the whole desktop.
mapfile -t STRAY < <(find "$THEME_DIR" -mindepth 1 -maxdepth 2 -type d \
  ! -name 'apps' ! -name 'scalable' ! -regex '.*/[0-9]+x[0-9]+' -printf '%p\n')
if ((${#STRAY[@]})); then
  printf 'FATAL: non-application directory in LiMaD icon theme: %s\n' "${STRAY[@]}" >&2
  exit 1
fi

COUNT="$(find "$THEME_DIR" -type f -name '*.png' -o -type f -name '*.svg' | wc -l)"
echo "   ${COUNT} LiMaD application icon files"

for size in 16 22 24 32 48 64 128 256 512; do
  primary="${THEME_DIR}/${size}x${size}/apps/de.limad.WindowsApps.png"
  alias="${THEME_DIR}/${size}x${size}/apps/windows-apps.png"
  [[ -s "$primary" && -s "$alias" ]] || {
    echo "FATAL: Windows-Programme icon missing at ${size}px" >&2
    exit 1
  }
  cmp -s "$primary" "$alias" || {
    echo "FATAL: Windows-Programme icon aliases differ at ${size}px" >&2
    exit 1
  }
done
cmp -s "${THEME_DIR}/scalable/apps/de.limad.WindowsApps.svg" \
       /usr/share/icons/hicolor/scalable/apps/de.limad.WindowsApps.svg || {
  echo "FATAL: Windows-Programme scalable fallback differs from LiMaD artwork" >&2
  exit 1
}

echo ":: Refreshing icon caches"
for theme in "${LIMAD_ICON_THEME_NAME}" "${LIMAD_WHITESUR_ICON_NAME}"; do
  [[ -d "/usr/share/icons/${theme}" ]] || continue
  gtk-update-icon-cache -f -q "/usr/share/icons/${theme}" 2>/dev/null || true
done

echo ":: LiMaD icon step done"

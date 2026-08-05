#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
[[ "$(cat VERSION)" == "2.8.0-rc2-gnome-rc2-build5" ]]
grep -q 'LIMAD_OS_VERSION="2.8.0-rc2"' build_files/versions.env
grep -Eq 'gnome-rc2-build(4|5)|gnome42-phase4-fix(32|35|36|37|38|39|41|42|43|44|45|46|47|48|49|50)' build_files/versions.env
for f in \
  system_files/usr/share/plymouth/themes/limad/boot-splash.png \
  system_files/usr/share/backgrounds/limad/LiMaD-Wallpaper-02-Logo-Zentriert-4K.png \
  system_files/usr/share/icons/LiMaD/512x512/apps/limad-start.png \
  tools/brand-installer-iso.sh \
  tools/verify-branded-iso.sh \
  system_files/usr/local/bin/limad-system-update \
  system_files/usr/local/bin/limad-updater; do
  [[ -s "$f" ]] || { echo "Fehlt oder leer: $f" >&2; exit 1; }
done
echo "Phase 4 release candidate wiring: PASS"

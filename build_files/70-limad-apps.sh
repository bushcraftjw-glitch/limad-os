#!/usr/bin/env bash
# Wires the natively shipped LiMaD applications into the running system:
# LiMaDCut, LiMaD Study, LiDrop, LiLink, LiNotes, LiSave and Anycubic Slicer Next.
set -Eeuo pipefail

# shellcheck source=/dev/null
source /ctx/build_files/versions.env

echo ":: Checking application payloads"
[[ -x /usr/local/libexec/limad-select-app-root ]] || { echo "FATAL: version-aware app selector missing" >&2; exit 1; }

declare -A LAUNCHERS=(
  [/usr/local/bin/limad-cut]="LiMaDCut ${LIMAD_CUT_VERSION}"
  [/usr/local/bin/limad-study]="LiMaD Study ${LIMAD_STUDY_VERSION}"
  [/usr/local/bin/limad-drop]="LiDrop ${LIDROP_VERSION}"
  [/usr/local/bin/lilink]="LiLink ${LILINK_VERSION}"
  [/usr/local/bin/limad-notes]="LiNotes ${LINOTES_VERSION}"
  [/usr/local/bin/limad-save]="LiSave ${LISAVE_VERSION}"
  [/usr/local/bin/limad-save-cli]="LiSave CLI ${LISAVE_VERSION}"
  [/usr/local/bin/limad-windows-setup]="Windows-Programme ${LIMAD_WINDOWS_VERSION}"
  [/usr/bin/anycubicslicernext]="Anycubic Slicer Next ${ANYCUBIC_DEB_VERSION}"
  [/usr/local/bin/limad-updater]="LiMaD App-Updater"
  [/usr/local/bin/limad-mail]="LiMaD Mail 1.8"
  [/usr/local/bin/limad-app-update-check]="LiMaD automatische Updateprüfung"
)
for bin in "${!LAUNCHERS[@]}"; do
  [[ -f "$bin" ]] || { echo "FATAL: launcher missing: $bin" >&2; exit 1; }
  chmod 0755 "$bin"
  echo "   ${LAUNCHERS[$bin]} -> ${bin}"
done

chmod 0755 /usr/share/limad-updater/backend.py /usr/share/limad-updater/updater.py /usr/share/limad-updater/check.py

for extra in /usr/local/bin/limad-linkd /usr/local/bin/limad-link-status-ensure /usr/local/bin/limad-dropd /usr/local/bin/limad-drop-send /usr/local/bin/limad-airdrop-check /usr/local/bin/limad-airdrop-control /usr/local/bin/limad-airdrop-session /usr/local/bin/limad-airdrop-wait /usr/local/bin/limad-opendrop-receive /usr/local/bin/limad-app-runtime-repair /usr/local/bin/limad-app-integrity-check /usr/local/bin/limad-mail-setup /usr/local/bin/limad-mail-theme-apply /usr/local/bin/limad-bottles-run /usr/local/bin/limad-user-folders-setup /usr/local/bin/limad-zen-deutsch-setup; do
  [[ -f "$extra" ]] && chmod 0755 "$extra"
done

echo ":: AirDrop services stay disabled until an explicit, authenticated hardware-safe activation"
systemctl --global disable limad-opendrop-receive.service 2>/dev/null || true

echo ":: Enabling LiDrop and LiLink user services"
systemctl --global enable limad-app-runtime-repair.service 2>/dev/null || true
systemctl --global enable limad-drop.service 2>/dev/null || true
systemctl --global enable limad-link.service 2>/dev/null || true
systemctl --global enable limad-airdrop.timer 2>/dev/null || true
systemctl --global enable limad-app-update-check.timer 2>/dev/null || true
systemctl --global disable limad-save.timer 2>/dev/null || true

echo ":: Registering file types"
update-mime-database /usr/share/mime 2>/dev/null || true
update-desktop-database /usr/share/applications 2>/dev/null || true

echo ":: Refreshing icon caches"
for theme in "${LIMAD_ICON_THEME_NAME}" hicolor; do
  [[ -d "/usr/share/icons/${theme}" ]] || continue
  gtk-update-icon-cache -f -q "/usr/share/icons/${theme}" 2>/dev/null || true
done

echo ":: Validating desktop entries"
for desktop in /usr/share/applications/de.limad.*.desktop; do
  [[ -e "$desktop" ]] || continue
  desktop-file-validate "$desktop" || {
    echo "FATAL: invalid desktop entry: $desktop" >&2
    exit 1
  }
  exec_bin="$(awk -F= '/^Exec=/{print $2; exit}' "$desktop" | awk '{print $1}')"
  if [[ "$exec_bin" == /* ]]; then
    [[ -x "$exec_bin" ]] || {
      echo "FATAL: ${desktop} points at non-executable ${exec_bin}" >&2
      exit 1
    }
  else
    command -v "$exec_bin" >/dev/null 2>&1 || {
      echo "FATAL: ${desktop} points at unavailable command ${exec_bin}" >&2
      exit 1
    }
  fi
done

echo ":: Application step done"

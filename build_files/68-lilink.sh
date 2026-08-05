#!/usr/bin/env bash
set -Eeuo pipefail
source /ctx/build_files/versions.env

echo ":: Installing LiLink ${LILINK_VERSION}"
for command in grdctl gnome-connections avahi-browse avahi-publish-service openssl; do
  command -v "$command" >/dev/null 2>&1 || { echo "FATAL: LiLink dependency missing: $command" >&2; exit 1; }
done
command -v xfreerdp3 >/dev/null 2>&1 || command -v xfreerdp >/dev/null 2>&1 || { echo "FATAL: FreeRDP client missing" >&2; exit 1; }
command -v deskflow >/dev/null 2>&1 || command -v deskflow-core >/dev/null 2>&1 || { echo "FATAL: Deskflow missing" >&2; exit 1; }
chmod 0755 /usr/local/bin/lilink /usr/local/bin/limad-linkd /usr/local/bin/limad-link-status-ensure /usr/share/limad-link/app.py /usr/share/limad-link/daemon.py
systemctl --global enable limad-link.service 2>/dev/null || true
if command -v firewall-offline-cmd >/dev/null 2>&1; then
  firewall-offline-cmd --add-service=limad-link >/dev/null 2>&1 || true
fi
update-desktop-database /usr/share/applications 2>/dev/null || true
for theme in LiMaD hicolor; do
  [[ -d "/usr/share/icons/${theme}" ]] && gtk-update-icon-cache -f -q "/usr/share/icons/${theme}" 2>/dev/null || true
done
echo ":: LiLink installed"

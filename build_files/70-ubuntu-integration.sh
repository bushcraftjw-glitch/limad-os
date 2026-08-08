#!/usr/bin/env bash
set -Eeuo pipefail
source /opt/limad-build/versions.env
chmod 0755 /usr/local/libexec/limad-select-app-root 2>/dev/null || true
find /usr/local/bin -maxdepth 1 -type f -name 'limad-*' -exec chmod 0755 {} + 2>/dev/null || true
chmod 0755 /usr/local/bin/lilink 2>/dev/null || true
chmod 0755 /usr/bin/anycubicslicernext 2>/dev/null || true
chmod 0755 /usr/share/limad-updater/*.py 2>/dev/null || true
find /usr/share/limad-study /usr/share/limad-drop /usr/share/limad-link /usr/share/limad-save /usr/share/limad-notes /usr/share/limad-klang -type f -name '*.py' -exec chmod 0644 {} + 2>/dev/null || true
systemctl --global enable limad-app-runtime-repair.service 2>/dev/null || true
systemctl --global enable limad-drop.service 2>/dev/null || true
systemctl --global enable limad-link.service 2>/dev/null || true
systemctl --global enable limad-airdrop.timer 2>/dev/null || true
systemctl --global enable limad-app-update-check.timer 2>/dev/null || true
systemctl --global disable limad-save.timer 2>/dev/null || true
systemctl --global disable limad-opendrop-receive.service 2>/dev/null || true
update-mime-database /usr/share/mime 2>/dev/null || true
update-desktop-database /usr/share/applications 2>/dev/null || true
for theme in LiMaD hicolor; do
  [[ -d "/usr/share/icons/$theme" ]] && gtk-update-icon-cache -f -q "/usr/share/icons/$theme" 2>/dev/null || true
done
cat > /usr/local/bin/limad-system-update <<'UPDATER'
#!/usr/bin/env bash
set -Eeuo pipefail
if command -v limad-save-cli >/dev/null 2>&1; then
  limad-save-cli pre-update || exit 1
fi
if command -v pkexec >/dev/null 2>&1; then
  exec pkexec sh -c 'apt-get update && DEBIAN_FRONTEND=noninteractive apt-get -y full-upgrade && apt-get -y autoremove'
fi
exec sudo sh -c 'apt-get update && DEBIAN_FRONTEND=noninteractive apt-get -y full-upgrade && apt-get -y autoremove'
UPDATER
chmod 0755 /usr/local/bin/limad-system-update
sed -i 's/readonly VERSION="[^"]*"/readonly VERSION="3.0.0-starter1"/' /usr/local/bin/limad-first-login-setup 2>/dev/null || true
sed -i 's/default-flatpaks-rc2-build5.done/default-flatpaks-3.0-starter1.done/' /usr/local/bin/limad-install-default-flatpaks 2>/dev/null || true
sed -i 's/LiMaD Apps" "Zen Browser ist auf Deutsch eingerichtet; LiMaD Mail, Zoom, YTMDesktop, LibreOffice, Bottles, LiMaD Klang und Bazaar sind installiert./LiMaD Apps" "Zen Browser, LiMaD Mail, Zoom, YTMDesktop, LibreOffice, LiMaD Klang und weitere Standardprogramme sind eingerichtet./' /usr/local/bin/limad-install-default-flatpaks 2>/dev/null || true

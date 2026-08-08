#!/usr/bin/env bash
set -Eeuo pipefail
source /opt/limad-build/versions.env

echo ":: Applying LiMaD OS 3.0 identity on Ubuntu"
install -d /usr/share/pixmaps /usr/share/limad/branding /etc/fastfetch
LIMAD_LOGO=/usr/share/icons/LiMaD/512x512/apps/de.limad.Logo.png
[[ -s "$LIMAD_LOGO" ]] || { echo "FATAL: LiMaD logo missing: $LIMAD_LOGO" >&2; exit 1; }
install -m 0644 "$LIMAD_LOGO" /usr/share/pixmaps/de.limad.Logo.png
install -m 0644 "$LIMAD_LOGO" /usr/share/limad/branding/LiMaD-System-Logo-512.png

cat > /usr/lib/os-release <<OSREL
PRETTY_NAME="LiMaD OS 3.0 (Ubuntu 26.04 LTS)"
NAME="LiMaD OS"
VERSION_ID="3.0"
VERSION="${LIMAD_OS_VERSION}"
VERSION_CODENAME=${UBUNTU_CODENAME}
ID=limad
ID_LIKE="ubuntu debian"
HOME_URL="https://github.com/"
SUPPORT_URL="https://github.com/"
BUG_REPORT_URL="https://github.com/"
LOGO=de.limad.Logo
DEFAULT_HOSTNAME=limad
UBUNTU_CODENAME=${UBUNTU_CODENAME}
OSREL
rm -f /etc/os-release
ln -s ../usr/lib/os-release /etc/os-release
printf 'LiMaD OS 3.0\n' > /etc/issue
printf 'LiMaD OS 3.0\n' > /etc/issue.net

cat > /etc/fastfetch/config.jsonc <<'JSON'
{
  "$schema": "https://github.com/fastfetch-cli/fastfetch/raw/dev/doc/json_schema.json",
  "logo": {"type":"file","source":"/usr/share/pixmaps/de.limad.Logo.png","height":12,"padding":{"right":2}},
  "display": {"separator":"  "},
  "modules": ["title","separator","os","host","kernel","uptime","packages","shell","display","de","wm","terminal","cpu","gpu","memory","disk","localip","break","colors"]
}
JSON

cat > /usr/share/limad/branding/identity.env <<EOF2
PRODUCT_NAME=LiMaD OS
PRODUCT_VERSION=${LIMAD_OS_VERSION}
BASE=Ubuntu ${UBUNTU_VERSION} LTS
BASE_CODENAME=${UBUNTU_CODENAME}
LOGO=/usr/share/pixmaps/de.limad.Logo.png
BOOT_SPLASH=/usr/share/plymouth/themes/limad/boot-splash.png
DEFAULT_WALLPAPER=/usr/share/backgrounds/limad/${LIMAD_DEFAULT_WALLPAPER}
EOF2

grep -q '^ID=limad$' /usr/lib/os-release || { echo 'FATAL: LiMaD ID not written' >&2; exit 1; }
grep -q '^ID_LIKE="ubuntu debian"$' /usr/lib/os-release || { echo 'FATAL: Ubuntu compatibility identity missing' >&2; exit 1; }
echo ":: LiMaD identity active"

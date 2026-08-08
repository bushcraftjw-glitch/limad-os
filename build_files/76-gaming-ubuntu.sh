#!/usr/bin/env bash
set -Eeuo pipefail
source /opt/limad-build/versions.env
[[ "${LIMAD_INSTALL_GAMING:-1}" == "1" ]] || exit 0

echo ':: Verifying LiMaD gaming stack'
required=(steam-installer steam-devices lutris gamemode gamescope libvulkan1 mesa-vulkan-drivers)
for pkg in "${required[@]}"; do
  dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q 'install ok installed' || {
    echo "FATAL: gaming package not installed: $pkg" >&2
    exit 1
  }
done
if dpkg --print-foreign-architectures | grep -qx i386; then
  for pkg in libvulkan1:i386 mesa-vulkan-drivers:i386 libgl1-mesa-dri:i386; do
    dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q 'install ok installed' || {
      echo "FATAL: 32-bit gaming runtime missing: $pkg" >&2
      exit 1
    }
  done
fi
install -d /usr/share/limad
cat > /usr/share/limad/gaming.env <<'ENV'
STEAM_NATIVE=1
STEAM_PLAY_PROTON=managed-by-steam
PROTONUP_QT=net.davidotek.pupgui2
LUTRIS_NATIVE=1
GAMEMODE_NATIVE=1
GAMESCOPE_NATIVE=1
DESKFLOW_FLATPAK=org.deskflow.deskflow
ENV
printf '%s\n' 'Steam/Steam Play (Proton), Lutris, GameMode, Gamescope and Vulkan runtimes installed.'

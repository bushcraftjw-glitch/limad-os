#!/usr/bin/env bash
set -Eeuo pipefail
export DEBIAN_FRONTEND=noninteractive
export LC_ALL=C
source /opt/limad-build/versions.env

cat > /usr/sbin/policy-rc.d <<'POLICY'
#!/bin/sh
exit 101
POLICY
chmod 0755 /usr/sbin/policy-rc.d
trap 'rm -f /usr/sbin/policy-rc.d' EXIT

# Ubuntu Desktop live media may leave file:/cdrom or cdrom: sources enabled.
# They work in the live session but are invalid inside the extracted build root.
# Remove only those media sources before the first apt-get update.
bash /opt/limad-build/10-apt-live-media-sources.sh /

# Ubuntu 26.04 uses deb822 sources on the desktop ISO. Ensure the components
# needed by Steam/Lutris are enabled before apt resolves the package list.
if [[ -f /etc/apt/sources.list.d/ubuntu.sources ]]; then
  sed -Ei 's/^Components:.*/Components: main restricted universe multiverse/' /etc/apt/sources.list.d/ubuntu.sources
fi
dpkg --add-architecture i386 || true
apt-get update
mapfile -t REQUIRED < <(grep -Ev '^\s*(#|$)' /opt/limad-build/packages-required.txt)
apt-get install -y --no-install-recommends "${REQUIRED[@]}"
while IFS= read -r pkg; do
  [[ -n "$pkg" ]] || continue
  apt-get install -y --no-install-recommends "$pkg" || echo "OPTIONAL nicht verfügbar: $pkg"
done < <(grep -Ev '^\s*(#|$)' /opt/limad-build/packages-optional.txt)
apt-get install -y --no-install-recommends wine32:i386 || true
locale-gen de_DE.UTF-8 en_US.UTF-8 || true
update-locale LANG=de_DE.UTF-8 LANGUAGE=de_DE:de || true

bash /opt/limad-build/20-mactahoe-gtk.sh
bash /opt/limad-build/30-whitesur-icons.sh
bash /opt/limad-build/40-limad-icons.sh
bash /opt/limad-build/45-logomenu-extension.sh
bash /opt/limad-build/50-gnome-defaults.sh
bash /opt/limad-build/52-branding.sh
bash /opt/limad-build/55-plymouth-ubuntu.sh
bash /opt/limad-build/60-anycubic-slicer.sh
bash /opt/limad-build/65-airdrop-compat.sh || echo 'WARNUNG: optionale AirDrop-Kompatibilität konnte nicht gebaut werden.'
bash /opt/limad-build/67-screen-share.sh || echo 'WARNUNG: experimentelles AirPlay-Modul konnte nicht gebaut werden.'
bash /opt/limad-build/70-ubuntu-integration.sh
# Safety comes after all system files are installed: no legacy installer CSS may survive.
bash /opt/limad-build/72-installer-safety.sh
bash /opt/limad-build/75-flatpak-system.sh
bash /opt/limad-build/76-gaming-ubuntu.sh
bash /opt/limad-build/80-wine-ubuntu.sh

if command -v gst-inspect-1.0 >/dev/null 2>&1; then
  for element in playbin uridecodebin audioconvert audioresample videoconvert videoscale gtk4paintablesink pipewiresrc h264parse; do
    gst-inspect-1.0 "$element" >/dev/null 2>&1 || { echo "FATAL: GStreamer-Element fehlt: $element" >&2; exit 1; }
  done
fi
if command -v glib-compile-schemas >/dev/null 2>&1; then glib-compile-schemas /usr/share/glib-2.0/schemas || true; fi
update-initramfs -u -k all || true
apt-get clean
rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

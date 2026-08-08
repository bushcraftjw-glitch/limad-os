#!/usr/bin/env bash
set -Eeuo pipefail
THEME=/usr/share/plymouth/themes/limad/limad.plymouth
test -f "$THEME"
mkdir -p /etc/plymouth
if [[ -f /etc/plymouth/plymouthd.conf ]]; then
  sed -i '/^Theme=/d' /etc/plymouth/plymouthd.conf
else
  printf '[Daemon]\n' > /etc/plymouth/plymouthd.conf
fi
printf 'Theme=limad\n' >> /etc/plymouth/plymouthd.conf
if command -v update-alternatives >/dev/null 2>&1; then
  update-alternatives --install /usr/share/plymouth/themes/default.plymouth default.plymouth "$THEME" 200 || true
  update-alternatives --set default.plymouth "$THEME" || true
fi
if command -v plymouth-set-default-theme >/dev/null 2>&1; then
  plymouth-set-default-theme limad || true
fi
printf 'LiMaD Plymouth theme configured for Ubuntu initramfs.\n'

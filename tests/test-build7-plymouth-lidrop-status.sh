#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
PLY=system_files/usr/local/sbin/limad-plymouth-initramfs
STATUS=system_files/usr/local/bin/limad-lidrop-status-ensure
EXT=system_files/usr/share/gnome-shell/extensions/lidrop@limad.local

grep -Fq 'plymouth-initramfs-280-rc2-build1.done' "$PLY"
grep -Fq "cat > /etc/plymouth/plymouthd.conf" "$PLY"
grep -Fq 'rpm-ostree kargs --append-if-missing=rhgb' "$PLY"
grep -Fq 'rpm-ostree kargs --append-if-missing=quiet' "$PLY"
grep -Fq 'rpm-ostree initramfs --enable --reboot' "$PLY"
if grep -Eq 'rm .*usr/share/plymouth|ln .*usr/share/plymouth|dracut --force' "$PLY"; then
  echo 'Unsafe Plymouth mutation found' >&2
  exit 1
fi

grep -Fq 'limad-lidrop-status-ensure' system_files/etc/xdg/autostart/limad-lidrop-status.desktop
grep -Fq 'gnome-extensions enable "$UUID"' "$STATUS"
grep -Fq 'notify-send -u critical' "$STATUS"
grep -Fq "Main.notifyError('LiDrop-Statussymbol konnte nicht geladen werden'" "$EXT/extension.js"
grep -Fq "Main.panel.addToStatusArea('lidrop'" "$EXT/extension.js"
python3 -m json.tool "$EXT/metadata.json" >/dev/null

echo 'Build 8 Plymouth and LiDrop status integration: PASS'
grep -Fq '"50"' "$EXT/metadata.json"
grep -Fq 'OUT OF DATE' "$STATUS"
grep -Fq 'run_rpm_ostree rpm-ostree initramfs --enable --reboot' "$PLY"
grep -Fq 'return Clutter.EVENT_PROPAGATE;' build_files/45-logomenu-extension.sh

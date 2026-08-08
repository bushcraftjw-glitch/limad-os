#!/usr/bin/env bash
set -Eeuo pipefail
[[ $EUID -eq 0 ]] || { echo 'Dieses Skript muss mit sudo/root laufen.' >&2; exit 1; }
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$REPO_ROOT/build_files/versions.env"
WORK="${1:-$REPO_ROOT/.work}"
OUT="${2:-$REPO_ROOT/out}"
CACHE="$WORK/cache"
PATCH="$WORK/iso-patch"
BASE_ROOT="$WORK/minimal-root"
STANDARD_UPPER="$WORK/minimal-standard-upper"
STANDARD_ORIGINAL="$WORK/minimal-standard-original-upper"
STANDARD_WORK="$WORK/minimal-standard-work"
ROOTFS="$WORK/rootfs"
STANDARD_MERGED="$WORK/minimal-standard-merged"
LIVE_UPPER="$WORK/minimal-standard-live-upper"
LIVE_WORK="$WORK/minimal-standard-live-work"
LIVE_ROOT="$WORK/live-rootfs"
STOCK_GDM="$WORK/stock-gdm"
BASE_ISO="$CACHE/$UBUNTU_ISO_NAME"
BASE_SQUASH="$WORK/minimal.squashfs"
STANDARD_SQUASH="$WORK/minimal.standard.original.squashfs"
LIVE_SQUASH="$WORK/minimal.standard.live.original.squashfs"
NEW_STANDARD_SQUASH="$WORK/minimal.standard.squashfs"
NEW_LIVE_SQUASH="$WORK/minimal.standard.live.squashfs"
OUT_ISO="$OUT/LiMaD-OS-${LIMAD_OS_VERSION}-amd64.iso"
mkdir -p "$CACHE" "$OUT"

for cmd in curl sha256sum xorriso unsquashfs mksquashfs rsync mount umount mountpoint chroot python3; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "FATAL: Host-Werkzeug fehlt: $cmd" >&2; exit 1; }
done

cleanup_runtime_mounts() {
  set +e
  for m in run sys proc dev/pts dev; do
    mountpoint -q "$ROOTFS/$m" 2>/dev/null && umount -lf "$ROOTFS/$m"
  done
  set -e
}
cleanup_mounts() {
  set +e
  mountpoint -q "$LIVE_ROOT" 2>/dev/null && umount -lf "$LIVE_ROOT"
  cleanup_runtime_mounts
  mountpoint -q "$ROOTFS" 2>/dev/null && umount -lf "$ROOTFS"
  set -e
}
trap cleanup_mounts EXIT

echo ":: Ubuntu ${UBUNTU_VERSION} LTS Basis laden"
if [[ ! -s "$BASE_ISO" ]]; then
  curl -fL --retry 4 --retry-delay 5 -o "$BASE_ISO.part" "$UBUNTU_ISO_URL"
  mv "$BASE_ISO.part" "$BASE_ISO"
fi
echo "$UBUNTU_ISO_SHA256  $BASE_ISO" | sha256sum -c -

rm -rf "$PATCH" "$BASE_ROOT" "$STANDARD_UPPER" "$STANDARD_ORIGINAL" "$STANDARD_WORK" "$ROOTFS" \
       "$STANDARD_MERGED" "$LIVE_UPPER" "$LIVE_WORK" "$LIVE_ROOT" "$STOCK_GDM" \
       "$BASE_SQUASH" "$STANDARD_SQUASH" "$LIVE_SQUASH" "$NEW_STANDARD_SQUASH" "$NEW_LIVE_SQUASH"
mkdir -p "$PATCH" "$BASE_ROOT" "$STANDARD_UPPER" "$STANDARD_ORIGINAL" "$STANDARD_WORK" "$ROOTFS" \
         "$STANDARD_MERGED" "$LIVE_UPPER" "$LIVE_WORK" "$LIVE_ROOT" "$STOCK_GDM"

echo ':: Ubuntu Layer extrahieren: minimal + standard + standard.live'
xorriso -osirrox on -indev "$BASE_ISO" -extract '/casper/minimal.squashfs' "$BASE_SQUASH" >/dev/null 2>&1
xorriso -osirrox on -indev "$BASE_ISO" -extract "/$UBUNTU_SQUASHFS" "$STANDARD_SQUASH" >/dev/null 2>&1
xorriso -osirrox on -indev "$BASE_ISO" -extract "/$UBUNTU_LIVE_SQUASHFS" "$LIVE_SQUASH" >/dev/null 2>&1
[[ -s "$BASE_SQUASH" && -s "$STANDARD_SQUASH" && -s "$LIVE_SQUASH" ]] || {
  echo 'FATAL: Ubuntu minimal/standard/live Layer konnten nicht aus der ISO extrahiert werden.' >&2; exit 1;
}

unsquashfs -d "$BASE_ROOT" "$BASE_SQUASH" >/dev/null
unsquashfs -d "$STANDARD_UPPER" "$STANDARD_SQUASH" >/dev/null
unsquashfs -d "$LIVE_UPPER" "$LIVE_SQUASH" >/dev/null
rm -f "$BASE_SQUASH" "$STANDARD_SQUASH" "$LIVE_SQUASH"
cp -a "$STANDARD_UPPER/." "$STANDARD_ORIGINAL/"

# The installed system is minimal + standard. Customize this layer so the
# installed machine receives every LiMaD change. The live-only layer is handled
# separately below and remains a real live/installer delta.
echo ':: Installations-RootFS aus minimal + standard aufbauen'
mount -t overlay overlay \
  -o "lowerdir=$BASE_ROOT,upperdir=$STANDARD_UPPER,workdir=$STANDARD_WORK" \
  "$ROOTFS"

[[ -x "$ROOTFS/bin/sh" || -x "$ROOTFS/usr/bin/sh" ]] || { echo 'FATAL: Standard-Overlay ergibt kein vollständiges Ubuntu RootFS.' >&2; exit 1; }
[[ -f "$ROOTFS/etc/os-release" ]] || { echo 'FATAL: /etc/os-release fehlt im Ubuntu Standard-Overlay.' >&2; exit 1; }

# Before branding the installed GDM, save the exact stock Ubuntu GDM resources.
# The live session deliberately keeps these stock resources: a broken custom
# login resource must never prevent the installer/live desktop from appearing.
echo ':: Ubuntu Live-GDM Sicherheitskopie sichern'
for candidate in \
  usr/share/gnome-shell/theme/Yaru/gnome-shell-theme.gresource \
  usr/share/gnome-shell/gnome-shell-theme.gresource \
  etc/alternatives/gdm3-theme.gresource; do
  # In the live view LIVE_UPPER wins over the original standard root. Read the
  # effective stock file without nesting overlay mounts.
  source_path=''
  if [[ -e "$LIVE_UPPER/$candidate" || -L "$LIVE_UPPER/$candidate" ]]; then
    source_path="$LIVE_UPPER/$candidate"
  elif [[ -e "$ROOTFS/$candidate" || -L "$ROOTFS/$candidate" ]]; then
    source_path="$ROOTFS/$candidate"
  fi
  if [[ -n "$source_path" ]]; then
    mkdir -p "$STOCK_GDM/$(dirname "$candidate")"
    cp -a "$source_path" "$STOCK_GDM/$candidate"
  fi
done
find "$STOCK_GDM" \( -type f -o -type l \) -print -quit | grep -q . || { echo 'FATAL: keine Ubuntu GDM-Ressource im Live-System gefunden.' >&2; exit 1; }

echo ':: LiMaD Systemdateien und Buildwerkzeuge einspielen'
rsync -aHAX "$REPO_ROOT/system_files/" "$ROOTFS/"
rm -rf "$ROOTFS/opt/limad-build"
mkdir -p "$ROOTFS/opt/limad-build"
rsync -a "$REPO_ROOT/build_files/" "$ROOTFS/opt/limad-build/"

RESOLV_KIND=missing
RESOLV_VALUE=''
if [[ -L "$ROOTFS/etc/resolv.conf" ]]; then
  RESOLV_KIND=symlink
  RESOLV_VALUE="$(readlink "$ROOTFS/etc/resolv.conf")"
elif [[ -f "$ROOTFS/etc/resolv.conf" ]]; then
  RESOLV_KIND=file
  cp -a "$ROOTFS/etc/resolv.conf" "$WORK/resolv.conf.saved"
fi
rm -f "$ROOTFS/etc/resolv.conf"
cp -L /etc/resolv.conf "$ROOTFS/etc/resolv.conf"

for d in dev dev/pts proc sys run; do mkdir -p "$ROOTFS/$d"; done
mount --bind /dev "$ROOTFS/dev"
mount --bind /dev/pts "$ROOTFS/dev/pts"
mount -t proc proc "$ROOTFS/proc"
mount -t sysfs sys "$ROOTFS/sys"
mount --bind /run "$ROOTFS/run"

echo ':: Ubuntu Installations-RootFS zu LiMaD OS 3.0 anpassen'
chroot "$ROOTFS" /usr/bin/env HOME=/root PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin bash /opt/limad-build/customize-rootfs.sh

rm -f "$ROOTFS/etc/resolv.conf"
case "$RESOLV_KIND" in
  symlink) ln -s "$RESOLV_VALUE" "$ROOTFS/etc/resolv.conf" ;;
  file) cp -a "$WORK/resolv.conf.saved" "$ROOTFS/etc/resolv.conf" ;;
esac

mkdir -p "$OUT/updates"
echo ':: Eigenständige LiMaD Update-ZIPs erzeugen'
bash "$REPO_ROOT/tools/build-all-updates.sh" "$ROOTFS" "$OUT/updates"

rm -rf "$ROOTFS/opt/limad-build"
rm -f "$ROOTFS/usr/sbin/policy-rc.d"
find "$ROOTFS/usr" "$ROOTFS/opt" "$ROOTFS/var" -xdev -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
cleanup_runtime_mounts

STANDARD_BASENAME="$(basename "$UBUNTU_SQUASHFS" .squashfs)"
LIVE_BASENAME="$(basename "$UBUNTU_LIVE_SQUASHFS" .squashfs)"
STANDARD_MANIFEST="$PATCH/${STANDARD_BASENAME}.manifest"
STANDARD_MANIFEST_FULL="$PATCH/${STANDARD_BASENAME}.manifest.full"
STANDARD_SIZE="$PATCH/${STANDARD_BASENAME}.size"
chroot "$ROOTFS" dpkg-query -W --showformat='${Package} ${Version}\n' > "$STANDARD_MANIFEST"
cp "$STANDARD_MANIFEST" "$STANDARD_MANIFEST_FULL"
printf '%s' "$(du -sx --block-size=1 "$ROOTFS" | cut -f1)" > "$STANDARD_SIZE"

# Materialize the customized installed view once. This avoids a fragile nested
# overlay (overlay-on-overlay) when constructing the live/installer layer.
echo ':: Angepasstes Standard-RootFS für Live-Layer materialisieren'
rsync -aHAX --numeric-ids --delete "$ROOTFS/" "$STANDARD_MERGED/"
umount "$ROOTFS"

# Reconcile files that LiMaD/apt changed in the standard layer but that the
# Ubuntu live layer would otherwise shadow with an older copy. This prevents a
# mixed GDM/systemd/GNOME userspace at live boot while preserving live-only
# installer files and configuration.
echo ':: Ubuntu Live-Layer gegen den angepassten Standard-Layer konsistent machen'
python3 "$REPO_ROOT/tools/sync-live-shadow.py" "$STANDARD_ORIGINAL" "$STANDARD_UPPER" "$LIVE_UPPER"

# Safety rule: the installed system may use the LiMaD-branded GDM resource, but
# the live installer/session uses Ubuntu's known-good stock GDM resource.
while IFS= read -r -d '' src; do
  rel="${src#$STOCK_GDM/}"
  mkdir -p "$LIVE_UPPER/$(dirname "$rel")"
  rm -rf "$LIVE_UPPER/$rel"
  cp -a "$src" "$LIVE_UPPER/$rel"
done < <(find "$STOCK_GDM" \( -type f -o -type l \) -print0)

mount -t overlay overlay -o "lowerdir=$STANDARD_MERGED,upperdir=$LIVE_UPPER,workdir=$LIVE_WORK" "$LIVE_ROOT"

echo ':: Live-/Installer-RootFS prüfen'
[[ -e "$LIVE_ROOT/usr/lib/systemd/user/ubuntu-desktop-installer.service" || -e "$LIVE_ROOT/etc/systemd/user/graphical-session.target.wants/ubuntu-desktop-installer.service" ]] \
  || { echo 'FATAL: Ubuntu Desktop Installer Live-Service fehlt.' >&2; exit 1; }
[[ -d "$LIVE_ROOT/usr/share/limad" ]] || { echo 'FATAL: LiMaD Dateien fehlen im Live-RootFS.' >&2; exit 1; }
[[ -x "$LIVE_ROOT/usr/bin/gnome-shell" ]] || { echo 'FATAL: GNOME Shell fehlt im Live-RootFS.' >&2; exit 1; }
[[ -x "$LIVE_ROOT/usr/sbin/gdm3" || -x "$LIVE_ROOT/usr/sbin/gdm" ]] || { echo 'FATAL: GDM fehlt im Live-RootFS.' >&2; exit 1; }

# Verify both installed branded and live stock GResources are parseable.
for root in "$STANDARD_MERGED" "$LIVE_ROOT"; do
  checked=0
  for res in \
    usr/share/gnome-shell/theme/Yaru/gnome-shell-theme.gresource \
    usr/share/gnome-shell/gnome-shell-theme.gresource; do
    if [[ -f "$root/$res" ]]; then
      chroot "$root" gresource list "/$res" >/dev/null 2>&1 || { echo "FATAL: ungültige GNOME/GDM GResource: $root/$res" >&2; exit 1; }
      checked=1
    fi
  done
  (( checked == 1 )) || { echo "FATAL: keine prüfbare GNOME/GDM GResource in $root" >&2; exit 1; }
done

# Confirm the live copy is really the stock resource saved before LiMaD GDM branding.
while IFS= read -r -d '' src; do
  rel="${src#$STOCK_GDM/}"
  if [[ -f "$src" && -f "$LIVE_ROOT/$rel" ]]; then
    [[ "$(sha256sum "$src" | cut -d' ' -f1)" == "$(sha256sum "$LIVE_ROOT/$rel" | cut -d' ' -f1)" ]] \
      || { echo "FATAL: Live-GDM Ressource wurde nach Stock-Restore verändert: /$rel" >&2; exit 1; }
  fi
done < <(find "$STOCK_GDM" -type f -print0)

echo "   GNOME Shell: $(chroot "$LIVE_ROOT" /usr/bin/gnome-shell --version 2>/dev/null || true)"
echo "   Live-Installer-Service: vorhanden"
echo "   Live-GDM: Ubuntu Stock-Ressource geschützt"

LIVE_MANIFEST="$PATCH/${LIVE_BASENAME}.manifest"
LIVE_MANIFEST_FULL="$PATCH/${LIVE_BASENAME}.manifest.full"
LIVE_SIZE="$PATCH/${LIVE_BASENAME}.size"
chroot "$LIVE_ROOT" dpkg-query -W --showformat='${Package} ${Version}\n' > "$LIVE_MANIFEST"
cp "$LIVE_MANIFEST" "$LIVE_MANIFEST_FULL"
printf '%s' "$(du -sx --block-size=1 "$LIVE_ROOT" | cut -f1)" > "$LIVE_SIZE"

cleanup_mounts

echo ':: Angepassten Ubuntu Standard- und Live-Layer schreiben'
mksquashfs "$STANDARD_UPPER" "$NEW_STANDARD_SQUASH" -comp xz -b 1M -noappend -no-progress
mksquashfs "$LIVE_UPPER" "$NEW_LIVE_SQUASH" -comp xz -b 1M -noappend -no-progress

rm -rf "$BASE_ROOT" "$STANDARD_UPPER" "$STANDARD_ORIGINAL" "$STANDARD_WORK" "$ROOTFS" \
       "$STANDARD_MERGED" "$LIVE_UPPER" "$LIVE_WORK" "$LIVE_ROOT" "$STOCK_GDM"

printf 'LiMaD OS %s – Ubuntu %s LTS\n' "$LIMAD_OS_VERSION" "$UBUNTU_VERSION" > "$PATCH/disk-info"
: > "$PATCH/md5sum.txt"

# Keep the Ubuntu boot mechanics intact, but make the menu visible and provide
# a guaranteed Safe Graphics entry for Macs/older GPUs.
for iso_path in /boot/grub/grub.cfg /boot/grub/loopback.cfg; do
  local_name="$PATCH/$(basename "$iso_path")"
  if xorriso -osirrox on -indev "$BASE_ISO" -extract "$iso_path" "$local_name" >/dev/null 2>&1; then
    python3 "$REPO_ROOT/tools/patch-ubuntu-grub.py" "$local_name"
  else
    rm -f "$local_name"
  fi
done
[[ -s "$PATCH/grub.cfg" ]] || { echo 'FATAL: ISO GRUB-Konfiguration konnte nicht gepatcht werden.' >&2; exit 1; }
grep -q 'LiMaD OS - Safe Graphics' "$PATCH/grub.cfg" || { echo 'FATAL: Safe Graphics fehlt in GRUB.' >&2; exit 1; }
grep -q 'nomodeset' "$PATCH/grub.cfg" || { echo 'FATAL: Safe Graphics besitzt kein nomodeset.' >&2; exit 1; }
grep -q 'set timeout=10' "$PATCH/grub.cfg" || { echo 'FATAL: sichtbarer GRUB-Timeout fehlt.' >&2; exit 1; }

rm -f "$OUT_ISO"
echo ':: Bootfähige Hybrid-ISO aus der offiziellen Ubuntu-ISO ableiten'
XORRISO=(xorriso -indev "$BASE_ISO" -outdev "$OUT_ISO" -overwrite nondir)
XORRISO+=( -map "$NEW_STANDARD_SQUASH" "/$UBUNTU_SQUASHFS" )
XORRISO+=( -map "$NEW_LIVE_SQUASH" "/$UBUNTU_LIVE_SQUASHFS" )
XORRISO+=( -map "$STANDARD_MANIFEST" "/casper/${STANDARD_BASENAME}.manifest" )
XORRISO+=( -map "$STANDARD_MANIFEST_FULL" "/casper/${STANDARD_BASENAME}.manifest.full" )
XORRISO+=( -map "$STANDARD_SIZE" "/casper/${STANDARD_BASENAME}.size" )
XORRISO+=( -map "$LIVE_MANIFEST" "/casper/${LIVE_BASENAME}.manifest" )
XORRISO+=( -map "$LIVE_MANIFEST_FULL" "/casper/${LIVE_BASENAME}.manifest.full" )
XORRISO+=( -map "$LIVE_SIZE" "/casper/${LIVE_BASENAME}.size" )
XORRISO+=( -map "$PATCH/disk-info" '/.disk/info' )
XORRISO+=( -map "$PATCH/md5sum.txt" '/md5sum.txt' )
[[ -s "$PATCH/grub.cfg" ]] && XORRISO+=( -map "$PATCH/grub.cfg" '/boot/grub/grub.cfg' )
[[ -s "$PATCH/loopback.cfg" ]] && XORRISO+=( -map "$PATCH/loopback.cfg" '/boot/grub/loopback.cfg' )
XORRISO+=( -boot_image any replay -volid 'LiMaD_OS_3_0' )
"${XORRISO[@]}" >/dev/null

# Final-media checks: verify the ISO contains both modified layers and the
# visible normal/safe boot menu. This catches packaging regressions before upload.
FINAL_GRUB="$WORK/final-grub.cfg"
xorriso -osirrox on -indev "$OUT_ISO" -extract '/boot/grub/grub.cfg' "$FINAL_GRUB" >/dev/null 2>&1
for needle in 'LiMaD OS starten oder installieren' 'LiMaD OS - Safe Graphics' 'set timeout=10' 'set timeout_style=menu' 'nomodeset' 'layerfs-path=minimal.standard.live.squashfs'; do
  grep -q "$needle" "$FINAL_GRUB" || { echo "FATAL: finales ISO GRUB fehlt: $needle" >&2; exit 1; }
done
for path in "/$UBUNTU_SQUASHFS" "/$UBUNTU_LIVE_SQUASHFS"; do
  xorriso -indev "$OUT_ISO" -find "$path" -type f -exec echo -- 2>/dev/null | grep -Fq "$path" \
    || { echo "FATAL: finales ISO enthält Layer nicht: $path" >&2; exit 1; }
done
rm -f "$FINAL_GRUB"

sha256sum "$OUT_ISO" > "$OUT_ISO.sha256"
cat > "$OUT/BUILD-INFO.txt" <<INFO
LiMaD OS: ${LIMAD_OS_VERSION}
Build: ${LIMAD_BUILD_REVISION}
Basis: Ubuntu ${UBUNTU_VERSION} LTS (${UBUNTU_CODENAME})
Basis-ISO: ${UBUNTU_ISO_NAME}
Basis-SHA256: ${UBUNTU_ISO_SHA256}
Installations-Layer: ${UBUNTU_SQUASHFS}
Live-/Installer-Layer: ${UBUNTU_LIVE_SQUASHFS}
Live-Sicherheit: Ubuntu Stock-GDM-Ressource; LiMaD-GDM-Branding bleibt im installierten System.
Bootmenü: 10 Sekunden sichtbar; normaler Start + Safe Graphics (nomodeset).
ISO: $(basename "$OUT_ISO")
Status: starter1; GitHub-Build kann technisch erfolgreich sein, Hardwareinstallation bleibt bis zum realen Test unbestätigt.
INFO

echo ":: Fertig: $OUT_ISO"
echo ":: Updates: $OUT/updates"

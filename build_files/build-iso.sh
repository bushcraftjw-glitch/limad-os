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
OVERLAY_WORK="$WORK/minimal-standard-work"
ROOTFS="$WORK/rootfs"
BASE_ISO="$CACHE/$UBUNTU_ISO_NAME"
BASE_SQUASH="$WORK/minimal.squashfs"
STANDARD_SQUASH="$WORK/minimal.standard.original.squashfs"
NEW_SQUASH="$WORK/minimal.standard.squashfs"
OUT_ISO="$OUT/LiMaD-OS-${LIMAD_OS_VERSION}-amd64.iso"
mkdir -p "$CACHE" "$OUT"

for cmd in curl sha256sum xorriso unsquashfs mksquashfs rsync mount umount mountpoint chroot python3; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "FATAL: Host-Werkzeug fehlt: $cmd" >&2; exit 1; }
done

cleanup_mounts() {
  set +e
  for m in run sys proc dev/pts dev; do
    [[ -n "${ROOTFS:-}" ]] && mountpoint -q "$ROOTFS/$m" && umount -lf "$ROOTFS/$m"
  done
  [[ -n "${ROOTFS:-}" ]] && mountpoint -q "$ROOTFS" && umount -lf "$ROOTFS"
  set -e
}
trap cleanup_mounts EXIT

echo ":: Ubuntu ${UBUNTU_VERSION} LTS Basis laden"
if [[ ! -s "$BASE_ISO" ]]; then
  curl -fL --retry 4 --retry-delay 5 -o "$BASE_ISO.part" "$UBUNTU_ISO_URL"
  mv "$BASE_ISO.part" "$BASE_ISO"
fi
echo "$UBUNTU_ISO_SHA256  $BASE_ISO" | sha256sum -c -

rm -rf "$PATCH" "$BASE_ROOT" "$STANDARD_UPPER" "$OVERLAY_WORK" "$ROOTFS" "$BASE_SQUASH" "$STANDARD_SQUASH" "$NEW_SQUASH"
mkdir -p "$PATCH" "$BASE_ROOT" "$STANDARD_UPPER" "$OVERLAY_WORK" "$ROOTFS"

echo ':: Ubuntu Layer extrahieren: minimal.squashfs + minimal.standard.squashfs'
xorriso -osirrox on -indev "$BASE_ISO" -extract '/casper/minimal.squashfs' "$BASE_SQUASH" >/dev/null 2>&1
xorriso -osirrox on -indev "$BASE_ISO" -extract "/$UBUNTU_SQUASHFS" "$STANDARD_SQUASH" >/dev/null 2>&1
[[ -s "$BASE_SQUASH" && -s "$STANDARD_SQUASH" ]] || { echo 'FATAL: Ubuntu Layer konnten nicht aus der ISO extrahiert werden.' >&2; exit 1; }

unsquashfs -d "$BASE_ROOT" "$BASE_SQUASH" >/dev/null
unsquashfs -d "$STANDARD_UPPER" "$STANDARD_SQUASH" >/dev/null
rm -f "$BASE_SQUASH" "$STANDARD_SQUASH"

# Ubuntu Desktop uses layered fsimages. Build a complete writable target from
# minimal + minimal.standard while keeping every change in the standard upper
# layer. The unchanged language/live/enhanced-secureboot layers remain above it.
echo ':: Schreibbares Ubuntu-Standard-System als Overlay aufbauen'
mount -t overlay overlay \
  -o "lowerdir=$BASE_ROOT,upperdir=$STANDARD_UPPER,workdir=$OVERLAY_WORK" \
  "$ROOTFS"

[[ -x "$ROOTFS/bin/sh" || -x "$ROOTFS/usr/bin/sh" ]] || { echo 'FATAL: Layer-Overlay ergibt kein vollständiges Ubuntu RootFS.' >&2; exit 1; }
[[ -f "$ROOTFS/etc/os-release" ]] || { echo 'FATAL: /etc/os-release fehlt im Ubuntu Layer-Overlay.' >&2; exit 1; }

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

echo ':: Ubuntu RootFS zu LiMaD OS 3.0 anpassen'
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

SQUASH_BASENAME="$(basename "$UBUNTU_SQUASHFS" .squashfs)"
MANIFEST="$PATCH/${SQUASH_BASENAME}.manifest"
MANIFEST_FULL="$PATCH/${SQUASH_BASENAME}.manifest.full"
SIZE_FILE="$PATCH/${SQUASH_BASENAME}.size"
chroot "$ROOTFS" dpkg-query -W --showformat='${Package} ${Version}\n' > "$MANIFEST"
cp "$MANIFEST" "$MANIFEST_FULL"
printf '%s' "$(du -sx --block-size=1 "$ROOTFS" | cut -f1)" > "$SIZE_FILE"

cleanup_mounts

echo ':: Angepassten Ubuntu-Standard-Layer schreiben'
# STANDARD_UPPER contains the original standard delta plus every LiMaD change
# made through the overlay, including overlay whiteouts where needed.
mksquashfs "$STANDARD_UPPER" "$NEW_SQUASH" -comp xz -b 1M -noappend -no-progress

# Large unpacked trees are not needed for final ISO rewriting.
rm -rf "$BASE_ROOT" "$STANDARD_UPPER" "$OVERLAY_WORK" "$ROOTFS"

printf 'LiMaD OS %s – Ubuntu %s LTS\n' "$LIMAD_OS_VERSION" "$UBUNTU_VERSION" > "$PATCH/disk-info"
: > "$PATCH/md5sum.txt"

# Conservatively brand only GRUB text. Installer widget CSS remains untouched.
for iso_path in /boot/grub/grub.cfg /boot/grub/loopback.cfg; do
  local_name="$PATCH/$(basename "$iso_path")"
  if xorriso -osirrox on -indev "$BASE_ISO" -extract "$iso_path" "$local_name" >/dev/null 2>&1; then
    sed -i \
      -e 's/Try or Install Ubuntu/LiMaD OS starten oder installieren/g' \
      -e 's/Install Ubuntu/LiMaD OS installieren/g' \
      "$local_name"
  else
    rm -f "$local_name"
  fi
done

rm -f "$OUT_ISO"
echo ':: Bootfähige Hybrid-ISO aus der offiziellen Ubuntu-ISO ableiten'
XORRISO=(xorriso -indev "$BASE_ISO" -outdev "$OUT_ISO" -overwrite nondir)
XORRISO+=( -map "$NEW_SQUASH" "/$UBUNTU_SQUASHFS" )
XORRISO+=( -map "$MANIFEST" "/casper/${SQUASH_BASENAME}.manifest" )
XORRISO+=( -map "$MANIFEST_FULL" "/casper/${SQUASH_BASENAME}.manifest.full" )
XORRISO+=( -map "$SIZE_FILE" "/casper/${SQUASH_BASENAME}.size" )
XORRISO+=( -map "$PATCH/disk-info" '/.disk/info' )
XORRISO+=( -map "$PATCH/md5sum.txt" '/md5sum.txt' )
[[ -s "$PATCH/grub.cfg" ]] && XORRISO+=( -map "$PATCH/grub.cfg" '/boot/grub/grub.cfg' )
[[ -s "$PATCH/loopback.cfg" ]] && XORRISO+=( -map "$PATCH/loopback.cfg" '/boot/grub/loopback.cfg' )
XORRISO+=( -boot_image any replay -volid 'LiMaD_OS_3_0' )
"${XORRISO[@]}" >/dev/null

sha256sum "$OUT_ISO" > "$OUT_ISO.sha256"
cat > "$OUT/BUILD-INFO.txt" <<INFO
LiMaD OS: ${LIMAD_OS_VERSION}
Build: ${LIMAD_BUILD_REVISION}
Basis: Ubuntu ${UBUNTU_VERSION} LTS (${UBUNTU_CODENAME})
Basis-ISO: ${UBUNTU_ISO_NAME}
Basis-SHA256: ${UBUNTU_ISO_SHA256}
Geänderter Installations-Layer: ${UBUNTU_SQUASHFS}
Layer-Prinzip: minimal.squashfs + modifizierter minimal.standard.squashfs; Ubuntu Sprach-, Live- und Enhanced-Secure-Boot-Layer bleiben unverändert darüber erhalten.
ISO: $(basename "$OUT_ISO")
Status: starter1; vollständiger GitHub-ISO-Build und Hardwareinstallation müssen vor RC-Status erfolgreich verifiziert werden.
INFO

echo ":: Fertig: $OUT_ISO"
echo ":: Updates: $OUT/updates"

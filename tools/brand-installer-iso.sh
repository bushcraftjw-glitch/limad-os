#!/usr/bin/env bash
set -Eeuo pipefail
[[ $# -eq 2 ]] || { echo "Usage: $0 INPUT.iso OUTPUT.iso" >&2; exit 2; }
INPUT="$(readlink -f "$1")"
OUTPUT="$(readlink -m "$2")"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/build_files/versions.env"
source "$ROOT/tools/lib-iso-branding.sh"
readonly REWRITE_TOOL="$ROOT/tools/rewrite-boot-config.py"
readonly TREEINFO_TOOL="$ROOT/tools/update-treeinfo-checksums.py"
readonly AUDIT_TOOL="$ROOT/tools/audit-boot-config.py"
readonly INSTALLER_THEME_TOOL="$ROOT/tools/build-installer-theme.py"
readonly VOLID="$(limad_iso_volume_id "$LIMAD_OS_VERSION")"

for cmd in xorriso mksquashfs unsquashfs python3 mcopy implantisomd5 sha256sum cmp; do
  command -v "$cmd" >/dev/null || { echo "FATAL: $cmd missing" >&2; exit 1; }
done
[[ "${EUID}" -eq 0 ]] || { echo "FATAL: run this ISO preservation step as root so SquashFS ownership and xattrs remain intact" >&2; exit 1; }
[[ -s "$INPUT" ]] || { echo "FATAL: input ISO missing: $INPUT" >&2; exit 1; }
[[ -x "$REWRITE_TOOL" ]] || { echo "FATAL: boot configuration rewriter missing" >&2; exit 1; }
[[ -x "$AUDIT_TOOL" ]] || { echo "FATAL: boot configuration auditor missing" >&2; exit 1; }
mkdir -p "$(dirname "$OUTPUT")"

read_volume_id() {
  xorriso -indev "$1" -pvd_info 2>&1 |
    sed -nE "s/.*Volume id[[:space:]]*:[[:space:]]*'([^']*)'.*/\1/p" |
    head -n1
}

INPUT_VOLID="$(read_volume_id "$INPUT")"
[[ "$INPUT_VOLID" == "$VOLID" ]] || {
  echo "FATAL: bootc-image-builder created ISO label '$INPUT_VOLID', expected '$VOLID'." >&2
  echo "The native [customizations.iso] volume_id setting was not applied; branding is aborted before creating inconsistent boot media." >&2
  exit 1
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
PRODUCT="$TMP/product"
LOGO="$ROOT/system_files/usr/share/limad/branding/LiMaD-System-Logo-512.png"
WALLPAPER="$ROOT/system_files/usr/share/backgrounds/limad/LiMaD-Wallpaper-03-Wellen-Emblem-4K.png"
[[ -s "$LOGO" ]] || { echo "FATAL: installer branding logo missing" >&2; exit 1; }
[[ -s "$WALLPAPER" ]] || { echo "FATAL: installer branding wallpaper missing" >&2; exit 1; }
[[ -x "$INSTALLER_THEME_TOOL" ]] || { echo "FATAL: installer theme generator missing" >&2; exit 1; }

iso_file_exists() {
  local iso_path="$1" output
  output="$(xorriso -indev "$INPUT" -find "$iso_path" -type f -exec echo -- 2>/dev/null || true)"
  printf '%s\n' "$output" |
    sed -nE \
      -e "s/^[[:space:]]*'([^']+)'[[:space:]]*$/\1/p" \
      -e 's/^[[:space:]]*"([^"]+)"[[:space:]]*$/\1/p' \
      -e 's|^[[:space:]]*(/[^[:space:]]+)[[:space:]]*$|\1|p' |
    grep -Fxq "$iso_path"
}

require_iso_file() {
  local iso_path="$1"
  iso_file_exists "$iso_path" || {
    echo "FATAL: required installer payload missing before branding: $iso_path" >&2
    exit 1
  }
}

for required_path in /images/install.img /images/efiboot.img /images/pxeboot/vmlinuz /images/pxeboot/initrd.img; do
  require_iso_file "$required_path"
done

rm -rf "$PRODUCT"
mkdir -p "$PRODUCT"
PRODUCT_MODE="created"
if iso_file_exists /images/product.img; then
  ORIGINAL_PRODUCT="$TMP/original-product.img"
  xorriso -osirrox on -indev "$INPUT" -extract /images/product.img "$ORIGINAL_PRODUCT" >/dev/null 2>&1 || {
    echo "FATAL: existing /images/product.img cannot be extracted" >&2
    exit 1
  }
  unsquashfs -d "$PRODUCT" "$ORIGINAL_PRODUCT" >/dev/null
  PRODUCT_MODE="preserved"
fi

INSTALLER_THEME="$TMP/installer-theme"
python3 "$INSTALLER_THEME_TOOL" "$LOGO" "$WALLPAPER" "$INSTALLER_THEME"
for asset in logo.png product-logo.png sidebar-logo.png sidebar-bg.png topbar-bg.png branding.css limad-anaconda.css anaconda-gtk.css; do
  [[ -s "$INSTALLER_THEME/$asset" ]] || { echo "FATAL: generated installer asset missing: $asset" >&2; exit 1; }
done

for id in limad bazzite fedora; do
  dir="$PRODUCT/usr/share/cockpit/branding/$id"
  mkdir -p "$dir"
  install -m 0644 "$INSTALLER_THEME"/{logo.png,product-logo.png,sidebar-logo.png,sidebar-bg.png,topbar-bg.png,branding.css} "$dir/"
done

mkdir -p "$PRODUCT/usr/share/cockpit/static" "$PRODUCT/usr/share/anaconda/pixmaps" "$PRODUCT/etc/anaconda/conf.d"
install -m 0644 "$INSTALLER_THEME"/{logo.png,product-logo.png,sidebar-logo.png,sidebar-bg.png,topbar-bg.png,branding.css} "$PRODUCT/usr/share/cockpit/static/"
install -m 0644 "$INSTALLER_THEME"/{product-logo.png,sidebar-logo.png,sidebar-bg.png,topbar-bg.png,limad-anaconda.css} "$PRODUCT/usr/share/anaconda/pixmaps/"
# Keep Anaconda's complete base stylesheet intact.  Older GTK installers load a
# product-specific stylesheet named after the detected product/profile, so ship
# the same narrow overlay under every identity this Bazzite/Fedora ISO can
# expose.  Current Anaconda WebUI uses Cockpit branding.css above.
for css_name in limad.css limad-os.css bazzite.css fedora.css; do
  install -m 0644 "$INSTALLER_THEME/limad-anaconda.css" \
    "$PRODUCT/usr/share/anaconda/pixmaps/$css_name"
done

cat > "$PRODUCT/.buildstamp" <<EOF_STAMP
[Main]
Product=LiMaD OS
Version=${LIMAD_OS_VERSION}
BugURL=https://github.com/bushcraftjw-glitch/limad-os
IsFinal=True
UUID=LiMaD-OS-${LIMAD_OS_VERSION}
[Compose]
Lorax=LiMaD
EOF_STAMP
cat > "$PRODUCT/etc/anaconda/conf.d/99-limad.conf" <<EOF_ANACONDA
[Product]
product_name = LiMaD OS
product_version = ${LIMAD_OS_VERSION}
[User Interface]
webui_web_engine = firefox
EOF_ANACONDA

cat > "$PRODUCT/usr/share/anaconda/pixmaps/limad-branding-manifest.txt" <<'EOF_MANIFEST'
LiMaD OS installer branding
WebUI: /usr/share/cockpit/branding/{limad,bazzite,fedora}/branding.css
GTK overlays: /usr/share/anaconda/pixmaps/{limad,limad-os,bazzite,fedora}.css
Logo: /usr/share/anaconda/pixmaps/sidebar-logo.png
EOF_MANIFEST

mksquashfs "$PRODUCT" "$TMP/product.img" -noappend -comp xz -all-root -quiet
# Audit the exact product.img that will be inserted into the ISO.  This catches
# missing paths before xorriso touches the bootable media.
PRODUCT_LIST="$TMP/product-list.txt"
unsquashfs -ll "$TMP/product.img" > "$PRODUCT_LIST"
for required in \
  usr/share/cockpit/branding/limad/branding.css \
  usr/share/cockpit/branding/bazzite/branding.css \
  usr/share/cockpit/branding/fedora/branding.css \
  usr/share/anaconda/pixmaps/limad-anaconda.css \
  usr/share/anaconda/pixmaps/limad.css \
  usr/share/anaconda/pixmaps/limad-os.css \
  usr/share/anaconda/pixmaps/bazzite.css \
  usr/share/anaconda/pixmaps/fedora.css \
  usr/share/anaconda/pixmaps/sidebar-logo.png \
  etc/anaconda/conf.d/99-limad.conf; do
  grep -Fq "$required" "$PRODUCT_LIST" || {
    echo "FATAL: branded product.img lacks $required" >&2
    exit 1
  }
done

map_args=(-map "$TMP/product.img" /images/product.img)

mapfile -t CFGS < <(
  xorriso -indev "$INPUT" -find / -type f \( -name '*.cfg' -o -name '*.conf' \) -exec echo -- 2>/dev/null |
    sed -nE       -e "s/^[[:space:]]*'([^']+)'[[:space:]]*$/\1/p"       -e 's/^[[:space:]]*"([^"]+)"[[:space:]]*$/\1/p'       -e 's|^[[:space:]]*(/[^[:space:]]+)[[:space:]]*$|\1|p' |
    sort -u
)

for candidate in \
  /EFI/BOOT/grub.cfg \
  /boot/grub2/grub.cfg \
  /isolinux/isolinux.cfg \
  /isolinux/grub.conf \
  /syslinux/syslinux.cfg
do
  already_present=0
  for existing in "${CFGS[@]}"; do
    [[ "$existing" == "$candidate" ]] && { already_present=1; break; }
  done
  if ((already_present == 0)) && iso_file_exists "$candidate"; then
    CFGS+=("$candidate")
  fi
done

for iso_path in "${CFGS[@]}"; do
  case "$iso_path" in
    *grub*.cfg|*isolinux*.cfg|*syslinux*.cfg)
      local_path="$TMP/cfg${iso_path}"
      mkdir -p "$(dirname "$local_path")"
      xorriso -osirrox on -indev "$INPUT" -extract "$iso_path" "$local_path" >/dev/null 2>&1 || continue
      python3 "$REWRITE_TOOL" "$local_path" "$LIMAD_OS_VERSION" "$VOLID"
      python3 "$AUDIT_TOOL" "$local_path" "$VOLID" "$iso_path in ISO tree" >/dev/null
      map_args+=(-map "$local_path" "$iso_path")
      ;;
  esac
done

ESP_IMG="$TMP/efiboot.img"
xorriso -osirrox on -indev "$INPUT" -extract /images/efiboot.img "$ESP_IMG" >/dev/null 2>&1

esp_extract_required() {
  local source="$1" destination="$2"
  rm -f "$destination"
  mcopy -n -i "$ESP_IMG" "::$source" "$destination" >/dev/null 2>&1
  [[ -s "$destination" ]]
}

ESP_BOOT_PATH="EFI/BOOT/BOOTX64.EFI"
esp_extract_required "$ESP_BOOT_PATH" "$TMP/BOOTX64.before" || {
  echo "FATAL: EFI/BOOT/BOOTX64.EFI missing from input efiboot.img" >&2
  exit 1
}
ESP_GRUB_PATH=""
for candidate in EFI/BOOT/grubx64.efi EFI/BOOT/GRUBX64.EFI efi/boot/grubx64.efi; do
  if esp_extract_required "$candidate" "$TMP/grubx64.before"; then
    ESP_GRUB_PATH="$candidate"
    break
  fi
done
[[ -n "$ESP_GRUB_PATH" ]] || {
  echo "FATAL: grubx64.efi missing from input efiboot.img" >&2
  exit 1
}
BOOTX64_SHA_BEFORE="$(sha256sum "$TMP/BOOTX64.before" | awk '{print $1}')"
GRUBX64_SHA_BEFORE="$(sha256sum "$TMP/grubx64.before" | awk '{print $1}')"

ESP_CFG_DIR="$TMP/esp-cfg"
mkdir -p "$ESP_CFG_DIR"
esp_cfg_found=0
for esp_cfg_path in EFI/BOOT/grub.cfg EFI/BOOT/GRUB.CFG efi/boot/grub.cfg; do
  rm -f "$ESP_CFG_DIR/grub.cfg"
  if mcopy -n -i "$ESP_IMG" "::$esp_cfg_path" "$ESP_CFG_DIR/grub.cfg" >/dev/null 2>&1; then
    python3 "$REWRITE_TOOL" "$ESP_CFG_DIR/grub.cfg" "$LIMAD_OS_VERSION" "$VOLID"
    python3 "$AUDIT_TOOL" "$ESP_CFG_DIR/grub.cfg" "$VOLID" "$esp_cfg_path inside input efiboot.img" >/dev/null
    mcopy -o -i "$ESP_IMG" "$ESP_CFG_DIR/grub.cfg" "::$esp_cfg_path"
    esp_cfg_found=1
    break
  fi
done
((esp_cfg_found == 1)) || {
  echo "FATAL: no EFI/BOOT/grub.cfg found inside /images/efiboot.img" >&2
  exit 1
}

esp_extract_required "$ESP_BOOT_PATH" "$TMP/BOOTX64.after" || {
  echo "FATAL: BOOTX64.EFI disappeared while updating efiboot.img" >&2
  exit 1
}
esp_extract_required "$ESP_GRUB_PATH" "$TMP/grubx64.after" || {
  echo "FATAL: grubx64.efi disappeared while updating efiboot.img" >&2
  exit 1
}
[[ "$(sha256sum "$TMP/BOOTX64.after" | awk '{print $1}')" == "$BOOTX64_SHA_BEFORE" ]] || {
  echo "FATAL: BOOTX64.EFI changed while only grub.cfg was meant to change" >&2
  exit 1
}
[[ "$(sha256sum "$TMP/grubx64.after" | awk '{print $1}')" == "$GRUBX64_SHA_BEFORE" ]] || {
  echo "FATAL: grubx64.efi changed while only grub.cfg was meant to change" >&2
  exit 1
}
cmp -s "$TMP/BOOTX64.before" "$TMP/BOOTX64.after" || {
  echo "FATAL: BOOTX64.EFI binary integrity check failed" >&2
  exit 1
}
cmp -s "$TMP/grubx64.before" "$TMP/grubx64.after" || {
  echo "FATAL: grubx64.efi binary integrity check failed" >&2
  exit 1
}
map_args+=(-map "$ESP_IMG" /images/efiboot.img)

TREEINFO_ISO_PATH=""
for candidate in /.treeinfo /treeinfo; do
  if iso_file_exists "$candidate"; then
    TREEINFO_ISO_PATH="$candidate"
    break
  fi
done
TREEINFO_MODE="absent-native-layout"
if [[ -n "$TREEINFO_ISO_PATH" ]]; then
  [[ -x "$TREEINFO_TOOL" ]] || { echo "FATAL: treeinfo checksum updater missing" >&2; exit 1; }
  TREEINFO_LOCAL="$TMP/treeinfo"
  xorriso -osirrox on -indev "$INPUT" -extract "$TREEINFO_ISO_PATH" "$TREEINFO_LOCAL" >/dev/null 2>&1
  python3 "$TREEINFO_TOOL" "$TREEINFO_LOCAL" \
    /images/product.img="$TMP/product.img" \
    /images/efiboot.img="$ESP_IMG"
  map_args+=(-map "$TREEINFO_LOCAL" "$TREEINFO_ISO_PATH")
  TREEINFO_MODE="preserved-and-refreshed"
else
  echo "No .treeinfo in source ISO; preserving the native bootc-image-builder metadata layout without inventing product metadata."
fi

rm -f "$OUTPUT"
xorriso -indev "$INPUT" -outdev "$OUTPUT" -overwrite on -boot_image any replay "${map_args[@]}" \
  >/tmp/limad-xorriso.log 2>&1 || { cat /tmp/limad-xorriso.log >&2; exit 1; }
[[ -s "$OUTPUT" ]] || { echo "FATAL: branded ISO not created" >&2; exit 1; }

OUTPUT_VOLID="$(read_volume_id "$OUTPUT")"
[[ "$OUTPUT_VOLID" == "$VOLID" ]] || {
  echo "FATAL: output ISO label changed unexpectedly to '$OUTPUT_VOLID'" >&2
  exit 1
}

implantisomd5 --force "$OUTPUT" >/tmp/limad-implantisomd5.log 2>&1 || {
  cat /tmp/limad-implantisomd5.log >&2
  exit 1
}

echo "Branded ISO: $OUTPUT"
echo "ISO volume id: $VOLID"
echo "Installer product image ${PRODUCT_MODE} and overlaid; EFI label references and embedded media checksum refreshed; treeinfo mode: ${TREEINFO_MODE}."

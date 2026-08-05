#!/usr/bin/env bash
set -Eeuo pipefail

[[ $# -eq 1 ]] || {
  echo "Usage: $0 ISO" >&2
  exit 2
}

ISO="$1"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/build_files/versions.env"
source "$ROOT/tools/lib-iso-branding.sh"

EXPECTED_VOLID="$(limad_iso_volume_id "$LIMAD_OS_VERSION")"
AUDIT_TOOL="$ROOT/tools/audit-boot-config.py"

for cmd in xorriso unsquashfs python3 mcopy checkisomd5 sha256sum; do
  command -v "$cmd" >/dev/null || {
    echo "FATAL: $cmd missing" >&2
    exit 1
  }
done
[[ -x "$AUDIT_TOOL" ]] || { echo "FATAL: boot config auditor missing" >&2; exit 1; }
[[ -s "$ISO" ]] || { echo "FATAL: ISO missing: $ISO" >&2; exit 1; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

extract_iso_file() {
  local iso_path="$1" local_path="$2"
  mkdir -p "$(dirname "$local_path")"
  xorriso -osirrox on -indev "$ISO" -extract "$iso_path" "$local_path" >/dev/null 2>&1 || {
    echo "ISO CHECK FAILED: cannot extract $iso_path" >&2
    exit 1
  }
  [[ -s "$local_path" ]] || {
    echo "ISO CHECK FAILED: $iso_path is empty" >&2
    exit 1
  }
}

iso_file_exists() {
  local iso_path="$1" output
  output="$(xorriso -indev "$ISO" -find "$iso_path" -type f -exec echo -- 2>/dev/null || true)"
  printf '%s\n' "$output" |
    sed -nE \
      -e "s/^[[:space:]]*'([^']+)'[[:space:]]*$/\1/p" \
      -e 's/^[[:space:]]*"([^"]+)"[[:space:]]*$/\1/p' \
      -e 's|^[[:space:]]*(/[^[:space:]]+)[[:space:]]*$|\1|p' |
    grep -Fxq "$iso_path"
}

require_iso_path() {
  local iso_path="$1"
  iso_file_exists "$iso_path" || {
    echo "ISO CHECK FAILED: required file missing: $iso_path" >&2
    exit 1
  }
}

PVD_INFO="$(xorriso -indev "$ISO" -pvd_info 2>&1)"
ACTUAL_VOLID="$(printf '%s\n' "$PVD_INFO" | sed -nE "s/.*Volume id[[:space:]]*:[[:space:]]*'([^']*)'.*/\1/p" | head -n1)"
[[ -n "$ACTUAL_VOLID" ]] || { echo "ISO CHECK FAILED: volume id could not be read" >&2; exit 1; }
[[ "$ACTUAL_VOLID" == "$EXPECTED_VOLID" ]] || {
  echo "ISO CHECK FAILED: volume id is '$ACTUAL_VOLID', expected '$EXPECTED_VOLID'" >&2
  exit 1
}

for required_path in \
  /images/install.img \
  /images/product.img \
  /images/efiboot.img \
  /images/pxeboot/vmlinuz \
  /images/pxeboot/initrd.img
do
  require_iso_path "$required_path"
done

EL_TORITO_REPORT="$(xorriso -indev "$ISO" -report_el_torito plain 2>&1 || true)"
printf '%s\n' "$EL_TORITO_REPORT" | grep -Eqi 'UEFI|EFI' || {
  echo "ISO CHECK FAILED: no UEFI El Torito boot entry found" >&2
  printf '%s\n' "$EL_TORITO_REPORT" >&2
  exit 1
}

SYSTEM_AREA_REPORT="$(xorriso -indev "$ISO" -report_system_area plain 2>&1 || true)"
limad_system_area_has_hybrid_boot "$SYSTEM_AREA_REPORT" || {
  echo "ISO CHECK FAILED: no hybrid USB boot partition metadata found" >&2
  printf '%s\n' "$SYSTEM_AREA_REPORT" >&2
  exit 1
}
if ! limad_system_area_has_esp "$SYSTEM_AREA_REPORT"; then
  echo "ISO CHECK FAILED: EFI System Partition is not exposed for raw USB boot" >&2
  printf '%s\n' "$SYSTEM_AREA_REPORT" >&2
  exit 1
fi

if ! checkisomd5 "$ISO" >/tmp/limad-checkisomd5.log 2>&1; then
  cat /tmp/limad-checkisomd5.log >&2
  echo "ISO CHECK FAILED: embedded media checksum is absent or invalid" >&2
  exit 1
fi

PRODUCT_IMG="$TMP/product.img"
ESP_IMG="$TMP/efiboot.img"
extract_iso_file /images/product.img "$PRODUCT_IMG"
extract_iso_file /images/efiboot.img "$ESP_IMG"
extract_iso_file /images/pxeboot/vmlinuz "$TMP/vmlinuz"
extract_iso_file /images/pxeboot/initrd.img "$TMP/initrd.img"
unsquashfs -d "$TMP/product" "$PRODUCT_IMG" >/dev/null
[[ -f "$TMP/product/.buildstamp" ]] || { echo "ISO CHECK FAILED: .buildstamp missing" >&2; exit 1; }
grep -q '^Product=LiMaD OS$' "$TMP/product/.buildstamp" || { echo "ISO CHECK FAILED: product name" >&2; exit 1; }
grep -q '^IsFinal=True$' "$TMP/product/.buildstamp" || { echo "ISO CHECK FAILED: IsFinal" >&2; exit 1; }
[[ -f "$TMP/product/usr/share/cockpit/branding/bazzite/logo.png" ]] || { echo "ISO CHECK FAILED: Bazzite WebUI overlay missing" >&2; exit 1; }
[[ -f "$TMP/product/etc/anaconda/conf.d/99-limad.conf" ]] || { echo "ISO CHECK FAILED: LiMaD Anaconda config missing" >&2; exit 1; }

TREEINFO_ISO_PATH=""
for candidate in /.treeinfo /treeinfo; do
  if iso_file_exists "$candidate"; then
    TREEINFO_ISO_PATH="$candidate"
    break
  fi
done
if [[ -n "$TREEINFO_ISO_PATH" ]]; then
  TREEINFO="$TMP/treeinfo"
  extract_iso_file "$TREEINFO_ISO_PATH" "$TREEINFO"

  python3 - "$TREEINFO" "$PRODUCT_IMG" "$ESP_IMG" <<'PY'
import configparser
import hashlib
import sys
from pathlib import Path

def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

cfg = configparser.ConfigParser(interpolation=None)
cfg.optionxform = str
cfg.read(sys.argv[1])
if not cfg.has_section('checksums'):
    raise SystemExit('ISO CHECK FAILED: [checksums] section missing from .treeinfo')
stage2 = cfg.get('stage2', 'mainimage', fallback='').lstrip('/')
if stage2 and stage2 != 'images/install.img':
    raise SystemExit(f'ISO CHECK FAILED: stage2 mainimage is {stage2!r}, expected images/install.img')
for key, local in (
    ('images/product.img', Path(sys.argv[2])),
    ('images/efiboot.img', Path(sys.argv[3])),
):
    actual = cfg.get('checksums', key, fallback='')
    if not actual:
        continue
    expected = f'sha256:{digest(local)}'
    if actual != expected:
        raise SystemExit(f'ISO CHECK FAILED: .treeinfo checksum for {key} is {actual!r}, expected {expected!r}')
PY
  while IFS= read -r metadata_path; do
    [[ -n "$metadata_path" ]] || continue
    require_iso_path "$metadata_path"
  done < <(python3 - "$TREEINFO" <<'PY'
import configparser
import sys
cfg = configparser.ConfigParser(interpolation=None)
cfg.optionxform = str
cfg.read(sys.argv[1])
paths = set()
for section in cfg.sections():
    for _, value in cfg.items(section):
        value = value.strip()
        if value.startswith(('http://', 'https://', 'ftp://')):
            continue
        if value.startswith('/'):
            paths.add(value)
        elif value.endswith(('.img', 'vmlinuz')) or value.endswith('initrd.img'):
            paths.add('/' + value.lstrip('/'))
for value in sorted(paths):
    print(value)
PY
  )
  echo "Final ISO metadata: optional $TREEINFO_ISO_PATH found and validated."
else
  echo "Final ISO metadata: no .treeinfo present; native bootc-image-builder layout preserved and direct payload checks passed."
fi

FIND_OUTPUT="$(xorriso -indev "$ISO" -find / -type f \( -name '*.cfg' -o -name '*.conf' \) -exec echo -- 2>&1 || true)"
mapfile -t CFGS < <(
  printf '%s\n' "$FIND_OUTPUT" |
    sed -nE -e "s/^[[:space:]]*'([^']+)'[[:space:]]*$/\1/p" -e 's/^[[:space:]]*"([^"]+)"[[:space:]]*$/\1/p' -e 's|^[[:space:]]*(/[^[:space:]]+)[[:space:]]*$|\1|p' |
    sort -u
)
for candidate in /EFI/BOOT/grub.cfg /boot/grub2/grub.cfg /isolinux/isolinux.cfg /isolinux/grub.conf /syslinux/syslinux.cfg; do
  if iso_file_exists "$candidate"; then
    present=0
    for existing in "${CFGS[@]:-}"; do [[ "$existing" == "$candidate" ]] && present=1; done
    ((present == 1)) || CFGS+=("$candidate")
  fi
done

checked=0
branded=0
for iso_path in "${CFGS[@]:-}"; do
  case "$iso_path" in
    *grub*.cfg|*isolinux*.cfg|*syslinux*.cfg)
      file="$TMP/configs/${iso_path#/}"
      mkdir -p "$(dirname "$file")"
      xorriso -osirrox on -indev "$ISO" -extract "$iso_path" "$file" >/dev/null 2>&1 || continue
      while IFS= read -r boot_path; do
        [[ -n "$boot_path" ]] || continue
        require_iso_path "$boot_path"
      done < <(python3 "$AUDIT_TOOL" "$file" "$EXPECTED_VOLID" "$iso_path")
      grep -q 'LiMaD OS' "$file" && branded=$((branded + 1))
      checked=$((checked + 1))
      ;;
  esac
done

esp_copy() {
  local source="$1" destination="$2"
  rm -f "$destination"
  mcopy -n -i "$ESP_IMG" "::$source" "$destination" >/dev/null 2>&1
}

esp_copy EFI/BOOT/BOOTX64.EFI "$TMP/BOOTX64.EFI" || {
  echo "ISO CHECK FAILED: EFI/BOOT/BOOTX64.EFI missing inside efiboot.img" >&2
  exit 1
}
[[ -s "$TMP/BOOTX64.EFI" ]] || { echo "ISO CHECK FAILED: BOOTX64.EFI is empty" >&2; exit 1; }

if ! esp_copy EFI/BOOT/grubx64.efi "$TMP/grubx64.efi" && ! esp_copy EFI/BOOT/GRUBX64.EFI "$TMP/grubx64.efi"; then
  echo "ISO CHECK FAILED: grubx64.efi missing inside efiboot.img" >&2
  exit 1
fi
[[ -s "$TMP/grubx64.efi" ]] || { echo "ISO CHECK FAILED: grubx64.efi is empty" >&2; exit 1; }

esp_cfg_found=0
for esp_cfg_path in EFI/BOOT/grub.cfg EFI/BOOT/GRUB.CFG efi/boot/grub.cfg; do
  if esp_copy "$esp_cfg_path" "$TMP/esp-grub.cfg"; then
    while IFS= read -r boot_path; do
      [[ -n "$boot_path" ]] || continue
      require_iso_path "$boot_path"
    done < <(python3 "$AUDIT_TOOL" "$TMP/esp-grub.cfg" "$EXPECTED_VOLID" "$esp_cfg_path inside images/efiboot.img")
    esp_cfg_found=1
    checked=$((checked + 1))
    break
  fi
done
((esp_cfg_found == 1)) || { echo "ISO CHECK FAILED: could not read EFI grub.cfg from efiboot.img" >&2; exit 1; }
((checked > 0)) || { echo "ISO CHECK FAILED: no boot config verified" >&2; exit 1; }
((branded > 0)) || { echo "ISO CHECK FAILED: no LiMaD boot menu title found" >&2; exit 1; }

echo "ISO deep boot audit passed: current images/install.img stage2, LiMaD product.img overlay, native label $EXPECTED_VOLID, UEFI boot entry, readable kernel/initrd, EFI binaries and media checksum verified; optional .treeinfo metadata validated only when present."

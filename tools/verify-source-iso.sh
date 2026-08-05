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

for cmd in xorriso mcopy checkisomd5 python3; do
  command -v "$cmd" >/dev/null || {
    echo "SOURCE ISO CHECK FAILED: $cmd missing" >&2
    exit 1
  }
done

[[ -s "$ISO" ]] || {
  echo "SOURCE ISO CHECK FAILED: ISO missing or empty: $ISO" >&2
  exit 1
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

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

require_iso_file() {
  local iso_path="$1"
  iso_file_exists "$iso_path" || {
    echo "SOURCE ISO CHECK FAILED: required file missing: $iso_path" >&2
    exit 1
  }
}

extract_iso_file() {
  local iso_path="$1" destination="$2"
  xorriso -osirrox on -indev "$ISO" -extract "$iso_path" "$destination" >/dev/null 2>&1 || {
    echo "SOURCE ISO CHECK FAILED: cannot extract $iso_path" >&2
    exit 1
  }
  [[ -s "$destination" ]] || {
    echo "SOURCE ISO CHECK FAILED: $iso_path is empty" >&2
    exit 1
  }
}

PVD_INFO="$(xorriso -indev "$ISO" -pvd_info 2>&1)"
ACTUAL_VOLID="$(printf '%s\n' "$PVD_INFO" | sed -nE "s/.*Volume id[[:space:]]*:[[:space:]]*'([^']*)'.*/\1/p" | head -n1)"
[[ "$ACTUAL_VOLID" == "$EXPECTED_VOLID" ]] || {
  echo "SOURCE ISO CHECK FAILED: volume id is '$ACTUAL_VOLID', expected '$EXPECTED_VOLID'" >&2
  exit 1
}

for required_path in \
  /images/install.img \
  /images/efiboot.img \
  /images/pxeboot/vmlinuz \
  /images/pxeboot/initrd.img \
  /osbuild.ks
do
  require_iso_file "$required_path"
done

extract_iso_file /images/pxeboot/vmlinuz "$TMP/vmlinuz"
extract_iso_file /images/pxeboot/initrd.img "$TMP/initrd.img"
extract_iso_file /images/efiboot.img "$TMP/efiboot.img"
extract_iso_file /osbuild.ks "$TMP/osbuild.ks"

EL_TORITO_REPORT="$(xorriso -indev "$ISO" -report_el_torito plain 2>&1 || true)"
printf '%s\n' "$EL_TORITO_REPORT" | grep -Eqi 'UEFI|EFI' || {
  echo "SOURCE ISO CHECK FAILED: no UEFI El Torito entry" >&2
  printf '%s\n' "$EL_TORITO_REPORT" >&2
  exit 1
}

SYSTEM_AREA_REPORT="$(xorriso -indev "$ISO" -report_system_area plain 2>&1 || true)"
limad_system_area_has_hybrid_boot "$SYSTEM_AREA_REPORT" || {
  echo "SOURCE ISO CHECK FAILED: hybrid USB boot metadata missing" >&2
  printf '%s\n' "$SYSTEM_AREA_REPORT" >&2
  exit 1
}
if ! limad_system_area_has_esp "$SYSTEM_AREA_REPORT"; then
  echo "SOURCE ISO CHECK FAILED: EFI System Partition is not exposed for raw USB boot" >&2
  printf '%s\n' "$SYSTEM_AREA_REPORT" >&2
  exit 1
fi

TREEINFO_PATH=""
for candidate in /.treeinfo /treeinfo; do
  if iso_file_exists "$candidate"; then
    TREEINFO_PATH="$candidate"
    break
  fi
done
if [[ -n "$TREEINFO_PATH" ]]; then
  extract_iso_file "$TREEINFO_PATH" "$TMP/treeinfo"
  python3 - "$TMP/treeinfo" "$TMP/efiboot.img" "$TMP/vmlinuz" "$TMP/initrd.img" <<'PY_TREE'
import configparser
import hashlib
import sys
from pathlib import Path

cfg = configparser.ConfigParser(interpolation=None)
cfg.optionxform = str
cfg.read(sys.argv[1])
if not cfg.has_section('checksums'):
    raise SystemExit('SOURCE ISO CHECK FAILED: [checksums] missing from .treeinfo')

stage2 = cfg.get('stage2', 'mainimage', fallback='').lstrip('/')
if stage2 and stage2 != 'images/install.img':
    raise SystemExit(f'SOURCE ISO CHECK FAILED: stage2 mainimage is {stage2!r}, expected images/install.img')

def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return 'sha256:' + h.hexdigest()

required = (
    ('images/efiboot.img', sys.argv[2]),
    ('images/pxeboot/vmlinuz', sys.argv[3]),
    ('images/pxeboot/initrd.img', sys.argv[4]),
)
for key, local in required:
    actual = cfg.get('checksums', key, fallback='')
    if not actual:
        continue
    expected = digest(local)
    if actual != expected:
        raise SystemExit(f'SOURCE ISO CHECK FAILED: .treeinfo {key} is {actual!r}, expected {expected!r}')
PY_TREE
  echo "Source ISO metadata: optional $TREEINFO_PATH found and validated."
else
  echo "Source ISO metadata: no .treeinfo present; this is the native bootc-image-builder Fedora 44 layout. Direct payload, boot and media checks remain authoritative."
fi

if ! checkisomd5 "$ISO" >"$TMP/checkisomd5.log" 2>&1; then
  cat "$TMP/checkisomd5.log" >&2
  echo "SOURCE ISO CHECK FAILED: embedded media checksum invalid" >&2
  exit 1
fi

copy_esp_file() {
  local source="$1" destination="$2"
  rm -f "$destination"
  mcopy -n -i "$TMP/efiboot.img" "::$source" "$destination" >/dev/null 2>&1
}

ESP_CFG=""
for candidate in EFI/BOOT/grub.cfg EFI/BOOT/GRUB.CFG efi/boot/grub.cfg; do
  if copy_esp_file "$candidate" "$TMP/efi-grub.cfg"; then
    ESP_CFG="$TMP/efi-grub.cfg"
    break
  fi
done
[[ -n "$ESP_CFG" ]] || {
  echo "SOURCE ISO CHECK FAILED: EFI grub.cfg missing inside efiboot.img" >&2
  exit 1
}

copy_esp_file EFI/BOOT/BOOTX64.EFI "$TMP/BOOTX64.EFI" || {
  echo "SOURCE ISO CHECK FAILED: BOOTX64.EFI missing inside efiboot.img" >&2
  exit 1
}
[[ -s "$TMP/BOOTX64.EFI" ]] || {
  echo "SOURCE ISO CHECK FAILED: BOOTX64.EFI is empty" >&2
  exit 1
}
if ! copy_esp_file EFI/BOOT/grubx64.efi "$TMP/grubx64.efi" && \
   ! copy_esp_file EFI/BOOT/GRUBX64.EFI "$TMP/grubx64.efi"; then
  echo "SOURCE ISO CHECK FAILED: grubx64.efi missing inside efiboot.img" >&2
  exit 1
fi
[[ -s "$TMP/grubx64.efi" ]] || {
  echo "SOURCE ISO CHECK FAILED: grubx64.efi is empty" >&2
  exit 1
}

python3 - "$ESP_CFG" "$EXPECTED_VOLID" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
expected = sys.argv[2]
text = path.read_text(errors='replace')

variables = {}
for line in text.splitlines():
    match = re.match(r'^\s*set\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$', line)
    if match:
        value = match.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        variables[match.group(1)] = value

def resolve(value):
    value = value.strip().strip("\"'")
    match = re.fullmatch(r'\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))', value)
    if match:
        name = match.group(1) or match.group(2)
        if name not in variables:
            raise SystemExit(f'SOURCE ISO CHECK FAILED: unresolved label variable {value!r}')
        return variables[name]
    return value

labels = []
for pattern in (
    r'inst\.stage2=hd:LABEL=([^:\s"\']+)',
    r'inst\.ks=hd:LABEL=([^:\s"\']+)',
    r'root=live:CDLABEL=([^\s"\']+)',
    r'root=live:LABEL=([^\s"\']+)',
):
    labels.extend(re.findall(pattern, text))

for line in text.splitlines():
    stripped = line.strip()
    if not re.match(r'^search(?:\.file|\.fs_uuid|\.fs_label)?\b', stripped, re.I):
        continue
    for pattern in (
        r'(?:--label|--fs-label)(?:=|\s+)(["\']?[^\s"\']+["\']?)',
        r'(?<!\S)-[lL](?:=|\s+)(["\']?[^\s"\']+["\']?)',
    ):
        labels.extend(re.findall(pattern, stripped))
    match = re.match(r'^search\.fs_label\s+(["\']?[^\s"\']+["\']?)', stripped, re.I)
    if match:
        labels.append(match.group(1))

if not labels:
    raise SystemExit('SOURCE ISO CHECK FAILED: no ISO label references found in EFI grub.cfg')
for label in labels:
    actual = resolve(label)
    if actual != expected:
        raise SystemExit(f'SOURCE ISO CHECK FAILED: EFI label {actual!r} != {expected!r}')

paths = set()
for line in text.splitlines():
    match = re.match(r'^\s*(?:linux|linuxefi|linux16|initrd|initrdefi|initrd16)\s+([^\s]+)', line, re.I)
    if match:
        value = match.group(1).strip("\"'")
        if value.startswith('/'):
            paths.add(value)
required = {'/images/pxeboot/vmlinuz', '/images/pxeboot/initrd.img'}
missing = required - paths
if missing:
    raise SystemExit(f'SOURCE ISO CHECK FAILED: EFI grub.cfg misses boot targets: {sorted(missing)}')
PY

echo "Source ISO verified: current Anaconda images/install.img layout, native label, UEFI binaries and configuration, kernel, initramfs, hybrid USB structure and media checksum are valid; optional .treeinfo metadata was validated only when present."

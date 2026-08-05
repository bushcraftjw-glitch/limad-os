#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."

fail() { echo "FIX16 DEEP ISO BOOT AUDIT FAILED: $*" >&2; exit 1; }

source build_files/versions.env
[[ "$LIMAD_BUILD_REVISION" =~ ^gnome-rc2-build(4|5)$ || "$LIMAD_BUILD_REVISION" =~ ^gnome42-phase4-fix(32|35|36|37|38|39|41|42|43|44|45|46|47|48|49|50)$ ]] || fail "wrong build revision"
[[ "$LIMAD_IMAGE_NAME" == "limad-os-gnome-280" ]] || fail "wrong GHCR image name"

source tools/lib-iso-branding.sh
VOLID="$(limad_iso_volume_id "$LIMAD_OS_VERSION")"
[[ "$VOLID" == "LIMAD_OS_280_RC2" ]] || fail "unexpected native volume id"

grep -Fq '[customizations.iso]' disk_config/iso.toml || fail "native ISO customization missing"
grep -Fq 'volume_id = "LIMAD_OS_280_RC2"' disk_config/iso.toml || fail "native ISO volume id missing"
grep -Fq 'application_id = "LiMaD OS 2.8.0-rc2"' disk_config/iso.toml || fail "native application id missing"

brand="$(cat tools/brand-installer-iso.sh)"
for needle in \
  'run this ISO preservation step as root' \
  'if iso_file_exists /images/product.img; then' \
  'PRODUCT_MODE="created"' \
  'PRODUCT_MODE="preserved"' \
  'unsquashfs -d "$PRODUCT" "$ORIGINAL_PRODUCT"' \
  'mksquashfs "$PRODUCT" "$TMP/product.img" -noappend -comp xz -all-root' \
  'update-treeinfo-checksums.py' \
  'implantisomd5 --force' \
  '-boot_image any replay' \
  'bootc-image-builder created ISO label' \
  'in ISO tree' \
  'BOOTX64.EFI changed while only grub.cfg was meant to change' \
  'grubx64.efi changed while only grub.cfg was meant to change'; do
  grep -Fq -- "$needle" tools/brand-installer-iso.sh || fail "branding hardening missing: $needle"
done
if grep -Eq -- '(^|[[:space:]])-volid([[:space:]]|$)' tools/brand-installer-iso.sh; then
  fail "post-build volume label mutation remains"
fi
if grep -Fq 'limad-grub-background' tools/brand-installer-iso.sh; then
  fail "cosmetic GRUB background is still injected into the EFI boot path"
fi

for needle in \
  'checkisomd5' \
  '-report_el_torito plain' \
  '-report_system_area plain' \
  '/images/pxeboot/vmlinuz' \
  '/images/pxeboot/initrd.img' \
  'BOOTX64.EFI' \
  'grubx64.efi' \
  '.treeinfo checksum' \
  'audit-boot-config.py'; do
  grep -Fq -- "$needle" tools/verify-branded-iso.sh || fail "deep verifier missing: $needle"
done

grep -Fq 'isomd5sum' .github/workflows/build.yml || fail "CI does not install media-check tools"
grep -Fq 'sudo bash tools/brand-installer-iso.sh' .github/workflows/build.yml || fail "SquashFS overlay is not built as root"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cat > "$TMP/grub.cfg" <<'CFG'
set isolabel='Fedora-WS-Live-44-1-1'
search --no-floppy --set=root -L "$isolabel"
search.fs_label "$isolabel" root
menuentry 'Start Fedora Linux 44' {
 linuxefi /images/pxeboot/vmlinuz inst.stage2=hd:LABEL=Fedora-WS-Live-44-1-1 root=live:CDLABEL=Fedora-WS-Live-44-1-1 rd.live.image
 initrdefi /images/pxeboot/initrd.img
}
CFG
python3 tools/rewrite-boot-config.py "$TMP/grub.cfg" "$LIMAD_OS_VERSION" "$VOLID"
grep -Fq "set isolabel='LIMAD_OS_280_RC2'" "$TMP/grub.cfg" || fail "label variable was not rewritten"
grep -Fq 'inst.stage2=hd:LABEL=LIMAD_OS_280_RC2' "$TMP/grub.cfg" || fail "stage2 label was not rewritten"
grep -Fq 'root=live:CDLABEL=LIMAD_OS_280_RC2' "$TMP/grub.cfg" || fail "live root label was not rewritten"
paths="$(python3 tools/audit-boot-config.py "$TMP/grub.cfg" "$VOLID" synthetic-grub)"
printf '%s\n' "$paths" | grep -Fxq '/images/pxeboot/vmlinuz' || fail "kernel path was not audited"
printf '%s\n' "$paths" | grep -Fxq '/images/pxeboot/initrd.img' || fail "initrd path was not audited"

cat > "$TMP/bad.cfg" <<'CFG'
search --no-floppy --set=root -l 'WRONG_LABEL'
linuxefi /images/pxeboot/vmlinuz root=live:CDLABEL=WRONG_LABEL
CFG
if python3 tools/audit-boot-config.py "$TMP/bad.cfg" "$VOLID" bad-grub >/dev/null 2>&1; then
  fail "wrong GRUB label was accepted"
fi

printf 'product' > "$TMP/product.img"
printf 'efi' > "$TMP/efiboot.img"
cat > "$TMP/.treeinfo" <<'TREE'
[checksums]
images/product.img = sha256:old
images/efiboot.img = sha256:old
TREE
python3 tools/update-treeinfo-checksums.py "$TMP/.treeinfo" \
  /images/product.img="$TMP/product.img" \
  /images/efiboot.img="$TMP/efiboot.img"
python3 - "$TMP/.treeinfo" "$TMP/product.img" "$TMP/efiboot.img" <<'PY'
import configparser
import hashlib
import sys
from pathlib import Path
cfg = configparser.ConfigParser(interpolation=None)
cfg.read(sys.argv[1])
for key, name in [('images/product.img', sys.argv[2]), ('images/efiboot.img', sys.argv[3])]:
    actual = cfg.get('checksums', key)
    expected = 'sha256:' + hashlib.sha256(Path(name).read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f'{key}: {actual} != {expected}')
PY

echo "FIX16/18 native-label, adaptive-product-overlay, treeinfo, EFI and media-check audit: PASS"

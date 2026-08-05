#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."

fail() { echo "FIX15 EFI BOOT REPAIR FAILED: $*" >&2; exit 1; }

source build_files/versions.env

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cat > "$TMP/grub.cfg" <<'CFG'
search --no-floppy --set=root -l 'Fedora-WS-Live-44-1-1'
menuentry 'Start Fedora Linux 44' {
 linuxefi /images/pxeboot/vmlinuz root=live:CDLABEL=Fedora-WS-Live-44-1-1 rd.live.image
 initrdefi /images/pxeboot/initrd.img
}
CFG

python3 tools/rewrite-boot-config.py "$TMP/grub.cfg" "$LIMAD_OS_VERSION" LIMAD_OS_280_RC2

grep -Fq "search --no-floppy --set=root -l 'LIMAD_OS_280_RC2'" "$TMP/grub.cfg" || fail "short GRUB -l volume label was not rewritten"
grep -Fq 'root=live:CDLABEL=LIMAD_OS_280_RC2' "$TMP/grub.cfg" || fail "live root label was not rewritten"
grep -Fq "menuentry 'Start LiMaD OS 2.8.0-rc2'" "$TMP/grub.cfg" || fail "visible EFI menu title was not rewritten"
grep -Fq "r'(?<!\\S)-[lL]" tools/audit-boot-config.py || fail "ISO verifier does not validate short -l labels"
grep -Fq 'require_iso_path "$boot_path"' tools/verify-branded-iso.sh || fail "ISO verifier does not validate kernel/initrd paths"
grep -Fq 'mcopy -o -i "$ESP_IMG"' tools/brand-installer-iso.sh || fail "EFI grub.cfg is not overwritten explicitly"

if grep -Fq 'mcopy -n -o -i "$ESP_IMG"' tools/brand-installer-iso.sh; then
  fail "ambiguous mcopy overwrite flags remain"
fi

echo "FIX15 EFI short-label and boot-payload validation: PASS"

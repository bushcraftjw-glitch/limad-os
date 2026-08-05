#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
source build_files/versions.env
source tools/lib-iso-branding.sh

fail() { echo "FIX20 ESP GUID REPORT REPAIR FAILED: $*" >&2; exit 1; }

[[ "$LIMAD_BUILD_REVISION" =~ ^gnome-rc2-build(4|5)$ || "$LIMAD_BUILD_REVISION" =~ ^gnome42-phase4-fix(32|35|36|37|38|39|41|42|43|44|45|46|47|48|49|50)$ ]] || fail "wrong build revision"

REPORT='Boot record  : El Torito , MBR protective-msdos-label grub2-mbr cyl-align-off GPT
MBR partition      :   1   0x00  0xee            1     12215743
GPT partition name :   2  41007000700065006e006400650064003200
GPT partname local :   2  Appended2
GPT type GUID      :   2  28732ac11ff8d211ba4b00a0c93ec93b
GPT start and size :   2  12174120  40960'

limad_system_area_has_hybrid_boot "$REPORT" || fail "hybrid metadata not detected"
limad_system_area_has_esp "$REPORT" || fail "xorriso raw ESP GUID not detected"

CANONICAL='GPT partition type GUID : C12A7328-F81F-11D2-BA4B-00A0C93EC93B'
limad_system_area_has_esp "$CANONICAL" || fail "canonical ESP GUID not detected"

PATH_REPORT='GPT partition path : 2 /images/efiboot.img'
limad_system_area_has_esp "$PATH_REPORT" || fail "efiboot path not detected"

MBR_REPORT='MBR partition : 2 0x00 0xef 100 200'
limad_system_area_has_esp "$MBR_REPORT" || fail "MBR EFI type not detected"

NEGATIVE='Boot record : MBR protective-msdos-label GPT
MBR partition : 1 0x00 0xee 1 1000
GPT type GUID : 1 a2a0d0ebe5b9334487c068b6b72699c7'
if limad_system_area_has_esp "$NEGATIVE"; then
  fail "protective MBR or ISO9660 GUID misdetected as ESP"
fi

grep -Fq 'limad_system_area_has_esp "$SYSTEM_AREA_REPORT"' tools/verify-source-iso.sh || fail "source verifier not wired to helper"
grep -Fq 'limad_system_area_has_esp "$SYSTEM_AREA_REPORT"' tools/verify-branded-iso.sh || fail "final verifier not wired to helper"
! grep -Rq 'GPT partition type GUID.*C12A7328' tools/verify-source-iso.sh tools/verify-branded-iso.sh || fail "old fragile regex remains"

echo "FIX20 xorriso system-area ESP GUID parsing: PASS"

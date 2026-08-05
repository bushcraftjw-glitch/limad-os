#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."

fail() { echo "FIX22 ANACONDA LABEL PATH FAILED: $*" >&2; exit 1; }

source build_files/versions.env
[[ "$LIMAD_BUILD_REVISION" =~ ^gnome-rc2-build(4|5)$ || "$LIMAD_BUILD_REVISION" =~ ^gnome42-phase4-fix(32|35|36|37|38|39|41|42|43|44|45|46|47|48|49|50)$ ]] || fail "wrong build revision"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

cat > "$TMP/grub.cfg" <<'CFG'
set iso_label='Fedora-WS-dvd-x86_64-44'
menuentry 'LiMaD OS 2.8.0-rc2' {
  search --no-floppy --set=root -l 'Fedora-WS-dvd-x86_64-44'
  linuxefi /images/pxeboot/vmlinuz inst.stage2=hd:LABEL=Fedora-WS-dvd-x86_64-44 inst.ks=hd:LABEL=Fedora-WS-dvd-x86_64-44:/osbuild.ks quiet
  initrdefi /images/pxeboot/initrd.img
}
CFG

python3 tools/rewrite-boot-config.py "$TMP/grub.cfg" 2.8.0-rc2 LIMAD_OS_280_RC2

grep -Fq 'inst.stage2=hd:LABEL=LIMAD_OS_280_RC2' "$TMP/grub.cfg" || fail "stage2 label not rewritten"
grep -Fq 'inst.ks=hd:LABEL=LIMAD_OS_280_RC2:/osbuild.ks' "$TMP/grub.cfg" || fail "kickstart label or path not preserved"
if grep -Fq 'inst.ks=hd:LABEL=LIMAD_OS_280_RC2 quiet' "$TMP/grub.cfg"; then
  fail "kickstart path was removed"
fi

grep -Fq -- "-l 'LIMAD_OS_280_RC2'" "$TMP/grub.cfg" || fail "search label not rewritten"
python3 tools/audit-boot-config.py "$TMP/grub.cfg" LIMAD_OS_280_RC2 'FIX22 regression' > "$TMP/paths.txt"
grep -Fxq '/images/pxeboot/vmlinuz' "$TMP/paths.txt" || fail "kernel path not reported"
grep -Fxq '/images/pxeboot/initrd.img' "$TMP/paths.txt" || fail "initrd path not reported"

cp "$TMP/grub.cfg" "$TMP/bad.cfg"
sed -i.bak 's/inst.ks=hd:LABEL=LIMAD_OS_280_RC2:/inst.ks=hd:LABEL=WRONG_LABEL:/' "$TMP/bad.cfg"
if python3 tools/audit-boot-config.py "$TMP/bad.cfg" LIMAD_OS_280_RC2 'FIX22 mismatch' >"$TMP/bad.out" 2>"$TMP/bad.err"; then
  fail "wrong kickstart label was accepted"
fi
grep -Fq "label reference 'WRONG_LABEL' != 'LIMAD_OS_280_RC2'" "$TMP/bad.err" || fail "mismatch did not isolate the label from the path"
if grep -Fq "WRONG_LABEL:/osbuild.ks" "$TMP/bad.err"; then
  fail "error still treats the path as part of the label"
fi

grep -Fq "r'inst\\.ks=hd:LABEL=([^:\\s\"\\']+)'" tools/audit-boot-config.py || fail "audit parser does not stop before path separator"
grep -Fq "r'inst\\.ks=hd:LABEL=([^:\\s\"\\']+)'" tools/verify-source-iso.sh || fail "source ISO parser does not stop before path separator"
grep -Fq 'r"(inst\.ks=hd:LABEL=)([^:\s\"'"'"']+)",' tools/rewrite-boot-config.py || fail "rewriter does not preserve kickstart path"

echo "FIX22 Anaconda hd:LABEL parsing and kickstart path preservation: PASS"

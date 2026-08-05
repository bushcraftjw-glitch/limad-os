#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."

fail() { echo "FIX18 CURRENT ANACONDA ISO LAYOUT FAILED: $*" >&2; exit 1; }

source build_files/versions.env
[[ "$LIMAD_BUILD_REVISION" =~ ^gnome-rc2-build(4|5)$ || "$LIMAD_BUILD_REVISION" =~ ^gnome42-phase4-fix(32|35|36|37|38|39|41|42|43|44|45|46|47|48|49|50)$ ]] || fail "wrong build revision"

SOURCE_CHECK="tools/verify-source-iso.sh"
BRAND="tools/brand-installer-iso.sh"
FINAL_CHECK="tools/verify-branded-iso.sh"

for script in "$SOURCE_CHECK" "$BRAND" "$FINAL_CHECK"; do
  [[ -x "$script" ]] || fail "missing executable: $script"
  bash -n "$script" || fail "shell syntax: $script"
done

grep -Fq '/images/install.img' "$SOURCE_CHECK" || fail "source stage2 image is not required"
if grep -Fq '/images/product.img' "$SOURCE_CHECK"; then
  fail "source verifier still assumes product.img exists before branding"
fi
grep -Fq 'if [[ -n "$TREEINFO_PATH" ]]; then' "$SOURCE_CHECK" || fail "source .treeinfo is not handled conditionally"
grep -Fq 'no .treeinfo present; this is the native bootc-image-builder Fedora 44 layout' "$SOURCE_CHECK" || fail "native metadata layout is not accepted"
if grep -Fq 'SOURCE ISO CHECK FAILED: .treeinfo missing' "$SOURCE_CHECK"; then
  fail "source verifier still requires .treeinfo"
fi

grep -Fq 'if iso_file_exists /images/product.img; then' "$BRAND" || fail "existing product.img is not handled adaptively"
grep -Fq 'PRODUCT_MODE="created"' "$BRAND" || fail "missing product.img is not created"
grep -Fq 'PRODUCT_MODE="preserved"' "$BRAND" || fail "existing product.img is not preserved"
grep -Fq 'map_args=(-map "$TMP/product.img" /images/product.img)' "$BRAND" || fail "new product overlay is not mapped into final ISO"
grep -Fq '/images/install.img' "$BRAND" || fail "branding does not require current Anaconda stage2"

grep -Fq '/images/install.img' "$FINAL_CHECK" || fail "final verifier does not require installer stage2"
grep -Fq '/images/product.img' "$FINAL_CHECK" || fail "final verifier does not require LiMaD product overlay"
grep -Fq 'if [[ -n "$TREEINFO_ISO_PATH" ]]; then' "$FINAL_CHECK" || fail "final .treeinfo is not handled conditionally"
if grep -Fq 'ISO CHECK FAILED: .treeinfo missing' "$FINAL_CHECK"; then
  fail "final verifier still requires .treeinfo"
fi

for script in "$SOURCE_CHECK" "$BRAND" "$FINAL_CHECK"; do
  if grep -Eq 'xorriso[^\n]* -ls \"\$candidate\"|xorriso[^\n]* -ls \"\$required_path\"' "$script"; then
    fail "unreliable xorriso -ls existence check remains in $script"
  fi
  grep -Fq 'iso_file_exists()' "$script" || fail "exact ISO file lookup missing in $script"
done

echo "FIX18 current Anaconda images/install.img layout and adaptive product.img overlay: PASS"

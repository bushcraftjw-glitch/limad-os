#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."

fail() { echo "FIX21 NATIVE ISO METADATA FAILED: $*" >&2; exit 1; }

source build_files/versions.env
[[ "$LIMAD_BUILD_REVISION" =~ ^gnome-rc2-build(4|5)$ || "$LIMAD_BUILD_REVISION" =~ ^gnome42-phase4-fix(32|35|36|37|38|39|41|42|43|44|45|46|47|48|49|50)$ ]] || fail "wrong build revision"

SOURCE_CHECK="tools/verify-source-iso.sh"
BRAND="tools/brand-installer-iso.sh"
FINAL_CHECK="tools/verify-branded-iso.sh"
WORKFLOW=".github/workflows/build.yml"

for script in "$SOURCE_CHECK" "$BRAND" "$FINAL_CHECK"; do
  bash -n "$script" || fail "shell syntax: $script"
done

for forbidden in \
  'SOURCE ISO CHECK FAILED: .treeinfo missing' \
  'FATAL: installer metadata .treeinfo is missing' \
  'ISO CHECK FAILED: .treeinfo missing'; do
  if grep -RFn -- "$forbidden" "$SOURCE_CHECK" "$BRAND" "$FINAL_CHECK" >/dev/null; then
    fail "mandatory treeinfo failure remains: $forbidden"
  fi
done

grep -Fq 'no .treeinfo present; this is the native bootc-image-builder Fedora 44 layout' "$SOURCE_CHECK" || fail "source native-layout branch missing"
grep -Fq 'TREEINFO_MODE="absent-native-layout"' "$BRAND" || fail "branding native-layout mode missing"
grep -Fq 'No .treeinfo in source ISO; preserving the native bootc-image-builder metadata layout' "$BRAND" || fail "branding skip message missing"
grep -Fq 'Final ISO metadata: no .treeinfo present' "$FINAL_CHECK" || fail "final native-layout branch missing"
grep -Fq 'source-iso-layout.txt' "$WORKFLOW" || fail "ISO layout diagnostics missing"
grep -Fq 'source-iso-boot-report.txt' "$WORKFLOW" || fail "ISO boot diagnostics missing"

echo "FIX21 optional treeinfo handling for native bootc-image-builder ISO metadata: PASS"

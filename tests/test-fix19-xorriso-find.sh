#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

fail() { echo "FIX19 XORRISO FIND REPAIR FAILED: $*" >&2; exit 1; }

source build_files/versions.env
[[ "$LIMAD_BUILD_REVISION" =~ ^gnome-rc2-build(4|5)$ || "$LIMAD_BUILD_REVISION" =~ ^gnome42-phase4-fix(32|35|36|37|38|39|41|42|43|44|45|46|47|48|49|50)$ ]] || fail "wrong build revision"

for script in \
  tools/verify-source-iso.sh \
  tools/brand-installer-iso.sh \
  tools/verify-branded-iso.sh
do
  grep -q -- '-find "$iso_path" -type f -exec echo --' "$script" || fail "$script does not use documented xorriso find action"
  if grep -Eq -- '-find .* -print([[:space:]]|$)' "$script"; then
    fail "$script still uses shell-find -print syntax with xorriso"
  fi
done

grep -Fq -- "-find / -type f \\( -name '*.cfg' -o -name '*.conf' \\) -exec echo --" tools/brand-installer-iso.sh || fail "brand config discovery not repaired"
grep -Fq -- "-find / -type f \\( -name '*.cfg' -o -name '*.conf' \\) -exec echo --" tools/verify-branded-iso.sh || fail "verify config discovery not repaired"

echo "FIX19 xorriso -find action and ISO path discovery: PASS"

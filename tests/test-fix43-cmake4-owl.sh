#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
source build_files/versions.env
[[ "$LIMAD_BUILD_REVISION" =~ ^gnome-rc2-build(4|5)$ || "$LIMAD_BUILD_REVISION" =~ ^gnome42-phase4-fix(43|44|45|46|47|48|49|50)$ ]]
SCRIPT=build_files/65-airdrop-compat.sh
grep -Fq -- '-DCMAKE_POLICY_VERSION_MINIMUM=3.5' "$SCRIPT"
grep -Fq -- '-DBUILD_TESTING=OFF' "$SCRIPT"
grep -Fq 'cmake --build "$work/owl/build" --target owl' "$SCRIPT"
# The workaround is confined to the temporary OWL build; no workflow or
# upstream repository file is rewritten or pushed.
! grep -Rqs 'CMAKE_POLICY_VERSION_MINIMUM' .github
bash -n "$SCRIPT"
echo "FIX43 OWL target-only build regression protection: PASS"

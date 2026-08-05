#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."

fail() { echo "FIX17 BIB EXIT RECOVERY FAILED: $*" >&2; exit 1; }

source build_files/versions.env
[[ "$LIMAD_BUILD_REVISION" =~ ^gnome-rc2-build(4|5)$ || "$LIMAD_BUILD_REVISION" =~ ^gnome42-phase4-fix(32|35|36|37|38|39|41|42|43|44|45|46|47|48|49|50)$ ]] || fail "wrong build revision"
[[ "$LIMAD_IMAGE_NAME" == "limad-os-gnome-280" ]] || fail "wrong GHCR image name"

WORKFLOW=".github/workflows/build.yml"
SOURCE_CHECK="tools/verify-source-iso.sh"
[[ -x "$SOURCE_CHECK" ]] || fail "source ISO verifier missing or not executable"

for needle in \
  '- name: Build and validate source ISO' \
  'BIB_CONTAINER="limad-bib-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"' \
  'sudo podman run --runtime "${LIMAD_OCI_RUNTIME}" --name "$BIB_CONTAINER" --privileged' \
  '--output /output' \
  '2>&1 | tee output/bootc-image-builder.log' \
  'BIB_RC="${PIPESTATUS[0]}"' \
  'bash tools/verify-source-iso.sh "$SOURCE_ISO"' \
  'case "$BIB_RC" in' \
  '5)' \
  'Unerwarteter bootc-image-builder-Exitcode' \
  '- name: Brand and verify final ISO' \
  '- name: Upload builder diagnostics on failure'; do
  grep -Fq -- "$needle" "$WORKFLOW" || fail "workflow marker missing: $needle"
done

BUILD_BLOCK="$(sed -n '/- name: Build and validate source ISO/,/- name: Brand and verify final ISO/p' "$WORKFLOW")"
printf '%s\n' "$BUILD_BLOCK" | grep -Fq 'set +e' || fail "builder exit is not captured"
printf '%s\n' "$BUILD_BLOCK" | grep -Fq 'set -e' || fail "strict mode is not restored"
if printf '%s\n' "$BUILD_BLOCK" | grep -Eq 'podman run[^[:cntrl:]]*--rm'; then
  fail "podman auto-remove remains in the builder invocation"
fi

VERIFY_LINE="$(grep -nF 'bash tools/verify-source-iso.sh "$SOURCE_ISO"' "$WORKFLOW" | head -n1 | cut -d: -f1)"
CASE_LINE="$(grep -nF 'case "$BIB_RC" in' "$WORKFLOW" | head -n1 | cut -d: -f1)"
[[ -n "$VERIFY_LINE" && -n "$CASE_LINE" && "$VERIFY_LINE" -lt "$CASE_LINE" ]] || fail "exit 5 is accepted before source ISO validation"

for needle in \
  'LIMAD_OS_VERSION' \
  '/images/install.img' \
  '/images/pxeboot/vmlinuz' \
  '/images/pxeboot/initrd.img' \
  '/images/efiboot.img' \
  '/osbuild.ks' \
  'no .treeinfo present; this is the native bootc-image-builder Fedora 44 layout' \
  'BOOTX64.EFI missing inside efiboot.img' \
  'grubx64.efi missing inside efiboot.img' \
  'EFI System Partition is not exposed for raw USB boot' \
  '-report_el_torito plain' \
  '-report_system_area plain' \
  'checkisomd5' \
  'EFI grub.cfg missing inside efiboot.img' \
  'no ISO label references found' \
  "required = {'/images/pxeboot/vmlinuz', '/images/pxeboot/initrd.img'}"; do
  grep -Fq -- "$needle" "$SOURCE_CHECK" || fail "source verifier marker missing: $needle"
done

echo "FIX17/18 controlled BIB exit recovery with current Anaconda source ISO validation: PASS"

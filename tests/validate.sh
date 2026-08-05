#!/usr/bin/env bash
# Complete offline validation of the LiMaD OS GNOME repository.
# Everything here runs without network, podman or a Linux desktop, so it can be
# used on macOS before pushing and in CI before the image build starts.
set -Eeuo pipefail
export PYTHONDONTWRITEBYTECODE=1
cd "$(dirname "$0")/.."

# Generated Python bytecode is not source material. Remove it before and after
# validation so the subsequent Git upload remains clean as well.
cleanup_python_cache() {
  find . -type d -name '__pycache__' -prune -exec rm -rf {} +
  find . -type f \( -name '*.pyc' -o -name '*.pyo' \) -exec rm -f {} +
}
cleanup_python_cache
trap cleanup_python_cache EXIT

TESTS=(
  tests/test-shell-syntax.sh
  tests/test-clean-project.sh
  tests/test-fix22-protected-baseline.sh
  tests/test-ci-oci-runtime.sh
  tests/test-theme-sources.sh
  tests/test-icon-overlay.sh
  tests/test-build3-gstreamer-icons.sh
  tests/test-build4-lisave-zen-lidrop.sh
  tests/test-build5-linotes-study.sh
  tests/test-lidrop-exact-icon.sh
  tests/test-lidrop-os-to-os.sh
  tests/test-gnome-defaults.sh
  tests/test-desktop-polish.sh
  tests/test-logomenu-schema-patch.sh
  tests/test-first-login-runtime.sh
  tests/test-window-button-layout-hardening.sh
  tests/test-firefox-theme.sh
  tests/test-limad-apps.sh
  tests/test-screen-share.sh
  tests/test-lilink.sh
  tests/test-lilink-runtime.sh
  tests/test-build7-study-lidrop-status.sh
  tests/test-build7-plymouth-lidrop-status.sh
  tests/test-app-updater.sh
  tests/test-plymouth.sh
  tests/test-phase1-branding.sh
  tests/test-wine-integration.sh
  tests/test-windows-recipe-engine.sh
  tests/test-windows-installer2.sh
  tests/test-anycubic-package.sh
  tests/test-repo-key-paths.sh
  tests/test-bib-distro-identity.sh
  tests/test-bib-key-bridge.sh
  tests/test-build-wiring.sh
  tests/test-phase2-update-nws.sh
  tests/test-phase3-app-updater.sh
  tests/test-phase4-release-audit.sh
  tests/test-fix10-branding-hardening.sh
  tests/test-fix15-efi-boot.sh
  tests/test-fix16-deep-iso-boot.sh
  tests/test-fix17-bib-exit-recovery.sh
  tests/test-fix18-current-anaconda-iso-layout.sh
  tests/test-fix19-xorriso-find.sh
  tests/test-fix20-esp-guid-report.sh
  tests/test-fix21-native-iso-metadata.sh
  tests/test-fix22-anaconda-label-path.sh
  tests/test-fix27-branding-windows-complete.sh
  tests/test-fix28-dock-override.sh
  tests/test-fix30-bootc-initramfs-rollback.sh
  tests/test-fix32-aerion-mail-dock.sh
  tests/test-fix35-app-rollup-airdrop.sh
  tests/test-fix36-runtime-safety.sh
  tests/test-fix37-media-klang.sh
  tests/test-fix43-cmake4-owl.sh
  tests/test-280-build7-runtime.sh
  tests/test-phase5-lidrop-streaming.sh
  tests/test-fix50-study-cut-first-login.sh
  tests/test-fix11-desktop-launchers.sh
  tests/test-wallpaper-override-hardening.sh
  tests/test-identity-branding.sh
)

echo "== LiMaD OS $(cat VERSION) – offline validation =="
for t in "${TESTS[@]}"; do
  echo "-- ${t}"
  if ! bash "$t"; then
    echo >&2
    echo "VALIDIERUNG FEHLGESCHLAGEN: $t" >&2
    exit 1
  fi
done

echo
echo "LiMaD OS GNOME: vollständige Offline-Validierung erfolgreich."
echo "Image-, GNOME- und ISO-Prüfungen laufen im GitHub-Workflow."


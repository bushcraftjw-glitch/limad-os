#!/usr/bin/env bash
# LiMaD OS GNOME image build orchestrator.
# Runs inside the Bazzite GNOME container during `podman build`.
set -Eeuo pipefail

readonly BUILD_DIR="/ctx/build_files"
# shellcheck source=/dev/null
source "${BUILD_DIR}/versions.env"

log() { printf '\n\033[1;35m==> %s\033[0m\n' "$*"; }

log "LiMaD OS ${LIMAD_OS_VERSION}-${LIMAD_BUILD_REVISION} on ${BASE_IMAGE_REF}"

# Note the base the image was actually built on. Once a build is known good,
# BASE_IMAGE_TAG in versions.env can be replaced by this digest to freeze it.
install -d /usr/share/limad
{
  echo "base_image=${BASE_IMAGE_REF}"
  echo "built_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "limad_version=${LIMAD_OS_VERSION}-${LIMAD_BUILD_REVISION}"
} > /usr/share/limad/base-image.txt

bash "${BUILD_DIR}/10-packages.sh"
bash "${BUILD_DIR}/11-gstreamer-runtime.sh"
bash "${BUILD_DIR}/20-mactahoe-gtk.sh"
bash "${BUILD_DIR}/30-whitesur-icons.sh"
bash "${BUILD_DIR}/40-limad-icons.sh"
bash "${BUILD_DIR}/45-logomenu-extension.sh"
bash "${BUILD_DIR}/50-gnome-defaults.sh"
bash "${BUILD_DIR}/52-branding.sh"
bash "${BUILD_DIR}/55-plymouth.sh"
bash "${BUILD_DIR}/60-anycubic-slicer.sh"
bash "${BUILD_DIR}/65-airdrop-compat.sh"
bash "${BUILD_DIR}/67-screen-share.sh"
bash "${BUILD_DIR}/68-lilink.sh"
bash "${BUILD_DIR}/69-linotes.sh"
bash "${BUILD_DIR}/69-lisave.sh"
bash "${BUILD_DIR}/70-limad-apps.sh"
bash "${BUILD_DIR}/75-default-flatpaks.sh"
bash "${BUILD_DIR}/80-wine-installer.sh"
bash "${BUILD_DIR}/84-repo-keys.sh"
bash "${BUILD_DIR}/85-repo-hygiene.sh"
bash "${BUILD_DIR}/90-verify.sh"

log "Cleaning up build residue"
rm -rf /tmp/limad-build /var/cache/* /var/log/* /var/tmp/* 2>/dev/null || true
mkdir -p /var/cache /var/log /var/tmp

log "Build finished"

#!/usr/bin/env bash
# Work around bootc-image-builder's ISO depsolve bug for file:// GPG keys.
#
# The source bootc image can contain a valid key and its repository can work
# normally inside that image, while the ISO manifest generator still resolves
# file:// URLs against the bootc-image-builder container filesystem.  This
# helper copies the source image's public repository keys into a tiny derived
# builder image at the same absolute paths.  The LiMaD OS image itself is not
# modified and no repository or signature check is disabled.
set -Eeuo pipefail

SOURCE_IMAGE="${1:?usage: prepare-bib-key-wrapper.sh SOURCE_IMAGE OUTPUT_IMAGE [WORK_DIR]}"
OUTPUT_IMAGE="${2:?usage: prepare-bib-key-wrapper.sh SOURCE_IMAGE OUTPUT_IMAGE [WORK_DIR]}"
WORK_DIR="${3:-/tmp/limad-bib-key-wrapper}"
BIB_BASE_IMAGE="${LIMAD_BIB_BASE_IMAGE:-quay.io/centos-bootc/bootc-image-builder:latest}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "FATAL: this helper must run as root because the ISO job uses rootful Podman" >&2
  exit 1
fi
command -v podman >/dev/null 2>&1 || {
  echo "FATAL: podman is required" >&2
  exit 1
}

PODMAN=(podman)
if [[ -n "${LIMAD_OCI_RUNTIME:-}" ]]; then
  [[ -x "${LIMAD_OCI_RUNTIME}" ]] || {
    echo "FATAL: configured OCI runtime is not executable: ${LIMAD_OCI_RUNTIME}" >&2
    exit 1
  }
  PODMAN+=(--runtime "${LIMAD_OCI_RUNTIME}")
fi

rm -rf "${WORK_DIR}"
install -d -m 0755 "${WORK_DIR}/rootfs"

container_id="$("${PODMAN[@]}" create --entrypoint /usr/bin/true "${SOURCE_IMAGE}")"
cleanup() {
  "${PODMAN[@]}" rm -f "${container_id}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

copy_tree() {
  local source="$1" required="$2" destination
  destination="${WORK_DIR}/rootfs${source}"
  install -d -m 0755 "${destination}"

  if "${PODMAN[@]}" cp "${container_id}:${source}/." "${destination}/" >/dev/null 2>&1; then
    echo "   copied ${source}"
    return 0
  fi

  rm -rf "${destination}"
  if [[ "${required}" == "required" ]]; then
    echo "FATAL: required key directory is absent from the source image: ${source}" >&2
    exit 1
  fi
  echo "   optional key directory not present: ${source}"
}

# LiMaD rewrites active mutable file:// references here.  The other two trees
# are copied as a safety net for an upstream repository that already uses an
# immutable distribution-key path or that could not be rewritten.
copy_tree /usr/share/limad/repo-keys required
copy_tree /usr/share/distribution-gpg-keys optional
copy_tree /etc/pki/rpm-gpg optional

if ! find "${WORK_DIR}/rootfs/usr/share/limad/repo-keys" \
    -type f -size +0c -name 'RPM-GPG-KEY-terra*-mesa' -print -quit \
    | grep -q .; then
  echo "FATAL: the source image contains no non-empty Terra Mesa key" >&2
  find "${WORK_DIR}/rootfs" -type f -iname '*terra*' -print >&2 || true
  exit 1
fi

cat > "${WORK_DIR}/Containerfile" <<EOF_CONTAINER
FROM ${BIB_BASE_IMAGE}
COPY rootfs/ /
EOF_CONTAINER

# The base builder remains upstream bootc-image-builder.  The only added layer
# contains public RPM signing keys copied from the exact LiMaD image that the
# ISO will embed.
echo ":: Building keyed bootc-image-builder wrapper ${OUTPUT_IMAGE}"
"${PODMAN[@]}" build \
  --pull=newer \
  --format docker \
  -f "${WORK_DIR}/Containerfile" \
  -t "${OUTPUT_IMAGE}" \
  "${WORK_DIR}"

"${PODMAN[@]}" run --rm --entrypoint /usr/bin/bash "${OUTPUT_IMAGE}" -lc '
  set -Eeuo pipefail
  key="$(find /usr/share/limad/repo-keys -type f -size +0c \
          -name "RPM-GPG-KEY-terra*-mesa" -print -quit)"
  test -n "$key"
  echo "   wrapper key visible at $key"
'

echo ":: Keyed bootc-image-builder wrapper ready"

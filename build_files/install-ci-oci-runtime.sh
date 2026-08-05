#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${ROOT_DIR}/build_files/versions.env"

DESTINATION="${1:-/usr/local/bin/runc-limad}"
ARCH="$(uname -m)"

case "${ARCH}" in
  x86_64|amd64)
    ASSET="runc.amd64"
    EXPECTED_SHA256="${LIMAD_CI_RUNC_AMD64_SHA256}"
    ;;
  *)
    echo "FATAL: unsupported GitHub runner architecture for pinned runc: ${ARCH}" >&2
    exit 1
    ;;
esac

URL="https://github.com/opencontainers/runc/releases/download/v${LIMAD_CI_RUNC_VERSION}/${ASSET}"
TMP_FILE="$(mktemp)"
cleanup() {
  rm -f "${TMP_FILE}"
}
trap cleanup EXIT

curl --fail --location --silent --show-error \
  --retry 4 --retry-all-errors --connect-timeout 20 \
  --output "${TMP_FILE}" "${URL}"

printf '%s  %s\n' "${EXPECTED_SHA256}" "${TMP_FILE}" | sha256sum --check --status || {
  echo "FATAL: SHA-256 verification failed for ${URL}" >&2
  exit 1
}

install -D -m 0755 "${TMP_FILE}" "${DESTINATION}"
"${DESTINATION}" --version

install -d -m 0755 /etc/containers/containers.conf.d
cat > /etc/containers/containers.conf.d/99-limad-ci-runtime.conf <<EOF_CONF
[engine]
runtime="${DESTINATION}"
EOF_CONF

printf 'Installed verified OCI runtime: %s\n' "${DESTINATION}"

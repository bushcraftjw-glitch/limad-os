#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."

fail() {
  echo "CI OCI runtime test failed: $*" >&2
  exit 1
}

source build_files/versions.env

[[ "${LIMAD_CI_RUNC_VERSION}" == "1.4.2" ]] || fail "unexpected pinned runc version"
[[ "${LIMAD_CI_RUNC_AMD64_SHA256}" == "ac8a90f9e225bb9322189937b230cdc5478d5753f0e31e1bda98a5cf06bd9539" ]] \
  || fail "unexpected pinned runc SHA-256"

INSTALLER="build_files/install-ci-oci-runtime.sh"
[[ -x "${INSTALLER}" ]] || fail "runtime installer is missing or not executable"
grep -Fq 'sha256sum --check --status' "${INSTALLER}" || fail "download checksum is not verified"
grep -Fq 'opencontainers/runc/releases/download' "${INSTALLER}" || fail "runtime is not fetched from upstream runc releases"
grep -Fq '99-limad-ci-runtime.conf' "${INSTALLER}" || fail "Podman runtime override is not installed"

WORKFLOW=".github/workflows/build.yml"
grep -Fq 'Install verified OCI runtime' "${WORKFLOW}" || fail "image workflow does not install the verified runtime"
grep -Fq 'BUILDAH_RUNTIME=/usr/local/bin/runc-limad' "${WORKFLOW}" || fail "Buildah runtime override is missing"
grep -Fq -- '--runtime "${LIMAD_OCI_RUNTIME}"' "${WORKFLOW}" || fail "Podman does not explicitly use the pinned runtime"
grep -Fq 'sudo env LIMAD_OCI_RUNTIME="${LIMAD_OCI_RUNTIME}"' "${WORKFLOW}" || fail "ISO wrapper does not receive the runtime"

THEME_WORKFLOW=".github/workflows/theme-probe.yml"
grep -Fq 'Verifizierte OCI-Laufzeit installieren' "${THEME_WORKFLOW}" || fail "theme workflow does not install the runtime"
grep -Fq -- '--runtime "${LIMAD_OCI_RUNTIME}"' "${THEME_WORKFLOW}" || fail "theme workflow does not use the runtime"

HELPER="build_files/prepare-bib-key-wrapper.sh"
grep -Fq 'PODMAN=(podman)' "${HELPER}" || fail "BIB helper has no runtime-aware Podman wrapper"
grep -Fq 'PODMAN+=(--runtime "${LIMAD_OCI_RUNTIME}")' "${HELPER}" || fail "BIB helper does not use the pinned runtime"

echo "Pinned and SHA-256-verified OCI runtime wiring: PASS"

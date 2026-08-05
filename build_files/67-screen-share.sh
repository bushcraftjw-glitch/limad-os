#!/usr/bin/env bash
set -Eeuo pipefail

# shellcheck source=/dev/null
source /ctx/build_files/versions.env

echo ":: Installing LiMaD auf TV übertragen ${LIMAD_SCREEN_SHARE_VERSION}"

command -v gnome-network-displays >/dev/null 2>&1 || {
  echo "FATAL: gnome-network-displays is required for Google Cast and Miracast" >&2
  exit 1
}
command -v go >/dev/null 2>&1 || {
  echo "FATAL: Go compiler is required for the pinned AirPlay module" >&2
  exit 1
}

work="$(mktemp -d /tmp/limad-doubletake.XXXXXX)"
trap 'rm -rf "$work"' EXIT

git clone --quiet --depth=1 --branch "$DOUBLETAKE_TAG" "$DOUBLETAKE_REPO" "$work/source"
actual_commit="$(git -C "$work/source" rev-parse HEAD)"
[[ "$actual_commit" == "$DOUBLETAKE_COMMIT" ]] || {
  echo "FATAL: doubletake tag ${DOUBLETAKE_TAG} resolved to ${actual_commit}, expected ${DOUBLETAKE_COMMIT}" >&2
  exit 1
}

make -C "$work/source" clean >/dev/null 2>&1 || true
make -C "$work/source"
make -C "$work/source" test

install -d -m 0755 /usr/local/libexec/limad-screen-share
install -m 0755 "$work/source/bin/doubletake" /usr/local/libexec/limad-screen-share/doubletake
install -m 0755 "$work/source/bin/doubletake-ctl" /usr/local/libexec/limad-screen-share/doubletake-ctl

[[ -f "$work/source/LICENSE" ]] || { echo "FATAL: doubletake LICENSE missing" >&2; exit 1; }
[[ -f "$work/source/COPYING.GPL" ]] || { echo "FATAL: doubletake COPYING.GPL missing" >&2; exit 1; }
install -d -m 0755 /usr/share/licenses/limad-screen-share-doubletake
install -m 0644 "$work/source/LICENSE" /usr/share/licenses/limad-screen-share-doubletake/LICENSE
install -m 0644 "$work/source/COPYING.GPL" /usr/share/licenses/limad-screen-share-doubletake/COPYING.GPL

install -d -m 0755 /usr/share/limad-source/doubletake
cat > /usr/share/limad-source/doubletake/PROVENANCE.txt <<PROVENANCE
project=doubletake
source=${DOUBLETAKE_REPO}
tag=${DOUBLETAKE_TAG}
commit=${DOUBLETAKE_COMMIT}
license=LGPL-3.0-or-later AND GPL-3.0-or-later
purpose=experimental AirPlay sender for LiMaD auf TV übertragen
security_status=experimental; disabled until explicitly started by an active local user
PROVENANCE

chmod 0755 /usr/local/bin/limad-screen-share /usr/local/bin/limad-screen-share-firewall
chmod 0755 /usr/share/limad-screen-share/app.py

for element in pipewiresrc audioconvert h264parse; do
  gst-inspect-1.0 "$element" >/dev/null 2>&1 || {
    echo "FATAL: required GStreamer element missing: ${element}" >&2
    exit 1
  }
done

update-desktop-database /usr/share/applications 2>/dev/null || true

echo ":: LiMaD auf TV übertragen installed"

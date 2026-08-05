#!/usr/bin/env bash
# Reconstructs the Anycubic Slicer Next native Linux package from the two
# losslessly split, checksummed DEB parts and installs it into the image.
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/versions.env"
VENDOR_DIR="$SCRIPT_DIR/vendor/anycubic"
DEB_NAME="anycubicslicernext_${ANYCUBIC_DEB_VERSION}_amd64.deb"
PART_GLOB="$VENDOR_DIR/${DEB_NAME}.part"
APP_ROOT=/usr/lib/limad/apps/anycubic-slicer-next
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
DEB="$TMP/$DEB_NAME"

mapfile -t PARTS < <(find "$VENDOR_DIR" -maxdepth 1 -type f -name "${DEB_NAME}.part[0-9][0-9]" -print | sort)
test "${#PARTS[@]}" -eq 2
for part in "${PARTS[@]}"; do test -s "$part"; done
(cd "$VENDOR_DIR" && sha256sum -c SHA256SUMS)
cat "${PARTS[@]}" > "$DEB"
printf '%s  %s\n' "$ANYCUBIC_SOURCE_SHA256" "$DEB" | sha256sum -c -
command -v ar >/dev/null
command -v tar >/dev/null
mkdir -p "$TMP/deb" "$TMP/root"
(cd "$TMP/deb" && ar x "$DEB")
DATA_ARCHIVE="$(find "$TMP/deb" -maxdepth 1 -type f -name 'data.tar.*' -print -quit)"
test -n "$DATA_ARCHIVE"
tar -xf "$DATA_ARCHIVE" -C "$TMP/root"

test -x "$TMP/root/usr/bin/AnycubicSlicerNext"
test -d "$TMP/root/usr/share/AnycubicSlicerNext/resources"

rm -rf "$APP_ROOT"
install -d -m 0755 "$APP_ROOT/bin" "$APP_ROOT/lib" "$APP_ROOT/resources"
install -m 0755 "$TMP/root/usr/bin/AnycubicSlicerNext" "$APP_ROOT/bin/AnycubicSlicerNext"
find "$TMP/root/usr/lib" -maxdepth 1 -type f \( -name '*.so' -o -name '*.so.*' -o -name '*.a' \) -exec install -m 0644 {} "$APP_ROOT/lib/" \;
cp -a "$TMP/root/usr/share/AnycubicSlicerNext/resources/." "$APP_ROOT/resources/"
printf '%s\n' "$ANYCUBIC_DEB_VERSION" > "$APP_ROOT/PACKAGE-VERSION"
printf '%s\n' "$ANYCUBIC_BUILD_VERSION" > "$APP_ROOT/BUILD-VERSION"
printf '%s\n' "$ANYCUBIC_SOURCE_SHA256" > "$APP_ROOT/SOURCE-SHA256"

rm -rf /usr/share/AnycubicSlicerNext
ln -s /usr/lib/limad/apps/anycubic-slicer-next /usr/share/AnycubicSlicerNext
chmod 0755 "$APP_ROOT/bin/AnycubicSlicerNext"
test "$(cat "$APP_ROOT/PACKAGE-VERSION")" = "$ANYCUBIC_DEB_VERSION"
test "$(cat "$APP_ROOT/BUILD-VERSION")" = "$ANYCUBIC_BUILD_VERSION"
echo "Anycubic Slicer Next ${ANYCUBIC_DEB_VERSION} (${ANYCUBIC_BUILD_VERSION}) installed from one reconstructed and verified native Linux package source."

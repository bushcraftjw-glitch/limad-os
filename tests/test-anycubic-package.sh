#!/usr/bin/env bash
# Anycubic Slicer Next is the only vendored binary payload in this repository.
# It must stay a losslessly split, checksummed native Linux package that the
# build reconstructs and verifies - never an unpacked binary tree.
set -Eeuo pipefail
cd "$(dirname "$0")/.."

# shellcheck source=/dev/null
source build_files/versions.env

vendor="build_files/vendor/anycubic"
base="anycubicslicernext_${ANYCUBIC_DEB_VERSION}_amd64.deb"

fail() { echo "ANYCUBIC AUDIT FAILED: $*" >&2; exit 1; }

# 1. The vendored source: two parts, no reassembled package, matching sums.
[[ -e "${vendor}/${base}" ]] && fail "the reassembled package must never be committed"
# Deliberately array-free: this suite also runs on macOS with bash 3.2.
parts=""
part_count=0
while IFS= read -r part; do
  parts="${parts} ${part}"
  part_count=$((part_count + 1))
done < <(find "$vendor" -maxdepth 1 -type f -name "${base}.part[0-9][0-9]" | sort)
[[ "$part_count" -eq 2 ]] || fail "expected two package parts, found ${part_count}"
(cd "$vendor" && sha256sum -c SHA256SUMS >/dev/null) || fail "part checksums do not match"
grep -Fq "$ANYCUBIC_SOURCE_SHA256" "${vendor}/PACKAGE-SHA256" \
  || fail "ANYCUBIC_SOURCE_SHA256 does not match PACKAGE-SHA256"

# 2. Reassemble and verify exactly as the build does, then look inside.
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
# shellcheck disable=SC2086
cat ${parts} > "${tmp}/${base}"
printf '%s  %s\n' "$ANYCUBIC_SOURCE_SHA256" "${tmp}/${base}" | sha256sum -c - >/dev/null \
  || fail "the reassembled package does not match its recorded checksum"

if command -v ar >/dev/null 2>&1; then
  (cd "$tmp" && ar x "$base")
  tar -xf "$tmp"/data.tar.* -C "$tmp"
  [[ -x "$tmp/usr/bin/AnycubicSlicerNext" ]] || fail "no executable in the package"
  [[ -d "$tmp/usr/share/AnycubicSlicerNext/resources" ]] || fail "resources missing"
  if command -v file >/dev/null 2>&1; then
    file "$tmp/usr/bin/AnycubicSlicerNext" | grep -q 'ELF 64-bit.*x86-64' \
      || fail "the binary is not a 64-bit x86 ELF executable"
  fi
else
  echo "note: 'ar' unavailable, package contents not inspected locally"
fi

# 3. The launcher and the build step agree on where the application lives.
launcher="system_files/usr/bin/anycubicslicernext"
[[ -f "$launcher" ]] || fail "launcher missing"
grep -Fq 'APP_ROOT=/usr/lib/limad/apps/anycubic-slicer-next' "$launcher" \
  || fail "launcher does not use the canonical application path"
grep -Fq 'ANYCUBIC_RESOURCES_PATH="$APP_ROOT/resources"' "$launcher" \
  || fail "launcher does not point at the bundled resources"

step="build_files/60-anycubic-slicer.sh"
[[ -x "$step" ]] || fail "build step ${step} missing or not executable"
grep -Fq 'cat "${PARTS[@]}" > "$DEB"' "$step" || fail "build step does not reassemble the parts"
grep -Fq 'ln -s /usr/lib/limad/apps/anycubic-slicer-next /usr/share/AnycubicSlicerNext' "$step" \
  || fail "build step does not create the resource symlink"
grep -Fq '60-anycubic-slicer.sh' build_files/build.sh || fail "build step is never called"

# 4. GNOME integration: desktop entry, metainfo, icon.
entry="system_files/usr/share/applications/de.limad.AnycubicSlicerNext.desktop"
[[ -f "$entry" ]] || fail "desktop entry missing"
grep -Fq 'Exec=/usr/bin/anycubicslicernext %F' "$entry" || fail "desktop entry has the wrong Exec line"
grep -Fq 'Icon=de.limad.AnycubicSlicerNext' "$entry" || fail "desktop entry has the wrong icon"
[[ -f system_files/usr/share/metainfo/de.limad.AnycubicSlicerNext.metainfo.xml ]] \
  || fail "metainfo missing"
[[ -f system_files/usr/share/icons/LiMaD/scalable/apps/de.limad.AnycubicSlicerNext.svg ]] \
  || fail "the LiMaD icon for Anycubic is missing"
grep -Fq 'de.limad.AnycubicSlicerNext.desktop' \
  system_files/usr/share/glib-2.0/schemas/zzzzzzzzzz-limad-defaults.gschema.override \
  || fail "Anycubic is not pinned to the GNOME dock"

echo "Anycubic Slicer Next package integrity and GNOME integration: PASS"

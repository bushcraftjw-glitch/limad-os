#!/usr/bin/env bash
set -Eeuo pipefail
ROOTFS="${1:?Aufruf: build-all-updates.sh ROOTFS OUTPUT_DIR}"
OUT="${2:?Aufruf: build-all-updates.sh ROOTFS OUTPUT_DIR}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$REPO_ROOT/build_files/versions.env"
mkdir -p "$OUT"
rm -f "$OUT"/*.limad-update.zip "$OUT"/*.sha256 "$OUT/SHA256SUMS" 2>/dev/null || true
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

build_one() {
  local app_id="$1" version="$2" source_rel="$3" label="$4" slug="$5"
  local src="$ROOTFS$source_rel"
  [[ -d "$src" ]] || { echo "WARNUNG: $label fehlt in RootFS: $source_rel" >&2; return 0; }
  local stage="$TMP/$slug"
  mkdir -p "$stage"
  rsync -aL --delete "$src/" "$stage/"
  find "$stage" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
  local zip="$OUT/${slug}-${version}.limad-update.zip"
  python3 "$REPO_ROOT/tools/build-limad-update.py" --app-id "$app_id" --version "$version" --payload "$stage" --output "$zip" --name "$label"
  sha256sum "$zip" > "$zip.sha256"
}

version_file() {
  local rel="$1" fallback="$2"
  if [[ -s "$ROOTFS$rel" ]]; then tr -d '\r\n' < "$ROOTFS$rel"; else printf '%s' "$fallback"; fi
}

build_one de.limad.Cut "$(version_file /usr/share/limad-cut/VERSION "$LIMAD_CUT_VERSION")" /usr/share/limad-cut 'LiMaD Cut' 'LiMaD-Cut'
build_one de.limad.Study "$(version_file /usr/share/limad-study/VERSION "$LIMAD_STUDY_VERSION")" /usr/share/limad-study 'LiMaD Study' 'LiMaD-Study'
build_one de.limad.Drop "$(version_file /usr/share/limad-drop/VERSION "$LIDROP_VERSION")" /usr/share/limad-drop 'LiDrop' 'LiDrop'
build_one de.limad.Link "$(version_file /usr/share/limad-link/VERSION "$LILINK_VERSION")" /usr/share/limad-link 'LiLink' 'LiLink'
build_one de.limad.Notes "$(version_file /usr/share/limad-notes/VERSION "$LINOTES_VERSION")" /usr/share/limad-notes 'LiNotes' 'LiNotes'
build_one de.limad.Save "$(version_file /usr/share/limad-save/VERSION "$LISAVE_VERSION")" /usr/share/limad-save 'LiSave' 'LiSave'
build_one de.limad.ScreenShare "$(version_file /usr/share/limad-screen-share/VERSION "$LIMAD_SCREEN_SHARE_VERSION")" /usr/share/limad-screen-share 'LiMaD auf TV übertragen' 'LiMaD-ScreenShare'
build_one de.limad.Mail "$(version_file /usr/share/limad-mail/VERSION "$LIMAD_MAIL_VERSION")" /usr/share/limad-mail 'LiMaD Mail' 'LiMaD-Mail'
build_one de.limad.Klang "$(version_file /usr/share/limad-klang/VERSION "$LIMAD_KLANG_VERSION")" /usr/share/limad-klang 'LiMaD Klang' 'LiMaD-Klang'
build_one de.limad.AnycubicSlicerNext "$ANYCUBIC_DEB_VERSION" /usr/lib/limad/apps/anycubic-slicer-next 'Anycubic Slicer Next' 'Anycubic-Slicer-Next'
build_one de.limad.WindowsApps "$(version_file /usr/share/limad-windows/VERSION "$LIMAD_WINDOWS_VERSION")" /usr/share/limad-windows 'Windows-Programme' 'LiMaD-Windows-Programme'
(
  cd "$OUT"
  find . -maxdepth 1 -type f -name '*.limad-update.zip' -printf '%f\n' | sort | xargs -r sha256sum > SHA256SUMS
)
cat > "$OUT/README.txt" <<TXT
LiMaD OS ${LIMAD_OS_VERSION} – eigenständige Updatepakete

Diese ZIP-Dateien sind für LiMaD Updates gedacht und können unabhängig von der OS-ISO verteilt werden.
LiMaD Mail enthält nur die LiMaD-Integration/Theme-Schicht; Thunderbird selbst wird separat über Flatpak aktualisiert.
LiMaD Klang enthält die LiMaD-Steuerung/Preset-Schicht; EasyEffects selbst wird separat über Flatpak aktualisiert.
TXT
echo "Updatepakete: $OUT"

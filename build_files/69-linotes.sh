#!/usr/bin/env bash
set -Eeuo pipefail
source /ctx/build_files/versions.env

echo ":: Installing LiNotes ${LINOTES_VERSION}"
for file in \
  /usr/share/limad-notes/VERSION \
  /usr/share/limad-notes/app.py \
  /usr/share/limad-notes/storage.py \
  /usr/local/bin/limad-notes \
  /usr/share/applications/de.limad.Notes.desktop \
  /usr/share/metainfo/de.limad.Notes.metainfo.xml \
  /usr/share/icons/hicolor/scalable/apps/de.limad.Notes.svg \
  /usr/share/icons/LiMaD/scalable/apps/de.limad.Notes.svg; do
  [[ -s "$file" ]] || { echo "FATAL: LiNotes file missing: $file" >&2; exit 1; }
done
[[ "$(tr -d '[:space:]' </usr/share/limad-notes/VERSION)" == "$LINOTES_VERSION" ]] || { echo "FATAL: LiNotes version mismatch" >&2; exit 1; }
chmod 0755 /usr/local/bin/limad-notes /usr/share/limad-notes/app.py
chmod 0644 /usr/share/applications/de.limad.Notes.desktop /usr/share/metainfo/de.limad.Notes.metainfo.xml
python3 -m py_compile /usr/share/limad-notes/app.py /usr/share/limad-notes/storage.py
desktop-file-validate /usr/share/applications/de.limad.Notes.desktop
for size in 16 22 24 32 48 64 128 256 512; do
  [[ -s "/usr/share/icons/hicolor/${size}x${size}/apps/de.limad.Notes.png" ]] || { echo "FATAL: LiNotes hicolor icon ${size}px missing" >&2; exit 1; }
  [[ -s "/usr/share/icons/LiMaD/${size}x${size}/apps/de.limad.Notes.png" ]] || { echo "FATAL: LiNotes LiMaD icon ${size}px missing" >&2; exit 1; }
done
echo ":: LiNotes step done"

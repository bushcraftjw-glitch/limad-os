#!/usr/bin/env bash
# Installs a pinned Logo Menu GNOME Shell extension system-wide and refuses to
# install a release that does not declare compatibility with the GNOME Shell
# major version in the base image.
set -Eeuo pipefail
source /ctx/build_files/versions.env

readonly EXT_UUID="logomenu@aryan_k"
readonly EXT_DIR="/usr/share/gnome-shell/extensions/${EXT_UUID}"
readonly ARCHIVE_URL="https://github.com/Aryan20/Logomenu/archive/refs/tags/${LIMAD_LOGOMENU_VERSION}.zip"

echo ":: Installing Logo Menu ${LIMAD_LOGOMENU_VERSION}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

command -v gnome-shell >/dev/null 2>&1 || {
  echo "FATAL: gnome-shell is missing from the GNOME base image" >&2
  exit 1
}
GNOME_MAJOR="$(gnome-shell --version | sed -nE 's/.* ([0-9]+)(\.[0-9]+)*/\1/p' | head -n1)"
[[ "$GNOME_MAJOR" =~ ^[0-9]+$ ]] || {
  echo "FATAL: could not determine the GNOME Shell major version" >&2
  gnome-shell --version >&2 || true
  exit 1
}

echo "   GNOME Shell major: ${GNOME_MAJOR}"
if ! curl -fsSL --retry 3 --retry-delay 3 -o "${TMP}/src.zip" "$ARCHIVE_URL"; then
  echo "FATAL: could not download ${ARCHIVE_URL}" >&2
  exit 1
fi

install -d "${TMP}/src"
python3 - "${TMP}/src.zip" "${TMP}/src" <<'PY'
import sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as archive:
    archive.extractall(sys.argv[2])
PY

mapfile -t TOP_LEVEL < <(find "${TMP}/src" -mindepth 1 -maxdepth 1 -type d -print)
if [[ "${#TOP_LEVEL[@]}" -ne 1 ]]; then
  echo "FATAL: expected one top-level directory in Logo Menu archive, found ${#TOP_LEVEL[@]}" >&2
  find "${TMP}/src" -mindepth 1 -maxdepth 1 -print >&2
  exit 1
fi
readonly SRC_ROOT="${TOP_LEVEL[0]}"
readonly METADATA="${SRC_ROOT}/metadata.json"

[[ -s "$METADATA" ]] || { echo "FATAL: Logo Menu metadata.json missing" >&2; exit 1; }
[[ -s "${SRC_ROOT}/extension.js" ]] || { echo "FATAL: Logo Menu extension.js missing" >&2; exit 1; }

python3 - "$METADATA" "$EXT_UUID" "$GNOME_MAJOR" "$LIMAD_LOGOMENU_VERSION" <<'PY'
import json, sys
path, expected_uuid, gnome_major, pinned_tag = sys.argv[1:]
with open(path, encoding='utf-8') as handle:
    data = json.load(handle)
if data.get('uuid') != expected_uuid:
    raise SystemExit(f'FATAL: Logo Menu UUID mismatch: {data.get("uuid")!r}')
supported = {str(v) for v in data.get('shell-version', [])}
if gnome_major not in supported:
    raise SystemExit(
        f'FATAL: Logo Menu {pinned_tag} supports GNOME Shell {sorted(supported)}, '
        f'but the base image contains GNOME Shell {gnome_major}'
    )
print(f'   metadata compatibility: GNOME Shell {gnome_major} supported')
PY


# GNOME Shell 50 no longer provides a parent StWidget vfunc_event implementation.
# Logo Menu 24.8 calls super.vfunc_event(event), which produces repeated runtime
# errors on GNOME 50. Replace only that unsupported fallback with propagation.
python3 - "${SRC_ROOT}/extension.js" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text(encoding='utf-8')
old = 'return super.vfunc_event(event);'
if old not in text:
    raise SystemExit('FATAL: expected Logo Menu vfunc_event fallback was not found')
path.write_text(text.replace(old, 'return Clutter.EVENT_PROPAGATE;', 1), encoding='utf-8')
print('   patched Logo Menu GNOME 50 vfunc_event fallback')
PY

rm -rf "$EXT_DIR"
install -d "$EXT_DIR"
cp -a "${SRC_ROOT}/metadata.json" "${SRC_ROOT}/extension.js" "$EXT_DIR/"
for optional in prefs.js stylesheet.css constants.js display_module.js selection.js Resources PrefsLib schemas locale po; do
  [[ -e "${SRC_ROOT}/${optional}" ]] && cp -a "${SRC_ROOT}/${optional}" "$EXT_DIR/"
done

if [[ -d "${EXT_DIR}/schemas" ]]; then
  python3 /ctx/build_files/patch-logomenu-schema.py "${EXT_DIR}/schemas"
  glib-compile-schemas "${EXT_DIR}/schemas"
  install -d /usr/share/glib-2.0/schemas
  # A base image may already ship the same schema ID under another filename.
  # GLib rejects duplicate IDs, so remove only previous global definitions of
  # Logo Menu before installing the pinned and patched LiMaD copy.
  while IFS= read -r existing_schema; do
    [[ -n "$existing_schema" ]] || continue
    rm -f "$existing_schema"
    echo "   removed conflicting global Logo Menu schema: ${existing_schema}"
  done < <(grep -Il 'id="org.gnome.shell.extensions.logo-menu"'     /usr/share/glib-2.0/schemas/*.gschema.xml 2>/dev/null || true)
  mapfile -t LOGOMENU_SCHEMAS < <(find "${EXT_DIR}/schemas" -maxdepth 1 -type f -name '*.gschema.xml' -print | sort)
  ((${#LOGOMENU_SCHEMAS[@]} > 0)) || {
    echo "FATAL: Logo Menu schemas directory contains no .gschema.xml file" >&2
    exit 1
  }
  for schema in "${LOGOMENU_SCHEMAS[@]}"; do
    install -m 0644 "$schema" "/usr/share/glib-2.0/schemas/95-limad-logomenu-$(basename "$schema")"
  done
fi

[[ -s "${EXT_DIR}/metadata.json" && -s "${EXT_DIR}/extension.js" ]] || {
  echo "FATAL: Logo Menu runtime files were not installed" >&2
  exit 1
}

echo "   Logo Menu installed at ${EXT_DIR}"

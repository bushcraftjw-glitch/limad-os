#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."

fail() { echo "WALLPAPER OVERRIDE HARDENING FAILED: $*" >&2; exit 1; }

TOOL="build_files/enforce-gnome-wallpaper.py"
[[ -x "$TOOL" ]] || fail "wallpaper normalization helper missing or not executable"
grep -q 'enforce-gnome-wallpaper.py' build_files/50-gnome-defaults.sh \
  || fail "GNOME defaults step does not invoke the helper"
grep -q 'zzzzzzzzzz-limad-wallpaper.gschema.override' "$TOOL" \
  || fail "canonical late override name missing"

TMP="$(mktemp -d)"
cleanup() { rm -rf -- "$TMP"; }
trap cleanup EXIT INT TERM
mkdir -p "$TMP/schemas" "$TMP/backgrounds"
touch "$TMP/backgrounds/LiMaD-Wallpaper.png"

cat > "$TMP/schemas/10-base.gschema.override" <<'DATA'
[org.gnome.desktop.background]
picture-uri='file:///usr/share/backgrounds/base.xml'
picture-uri-dark='file:///usr/share/backgrounds/base-dark.xml'
picture-options='scaled'

[org.gnome.desktop.interface]
color-scheme='prefer-dark'
DATA

cat > "$TMP/schemas/zzzzzzzzzzzz-upstream.gschema.override" <<'DATA'
[org.gnome.desktop.background]
picture-uri='file:///usr/share/backgrounds/convergence-dynamic.xml'
picture-uri-dark='file:///usr/share/backgrounds/convergence-dynamic.xml'

[org.gnome.desktop.screensaver]
picture-uri='file:///usr/share/backgrounds/convergence-dynamic.xml'
DATA

python3 "$TOOL" "$TMP/schemas" "$TMP/backgrounds/LiMaD-Wallpaper.png" >"$TMP/wallpaper-test.log"

canonical="$TMP/schemas/zzzzzzzzzz-limad-wallpaper.gschema.override"
[[ -f "$canonical" ]] || fail "canonical override not created"
wallpaper_uri="file://$(cd "$TMP/backgrounds" && pwd -P)/LiMaD-Wallpaper.png"

while IFS= read -r file; do
  while IFS= read -r line; do
    case "$line" in
      picture-uri=*|picture-uri-dark=*)
        [[ "$line" == *"'$wallpaper_uri'" ]] || fail "conflicting wallpaper remains in $(basename "$file"): $line"
        ;;
      picture-options=*)
        [[ "$line" == "picture-options='zoom'" ]] || fail "conflicting picture-options remains in $(basename "$file"): $line"
        ;;
    esac
  done < "$file"
done < <(find "$TMP/schemas" -maxdepth 1 -type f -name '*.gschema.override' -print | LC_ALL=C sort)

echo "synthetic conflicting override normalization: PASS"
echo "Wallpaper override conflict hardening: PASS"

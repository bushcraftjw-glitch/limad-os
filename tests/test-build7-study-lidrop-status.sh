#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ "$(cat "$ROOT/VERSION")" == "2.8.0-rc2-gnome-rc2-build5" ]]
[[ "$(cat "$ROOT/system_files/usr/share/limad-study/VERSION")" == "6.6.3" ]]
[[ "$(cat "$ROOT/system_files/usr/share/limad-drop/VERSION")" == "0.12.0-preview5" ]]
grep -Fq "X-LiMaD-Version=0.12.0-preview5" "$ROOT/system_files/usr/share/applications/de.limad.Drop.desktop"
grep -Fq "de.limad.Drop.desktop" "$ROOT/system_files/usr/share/glib-2.0/schemas/zzzzzzzzzz-limad-defaults.gschema.override"
grep -Fq "lidrop@limad.local" "$ROOT/system_files/usr/share/glib-2.0/schemas/zzzzzzzzzz-limad-defaults.gschema.override"
grep -Fq "enable_extension lidrop@limad.local" "$ROOT/system_files/usr/local/bin/limad-first-login-setup"
python3 -m json.tool "$ROOT/system_files/usr/share/gnome-shell/extensions/lidrop@limad.local/metadata.json" >/dev/null
[[ -s "$ROOT/system_files/usr/share/gnome-shell/extensions/lidrop@limad.local/extension.js" ]]
[[ -s "$ROOT/system_files/usr/share/gnome-shell/extensions/lidrop@limad.local/icons/lidrop-symbolic.svg" ]]
echo "Build 8 Study, LiDrop, dock and GNOME status integration: PASS"

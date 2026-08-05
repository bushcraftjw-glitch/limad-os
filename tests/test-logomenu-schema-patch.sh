#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."

fail() { echo "LOGO MENU SCHEMA PATCH FAILED: $*" >&2; exit 1; }
TOOL=build_files/patch-logomenu-schema.py
[[ -x "$TOOL" ]] || fail "schema patch helper missing or not executable"
grep -q 'patch-logomenu-schema.py' build_files/45-logomenu-extension.sh \
  || fail "Logo Menu build step does not invoke schema patch helper"
grep -q 'removed conflicting global Logo Menu schema' build_files/45-logomenu-extension.sh \
  || fail "duplicate global schema protection missing"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/schemas"
cat > "$TMP/schemas/org.gnome.shell.extensions.logo-menu.gschema.xml" <<'XML'
<?xml version="1.0" encoding="UTF-8"?>
<schemalist>
  <schema path="/org/gnome/shell/extensions/Logo-menu/" id="org.gnome.shell.extensions.logo-menu">
    <key type="i" name="menu-button-icon-image"><default>0</default></key>
    <key type="i" name="menu-button-icon-size"><default>25</default></key>
    <key type="b" name="use-custom-icon"><default>false</default></key>
    <key type="s" name="custom-icon-path"><default>"''"</default></key>
    <key type="b" name="show-activities-button"><default>true</default></key>
    <key type="b" name="hide-icon-shadow"><default>false</default></key>
    <key type="b" name="symbolic-icon"><default>true</default></key>
  </schema>
</schemalist>
XML
python3 "$TOOL" "$TMP/schemas" >/tmp/limad-logomenu-schema-test.log
python3 - "$TMP/schemas/org.gnome.shell.extensions.logo-menu.gschema.xml" <<'PY'
import sys
import xml.etree.ElementTree as ET
values = {}
for key in ET.parse(sys.argv[1]).getroot().iter('key'):
    default = key.find('default')
    if default is not None:
        values[key.get('name')] = default.text
expected = {
    'menu-button-icon-image': '0',
    'menu-button-icon-size': '24',
    'use-custom-icon': 'true',
    'custom-icon-path': "'/usr/share/icons/LiMaD/64x64/apps/limad-start.png'",
    'show-activities-button': 'false',
    'hide-icon-shadow': 'true',
    'symbolic-icon': 'false',
}
for key, value in expected.items():
    if values.get(key) != value:
        raise SystemExit(f'{key} is {values.get(key)!r}, expected {value!r}')
print('Logo Menu schema custom LiMaD defaults: PASS')
PY

#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."

fail() { echo "WINDOW BUTTON HARDENING FAILED: $*" >&2; exit 1; }

TOOL="build_files/enforce-gnome-button-layout.py"
[[ -x "$TOOL" ]] || fail "window-button normalization helper missing or not executable"
grep -q 'enforce-gnome-button-layout.py' build_files/50-gnome-defaults.sh \
  || fail "GNOME defaults step does not invoke the helper"
grep -q "button-layout='close,maximize,minimize:'" \
  system_files/usr/share/glib-2.0/schemas/zzzzzzzzzz-limad-defaults.gschema.override \
  || fail "FIX22 left-side button order changed in the source defaults"
grep -q "button-layout 'close,maximize,minimize:'" \
  system_files/usr/local/bin/limad-first-login-setup \
  || fail "FIX22 left-side button order changed in first-login migration"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/schemas"
cat > "$TMP/schemas/10-fedora.gschema.override" <<'EOF'
[org.gnome.desktop.wm.preferences]
button-layout='appmenu:minimize,maximize,close'
EOF
cat > "$TMP/schemas/zzzzzz-upstream.gschema.override" <<'EOF'
[org.gnome.desktop.wm.preferences]
button-layout=':minimize,maximize,close'
EOF
python3 "$TOOL" "$TMP/schemas" >/tmp/limad-window-buttons-test.log
python3 - "$TMP/schemas" <<'PY'
import re
import sys
from pathlib import Path
schema_dir = Path(sys.argv[1])
expected = "'close,maximize,minimize:'"
canonical = schema_dir / 'zzzzzzzzzzz-limad-window-buttons.gschema.override'
if not canonical.is_file():
    raise SystemExit('canonical window-button override not created')
for path in schema_dir.glob('*.gschema.override'):
    for value in re.findall(r'^button-layout=(.*)$', path.read_text(), re.M):
        if value != expected:
            raise SystemExit(f'wrong button layout remains in {path.name}: {value}')
print('synthetic conflicting window-button normalization: PASS')
PY

echo "FIX22 macOS-style left window buttons hardening: PASS"

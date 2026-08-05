#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."

fail() { echo "FIRST-LOGIN RUNTIME FAILED: $*" >&2; exit 1; }
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/home"
LOG="$TMP/gsettings.log"

cat > "$TMP/bin/gsettings" <<'FAKE'
#!/usr/bin/env bash
set -u
case "${1-}" in
  list-schemas)
    cat <<'EOF'
org.gnome.desktop.interface
org.gnome.desktop.background
org.gnome.desktop.screensaver
org.gnome.desktop.wm.preferences
org.gnome.shell
org.gnome.shell.extensions.user-theme
org.gnome.shell.extensions.dash-to-dock
org.gnome.shell.extensions.logo-menu
EOF
    ;;
  writable)
    printf '%s\n' true
    ;;
  get)
    if [[ "${2-}" == org.gnome.shell && "${3-}" == favorite-apps ]]; then
      printf "%s\n" "['org.gnome.Nautilus.desktop', 'de.limad.Study.desktop']"
    else
      printf "%s\n" "''"
    fi
    ;;
  set)
    printf '%s\t%s\t%s\n' "${2-}" "${3-}" "${4-}" >> "$LIMAD_TEST_GSETTINGS_LOG"
    ;;
  *) exit 2 ;;
esac
FAKE
chmod 0755 "$TMP/bin/gsettings"

cat > "$TMP/bin/gnome-extensions" <<'FAKE'
#!/usr/bin/env bash
case "${1-}" in
  info|enable) exit 0 ;;
  *) exit 2 ;;
esac
FAKE
chmod 0755 "$TMP/bin/gnome-extensions"

export PATH="$TMP/bin:/usr/bin:/bin"
export HOME="$TMP/home"
export XDG_CONFIG_HOME="$TMP/home/.config"
export LIMAD_TEST_GSETTINGS_LOG="$LOG"
bash system_files/usr/local/bin/limad-first-login-setup
[[ -s "$LOG" ]] || fail "first run did not apply settings"

python3 - "$LOG" <<'PY'
import ast
import sys
from pathlib import Path
entries = [line.split('\t', 2) for line in Path(sys.argv[1]).read_text().splitlines()]
settings = {(schema, key): value for schema, key, value in entries}
expected_buttons = "close,maximize,minimize:"
if settings.get(('org.gnome.desktop.wm.preferences', 'button-layout')) != expected_buttons:
    raise SystemExit('FIX22 left-side window buttons were not applied exactly')
favorites = ast.literal_eval(settings[('org.gnome.shell', 'favorite-apps')])
expected = [
    'app.zen_browser.zen.desktop',
    'de.limad.Mail.desktop',
    'de.limad.Cut.desktop',
    'de.limad.Study.desktop',
    'de.limad.Notes.desktop',
    'de.limad.Drop.desktop',
    'de.limad.Link.desktop',
    'de.limad.Save.desktop',
    'de.limad.WindowsApps.desktop',
    'de.limad.Updater.desktop',
    'de.limad.AnycubicSlicerNext.desktop',
    'us.zoom.Zoom.desktop',
    'app.ytmdesktop.ytmdesktop.desktop',
    'org.libreoffice.LibreOffice.desktop',
    'de.limad.Klang.desktop',
    'de.limad.Terminal.desktop',
    'io.github.kolunmi.Bazaar.desktop',
    'org.gnome.Nautilus.desktop',
]
if favorites != expected:
    raise SystemExit(f'RC2 dock order is wrong: {favorites}')
logo = settings.get(('org.gnome.shell.extensions.logo-menu', 'custom-icon-path'))
if logo != "/usr/share/icons/LiMaD/64x64/apps/limad-start.png":
    raise SystemExit(f'wrong Logo Menu path: {logo}')
if settings.get(('org.gnome.shell.extensions.logo-menu', 'use-custom-icon')) != 'true':
    raise SystemExit('Logo Menu custom icon switch was not enabled')
PY

before="$(wc -l < "$LOG" | tr -d ' ')"
bash system_files/usr/local/bin/limad-first-login-setup
after="$(wc -l < "$LOG" | tr -d ' ')"
[[ "$before" == "$after" ]] || fail "version marker did not prevent a duplicate migration"
[[ -f "$XDG_CONFIG_HOME/limad/first-login-2.8.0-rc2-build5.done" ]] \
  || fail "RC2 first-login marker missing"

echo "First-login FIX22 buttons, Logo Menu and dock migration runtime: PASS"

#!/usr/bin/env bash
# Applies the LiMaD GNOME defaults: schema overrides, wallpaper, flatpak theming.
set -Eeuo pipefail

# shellcheck source=/dev/null
source /opt/limad-build/versions.env

readonly SCHEMA_DIR="/usr/share/glib-2.0/schemas"

# The MacTahoe installer decides the final theme names; step 20 recorded them.
if [[ -f /usr/share/limad/theme-names.env ]]; then
  # shellcheck source=/dev/null
  source /usr/share/limad/theme-names.env
fi
LIMAD_GTK_THEME_VARIANT="${LIMAD_GTK_THEME_ACTUAL:-$LIMAD_GTK_THEME_VARIANT}"
LIMAD_SHELL_THEME_VARIANT="${LIMAD_SHELL_THEME_ACTUAL:-$LIMAD_SHELL_THEME_VARIANT}"

echo ":: Verifying that the themes referenced by the defaults exist"
[[ -d "/usr/share/themes/${LIMAD_GTK_THEME_VARIANT}" ]] \
  || { echo "FATAL: GTK theme ${LIMAD_GTK_THEME_VARIANT} missing" >&2; ls -1 /usr/share/themes >&2; exit 1; }

echo ":: Writing the detected theme names into the defaults"
sed -i -e "s|^gtk-theme=.*|gtk-theme='${LIMAD_GTK_THEME_VARIANT}'|" \
       -e "s|^name='LiMaD-Dark'|name='${LIMAD_SHELL_THEME_VARIANT}'|" \
       "${SCHEMA_DIR}/zzzzzzzzzz-limad-defaults.gschema.override"
echo "   GTK: ${LIMAD_GTK_THEME_VARIANT}, Shell: ${LIMAD_SHELL_THEME_VARIANT}"
[[ -d "/usr/share/icons/${LIMAD_ICON_THEME_NAME}" ]] \
  || { echo "FATAL: icon theme ${LIMAD_ICON_THEME_NAME} missing" >&2; exit 1; }

# The cursor theme is optional: WhiteSur cursors are a separate upstream
# project. Fall back to the base image default rather than shipping a broken
# reference.
if [[ ! -d /usr/share/icons/WhiteSur-cursors ]]; then
  echo "   WhiteSur-cursors not present, falling back to Adwaita cursors"
  sed -i "s/^cursor-theme='WhiteSur-cursors'/cursor-theme='Adwaita'/" \
    "${SCHEMA_DIR}/zzzzzzzzzz-limad-defaults.gschema.override"
fi

# The shell theme only works together with the user-theme extension; if the
# extension is unavailable the shell must not be pointed at a missing theme.
if [[ ! -d /usr/share/gnome-shell/extensions/user-theme@gnome-shell-extensions.gcampax.github.com ]]; then
  echo "   WARNING: user-theme extension missing, shell keeps the default theme" >&2
fi

# Extensions can disappear or change between distribution releases. Listing
# an extension in enabled-extensions that was never actually installed leaves
# the visible result silently wrong. Prune any extension that did not make it
# onto disk before the default is written, so the shipped default always
# matches what actually got installed.
declare -A LIMAD_EXTENSION_DIRS=(
  [user-theme@gnome-shell-extensions.gcampax.github.com]=1
  [ubuntu-dock@ubuntu.com]=1
  [blur-my-shell@aunetx]=1
  [logomenu@aryan_k]=1
)
for ext_id in "${!LIMAD_EXTENSION_DIRS[@]}"; do
  if [[ ! -d "/usr/share/gnome-shell/extensions/${ext_id}" ]]; then
    echo "   WARNING: extension ${ext_id} was not installed (missing package?), removing it from enabled-extensions" >&2
    python3 - "${SCHEMA_DIR}/zzzzzzzzzz-limad-defaults.gschema.override" "$ext_id" <<'PY'
import re, sys
path, ext_id = sys.argv[1], sys.argv[2]
text = open(path, encoding="utf-8").read()
def strip(match):
    items = [i.strip() for i in match.group(1).split(",")]
    items = [i for i in items if i.strip("'\"") != ext_id]
    return "enabled-extensions=[" + ", ".join(items) + "]"
text = re.sub(r"enabled-extensions=\[(.*?)\]", strip, text)
open(path, "w", encoding="utf-8").write(text)
PY
  fi
done
if [[ ! -d /usr/share/gnome-shell/extensions/logomenu@aryan_k ]]; then
  echo "   WARNING: logo-menu extension missing, GNOME keeps the default Activities button" >&2
fi

echo ":: Selecting default wallpaper"
WALLPAPER=""
CANDIDATE="/usr/share/backgrounds/limad/${LIMAD_DEFAULT_WALLPAPER:-}"
if [[ -n "${LIMAD_DEFAULT_WALLPAPER:-}" && -f "$CANDIDATE" ]]; then
  WALLPAPER="$CANDIDATE"
else
  # Fall back to any LiMaD wallpaper, never to an upstream one.
  WALLPAPER="$(find /usr/share/backgrounds/limad -maxdepth 1 -type f -name 'LiMaD-*' | sort | head -n 1)"
fi

if [[ -n "$WALLPAPER" ]]; then
  echo "   ${WALLPAPER}"
  # A late filename alone is not sufficient when the base system ships another
  # wallpaper override. The helper writes a canonical LiMaD override and
  # normalizes every existing override that defines the same wallpaper keys.
  python3 /opt/limad-build/enforce-gnome-wallpaper.py "${SCHEMA_DIR}" "${WALLPAPER}"
else
  echo "   FATAL: no LiMaD wallpaper found" >&2
  exit 1
fi

# Preserve the already installed FIX22 window design exactly. Normalize only
# this one key so every upstream override resolves to the confirmed layout.
python3 /opt/limad-build/enforce-gnome-button-layout.py "${SCHEMA_DIR}"
python3 /opt/limad-build/enforce-gnome-favorite-apps.py "${SCHEMA_DIR}"

# The base image can ship preseeded dconf values which are stronger than GLib
# schema defaults. Install an unlocked system dconf database as a second layer;
# users can still choose a different wallpaper or icon afterwards.
install -d /etc/dconf/db/local.d /etc/dconf/profile
cat > /etc/dconf/db/local.d/zzzzzzzzzz-limad-branding <<EOF
[org/gnome/desktop/wm/preferences]
button-layout='close,maximize,minimize:'

[org/gnome/shell]
favorite-apps=['app.zen_browser.zen.desktop', 'de.limad.Mail.desktop', 'de.limad.Cut.desktop', 'de.limad.Study.desktop', 'de.limad.Notes.desktop', 'de.limad.Drop.desktop', 'de.limad.Link.desktop', 'de.limad.Save.desktop', 'de.limad.WindowsApps.desktop', 'de.limad.Updater.desktop', 'de.limad.AnycubicSlicerNext.desktop', 'us.zoom.Zoom.desktop', 'app.ytmdesktop.ytmdesktop.desktop', 'org.libreoffice.LibreOffice.desktop', 'de.limad.Klang.desktop', 'de.limad.Terminal.desktop', 'io.github.kolunmi.Bazaar.desktop', 'org.gnome.Nautilus.desktop']

[org/gnome/desktop/background]
picture-uri='file://${WALLPAPER}'
picture-uri-dark='file://${WALLPAPER}'
picture-options='zoom'

[org/gnome/desktop/screensaver]
picture-uri='file://${WALLPAPER}'
picture-options='zoom'

[org/gnome/shell/extensions/logo-menu]
custom-icon-path='/usr/share/icons/LiMaD/64x64/apps/limad-start.png'
menu-button-icon-image=0
menu-button-icon-size=24
symbolic-icon=false
hide-icon-shadow=true
show-activities-button=false
use-custom-icon=true
custom-icon=true

[org/gnome/shell/extensions/Logo-menu]
custom-icon-path='/usr/share/icons/LiMaD/64x64/apps/limad-start.png'
menu-button-icon-image=0
menu-button-icon-size=24
symbolic-icon=false
hide-icon-shadow=true
show-activities-button=false
use-custom-icon=true
custom-icon=true
EOF
if [[ ! -f /etc/dconf/profile/user ]]; then
  printf '%s\n' 'user-db:user' 'system-db:local' > /etc/dconf/profile/user
elif ! grep -Fxq 'system-db:local' /etc/dconf/profile/user; then
  printf '%s\n' 'system-db:local' >> /etc/dconf/profile/user
fi
command -v dconf >/dev/null 2>&1 && dconf update || true

# Logo Menu has changed its custom-icon switch between releases. In addition
# to the settings above, overwrite any bundled distro logo assets with the
# LiMaD L so a fallback can never expose foreign distribution branding.
LOGOMENU_DIR=/usr/share/gnome-shell/extensions/logomenu@aryan_k
if [[ -d "$LOGOMENU_DIR" ]]; then
  mapfile -t UPSTREAM_LOGOS < <(find "$LOGOMENU_DIR" -type f \
    \( -iname '*bazzite*.png' -o -iname '*bazzite*.svg' \
       -o -iname '*fedora*.png' -o -iname '*fedora*.svg' \
       -o -iname '*ublue*.png' -o -iname '*ublue*.svg' \) -print)
  for logo in "${UPSTREAM_LOGOS[@]}"; do
    case "$logo" in
      *.png) install -m 0644 /usr/share/icons/LiMaD/64x64/apps/limad-start.png "$logo" ;;
      *.svg)
        LOGO_B64="$(base64 /usr/share/icons/LiMaD/64x64/apps/limad-start.png | tr -d '\n')"
        cat > "$logo" <<SVG
<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"><image href="data:image/png;base64,${LOGO_B64}" width="64" height="64"/></svg>
SVG
        ;;
    esac
  done
  install -m 0644 /usr/share/icons/LiMaD/64x64/apps/limad-start.png "$LOGOMENU_DIR/limad-logo.png"
  printf '%s\n' "${#UPSTREAM_LOGOS[@]} built-in distro Logo Menu asset(s) replaced"
fi

# Make every shipped wallpaper selectable in Settings -> Appearance.
if [[ -f /usr/share/gnome-background-properties/limad-wallpapers.xml ]]; then
  MISSING=0
  while IFS= read -r file; do
    [[ -f "$file" ]] || { echo "   FATAL: wallpaper listed but missing: $file" >&2; MISSING=1; }
  done < <(grep -o '<filename>[^<]*</filename>' /usr/share/gnome-background-properties/limad-wallpapers.xml \
           | sed 's|</\?filename>||g')
  ((MISSING == 0)) || exit 1
  echo "   wallpaper list registered for Settings"
fi

echo ":: Compiling GLib schemas"
# gsettings only has to read the compiled defaults during the image build. Give
# it a throwaway home and memory backend so no real root dconf database is used.
export HOME="/tmp/limad-gsettings/home"
export XDG_CACHE_HOME="/tmp/limad-gsettings/cache"
export XDG_RUNTIME_DIR="/tmp/limad-gsettings/run"
export GSETTINGS_BACKEND="memory"
install -d -m 0700 "$HOME" "$XDG_CACHE_HOME/dconf" "$XDG_RUNTIME_DIR"

COMPILE_LOG="$(glib-compile-schemas "${SCHEMA_DIR}" 2>&1)" || {
  echo "$COMPILE_LOG" >&2
  echo "FATAL: schema compilation failed" >&2
  exit 1
}
# A single malformed line makes glib-compile-schemas discard a whole override
# file with nothing but a warning - and every default would be silently lost.
if grep -q 'limad' <<<"$COMPILE_LOG"; then
  echo "$COMPILE_LOG" | grep 'limad' >&2
  echo "FATAL: a LiMaD override file was rejected by glib-compile-schemas" >&2
  exit 1
fi

echo ":: Confirming the defaults are in effect"
for pair in "org.gnome.desktop.interface icon-theme ${LIMAD_ICON_THEME_NAME}" \
            "org.gnome.desktop.interface gtk-theme ${LIMAD_GTK_THEME_VARIANT}" \
            "org.gnome.desktop.interface color-scheme prefer-dark"; do
  set -- $pair
  actual="$(gsettings --schemadir "${SCHEMA_DIR}" get "$1" "$2" 2>/dev/null || echo '?')"
  if [[ "$actual" != *"$3"* ]]; then
    echo "FATAL: ${1} ${2} is ${actual}, expected ${3}" >&2
    exit 1
  fi
  echo "   ${2} = ${actual}"
done
wallpaper_actual="$(gsettings --schemadir "${SCHEMA_DIR}" get org.gnome.desktop.background picture-uri 2>/dev/null || echo '?')"
[[ "$wallpaper_actual" == *"${WALLPAPER}"* ]] || {
  echo "FATAL: default wallpaper is ${wallpaper_actual}, expected ${WALLPAPER}" >&2
  exit 1
}
echo "   picture-uri = ${wallpaper_actual}"
button_layout_actual="$(gsettings --schemadir "${SCHEMA_DIR}" get org.gnome.desktop.wm.preferences button-layout 2>/dev/null || echo '?')"
[[ "$button_layout_actual" == "'close,maximize,minimize:'" ]] || {
  echo "FATAL: window buttons are ${button_layout_actual}, expected FIX22 left-side layout" >&2
  exit 1
}
echo "   button-layout = ${button_layout_actual}"
shell_theme_actual="$(gsettings --schemadir "${SCHEMA_DIR}" get org.gnome.shell.extensions.user-theme name 2>/dev/null || echo '?')"
[[ "$shell_theme_actual" == "'${LIMAD_SHELL_THEME_VARIANT}'" ]] || {
  echo "FATAL: shell theme is ${shell_theme_actual}, expected ${LIMAD_SHELL_THEME_VARIANT}" >&2
  exit 1
}
echo "   shell-theme = ${shell_theme_actual}"
favorites_actual="$(gsettings --schemadir "${SCHEMA_DIR}" get org.gnome.shell favorite-apps 2>/dev/null || echo '?')"
for desktop in app.zen_browser.zen.desktop de.limad.Mail.desktop de.limad.Cut.desktop de.limad.Study.desktop de.limad.Notes.desktop de.limad.Drop.desktop de.limad.Link.desktop de.limad.Save.desktop de.limad.WindowsApps.desktop de.limad.Updater.desktop de.limad.AnycubicSlicerNext.desktop us.zoom.Zoom.desktop app.ytmdesktop.ytmdesktop.desktop org.libreoffice.LibreOffice.desktop de.limad.Klang.desktop de.limad.Terminal.desktop io.github.kolunmi.Bazaar.desktop org.gnome.Nautilus.desktop; do
  [[ "$favorites_actual" == *"'$desktop'"* ]] || {
    echo "FATAL: requested dock application missing from defaults: ${desktop}" >&2
    exit 1
  }
done
echo "   requested LiMaD applications are pinned in favorite-apps"

echo ":: Enabling Flatpak GTK theme access for new users"
install -d /etc/skel/.local/share/flatpak/overrides
cat > /etc/skel/.local/share/flatpak/overrides/global <<EOF
[Context]
filesystems=xdg-config/gtk-3.0:ro;xdg-config/gtk-4.0:ro;/usr/share/themes:ro;/usr/share/icons:ro;

[Environment]
GTK_THEME=${LIMAD_GTK_THEME_VARIANT}
EOF

echo ":: Preparing one-time desktop, Zen and Firefox setup"
chmod 0755 /usr/local/bin/limad-first-login-setup /usr/local/bin/limad-firefox-theme-setup /usr/local/bin/limad-zen-deutsch-setup /usr/local/bin/limad-user-folders-setup
chmod 0644 /etc/xdg/autostart/limad-first-login.desktop /etc/xdg/autostart/limad-firefox-theme.desktop /etc/xdg/autostart/limad-zen-deutsch.desktop /etc/xdg/autostart/limad-user-folders.desktop
[[ -f /usr/share/icons/LiMaD/64x64/apps/limad-start.png ]] || { echo "FATAL: LiMaD start icon missing" >&2; exit 1; }

echo ":: Updating desktop and icon caches"
update-desktop-database /usr/share/applications 2>/dev/null || true
gtk-update-icon-cache -f -q "/usr/share/icons/${LIMAD_ICON_THEME_NAME}" 2>/dev/null || true

echo ":: GNOME defaults step done"

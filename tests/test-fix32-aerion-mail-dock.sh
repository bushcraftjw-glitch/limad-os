#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
fail() { echo "RC2 MAIL/DEFAULT APPS FAILED: $*" >&2; exit 1; }
INSTALLER=system_files/usr/local/bin/limad-install-default-flatpaks
MAIL=system_files/usr/local/bin/limad-mail
MAIL_SETUP=system_files/usr/local/bin/limad-mail-setup
MAIL_APPLY=system_files/usr/local/bin/limad-mail-theme-apply
MAIL_CSS=system_files/usr/share/limad-mail/theme/limad-mail.css
MAIL_DESKTOP=system_files/usr/share/applications/de.limad.Mail.desktop
OVERRIDE=system_files/usr/share/glib-2.0/schemas/zzzzzzzzzz-limad-defaults.gschema.override
for f in "$INSTALLER" "$MAIL" "$MAIL_SETUP" "$MAIL_APPLY"; do [[ -x "$f" ]] || fail "$f missing"; done
for f in "$MAIL_CSS" "$MAIL_DESKTOP"; do [[ -s "$f" ]] || fail "$f missing"; done
for needle in 'width: 14px' 'order: 1' 'order: 2' 'order: 3' '#ff5f57' '#28c840' '#ffbd2e'; do grep -Fq "$needle" "$MAIL_CSS" || fail "mail css missing $needle"; done
grep -Fq 'Exec=/usr/local/bin/limad-mail %U' "$MAIL_DESKTOP" || fail "mail desktop launcher wrong"
for id in app.zen_browser.zen org.mozilla.thunderbird_esr us.zoom.Zoom app.ytmdesktop.ytmdesktop org.libreoffice.LibreOffice com.usebottles.bottles com.github.wwmm.easyeffects io.github.kolunmi.Bazaar; do
  grep -Fq "$id" "$INSTALLER" || fail "installer missing $id"
done
python3 - "$OVERRIDE" <<'PYMAIL'
from pathlib import Path
import ast,re,sys
text=Path(sys.argv[1]).read_text()
actual=ast.literal_eval(re.search(r'^favorite-apps=(.*)$',text,re.M).group(1))
expected=['app.zen_browser.zen.desktop','de.limad.Mail.desktop','de.limad.Cut.desktop','de.limad.Study.desktop','de.limad.Notes.desktop','de.limad.Drop.desktop','de.limad.Link.desktop','de.limad.Save.desktop','de.limad.WindowsApps.desktop','de.limad.Updater.desktop','de.limad.AnycubicSlicerNext.desktop','us.zoom.Zoom.desktop','app.ytmdesktop.ytmdesktop.desktop','org.libreoffice.LibreOffice.desktop','de.limad.Klang.desktop','de.limad.Terminal.desktop','io.github.kolunmi.Bazaar.desktop','org.gnome.Nautilus.desktop']
if actual != expected: raise SystemExit(f'wrong order: {actual}')
PYMAIL
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/home" "$TMP/runtime" "$TMP/flatpak-state"
cat > "$TMP/bin/flatpak" <<'FAKEFLATPAK'
#!/usr/bin/env bash
set -u
printf '%s\n' "$*" >> "$LIMAD_TEST_FLATPAK_LOG"
case "${1-}" in
  remotes) exit 0;;
  remote-add|update|override) exit 0;;
  install) app="${@: -1}"; mkdir -p "$LIMAD_TEST_FLATPAK_STATE"; : > "$LIMAD_TEST_FLATPAK_STATE/$app"; exit 0;;
  info) app="${@: -1}"; [[ -f "$LIMAD_TEST_FLATPAK_STATE/$app" ]]; exit $?;;
  run) exit 0;;
  *) exit 0;;
esac
FAKEFLATPAK
cat > "$TMP/bin/gsettings" <<'FAKEGSETTINGS'
#!/usr/bin/env bash
case "${1-}" in list-schemas) echo org.gnome.shell;; writable) echo true;; set) printf '%s\t%s\t%s\n' "${2-}" "${3-}" "${4-}" >> "$LIMAD_TEST_GSETTINGS_LOG";; *) exit 0;; esac
FAKEGSETTINGS
cat > "$TMP/bin/notify-send" <<'FAKENOTIFY'
#!/usr/bin/env bash
exit 0
FAKENOTIFY
chmod 0755 "$TMP/bin/"*
export PATH="$TMP/bin:/usr/bin:/bin" HOME="$TMP/home" XDG_CONFIG_HOME="$TMP/home/.config" XDG_STATE_HOME="$TMP/home/.local/state" XDG_RUNTIME_DIR="$TMP/runtime"
export LIMAD_TEST_FLATPAK_LOG="$TMP/flatpak.log" LIMAD_TEST_GSETTINGS_LOG="$TMP/gsettings.log" LIMAD_TEST_FLATPAK_STATE="$TMP/flatpak-state"
export LIMAD_MAIL_SETUP_HELPER="$PWD/system_files/usr/local/bin/limad-mail-setup"
export LIMAD_MAIL_THEME_APPLY_HELPER="$PWD/system_files/usr/local/bin/limad-mail-theme-apply"
export LIMAD_MAIL_THEME_SOURCE="$PWD/system_files/usr/share/limad-mail/theme/limad-mail.css"
export LIMAD_KLANG_PRESET_HELPER="$PWD/system_files/usr/local/bin/limad-install-klang-preset"
export LIMAD_KLANG_PRESET_SOURCE="$PWD/system_files/usr/share/limad-klang/LiMaD Klang.json"
export LIMAD_ZEN_SETUP_HELPER="$PWD/system_files/usr/local/bin/limad-zen-deutsch-setup"
bash "$INSTALLER"
[[ -f "$XDG_CONFIG_HOME/limad/default-flatpaks-rc2-build5.done" ]] || fail "completion marker missing"
for id in app.zen_browser.zen org.mozilla.thunderbird_esr us.zoom.Zoom app.ytmdesktop.ytmdesktop org.libreoffice.LibreOffice com.usebottles.bottles com.github.wwmm.easyeffects io.github.kolunmi.Bazaar; do
  grep -Fq "install --user --noninteractive -y flathub $id" "$TMP/flatpak.log" || fail "$id not installed"
done
grep -Fq 'de.limad.Mail.desktop' "$TMP/gsettings.log" || fail "LiMaD Mail dock item missing"
echo "RC2 LiMaD Mail 1.8, Thunderbird ESR, LibreOffice and default dock order: PASS"

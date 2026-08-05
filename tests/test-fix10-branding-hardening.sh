#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."

fail() { echo "FIX10 BRANDING HARDENING FAILED: $*" >&2; exit 1; }

source build_files/versions.env
[[ "$LIMAD_BUILD_REVISION" =~ ^gnome-rc2-build(4|5)$ || "$LIMAD_BUILD_REVISION" =~ ^gnome42-phase4-fix(32|35|36|37|38|39|41|42|43|44|45|46|47|48|49|50)$ ]] || fail "wrong build revision"
[[ "$LIMAD_LOGOMENU_VERSION" == "v24.8_270626" ]] || fail "Logo Menu is not pinned to the GNOME 50 release"
[[ "$BASE_IMAGE_REF" == *bazzite-gnome* ]] || fail "base image is not Bazzite GNOME"

source tools/lib-iso-branding.sh
[[ "$(limad_iso_volume_id "$LIMAD_OS_VERSION")" == "LIMAD_OS_280_RC2" ]] || fail "dynamic ISO volume id is wrong"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cat > "$TMP/grub.cfg" <<'CFG'
menuentry 'Install Fedora Linux 44' {
 linux /images/pxeboot/vmlinuz inst.stage2=hd:LABEL=Fedora-WS-dvd-x86_64-44 root=live:CDLABEL=Fedora-WS-dvd-x86_64-44 rd.live.image
 search --no-floppy --set=root --label 'Fedora-WS-dvd-x86_64-44'
}
menu label ^Install Bazzite
label linux
CFG
python3 tools/rewrite-boot-config.py "$TMP/grub.cfg" "$LIMAD_OS_VERSION" LIMAD_OS_280_RC2
grep -q "menuentry 'Install LiMaD OS 2.8.0-rc2'" "$TMP/grub.cfg" || fail "GRUB title was not rebranded"
grep -q 'inst.stage2=hd:LABEL=LIMAD_OS_280_RC2' "$TMP/grub.cfg" || fail "inst.stage2 label was not rewritten"
grep -q 'root=live:CDLABEL=LIMAD_OS_280_RC2' "$TMP/grub.cfg" || fail "live root label was not rewritten"
grep -q -- "--label 'LIMAD_OS_280_RC2'" "$TMP/grub.cfg" || fail "GRUB search label was not rewritten"
grep -q '^label linux$' "$TMP/grub.cfg" || fail "non-visible boot identifier was changed"
if grep -q 'inst.stage2=.*LiMaD OS' "$TMP/grub.cfg"; then fail "visible branding leaked into a kernel parameter"; fi

LOGOMENU="$(cat build_files/45-logomenu-extension.sh)"
for needle in 'GNOME_MAJOR' "shell-version" 'metadata compatibility' 'v24.8_270626'; do
  case "$needle" in
    v24.8_270626) grep -q "$needle" build_files/versions.env || fail "missing $needle" ;;
    *) printf '%s' "$LOGOMENU" | grep -q "$needle" || fail "Logo Menu compatibility check missing $needle" ;;
  esac
done

GDM="$(cat build_files/20-mactahoe-gtk.sh)"
for needle in 'bazzite-gnome' '/usr/lib/systemd/system/gdm.service' 'display-manager.service' 'gdm-branding.env' 'GDM resource did not change' 'LIMAD_DEFAULT_WALLPAPER'; do
  printf '%s' "$GDM" | grep -q "$needle" || fail "GDM hardening missing $needle"
done
if printf '%s' "$GDM" | grep -q 'WARNING: GDM theming failed'; then fail "GDM failure is still non-fatal"; fi

for file in build_files/90-verify.sh build_files/post-commit-check.sh; do
  grep -q 'gdm-branding.env' "$file" || fail "$file does not verify GDM branding"
  grep -q 'display-manager.service' "$file" || fail "$file does not verify the active display manager"
done

grep -q 'GITHUB_RUN_NUMBER' .github/workflows/build.yml || fail "GHCR tag does not include the run number"
grep -q 'GITHUB_RUN_ATTEMPT' .github/workflows/build.yml || fail "GHCR tag does not include the run attempt"
grep -q 'VERSION="2.8.0-rc2-build5"' system_files/usr/local/bin/limad-first-login-setup || fail "first-login marker was not advanced"

echo "FIX10 branding hardening retained in FIX11: PASS"

#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
grep -q "'ID': 'fedora'" "$ROOT/build_files/52-branding.sh"
grep -q "'ID_LIKE': '\"fedora\"'" "$ROOT/build_files/52-branding.sh"
grep -q '/etc/fastfetch/config.jsonc' "$ROOT/build_files/52-branding.sh"
grep -q 'de.limad.Logo.png' "$ROOT/build_files/52-branding.sh"
grep -q 'for branding_id in limad bazzite fedora' "$ROOT/build_files/52-branding.sh"
grep -q '^LIMAD_INSTALL_GDM_THEME="1"$' "$ROOT/build_files/versions.env"
grep -q 'bazzite-gnome' "$ROOT/build_files/20-mactahoe-gtk.sh"
grep -q 'display-manager.service' "$ROOT/build_files/20-mactahoe-gtk.sh"
grep -q 'gdm-branding.env' "$ROOT/build_files/20-mactahoe-gtk.sh"
grep -q 'GDM resource did not change' "$ROOT/build_files/20-mactahoe-gtk.sh"
echo "Fedora-compatible LiMaD identity, Fastfetch and enforced GDM defaults: PASS"

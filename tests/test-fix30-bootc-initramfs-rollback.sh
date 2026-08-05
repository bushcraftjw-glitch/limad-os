#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."

PLYMOUTH=build_files/55-plymouth.sh
DRACUT=system_files/etc/dracut.conf.d/99-limad-plymouth.conf
DEFAULTS=system_files/usr/share/glib-2.0/schemas/zzzzzzzzzz-limad-defaults.gschema.override

[[ -f "$DEFAULTS" ]] || { echo "FIX30 FAILED: late LiMaD schema override missing" >&2; exit 1; }
[[ ! -e system_files/usr/share/glib-2.0/schemas/95-limad-defaults.gschema.override ]] \
  || { echo "FIX30 FAILED: obsolete 95 schema override still present" >&2; exit 1; }
grep -Fq '/etc/dconf/db/local.d/zzzzzzzzzz-limad-branding' build_files/50-gnome-defaults.sh \
  || { echo "FIX30 FAILED: late dconf fragment missing" >&2; exit 1; }

# Critical FIX30 regression guard: late manual initramfs rebuilding is forbidden
# on this bootc/OSTree image customization layer.
if grep -Eq '^[[:space:]]*dracut([[:space:]]|$)' "$PLYMOUTH"; then
  echo "FIX30 FAILED: 55-plymouth.sh must not invoke dracut" >&2
  exit 1
fi
grep -Fq 'initramfs remains managed by bootc/Bazzite' "$PLYMOUTH" \
  || { echo "FIX30 FAILED: bootc initramfs ownership note missing" >&2; exit 1; }

# Keep all animation assets ready for a platform-managed future initramfs build.
for n in $(seq -w 0 11); do
  grep -Fq "/usr/share/plymouth/themes/limad/spinner-${n}.png" "$DRACUT" \
    || { echo "FIX30 FAILED: spinner-${n}.png absent from dracut install_items" >&2; exit 1; }
done

grep -Fq 'org.gnome.shell.extensions.user-theme name' build_files/50-gnome-defaults.sh \
  || { echo "FIX30 FAILED: build-time shell-theme verification missing" >&2; exit 1; }
grep -Fq 'org.gnome.shell.extensions.user-theme name' build_files/90-verify.sh \
  || { echo "FIX30 FAILED: acceptance shell-theme verification missing" >&2; exit 1; }
grep -Eq 'gnome-rc2-build(4|5)|gnome42-phase4-fix(32|35|36|37|38|39|41|42|43|44|45|46|47|48|49|50)' build_files/versions.env \
  || { echo "FIX30 FAILED: revision not updated" >&2; exit 1; }

echo "FIX30 bootc initramfs rollback and branding priority retention: PASS"

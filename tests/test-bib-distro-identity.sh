#!/usr/bin/env bash
set -Eeuo pipefail
fail(){ echo "FAIL: $*" >&2; exit 1; }
branding=build_files/52-branding.sh
grep -Fq "'ID': 'fedora'" "$branding" || fail "os-release ID must remain fedora for bootc-image-builder"
! grep -Fq "'ID': 'limad'" "$branding" || fail "custom ID=limad makes bootc-image-builder seek unsupported limad-44 definition"
grep -Fq "'NAME': '\"LiMaD OS\"'" "$branding" || fail "visible LiMaD name missing"
grep -Fq "'PRETTY_NAME': f'\"LiMaD OS {version}\"'" "$branding" || fail "visible LiMaD pretty name missing"
grep -Fq "'VARIANT_ID': 'limad-gnome'" "$branding" || fail "LiMaD variant identity missing"
echo "bootc-image-builder Fedora distro identity: PASS"

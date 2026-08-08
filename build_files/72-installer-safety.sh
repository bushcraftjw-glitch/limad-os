#!/usr/bin/env bash
set -Eeuo pipefail
# LiMaD OS 3.0 intentionally keeps Ubuntu's installer controls unmodified.
# The old Anaconda CSS caused white text on white widgets. Never carry it over.
if find /usr/share /etc -xdev -type f \( -iname '*anaconda*.css' -o -iname '*limad*installer*.css' \) -print -quit 2>/dev/null | grep -q .; then
  echo 'FATAL: legacy/global installer CSS detected; contrast safety would be undefined.' >&2
  exit 1
fi
install -d /usr/share/limad/installer
cat > /usr/share/limad/installer/CONTRAST-POLICY.txt <<'POLICY'
LiMaD OS 3.0 installer policy
- Keep upstream Ubuntu installer widget styling and contrast.
- Do not apply a global text color.
- Do not import Anaconda/Fedora installer CSS.
- LiMaD branding may change product text/logo only; controls stay upstream-styled.
POLICY
echo ':: Installer contrast safety policy active'

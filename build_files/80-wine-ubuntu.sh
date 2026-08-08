#!/usr/bin/env bash
set -Eeuo pipefail
source /opt/limad-build/versions.env
[[ "${LIMAD_INSTALL_WINE:-1}" == "1" ]] || exit 0
command -v wine >/dev/null 2>&1 || { echo 'Wine fehlt nach Paketinstallation.' >&2; exit 1; }
chmod 0755 /usr/local/bin/limad-windows-setup /usr/local/bin/limad-winrun /usr/local/bin/limad-wine-diagnose /usr/local/bin/limad-bottles-run 2>/dev/null || true
python3 -m py_compile /usr/share/limad-windows/installer.py /usr/share/limad-windows/recipe_engine.py

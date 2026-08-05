#!/usr/bin/env bash
# Installs Wine, validates a real prefix in Xvfb and wires up LiMaD Windows.
set -Eeuo pipefail
source /ctx/build_files/versions.env
if [[ "${LIMAD_INSTALL_WINE:-1}" != "1" ]]; then echo ":: Wine disabled by configuration, skipping"; exit 0; fi
echo ":: Installing complete Fedora Wine runtime"
WINE_PACKAGES=(wine wine-core wine-mono mingw32-wine-gecko mingw64-wine-gecko wine-pulseaudio wine-desktop wine-winefonts winetricks cabextract samba-winbind-clients icoutils zenity xorg-x11-server-Xvfb file binutils)
for pkg in "${WINE_PACKAGES[@]}"; do
  if rpm -q "$pkg" >/dev/null 2>&1; then echo "   already present: $pkg";
  elif dnf5 -y install "$pkg" 2>/dev/null || dnf -y install "$pkg" 2>/dev/null; then echo "   installed: $pkg";
  else echo "FATAL: required Wine package unavailable: $pkg" >&2; exit 1; fi
done
for command in wine wineboot wineserver xvfb-run; do command -v "$command" >/dev/null || { echo "FATAL: $command missing" >&2; exit 1; }; done
echo ":: Running Wine prefix and command smoke test"
SMOKE_ROOT=/tmp/limad-wine-smoke; rm -rf "$SMOKE_ROOT"; install -d -m 0700 "$SMOKE_ROOT/home" "$SMOKE_ROOT/prefix"
export HOME="$SMOKE_ROOT/home" WINEPREFIX="$SMOKE_ROOT/prefix" WINEARCH=wow64 WINEDEBUG=-all
unset WINEDLLOVERRIDES || true
timeout 600 xvfb-run -a wineboot --init
timeout 600 wineserver -w
SMOKE_OUTPUT="$(timeout 180 xvfb-run -a wine cmd /c 'echo LIMAD_WINE_OK' 2>&1 | tr -d '\r')"
grep -q 'LIMAD_WINE_OK' <<<"$SMOKE_OUTPUT" || { echo "$SMOKE_OUTPUT" >&2; echo "FATAL: Wine command smoke test failed" >&2; exit 1; }
printf 'PASS wine=%s tested=%s\n' "$(wine --version)" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > /usr/share/limad/wine-smoke-test.txt
wineserver -k 2>/dev/null || true; rm -rf "$SMOKE_ROOT"; unset HOME WINEPREFIX WINEARCH WINEDEBUG
echo ":: Installing the LiMaD Windows integration"
chmod 0755 /usr/local/bin/limad-windows-setup /usr/local/bin/limad-winrun /usr/local/bin/limad-wine-diagnose /usr/local/bin/limad-bottles-run
chmod 0644 /usr/share/limad-windows/installer.py /usr/share/limad-windows/recipe_engine.py /usr/share/limad-windows/wine-env.sh /usr/share/limad-windows/VERSION
python3 -c 'from pathlib import Path; import sys; [compile(Path(p).read_text(encoding="utf-8"), p, "exec") for p in sys.argv[1:]]' /usr/share/limad-windows/installer.py /usr/share/limad-windows/recipe_engine.py
grep -Fxq "${LIMAD_WINDOWS_VERSION}" /usr/share/limad-windows/VERSION || { echo "FATAL: Windows installer version mismatch" >&2; exit 1; }
cat > /usr/share/mime/packages/de.limad.WindowsApps.xml <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="application/x-ms-dos-executable"><comment>Windows-Programm</comment><comment xml:lang="en">Windows program</comment><glob pattern="*.exe"/></mime-type>
  <mime-type type="application/x-msi"><comment>Windows-Installationspaket</comment><comment xml:lang="en">Windows installer package</comment><glob pattern="*.msi"/></mime-type>
</mime-info>
EOF
update-mime-database /usr/share/mime 2>/dev/null || true
cat > /usr/share/applications/mimeapps.list <<'EOF'
[Default Applications]
application/x-ms-dos-executable=de.limad.WindowsRun.desktop
application/x-msdownload=de.limad.WindowsRun.desktop
application/x-msi=de.limad.WindowsRun.desktop
application/vnd.microsoft.portable-executable=de.limad.WindowsRun.desktop
EOF
update-desktop-database /usr/share/applications 2>/dev/null || true
echo ":: Wine step done"

#!/usr/bin/env bash
set -Eeuo pipefail
LIMAD_WIN_HOME="${XDG_DATA_HOME:-$HOME/.local/share}/limad-windows"
LIMAD_WIN_APPS_HOME="$LIMAD_WIN_HOME/apps"
export WINEPREFIX="${WINEPREFIX:-$LIMAD_WIN_HOME/prefix}"
export WINEARCH="${WINEARCH:-wow64}"
export WINEDEBUG="${WINEDEBUG:--all}"
limad_win_use_prefix() { export WINEPREFIX="$1"; export WINEARCH=wow64; export WINEDEBUG="${WINEDEBUG:--all}"; }
limad_win_have_wine() { command -v wine >/dev/null 2>&1; }
limad_win_prefix_ready() { [[ -f "$WINEPREFIX/system.reg" && -f "$WINEPREFIX/user.reg" && -d "$WINEPREFIX/drive_c/windows/system32" ]]; }
limad_win_health_check() { limad_win_have_wine || return 1; wine cmd /c "echo LIMAD_WINE_OK" 2>&1 | tr -d '\r' | grep -q 'LIMAD_WINE_OK'; }
limad_win_init_prefix() { limad_win_have_wine || return 1; mkdir -p "$(dirname "$WINEPREFIX")"; if ! limad_win_prefix_ready; then wineboot --init || return 1; wineserver -w || return 1; fi; limad_win_prefix_ready && limad_win_health_check; }

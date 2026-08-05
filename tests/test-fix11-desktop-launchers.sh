#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
fail() { echo "FIX11 DESKTOP LAUNCHER TEST FAILED: $*" >&2; exit 1; }

desktop=system_files/usr/share/applications/de.limad.SystemUpdate.desktop
grep -qx 'Exec=/usr/local/bin/limad-system-update' "$desktop" || fail "system update launcher must call the shipped executable directly"
grep -qx 'TryExec=/usr/local/bin/limad-system-update' "$desktop" || fail "TryExec missing"
grep -qx 'Terminal=true' "$desktop" || fail "desktop environment must select its available terminal"
! grep -Eq '^Exec=(kgx|ptyxis|gnome-terminal|konsole|xterm)( |$)' "$desktop" || fail "hard-coded terminal dependency returned"

grep -q 'command -v "$exec_bin"' build_files/70-limad-apps.sh || fail "bare command validation is not PATH-aware"
grep -q '\[\[ "$exec_bin" == /\* \]\]' build_files/70-limad-apps.sh || fail "absolute executable validation missing"

# No LiMaD desktop entry should carry two main categories that caused duplicate-menu hints.
! grep -RHE '^Categories=(System;Settings|Education;Office|Network;FileTransfer;Utility|System;Utility;Emulator);$' \
  system_files/usr/share/applications/de.limad.*.desktop || fail "duplicate main desktop categories remain"

echo "FIX11 desktop launcher and category hardening: PASS"

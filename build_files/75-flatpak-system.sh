#!/usr/bin/env bash
set -Eeuo pipefail
command -v flatpak >/dev/null 2>&1 || exit 0
flatpak remote-add --system --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo || true

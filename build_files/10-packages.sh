#!/usr/bin/env bash
# Packages required to build and run the LiMaD look on GNOME.
set -Eeuo pipefail

# Sourced for standalone use by the theme probe workflow.
# shellcheck source=/dev/null
source /ctx/build_files/versions.env

echo ":: Installing build and runtime packages"

# Build dependencies for the vinceliuice installers (SCSS -> CSS, gresource).
BUILD_PACKAGES=(
  git
  sassc
  glib2-devel
  libxml2
  ImageMagick
  distribution-gpg-keys
  python3-devel
  libnl3-devel
  libev-devel
  libpcap-devel
  gcc-c++
  gcc
  make
  cmake
  golang
)

# Runtime pieces of the macOS-like GNOME experience.
RUNTIME_PACKAGES=(
  gnome-tweaks
  gnome-shell-extension-user-theme
  gnome-shell-extension-dash-to-dock
  gnome-shell-extension-blur-my-shell
  plymouth
  plymouth-plugin-script
  gnome-themes-extra
  gtk-murrine-engine
)

# GStreamer is a mandatory part of the LiMaD base image. LiMaD Study's
# separate native GTK4 player depends on the Python bindings and on the
# gtk4paintablesink plugin. These packages must never be silently skipped.
GSTREAMER_PACKAGES=(
  gstreamer1
  python3-gstreamer1
  gstreamer1-plugin-gtk4
  gstreamer1-plugins-base
  gstreamer1-plugins-good
  gstreamer1-plugins-bad-free
  gstreamer1-plugins-ugly-free
  gstreamer1-plugin-openh264
  gstreamer1-plugin-libav
  pipewire-gstreamer
)

# Runtime of the natively shipped LiMaD applications (GTK4 + WebKit via
# PyGObject) and of LiDrop's network discovery.
LISAVE_PACKAGES=(
  restic
  libsecret
)

APP_PACKAGES=(
  python3-gobject
  gtk4
  webkitgtk6.0
  avahi
  avahi-tools
  nss-mdns
  qrencode
  desktop-file-utils
  shared-mime-info
  file
  libnotify
  polkit
  libarchive
  bluez
  iw
  python3-virtualenv
  python3-pip
  gnome-network-displays
  gnome-remote-desktop
  gnome-connections
  freerdp
  deskflow
  openssl
  pulseaudio-utils
)

dnf5 -y install "${BUILD_PACKAGES[@]}" || dnf -y install "${BUILD_PACKAGES[@]}"

echo ":: Installing mandatory GStreamer runtime"
if ! (dnf5 -y install "${GSTREAMER_PACKAGES[@]}" 2>/dev/null || dnf -y install "${GSTREAMER_PACKAGES[@]}"); then
  echo "FATAL: mandatory GStreamer runtime could not be installed" >&2
  exit 1
fi
for pkg in "${GSTREAMER_PACKAGES[@]}"; do
  rpm -q "$pkg" >/dev/null 2>&1 || {
    echo "FATAL: mandatory GStreamer package missing after installation: $pkg" >&2
    exit 1
  }
done

echo ":: Installing mandatory LiSave runtime"
if ! (dnf5 -y install "${LISAVE_PACKAGES[@]}" 2>/dev/null || dnf -y install "${LISAVE_PACKAGES[@]}"); then
  echo "FATAL: mandatory LiSave runtime could not be installed" >&2
  exit 1
fi
for pkg in "${LISAVE_PACKAGES[@]}"; do
  rpm -q "$pkg" >/dev/null 2>&1 || {
    echo "FATAL: mandatory LiSave package missing after installation: $pkg" >&2
    exit 1
  }
done
command -v restic >/dev/null 2>&1 || { echo "FATAL: restic command missing" >&2; exit 1; }
command -v secret-tool >/dev/null 2>&1 || { echo "FATAL: secret-tool command missing" >&2; exit 1; }

# Remaining runtime packages are installed one by one: a single renamed package in a
# future Fedora release must not break the whole image build.
for pkg in "${RUNTIME_PACKAGES[@]}" "${APP_PACKAGES[@]}"; do
  if rpm -q "$pkg" >/dev/null 2>&1; then
    echo "   already present: $pkg"
    continue
  fi
  if dnf5 -y install "$pkg" 2>/dev/null || dnf -y install "$pkg" 2>/dev/null; then
    echo "   installed: $pkg"
  else
    echo "   WARNING: package not available, skipped: $pkg" >&2
  fi
done

echo ":: Package step done"

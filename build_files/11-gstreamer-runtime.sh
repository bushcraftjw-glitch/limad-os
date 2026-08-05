#!/usr/bin/env bash
set -Eeuo pipefail

source /ctx/build_files/versions.env

echo ":: Validating mandatory LiMaD GStreamer runtime"

required_packages=(
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
for pkg in "${required_packages[@]}"; do
  rpm -q "$pkg" >/dev/null 2>&1 || {
    echo "FATAL: required GStreamer package missing: $pkg" >&2
    exit 1
  }
done

command -v gst-inspect-1.0 >/dev/null 2>&1 || {
  echo "FATAL: gst-inspect-1.0 is unavailable" >&2
  exit 1
}

required_elements=(
  playbin
  uridecodebin
  audioconvert
  audioresample
  videoconvert
  videoscale
  gtk4paintablesink
  pipewiresrc
  h264parse
)
for element in "${required_elements[@]}"; do
  gst-inspect-1.0 "$element" >/dev/null 2>&1 || {
    echo "FATAL: required GStreamer element missing: $element" >&2
    exit 1
  }
done

python3 - <<'PY_GSTREAMER'
import gi
gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '4.0')
from gi.repository import Gst, Gtk
Gst.init(None)
if Gst.ElementFactory.find('gtk4paintablesink') is None:
    raise SystemExit('gtk4paintablesink is unavailable through Python GI')
if Gst.ElementFactory.find('playbin') is None:
    raise SystemExit('playbin is unavailable through Python GI')
print(f'GStreamer {Gst.version_string()} with GTK {Gtk.get_major_version()}.{Gtk.get_minor_version()}')
PY_GSTREAMER

install -d /usr/share/limad
{
  echo "required=1"
  echo "study_native_player=1"
  echo "gtk4paintablesink=1"
  echo "gstreamer_version=$(gst-inspect-1.0 --version | sed -n '2p' | xargs)"
} > /usr/share/limad/gstreamer-runtime.env

echo ":: Mandatory GStreamer runtime is ready"

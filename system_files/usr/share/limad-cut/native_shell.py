#!/usr/bin/env python3
import glob
import os
import sys
from pathlib import Path

if os.environ.get("LIMAD_CUT_DISABLE_DMABUF") == "1":
    os.environ["WEBKIT_DISABLE_DMABUF_RENDERER"] = "1"
else:
    os.environ.pop("WEBKIT_DISABLE_DMABUF_RENDERER", None)

if os.environ.get("LIMAD_CUT_FORCE_SOFTWARE") != "1":
    os.environ.pop("WEBKIT_SKIA_ENABLE_CPU_RENDERING", None)
    os.environ.pop("LIBGL_ALWAYS_SOFTWARE", None)

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gio, GLib, Gtk, WebKit

APP_ID = "de.limad.Cut"
BASE = os.environ.get("LIMAD_CUT_RESOURCE_ROOT", "/usr/share/limad-cut")
LANGUAGE = os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG", "de_DE")
LOCALE = "DE" if LANGUAGE.lower().startswith("de") else "EN"
MATCHES = sorted(glob.glob(os.path.join(BASE, f"LiMaD_Cut_Offline_*_{LOCALE}.html")))
if not MATCHES:
    MATCHES = sorted(glob.glob(os.path.join(BASE, "LiMaD_Cut_Offline_*_DE.html")))
if not MATCHES:
    raise SystemExit("LiMaD-Cut-HTML wurde nicht gefunden.")
URI = Gio.File.new_for_path(MATCHES[-1]).get_uri()

STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "limad-cut"
STATE_DIR.mkdir(parents=True, exist_ok=True)


def log(message):
    with (STATE_DIR / "graphics.log").open("a", encoding="utf-8") as handle:
        handle.write(message + "\n")


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)

    def do_activate(self):
        window = self.props.active_window
        if window:
            window.present()
            return

        window = Gtk.ApplicationWindow(application=self, title="LiMaD Cut")
        window.set_default_size(1440, 900)
        window.maximize()

        settings = WebKit.Settings()
        settings.set_enable_webgl(True)
        settings.set_enable_webaudio(True)
        settings.set_enable_write_console_messages_to_stdout(False)
        try:
            settings.set_hardware_acceleration_policy(WebKit.HardwareAccelerationPolicy.ALWAYS)
        except (AttributeError, TypeError) as error:
            log(f"Hardwarebeschleunigungsrichtlinie konnte nicht erzwungen werden: {error}")

        try:
            policy = settings.get_hardware_acceleration_policy()
        except (AttributeError, TypeError):
            policy = "unbekannt"

        log(
            "Start: "
            f"session={os.environ.get('XDG_SESSION_TYPE', 'unknown')} "
            f"policy={policy} "
            f"dmabuf_disabled={os.environ.get('WEBKIT_DISABLE_DMABUF_RENDERER', '0')} "
            f"software={os.environ.get('WEBKIT_SKIA_ENABLE_CPU_RENDERING', '0')} "
            f"uri={URI}"
        )

        view = WebKit.WebView(settings=settings)
        view.set_hexpand(True)
        view.set_vexpand(True)
        view.load_uri(URI)
        window.set_child(view)
        window.present()

    def do_open(self, files, n_files, hint):
        self.do_activate()


raise SystemExit(App().run(sys.argv))

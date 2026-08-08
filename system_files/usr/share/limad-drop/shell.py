#!/usr/bin/python3
from __future__ import annotations
import json
import os
import signal
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

APP_ID = "de.limad.Drop"
APP_NAME = "LiDrop"
SERVICE = "limad-drop.service"
EXPECTED_VERSION = "0.12.0-preview8"


def runtime_file() -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    return Path(runtime) / "limad-drop.json" if runtime else Path("/tmp") / f"limad-drop-{os.getuid()}.json"


def read_runtime() -> dict | None:
    try:
        value = json.loads(runtime_file().read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except Exception:
        return None


def health_url(payload: dict) -> str:
    port = int(payload["port"])
    if not 1 <= port <= 65535:
        raise ValueError("Ungültiger LiDrop-Port")
    return f"http://127.0.0.1:{port}/api/health"


def probe_runtime(payload: dict | None) -> tuple[str | None, str | None]:
    if not payload:
        return None, None
    try:
        with urllib.request.urlopen(health_url(payload), timeout=1.2) as response:
            if response.status != 200:
                return None, None
            result = json.loads(response.read().decode("utf-8"))
            if result.get("ok") is not True:
                return None, None
            return str(payload.get("url") or ""), str(result.get("version") or "")
    except Exception:
        return None, None


def versioned_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    query = [(key, value) for key, value in query if key != "appVersion"]
    query.append(("appVersion", EXPECTED_VERSION))
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(query), parts.fragment))


def healthy_runtime() -> str | None:
    url, version = probe_runtime(read_runtime())
    if url and version == EXPECTED_VERSION:
        return versioned_url(url)
    return None


def user_systemd_available() -> bool:
    result = subprocess.run(
        ["systemctl", "--user", "show-environment"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def service_state() -> str:
    result = subprocess.run(
        ["systemctl", "--user", "is-active", SERVICE],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.stdout.strip()


def service_log() -> str:
    result = subprocess.run(
        ["journalctl", "--user", "-u", SERVICE, "-n", "24", "--no-pager", "-o", "cat"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    text = result.stdout.strip()
    return text[-2200:] if text else "Kein Dienstprotokoll verfügbar."


def stop_stale_direct_runtime() -> None:
    payload = read_runtime()
    if not payload:
        return
    _url, version = probe_runtime(payload)
    if version == EXPECTED_VERSION:
        return
    try:
        pid = int(payload.get("pid") or 0)
    except (TypeError, ValueError):
        pid = 0
    if pid > 1:
        try:
            os.kill(pid, signal.SIGTERM)
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                try:
                    os.kill(pid, 0)
                except OSError:
                    break
                time.sleep(0.1)
        except OSError:
            pass


def start_direct_fallback() -> None:
    subprocess.Popen(
        ["/usr/local/bin/limad-dropd"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )


def ensure_server() -> str:
    ready = healthy_runtime()
    if ready:
        return ready

    if user_systemd_available():
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
        subprocess.run(["systemctl", "--user", "reset-failed", SERVICE], check=False)
        result = subprocess.run(
            ["systemctl", "--user", "restart", SERVICE],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"LiDrop-Dienst konnte nicht neu gestartet werden.\n{result.stdout.strip()}\n{service_log()}")
    else:
        stop_stale_direct_runtime()
        try:
            runtime_file().unlink(missing_ok=True)
        except OSError:
            pass
        start_direct_fallback()

    deadline = time.monotonic() + 30
    last_state = "wird gestartet"
    last_version = "unbekannt"
    while time.monotonic() < deadline:
        payload = read_runtime()
        url, version = probe_runtime(payload)
        if version:
            last_version = version
        if url and version == EXPECTED_VERSION:
            return versioned_url(url)
        if user_systemd_available():
            last_state = service_state() or last_state
            if last_state == "failed":
                raise RuntimeError(f"LiDrop-Dienst wurde beendet.\n{service_log()}")
        time.sleep(0.3)

    detail = service_log() if user_systemd_available() else "Der direkte Dienststart hat keine passende Laufzeitdatei erzeugt."
    raise RuntimeError(
        f"LiDrop {EXPECTED_VERSION} ist nach 30 Sekunden nicht erreichbar. "
        f"Geladene Dienstversion: {last_version}. Status: {last_state}\n{detail}"
    )


def install_css(Gtk, Gdk) -> None:
    css = b"""
    window { background: #090713; color: #f6f2ff; }
    headerbar { background: #111020; color: #f6f2ff; border-bottom: 1px solid rgba(177,134,255,.20); }
    button { border-radius: 10px; }
    """
    provider = Gtk.CssProvider()
    provider.load_from_data(css)
    display = Gdk.Display.get_default()
    if display is not None:
        Gtk.StyleContext.add_provider_for_display(display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


def run() -> int:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("WebKit", "6.0")
    from gi.repository import Gdk, Gio, Gtk, WebKit
    url = ensure_server()

    class App(Gtk.Application):
        def __init__(self):
            super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
            self.window = None

        def do_activate(self):
            install_css(Gtk, Gdk)
            if self.window:
                self.window.present()
                return
            self.window = Gtk.ApplicationWindow(application=self, title=APP_NAME)
            self.window.set_default_size(1180, 760)
            self.window.set_size_request(760, 520)
            settings = WebKit.Settings()
            settings.set_enable_javascript(True)
            settings.set_enable_smooth_scrolling(True)
            if hasattr(settings, "set_enable_accelerated_2d_canvas"):
                settings.set_enable_accelerated_2d_canvas(True)
            view = WebKit.WebView(settings=settings)
            view.set_hexpand(True)
            view.set_vexpand(True)
            view.load_uri(url)
            self.window.set_child(view)
            self.window.present()

    return App().run(sys.argv[:1])


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:
        try:
            import gi
            gi.require_version("Gtk", "4.0")
            from gi.repository import Gdk, Gtk
            app = Gtk.Application(application_id="de.limad.Drop.Error")

            def activate(application):
                install_css(Gtk, Gdk)
                window = Gtk.ApplicationWindow(application=application, title="LiDrop")
                window.set_default_size(680, 300)
                box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
                box.set_margin_top(28)
                box.set_margin_bottom(28)
                box.set_margin_start(30)
                box.set_margin_end(30)
                title = Gtk.Label(label="LiDrop konnte nicht gestartet werden")
                title.add_css_class("title-2")
                title.set_xalign(0)
                detail = Gtk.Label(label=str(exc))
                detail.set_wrap(True)
                detail.set_selectable(True)
                detail.set_xalign(0)
                button = Gtk.Button(label="Schließen")
                button.set_halign(Gtk.Align.END)
                button.connect("clicked", lambda _b: application.quit())
                box.append(title)
                box.append(detail)
                box.append(button)
                window.set_child(box)
                window.present()

            app.connect("activate", activate)
            raise SystemExit(app.run(None))
        except Exception:
            print(f"LiDrop konnte nicht gestartet werden: {exc}", file=sys.stderr)
            raise

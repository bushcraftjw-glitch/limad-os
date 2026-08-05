from __future__ import annotations
import json
import os
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from . import APP_ID, APP_NAME, VERSION
from .server import start_server


def _state_dir() -> Path:
    root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "limad-study"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _log(message: str) -> None:
    line = f"{datetime.now().isoformat(timespec='seconds')} {message}\n"
    try:
        with (_state_dir() / "startup.log").open("a", encoding="utf-8") as handle:
            handle.write(line)
    except OSError:
        pass
    print(line, end="", file=sys.stderr)


def _wait_for_server(url: str, timeout: float = 20.0) -> tuple[bool, str]:
    deadline = time.monotonic() + timeout
    health = url.rstrip("/") + "/api/health"
    last_error = ""
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(health, timeout=2) as response:
                payload = json.loads(response.read().decode("utf-8"))
                if response.status == 200 and payload.get("ok"):
                    _log(f"Server bereit: {health}")
                    return True, ""
                last_error = f"Ungültige Health-Antwort: HTTP {response.status}"
        except Exception as exc:
            last_error = f"{exc.__class__.__name__}: {exc}"
        time.sleep(0.25)
    return False, last_error or "Zeitüberschreitung beim Start des lokalen Servers"




def _configure_webkit_performance(settings, WebKit) -> None:
    enabled = []
    policy_type = getattr(WebKit, "HardwareAccelerationPolicy", None)
    policy = getattr(policy_type, "AUTOMATIC", None) if policy_type is not None else None
    if policy is not None:
        try:
            settings.set_hardware_acceleration_policy(policy)
            enabled.append("hardware-acceleration=automatic")
        except (AttributeError, TypeError, ValueError) as exc:
            _log(f"WebKit-Standardbeschleunigung konnte nicht gesetzt werden: {exc}")
    for method_name, label in (
        ("set_enable_webgl", "webgl"),
        ("set_enable_webaudio", "webaudio"),
        ("set_enable_mediasource", "mediasource"),
    ):
        try:
            getattr(settings, method_name)(True)
            enabled.append(label)
        except (AttributeError, TypeError, ValueError):
            pass
    _log("WebKit-Profil: " + (", ".join(enabled) if enabled else "Standardprofil"))


def _load_native_runtime():
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("WebKit", "6.0")
    from gi.repository import Gio, GLib, Gtk, WebKit
    return Gio, GLib, Gtk, WebKit


def run_native(url: str, server) -> int:
    Gio, GLib, Gtk, WebKit = _load_native_runtime()

    class Application(Gtk.Application):
        def __init__(self):
            super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)
            self.window = None
            self.view = None
            self.retry_count = 0
            self.loaded = False
            self.frontend_ready = False
            self.watchdog_id = 0
            self.frontend_poll_id = 0
            self.writer_window = None
            self.native_player = None

        def do_activate(self):
            if self.window:
                self.window.present()
                return
            self.window = Gtk.ApplicationWindow(application=self)
            self.window.set_title(APP_NAME)
            self.window.set_default_size(1460, 920)
            self.window.set_size_request(980, 650)
            self.window.connect("close-request", self._close)
            self._show_loading("LiMaD Study wird gestartet …")
            self.window.present()
            GLib.idle_add(self._create_webview)

        def _show_loading(self, text: str):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
            box.set_halign(Gtk.Align.CENTER)
            box.set_valign(Gtk.Align.CENTER)
            spinner = Gtk.Spinner()
            spinner.start()
            label = Gtk.Label(label=text)
            label.add_css_class("title-2")
            box.append(spinner)
            box.append(label)
            self.window.set_child(box)

        def _show_error(self, detail: str):
            _log(f"Native Startfehler: {detail}")
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
            box.set_margin_top(36)
            box.set_margin_bottom(36)
            box.set_margin_start(36)
            box.set_margin_end(36)
            title = Gtk.Label(label="LiMaD Study konnte die Oberfläche nicht laden")
            title.add_css_class("title-1")
            title.set_wrap(True)
            message = Gtk.Label(label=f"{detail}\n\nProtokoll: {_state_dir() / 'startup.log'}")
            message.set_wrap(True)
            message.set_selectable(True)
            retry = Gtk.Button(label="Erneut versuchen")
            retry.connect("clicked", lambda *_: self._retry())
            box.append(title)
            box.append(message)
            box.append(retry)
            self.window.set_child(box)

        def _create_webview(self):
            settings = WebKit.Settings()
            _configure_webkit_performance(settings, WebKit)
            settings.set_enable_developer_extras(os.environ.get("LIMAD_STUDY_DEVTOOLS") == "1")
            settings.set_enable_smooth_scrolling(True)
            for method_name in ("set_enable_javascript", "set_enable_html5_local_storage"):
                try:
                    getattr(settings, method_name)(True)
                except (AttributeError, TypeError):
                    pass
            try:
                settings.set_user_agent_with_application_details(APP_NAME.replace(" ", "-"), VERSION)
            except (AttributeError, TypeError):
                pass
            self.view = WebKit.WebView(settings=settings)
            self.view.set_hexpand(True)
            self.view.set_vexpand(True)
            self.view.connect("load-changed", self._load_changed)
            self.view.connect("load-failed", self._load_failed)
            self.view.connect("decide-policy", self._decide_policy)
            try:
                self.view.connect("web-process-terminated", self._web_process_terminated)
            except TypeError:
                pass
            self.window.set_child(self.view)
            self.view.load_uri(url.rstrip("/") + "/?native_shell=1")
            self.watchdog_id = GLib.timeout_add_seconds(20, self._load_watchdog)
            self.frontend_poll_id = GLib.timeout_add(500, self._poll_frontend_status)
            return False


        def _decide_policy(self, view, decision, decision_type):
            try:
                action = decision.get_navigation_action()
                request = action.get_request() if action else None
                uri = request.get_uri() if request else ""
            except Exception:
                uri = ""
            if uri == "limad-study://writer-window":
                decision.ignore()
                self._open_writer_window()
                return True
            if uri.startswith("limad-study://native-player/open"):
                decision.ignore()
                parsed = urllib.parse.urlparse(uri)
                session_id = (urllib.parse.parse_qs(parsed.query).get("session") or [""])[0]
                payload = server.take_native_player_session(session_id)
                if payload:
                    self._open_native_player(payload)
                else:
                    self._native_player_failed("Die Player-Sitzung ist abgelaufen oder ungültig.")
                return True
            return False

        def _open_native_player(self, payload):
            try:
                if self.native_player is None:
                    from .native_player import NativeMediaPlayer
                    self.native_player = NativeMediaPlayer(self, url, _log)
                self.native_player.open(payload)
                _log("Nativer GStreamer-Player geöffnet")
            except Exception as exc:
                _log(f"Nativer GStreamer-Player konnte nicht geöffnet werden: {exc}")
                self.native_player = None
                self._native_player_failed(str(exc))

        def _native_player_failed(self, detail: str):
            if not self.view:
                return
            script = "window.dispatchEvent(new CustomEvent('limad-native-player-failed',{detail:" + json.dumps(str(detail)) + "}));"
            for args in (
                (script, -1, None, None, None, None, None),
                (script, -1, None, None, None, None),
            ):
                try:
                    self.view.evaluate_javascript(*args)
                    return
                except Exception:
                    pass
            try:
                self.view.run_javascript(script, None, None, None)
            except Exception:
                pass

        def _open_writer_window(self):
            if self.writer_window is not None:
                self.writer_window.present()
                return
            writer = Gtk.ApplicationWindow(application=self)
            writer.set_title("LiMaD Study Writer")
            writer.set_default_size(920, 820)
            writer.set_size_request(640, 520)
            settings = WebKit.Settings()
            _configure_webkit_performance(settings, WebKit)
            settings.set_enable_smooth_scrolling(True)
            try:
                settings.set_enable_html5_local_storage(True)
            except (AttributeError, TypeError):
                pass
            view = WebKit.WebView(settings=settings)
            view.set_hexpand(True)
            view.set_vexpand(True)
            writer.set_child(view)
            writer.connect("close-request", self._writer_closed)
            self.writer_window = writer
            view.load_uri(url.rstrip("/") + "/writer-window.html")
            writer.present()
            _log("Study Writer als echtes natives GTK-Fenster geöffnet")

        def _writer_closed(self, *_):
            self.writer_window = None
            return False

        def _load_changed(self, view, event):
            if event == WebKit.LoadEvent.FINISHED:
                self.loaded = True
                _log(f"HTML und WebKit geladen: {view.get_uri()}; warte auf Frontend-Handshake")

        def _frontend_status(self) -> dict:
            endpoint = url.rstrip("/") + "/api/frontend/status"
            with urllib.request.urlopen(endpoint, timeout=2) as response:
                return json.loads(response.read().decode("utf-8"))

        def _poll_frontend_status(self):
            try:
                status = self._frontend_status()
            except Exception as exc:
                _log(f"Frontend-Status noch nicht erreichbar: {exc.__class__.__name__}: {exc}")
                return True
            state = status.get("state")
            stage = status.get("stage") or "unbekannt"
            if state == "ready":
                self.frontend_ready = True
                if self.watchdog_id:
                    GLib.source_remove(self.watchdog_id)
                    self.watchdog_id = 0
                self.frontend_poll_id = 0
                _log(f"Frontend vollständig bereit: {stage}")
                return False
            if state == "failed":
                self.frontend_poll_id = 0
                self._show_error(f"Frontend-Initialisierung fehlgeschlagen ({stage}): {status.get('message') or 'ohne Detail'}")
                return False
            return True

        def _load_failed(self, view, event, failing_uri, error):
            detail = f"Ladefehler bei {failing_uri}: {error.message if error else 'unbekannter Fehler'}"
            if self.retry_count < 2:
                self.retry_count += 1
                _log(f"{detail}; Versuch {self.retry_count + 1}")
                GLib.timeout_add(750, self._reload)
            else:
                self._show_error(detail)
            return True

        def _web_process_terminated(self, view, reason):
            self._show_error(f"Der native WebKit-Prozess wurde beendet: {reason}")

        def _load_watchdog(self):
            self.watchdog_id = 0
            if self.frontend_ready:
                return False
            try:
                status = self._frontend_status()
                stage = status.get("stage") or "unbekannt"
                message = status.get("message") or "Kein Ready-Signal empfangen."
            except Exception as exc:
                stage = "Status nicht erreichbar"
                message = f"{exc.__class__.__name__}: {exc}"
            self._show_error(f"Die Oberfläche wurde nicht vollständig aufgebaut. Status: {stage}. {message}")
            return False

        def _reload(self):
            if self.view:
                self.view.load_uri(url.rstrip("/") + "/?native_shell=1")
            return False

        def _retry(self):
            self.retry_count = 0
            self.loaded = False
            self.frontend_ready = False
            self._show_loading("LiMaD Study wird erneut geladen …")
            GLib.timeout_add(250, self._create_webview)

        def _close(self, *_):
            server.shutdown()
            return False

        def do_open(self, files, count, hint):
            self.do_activate()

    return Application().run(sys.argv[:1])


def launch(port: int = 0) -> int:
    _log(f"Start {APP_NAME} {VERSION} als eigenständige GTK4/WebKit-Desktop-App")
    try:
        _load_native_runtime()
    except Exception as exc:
        _log(f"GTK4/WebKit-Laufzeit fehlt: {exc}")
        raise RuntimeError("LiMaD Study benötigt GTK4 und WebKitGTK 6.0") from exc
    server = None
    try:
        server, _ = start_server(port=port)
        url = f"http://127.0.0.1:{server.server_address[1]}/"
        ready, error = _wait_for_server(url)
        if not ready:
            raise RuntimeError(f"LiMaD Study Server nicht erreichbar: {error}")
        return run_native(url, server)
    except Exception:
        if server is not None:
            server.shutdown()
        raise

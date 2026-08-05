#!/usr/bin/python3
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

APP_ID = "de.limad.ScreenShare"
APP_NAME = "LiMaD auf TV übertragen"
DOUBLETAKE = "/usr/local/libexec/limad-screen-share/doubletake"
DOUBLETAKE_CTL = "/usr/local/libexec/limad-screen-share/doubletake-ctl"
FIREWALL_HELPER = "/usr/local/bin/limad-screen-share-firewall"
PORT_RANGE = "60000-60010"


def command(args: list[str], timeout: int = 45) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)


class ScreenShareWindow(Gtk.ApplicationWindow):
    def __init__(self, application: Gtk.Application) -> None:
        super().__init__(application=application, title=APP_NAME)
        self.set_default_size(900, 720)
        self.set_size_request(720, 600)
        self._busy = False
        self._build_css()
        self._build_ui()
        GLib.timeout_add_seconds(2, self.refresh_airplay_status)

    def _build_css(self) -> None:
        css = b"""
        window { background: #101014; }
        .page { padding: 28px; }
        .hero-title { font-size: 28px; font-weight: 800; }
        .hero-subtitle { color: alpha(@theme_fg_color, 0.70); font-size: 15px; }
        .card { background: alpha(@theme_fg_color, 0.055); border: 1px solid alpha(@theme_fg_color, 0.10); border-radius: 18px; padding: 22px; }
        .card-title { font-size: 20px; font-weight: 750; }
        .card-subtitle { color: alpha(@theme_fg_color, 0.68); }
        .protocol { background: alpha(#8f63ff, 0.18); color: #c9b6ff; border-radius: 999px; padding: 5px 10px; font-weight: 700; }
        .warning { background: alpha(#ffb020, 0.14); border: 1px solid alpha(#ffb020, 0.38); border-radius: 12px; padding: 12px; color: #ffd28a; }
        .status { background: alpha(#000000, 0.30); border-radius: 12px; padding: 12px; font-family: monospace; }
        .primary { background: #7c4dff; color: white; font-weight: 700; }
        .danger { color: #ff8d8d; }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_display(self.get_display(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def _build_ui(self) -> None:
        outer = Gtk.ScrolledWindow()
        outer.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        page.add_css_class("page")
        outer.set_child(page)
        self.set_child(outer)

        hero = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        icon = Gtk.Image.new_from_icon_name("limad-screen-share")
        icon.set_pixel_size(58)
        hero_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        title = Gtk.Label(label=APP_NAME, xalign=0)
        title.add_css_class("hero-title")
        subtitle = Gtk.Label(label="Bild und Ton drahtlos auf Fernseher und Streaming-Geräte übertragen", xalign=0)
        subtitle.set_wrap(True)
        subtitle.add_css_class("hero-subtitle")
        hero_text.append(title)
        hero_text.append(subtitle)
        hero.append(icon)
        hero.append(hero_text)
        page.append(hero)

        network_note = Gtk.Label(label="Computer und Zielgerät müssen sich im selben lokalen Netzwerk befinden.", xalign=0)
        network_note.set_wrap(True)
        network_note.add_css_class("card-subtitle")
        page.append(network_note)
        page.append(self._google_samsung_card())
        page.append(self._airplay_card())

    def _google_samsung_card(self) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        card.add_css_class("card")
        heading = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        title = Gtk.Label(label="Google TV, Chromecast und Samsung", xalign=0, hexpand=True)
        title.add_css_class("card-title")
        heading.append(title)
        for text in ("Google Cast", "Miracast"):
            chip = Gtk.Label(label=text)
            chip.add_css_class("protocol")
            heading.append(chip)
        card.append(heading)
        desc = Gtk.Label(
            label="Öffnet die native GNOME-Geräteauswahl. Unterstützte Fernseher werden automatisch gesucht; anschließend wählst du den Bildschirm und das Zielgerät aus.",
            xalign=0,
        )
        desc.set_wrap(True)
        desc.add_css_class("card-subtitle")
        card.append(desc)
        button = Gtk.Button(label="Geräte suchen und Bildschirm teilen")
        button.add_css_class("primary")
        button.set_halign(Gtk.Align.START)
        button.connect("clicked", self.open_network_displays)
        card.append(button)
        return card

    def _airplay_card(self) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        card.add_css_class("card")
        heading = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        title = Gtk.Label(label="Apple TV und AirPlay-Fernseher", xalign=0, hexpand=True)
        title.add_css_class("card-title")
        heading.append(title)
        chip = Gtk.Label(label="AirPlay · Experimentell")
        chip.add_css_class("protocol")
        heading.append(chip)
        card.append(heading)

        warning = Gtk.Label(
            label="AirPlay unter Linux ist noch nicht als produktionsreif einzustufen. Verwende diese Funktion nur in einem vertrauenswürdigen Heimnetz.",
            xalign=0,
        )
        warning.set_wrap(True)
        warning.add_css_class("warning")
        card.append(warning)

        form = Gtk.Grid(column_spacing=12, row_spacing=10)
        form.attach(Gtk.Label(label="Apple-TV-Adresse", xalign=0), 0, 0, 1, 1)
        self.target_entry = Gtk.Entry()
        self.target_entry.set_placeholder_text("z. B. 192.168.1.77")
        self.target_entry.set_hexpand(True)
        form.attach(self.target_entry, 1, 0, 1, 1)
        form.attach(Gtk.Label(label="PIN", xalign=0), 0, 1, 1, 1)
        self.pin_entry = Gtk.Entry()
        self.pin_entry.set_placeholder_text("nur bei Ersteinrichtung")
        self.pin_entry.set_max_length(4)
        self.pin_entry.set_input_purpose(Gtk.InputPurpose.DIGITS)
        form.attach(self.pin_entry, 1, 1, 1, 1)
        audio_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        audio_box.append(Gtk.Label(label="Audio mit übertragen", xalign=0, hexpand=True))
        self.audio_switch = Gtk.Switch(active=True)
        audio_box.append(self.audio_switch)
        form.attach(audio_box, 0, 2, 2, 1)
        card.append(form)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.start_button = Gtk.Button(label="AirPlay vorbereiten")
        self.start_button.connect("clicked", self.start_airplay)
        self.search_button = Gtk.Button(label="Geräte suchen")
        self.search_button.connect("clicked", self.discover_airplay)
        self.connect_button = Gtk.Button(label="Verbinden")
        self.connect_button.add_css_class("primary")
        self.connect_button.connect("clicked", self.connect_airplay)
        self.stop_button = Gtk.Button(label="Übertragung stoppen")
        self.stop_button.add_css_class("danger")
        self.stop_button.connect("clicked", self.stop_airplay)
        for button in (self.start_button, self.search_button, self.connect_button, self.stop_button):
            controls.append(button)
        card.append(controls)

        status_head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.spinner = Gtk.Spinner()
        self.status_label = Gtk.Label(label="AirPlay-Status wird geprüft …", xalign=0, hexpand=True)
        status_head.append(self.spinner)
        status_head.append(self.status_label)
        card.append(status_head)

        self.status_view = Gtk.TextView()
        self.status_view.set_editable(False)
        self.status_view.set_cursor_visible(False)
        self.status_view.set_monospace(True)
        self.status_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.status_view.set_size_request(-1, 110)
        self.status_view.add_css_class("status")
        card.append(self.status_view)
        return card

    def set_status(self, headline: str, details: str = "") -> None:
        self.status_label.set_text(headline)
        self.status_view.get_buffer().set_text(details.strip())

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        if busy:
            self.spinner.start()
        else:
            self.spinner.stop()
        for button in (self.start_button, self.search_button, self.connect_button, self.stop_button):
            button.set_sensitive(not busy)

    def async_run(self, worker, success_title: str) -> None:
        if self._busy:
            return
        self.set_busy(True)

        def task() -> None:
            try:
                details = worker()
                GLib.idle_add(self._finish_task, True, success_title, details)
            except Exception as exc:
                GLib.idle_add(self._finish_task, False, "Aktion fehlgeschlagen", str(exc))

        threading.Thread(target=task, daemon=True).start()

    def _finish_task(self, ok: bool, title: str, details: str) -> bool:
        self.set_busy(False)
        self.set_status(title, details)
        if ok:
            addresses = re.findall(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)", details)
            if addresses and not self.target_entry.get_text().strip():
                self.target_entry.set_text(addresses[0])
        return False

    def open_network_displays(self, _button: Gtk.Button) -> None:
        binary = shutil.which("gnome-network-displays")
        if not binary:
            self.set_status("Komponente fehlt", "GNOME Network Displays ist nicht installiert.")
            return
        try:
            subprocess.Popen([binary], start_new_session=True)
            self.set_status("Gerätesuche geöffnet", "Wähle im neuen Fenster das Zielgerät und den zu teilenden Bildschirm.")
        except OSError as exc:
            self.set_status("Start fehlgeschlagen", str(exc))

    def _firewall(self, action: str) -> str:
        pkexec = shutil.which("pkexec")
        if not pkexec:
            raise RuntimeError("Polkit/pkexec ist nicht verfügbar.")
        result = command([pkexec, FIREWALL_HELPER, action], 90)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Firewall-Freigabe fehlgeschlagen.")
        return result.stdout.strip()

    def _ctl(self, *args: str, timeout: int = 45) -> subprocess.CompletedProcess[str]:
        if not Path(DOUBLETAKE_CTL).is_file():
            raise RuntimeError("Das AirPlay-Modul ist nicht installiert.")
        return command([DOUBLETAKE_CTL, *args], timeout)

    def _ensure_daemon(self) -> str:
        status = self._ctl("status", timeout=8)
        if status.returncode == 0:
            return status.stdout.strip() or "AirPlay-Dienst läuft bereits."
        if not Path(DOUBLETAKE).is_file():
            raise RuntimeError("Das AirPlay-Modul ist nicht installiert.")
        firewall_message = self._firewall("start")
        args = [DOUBLETAKE, "-daemonize", "-port-range", PORT_RANGE]
        if not self.audio_switch.get_active():
            args.append("-no-audio")
        state_dir = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "limad-screen-share"
        state_dir.mkdir(parents=True, exist_ok=True)
        log = state_dir / "airplay.log"
        with log.open("ab") as stream:
            process = subprocess.run(args, stdout=stream, stderr=stream, timeout=20, check=False)
        if process.returncode:
            self._firewall("stop")
            raise RuntimeError(f"AirPlay-Dienst konnte nicht gestartet werden. Protokoll: {log}")
        for _ in range(20):
            status = self._ctl("status", timeout=5)
            if status.returncode == 0:
                text = status.stdout.strip() or "AirPlay-Dienst ist bereit."
                return "\n".join(filter(None, (firewall_message, text, f"Protokoll: {log}")))
            threading.Event().wait(0.25)
        self._firewall("stop")
        raise RuntimeError(f"AirPlay-Dienst antwortet nicht. Protokoll: {log}")

    def start_airplay(self, _button: Gtk.Button) -> None:
        self.async_run(self._ensure_daemon, "AirPlay ist vorbereitet")

    def discover_airplay(self, _button: Gtk.Button) -> None:
        def worker() -> str:
            start = self._ensure_daemon()
            discover = self._ctl("discover", timeout=35)
            devices = self._ctl("devices", timeout=15)
            output = "\n".join(part for part in (start, discover.stdout, discover.stderr, devices.stdout, devices.stderr) if part.strip())
            if discover.returncode and devices.returncode:
                raise RuntimeError(output or "Keine AirPlay-Geräte gefunden.")
            return output or "Suche abgeschlossen."

        self.async_run(worker, "AirPlay-Gerätesuche abgeschlossen")

    def connect_airplay(self, _button: Gtk.Button) -> None:
        target = self.target_entry.get_text().strip()
        pin = self.pin_entry.get_text().strip()
        if not re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", target):
            self.set_status("Adresse fehlt", "Bitte die IPv4-Adresse des Apple TV oder AirPlay-Fernsehers eintragen.")
            return
        if pin and not re.fullmatch(r"\d{4}", pin):
            self.set_status("PIN ungültig", "Die AirPlay-PIN muss aus genau vier Ziffern bestehen.")
            return

        def worker() -> str:
            start = self._ensure_daemon()
            args = ["connect", target]
            if pin:
                args.append(pin)
            result = self._ctl(*args, timeout=90)
            output = "\n".join(part for part in (start, result.stdout, result.stderr) if part.strip())
            if result.returncode:
                raise RuntimeError(output or "Verbindung fehlgeschlagen.")
            return output or f"Verbindung zu {target} wurde gestartet."

        self.async_run(worker, "AirPlay-Verbindung gestartet")

    def stop_airplay(self, _button: Gtk.Button) -> None:
        def worker() -> str:
            parts: list[str] = []
            try:
                result = self._ctl("disconnect", timeout=25)
                parts.extend(part.strip() for part in (result.stdout, result.stderr) if part.strip())
            except Exception as exc:
                parts.append(str(exc))
            command(["pkill", "-TERM", "-f", "/usr/local/libexec/limad-screen-share/doubletake.*-daemonize"], 10)
            try:
                message = self._firewall("stop")
                if message:
                    parts.append(message)
            except Exception as exc:
                parts.append(str(exc))
            return "\n".join(parts) or "AirPlay wurde gestoppt."

        self.async_run(worker, "AirPlay wurde gestoppt")

    def refresh_airplay_status(self) -> bool:
        if self._busy or not Path(DOUBLETAKE_CTL).is_file():
            if not Path(DOUBLETAKE_CTL).is_file():
                self.set_status("AirPlay-Modul nicht installiert", "Google Cast und Miracast können trotzdem verwendet werden.")
            return False

        def worker() -> str:
            result = self._ctl("status", timeout=8)
            if result.returncode:
                return result.stderr.strip() or "AirPlay-Dienst ist nicht aktiv."
            return result.stdout.strip() or "AirPlay-Dienst ist aktiv."

        self.async_run(worker, "AirPlay-Status")
        return False


class ScreenShareApplication(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID)

    def do_activate(self) -> None:
        window = self.props.active_window
        if window is None:
            window = ScreenShareWindow(self)
        window.present()


def main() -> int:
    return ScreenShareApplication().run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())

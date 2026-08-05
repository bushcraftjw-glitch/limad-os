#!/usr/bin/env python3
from __future__ import annotations
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk

# The launcher executes this file directly, so make the adjacent pure-Python
# backend module importable without changing the system-wide Python path.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from limad_klang_backend import (
    BANDS,
    EE_ID,
    MIN_VERSION,
    detect_easyeffects,
    find_easyeffects_socket,
    first_float,
    load_preset_cli,
    send_socket_command,
    set_bypass_cli,
    start_hidden_cli,
    version_string,
    version_supported,
    write_user_preset,
)

APP_ID = "de.limad.Klang"
PRESET_NAME = "LiMaD Klang"
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "limad"
STATE_FILE = CONFIG_DIR / "klang.json"
ACTIVE_SOCKET: Path | None = None
CONTROL_MODE = "none"
PROFILES = {
    "Neutral": {"bass": 0.0, "mid": 0.0, "treble": 0.0},
    "Musik": {"bass": 2.0, "mid": 0.0, "treble": 2.0},
    "Mehr Bass": {"bass": 4.0, "mid": 0.0, "treble": 0.0},
    "Klare Sprache": {"bass": -1.0, "mid": 2.0, "treble": 2.0},
    "Mehr Höhen": {"bass": 0.0, "mid": 0.0, "treble": 4.0},
}

def socket_ready() -> bool:
    global ACTIVE_SOCKET
    ACTIVE_SOCKET = find_easyeffects_socket()
    return ACTIVE_SOCKET is not None

def send_command(command: str, timeout: float = 1.5) -> str:
    global ACTIVE_SOCKET
    if ACTIVE_SOCKET is None:
        ACTIVE_SOCKET = find_easyeffects_socket()
    if ACTIVE_SOCKET is None:
        raise OSError("EasyEffectsServer wurde nicht gefunden")
    return send_socket_command(ACTIVE_SOCKET, command, timeout)

def spawn(args: list[str]) -> None:
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

def wait_socket(seconds: float) -> bool:
    for _ in range(round(seconds * 10)):
        if socket_ready():
            return True
        time.sleep(0.1)
    return socket_ready()

def start_easyeffects() -> tuple[bool, str]:
    """Prepare a dependable preset path, then enable direct control if possible.

    EasyEffects' local server is optional and can be disabled in its settings.
    LiMaD Klang therefore never treats a missing socket as a fatal error.
    """
    global CONTROL_MODE
    install = detect_easyeffects()
    if not install.installed:
        return False, "EasyEffects ist nicht installiert."

    subprocess.run(["/usr/local/bin/limad-install-klang-preset"], check=False)
    supported = version_supported(install.version)
    readable_version = version_string(install.version, install.version_text)
    if supported is False:
        minimum = ".".join(map(str, MIN_VERSION))
        return False, f"EasyEffects {readable_version} ist zu alt; mindestens {minimum} wird benötigt."

    # Always establish the preset mode first.  It works independently of the
    # optional EasyEffectsServer socket and is therefore the safe baseline.
    try:
        write_user_preset(PROFILES["Neutral"])
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        return False, f"LiMaD-Klangprofil konnte nicht vorbereitet werden: {exc}"

    start_hidden_cli()
    result = load_preset_cli()
    if not result.ok:
        # A first start may still be creating the Flatpak data directories.
        start_hidden_cli()
        time.sleep(1.5)
        result = load_preset_cli()
    if not result.ok:
        return False, f"Das LiMaD-Klangprofil konnte nicht geladen werden: {result.detail}"

    CONTROL_MODE = "preset"
    suffix = "" if supported is not None else " · Version nicht gemeldet"

    # Direct control is an optional acceleration.  Failure falls back to the
    # already working preset mode and is not shown as an application error.
    if not socket_ready():
        wait_socket(4)
    if socket_ready():
        try:
            send_command(f"load_preset:output:{PRESET_NAME}")
            send_command("global_bypass:0")
            probe = send_command("get_property:output:equalizer:0:left:band0Gain")
            if first_float(probe) is not None:
                CONTROL_MODE = "server"
                send_command("hide_window")
                return True, f"EasyEffects {readable_version} verbunden · Direktsteuerung{suffix}"
        except OSError:
            CONTROL_MODE = "preset"

    return True, f"EasyEffects {readable_version} verbunden · Preset-Steuerung aktiv{suffix}"

class KlangWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application) -> None:
        super().__init__(application=app, title="LiMaD Klang")
        self.set_default_size(590, 520)
        self.set_size_request(440, 400)
        self._ready = False
        self._debounce_id = 0
        self._bypassed = False
        self._values = self._load_state()
        css = Gtk.CssProvider()
        css.load_from_data(b"window{background:#17131d;color:#f5effa}.title{font-size:24px;font-weight:800}.subtitle{color:#b9a9c4}.profile{border-radius:999px;padding:8px 14px}.primary{background:#8b3dff;color:white;font-weight:700}.status-ok{color:#7ee787}.status-warn{color:#f2cc60}scale trough{min-height:8px;border-radius:999px}scale highlight{background:#9a50ff;border-radius:999px}")
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        root.set_margin_top(22); root.set_margin_bottom(22); root.set_margin_start(24); root.set_margin_end(24)
        self.set_child(root)
        heading = Gtk.Label(label="LiMaD Klang"); heading.add_css_class("title"); heading.set_xalign(0); root.append(heading)
        subtitle = Gtk.Label(label="Bass, Mitten und Höhen direkt über EasyEffects anpassen"); subtitle.add_css_class("subtitle"); subtitle.set_xalign(0); root.append(subtitle)
        profiles = Gtk.FlowBox(); profiles.set_selection_mode(Gtk.SelectionMode.NONE); profiles.set_max_children_per_line(5); profiles.set_row_spacing(8); profiles.set_column_spacing(8)
        for name, values in PROFILES.items():
            button = Gtk.Button(label=name); button.add_css_class("profile"); button.connect("clicked", self._on_profile, values); profiles.append(button)
        root.append(profiles)
        self.scales: dict[str, Gtk.Scale] = {}
        labels = {"bass": ("Bass", "Tiefe Frequenzen"), "mid": ("Mitten", "Stimmen und Instrumente"), "treble": ("Höhen", "Klarheit und Brillanz")}
        for key in ("bass", "mid", "treble"):
            row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            label = Gtk.Label(label=labels[key][0]); label.set_xalign(0); label.set_hexpand(True)
            detail = Gtk.Label(label=labels[key][1]); detail.add_css_class("subtitle")
            value_label = Gtk.Label(label=f"{self._values[key]:+.1f} dB")
            line.append(label); line.append(detail); line.append(value_label); row.append(line)
            scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, -12.0, 12.0, 0.5)
            scale.set_draw_value(False); scale.set_hexpand(True); scale.set_value(self._values[key]); scale.connect("value-changed", self._on_scale, key, value_label)
            row.append(scale); root.append(row); self.scales[key] = scale
        options = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.bypass = Gtk.Switch(); self.bypass.set_active(True); self.bypass.connect("notify::active", self._on_effect_switch)
        options.append(self.bypass); options.append(Gtk.Label(label="Klangregelung aktiv")); root.append(options)
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        reset = Gtk.Button(label="Zurücksetzen"); reset.connect("clicked", self._on_profile, PROFILES["Neutral"])
        retry = Gtk.Button(label="Neu verbinden"); retry.connect("clicked", self._retry)
        advanced = Gtk.Button(label="EasyEffects öffnen"); advanced.connect("clicked", self._show_advanced); advanced.add_css_class("primary")
        actions.append(reset); actions.append(retry); actions.append(advanced); root.append(actions)
        self.status = Gtk.Label(label="EasyEffects wird geprüft …"); self.status.set_xalign(0); self.status.set_wrap(True); self.status.add_css_class("subtitle"); root.append(self.status)
        threading.Thread(target=self._prepare_backend, daemon=True).start()

    def _load_state(self) -> dict[str, float]:
        values = dict(PROFILES["Neutral"])
        try:
            raw = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            for key in values:
                values[key] = max(-12.0, min(12.0, float(raw.get(key, values[key]))))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
        return values

    def _save_state(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(self._values, indent=2) + "\n", encoding="utf-8")

    def _prepare_backend(self) -> None:
        ok, message = start_easyeffects()
        GLib.idle_add(self._backend_ready, ok, message)

    def _backend_ready(self, ok: bool, message: str) -> bool:
        self._ready = ok
        self.status.set_text(message + (" · Änderungen wirken sofort" if ok else ""))
        self.status.remove_css_class("status-ok"); self.status.remove_css_class("status-warn")
        self.status.add_css_class("status-ok" if ok else "status-warn")
        for scale in self.scales.values():
            scale.set_sensitive(ok)
        self.bypass.set_sensitive(ok)
        if ok:
            self._apply_values()
        return GLib.SOURCE_REMOVE

    def _retry(self, _button: Gtk.Button) -> None:
        self.status.set_text("EasyEffects wird erneut verbunden …")
        threading.Thread(target=self._prepare_backend, daemon=True).start()

    def _on_profile(self, _button: Gtk.Button, values: dict[str, float]) -> None:
        for key, value in values.items():
            self.scales[key].set_value(value)

    def _on_scale(self, scale: Gtk.Scale, key: str, value_label: Gtk.Label) -> None:
        value = round(scale.get_value() * 2.0) / 2.0
        self._values[key] = value
        value_label.set_text(f"{value:+.1f} dB")
        self._save_state()
        if self._debounce_id:
            GLib.source_remove(self._debounce_id)
        self._debounce_id = GLib.timeout_add(120, self._apply_values)

    def _apply_values(self) -> bool:
        self._debounce_id = 0
        if not self._ready or self._bypassed:
            return GLib.SOURCE_REMOVE
        values = dict(self._values)
        threading.Thread(target=self._apply_values_worker, args=(values,), daemon=True).start()
        return GLib.SOURCE_REMOVE

    def _apply_values_worker(self, values: dict[str, float]) -> None:
        global CONTROL_MODE
        try:
            if CONTROL_MODE == "server" and socket_ready():
                try:
                    for section, bands in BANDS.items():
                        value = values[section]
                        for channel in ("left", "right"):
                            for band in bands:
                                send_command(f"set_property:output:equalizer:0:{channel}:band{band}Gain:{value:.1f}")
                    headroom = -0.75 * max(0.0, *values.values())
                    send_command(f"set_property:output:equalizer:0:outputGain:{headroom:.2f}")
                    bass_reply = send_command("get_property:output:equalizer:0:left:band0Gain")
                    treble_reply = send_command("get_property:output:equalizer:0:left:band9Gain")
                    bass_value = first_float(bass_reply)
                    treble_value = first_float(treble_reply)
                    if bass_value is None or treble_value is None:
                        raise OSError("EasyEffects lieferte keine überprüfbaren Equalizerwerte")
                    if abs(bass_value - values["bass"]) > 0.26 or abs(treble_value - values["treble"]) > 0.26:
                        raise OSError("EasyEffects hat die Reglerwerte nicht übernommen")
                    GLib.idle_add(self._set_status, "Gespeichert · EasyEffects hat die Werte bestätigt", True)
                    return
                except OSError:
                    # A disappearing or disabled local server must not disable
                    # the sliders.  Continue with the persistent preset path.
                    CONTROL_MODE = "preset"

            write_user_preset(values)
            result = load_preset_cli()
            if not result.ok:
                start_hidden_cli()
                time.sleep(0.8)
                result = load_preset_cli()
            if not result.ok:
                raise OSError(result.detail)
            GLib.idle_add(self._set_status, "Gespeichert · Preset wurde sofort neu geladen", True)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            GLib.idle_add(self._connection_failed, str(exc))

    def _set_status(self, message: str, ok: bool) -> bool:
        self.status.set_text(message)
        self.status.remove_css_class("status-ok")
        self.status.remove_css_class("status-warn")
        self.status.add_css_class("status-ok" if ok else "status-warn")
        return GLib.SOURCE_REMOVE

    def _connection_failed(self, detail: str) -> bool:
        self._ready = False
        self._set_status(f"Steuerung fehlgeschlagen · {detail} · bitte Neu verbinden", False)
        return GLib.SOURCE_REMOVE

    def _on_effect_switch(self, switch: Gtk.Switch, _param: object) -> None:
        global CONTROL_MODE
        self._bypassed = not switch.get_active()
        if not self._ready:
            return
        try:
            handled = False
            if CONTROL_MODE == "server" and socket_ready():
                try:
                    send_command(f"global_bypass:{1 if self._bypassed else 0}")
                    handled = True
                except OSError:
                    CONTROL_MODE = "preset"
            if not handled:
                result = set_bypass_cli(self._bypassed)
                if not result.ok:
                    raise OSError(result.detail)
            self._apply_values()
        except OSError as exc:
            self._connection_failed(str(exc))

    def _show_advanced(self, _button: Gtk.Button) -> None:
        if CONTROL_MODE == "server" and socket_ready():
            try:
                send_command("show_window")
                return
            except OSError:
                pass
        spawn(["flatpak", "run", EE_ID])

class KlangApp(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
    def do_activate(self) -> None:
        win = self.props.active_window or KlangWindow(self)
        win.present()

if __name__ == "__main__":
    raise SystemExit(KlangApp().run())

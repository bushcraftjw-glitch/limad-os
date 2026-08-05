from __future__ import annotations

import json
import threading
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


class NativePlayerUnavailable(RuntimeError):
    pass


class NativeMediaPlayer:
    def __init__(self, application, base_url: str, log):
        self.application = application
        self.base_url = base_url.rstrip("/") + "/"
        self.log = log
        self.window = None
        self.GLib = None
        self.Gst = None
        self.Gtk = None
        self.pipeline = None
        self.video_sink = None
        self.picture = None
        self.audio_placeholder = None
        self.play_button = None
        self.position_scale = None
        self.current_label = None
        self.duration_label = None
        self.title_label = None
        self.status_label = None
        self.decoder_label = None
        self.quality_dropdown = None
        self.decoder_dropdown = None
        self.download_button = None
        self.playlist_button = None
        self.overlay_controls_revealer = None
        self.timeline_revealer = None
        self.controls_hide_id = 0
        self.subtitle_dropdown = None
        self.subtitle_tracks: list[tuple[int, str]] = [(-1, "Aus")]
        self.subtitle_stream_signature: tuple[str, ...] = ()
        self.payload: dict[str, Any] = {}
        self.playlist: list[dict[str, Any]] = []
        self.index = 0
        self.source_index = 0
        self.duration_ns = 0
        self.updating_scale = False
        self.user_paused = False
        self.decoder_name = "wird ermittelt"
        self.decoder_hardware = None
        self.qos_processed = 0
        self.qos_dropped = 0
        self.tick_id = 0
        self.setting_quality = False
        self._load_runtime()

    def _load_runtime(self):
        try:
            import gi
            gi.require_version("Gst", "1.0")
            from gi.repository import GLib, Gst, Gtk
        except Exception as exc:
            raise NativePlayerUnavailable(f"GStreamer-GTK-Laufzeit fehlt: {exc}") from exc
        Gst.init(None)
        if Gst.ElementFactory.find("gtk4paintablesink") is None:
            raise NativePlayerUnavailable("Das GStreamer-Element gtk4paintablesink ist nicht installiert.")
        self.GLib = GLib
        self.Gst = Gst
        self.Gtk = Gtk
        self._install_css()

    def _install_css(self):
        css = b"""
        .limad-player-root {
            background: #15131c;
            color: #f7f4ff;
        }
        .limad-player-titlebar-handle,
        .limad-player-header {
            background: #303030;
            border-bottom: 1px solid rgba(0,0,0,.28);
            min-height: 31px;
            padding: 0;
            margin: 0;
            box-shadow: none;
        }
        .limad-player-header {
            padding: 0 9px;
        }
        .limad-player-title {
            font-weight: 700;
            color: #f6f2ff;
            font-size: 12px;
        }
        .limad-window-controls {
            margin: 0;
            padding: 0;
        }
        button.limad-player-menu {
            min-width: 30px;
            min-height: 24px;
            padding: 0 7px;
            margin: 0;
            border-radius: 8px;
            background: transparent;
            background-image: none;
            border: 0;
            box-shadow: none;
            color: #e8e2f2;
            font-size: 15px;
            font-weight: 700;
        }
        button.limad-player-menu:hover {
            background: rgba(137,78,255,.11);
        }
        .limad-player-stage {
            background: #050507;
        }
        .limad-player-overlay-controls {
            padding: 0;
        }
        button.limad-player-overlay-button {
            min-width: 42px;
            min-height: 42px;
            padding: 0;
            border-radius: 999px;
            border: 1px solid rgba(255,255,255,.16);
            background: rgba(12,10,16,.72);
            background-image: none;
            box-shadow: 0 4px 16px rgba(0,0,0,.28);
            color: #ffffff;
            font-size: 18px;
            font-weight: 800;
        }
        button.limad-player-overlay-button:hover {
            background: rgba(34,27,45,.88);
            border-color: rgba(196,164,255,.38);
        }
        button.limad-player-overlay-primary {
            min-width: 60px;
            min-height: 60px;
            border: 2px solid #ff7a21;
            font-size: 24px;
            background: rgba(12,10,16,.82);
        }
        .limad-player-timeline-overlay {
            background: rgba(8,7,11,.72);
            border-radius: 9px;
            padding: 5px 7px;
            margin: 0 8px 8px;
        }
        .limad-player-time {
            color: #f1ecf8;
            font-variant-numeric: tabular-nums;
            min-width: 39px;
            font-size: 11px;
        }
        scale.limad-player-scale {
            min-height: 16px;
            padding: 0;
            margin: 0;
        }
        button.limad-player-fullscreen {
            min-width: 28px;
            min-height: 26px;
            padding: 0;
            margin: 0;
            border-radius: 7px;
            border: 0;
            background: transparent;
            background-image: none;
            box-shadow: none;
            color: #f5f1fa;
            font-size: 14px;
        }
        button.limad-player-fullscreen:hover {
            background: rgba(137,78,255,.14);
        }
        .limad-player-footer {
            background: #1d1925;
            border-top: 1px solid rgba(255,255,255,.07);
            padding: 6px 8px;
        }
        button.limad-player-action {
            min-height: 30px;
            padding: 2px 12px;
            margin: 0;
            border: 1px solid rgba(177,137,255,.14);
            background: rgba(255,255,255,.018);
            background-image: none;
            box-shadow: none;
            border-radius: 8px;
            color: #e9e3f1;
            font-size: 12px;
            font-weight: 600;
        }
        button.limad-player-action:hover {
            background: rgba(137,78,255,.10);
            border-color: rgba(177,137,255,.28);
        }
        .limad-player-popover {
            padding: 12px;
            min-width: 300px;
        }
        .limad-player-popover-title {
            font-weight: 700;
            margin-bottom: 4px;
        }
        .limad-player-status {
            color: #b8afc8;
            font-size: 11px;
        }
        .limad-player-diagnostics {
            color: #9c8cb6;
            font-size: 10px;
        }
        .limad-player-shortcuts {
            color: #8f829f;
            font-size: 10px;
        }
        """
        try:
            provider = self.Gtk.CssProvider()
            provider.load_from_data(css)
            from gi.repository import Gdk
            display = Gdk.Display.get_default()
            if display is not None:
                self.Gtk.StyleContext.add_provider_for_display(display, provider, self.Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        except Exception as exc:
            self.log(f"Native-Player-CSS konnte nicht geladen werden: {exc}")

    def open(self, payload: dict[str, Any]):
        playlist = payload.get("playlist")
        if not isinstance(playlist, list) or not playlist:
            raise ValueError("Die native Player-Wiedergabeliste ist leer.")
        self.payload = payload
        self.playlist = [item for item in playlist if isinstance(item, dict) and item.get("sources")]
        if not self.playlist:
            raise ValueError("Es wurden keine abspielbaren Medien übergeben.")
        requested_index = int(payload.get("index") or 0)
        self.index = max(0, min(requested_index, len(self.playlist) - 1))
        if self.window is None:
            self._build_window()
        self._load_item(self.index, autoplay=bool(payload.get("autoplay", True)))
        self.window.present()
        self._try_keep_above(True)

    def _build_window(self):
        Gtk = self.Gtk
        self.window = Gtk.ApplicationWindow(application=self.application)
        self.window.set_title("LiMaD Study Player")
        self.window.set_default_size(720, 470)
        self.window.set_size_request(390, 280)
        self.window.connect("close-request", self._on_close)

        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.window.add_controller(key_controller)

        titlebar = Gtk.CenterBox()
        titlebar.add_css_class("limad-player-header")
        titlebar.set_size_request(-1, 31)
        titlebar.set_hexpand(True)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        controls.add_css_class("limad-window-controls")
        controls.set_valign(Gtk.Align.CENTER)
        controls.append(self._window_button("close", "Schließen", self._close_window))
        controls.append(self._window_button("maximize", "Maximieren", self._toggle_maximize))
        controls.append(self._window_button("minimize", "Minimieren", self._minimize))
        titlebar.set_start_widget(controls)

        self.title_label = Gtk.Label(label="LiMaD Study Player")
        self.title_label.add_css_class("limad-player-title")
        self.title_label.set_max_width_chars(56)
        self.title_label.set_ellipsize(3)
        self.title_label.set_halign(Gtk.Align.CENTER)
        self.title_label.set_valign(Gtk.Align.CENTER)
        titlebar.set_center_widget(self.title_label)

        menu_button = Gtk.MenuButton(label="•••")
        menu_button.add_css_class("limad-player-menu")
        menu_button.set_size_request(30, 24)
        menu_button.set_valign(Gtk.Align.CENTER)
        menu_button.set_tooltip_text("Player-Einstellungen und Diagnose")
        titlebar.set_end_widget(menu_button)

        titlebar_handle_type = getattr(Gtk, "WindowHandle", None)
        if titlebar_handle_type is not None:
            titlebar_handle = titlebar_handle_type()
            titlebar_handle.add_css_class("limad-player-titlebar-handle")
            titlebar_handle.set_size_request(-1, 31)
            titlebar_handle.set_child(titlebar)
            self.window.set_titlebar(titlebar_handle)
        else:
            self.window.set_titlebar(titlebar)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        root.add_css_class("limad-player-root")
        self.window.set_child(root)

        stage = Gtk.Overlay()
        stage.set_hexpand(True)
        stage.set_vexpand(True)
        stage.add_css_class("limad-player-stage")
        self.stage = stage

        self.picture = Gtk.Picture()
        self.picture.set_hexpand(True)
        self.picture.set_vexpand(True)
        try:
            self.picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        except Exception:
            pass
        stage.set_child(self.picture)

        self.audio_placeholder = Gtk.Label(label="♫")
        self.audio_placeholder.set_halign(Gtk.Align.CENTER)
        self.audio_placeholder.set_valign(Gtk.Align.CENTER)
        self.audio_placeholder.set_opacity(0.42)
        self.audio_placeholder.set_markup('<span size="72000">♫</span>')
        stage.add_overlay(self.audio_placeholder)

        overlay_controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        overlay_controls.add_css_class("limad-player-overlay-controls")
        overlay_controls.set_halign(Gtk.Align.CENTER)
        overlay_controls.set_valign(Gtk.Align.CENTER)
        previous_button = self._text_button("|◀", "Vorheriger Titel", lambda *_: self._previous())
        previous_button.add_css_class("limad-player-overlay-button")
        previous_button.set_size_request(42, 42)
        self.play_button = self._text_button("▶", "Wiedergabe/Pause", lambda *_: self._toggle_play())
        self.play_button.add_css_class("limad-player-overlay-button")
        self.play_button.add_css_class("limad-player-overlay-primary")
        self.play_button.set_size_request(60, 60)
        next_button = self._text_button("▶|", "Nächster Titel", lambda *_: self._next())
        next_button.add_css_class("limad-player-overlay-button")
        next_button.set_size_request(42, 42)
        overlay_controls.append(previous_button)
        overlay_controls.append(self.play_button)
        overlay_controls.append(next_button)
        self.overlay_controls_revealer = Gtk.Revealer()
        self.overlay_controls_revealer.set_transition_type(Gtk.RevealerTransitionType.CROSSFADE)
        self.overlay_controls_revealer.set_transition_duration(180)
        self.overlay_controls_revealer.set_reveal_child(True)
        self.overlay_controls_revealer.set_halign(Gtk.Align.CENTER)
        self.overlay_controls_revealer.set_valign(Gtk.Align.CENTER)
        self.overlay_controls_revealer.set_child(overlay_controls)
        stage.add_overlay(self.overlay_controls_revealer)

        timeline = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        timeline.add_css_class("limad-player-timeline-overlay")
        timeline.set_halign(Gtk.Align.FILL)
        timeline.set_valign(Gtk.Align.END)
        self.current_label = Gtk.Label(label="0:00")
        self.current_label.add_css_class("limad-player-time")
        self.position_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1000, 1)
        self.position_scale.add_css_class("limad-player-scale")
        self.position_scale.set_hexpand(True)
        self.position_scale.set_draw_value(False)
        self.position_scale.connect("change-value", self._seek_requested)
        self.duration_label = Gtk.Label(label="0:00")
        self.duration_label.add_css_class("limad-player-time")
        fullscreen_button = self._text_button("⛶", "Vollbild; ESC beendet Vollbild", lambda *_: self._toggle_fullscreen())
        fullscreen_button.add_css_class("limad-player-fullscreen")
        fullscreen_button.set_size_request(28, 26)
        timeline.append(self.current_label)
        timeline.append(self.position_scale)
        timeline.append(self.duration_label)
        timeline.append(fullscreen_button)
        self.timeline_revealer = Gtk.Revealer()
        self.timeline_revealer.set_transition_type(Gtk.RevealerTransitionType.CROSSFADE)
        self.timeline_revealer.set_transition_duration(180)
        self.timeline_revealer.set_reveal_child(True)
        self.timeline_revealer.set_halign(Gtk.Align.FILL)
        self.timeline_revealer.set_valign(Gtk.Align.END)
        self.timeline_revealer.set_child(timeline)
        stage.add_overlay(self.timeline_revealer)
        self._install_controls_activity_handlers(stage)
        root.append(stage)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        footer.add_css_class("limad-player-footer")
        self.download_button = self._text_button("↓  Herunterladen", "Medium herunterladen", lambda *_: self._download())
        self.download_button.set_hexpand(True)
        self.playlist_button = self._text_button("▣  Zu Playlist", "Zu Playlist hinzufügen", lambda *_: self._choose_playlist())
        self.playlist_button.set_hexpand(True)
        footer.append(self.download_button)
        footer.append(self.playlist_button)
        root.append(footer)

        popover = Gtk.Popover()
        popover_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9)
        popover_box.add_css_class("limad-player-popover")
        popover_title = Gtk.Label(label="Wiedergabe-Einstellungen", xalign=0)
        popover_title.add_css_class("limad-player-popover-title")
        popover_box.append(popover_title)

        quality_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        quality_row.append(Gtk.Label(label="Qualität", xalign=0))
        quality_spacer = Gtk.Box()
        quality_spacer.set_hexpand(True)
        quality_row.append(quality_spacer)
        self.quality_dropdown = Gtk.DropDown()
        self.quality_dropdown.connect("notify::selected", self._quality_changed)
        quality_row.append(self.quality_dropdown)
        popover_box.append(quality_row)

        subtitle_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        subtitle_row.append(Gtk.Label(label="Untertitel", xalign=0))
        subtitle_spacer = Gtk.Box()
        subtitle_spacer.set_hexpand(True)
        subtitle_row.append(subtitle_spacer)
        self.subtitle_dropdown = Gtk.DropDown.new(Gtk.StringList.new(["Aus"]), None)
        self.subtitle_dropdown.set_selected(0)
        self.subtitle_dropdown.set_sensitive(False)
        self.subtitle_dropdown.connect("notify::selected", self._subtitle_changed)
        subtitle_row.append(self.subtitle_dropdown)
        popover_box.append(subtitle_row)
        subtitle_note = Gtk.Label(label="Eingebettete Untertitel können hier ausgeschaltet werden. Fest ins Videobild eingebrannte Schrift bleibt sichtbar.", xalign=0)
        subtitle_note.set_wrap(True)
        subtitle_note.add_css_class("limad-player-shortcuts")
        popover_box.append(subtitle_note)

        decoder_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        decoder_row.append(Gtk.Label(label="Decoder", xalign=0))
        decoder_spacer = Gtk.Box()
        decoder_spacer.set_hexpand(True)
        decoder_row.append(decoder_spacer)
        decoder_model = Gtk.StringList.new(["Automatisch", "Software bevorzugen"])
        self.decoder_dropdown = Gtk.DropDown.new(decoder_model, None)
        self.decoder_dropdown.connect("notify::selected", self._decoder_mode_changed)
        decoder_row.append(self.decoder_dropdown)
        popover_box.append(decoder_row)

        pin_button = Gtk.CheckButton(label="Player möglichst im Vordergrund halten")
        pin_button.set_active(True)
        pin_button.connect("toggled", lambda button: self._try_keep_above(button.get_active()))
        popover_box.append(pin_button)

        seek_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        seek_back = self._text_button("−10 Sekunden", "10 Sekunden zurück", lambda *_: self._seek_relative(-10))
        seek_back.set_hexpand(True)
        seek_forward = self._text_button("+10 Sekunden", "10 Sekunden vor", lambda *_: self._seek_relative(10))
        seek_forward.set_hexpand(True)
        seek_row.append(seek_back)
        seek_row.append(seek_forward)
        popover_box.append(seek_row)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        popover_box.append(separator)
        self.status_label = Gtk.Label(label="Player wird vorbereitet …", xalign=0)
        self.status_label.set_wrap(True)
        self.status_label.add_css_class("limad-player-status")
        popover_box.append(self.status_label)
        self.decoder_label = Gtk.Label(label="GStreamer • Decoder wird ermittelt", xalign=0)
        self.decoder_label.set_wrap(True)
        self.decoder_label.add_css_class("limad-player-diagnostics")
        popover_box.append(self.decoder_label)
        shortcuts = Gtk.Label(label="Tastatur: Leertaste = Pause • ←/→ = 10 s • F = Vollbild • ESC = zurück", xalign=0)
        shortcuts.set_wrap(True)
        shortcuts.add_css_class("limad-player-shortcuts")
        popover_box.append(shortcuts)
        popover.set_child(popover_box)
        menu_button.set_popover(popover)

    def _window_button(self, kind: str, tooltip: str, callback):
        Gtk = self.Gtk
        control = Gtk.DrawingArea()
        control.set_content_width(20)
        control.set_content_height(20)
        control.set_size_request(20, 20)
        control.set_hexpand(False)
        control.set_vexpand(False)
        control.set_valign(Gtk.Align.CENTER)
        control.set_tooltip_text(tooltip)
        control.set_can_target(True)

        state = {"hovered": False}
        colors = {
            "close": (233 / 255, 82 / 255, 74 / 255),
            "maximize": (89 / 255, 200 / 255, 55 / 255),
            "minimize": (241 / 255, 174 / 255, 27 / 255),
        }

        def draw(_area, cr, width, height):
            import cairo
            import math

            cx = width / 2
            cy = height / 2
            radius = 6.3
            red, green, blue = colors[kind]

            cr.arc(cx, cy, radius, 0, math.tau)
            cr.set_source_rgb(red, green, blue)
            cr.fill_preserve()
            cr.set_line_width(0.7)
            cr.set_source_rgba(0.10, 0.09, 0.10, 0.30)
            cr.stroke()

            cr.arc(cx, cy - radius * 0.20, radius * 0.78, math.pi * 1.08, math.pi * 1.92)
            cr.set_line_width(0.45)
            cr.set_source_rgba(1, 1, 1, 0.22)
            cr.stroke()

            if not state["hovered"]:
                return

            cr.set_source_rgba(0.16, 0.13, 0.14, 0.88)
            cr.set_line_width(1.55)
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.set_line_join(cairo.LINE_JOIN_ROUND)

            if kind == "close":
                extent = radius * 0.48
                cr.move_to(cx - extent, cy - extent)
                cr.line_to(cx + extent, cy + extent)
                cr.move_to(cx + extent, cy - extent)
                cr.line_to(cx - extent, cy + extent)
                cr.stroke()
            elif kind == "minimize":
                extent = radius * 0.58
                cr.move_to(cx - extent, cy)
                cr.line_to(cx + extent, cy)
                cr.stroke()
            else:
                outer = radius * 0.60
                inner = radius * 0.12
                head = radius * 0.30

                cr.move_to(cx + inner, cy - inner)
                cr.line_to(cx + outer, cy - outer)
                cr.move_to(cx + outer, cy - outer)
                cr.line_to(cx + outer - head, cy - outer)
                cr.move_to(cx + outer, cy - outer)
                cr.line_to(cx + outer, cy - outer + head)

                cr.move_to(cx - inner, cy + inner)
                cr.line_to(cx - outer, cy + outer)
                cr.move_to(cx - outer, cy + outer)
                cr.line_to(cx - outer + head, cy + outer)
                cr.move_to(cx - outer, cy + outer)
                cr.line_to(cx - outer, cy + outer - head)
                cr.stroke()

        control.set_draw_func(draw)

        gesture = Gtk.GestureClick()
        gesture.set_button(1)
        try:
            gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        except Exception:
            pass
        gesture.connect("released", lambda *_args: callback())
        control.add_controller(gesture)

        motion = Gtk.EventControllerMotion()

        def set_hovered(value: bool):
            state["hovered"] = value
            control.queue_draw()
            try:
                control.set_cursor_from_name("pointer" if value else None)
            except Exception:
                pass

        motion.connect("enter", lambda *_args: set_hovered(True))
        motion.connect("leave", lambda *_args: set_hovered(False))
        control.add_controller(motion)
        return control

    def _text_button(self, text: str, tooltip: str, callback):
        button = self.Gtk.Button(label=text)
        button.add_css_class("limad-player-action")
        button.set_tooltip_text(tooltip)
        button.set_focusable(False)
        button.set_vexpand(False)
        button.connect("clicked", callback)
        return button

    def _install_controls_activity_handlers(self, stage):
        try:
            motion = self.Gtk.EventControllerMotion()
            motion.connect("enter", lambda *_args: self._show_controls(True))
            motion.connect("motion", lambda *_args: self._show_controls(True))
            stage.add_controller(motion)
        except Exception as exc:
            self.log(f"Player-Mausbewegung konnte nicht überwacht werden: {exc}")
        try:
            click = self.Gtk.GestureClick()
            click.connect("pressed", lambda *_args: self._show_controls(True))
            stage.add_controller(click)
        except Exception as exc:
            self.log(f"Player-Klickaktivität konnte nicht überwacht werden: {exc}")

    def _cancel_controls_hide(self):
        if self.controls_hide_id and self.GLib is not None:
            try:
                self.GLib.source_remove(self.controls_hide_id)
            except Exception:
                pass
        self.controls_hide_id = 0

    def _is_playing(self) -> bool:
        if self.pipeline is None or self.Gst is None:
            return False
        try:
            _result, state, _pending = self.pipeline.get_state(0)
            return state == self.Gst.State.PLAYING
        except Exception:
            return False

    def _show_controls(self, schedule_hide: bool = True):
        self._cancel_controls_hide()
        if self.overlay_controls_revealer is not None:
            self.overlay_controls_revealer.set_reveal_child(True)
        if self.timeline_revealer is not None:
            self.timeline_revealer.set_reveal_child(True)
        if schedule_hide and self._is_playing() and self.GLib is not None:
            self.controls_hide_id = self.GLib.timeout_add(3000, self._hide_controls)
        return False

    def _hide_controls(self):
        self.controls_hide_id = 0
        if not self._is_playing():
            return False
        if self.overlay_controls_revealer is not None:
            self.overlay_controls_revealer.set_reveal_child(False)
        if self.timeline_revealer is not None:
            self.timeline_revealer.set_reveal_child(False)
        return False

    def _try_keep_above(self, enabled: bool):
        if self.window is None:
            return
        method = getattr(self.window, "set_keep_above", None)
        if callable(method):
            try:
                method(bool(enabled))
                return
            except Exception:
                pass
        if enabled and self.status_label is not None:
            self.status_label.set_text("Eigenständiges Playerfenster aktiv. Dauerhaftes 'Immer im Vordergrund' wird unter Wayland vom Fenstermanager bestimmt.")

    def _on_key_pressed(self, _controller, keyval, _keycode, _state):
        self._show_controls(True)
        try:
            from gi.repository import Gdk
        except Exception:
            return False
        if self.window is None:
            return False
        if keyval == Gdk.KEY_Escape:
            try:
                if self.window.is_fullscreen():
                    self.window.unfullscreen()
                    return True
            except Exception:
                pass
            try:
                if self.window.is_maximized():
                    self.window.unmaximize()
                    return True
            except Exception:
                pass
            return False
        if keyval in {Gdk.KEY_space, Gdk.KEY_KP_Space}:
            self._toggle_play()
            return True
        if keyval in {Gdk.KEY_Left, Gdk.KEY_KP_Left}:
            self._seek_relative(-10)
            return True
        if keyval in {Gdk.KEY_Right, Gdk.KEY_KP_Right}:
            self._seek_relative(10)
            return True
        if keyval in {Gdk.KEY_f, Gdk.KEY_F, Gdk.KEY_F11}:
            self._toggle_fullscreen()
            return True
        return False

    def _close_window(self, *_):
        if self.window is not None:
            self.window.close()

    def _toggle_maximize(self, *_):
        if self.window is None:
            return
        try:
            maximized = bool(self.window.is_maximized())
        except Exception:
            maximized = False
        if maximized:
            self.window.unmaximize()
        else:
            self.window.maximize()

    def _minimize(self, *_):
        if self.window is not None:
            self.window.minimize()

    def _toggle_fullscreen(self, *_):
        self._show_controls(True)
        if self.window is None:
            return
        try:
            fullscreened = bool(self.window.is_fullscreen())
        except Exception:
            fullscreened = False
        if fullscreened:
            self.window.unfullscreen()
        else:
            self.window.fullscreen()

    def _on_close(self, *_):
        self._stop_pipeline()
        if self.tick_id:
            self.GLib.source_remove(self.tick_id)
            self.tick_id = 0
        self._cancel_controls_hide()
        self.setting_quality = False
        self.window = None
        return False

    def _current_item(self) -> dict[str, Any]:
        return self.playlist[self.index]

    def _sources(self) -> list[dict[str, Any]]:
        sources = self._current_item().get("sources") or []
        return [source for source in sources if isinstance(source, dict) and source.get("url")]

    def _source_height(self, source: dict[str, Any]) -> int:
        try:
            direct = int(source.get("height") or 0)
        except Exception:
            direct = 0
        if direct > 0:
            return direct
        quality = str(source.get("quality") or "")
        digits = "".join(character for character in quality if character.isdigit())
        return int(digits) if digits else 0

    def _preferred_source_index(self, sources: list[dict[str, Any]]) -> int:
        preferred = str(self.payload.get("preferred_quality") or "auto")
        if preferred != "auto":
            for index, source in enumerate(sources):
                if str(source.get("quality") or "") == preferred:
                    return index
        item_type = str(self._current_item().get("type") or "video")
        if item_type == "audio":
            for index, source in enumerate(sources):
                if str(source.get("mime_type") or "").lower() in {"audio/mpeg", "audio/mp3"}:
                    return index
            return 0
        candidates = [(index, self._source_height(source)) for index, source in enumerate(sources)]
        candidates = [(index, height) for index, height in candidates if height > 0]
        suitable = sorted((item for item in candidates if item[1] <= 720), key=lambda item: item[1], reverse=True)
        if suitable:
            return suitable[0][0]
        if candidates:
            return sorted(candidates, key=lambda item: item[1])[0][0]
        return 0

    def _load_item(self, index: int, autoplay: bool = True, position_ns: int = 0):
        self.index = max(0, min(index, len(self.playlist) - 1))
        item = self._current_item()
        sources = self._sources()
        if not sources:
            self._set_status("Keine Medienquelle verfügbar.")
            return
        self.source_index = self._preferred_source_index(sources)
        self._populate_quality_dropdown(sources)
        self.title_label.set_text(str(item.get("title") or "LiMaD Study Player"))
        self.window.set_title(str(item.get("title") or "LiMaD Study Player"))
        is_video = str(item.get("type") or "video") == "video"
        self.picture.set_visible(is_video)
        self.audio_placeholder.set_visible(not is_video)
        self.user_paused = not autoplay
        self._create_pipeline(is_video)
        self._set_source(self.source_index, autoplay=autoplay, position_ns=position_ns)
        self._show_controls(True)

    def _populate_quality_dropdown(self, sources: list[dict[str, Any]]):
        labels = [str(source.get("quality") or "Standard") for source in sources]
        model = self.Gtk.StringList.new(labels)
        self.setting_quality = True
        self.quality_dropdown.set_model(model)
        self.quality_dropdown.set_selected(self.source_index)
        self.quality_dropdown.set_sensitive(len(labels) > 1)
        self.setting_quality = False

    def _create_pipeline(self, is_video: bool):
        self._stop_pipeline()
        Gst = self.Gst
        self.pipeline = Gst.ElementFactory.make("playbin") or Gst.ElementFactory.make("playbin3")
        if self.pipeline is None:
            raise NativePlayerUnavailable("GStreamer playbin konnte nicht erstellt werden.")
        if is_video:
            self.video_sink = Gst.ElementFactory.make("gtk4paintablesink")
            if self.video_sink is None:
                raise NativePlayerUnavailable("gtk4paintablesink konnte nicht erstellt werden.")
            self.pipeline.set_property("video-sink", self.video_sink)
            paintable = self.video_sink.get_property("paintable")
            self.picture.set_paintable(paintable)
        else:
            fake_sink = Gst.ElementFactory.make("fakesink")
            if fake_sink is not None:
                self.pipeline.set_property("video-sink", fake_sink)
        try:
            self.pipeline.connect("deep-element-added", self._deep_element_added)
        except Exception:
            pass
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._bus_message)
        self.decoder_name = "wird ermittelt"
        self.decoder_hardware = None
        self.qos_processed = 0
        self.qos_dropped = 0
        self.subtitle_tracks = [(-1, "Aus")]
        self.subtitle_stream_signature = ()
        if self.subtitle_dropdown is not None:
            self.subtitle_dropdown.set_model(self.Gtk.StringList.new(["Aus"]))
            self.subtitle_dropdown.set_selected(0)
            self.subtitle_dropdown.set_sensitive(False)
        if not self.tick_id:
            self.tick_id = self.GLib.timeout_add(250, self._tick)

    def _stop_pipeline(self):
        if self.pipeline is not None and self.Gst is not None:
            try:
                self.pipeline.set_state(self.Gst.State.NULL)
            except Exception:
                pass
        self.pipeline = None
        self.video_sink = None

    def _absolute_url(self, value: str) -> str:
        value = str(value or "").strip()
        if value.startswith("file://") or value.startswith("http://") or value.startswith("https://"):
            return value
        if value.startswith("/"):
            return urllib.parse.urljoin(self.base_url, value.lstrip("/"))
        path = Path(value).expanduser()
        if path.is_file():
            return path.resolve().as_uri()
        return urllib.parse.urljoin(self.base_url, value)

    def _set_source(self, index: int, autoplay: bool, position_ns: int = 0):
        sources = self._sources()
        if not sources or self.pipeline is None:
            return
        self.source_index = max(0, min(index, len(sources) - 1))
        source = sources[self.source_index]
        uri = self._absolute_url(str(source.get("url") or ""))
        self.pipeline.set_state(self.Gst.State.READY)
        self.pipeline.set_property("uri", uri)
        self._apply_decoder_preference()
        self._apply_subtitle_selection(-1)
        self.pipeline.set_state(self.Gst.State.PAUSED)
        self._set_status(f"Lädt: {source.get('quality') or 'Standard'} …")

        def start_when_ready():
            if self.pipeline is None:
                return False
            if position_ns > 0:
                self.pipeline.seek_simple(self.Gst.Format.TIME, self.Gst.SeekFlags.FLUSH | self.Gst.SeekFlags.KEY_UNIT, position_ns)
            if autoplay and not self.user_paused:
                self.pipeline.set_state(self.Gst.State.PLAYING)
            return False

        self.GLib.timeout_add(120, start_when_ready)

    def _subtitle_label(self, index: int) -> str:
        label = f"Untertitel {index + 1}"
        if self.pipeline is None:
            return label
        try:
            tags = self.pipeline.emit("get-text-tags", index)
        except Exception:
            tags = None
        if tags is None:
            return label
        values = []
        for tag_name in (self.Gst.TAG_TITLE, self.Gst.TAG_LANGUAGE_NAME, self.Gst.TAG_LANGUAGE_CODE):
            try:
                ok, value = tags.get_string(tag_name)
            except Exception:
                ok, value = False, None
            value = str(value or "").strip()
            if ok and value and value not in values:
                values.append(value)
        return " · ".join(values) if values else label

    def _refresh_subtitle_tracks(self):
        if self.pipeline is None or self.subtitle_dropdown is None:
            return False
        prop = self.pipeline.find_property("n-text")
        if prop is None:
            self.subtitle_dropdown.set_sensitive(False)
            return False
        try:
            count = max(0, int(self.pipeline.get_property("n-text") or 0))
        except Exception:
            count = 0
        labels = tuple(["Aus"] + [self._subtitle_label(index) for index in range(count)])
        if labels == self.subtitle_stream_signature:
            return False
        previous_stream = -1
        selected = int(self.subtitle_dropdown.get_selected())
        if 0 <= selected < len(self.subtitle_tracks):
            previous_stream = self.subtitle_tracks[selected][0]
        self.subtitle_tracks = [(-1, "Aus")] + [(index, labels[index + 1]) for index in range(count)]
        self.subtitle_stream_signature = labels
        self.subtitle_dropdown.set_model(self.Gtk.StringList.new(list(labels)))
        target = next((position for position, item in enumerate(self.subtitle_tracks) if item[0] == previous_stream), 0)
        self.subtitle_dropdown.set_selected(target)
        self.subtitle_dropdown.set_sensitive(count > 0)
        self._apply_subtitle_selection(self.subtitle_tracks[target][0])
        return False

    def _apply_subtitle_selection(self, stream_index: int):
        if self.pipeline is None:
            return
        stream_index = int(stream_index)
        try:
            flags = self.pipeline.get_property("flags")
            value = int(flags)
            text_flag = 1 << 2
            value = value | text_flag if stream_index >= 0 else value & ~text_flag
            self.pipeline.set_property("flags", value)
        except Exception:
            pass
        if self.pipeline.find_property("current-text") is not None:
            try:
                self.pipeline.set_property("current-text", stream_index)
            except Exception as exc:
                self.log(f"Untertitelspur konnte nicht gesetzt werden: {exc}")

    def _subtitle_changed(self, dropdown, _param):
        selected = int(dropdown.get_selected())
        if not 0 <= selected < len(self.subtitle_tracks):
            selected = 0
        stream_index, label = self.subtitle_tracks[selected]
        self._apply_subtitle_selection(stream_index)
        self._set_status(f"Untertitel: {label}")

    def _apply_decoder_preference(self):
        if self.pipeline is None:
            return
        prefer_software = bool(self.decoder_dropdown and self.decoder_dropdown.get_selected() == 1)
        applied = False
        for element in (self.pipeline,):
            prop = element.find_property("force-sw-decoders")
            if prop is not None:
                try:
                    element.set_property("force-sw-decoders", prefer_software)
                    applied = True
                except Exception:
                    pass
        if prefer_software and not applied:
            self._set_status("Softwaredecoder wird bevorzugt, soweit die installierte GStreamer-Version dies unterstützt.")

    def _deep_element_added(self, _bin, _sub_bin, element):
        try:
            prop = element.find_property("force-sw-decoders")
            if prop is not None:
                element.set_property("force-sw-decoders", bool(self.decoder_dropdown and self.decoder_dropdown.get_selected() == 1))
        except Exception:
            pass
        try:
            factory = element.get_factory()
            if factory is None:
                return
            klass = str(factory.get_klass() or "")
            if "Decoder/Video" not in klass and "Video/Decoder" not in klass:
                return
            name = str(factory.get_name() or element.get_name() or "Decoder")
            hardware_tokens = ("vaapi", "vah", "vav1", "nv", "v4l2", "qsv", "d3d11", "vtdec", "amf", "omx")
            self.decoder_name = name
            self.decoder_hardware = any(token in name.lower() for token in hardware_tokens) or "Hardware" in klass
            self.GLib.idle_add(self._update_diagnostics)
        except Exception:
            pass

    def _bus_message(self, _bus, message):
        Gst = self.Gst
        message_type = message.type
        if message_type == Gst.MessageType.ERROR:
            error, debug = message.parse_error()
            self._set_status(f"Wiedergabefehler: {error.message}")
            self.log(f"Native-Player-GStreamer-Fehler: {error.message}; {debug or ''}")
        elif message_type == Gst.MessageType.EOS:
            if bool(self.payload.get("autoplay", True)) and self.index < len(self.playlist) - 1:
                self._load_item(self.index + 1, autoplay=True)
            else:
                self._set_status("Wiedergabe beendet.")
                self.play_button.set_label("▶")
        elif message_type == Gst.MessageType.BUFFERING:
            percent = message.parse_buffering()
            self._set_status(f"Puffert: {percent} %")
        elif message_type == Gst.MessageType.STATE_CHANGED and message.src == self.pipeline:
            _old, new, _pending = message.parse_state_changed()
            if new == Gst.State.PLAYING:
                self.play_button.set_label("Ⅱ")
                self._set_status("Wiedergabe läuft.")
                self._show_controls(True)
            elif new in {Gst.State.PAUSED, Gst.State.READY}:
                self.play_button.set_label("▶")
                self._show_controls(False)
                self._refresh_subtitle_tracks()
        elif message_type == Gst.MessageType.QOS:
            try:
                _format, processed, dropped = message.parse_qos_stats()
                self.qos_processed = max(self.qos_processed, int(processed))
                self.qos_dropped = max(self.qos_dropped, int(dropped))
                self._update_diagnostics()
            except Exception:
                pass

    def _tick(self):
        if self.pipeline is None or self.window is None:
            self.tick_id = 0
            return False
        try:
            ok_position, position = self.pipeline.query_position(self.Gst.Format.TIME)
            ok_duration, duration = self.pipeline.query_duration(self.Gst.Format.TIME)
            if ok_duration and duration > 0:
                self.duration_ns = duration
                self.duration_label.set_text(self._format_time(duration))
            if ok_position and position >= 0:
                self.current_label.set_text(self._format_time(position))
                if self.duration_ns > 0:
                    self.updating_scale = True
                    self.position_scale.set_value(min(1000, max(0, position / self.duration_ns * 1000)))
                    self.updating_scale = False
            self._update_diagnostics()
            self._refresh_subtitle_tracks()
        except Exception:
            pass
        return True

    def _format_time(self, nanoseconds: int) -> str:
        seconds = max(0, int(nanoseconds / self.Gst.SECOND))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    def _seek_requested(self, _scale, _scroll_type, value):
        if self.updating_scale or self.pipeline is None or self.duration_ns <= 0:
            return False
        target = int(max(0, min(1000, float(value))) / 1000 * self.duration_ns)
        self.pipeline.seek_simple(self.Gst.Format.TIME, self.Gst.SeekFlags.FLUSH | self.Gst.SeekFlags.KEY_UNIT, target)
        return False

    def _seek_relative(self, seconds: int):
        if self.pipeline is None:
            return
        ok, position = self.pipeline.query_position(self.Gst.Format.TIME)
        if not ok:
            return
        target = max(0, position + seconds * self.Gst.SECOND)
        if self.duration_ns > 0:
            target = min(target, self.duration_ns)
        self.pipeline.seek_simple(self.Gst.Format.TIME, self.Gst.SeekFlags.FLUSH | self.Gst.SeekFlags.KEY_UNIT, target)

    def _toggle_play(self):
        self._show_controls(True)
        if self.pipeline is None:
            return
        _result, state, _pending = self.pipeline.get_state(0)
        if state == self.Gst.State.PLAYING:
            self.user_paused = True
            self.pipeline.set_state(self.Gst.State.PAUSED)
        else:
            self.user_paused = False
            self.pipeline.set_state(self.Gst.State.PLAYING)

    def _previous(self):
        if self.index > 0:
            self._load_item(self.index - 1, autoplay=True)
        else:
            self._seek_relative(-10_000)

    def _next(self):
        if self.index < len(self.playlist) - 1:
            self._load_item(self.index + 1, autoplay=True)

    def _quality_changed(self, dropdown, _param):
        if self.setting_quality or self.pipeline is None:
            return
        index = int(dropdown.get_selected())
        if index == self.source_index:
            return
        ok, position = self.pipeline.query_position(self.Gst.Format.TIME)
        playing = False
        try:
            _result, state, _pending = self.pipeline.get_state(0)
            playing = state == self.Gst.State.PLAYING
        except Exception:
            pass
        self._set_source(index, autoplay=playing, position_ns=position if ok else 0)

    def _decoder_mode_changed(self, _dropdown, _param):
        if self.pipeline is None:
            return
        ok, position = self.pipeline.query_position(self.Gst.Format.TIME)
        _result, state, _pending = self.pipeline.get_state(0)
        self._create_pipeline(str(self._current_item().get("type") or "video") == "video")
        self._set_source(self.source_index, autoplay=state == self.Gst.State.PLAYING, position_ns=position if ok else 0)

    def _update_diagnostics(self):
        if self.decoder_label is None:
            return False
        if self.decoder_hardware is True:
            mode = "Hardware"
        elif self.decoder_hardware is False:
            mode = "Software"
        else:
            mode = "Automatisch"
        dropped = f" • Frames verworfen: {self.qos_dropped}" if self.qos_dropped else ""
        self.decoder_label.set_text(f"GStreamer • Decoder: {self.decoder_name} ({mode}){dropped}")
        return False

    def _set_status(self, text: str):
        if self.status_label is not None:
            self.status_label.set_text(str(text))

    def _api_json(self, path: str, method: str = "GET", payload: dict[str, Any] | None = None):
        url = urllib.parse.urljoin(self.base_url, path.lstrip("/"))
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))

    def _download(self):
        source = self._sources()[self.source_index]
        item = self._current_item()
        self.download_button.set_sensitive(False)
        self._set_status("Download läuft …")

        def worker():
            try:
                result = self._api_json("/api/media/download", "POST", {
                    "url": source.get("download_url") or source.get("url"),
                    "title": item.get("title") or "Medium",
                    "kind": item.get("type") or "video",
                    "quality": source.get("quality") or "",
                    "image": item.get("image") or "",
                    "natural_key": item.get("natural_key") or "",
                })
                self.GLib.idle_add(self._download_done, bool(result.get("ok", True)), "Medium wurde offline gespeichert.")
            except Exception as exc:
                self.GLib.idle_add(self._download_done, False, f"Download fehlgeschlagen: {exc}")

        threading.Thread(target=worker, daemon=True).start()

    def _download_done(self, ok: bool, message: str):
        if self.download_button is not None:
            self.download_button.set_sensitive(True)
        self._set_status(message)
        return False

    def _choose_playlist(self):
        self.playlist_button.set_sensitive(False)

        def worker():
            try:
                playlists = self._api_json("/api/playlists")
                self.GLib.idle_add(self._show_playlist_dialog, playlists)
            except Exception as exc:
                self.GLib.idle_add(self._playlist_error, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _playlist_error(self, error: str):
        self.playlist_button.set_sensitive(True)
        self._set_status(f"Playlists konnten nicht geladen werden: {error}")
        return False

    def _show_playlist_dialog(self, playlists):
        self.playlist_button.set_sensitive(True)
        if not isinstance(playlists, list):
            playlists = []
        if not playlists:
            self._create_default_playlist()
            return False
        dialog = self.Gtk.Window(title="Zu Playlist hinzufügen", transient_for=self.window, modal=True)
        dialog.set_default_size(420, 360)
        box = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)
        dialog.set_child(box)
        label = self.Gtk.Label(label="Playlist auswählen")
        label.set_xalign(0)
        box.append(label)
        scroller = self.Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        list_box = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=6)
        scroller.set_child(list_box)
        box.append(scroller)
        for playlist in playlists:
            button = self.Gtk.Button(label=str(playlist.get("title") or "Playlist"))
            button.connect("clicked", lambda _button, item=playlist: self._add_to_playlist(str(item.get("id") or ""), dialog))
            list_box.append(button)
        dialog.present()
        return False

    def _create_default_playlist(self):
        def worker():
            try:
                result = self._api_json("/api/playlists", "POST", {"title": "Meine Medien"})
                playlist = result.get("playlist") or {}
                self.GLib.idle_add(self._add_to_playlist, str(playlist.get("id") or ""), None)
            except Exception as exc:
                self.GLib.idle_add(self._playlist_error, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _add_to_playlist(self, playlist_id: str, dialog=None):
        if dialog is not None:
            dialog.close()
        if not playlist_id:
            self._set_status("Playlist konnte nicht bestimmt werden.")
            return False
        source = self._sources()[self.source_index]
        item = self._current_item()

        def worker():
            try:
                self._api_json(f"/api/playlists/{playlist_id}/items", "POST", {
                    "label": item.get("title") or "Medium",
                    "media_url": source.get("url") or "",
                    "mime_type": source.get("mime_type") or "",
                    "thumbnail_path": item.get("image") or "",
                    "source": {
                        "kind": item.get("type") or "video",
                        "quality": source.get("quality") or "",
                        "natural_key": item.get("natural_key") or "",
                        "sources": self._sources(),
                    },
                })
                self.GLib.idle_add(self._set_status, "Zur Playlist hinzugefügt.")
            except Exception as exc:
                self.GLib.idle_add(self._set_status, f"Playlist konnte nicht aktualisiert werden: {exc}")

        threading.Thread(target=worker, daemon=True).start()
        return False

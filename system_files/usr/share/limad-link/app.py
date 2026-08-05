from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk

from common import APP_ID, APP_NAME, VERSION, api_request, ensure_service

CSS = b"""
window { background: #090713; color: #f7f3ff; }
headerbar { background: #111020; color: #f7f3ff; border-bottom: 1px solid rgba(181,130,255,.22); }
.card { background: rgba(255,255,255,.045); border: 1px solid rgba(255,255,255,.09); border-radius: 16px; padding: 16px; }
.device-title { font-size: 18px; font-weight: 700; }
.dim { color: rgba(247,243,255,.62); }
.online { color: #66d17a; font-weight: 700; }
.offline { color: #a8a3b4; }
.accent { background: #a855b8; color: white; border-radius: 10px; }
button { border-radius: 10px; }
"""


class LiLinkApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.window = None
        self.runtime = None
        self.devices_box = None
        self.status = None
        self.refresh_button = None
        self.device_map = {}

    def do_activate(self):
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        if self.window:
            self.window.present()
            return
        self.window = Gtk.ApplicationWindow(application=self, title=APP_NAME)
        self.window.set_default_size(980, 720)
        self.window.set_size_request(760, 520)
        header = Gtk.HeaderBar()
        title = Gtk.Label(label="LiLink")
        title.add_css_class("title-2")
        header.set_title_widget(title)
        pair_code = Gtk.Button(label="Kopplungscode")
        pair_code.connect("clicked", self.on_pair_code)
        header.pack_start(pair_code)
        self.refresh_button = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        self.refresh_button.set_tooltip_text("Geräte neu suchen")
        self.refresh_button.connect("clicked", lambda *_: self.refresh())
        header.pack_end(self.refresh_button)
        self.window.set_titlebar(header)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        root.set_margin_top(20)
        root.set_margin_bottom(20)
        root.set_margin_start(22)
        root.set_margin_end(22)
        intro = Gtk.Label(label="Verbinde deine LiMaD-Geräte und arbeite nahtlos weiter.")
        intro.set_xalign(0)
        intro.add_css_class("dim")
        root.append(intro)
        self.status = Gtk.Label(label="LiLink wird gestartet …")
        self.status.set_xalign(0)
        root.append(self.status)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        self.devices_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        scroll.set_child(self.devices_box)
        root.append(scroll)
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        deskflow = Gtk.Button(label="Maus und Tastatur teilen")
        deskflow.connect("clicked", self.on_deskflow)
        settings = Gtk.Button(label="Remote-Desktop-Einstellungen")
        settings.connect("clicked", self.on_remote_settings)
        footer.append(deskflow)
        footer.append(settings)
        root.append(footer)
        self.window.set_child(root)
        self.window.present()
        self.run_async(self.start_service, self.after_start)

    def start_service(self):
        return ensure_service()

    def after_start(self, result, error):
        if error:
            self.show_error("LiLink konnte nicht gestartet werden", str(error))
            self.status.set_text(str(error))
            return
        self.runtime = result
        self.refresh()

    def api(self, path, payload=None):
        if not self.runtime:
            self.runtime = ensure_service()
        return api_request(f"https://127.0.0.1:{int(self.runtime['port'])}{path}", payload, admin=self.runtime["adminToken"], timeout=120)

    def run_async(self, func, callback):
        def worker():
            try:
                result, error = func(), None
            except Exception as exc:
                result, error = None, exc
            GLib.idle_add(callback, result, error)
        threading.Thread(target=worker, daemon=True).start()

    def refresh(self):
        if self.refresh_button:
            self.refresh_button.set_sensitive(False)
        self.status.set_text("Suche LiMaD-Geräte im lokalen Netzwerk …")
        self.run_async(lambda: self.api("/api/admin/state"), self.render_state)

    def clear_box(self):
        child = self.devices_box.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.devices_box.remove(child)
            child = nxt

    def render_state(self, state, error):
        if self.refresh_button:
            self.refresh_button.set_sensitive(True)
        self.clear_box()
        if error:
            self.status.set_text(f"Gerätesuche fehlgeschlagen: {error}")
            return
        identity = state.get("identity", {})
        devices = state.get("devices", [])
        self.device_map = {item.get("deviceId"): item for item in devices if item.get("deviceId")}
        self.status.set_text(f"Dieses Gerät: {identity.get('name', 'LiMaD-Gerät')} · LiLink {VERSION}")
        if not devices:
            empty = Gtk.Label(label="Noch kein anderes LiMaD-Gerät gefunden.\nÖffne LiLink auf dem zweiten Gerät und aktualisiere die Suche.")
            empty.set_justify(Gtk.Justification.CENTER)
            empty.add_css_class("dim")
            empty.set_margin_top(80)
            self.devices_box.append(empty)
            return
        for device in devices:
            self.devices_box.append(self.device_card(device))

    def device_card(self, device):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.add_css_class("card")
        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        icon = Gtk.Image.new_from_icon_name("computer-symbolic")
        icon.set_pixel_size(28)
        top.append(icon)
        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        name = Gtk.Label(label=device.get("name") or "LiMaD-Gerät")
        name.set_xalign(0)
        name.add_css_class("device-title")
        labels.append(name)
        online = bool(device.get("online"))
        paired = bool(device.get("paired"))
        status = Gtk.Label(label=("Online" if online else "Offline") + (" · gekoppelt" if paired else " · noch nicht gekoppelt"))
        status.set_xalign(0)
        status.add_css_class("online" if online else "offline")
        labels.append(status)
        top.append(labels)
        card.append(top)
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        if not paired:
            button = Gtk.Button(label="Koppeln")
            button.add_css_class("accent")
            button.connect("clicked", self.on_pair, device)
            actions.append(button)
        else:
            screen = Gtk.Button(label="Bildschirm übernehmen")
            screen.add_css_class("accent")
            screen.set_sensitive(online)
            screen.connect("clicked", self.on_screen, device)
            actions.append(screen)
            send = Gtk.Button(label="Datei senden")
            send.set_sensitive(online)
            send.connect("clicked", self.on_send_file, device)
            actions.append(send)
            handoff = Gtk.Button(label="Hier fortsetzen")
            handoff.set_sensitive(online)
            handoff.connect("clicked", self.on_handoff, device)
            actions.append(handoff)
            menu = Gtk.MenuButton(icon_name="view-more-symbolic")
            model = Gio.Menu()
            model.append("Berechtigungen", f"app.permissions::{device['deviceId']}")
            model.append("Kopplung aufheben", f"app.unpair::{device['deviceId']}")
            menu.set_menu_model(model)
            actions.append(menu)
        card.append(actions)
        return card

    def do_startup(self):
        Gtk.Application.do_startup(self)
        action = Gio.SimpleAction.new("unpair", GLib.VariantType.new("s"))
        action.connect("activate", self.on_unpair)
        self.add_action(action)
        permissions = Gio.SimpleAction.new("permissions", GLib.VariantType.new("s"))
        permissions.connect("activate", self.on_permissions)
        self.add_action(permissions)

    def on_pair_code(self, *_):
        self.run_async(lambda: self.api("/api/admin/pair-code", {}), self.show_pair_code)

    def show_pair_code(self, result, error):
        if error:
            return self.show_error("Kopplungscode konnte nicht erzeugt werden", str(error))
        code = result["code"]
        self.show_info("LiLink-Kopplung", f"Code auf dem anderen Gerät eingeben:\n\n{code[:3]} {code[3:]}\n\nGültig für fünf Minuten.")

    def on_pair(self, _button, device):
        dialog = Gtk.Dialog(transient_for=self.window, modal=True, title=f"{device.get('name','Gerät')} koppeln")
        dialog.add_button("Abbrechen", Gtk.ResponseType.CANCEL)
        dialog.add_button("Koppeln", Gtk.ResponseType.OK)
        box = dialog.get_content_area()
        box.set_spacing(12)
        box.set_margin_top(18); box.set_margin_bottom(18); box.set_margin_start(18); box.set_margin_end(18)
        label = Gtk.Label(label="Zeige auf dem Zielgerät zuerst den Kopplungscode an und gib ihn hier ein.")
        label.set_wrap(True); label.set_xalign(0)
        entry = Gtk.Entry(); entry.set_placeholder_text("000 000"); entry.set_max_length(7)
        box.append(label); box.append(entry)
        def response(_dialog, response_id):
            code = entry.get_text()
            dialog.destroy()
            if response_id != Gtk.ResponseType.OK:
                return
            payload = {"host": device.get("host"), "port": device.get("port"), "fingerprint": device.get("fingerprint"), "code": code}
            self.status.set_text("Geräte werden sicher gekoppelt …")
            self.run_async(lambda: self.api("/api/admin/pair", payload), self.after_pair)
        dialog.connect("response", response)
        dialog.present()

    def after_pair(self, result, error):
        if error:
            self.show_error("Kopplung fehlgeschlagen", str(error))
        else:
            self.show_info("LiLink", f"{result.get('name','Gerät')} wurde sicher gekoppelt.")
        self.refresh()

    def on_unpair(self, _action, parameter):
        device_id = parameter.get_string()
        self.run_async(lambda: self.api("/api/admin/unpair", {"deviceId": device_id}), lambda _r, e: self.refresh() if not e else self.show_error("Fehler", str(e)))

    def on_permissions(self, _action, parameter):
        device_id = parameter.get_string()
        device = self.device_map.get(device_id)
        if not device:
            return
        dialog = Gtk.Dialog(transient_for=self.window, modal=True, title=f"Berechtigungen für {device.get('name', 'Gerät')}")
        dialog.add_button("Abbrechen", Gtk.ResponseType.CANCEL)
        dialog.add_button("Speichern", Gtk.ResponseType.OK)
        box = dialog.get_content_area()
        box.set_spacing(10)
        box.set_margin_top(18); box.set_margin_bottom(18); box.set_margin_start(18); box.set_margin_end(18)
        labels = {
            "screen": "Bildschirm ansehen und steuern",
            "files": "Dateien an dieses Gerät senden",
            "clipboard": "Zwischenablage verwenden",
            "handoff": "Arbeitsstände übergeben",
        }
        current = device.get("permissions") or {}
        switches = {}
        for key, label in labels.items():
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            text = Gtk.Label(label=label)
            text.set_xalign(0)
            text.set_hexpand(True)
            toggle = Gtk.Switch(active=bool(current.get(key, True)))
            row.append(text)
            row.append(toggle)
            box.append(row)
            switches[key] = toggle
        def response(_dialog, response_id):
            values = {key: toggle.get_active() for key, toggle in switches.items()}
            dialog.destroy()
            if response_id != Gtk.ResponseType.OK:
                return
            self.run_async(lambda: self.api("/api/admin/permissions", {"deviceId": device_id, "permissions": values}), self.after_permissions)
        dialog.connect("response", response)
        dialog.present()

    def after_permissions(self, _result, error):
        if error:
            self.show_error("Berechtigungen konnten nicht gespeichert werden", str(error))
        self.refresh()

    def on_screen(self, _button, device):
        self.status.set_text(f"Bereite Bildschirmverbindung zu {device['name']} vor …")
        self.run_async(lambda: self.api("/api/admin/rdp-prepare", {"deviceId": device["deviceId"]}), self.launch_rdp)

    def launch_rdp(self, result, error):
        if error:
            self.show_error("Bildschirmübernahme konnte nicht gestartet werden", str(error))
            self.refresh()
            return
        binary = shutil.which("xfreerdp3") or shutil.which("xfreerdp")
        if not binary:
            self.show_error("RDP-Client fehlt", "FreeRDP ist nicht installiert.")
            return
        args = [f"/v:{result['host']}:{result['port']}", f"/u:{result['username']}", f"/p:{result['password']}", "/cert:tofu", "+clipboard", "/dynamic-resolution", "/network:auto"]
        process = subprocess.Popen([binary, "/args-from:stdin"], stdin=subprocess.PIPE, text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        process.stdin.write("\n".join(args) + "\n")
        process.stdin.close()
        device_id = result["deviceId"]
        def waiter():
            process.wait()
            try:
                self.api("/api/admin/rdp-release", {"deviceId": device_id})
            except Exception:
                pass
            GLib.idle_add(self.refresh)
        threading.Thread(target=waiter, daemon=True).start()
        self.status.set_text(f"Bildschirmverbindung zu {result['name']} läuft.")

    def on_send_file(self, _button, device):
        chooser = Gtk.FileChooserNative(title=f"Datei an {device['name']} senden", transient_for=self.window, action=Gtk.FileChooserAction.OPEN, accept_label="Senden", cancel_label="Abbrechen")
        chooser.set_select_multiple(True)
        def response(dialog, response_id):
            if response_id == Gtk.ResponseType.ACCEPT:
                model = dialog.get_files()
                paths = []
                for index in range(model.get_n_items()):
                    path = model.get_item(index).get_path()
                    if path:
                        paths.append(path)
                if paths:
                    self.status.set_text(f"Übertrage {len(paths)} Datei(en) an {device['name']} …")
                    self.run_async(lambda: self.api("/api/admin/send-files", {"deviceId": device["deviceId"], "paths": paths}), self.after_send)
            dialog.destroy()
        chooser.connect("response", response)
        chooser.show()

    def after_send(self, result, error):
        if error:
            self.show_error("Dateiübertragung fehlgeschlagen", str(error))
        else:
            self.show_info("LiLink", f"{len(result.get('results', []))} Datei(en) wurden übertragen und per SHA-256 geprüft.")
        self.refresh()

    def on_handoff(self, _button, device):
        dialog = Gtk.Dialog(transient_for=self.window, modal=True, title=f"Auf {device['name']} fortsetzen")
        dialog.add_button("Abbrechen", Gtk.ResponseType.CANCEL)
        dialog.add_button("Übergeben", Gtk.ResponseType.OK)
        box = dialog.get_content_area(); box.set_spacing(12)
        box.set_margin_top(18); box.set_margin_bottom(18); box.set_margin_start(18); box.set_margin_end(18)
        app = Gtk.DropDown.new_from_strings(["LiMaD Study", "LiNotes", "LiMaD Cut", "LibreOffice", "Zen Browser", "Audio/Video", "URL oder Datei"])
        entry = Gtk.Entry(); entry.set_placeholder_text("URL oder Dateipfad (optional)")
        note = Gtk.Label(label="LiMaD-eigene Apps können schrittweise um exakte Zustandsadapter erweitert werden. Diese Preview startet bereits App, URL oder Datei auf dem Zielgerät.")
        note.set_wrap(True); note.set_xalign(0); note.add_css_class("dim")
        box.append(app); box.append(entry); box.append(note)
        ids = ["limad-study", "limad-notes", "limad-cut", "libreoffice", "zen-browser", "media", "generic"]
        def response(_dialog, response_id):
            selected = ids[app.get_selected()]
            value = entry.get_text().strip()
            dialog.destroy()
            if response_id != Gtk.ResponseType.OK:
                return
            handoff = {"schema": 1, "application": selected, "uri": value, "files": [], "state": {}}
            self.status.set_text(f"Übergebe Arbeitsstand an {device['name']} …")
            self.run_async(lambda: self.api("/api/admin/handoff", {"deviceId": device["deviceId"], "handoff": handoff}), self.after_handoff)
        dialog.connect("response", response)
        dialog.present()

    def after_handoff(self, _result, error):
        if error:
            self.show_error("Handoff fehlgeschlagen", str(error))
        else:
            self.show_info("LiLink", "Der Arbeitsstand wurde an das Zielgerät übergeben.")
        self.refresh()

    def on_deskflow(self, *_):
        binary = shutil.which("deskflow") or shutil.which("deskflow-core")
        if not binary:
            return self.show_error("Deskflow fehlt", "Deskflow ist nicht installiert.")
        subprocess.Popen([binary], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def on_remote_settings(self, *_):
        subprocess.Popen(["gnome-control-center", "system", "remote-desktop"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def show_info(self, title, message):
        dialog = Gtk.AlertDialog(message=title, detail=message)
        dialog.show(self.window)

    def show_error(self, title, message):
        dialog = Gtk.AlertDialog(message=title, detail=message)
        dialog.show(self.window)


if __name__ == "__main__":
    raise SystemExit(LiLinkApp().run(sys.argv))

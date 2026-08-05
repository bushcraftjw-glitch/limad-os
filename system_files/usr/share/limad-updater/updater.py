#!/usr/bin/env python3
import argparse
import threading
from pathlib import Path
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk

from backend import inspect_package, install_package, launch_app, load_config, restore_system, scan_updates, status


class UpdateWindow(Gtk.ApplicationWindow):
    def __init__(self, app, requested_app=None, package=None):
        super().__init__(application=app, title="LiMaD Updates")
        self.set_default_size(850, 700)
        self.requested_app = requested_app
        self.pending_package = package
        self.rows = {}
        self.candidates = {}
        self.busy = False

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        root.set_margin_top(24)
        root.set_margin_bottom(24)
        root.set_margin_start(28)
        root.set_margin_end(28)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        title = Gtk.Label(label="LiMaD Updates", xalign=0)
        title.add_css_class("title-1")
        subtitle = Gtk.Label(
            label="Sucht automatisch in Downloads und auf dem Schreibtisch nach passenden Update-ZIPs. Installation und Rückkehr zur Systemversion funktionieren ohne Terminal.",
            xalign=0,
        )
        subtitle.set_wrap(True)
        subtitle.add_css_class("dim-label")
        title_box.append(title)
        title_box.append(subtitle)
        title_box.set_hexpand(True)

        scan_button = Gtk.Button(label="Nach Updates suchen")
        scan_button.add_css_class("suggested-action")
        scan_button.connect("clicked", self.scan_clicked)
        self.scan_button = scan_button

        open_button = Gtk.Button(label="Update-ZIP öffnen")
        open_button.connect("clicked", self.choose_package, None)
        self.open_button = open_button

        header.append(title_box)
        header.append(scan_button)
        header.append(open_button)
        root.append(header)

        self.progress = Gtk.ProgressBar()
        self.progress.set_visible(False)
        root.append(self.progress)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        for app_id, config in load_config().items():
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            card.add_css_class("card")
            card.set_margin_top(2)
            card.set_margin_bottom(2)
            card.set_margin_start(2)
            card.set_margin_end(2)

            info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            name = Gtk.Label(label=config["name"], xalign=0)
            name.add_css_class("title-4")
            version = Gtk.Label(xalign=0)
            version.add_css_class("dim-label")
            candidate = Gtk.Label(xalign=0)
            candidate.set_wrap(True)
            candidate.add_css_class("accent")
            info.append(name)
            info.append(version)
            info.append(candidate)

            actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            detected = Gtk.Button(label="Gefundenes Update installieren")
            detected.add_css_class("suggested-action")
            detected.connect("clicked", self.install_detected, app_id)
            choose = Gtk.Button(label="ZIP auswählen")
            choose.connect("clicked", self.choose_package, app_id)
            launch = Gtk.Button(label="App starten")
            launch.connect("clicked", self.launch_clicked, app_id)
            restore = Gtk.Button(label="Systemversion")
            restore.connect("clicked", self.restore_clicked, app_id)
            actions.append(detected)
            actions.append(choose)
            actions.append(launch)
            actions.append(restore)

            card.append(info)
            card.append(actions)
            list_box.append(card)
            self.rows[app_id] = {
                "version": version,
                "candidate": candidate,
                "detected": detected,
                "choose": choose,
                "launch": launch,
                "restore": restore,
            }

        scroller.set_child(list_box)
        scroller.set_vexpand(True)
        root.append(scroller)

        self.message = Gtk.Label(xalign=0)
        self.message.set_wrap(True)
        root.append(self.message)
        self.set_child(root)
        self.refresh()
        GLib.idle_add(self.start_scan)
        if self.pending_package:
            GLib.idle_add(self.start_install, self.pending_package, self.requested_app)

    def refresh(self):
        for app_id, row in self.rows.items():
            current = status(app_id)
            row["version"].set_text(
                f"Aktiv: {current['active_version']} · {current['source']} · System: {current['system_version']}"
            )
            candidate = self.candidates.get(app_id)
            if candidate:
                row["candidate"].set_text(
                    f"Neues Update gefunden: {candidate['version']} · {Path(candidate['path']).name}"
                )
            else:
                row["candidate"].set_text("Kein neueres Update-ZIP gefunden.")
            allowed = not self.requested_app or app_id == self.requested_app
            row["detected"].set_sensitive(bool(candidate) and allowed and not self.busy)
            row["choose"].set_sensitive(allowed and not self.busy)
            row["launch"].set_sensitive(bool(current.get("launcher")) and not self.busy)
            row["restore"].set_sensitive(current["can_restore"] and allowed and not self.busy)
        self.scan_button.set_sensitive(not self.busy)
        self.open_button.set_sensitive(not self.busy)

    def set_busy(self, busy, text=""):
        self.busy = busy
        self.progress.set_visible(busy)
        if busy:
            self.progress.pulse()
            self._pulse = GLib.timeout_add(120, self.pulse)
        elif hasattr(self, "_pulse"):
            GLib.source_remove(self._pulse)
            del self._pulse
        self.message.set_text(text)
        self.refresh()

    def pulse(self):
        self.progress.pulse()
        return True

    def dialog(self, title, text, error=False):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            buttons=Gtk.ButtonsType.OK,
            text=title,
        )
        dialog.set_property("secondary-text", text)
        dialog.set_message_type(Gtk.MessageType.ERROR if error else Gtk.MessageType.INFO)
        dialog.connect("response", lambda window, _response: window.destroy())
        dialog.present()

    def scan_clicked(self, _button):
        self.start_scan()

    def start_scan(self):
        if self.busy:
            return False
        self.set_busy(True, "Downloads und Schreibtisch werden nach LiMaD-Update-ZIPs durchsucht …")
        threading.Thread(target=self.scan_worker, daemon=True).start()
        return False

    def scan_worker(self):
        try:
            candidates = scan_updates()
            GLib.idle_add(self.scan_done, candidates, None)
        except Exception as exc:
            GLib.idle_add(self.scan_done, None, str(exc))

    def scan_done(self, candidates, error):
        if error:
            self.set_busy(False, "Suche fehlgeschlagen.")
            self.dialog("Updatesuche fehlgeschlagen", error, True)
            return False
        self.candidates = {app_id: item for app_id, item in candidates.items() if item}
        count = len(self.candidates)
        text = "Keine neueren Update-ZIPs gefunden." if count == 0 else f"{count} neueres Update-ZIP gefunden."
        self.set_busy(False, text)
        return False

    def choose_package(self, _button, expected_app):
        chooser = Gtk.FileChooserNative(
            title="LiMaD Update-ZIP auswählen",
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        update_filter = Gtk.FileFilter()
        update_filter.set_name("LiMaD Update-ZIP")
        update_filter.add_pattern("*.limad-update.zip")
        chooser.add_filter(update_filter)
        chooser.connect("response", self.file_response, expected_app)
        chooser.show()

    def file_response(self, chooser, response, expected_app):
        if response == Gtk.ResponseType.ACCEPT:
            selected = chooser.get_file()
            if selected and selected.get_path():
                self.start_install(selected.get_path(), expected_app)
        chooser.destroy()

    def install_detected(self, _button, app_id):
        candidate = self.candidates.get(app_id)
        if candidate:
            self.start_install(candidate["path"], app_id)

    def start_install(self, package, expected_app):
        try:
            manifest = inspect_package(package)
            name = load_config().get(manifest.get("app_id"), {}).get("name", manifest.get("app_id", "App"))
            version = manifest.get("version", "?")
        except Exception as exc:
            self.dialog("Update-Paket ungültig", str(exc), True)
            return False
        self.set_busy(True, f"{name} {version} wird vollständig geprüft und installiert …")
        threading.Thread(target=self.install_worker, args=(package, expected_app), daemon=True).start()
        return False

    def install_worker(self, package, expected_app):
        try:
            result = install_package(package, expected_app)
            GLib.idle_add(self.install_done, result, None)
        except Exception as exc:
            GLib.idle_add(self.install_done, None, str(exc))

    def install_done(self, result, error):
        if error:
            self.set_busy(False, "Update fehlgeschlagen. Details wurden protokolliert.")
            self.dialog("Update fehlgeschlagen", error, True)
            return False
        self.candidates.pop(result["app_id"], None)
        self.set_busy(False, f"{result['name']} {result['active_version']} wurde installiert.")
        self.dialog(
            "Update installiert",
            f"{result['name']} wurde von {result['previous_version']} auf {result['active_version']} aktualisiert. Die App kann jetzt über „App starten“ geöffnet werden.",
        )
        return False

    def launch_clicked(self, _button, app_id):
        try:
            launch_app(app_id)
            self.message.set_text(f"{load_config()[app_id]['name']} wurde gestartet.")
        except Exception as exc:
            self.dialog("App konnte nicht gestartet werden", str(exc), True)

    def restore_clicked(self, _button, app_id):
        try:
            result = restore_system(app_id)
            self.candidates.pop(app_id, None)
            self.refresh()
            self.dialog(
                "Systemversion aktiviert",
                f"{result['name']} verwendet wieder die in LiMaD OS enthaltene Version {result['system_version']}.",
            )
        except Exception as exc:
            self.dialog("Zurücksetzen fehlgeschlagen", str(exc), True)


class UpdateApp(Gtk.Application):
    def __init__(self, requested_app=None, package=None):
        super().__init__(application_id="de.limad.Updater", flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.requested_app = requested_app
        self.package = package

    def do_activate(self):
        UpdateWindow(self, self.requested_app, self.package).present()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("package", nargs="?")
    parser.add_argument("--app")
    args = parser.parse_args()
    package = str(Path(args.package).expanduser()) if args.package else None
    return UpdateApp(args.app, package).run([])


if __name__ == "__main__":
    raise SystemExit(main())

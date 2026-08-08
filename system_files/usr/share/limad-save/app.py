#!/usr/bin/env python3
from __future__ import annotations
import os
import threading
from pathlib import Path
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from core import DEFAULT_CATEGORIES, LiSaveError, VERSION, analyze, backup, configure_automatic, load_config, restore, verify


class LiSaveApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="de.limad.Save")
        self.window = None
        self.target = None
        self.password = None
        self.confirm = None
        self.status = None
        self.progress = None
        self.buttons = []
        self.switches = {}
        self.automatic = None
        self.before_update = None

    def do_activate(self):
        if self.window:
            self.window.present()
            return
        self.window = Gtk.ApplicationWindow(application=self, title="LiSave")
        self.window.set_default_size(760, 720)
        header = Gtk.HeaderBar()
        title = Gtk.Label(label="LiSave")
        title.add_css_class("title")
        header.set_title_widget(title)
        self.window.set_titlebar(header)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        root.set_margin_top(20)
        root.set_margin_bottom(20)
        root.set_margin_start(24)
        root.set_margin_end(24)

        intro = Gtk.Label(label="Persönlichen LiMaD-Stand sichern und nach einer sauberen Installation wiederherstellen.")
        intro.set_wrap(True)
        intro.set_xalign(0)
        intro.add_css_class("dim-label")
        root.append(intro)

        destination = Gtk.Frame(label="Backup-Ziel")
        destination_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        destination_box.set_margin_top(12)
        destination_box.set_margin_bottom(12)
        destination_box.set_margin_start(12)
        destination_box.set_margin_end(12)
        target_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.target = Gtk.Entry()
        self.target.set_hexpand(True)
        self.target.set_placeholder_text("USB-Laufwerk oder zweites Laufwerk auswählen")
        browse = Gtk.Button(label="Auswählen")
        browse.connect("clicked", self.choose_target)
        target_row.append(self.target)
        target_row.append(browse)
        destination_box.append(target_row)
        password_grid = Gtk.Grid(column_spacing=8, row_spacing=8)
        password_grid.attach(Gtk.Label(label="Backup-Passwort", xalign=0), 0, 0, 1, 1)
        self.password = Gtk.PasswordEntry(show_peek_icon=True)
        self.password.set_hexpand(True)
        password_grid.attach(self.password, 1, 0, 1, 1)
        password_grid.attach(Gtk.Label(label="Wiederholen", xalign=0), 0, 1, 1, 1)
        self.confirm = Gtk.PasswordEntry(show_peek_icon=True)
        self.confirm.set_hexpand(True)
        password_grid.attach(self.confirm, 1, 1, 1, 1)
        destination_box.append(password_grid)
        destination.set_child(destination_box)
        root.append(destination)

        data_frame = Gtk.Frame(label="Gesicherter LiMaD-Stand")
        data_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        data_box.set_margin_top(12)
        data_box.set_margin_bottom(12)
        data_box.set_margin_start(12)
        data_box.set_margin_end(12)
        rows = [
            ("documents", "Dokumente, Desktop, Downloads/LiDrop und LiLink Sync"),
            ("zen", "Zen Browser: Passwörter, Lesezeichen, Verlauf, Tabs und Arbeitsbereiche"),
            ("mail", "LiMaD Mail: Konten, Adressbücher, lokale Nachrichten und Einstellungen"),
            ("study", "LiMaD Study: Datenbank, Einstellungen und eigener JWL-Library-Export"),
            ("notes", "LiNotes: Notizen, Ordner, Anhänge, Papierkorb und Einstellungen"),
            ("windows", "Windows-Programme: Installationsliste, Einstellungen und Benutzerdaten"),
            ("windows_full", "Windows-Programme vollständig inklusive großer Wine-Prefixe"),
            ("settings", "GNOME-, LiMaD-, Dock- und Dateimanager-Einstellungen"),
            ("appsettings", "LibreOffice, LiMaD Klang, Vorlagen und weitere App-Einstellungen"),
        ]
        for key, label in rows:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            text = Gtk.Label(label=label, xalign=0)
            text.set_wrap(True)
            text.set_hexpand(True)
            switch = Gtk.Switch(active=DEFAULT_CATEGORIES[key])
            self.switches[key] = switch
            row.append(text)
            row.append(switch)
            data_box.append(row)
        scan = Gtk.Button(label="Benötigte Backup-Größe analysieren")
        scan.connect("clicked", self.on_analyze)
        data_box.append(scan)
        data_frame.set_child(data_box)
        root.append(data_frame)

        schedule_frame = Gtk.Frame(label="Automatische Sicherung")
        schedule_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        schedule_box.set_margin_top(12)
        schedule_box.set_margin_bottom(12)
        schedule_box.set_margin_start(12)
        schedule_box.set_margin_end(12)
        automatic_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        automatic_label = Gtk.Label(label="Täglich um 20:00 Uhr sichern, wenn das Laufwerk verbunden ist", xalign=0)
        automatic_label.set_wrap(True)
        automatic_label.set_hexpand(True)
        self.automatic = Gtk.Switch()
        automatic_row.append(automatic_label)
        automatic_row.append(self.automatic)
        schedule_box.append(automatic_row)
        update_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        update_label = Gtk.Label(label="Vor LiMaD-Systemupdates automatisch sichern", xalign=0)
        update_label.set_hexpand(True)
        self.before_update = Gtk.Switch(active=True)
        update_row.append(update_label)
        update_row.append(self.before_update)
        schedule_box.append(update_row)
        save_schedule = Gtk.Button(label="Automatik speichern")
        save_schedule.connect("clicked", self.on_configure)
        schedule_box.append(save_schedule)
        schedule_frame.set_child(schedule_box)
        root.append(schedule_frame)

        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        create = Gtk.Button(label="Backup jetzt erstellen")
        create.add_css_class("suggested-action")
        create.connect("clicked", self.on_backup)
        recover = Gtk.Button(label="Vorherigen Stand wiederherstellen")
        recover.connect("clicked", self.on_restore)
        check = Gtk.Button(label="Backup prüfen")
        check.connect("clicked", self.on_verify)
        for button in (create, recover, check, browse, scan, save_schedule):
            self.buttons.append(button)
        action_box.append(create)
        action_box.append(recover)
        action_box.append(check)
        root.append(action_box)

        self.progress = Gtk.ProgressBar()
        self.progress.set_visible(False)
        root.append(self.progress)
        self.status = Gtk.Label(label="Bereit")
        self.status.set_xalign(0)
        self.status.set_wrap(True)
        root.append(self.status)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(root)
        self.window.set_child(scroll)
        self.load_saved_config()
        self.window.present()

    def categories(self):
        return {key: switch.get_active() for key, switch in self.switches.items()}

    def load_saved_config(self):
        config = load_config()
        detected = os.environ.get("LISAVE_INITIAL_TARGET", "").strip()
        if detected:
            self.target.set_text(detected)
            self.status.set_text("LiSave-Backup wurde auf einem angeschlossenen Laufwerk erkannt.")
        elif config.get("bundle"):
            self.target.set_text(str(config["bundle"]))
        for key, value in config.get("categories", {}).items():
            if key in self.switches:
                self.switches[key].set_active(bool(value))
        self.automatic.set_active(bool(config.get("automatic")))
        self.before_update.set_active(bool(config.get("before_update", True)))

    def choose_target(self, *_):
        dialog = Gtk.FileChooserNative.new("Backup-Laufwerk auswählen", self.window, Gtk.FileChooserAction.SELECT_FOLDER, "Auswählen", "Abbrechen")
        dialog.connect("response", self.target_chosen)
        dialog.show()

    def target_chosen(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            file = dialog.get_file()
            if file and file.get_path():
                self.target.set_text(file.get_path())
        dialog.destroy()

    def credentials(self, require_confirm=True):
        target = self.target.get_text().strip()
        password = self.password.get_text()
        if not target:
            raise LiSaveError("Bitte ein Backup-Ziel auswählen.")
        if len(password) < 10:
            raise LiSaveError("Das Backup-Passwort muss mindestens zehn Zeichen lang sein.")
        if require_confirm and password != self.confirm.get_text():
            raise LiSaveError("Die beiden Passwörter stimmen nicht überein.")
        return Path(target), password

    def busy(self, active, text=""):
        for button in self.buttons:
            button.set_sensitive(not active)
        self.progress.set_visible(active)
        if active:
            self.progress.pulse()
        if text:
            self.status.set_text(text)

    def run_async(self, function, callback):
        self.busy(True, "LiSave arbeitet …")
        def progress(message):
            GLib.idle_add(self.update_progress, message)
        def worker():
            try:
                result, error = function(progress), None
            except Exception as exc:
                result, error = None, exc
            GLib.idle_add(callback, result, error)
        threading.Thread(target=worker, daemon=True).start()

    def update_progress(self, message):
        self.progress.pulse()
        self.status.set_text(message)
        return False

    def complete(self, result, error, title):
        self.busy(False)
        if error:
            self.status.set_text(str(error))
            self.message("LiSave-Fehler", str(error))
        else:
            self.status.set_text(title)
            self.message("LiSave", title)

    def message(self, title, body):
        dialog = Gtk.AlertDialog(message=title, detail=body)
        dialog.show(self.window)

    def on_analyze(self, *_):
        self.run_async(lambda _p: analyze(self.categories()), self.after_analyze)

    def after_analyze(self, result, error):
        self.busy(False)
        if error:
            return self.message("Analyse fehlgeschlagen", str(error))
        labels = {
            "documents": "Dokumente",
            "zen": "Zen Browser",
            "mail": "LiMaD Mail",
            "study": "LiMaD Study",
            "notes": "LiNotes",
            "windows": "Windows-Programme",
            "settings": "Systemeinstellungen",
            "appsettings": "App-Einstellungen",
        }
        lines = []
        for key, size in result.get("categories", {}).items():
            if size:
                lines.append(f"{labels.get(key, key)}: {self.format_size(size)}")
        lines.append(f"\nZu sichernde Quelldaten: {self.format_size(result.get('total', 0))}")
        lines.append("Backup-Ausschlüsse für Cache-, Download-, Katalog- und große Wine-Prefix-Daten sind bereits berücksichtigt.")
        lines.append("Die fertige Backupgröße kann durch Komprimierung und Deduplizierung deutlich kleiner sein.")
        lines.append("Programme und neu ladbare Systembestandteile werden als Wiederherstellungsplan erfasst.")
        self.status.set_text(lines[-4].strip())
        self.message("LiSave-Sicherungsanalyse", "\n".join(lines))

    def on_backup(self, *_):
        try:
            target, password = self.credentials(True)
        except Exception as exc:
            return self.message("Backup kann nicht starten", str(exc))
        self.run_async(lambda progress: backup(target, password, self.categories(), progress), self.after_backup)

    def after_backup(self, result, error):
        title = f"Backup erfolgreich erstellt\n{result.get('bundle', '')}" if result else ""
        self.complete(result, error, title)

    def on_restore(self, *_):
        try:
            target, password = self.credentials(False)
        except Exception as exc:
            return self.message("Wiederherstellung kann nicht starten", str(exc))
        self.confirm_restore(target, password)

    def confirm_restore(self, target, password):
        dialog = Gtk.AlertDialog(message="Vorherigen LiMaD-Stand wiederherstellen?", detail="Zen Browser, LiMaD Mail und LiMaD Study werden geschlossen. Vorhandene persönliche Daten können durch den Sicherungsstand ergänzt oder ersetzt werden.", buttons=["Abbrechen", "Wiederherstellen"], cancel_button=0, default_button=1)
        dialog.choose(self.window, None, self.restore_confirmed, (target, password))

    def restore_confirmed(self, dialog, result, values):
        try:
            choice = dialog.choose_finish(result)
        except Exception:
            return
        if choice != 1:
            return
        target, password = values
        self.run_async(lambda progress: restore(target, password, self.categories(), progress), self.after_restore)

    def after_restore(self, result, error):
        if error:
            return self.complete(result, error, "")
        pending = len(result.get("windowsProgramsPrepared", []))
        failures = len(result.get("flatpakFailures", []))
        text = "Wiederherstellung abgeschlossen. Bitte einmal abmelden oder neu starten."
        if pending:
            text += f"\n{pending} Windows-Programm(e) wurden für die erneute Einrichtung vorbereitet."
        if failures:
            text += f"\n{failures} Programm(e) konnten noch nicht aus dem Internet installiert werden."
        self.complete(result, None, text)

    def on_verify(self, *_):
        try:
            target, password = self.credentials(False)
        except Exception as exc:
            return self.message("Prüfung kann nicht starten", str(exc))
        self.run_async(lambda progress: (progress("Verschlüsseltes Backup wird geprüft …"), verify(target, password))[1], self.after_verify)

    def after_verify(self, result, error):
        self.complete(result, error, "Backup-Prüfung erfolgreich abgeschlossen.")

    def on_configure(self, *_):
        try:
            target, password = self.credentials(True)
        except Exception as exc:
            return self.message("Automatik kann nicht gespeichert werden", str(exc))
        enabled = self.automatic.get_active()
        before_update = self.before_update.get_active()
        self.run_async(lambda progress: (progress("Automatische Sicherung wird eingerichtet …"), configure_automatic(target, password, self.categories(), enabled, before_update))[1], self.after_configure)

    def after_configure(self, result, error):
        text = "Automatische Sicherung ist aktiv." if result and result.get("automatic") else "Automatische Sicherung ist deaktiviert."
        self.complete(result, error, text)

    @staticmethod
    def format_size(value):
        size = float(value)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024 or unit == "TB":
                return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
            size /= 1024


if __name__ == "__main__":
    raise SystemExit(LiSaveApp().run())

#!/usr/bin/env python3
from __future__ import annotations

import html
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

APP_ID = "de.limad.Notes"
VERSION = "1.0.0-preview2"
HOME = Path.home()

CSS = r"""
window{background:#f5f4f8;color:#17161c}.linotes-header{background:rgba(250,249,252,.96);border-bottom:1px solid #dad7df}.linotes-sidebar{background:#ecebf1;border-right:1px solid #d8d5dd}.linotes-list-pane{background:#f8f7fa;border-right:1px solid #ddd9e1}.linotes-editor{background:#fff}.linotes-title{font-size:24px;font-weight:800}.linotes-folder-heading{font-size:18px;font-weight:800;margin:14px 14px 7px}.linotes-folder-row{border-radius:10px;margin:2px 8px;padding:8px}.linotes-folder-row:selected{background:#e6b900;color:#15120a}.linotes-folder-row:selected label{color:#15120a}.linotes-note-row{border-bottom:1px solid #e3e0e7;padding:11px 12px}.linotes-note-row:selected{background:#fff0ad;color:#17161c}.linotes-note-row .title{font-weight:760;font-size:15px}.linotes-note-row .preview{color:#77737e;font-size:12px}.linotes-note-row .date{color:#96919b;font-size:11px}.linotes-card{background:#fff;border:1px solid #dad7df;border-radius:12px;padding:12px;min-width:180px;min-height:135px}.linotes-card:hover{border-color:#d3aa00;box-shadow:0 4px 14px rgba(60,48,0,.10)}.linotes-card-title{font-weight:800;font-size:15px}.linotes-card-preview{color:#66616c;font-size:12px}.linotes-toolbar{background:#fff;border-bottom:1px solid #e1dee5;padding:7px}.linotes-toolbar button{border-radius:9px}.linotes-search{border-radius:12px}.linotes-editor-title{font-size:26px;font-weight:800;border:0;background:transparent;padding:12px 18px 5px}.linotes-editor-text{font-size:16px;line-height:1.55;padding:12px 18px 28px;background:#fff}.linotes-status{color:#8b8690;font-size:11px;padding:5px 18px}.yellow-action{background:#e6b900;color:#17130a;border-radius:10px;font-weight:750}.yellow-action:hover{background:#f0c514}.destructive-action{color:#b4232d}.pin-badge{color:#a98200}.empty-title{font-size:22px;font-weight:800}.empty-copy{color:#807b85}.attachment-row{padding:4px 8px;border-radius:8px;background:#f3f1f5}.folder-count{color:#7e7984}.special-icon{color:#bd9600}.gallery-scroll{padding:12px}.gallery-scroll flowboxchild{margin:5px}
window.linotes-dark{background:#17161b;color:#f0ecf3}.linotes-dark .linotes-header{background:#201e24;border-color:#3c3742}.linotes-dark .linotes-sidebar{background:#1c1a20;border-color:#3c3742}.linotes-dark .linotes-list-pane{background:#211f25;border-color:#3f3945}.linotes-dark .linotes-editor{background:#19171d}.linotes-dark .linotes-folder-row:selected{background:#d7ad16;color:#16120a}.linotes-dark .linotes-folder-row:selected label{color:#16120a}.linotes-dark .linotes-note-row{border-color:#3b3640}.linotes-dark .linotes-note-row:selected{background:#493d20;color:#f6f0df}.linotes-dark .linotes-note-row .preview{color:#b9b2bd}.linotes-dark .linotes-note-row .date{color:#96909b}.linotes-dark .linotes-card{background:#25222a;border-color:#403a47}.linotes-dark .linotes-card:hover{border-color:#d7ad16;box-shadow:none}.linotes-dark .linotes-card-preview{color:#bbb4c0}.linotes-dark .linotes-toolbar{background:#211e25;border-color:#3c3742}.linotes-dark .linotes-editor-title{color:#f2eef5}.linotes-dark .linotes-editor-text{background:#19171d;color:#eeeaf2}.linotes-dark .linotes-status,.linotes-dark .folder-count,.linotes-dark .empty-copy{color:#aaa4b0}.linotes-dark .attachment-row{background:#29262e}.linotes-dark .destructive-action{color:#ff929d}.linotes-dark .pin-badge,.linotes-dark .special-icon{color:#e2bc35}.linotes-dark entry,.linotes-dark textview,.linotes-dark dropdown{color:#eeeaf2}
"""


from storage import Store


class NotesWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application, open_note_id: str = ""):
        super().__init__(application=app, title="LiNotes")
        self.set_default_size(1280, 800)
        self.set_size_request(900, 580)
        self.style_manager = Adw.StyleManager.get_default()
        self.style_manager.connect("notify::dark", self.on_color_scheme_changed)
        self.on_color_scheme_changed()
        self.store = Store()
        self.folder_id = "all"
        self.note_id = ""
        self.search_text = ""
        self.view_mode = "list"
        self.save_source = 0
        self.loading = False
        self.folder_rows: dict[Gtk.ListBoxRow, str] = {}
        self.note_rows: dict[Gtk.ListBoxRow, str] = {}
        self.card_rows: dict[Gtk.FlowBoxChild, str] = {}
        self.build_ui()
        self.refresh_folders()
        self.refresh_notes(select_id=open_note_id)

    def on_color_scheme_changed(self, *_args):
        if self.style_manager.get_dark():
            self.add_css_class("linotes-dark")
        else:
            self.remove_css_class("linotes-dark")

    def build_ui(self):
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS.encode())
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        header = Gtk.HeaderBar()
        header.add_css_class("linotes-header")
        self.set_titlebar(header)
        title = Gtk.Label(label="LiNotes")
        title.add_css_class("linotes-title")
        header.set_title_widget(title)

        new_button = Gtk.Button.new_from_icon_name("document-new-symbolic")
        new_button.set_tooltip_text("Neue Notiz")
        new_button.add_css_class("yellow-action")
        new_button.connect("clicked", self.on_new_note)
        header.pack_start(new_button)

        self.search = Gtk.SearchEntry(placeholder_text="Notizen durchsuchen")
        self.search.set_width_chars(28)
        self.search.add_css_class("linotes-search")
        self.search.connect("search-changed", self.on_search)
        header.pack_start(self.search)

        cloud = Gtk.Button(label="Apple Notizen")
        cloud.set_icon_name("cloud-symbolic")
        cloud.set_tooltip_text("Apple Notizen offiziell in iCloud über Zen öffnen")
        cloud.connect("clicked", lambda *_: Gio.AppInfo.launch_default_for_uri("https://www.icloud.com/notes/", None))
        header.pack_end(cloud)

        menu = Gio.Menu()
        menu.append("Datei importieren", "app.import")
        menu.append("Notiz exportieren", "app.export")
        menu.append("In LiLink öffnen", "app.lilink")
        menu.append("Über LiNotes", "app.about")
        menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu)
        header.pack_end(menu_button)

        outer = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        outer.set_position(245)
        self.set_child(outer)

        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar_box.add_css_class("linotes-sidebar")
        folder_title = Gtk.Label(label="Ordner", xalign=0)
        folder_title.add_css_class("linotes-folder-heading")
        sidebar_box.append(folder_title)
        self.folder_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.folder_list.connect("row-selected", self.on_folder_selected)
        folder_scroll = Gtk.ScrolledWindow(vexpand=True)
        folder_scroll.set_child(self.folder_list)
        sidebar_box.append(folder_scroll)
        folder_actions = Gtk.Box(spacing=6, margin_start=10, margin_end=10, margin_top=8, margin_bottom=10)
        add_folder = Gtk.Button(label="Neuer Ordner", icon_name="folder-new-symbolic", hexpand=True)
        add_folder.connect("clicked", self.on_new_folder)
        folder_actions.append(add_folder)
        sidebar_box.append(folder_actions)
        outer.set_start_child(sidebar_box)

        content = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        content.set_position(390)
        outer.set_end_child(content)

        list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        list_box.add_css_class("linotes-list-pane")
        list_header = Gtk.Box(spacing=8, margin_start=12, margin_end=12, margin_top=10, margin_bottom=8)
        self.list_title = Gtk.Label(label="Alle Notizen", xalign=0, hexpand=True)
        self.list_title.add_css_class("linotes-folder-heading")
        list_header.append(self.list_title)
        view_list = Gtk.ToggleButton(icon_name="view-list-symbolic", active=True)
        view_grid = Gtk.ToggleButton(icon_name="view-grid-symbolic", group=view_list)
        view_list.connect("toggled", lambda button: self.set_view("list") if button.get_active() else None)
        view_grid.connect("toggled", lambda button: self.set_view("grid") if button.get_active() else None)
        list_header.append(view_list)
        list_header.append(view_grid)
        list_box.append(list_header)

        self.note_stack = Gtk.Stack(vexpand=True)
        self.note_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.note_list.connect("row-selected", self.on_note_selected)
        list_scroll = Gtk.ScrolledWindow(vexpand=True)
        list_scroll.set_child(self.note_list)
        self.note_stack.add_named(list_scroll, "list")
        self.note_grid = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.SINGLE, max_children_per_line=2, min_children_per_line=1, row_spacing=8, column_spacing=8)
        self.note_grid.connect("child-activated", self.on_card_activated)
        grid_scroll = Gtk.ScrolledWindow(vexpand=True)
        grid_scroll.add_css_class("gallery-scroll")
        grid_scroll.set_child(self.note_grid)
        self.note_stack.add_named(grid_scroll, "grid")
        list_box.append(self.note_stack)
        content.set_start_child(list_box)

        self.editor_stack = Gtk.Stack()
        content.set_end_child(self.editor_stack)
        self.empty_editor = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        empty_title = Gtk.Label(label="Neue Gedanken festhalten")
        empty_title.add_css_class("empty-title")
        empty_copy = Gtk.Label(label="Wähle eine Notiz oder erstelle eine neue.")
        empty_copy.add_css_class("empty-copy")
        self.empty_editor.append(empty_title)
        self.empty_editor.append(empty_copy)
        self.editor_stack.add_named(self.empty_editor, "empty")

        editor = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        editor.add_css_class("linotes-editor")
        toolbar = Gtk.Box(spacing=4)
        toolbar.add_css_class("linotes-toolbar")
        self.pin_button = Gtk.ToggleButton(icon_name="view-pin-symbolic", tooltip_text="Anpinnen")
        self.pin_button.connect("toggled", self.on_pin)
        toolbar.append(self.pin_button)
        for label, token, tooltip in [
            ("H", "heading", "Überschrift"), ("B", "bold", "Fett"), ("I", "italic", "Kursiv"),
            ("☐", "check", "Checkliste"), ("•", "bullet", "Aufzählung")
        ]:
            button = Gtk.Button(label=label, tooltip_text=tooltip)
            button.connect("clicked", self.on_format, token)
            toolbar.append(button)
        toolbar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        attach = Gtk.Button(icon_name="mail-attachment-symbolic", tooltip_text="Datei anhängen")
        attach.connect("clicked", self.on_attach)
        toolbar.append(attach)
        self.restore_button = Gtk.Button(label="Wiederherstellen", icon_name="edit-undo-symbolic")
        self.restore_button.connect("clicked", self.on_restore)
        toolbar.append(self.restore_button)
        spacer = Gtk.Box(hexpand=True)
        toolbar.append(spacer)
        trash = Gtk.Button(icon_name="user-trash-symbolic", tooltip_text="In den Papierkorb")
        trash.add_css_class("destructive-action")
        trash.connect("clicked", self.on_trash)
        toolbar.append(trash)
        editor.append(toolbar)

        self.title_entry = Gtk.Entry(placeholder_text="Titel")
        self.title_entry.add_css_class("linotes-editor-title")
        self.title_entry.connect("changed", self.schedule_save)
        editor.append(self.title_entry)

        self.folder_dropdown = Gtk.DropDown()
        self.folder_dropdown.set_margin_start(18)
        self.folder_dropdown.set_margin_end(18)
        self.folder_dropdown.set_margin_bottom(4)
        self.folder_dropdown.connect("notify::selected", self.schedule_save)
        editor.append(self.folder_dropdown)

        body_scroll = Gtk.ScrolledWindow(vexpand=True)
        self.text_view = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, top_margin=12, bottom_margin=28, left_margin=18, right_margin=18)
        self.text_view.add_css_class("linotes-editor-text")
        self.text_view.get_buffer().connect("changed", self.schedule_save)
        body_scroll.set_child(self.text_view)
        editor.append(body_scroll)

        self.attachments_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=7, margin_start=18, margin_end=18, margin_bottom=8)
        editor.append(self.attachments_box)
        self.status = Gtk.Label(label="", xalign=0)
        self.status.add_css_class("linotes-status")
        editor.append(self.status)
        self.editor_stack.add_named(editor, "editor")
        self.editor_stack.set_visible_child_name("empty")

    def clear_list(self, widget):
        child = widget.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            widget.remove(child)
            child = next_child

    def folder_row(self, label: str, icon: str, count: int, folder_id: str) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row.add_css_class("linotes-folder-row")
        box = Gtk.Box(spacing=10, margin_start=5, margin_end=5, margin_top=3, margin_bottom=3)
        image = Gtk.Image.new_from_icon_name(icon)
        image.add_css_class("special-icon")
        box.append(image)
        box.append(Gtk.Label(label=label, xalign=0, hexpand=True))
        count_label = Gtk.Label(label=str(count))
        count_label.add_css_class("folder-count")
        box.append(count_label)
        row.set_child(box)
        self.folder_rows[row] = folder_id
        return row

    def refresh_folders(self):
        selected = self.folder_id
        self.folder_rows.clear()
        self.clear_list(self.folder_list)
        total = len(self.store.notes("all"))
        deleted = len(self.store.notes("deleted", deleted=True))
        self.folder_list.append(self.folder_row("Alle Notizen", "folder-symbolic", total, "all"))
        for folder in self.store.folders():
            icon = "document-edit-symbolic" if folder["id"] == "quick" else "folder-symbolic"
            self.folder_list.append(self.folder_row(folder["name"], icon, folder["count"], folder["id"]))
        self.folder_list.append(self.folder_row("Zuletzt gelöscht", "user-trash-symbolic", deleted, "deleted"))
        for row, folder_id in self.folder_rows.items():
            if folder_id == selected:
                self.folder_list.select_row(row)
                break

    def note_preview(self, note: dict) -> str:
        lines = [re.sub(r"^[#>*☐☑•\-\s]+", "", line).strip() for line in (note.get("body") or "").splitlines()]
        return " ".join(line for line in lines if line)[:130] or "Keine weiteren Inhalte"

    def format_date(self, value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone()
            return parsed.strftime("%d.%m.%Y · %H:%M")
        except Exception:
            return value[:16]

    def make_note_row(self, note: dict) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row.add_css_class("linotes-note-row")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        title_line = Gtk.Box(spacing=5)
        if note.get("pinned"):
            pin = Gtk.Image.new_from_icon_name("view-pin-symbolic")
            pin.add_css_class("pin-badge")
            title_line.append(pin)
        title = Gtk.Label(label=note.get("title") or "Neue Notiz", xalign=0, hexpand=True, ellipsize=3)
        title.add_css_class("title")
        title_line.append(title)
        box.append(title_line)
        preview = Gtk.Label(label=self.note_preview(note), xalign=0, ellipsize=3, max_width_chars=42)
        preview.add_css_class("preview")
        box.append(preview)
        meta = Gtk.Label(label=f"{self.format_date(note['updated_at'])} · {note.get('folder_name') or 'Notizen'}", xalign=0)
        meta.add_css_class("date")
        box.append(meta)
        row.set_child(box)
        self.note_rows[row] = note["id"]
        return row

    def make_note_card(self, note: dict) -> Gtk.FlowBoxChild:
        child = Gtk.FlowBoxChild()
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        card.add_css_class("linotes-card")
        title_line = Gtk.Box(spacing=5)
        title = Gtk.Label(label=note.get("title") or "Neue Notiz", xalign=0, hexpand=True, ellipsize=3)
        title.add_css_class("linotes-card-title")
        title_line.append(title)
        if note.get("pinned"):
            pin = Gtk.Image.new_from_icon_name("view-pin-symbolic")
            pin.add_css_class("pin-badge")
            title_line.append(pin)
        card.append(title_line)
        preview = Gtk.Label(label=self.note_preview(note), xalign=0, yalign=0, wrap=True, lines=4, ellipsize=3)
        preview.add_css_class("linotes-card-preview")
        preview.set_vexpand(True)
        card.append(preview)
        date = Gtk.Label(label=self.format_date(note["updated_at"]), xalign=0)
        date.add_css_class("date")
        card.append(date)
        child.set_child(card)
        self.card_rows[child] = note["id"]
        return child

    def refresh_notes(self, select_id: str = ""):
        self.save_now()
        deleted = self.folder_id == "deleted"
        notes = self.store.notes(self.folder_id, self.search_text, deleted=deleted)
        title = "Alle Notizen" if self.folder_id == "all" else "Zuletzt gelöscht" if deleted else (self.store.folder(self.folder_id) or {}).get("name", "Notizen")
        self.list_title.set_label(f"{title} · {len(notes)}")
        self.note_rows.clear()
        self.card_rows.clear()
        self.clear_list(self.note_list)
        self.clear_list(self.note_grid)
        for note in notes:
            self.note_list.append(self.make_note_row(note))
            self.note_grid.append(self.make_note_card(note))
        desired = select_id or self.note_id
        if desired:
            for row, note_id in self.note_rows.items():
                if note_id == desired:
                    self.note_list.select_row(row)
                    self.open_note(note_id)
                    return
        if notes:
            first_id = notes[0]["id"]
            if self.view_mode == "list":
                first_row = next(iter(self.note_rows))
                self.note_list.select_row(first_row)
            self.open_note(first_id)
        else:
            self.note_id = ""
            self.editor_stack.set_visible_child_name("empty")

    def open_note(self, note_id: str):
        self.save_now()
        note = self.store.note(note_id)
        if not note:
            return
        self.loading = True
        self.note_id = note_id
        self.title_entry.set_text(note.get("title") or "")
        self.text_view.get_buffer().set_text(note.get("body") or "")
        folders = self.store.folders()
        names = Gtk.StringList.new([item["name"] for item in folders])
        self.folder_dropdown.set_model(names)
        selected = next((index for index, item in enumerate(folders) if item["id"] == note.get("folder_id")), 0)
        self.folder_dropdown.set_selected(selected)
        self.folder_dropdown.set_sensitive(not bool(note.get("deleted_at")))
        self.pin_button.set_active(bool(note.get("pinned")))
        self.pin_button.set_sensitive(not bool(note.get("deleted_at")))
        self.restore_button.set_visible(bool(note.get("deleted_at")))
        self.status.set_label(f"Automatisch gespeichert · {self.format_date(note['updated_at'])}")
        self.refresh_attachments()
        self.editor_stack.set_visible_child_name("editor")
        self.loading = False

    def selected_folder_id(self) -> str:
        folders = self.store.folders()
        index = int(self.folder_dropdown.get_selected())
        return folders[index]["id"] if 0 <= index < len(folders) else "notes"

    def schedule_save(self, *_):
        if self.loading or not self.note_id:
            return
        if self.save_source:
            GLib.source_remove(self.save_source)
        self.status.set_label("Speichern …")
        self.save_source = GLib.timeout_add(450, self.save_now)

    def save_now(self):
        if self.save_source:
            try:
                GLib.source_remove(self.save_source)
            except Exception:
                pass
            self.save_source = 0
        if self.loading or not self.note_id:
            return False
        note = self.store.note(self.note_id)
        if not note or note.get("deleted_at"):
            return False
        buffer = self.text_view.get_buffer()
        body = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
        self.store.update_note(self.note_id, self.title_entry.get_text(), body, self.selected_folder_id())
        self.status.set_label("Automatisch gespeichert")
        return False

    def set_view(self, mode: str):
        self.view_mode = mode
        self.note_stack.set_visible_child_name(mode)

    def on_folder_selected(self, _list, row):
        if not row or row not in self.folder_rows:
            return
        folder_id = self.folder_rows[row]
        if folder_id == self.folder_id:
            return
        self.folder_id = folder_id
        self.refresh_notes()

    def on_note_selected(self, _list, row):
        if row and row in self.note_rows:
            self.open_note(self.note_rows[row])

    def on_card_activated(self, _flowbox, child):
        note_id = self.card_rows.get(child)
        if note_id:
            self.open_note(note_id)

    def on_search(self, entry):
        self.search_text = entry.get_text()
        self.refresh_notes()

    def on_new_note(self, *_):
        folder = self.folder_id if self.folder_id not in {"all", "deleted"} else "notes"
        note = self.store.create_note(folder)
        self.refresh_folders()
        self.refresh_notes(select_id=note["id"])
        self.title_entry.grab_focus()
        self.title_entry.select_region(0, -1)

    def on_new_folder(self, *_):
        dialog = Gtk.Dialog(title="Neuer Ordner", transient_for=self, modal=True)
        dialog.add_button("Abbrechen", Gtk.ResponseType.CANCEL)
        dialog.add_button("Erstellen", Gtk.ResponseType.OK)
        entry = Gtk.Entry(placeholder_text="Ordnername", margin_top=14, margin_bottom=14, margin_start=16, margin_end=16)
        dialog.get_content_area().append(entry)
        dialog.connect("response", lambda d, response: self.finish_new_folder(d, response, entry))
        dialog.present()

    def finish_new_folder(self, dialog, response, entry):
        if response == Gtk.ResponseType.OK and entry.get_text().strip():
            try:
                folder = self.store.add_folder(entry.get_text())
                self.folder_id = folder.get("id", "all")
            except Exception:
                self.toast("Dieser Ordner ist bereits vorhanden.")
        dialog.destroy()
        self.refresh_folders()
        self.refresh_notes()

    def on_pin(self, button):
        if self.loading or not self.note_id:
            return
        self.store.pin(self.note_id, button.get_active())
        self.refresh_notes(select_id=self.note_id)

    def on_format(self, _button, kind: str):
        buffer = self.text_view.get_buffer()
        if buffer.get_has_selection():
            start, end = buffer.get_selection_bounds()
            text = buffer.get_text(start, end, True)
        else:
            start = end = buffer.get_iter_at_mark(buffer.get_insert())
            text = ""
        replacements = {
            "heading": ("## ", ""), "bold": ("**", "**"), "italic": ("_", "_"),
            "check": ("☐ ", ""), "bullet": ("• ", ""),
        }
        prefix, suffix = replacements[kind]
        buffer.begin_user_action()
        if buffer.get_has_selection():
            buffer.delete(start, end)
        buffer.insert(start, prefix + text + suffix)
        buffer.end_user_action()
        self.text_view.grab_focus()

    def on_trash(self, *_):
        if not self.note_id:
            return
        note = self.store.note(self.note_id)
        if not note:
            return
        if note.get("deleted_at"):
            self.store.purge(self.note_id)
        else:
            self.store.trash(self.note_id)
        self.note_id = ""
        self.refresh_folders()
        self.refresh_notes()

    def on_restore(self, *_):
        if self.note_id:
            self.store.restore(self.note_id)
            self.folder_id = "all"
            self.refresh_folders()
            self.refresh_notes(select_id=self.note_id)

    def choose_file(self, title: str, action: Gtk.FileChooserAction, callback, multiple: bool = False):
        chooser = Gtk.FileChooserNative(title=title, transient_for=self, action=action, accept_label="Auswählen" if action == Gtk.FileChooserAction.OPEN else "Speichern", cancel_label="Abbrechen")
        chooser.set_select_multiple(multiple)
        chooser.connect("response", lambda c, response: callback(c) if response == Gtk.ResponseType.ACCEPT else c.destroy())
        chooser.show()

    def on_attach(self, *_):
        if not self.note_id:
            return
        self.choose_file("Datei anhängen", Gtk.FileChooserAction.OPEN, self.finish_attach, multiple=True)

    def finish_attach(self, chooser):
        files = chooser.get_files()
        for index in range(files.get_n_items()):
            path = files.get_item(index).get_path()
            if path:
                item = self.store.add_attachment(self.note_id, Path(path))
                buffer = self.text_view.get_buffer()
                buffer.insert(buffer.get_end_iter(), f"\n[Anhang: {item['name']}](file://{item['path']})\n")
        chooser.destroy()
        self.refresh_attachments()
        self.schedule_save()

    def refresh_attachments(self):
        self.clear_list(self.attachments_box)
        if not self.note_id:
            return
        for item in self.store.attachments(self.note_id):
            row = Gtk.Box(spacing=5)
            row.add_css_class("attachment-row")
            open_button = Gtk.Button(label=item["name"], icon_name="mail-attachment-symbolic")
            open_button.connect("clicked", lambda _b, path=item["path"]: Gio.AppInfo.launch_default_for_uri(Path(path).as_uri(), None))
            row.append(open_button)
            remove = Gtk.Button(icon_name="window-close-symbolic", tooltip_text="Anhang entfernen")
            remove.connect("clicked", lambda _b, aid=item["id"]: self.remove_attachment(aid))
            row.append(remove)
            self.attachments_box.append(row)

    def remove_attachment(self, attachment_id: str):
        self.store.remove_attachment(attachment_id)
        self.refresh_attachments()

    def import_notes(self):
        self.choose_file("Notizen importieren", Gtk.FileChooserAction.OPEN, self.finish_import, multiple=True)

    def import_paths(self, paths: list[Path]):
        count = 0
        folder = self.folder_id if self.folder_id not in {"all", "deleted"} else "notes"
        for path in paths:
            try:
                count += len(self.store.import_file(path, folder))
            except Exception as error:
                self.toast(f"Import fehlgeschlagen: {error}")
        self.refresh_folders()
        self.refresh_notes()
        self.toast(f"{count} Notiz(en) importiert.")
        return False

    def finish_import(self, chooser):
        files = chooser.get_files()
        count = 0
        folder = self.folder_id if self.folder_id not in {"all", "deleted"} else "notes"
        for index in range(files.get_n_items()):
            path = files.get_item(index).get_path()
            if not path:
                continue
            try:
                count += len(self.store.import_file(Path(path), folder))
            except Exception as error:
                self.toast(f"Import fehlgeschlagen: {error}")
        chooser.destroy()
        self.refresh_folders()
        self.refresh_notes()
        self.toast(f"{count} Notiz(en) importiert.")

    def export_note(self):
        if not self.note_id:
            self.toast("Keine Notiz ausgewählt.")
            return
        note = self.store.note(self.note_id)
        chooser = Gtk.FileChooserNative(title="Notiz exportieren", transient_for=self, action=Gtk.FileChooserAction.SAVE, accept_label="Exportieren", cancel_label="Abbrechen")
        chooser.set_current_name(re.sub(r"[^\w .-]+", "_", note["title"]) + ".md")
        chooser.connect("response", lambda c, response: self.finish_export(c, response, note))
        chooser.show()

    def finish_export(self, chooser, response, note):
        if response == Gtk.ResponseType.ACCEPT:
            path = chooser.get_file().get_path()
            if path:
                target = Path(path)
                suffix = target.suffix.lower()
                if suffix in {".html", ".htm"}:
                    content = f"<!doctype html><meta charset='utf-8'><title>{html.escape(note['title'])}</title><h1>{html.escape(note['title'])}</h1><pre>{html.escape(note['body'])}</pre>"
                elif suffix == ".txt":
                    content = f"{note['title']}\n\n{note['body']}"
                else:
                    if not suffix:
                        target = target.with_suffix(".md")
                    content = f"# {note['title']}\n\n{note['body']}"
                target.write_text(content, encoding="utf-8")
                self.toast(f"Exportiert: {target.name}")
        chooser.destroy()

    def open_lilink(self):
        try:
            subprocess.Popen(["lilink"], start_new_session=True)
        except OSError:
            self.toast("LiLink ist nicht verfügbar.")

    def toast(self, text: str):
        self.status.set_label(text)


class NotesApplication(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.window: NotesWindow | None = None
        for name, callback in {
            "import": self.action_import,
            "export": self.action_export,
            "lilink": self.action_lilink,
            "about": self.action_about,
        }.items():
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

    def do_activate(self):
        if not self.window:
            self.window = NotesWindow(self)
        self.window.present()

    def do_command_line(self, command_line):
        arguments = command_line.get_arguments()[1:]
        note_id = ""
        create_new = "--new" in arguments
        import_requested = "--import" in arguments
        import_paths: list[Path] = []
        for index, value in enumerate(arguments):
            if value == "--note" and index + 1 < len(arguments):
                note_id = arguments[index + 1]
            elif value.startswith("linotes://note/"):
                note_id = value.rsplit("/", 1)[-1]
            elif value.startswith("file://"):
                path = Gio.File.new_for_uri(value).get_path()
                if path and Path(path).is_file():
                    import_paths.append(Path(path))
            elif not value.startswith("--") and Path(value).is_file():
                import_paths.append(Path(value))
        if not self.window:
            self.window = NotesWindow(self, note_id)
        elif note_id:
            self.window.open_note(note_id)
        self.window.present()
        if create_new:
            GLib.idle_add(self.window.on_new_note)
        if import_requested:
            GLib.idle_add(self.window.import_notes)
        if import_paths:
            GLib.idle_add(self.window.import_paths, import_paths)
        command_line.set_exit_status(0)
        return 0

    def action_import(self, *_):
        self.do_activate()
        self.window.import_notes()

    def action_export(self, *_):
        self.do_activate()
        self.window.export_note()

    def action_lilink(self, *_):
        self.do_activate()
        self.window.open_lilink()

    def action_about(self, *_):
        self.do_activate()
        dialog = Gtk.AboutDialog(transient_for=self.window, modal=True, program_name="LiNotes", version=VERSION, comments="Notizen für LiMaD OS", website="https://github.com/bushcraftjw-glitch/limad-os")
        dialog.present()


def main() -> int:
    return NotesApplication().run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())

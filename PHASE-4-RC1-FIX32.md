# LiMaD OS 2.7.0-rc1 FIX32

## Aerion Mail und Dock

FIX32 ergänzt Aerion als Benutzer-Flatpak aus Flathub:

- Aerion (`io.github.hkdb.Aerion`)
- Desktop-Datei: `io.github.hkdb.Aerion.desktop`

Die Installation erfolgt beim ersten GNOME-Login ohne Veränderung des unveränderlichen bootc-/OSTree-Systembereichs. Bei fehlendem Netzwerk wird sie automatisch beim nächsten Login erneut versucht.

Vor dem ersten Start wird ausschließlich Aerions Einstellung `native_titlebar=true` in der benutzereigenen Einstellungsdatenbank gesetzt. Dadurch verwendet Aerion die native GNOME-Titelleiste und übernimmt die linken LiMaD-Fensterbuttons. Vorhandene Konten und andere Einstellungen werden nicht verändert.

Die Dock-Reihenfolge lautet: Zen, Aerion, LiMaDCut, Study, LiDrop, Windows, LiMaD Updates, Anycubic, Zoom, Bazaar, Terminal und Dateien. Danach folgen Papierkorb und „Anwendungen anzeigen“.

Der bootc-sichere initramfs-Rollback aus FIX30 und alle FIX31-Funktionen bleiben erhalten.

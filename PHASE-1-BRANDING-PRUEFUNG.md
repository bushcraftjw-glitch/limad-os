# Phase 1 – verbindliche Branding-Prüfung

Der GitHub-Workflow bricht automatisch ab, wenn eine dieser Prüfungen fehlschlägt:

1. Das fertige Container-Abbild enthält `NAME="LiMaD OS"` und einen LiMaD-Bootloader-Titel.
2. `default.plymouth` zeigt auf das LiMaD-Plymouth-Thema und alle Dateien sind für Dracut eingetragen.
3. Das Standard-Wallpaper ist in GLib und in der systemweiten, nicht gesperrten dconf-Datenbank gesetzt.
4. Das LiMaD-L ist vorhanden; eingebettete Bazzite-Fallback-Logos des Logo-Menüs werden beim Image-Bau überschrieben.
5. Die fertige ISO enthält `/images/product.img` mit `Product=LiMaD OS` und `IsFinal=True`.
6. Alle gefundenen BIOS-/UEFI-Bootkonfigurationen enthalten LiMaD OS und keinen Bazzite-Schriftzug.
7. Das Installer-product.img enthält LiMaD-Branding für LiMaD-, Bazzite- und Fedora-Cockpit-Pfade.

## Manueller Abnahmetest nach dem GitHub-Build

Für die endgültige Freigabe ist eine echte Neuinstallation erforderlich:

- USB-Stick von der neuen ISO starten: Bootmenü zeigt LiMaD OS und den LiMaD-Hintergrund.
- Installer öffnen: LiMaD-Logo, LiMaD-Name und violette LiMaD-Akzente sichtbar.
- Installation abschließen und neu starten: LiMaD-Bootscreen, kein Bazzite-Logo.
- Erster Desktopstart: Wallpaper 02 ist Standard.
- Links oben: LiMaD-L statt Bazzite-Symbol.
- Einstellungen → System → Info: LiMaD OS.

Erst nach diesem echten Neuinstallationstest wird Phase 2 begonnen.

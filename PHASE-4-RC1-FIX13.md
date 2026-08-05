# LiMaD OS 2.7.0-rc1 FIX13

FIX13 enthält den vollständigen Stand von FIX12 und korrigiert die abschließende ISO-Branding-Prüfung.

## Korrektur

`tools/verify-branded-iso.sh` prüft bei GRUB-Menüzeilen jetzt nur den tatsächlich sichtbaren Titel. Interne GRUB-Metadaten wie `--class fedora` sind nicht sichtbar und lösen deshalb keinen falschen Branding-Fehler mehr aus.

Zusätzlich bleiben die vorherigen Korrekturen erhalten:

- zuverlässiges Lesen der ISO-Volume-ID aus der xorriso-Ausgabe
- robuste Erkennung der Boot-Konfigurationsdateien
- Prüfung des sichtbaren LiMaD-OS-Bootmenüs
- technische Fedora-Identität für bootc-image-builder

Buildrevision: `gnome42-phase4-fix13`.
First-Login-Migrationsmarker: `2.7.0-rc1-fix13`.

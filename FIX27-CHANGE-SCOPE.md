# LiMaD OS 2.7.0 RC1 FIX27 – geprüfter Änderungsumfang

## Verbindliche Basis

- Basis: LiMaD OS 2.7.0 RC1 FIX22
- Basisarchiv: `LiMaD-OS-2.7.0-RC1-FIX22-GNOME-Anaconda-Label-Path-Repair(1).zip`
- SHA-256 der Basis: `56e2e53416a772b7753e7af45d0fbc969bea61e372ae657fc599cc04ea6b4a5e`
- Es wurden keine Dateien aus FIX23, FIX24, FIX25 oder FIX26 als Systembasis übernommen.

## Unverändert geschützte FIX22-Bereiche

Eine Hash- und Modus-Schutzliste prüft 398 bestehende Dateien aus FIX22. Dazu gehören insbesondere:

- MacTahoe-/WhiteSur-Designquellen und bestehende Theme-Konfiguration
- LiMaD-Wallpaper und bestehende Wallpaper-Auswahl
- App-Payloads und bestehende Programmdateien
- ISO-Bauwerkzeuge und GitHub-Workflow, soweit keine Versionsprüfung angepasst werden musste
- vorhandene Update- und Installationsmechanismen

Es wurden keine Dateien aus FIX22 entfernt.

## Ausdrücklich eingebaute Änderungen

1. Vollständiger LiMaD-Bootscreen bleibt als ruhiges Hintergrundbild erhalten.
2. Separater violetter Plymouth-Ladering mit zwölf Einzelbildern.
3. LiMaD-Branding für Installer, Systeminformationen, Fastfetch und sichtbare Fallback-Logos.
4. Transparentes, größenoptimiertes LiMaD-L für das GNOME-Startmenü.
5. Gepinntes Logo-Menu-Schema mit LiMaD-L als Standard und Schutz gegen doppelte Schema-IDs.
6. Sichtbare Fedora-/Bazzite-Produktgrafiken werden durch LiMaD-Grafiken ersetzt, ohne die technisch notwendige Fedora-Kompatibilitäts-ID zu entfernen.
7. LiMaD Cut, LiDrop, LiMaD Windows Installer und Anycubic werden beim ersten Login ergänzt, ohne vorhandene Favoriten zu löschen.
8. Windows-Auto-Installer mit Profil- und Rezeptlogik für Standard, .NET/NWS, Office, CAD, Kreativprogramme, Spiele, ältere Programme und Minimalbetrieb.
9. Abhängigkeiten werden geordnet über Winetricks installiert; Wine-Prefix, Protokollierung und Fehlerdialoge sind integriert.
10. FIX22-Fensterlayout wird exakt als `close,maximize,minimize:` auf der linken Seite erzwungen.

## Nicht verändert

- farbige macOS-artige Fensterbuttons aus FIX22
- Position und Reihenfolge der Fensterbuttons
- Wallpaper
- GTK-/Shell-Theme und Dock-Stil
- übriges Desktopdesign

## Zusätzliche Schutzprüfungen

- synthetischer Konflikttest für abweichende Fedora-/Bazzite-Button-Overrides
- simulierter erster GNOME-Login mit bestehender Favoritenliste
- Logo-Menu-Schema-Patchtest
- Windows-Rezept- und Abhängigkeitspläne
- Plymouth-Animations- und Grafikprüfung
- vollständige FIX22-Baseline-Prüfung
- GitHub-Workflow-, Container-, OSTree-, EFI-, Anaconda-, ISO-Label- und Medienprüfungen

Der reale GitHub-Containerbau, die ISO-Erzeugung und der Hardware-Livetest bleiben die abschließenden Laufzeitprüfungen.

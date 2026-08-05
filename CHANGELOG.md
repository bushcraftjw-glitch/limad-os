# LiMaD OS 2.8.0 RC2 Build 5 – LiNotes und Study-Wachtturm-Korrektur

- LiNotes 1.0.0-preview1 als native GTK4-Notizen-App integriert.
- Ordner, Schnellnotizen, Pins, Suche, Liste/Galerie, automatische Speicherung, Anhänge und Papierkorb ergänzt.
- TXT-, Markdown-, HTML-, RTF- und ENEX-Import sowie TXT-, Markdown- und HTML-Export ergänzt.
- Apple Notizen werden offiziell über iCloud im Zen Browser geöffnet; keine ungesicherte native Apple-Datenbanksynchronisation wird behauptet.
- LiMaD Study auf 6.6.2 angehoben.
- Wachtturm-Fragen kleiner und grau, Fragennummern kräftig dargestellt.
- Wachtturm-Studienartikel wird anhand der ausgewählten Woche direkt aufgelöst.
- LiSave auf 1.0.0-preview2 und LiLink auf 1.0.0-preview3 angehoben.
- LiNotes in Dock, First Login, GNOME-Suche, LiMaD Update, LiSave und LiLink integriert.

# LiMaD OS 2.8.0 RC2 Build 4 – LiSave, Zen DE und LiDrop-Ordner

- LiSave 1.0.0-preview1 als verschlüsselte, inkrementelle Backup- und Wiederherstellungs-App integriert.
- Zen Browser verbindlich als deutscher Hauptbrowser eingerichtet und in LiSave vollständig berücksichtigt.
- LiDrop 0.12.0-preview4 und LiLink 1.0.0-preview2 verwenden gemeinsam `Downloads/LiDrop`.
- LiDrop- und LiLink-Sync-Ordner werden beim ersten Login angelegt und dauerhaft in Dateien/Nautilus angezeigt.
- Alter `~/LiDrop`-Bestand wird verlustfrei migriert; Kompatibilitätslink bleibt bestehen.
- LiSave erfasst Flatpaks und Windows-Programme als Wiederherstellungsplan und lädt neu verfügbare Programme bei der Wiederherstellung aus dem Internet.
- LiMaD Study wird zusätzlich über die eigene JWL-Library-Exportfunktion gesichert.
- Automatische tägliche Sicherung, Backup vor Systemupdate, Aufbewahrungsregeln und Clean-Install-Erkennung ergänzt.
- Alle Funktionen aus Build 3 einschließlich GStreamer-Härtung, konsistentem Windows-Programme-Icon und LiLink bleiben enthalten.

# LiMaD OS 2.8.0 RC2 Build 3 – LiLink & GStreamer

- Windows-Programme-Icon über alle Raster- und SVG-Fallbacks vereinheitlicht.
- GStreamer samt Python-Bindings und GTK4-Sink als verbindliche Basisinstallation ergänzt.
- `gtk4paintablesink`, Playbin, PipeWire und Python-GI werden während des Builds hart geprüft.
- Bestehende Build-2-Funktionen einschließlich LiLink bleiben unverändert enthalten.

# LiMaD OS Changelog

## 2.8.0 RC2 Build 2 – LiLink

- LiLink 1.0.0-preview2 als neue System-App integriert.
- Andere LiMaD-OS-Rechner werden über `_limad-link._tcp` automatisch gefunden.
- Einmalige Kopplung mit sechsstelliger Bestätigung, getrennten Gerätetoken und gespeicherten TLS-SHA-256-Fingerabdrücken.
- Native GNOME-Remote-Desktop-Integration für Bildschirmübernahme; FreeRDP erhält Zugangsdaten über Standardeingabe statt Prozessargumenten.
- Neues GNOME-Panel-Symbol mit großem und kleinem Monitor.
- Verschlüsselte, fortsetzbare Dateiübertragung mit abschließender SHA-256-Prüfung.
- Handoff-Grundgerüst für LiMaD Study, LiMaD Cut, LibreOffice, Medien, Zen Browser sowie URL/Datei.
- Deskflow-Integration als Bedienoberfläche für gemeinsame Maus und Tastatur.
- LiLink in LiMaD Update, First Login, Dock, GNOME-Vorgaben, Build-Verifikation und vollständige Offline-Testkette aufgenommen.
- Bestehende Casting-App sichtbar in „LiMaD auf TV übertragen“ umbenannt und auf 1.0.1 angehoben.
- Simulierter Zwei-Geräte-Test für TLS-Kopplung, gegenseitige Autorisierung, 3-MB-Dateiübertragung, SHA-256 und Widerruf ergänzt.

## 2.8.0 RC2 Build 1

- Based on the confirmed RC1 Build 9 source tree.
- Integrates LiMaD Study 6.6.1.
- Integrates Windows-Programme 2.2.5 and adds it to LiMaD Updates.
- Replaces Aerion with LiMaD Mail 1.8 based on Thunderbird ESR.
- Adds Zoom, YTMDesktop and LibreOffice to the default first-login installation.
- Updates dock order, RC2 first-login markers, Plymouth markers and ISO volume ID.
- Keeps LiDrop 0.12.0-preview4, LiMaD Cut 1.1.4, Screen Share 1.0.0 and Anycubic Slicer Next 1.3.96.

## Build 9 – GitHub OCI runtime compatibility fix

- fixes `crun: unknown version specified` before the first Containerfile RUN step
- pins upstream runc 1.4.2 for GitHub image and ISO builds
- verifies runc.amd64 with SHA-256 before use
- uses the same runtime for Buildah, Podman checks, BIB wrapper and ISO creation
- adds an offline regression test for OCI runtime wiring

## 2.8.0-RC1-BUILD9 – Windows-Programme 2.0

- existing Windows-Programme app replaced in place; app ID and dock icon retained
- single-window installer with Installieren, Meine Programme, Reparieren, Umgebungen, Protokoll and Einstellungen
- one isolated Wine WoW64 prefix per application
- resumable dependency manager with retries and warning-based continuation
- EXE/MSI content analysis for runtimes and known Wine blockers
- WebView2 and .NET Desktop Runtime provider support
- per-program repair, launch, menu entry and environment removal
- LiMaD Study 6.5.0 and LiDrop 0.12.0-preview4 retained

## Build 8 – globaler Wine-11-WoW64-Fix

- allgemeiner Prefix-Fix für alle 32- und 64-Bit-EXE/MSI-Dateien
- WINEARCH von win64 auf wow64 umgestellt
- syswow64/regedit.exe wird vor Winetricks geprüft
- automatisches corefonts aus allen Profilen entfernt
- wine-winefonts explizit im Systemabbild enthalten
- vorhandene NWS-Erkennung unverändert

## 2.8.0-RC1-BUILD8-GNOME50-Study6.5.0-LiDrop-IconSync

- LiMaD Study updated from 6.3.1 to 6.5.0
- LiDrop updated from 0.12.0-preview1 to 0.12.0-preview4
- LiDrop mobile layout fix for long filenames included
- LiDrop dock icon synchronized with the in-app branding icon
- Build 7 GNOME50 / Plymouth base retained

# LiMaD OS changelog

## 2.8.0 RC1 Build 2 – Screen sharing

- Adds LiMaD Screen Sharing 1.0.0.
- Native Google Cast and Miracast through GNOME Network Displays.
- Experimental Apple TV/AirPlay sender pinned to Doubletake v0.4.0.
- AirPlay is opt-in and opens TCP/UDP 60000-60010 only temporarily.
- Adds per-user update-package support for `de.limad.ScreenShare`.

- Neue Produktversion auf Basis des funktionsfähigen FIX50-Stands.
- LiMaD-Plymouth bleibt über den sicheren rpm-ostree-initramfs-Weg aktiviert; kein `dracut --force`.
- LiMaD Klang verwendet den Preset-Modus als zuverlässige Basis und die EasyEffects-Socketsteuerung nur optional.
- Installerdesign, Study 6.2.2, Cut 1.1.4, LiDrop 0.11.0-preview5, AMD-/Gaming-/Wine-Integration und GitHub-Ziel bleiben erhalten.
- Versionsmarker, ISO-Kennung, GHCR-Paketname und Startskripte sind auf 2.8.0 RC1 Build 1 synchronisiert.

# Changelog

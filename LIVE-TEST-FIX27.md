# FIX27 – Live-Test nach erfolgreichem GitHub-Build

## 1. ISO und Installation

1. ISO als GitHub-Artefakt herunterladen und auf einen USB-Stick schreiben.
2. Im ISO-Bootmenü prüfen, dass **LiMaD OS** statt Fedora/Bazzite sichtbar ist.
3. Beim Start muss der vollständige LiMaD-Screen ruhig stehen; nur der violette Ring dreht sich.
4. Im Installer LiMaD-Logo und Produktname kontrollieren.
5. Installation vollständig durchführen und neu starten.

## 2. Unverändertes FIX22-Design

- Fensterknöpfe links und farbig: Rot, Grün, Orange.
- Reihenfolge technisch: `close,maximize,minimize:`.
- LiMaD-Wallpaper 02 weiterhin Standard.
- Theme, Dock-Optik und Dock-Verhalten wie in der installierten FIX22-Version.

## 3. Branding

- oben links nur das feine transparente LiMaD-L, kein Fedora-/Bazzite-Symbol,
- Einstellungen → System → Info: **LiMaD OS** und LiMaD-Logo,
- `fastfetch`: LiMaD-Logo und LiMaD-OS-Bezeichnung,
- Login und erneutes Booten weiterhin mit LiMaD-Branding.

## 4. Dock

Folgende Starter müssen ohne manuelles Anheften vorhanden sein:

- LiMaD Cut
- LiDrop
- Windows-Programme
- Anycubic Slicer Next

LiMaD Study und vorhandene Systemstarter dürfen weiterhin vorhanden sein.

## 5. Windows-Auto-Installer

1. **Windows-Programme** öffnen.
2. Zuerst eine kleine bekannte EXE testen.
3. Installationsplan, Profil und Abhängigkeiten prüfen.
4. Danach NWS testen und kontrollieren, dass Core Fonts und .NET 4.8 vorbereitet werden.
5. Bei einem Fehler `~/.local/share/limad-windows/install.log` sichern.
6. Diagnose über `limad-wine-diagnose` ausführen.

## 6. Rückmeldung

Bei Abweichungen bitte Screenshot und die letzten relevanten Zeilen aus GitHub Actions beziehungsweise dem Wine-Protokoll übermitteln. Keine weitere Designänderung vornehmen, bevor der konkrete Fehler isoliert ist.

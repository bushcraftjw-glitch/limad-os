# LiMaD Windows Auto-Installer – Live-Test

## 1. Systemabbild bauen und installieren
Den normalen GitHub-Build starten und das daraus erzeugte LiMaD-OS-Abbild installieren beziehungsweise aktualisieren.

## 2. Grundtest
Im GNOME-Menü `Windows-Programme` öffnen. Unter `Umgebung` auf `Jetzt einrichten` klicken. Erwartet wird die Meldung `Windows-Umgebung ist bereit`.

## 3. Erkennung testen
Eine EXE- oder MSI-Datei über `Windows-Datei wählen` auswählen. Vor dem Start muss LiMaD einen Installationsplan mit Profil, Windows-Modus, Architektur und Abhängigkeiten anzeigen.

## 4. NWS-Test
Den originalen NWS-/New-World-Scheduler-Installer auswählen. Erwarteter Plan:

- Profil: `dotnet`
- Windows-Modus: `win11`
- Abhängigkeiten: `corefonts`, `dotnet48`

Die erstmalige Einrichtung von .NET 4.8 benötigt Internetzugang und kann mehrere Microsoft-Komponenten herunterladen.

## 5. Ergebnis prüfen
Nach Abschluss muss ein erkanntes Hauptprogramm angeboten werden. Nach Bestätigung erscheint es im GNOME-Menü und lässt sich dort starten.

## 6. Fehlerprotokolle
Installationsprotokoll:

`~/.local/share/limad-windows/install.log`

Diagnose starten:

`limad-wine-diagnose`

Diagnoseprotokoll:

`~/.local/share/limad-windows/diagnose.log`

## Technische Grenze
Programme mit Windows-Kerneltreibern, bestimmten DRM-/Anti-Cheat-Systemen oder zwingenden Windows-Diensten können weiterhin scheitern. Der Auto-Installer erkennt und automatisiert bekannte Laufzeitabhängigkeiten, ersetzt aber keinen echten Windows-Kernel.

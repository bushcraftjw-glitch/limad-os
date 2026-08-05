# LiMaD OS 2.7.0 RC1 – FIX35

FIX35 ist ein App-Rollup auf Grundlage von FIX32. Das Paket verändert keine `.github`-Dateien und keine GitHub-Workflow-Konfiguration.

## Integrierte Anwendungen

- LiMaD Study 6.2.1
- LiMaD Cut 1.1.3
- LiDrop 0.11.0-preview4
- Anycubic Slicer Next 1.3.96 (unverändert aus FIX32)
- Aerion Mail und die übrigen FIX32-Komponenten bleiben erhalten.

## Laufzeitkorrekturen

- Versionsbewusster App-Start verhindert, dass ein älteres Benutzer-Update eine neuere Systemversion überlagert.
- Aktuelle App-Payloads sind direkt im Systemabbild enthalten.
- LiDrop enthält die kompakte Oberfläche, Löschfunktionen und robustere Wiederaufnahme von Übertragungen.

## Optionale AirDrop-Kompatibilität

OWL und OpenDrop werden aus festgeschriebenen Upstream-Commits gebaut. Sie bleiben standardmäßig inaktiv. Eine Aktivierung erfolgt nur explizit, zeitlich begrenzt und nach Hardwareprüfung. Die aktive WLAN-Verbindung wird nie übernommen; eine separate freie, geeignete WLAN-Schnittstelle ist erforderlich.

## Sicherheit

- keine automatische AWDL-Aktivierung
- privilegierter Start nur über Polkit mit Administratorbestätigung
- automatische Abschaltung nach zehn Minuten
- Kontakte-Modus deaktiviert
- keine Änderung an GitHub-Workflows

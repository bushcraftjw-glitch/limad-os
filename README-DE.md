# LiMaD OS 2.8.0 RC2 Build 5 – LiNotes und Study-Wachtturm-Korrektur

## Aktueller Zusatzstand

- LiDrop 0.12.0-preview5 verbindet zwei LiMaD-OS-Rechner automatisch in beide Richtungen.
- Dateien werden direkt im lokalen Netzwerk übertragen und unter `Downloads/LiDrop` gespeichert.
- Avahi-Suche, Fortschrittsanzeige und SHA-256-Prüfung sind integriert.
- LiMaD Study 6.6.3, LiNotes preview2 und Windows-Programme 2.2.6 sind fest eingebaut.


Dieses Repository ist das vollständige GitHub-/ISO-Buildpaket für **RC2 Build 5**. Es basiert auf Build 4 und behält LiSave, Zen als deutschen Hauptbrowser, `Downloads/LiDrop`, LiLink, den vollständigen GStreamer-Unterbau und alle bisherigen LiMaD-Anwendungen bei.

## Neu in Build 5

### LiNotes 1.0.0-preview2

LiNotes ist eine native GTK4-Notizen-App im LiMaD-Design mit gelbem Post-it-Symbol.

Enthalten sind:

- Ordner, Schnellnotizen und „Alle Notizen“
- angepinnte Notizen
- Suche
- Listen- und Galerieansicht
- automatische Speicherung
- einfache Textformatierung und Checklisten
- Dateianhänge als normale, zugängliche Dateien
- Papierkorb mit Wiederherstellung
- Import aus TXT, Markdown, HTML, RTF und ENEX
- Export als TXT, Markdown oder HTML
- LiLink-Handoff für Notizen und Importdateien
- vollständige Aufnahme in LiSave
- offizieller Zugriff auf Apple Notizen über iCloud im Zen Browser

LiNotes verwendet lokal eine SQLite-Datenbank unter `~/.local/share/limad-notes`. Apple stellt keine allgemeine native Linux-Schnittstelle für eine direkte Zwei-Wege-Synchronisation seiner Notizen-Datenbank bereit. Deshalb wird keine unzuverlässige Apple-Synchronisation vorgetäuscht: bestehende Apple-Notizen werden offiziell über iCloud in Zen geöffnet; über die unterstützten Import- und Exportformate können Inhalte übertragen werden.

### LiMaD Study 6.6.3

- Wachtturm-Fragen sind kleiner als der Absatztext, grau dargestellt und klar abgesetzt.
- Die Fragennummer, einschließlich Bereiche wie `1–2.`, bleibt kräftig hervorgehoben.
- Abstände und Antwortfelder wurden an die mobile Referenz angenähert.
- **Zusammenkünfte → Wachtturm-Studium** ermittelt gezielt den Studienartikel der gewählten Woche.
- Die Auflösung berücksichtigt direkte Dokumentverknüpfungen, Datumsbereiche, Studienartikelnummer, Wochenposition und Fragenbestand.
- Ist die Zuordnung nicht direkt möglich, wird ein kontrollierter Fallback verwendet statt auf der Ausgabenübersicht stehenzubleiben.

### Abhängige Aktualisierungen

- LiSave **1.0.0-preview2** sichert LiNotes-Datenbank, Anhänge und Einstellungen.
- LiLink **1.0.0-preview3** kann LiNotes öffnen und Notizen beziehungsweise Importdateien übergeben.
- LiNotes ist in Dock, GNOME-Suche, App-Menü, LiMaD Update und First Login integriert.

## Bestehender Stand aus Build 4

- Zen Browser ist der deutsche Hauptbrowser.
- LiSave erstellt verschlüsselte, inkrementelle Wiederherstellungsbackups.
- LiDrop und LiLink empfangen dauerhaft unter `Downloads/LiDrop`.
- `Downloads/LiDrop` und `Dokumente/LiLink Sync` erscheinen in Dateien/Nautilus.
- GNOME Remote Desktop bildet den nativen Unterbau für LiLink.
- GStreamer einschließlich `python3-gstreamer1`, GTK4-Sink und PipeWire ist verbindlicher Bestandteil des Basis-Builds.
- Das Windows-Programme-Symbol ist über alle Größen und Skalierungen vereinheitlicht.

## Versionsstände

- LiMaD OS: 2.8.0 RC2 Build 5
- LiNotes: 1.0.0-preview2
- LiMaD Study: 6.6.3
- LiSave: 1.0.0-preview2
- LiLink: 1.0.0-preview3
- LiDrop: 0.12.0-preview5
- LiMaD Cut: 1.1.4
- Windows-Programme: 2.2.6
- LiMaD auf TV übertragen: 1.0.1

## Offline prüfen

```bash
bash tests/validate.sh
```

Der vollständige Sammellauf benötigt mehr als 20 Minuten. In der Erstellungsumgebung wurde er bis zur Laufzeitgrenze fehlerfrei ausgeführt; die danach offenen Tests wurden einzeln vollständig durchgeführt.

## GitHub-Build starten

Unter Linux:

```bash
chmod +x START-GITHUB-BUILD-LINUX.sh
./START-GITHUB-BUILD-LINUX.sh
```

Unter macOS kann `START-GITHUB-BUILD-MAC.command` gestartet werden.

## Testgrenze

Quellcode, Syntax, Datenbanklogik, Import, Anhänge, Papierkorb, App-Integration, LiSave, LiLink, aktuelle-Woche-Auflösung, Dock, Updater und alle bisherigen Offline-Regressionstests wurden geprüft. Nicht als real hardwaregetestet gelten der fertige GitHub-ISO-Build, eine echte JWPUB der betreffenden Woche, die visuelle Darstellung auf deinem Display, iCloud-Anmeldung sowie eine reale Clean-Install-Wiederherstellung.

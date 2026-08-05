# LiMaD OS 2.8.0 RC2 Build 5 – LiNotes & Study

Build 5 ergänzt LiMaD OS um die native Notizen-App **LiNotes** und korrigiert die Darstellung sowie die Wochenzuordnung im Wachtturm-Studium von LiMaD Study.

## Neu

### LiNotes 1.0.0-preview1

- native GTK4-App mit gelbem Post-it-Symbol
- Ordner, Schnellnotizen und angepinnte Notizen
- Suche, Listen- und Galerieansicht
- automatische Speicherung
- Checklisten und einfache Formatierung
- Dateianhänge als normale Dateien
- Papierkorb und Wiederherstellung
- Import: TXT, Markdown, HTML, RTF und ENEX
- Export: TXT, Markdown und HTML
- LiSave-Sicherung und LiLink-Handoff
- Apple Notizen offiziell über iCloud im Zen Browser öffnen

Eine direkte native Zwei-Wege-Synchronisation mit Apples interner Notizen-Datenbank wird nicht behauptet. Apple-Notizen bleiben über iCloud erreichbar; unterstützte Austauschformate können importiert werden.

### LiMaD Study 6.6.2

- kleinere und dezent graue Wachtturm-Fragen
- kräftig hervorgehobene Fragennummern wie `1–2.`
- verbesserte Abstände und Antwortfelder
- direkte Öffnung des Studienartikels der ausgewählten Woche
- robustere Zuordnung über Dokument-ID, Datumsbereich, Artikelnummer, Wochenposition und Fragenbestand

### Integration

- LiSave 1.0.0-preview2 sichert LiNotes vollständig.
- LiLink 1.0.0-preview3 unterstützt LiNotes-Handoff.
- LiNotes ist in Dock, First Login, GNOME-Suche und LiMaD Update enthalten.
- Alle Funktionen aus Build 4 bleiben erhalten.

## Versionen

- LiMaD OS 2.8.0 RC2 Build 5
- LiNotes 1.0.0-preview1
- LiMaD Study 6.6.2
- LiSave 1.0.0-preview2
- LiLink 1.0.0-preview3
- LiDrop 0.12.0-preview5
- LiMaD Cut 1.1.4
- Windows-Programme 2.2.5

## Teststatus

Bestanden wurden Syntax- und Strukturprüfungen, LiNotes-Datenbanktests, Ordner, Anpinnen, Anhänge, Papierkorb, HTML-/RTF-/ENEX-Import, LiSave- und LiLink-Integration, automatische Wachtturm-Wochenzuordnung sowie die gesamte bestehende LiMaD-Regressionstestbasis. Der lange Sammellauf wurde durch die Laufzeitgrenze der Erstellungsumgebung beendet; alle danach offenen Tests wurden separat ausgeführt und bestanden.

Reale Tests mit einer aktuellen installierten Wachtturm-Ausgabe, visueller Darstellung, iCloud-Anmeldung, Notebook/iMac, Clean Install und der von GitHub Actions erzeugten ISO bleiben erforderlich.

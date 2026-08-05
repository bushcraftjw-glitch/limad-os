# LiMaD OS 2.6.2 – Phase 3 Prüfung

## Enthalten

- grafischer Updater für LiMaD Cut, LiMaD Study, LiDrop und Anycubic Slicer Next
- automatische Suche nach `*.limad-update.zip` in Downloads und auf dem Schreibtisch
- Update-Aktion im Kontextmenü jeder unterstützten App
- SHA-256-Prüfung jeder Nutzlastdatei
- Schutz vor Pfadmanipulation, symbolischen Links, verschlüsselten ZIPs, doppelten Pfaden und ZIP-Bomben
- atomare Aktivierung im Benutzerprofil
- automatische Rückkehr auf die vorherige Version, wenn ein Installationsschritt fehlschlägt
- Schaltfläche zum Starten der aktualisierten App
- Schaltfläche zur Rückkehr auf die im Betriebssystem enthaltene Systemversion
- Benutzer-Timer zur lokalen Updatesuche alle sechs Stunden
- Protokoll unter `~/.local/state/limad-updater/updater.log`

## Test nach Installation

1. Eine passende Datei mit der Endung `.limad-update.zip` nach Downloads kopieren.
2. `LiMaD Updates` im Anwendungsmenü öffnen.
3. `Nach Updates suchen` anklicken.
4. Prüfen, ob App-Name und neue Version erkannt werden.
5. `Gefundenes Update installieren` anklicken.
6. Die App über `App starten` öffnen.
7. Updater erneut öffnen und `Systemversion` testen.

## Wichtige Grenze

Die automatische Prüfung sucht lokal nach bereits heruntergeladenen Update-Paketen. Ein Online-Updatekanal ist bewusst nicht eingetragen, solange keine verbindlichen öffentlichen Release-URLs für die einzelnen Apps festgelegt sind. Dadurch werden keine erfundenen oder instabilen Downloadadressen in das Betriebssystem eingebaut.

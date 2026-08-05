# LiDrop 0.12.0-preview5 – Hardwaretest zwischen zwei LiMaD-OS-Rechnern

## Vorbereitung

- Beide Rechner müssen im gleichen lokalen Netzwerk sein.
- LiDrop auf beiden Rechnern öffnen.
- Firewall-Regel für den vorhandenen LiDrop-Dienst muss aktiv sein.

## Kopplung

1. Auf Rechner B in LiDrop **Gerät verbinden** öffnen.
2. Den angezeigten sechsstelligen Code merken.
3. Auf Rechner A **Gerät verbinden → Rechner suchen** wählen.
4. Rechner B auswählen oder seine lokale Adresse eintragen.
5. Den Code von Rechner B eingeben und **Beide Rechner verbinden** wählen.
6. Prüfen, dass beide Rechner anschließend gegenseitig als LiMaD-OS-Ziel erscheinen.

## Dateiübertragung

1. Auf Rechner A Rechner B auswählen.
2. Eine kleine Datei, eine Datei über 16 MiB und mehrere Dateien gemeinsam senden.
3. Prüfen, dass der Fortschritt bis **Gesendet** läuft.
4. Auf Rechner B `Downloads/LiDrop` öffnen und Dateiname, Größe und Inhalt prüfen.
5. Den Test anschließend in Gegenrichtung wiederholen.

## Unterbrechung

1. Während einer großen Übertragung WLAN kurz trennen.
2. Prüfen, dass LiDrop einen verständlichen Fehler anzeigt und nicht hängen bleibt.
3. Datei erneut senden.

## Bereits automatisch geprüft

- bidirektionale Kopplung zweier isolierter LiDrop-Dienste
- direkter System-zu-System-Transfer über mehrere Datenblöcke
- automatische Speicherung in `Downloads/LiDrop`
- SHA-256-Übereinstimmung von Quelle und Ziel

## Noch real zu bestätigen

- automatische Avahi-Erkennung auf Notebook und iMac
- Firewall-Verhalten nach einer Neuinstallation
- Übertragung über reales WLAN und Ethernet
- Standby und Wiederaufnahme während einer Verbindung

# LiLink Zwei-Geräte-Hardwaretest

## Voraussetzungen

- zwei Geräte mit LiMaD OS 2.8.0 RC2 Build 3
- beide Geräte im gleichen privaten LAN/WLAN
- auf beiden Geräten ein angemeldeter GNOME-Benutzer

## Ablauf

1. Auf beiden Geräten `LiLink` öffnen.
2. Prüfen, ob beide Geräte automatisch erscheinen.
3. Auf Gerät A `Kopplungscode` wählen.
4. Auf Gerät B `Koppeln` wählen und den Code eingeben.
5. LiLink auf beiden Geräten schließen und erneut öffnen; Kopplung muss erhalten bleiben.
6. Auf Gerät B `Bildschirm übernehmen` wählen.
7. Bild, Maus, Tastatur, dynamische Auflösung und Zwischenablage prüfen.
8. Verbindung schließen; bei zuvor deaktivierter GNOME-Freigabe prüfen, ob LiLink sie wieder deaktiviert.
9. Eine Datei mit mindestens 100 MB senden und SHA-256/Empfang im Ordner `~/LiDrop` prüfen.
10. Handoff mit URL, LibreOffice-Datei, LiMaD Study und LiMaD Cut prüfen.
11. Deskflow starten und die Wayland-Portalabfrage lokal bestätigen; Bildschirmposition links/rechts prüfen.
12. Gerät entkoppeln und sicherstellen, dass alte Token keinen Zugriff mehr erlauben.

## Noch nicht als bestanden markieren, bevor

- RDP auf realem Notebook und iMac getestet wurde,
- Wayland-Eingabe über Deskflow auf beiden Geräten funktioniert,
- Schlaf-/Aufwachverhalten geprüft wurde,
- LAN und WLAN getestet wurden,
- ein Update über LiMaD Update und ein rpm-ostree-Systemupdate geprüft wurden.

## GStreamer-/Medientest

1. LiMaD Study öffnen und ein Video starten.
2. Prüfen, dass der separate native GTK4-/GStreamer-Player ohne Fehlermeldung öffnet.
3. Bild, Ton, Pause, Zeitleiste, Vollbild, Qualität und ±10 Sekunden testen.
4. Im Drei-Punkte-Menü die Decoderanzeige prüfen.
5. Eine H.264/AAC-MP4-Datei und eine reine Audiodatei testen.
6. Nach **LiMaD Update → System aktualisieren** erneut prüfen, dass der Player ohne manuelle Paketinstallation funktioniert.
7. Auf Notebook und iMac kontrollieren, dass die App **Windows-Programme** im Dock, App-Menü und Suchergebnis dasselbe Symbol zeigt.

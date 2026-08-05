# LiMaD OS 2.8.0 RC2 Build 4 – LiSave, Zen DE und LiDrop-Ordner

Build 4 ergänzt LiMaD OS um eine schlanke, verschlüsselte Wiederherstellungslösung. Persönliche Daten und Einstellungen werden tatsächlich gesichert; erneut verfügbare Programme werden nach einer sauberen Installation anhand des gespeicherten Manifests aus dem Internet installiert.

## Neu

### LiSave 1.0.0-preview1

- verschlüsselte, inkrementelle und deduplizierte Backups auf USB- oder Zweitlaufwerke
- Zen Browser vollständig mit Passwörtern, Lesezeichen, Verlauf, Sitzungen und Arbeitsbereichen
- LiMaD Mail mit Konten, Adressbüchern, lokalen Nachrichten und Einstellungen
- LiMaD Study einschließlich zusätzlichem Export über die eigene JWL-Library-Backupfunktion
- Dokumente, Desktop, `Downloads/LiDrop` und `Dokumente/LiLink Sync`
- Flatpaks und Windows-Programme als Wiederherstellungsplan
- ausgewählte GNOME-, Dock-, Nautilus- und LiMaD-Einstellungen
- tägliche Sicherung um 20:00 Uhr, sobald das konfigurierte Laufwerk verbunden ist
- optionale Sicherung vor LiMaD-Systemupdates
- 7 tägliche, 4 wöchentliche und 6 monatliche Sicherungsstände
- Erkennung eines angeschlossenen `.lisavebackup` nach einer Clean-Installation

### Zen Browser

- Hauptbrowser von LiMaD OS
- deutsche Oberfläche, Webseitenpräferenz und Rechtschreibprüfung
- als Standard für HTTP, HTTPS, HTML und XHTML gesetzt
- vollständige Berücksichtigung in LiSave

### LiDrop und LiLink

- LiDrop 0.12.0-preview4
- LiLink 1.0.0-preview2
- einheitlicher Empfangsordner `Downloads/LiDrop`
- der Ordner wird bei der Installation angelegt und dauerhaft in Dateien/Nautilus angezeigt
- alter Ordner `~/LiDrop` wird verlustfrei migriert
- `Dokumente/LiLink Sync` wird ebenfalls angelegt und als Favorit angezeigt

## Enthaltene Versionsstände

- LiMaD OS 2.8.0 RC2 Build 4
- LiSave 1.0.0-preview1
- LiLink 1.0.0-preview2
- LiDrop 0.12.0-preview4
- LiMaD Study 6.6.1
- LiMaD Cut 1.1.4
- Windows-Programme 2.2.5
- LiMaD auf TV übertragen 1.0.1

## Teststatus

Die Offline-Prüfung umfasst Python-, Shell-, JSON- und Desktop-Dateien, FIX22-Schutzbasis, Themes, Icons, First Login, Dock, Zen-DE-Konfiguration, LiDrop-Migration, LiSave-Backup und Wiederherstellung mit simuliertem Repository, LiLink-TLS-Kopplung, GStreamer, Study, Cut, Windows-Programme, Updater, Plymouth und ISO-Bauverkabelung.

Noch nicht real hardwaregetestet sind das Schreiben auf ein physisches USB-Laufwerk, eine vollständige Clean-Install-Wiederherstellung, echte RDP-/Deskflow-Verbindungen zwischen Notebook und iMac sowie der finale GitHub-Image-/ISO-Build.

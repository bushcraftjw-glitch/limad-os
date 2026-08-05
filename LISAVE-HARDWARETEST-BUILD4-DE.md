# LiSave-Hardwaretest – RC2 Build 4

## 1. Erstes Backup

1. USB-SSD oder zweites Laufwerk anschließen.
2. LiSave öffnen.
3. Ziellaufwerk auswählen und ein mindestens zehn Zeichen langes Backup-Passwort vergeben.
4. **Benötigte Backup-Größe analysieren** ausführen.
5. **Backup jetzt erstellen** wählen.
6. Danach **Backup prüfen** ausführen.

## 2. Inhalt kontrollieren

Prüfen, dass LiSave Zen, LiMaD Mail, LiMaD Study, Dokumente, `Downloads/LiDrop`, `Dokumente/LiLink Sync`, Windows-Programme und Einstellungen anzeigt. Das Repository selbst ist verschlüsselt; persönliche Dateien dürfen auf dem Laufwerk nicht im Klartext lesbar sein.

## 3. Automatik

1. Tägliche Sicherung und Sicherung vor Systemupdates aktivieren.
2. Laufwerk entfernen und einen Timerlauf abwarten: der Lauf muss übersprungen werden.
3. Laufwerk wieder anschließen und `systemctl --user start limad-save.service` ausführen.
4. In LiSave den neuen Sicherungsstand prüfen.

## 4. Clean-Install-Wiederherstellung

1. Vorher ein zusätzliches manuelles Backup wichtiger Einzeldateien anlegen.
2. LiMaD OS RC2 Build 4 sauber installieren.
3. Beim ersten Login das LiSave-Laufwerk angeschlossen lassen.
4. LiSave muss das `.lisavebackup` automatisch erkennen und öffnen.
5. Passwort eingeben und **Vorherigen Stand wiederherstellen** wählen.
6. Neu starten und Zen, Mail, Study, Dokumente, LiDrop, LiLink Sync, Dock und Programme prüfen.

## 5. Erwartete manuelle Nacharbeiten

- Hardwaregebundene Einstellungen wie Monitoranordnung prüfen.
- Konten mit abgelaufenen Anmeldesitzungen erneut anmelden.
- Windows-Programme mit Lizenzaktivierung oder interaktivem Installer abschließen.
- LiLink auf neuer Hardware aus Sicherheitsgründen neu koppeln.

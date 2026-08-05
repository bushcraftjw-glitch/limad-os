# LiMaD OS 2.7.0 RC1 – FIX36

FIX36 übernimmt den vollständig validierten FIX35-App-Stand und ergänzt Laufzeithärtung.

## Zusätzlich zu FIX35

- veraltete Benutzer-App-Payloads werden beim nächsten Login archiviert, nicht gelöscht
- LiDrop wird nach einem Versionswechsel kontrolliert neu gestartet und nur sein darstellungsbezogener Cache bereinigt
- App-Integritätsbericht unter `~/.local/state/limad/app-integrity.json`
- OWL und OpenDrop enden spätestens nach zehn Minuten, auch wenn der Benutzer-Timer ausfällt
- Startbegrenzung verhindert Dienstschleifen
- keine Änderung an `.github`, Build-Workflow oder GitHub-Zugangsdaten

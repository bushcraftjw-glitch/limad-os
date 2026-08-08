# LiSave 1.0.0-preview3

LiSave erstellt verschlüsselte, inkrementelle Wiederherstellungsbackups. Persönliche Daten und App-Zustände werden gesichert; installierbare Programme werden als Manifest erfasst und bei einer Wiederherstellung erneut aus ihren Quellen geladen.

Standardmäßig enthalten sind Zen Browser, LiMaD Mail, LiMaD Study einschließlich JWL-Library-Export, Dokumente, Downloads/LiDrop, Dokumente/LiLink Sync, Windows-Programme-Metadaten, Flatpak-Liste sowie ausgewählte GNOME- und LiMaD-Einstellungen. Große Wine-Prefixe sind optional.


## Änderung in preview3

Die Größenanalyse verwendet nun dieselben relevanten Ausschlussregeln wie das eigentliche Restic-Backup. Ausgeschlossene LiMaD-Study-Bereiche, Cache-Verzeichnisse und standardmäßig nicht gesicherte große Wine-Prefixe werden nicht mehr fälschlich zur angezeigten Sicherungsgröße addiert. Die Backup- und Restore-Logik selbst wurde nicht verändert.

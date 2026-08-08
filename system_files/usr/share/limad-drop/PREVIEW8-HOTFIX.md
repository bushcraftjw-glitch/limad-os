# LiDrop 0.12.0-preview8

Hotfix für die Dateiauswahl und uneingeschränkte Dateiübertragung.

- Entfernt den fehlerhaften HTML-Filter `accept="*/*"`, der auf einzelnen Browser-/Portal-Kombinationen einen leeren Dateidialog erzeugte.
- Ohne `accept` zeigt der Dateidialog wieder sämtliche Dateien in Downloads und anderen Ordnern an.
- Unbekannte und eigene Endungen wie `.jwpub` und `.jwpubx` bleiben erlaubt.
- Die Dateiübertragung bleibt binär (`application/octet-stream`), Originalname und vollständige Endung bleiben erhalten.
- PC → Handy, Handy → PC und PC → PC bleiben erhalten.

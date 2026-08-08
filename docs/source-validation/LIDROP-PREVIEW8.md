# LiDrop 0.12.0-preview8 – Quellenvalidierung

LiDrop 0.12.0-preview8 wurde aus dem bereitgestellten eigenständigen LiMaD-Updatepaket in LiMaD OS 3.0 Starter1 integriert.

- App-ID: `de.limad.Drop`
- Version: `0.12.0-preview8`
- Paketformat: `org.limad.app-update`, Formatversion 1
- Paket-SHA256: `81e446b9d1881c1bac10a52ff9404618c4fd9eb1fee61d35dc83db9691a83954`
- Interne `SHA256SUMS`: vollständig erfolgreich geprüft
- Eingebetteter Zielpfad: `/usr/share/limad-drop`
- Eigenständiges Updatepaket: `updates/LiDrop-0.12.0-preview8.limad-update.zip`

Der Preview8-Hotfix entfernt den fehlerhaften HTML-Dateifilter `accept="*/*"`, sodass wieder sämtliche Dateien auswählbar sind. Unbekannte bzw. eigene Dateiendungen wie `.jwpub` und `.jwpubx` bleiben erlaubt. Die Dateiübertragung bleibt binär und behält Originalnamen sowie vollständige Endung bei.

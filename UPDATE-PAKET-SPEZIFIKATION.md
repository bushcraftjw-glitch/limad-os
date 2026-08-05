# LiMaD App-Update-Pakete

LiMaD OS 2.7.0 RC1 FIX11 enthält die grafische Anwendung **LiMaD Updates**. Sie installiert Aktualisierungen für LiMaD Cut, LiMaD Study, LiDrop, LiMaD Bildschirmfreigabe und Anycubic Slicer Next ohne Terminal und ohne Änderung des unveränderlichen Basissystems.

## Bedienung

- Eine passende Datei mit der Endung `.limad-update.zip` in Downloads oder auf dem Schreibtisch speichern.
- **LiMaD Updates** öffnen. Die Anwendung sucht beim Start automatisch nach neueren Paketen.
- Alternativ die Datei doppelklicken oder im Kontextmenü der App **Nach Updates suchen** wählen.
- **Systemversion** entfernt nur das Benutzer-Update und aktiviert wieder die im Betriebssystem enthaltene Fassung.
- **App starten** öffnet die gerade aktive Fassung direkt aus dem Updater.

Ein Benutzer-Timer durchsucht die lokalen Updateordner alle sechs Stunden und meldet neu gefundene Pakete. Es erfolgt kein automatischer Download aus dem Internet, solange keine verbindlichen öffentlichen Release-Adressen für die Apps festgelegt sind.

Die Aktualisierung wird pro Benutzer unter `~/.local/share/limad-updater/` installiert. Das ZIP wird vollständig geprüft und erst danach atomar aktiviert. Scheitert ein Nachinstallationsschritt, wird automatisch der vorherige Stand wiederhergestellt. Das Protokoll liegt unter `~/.local/state/limad-updater/updater.log`.

## Verbindlicher ZIP-Aufbau

```text
Programmname-VERSION.limad-update.zip
├── limad-update.json
├── SHA256SUMS
└── payload/
    └── vollständiger Inhalt des jeweiligen App-Stammordners
```

`limad-update.json`:

```json
{
  "format": "org.limad.app-update",
  "format_version": 1,
  "app_id": "de.limad.Study",
  "name": "LiMaD Study",
  "version": "6.1.0-preview18"
}
```

| Programm | App-ID | Inhalt unter `payload/` |
|---|---|---|
| LiMaD Cut | `de.limad.Cut` | Inhalt von `/usr/share/limad-cut/`, einschließlich `VERSION` und `native_shell.py` |
| LiMaD Study | `de.limad.Study` | Inhalt von `/usr/share/limad-study/`, einschließlich `VERSION`, `src/` und `web/` |
| LiDrop | `de.limad.Drop` | Inhalt von `/usr/share/limad-drop/`, einschließlich `VERSION`, `limad_dropd.py` und `shell.py` |
| LiMaD Bildschirmfreigabe | `de.limad.ScreenShare` | Inhalt von `/usr/share/limad-screen-share/`, einschließlich `VERSION` und `app.py`; setzt LiMaD OS Build 2 oder neuer voraus |
| Anycubic Slicer Next | `de.limad.AnycubicSlicerNext` | Inhalt von `/usr/lib/limad/apps/anycubic-slicer-next/` |

`SHA256SUMS` muss jede Datei unter `payload/` exakt einmal enthalten. Zusätzliche oder fehlende Einträge werden abgelehnt. Ebenso abgelehnt werden absolute Pfade, `..`, symbolische Links, verschlüsselte Dateien, doppelte Pfade und auffällige ZIP-Kompressionsverhältnisse.

## Paket erstellen

```bash
python3 tools/build-limad-update.py \
  --app-id de.limad.Study \
  --version 6.1.0-preview18 \
  --payload app \
  --output LiMaD-Study-6.1.0-preview18.limad-update.zip
```

Für künftige Übergaben werden die fünf updatefähigen Programme jeweils als eigenständige `.limad-update.zip` geliefert. Ein komplettes OS-Image ist für reine App-Updates nicht erforderlich.

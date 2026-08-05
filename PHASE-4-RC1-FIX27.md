# LiMaD OS 2.7.0 RC1 – FIX27

## Grundlage

FIX27 wurde direkt aus `LiMaD-OS-2.7.0-RC1-FIX22-GNOME-Anaconda-Label-Path-Repair.zip` aufgebaut. Die geprüfte Quell-ZIP besitzt die SHA-256-Prüfsumme:

```text
56e2e53416a772b7753e7af45d0fbc969bea61e372ae657fc599cc04ea6b4a5e
```

## Unveränderte FIX22-Eigenschaften

- Fensterknöpfe links: `close,maximize,minimize:`
- farbige MacTahoe-Fensterknöpfe
- GTK-, Shell- und Icon-Theme
- drei LiMaD-Wallpaper und bestehendes Standard-Wallpaper
- Dock-Position, Größe, Transparenz und Verhalten
- LiMaD Cut, Study, LiDrop und Anycubic-Payloads
- ISO-/EFI-/Anaconda-Reparaturen aus FIX22

## Gezielte Ergänzungen

- separater violetter Plymouth-Spinner mit zwölf Frames
- transparentes LiMaD-Systemlogo und feines Menü-L in allen benötigten Größen
- Logo-Menu-Schema mit LiMaD-Standard und Schutz gegen doppelte Schema-IDs
- sichtbares LiMaD-Branding für Systeminfo sowie Installer-Fallbackpfade
- abgesicherte Dock-Favoriten für Cut, LiDrop, Windows und Anycubic
- Windows-Auto-Installer mit Rezept- und Abhängigkeitsplanung
- Buildrevision `gnome42-phase4-fix27`

## Schutzmaßnahmen

- Offline-Prüfung sämtlicher Shell-, Python-, JSON-, Branding-, Wine-, GNOME- und ISO-Pfade
- echte First-Login-Simulation mit bestehender Favoritenliste
- synthetische Konflikttests für Upstream-Wallpaper und Fensterknöpfe
- byte- und rechtegenauer Vergleich von 398 geschützten Dateien mit FIX22
- Acceptance-Prüfung während des Image-Builds
- erneute Prüfung im committed OSTree-Container

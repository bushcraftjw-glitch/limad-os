# LiMaD OS 2.7.0 RC1 – FIX49

FIX49 übernimmt den auf echter Hardware bestätigten Plymouth-Ablauf und macht
LiMaD Klang unabhängig davon, ob EasyEffects seinen lokalen Server direkt am
Standardpfad bereitstellt.

## Bootscreen

- Das Theme bleibt `limad`; `dracut --force` wird nirgends verwendet.
- Auf dem installierten OSTree-System läuft einmalig und transaktional:
  `rpm-ostree initramfs --enable`.
- Die OSTree-Erkennung verwendet den Marker `/run/ostree-booted` mit `-e`.
- Der Dienst startet 45 Sekunden nach dem ersten installierten Boot und wartet
  bei einer belegten rpm-ostree-Transaktion automatisch.
- `rhgb quiet` wird nur ergänzt, wenn einer der Parameter tatsächlich fehlt.
- Der Erfolgsmarker wird erst nach erfolgreicher rpm-ostree-Transaktion gesetzt.
- Eine Desktopmeldung fordert genau einen weiteren Neustart an. Es erfolgt kein
  unaufgeforderter automatischer Neustart.
- Laufzeitprotokoll:
  `/var/lib/limad/plymouth-initramfs-fix49.log`.

Wichtig: Der allererste Start direkt nach der Installation kann noch die vom
Basisimage gelieferte initramfs verwenden. Nach der automatisch vorbereiteten
Deployment-Version und einem weiteren Neustart wird das LiMaD-Theme geladen.

## LiMaD Klang / EasyEffects

- EasyEffects wird mit der aktuellen Qt/Kirigami-Option `--hide-window`
  gestartet; der veraltete GTK-Schalter `--gapplication-service` wurde entfernt.
- LiMaD Klang sucht `EasyEffectsServer` am dokumentierten Standardpfad sowie in
  Flatpak-Unterordnern des Benutzer-Runtime-Verzeichnisses.
- Der gefundene Socket muss dem angemeldeten Benutzer gehören und ein echter
  Unix-Socket sein.
- Direkte Live-Steuerung bleibt der bevorzugte Modus.
- Falls der lokale Server fehlt oder die Equalizer-API nicht antwortet, wechselt
  LiMaD Klang automatisch in den Preset-Kompatibilitätsmodus:
  - Bass, Mitten und Höhen werden in das eigene LiMaD-Preset geschrieben.
  - Das Preset wird sofort über die EasyEffects-Kommandozeile neu geladen.
  - Der Ein-/Ausschalter verwendet den EasyEffects-Bypass-Befehl.
- Der Preset-Installer überschreibt geänderte LiMaD-Reglerwerte nicht mehr bei
  jedem Login. Eine bewusste Rücksetzung bleibt über `--reset` möglich.

## Versionsstand

- Produktversion: `2.7.0-rc1`
- Buildrevision: `gnome42-phase4-fix49`
- First-Login-Marker: `2.7.0-rc1-fix49`
- Flatpak-Marker: `default-flatpaks-fix49.done`
- Plymouth-Marker: `plymouth-initramfs-fix49.done`

# LiMaD OS 2.7.0 RC1 FIX9

FIX9 korrigiert die drei verbleibenden Branding-Blocker vor dem ersten echten ISO-Build.

## Logo Menu unter GNOME 50

- Version auf `v24.8_270626` angehoben.
- Der Build liest die echte `metadata.json` des heruntergeladenen Tags.
- Die Installation bricht ab, wenn die dort deklarierte `shell-version` die im Basisabbild installierte GNOME-Shell-Hauptversion nicht enthält.
- Die endgültige Image-Prüfung wiederholt diese Kompatibilitätskontrolle.

## GDM im Bazzite-GNOME-Abbild

- `bazzite-gnome` wird ausdrücklich als GNOME-Basis verlangt.
- `gdm.service` wird zwingend aktiviert und als `display-manager.service` gesetzt.
- Ein anderer aktiver Display-Manager beendet den Build mit einem Fehler.
- Der während des OSTree-Builds nicht beschreibbare `/root`-Symlink wird nur für den GDM-Theme-Schritt vorübergehend funktionsfähig gemacht.
- MacTahoe erhält das tatsächliche LiMaD-Standard-Wallpaper als GDM-Hintergrund.
- Der Build vergleicht den Hash der GNOME-Shell-GDM-Ressource vor und nach der Änderung. Ein unverändertes Ergebnis gilt als Fehler.
- Ergebnis und Hashwerte werden in `/usr/share/limad/gdm-branding.env` festgehalten und vor sowie nach dem OSTree-Commit erneut geprüft.

## ISO-Volume-ID und Startparameter

- Die feste alte Kennung `LIMAD_OS_260` wurde entfernt.
- Für `2.7.0-rc1` wird dynamisch `LIMAD_OS_270_RC1` erzeugt.
- Sichtbare Menütexte werden getrennt von Kernel-Startparametern bearbeitet.
- `inst.stage2=hd:LABEL=`, `root=live:CDLABEL=`, `root=live:LABEL=`, `live:CDLABEL=`, `--label` und `--fs-label` werden auf dieselbe Volume-ID gesetzt.
- Die ISO-Prüfung vergleicht die tatsächliche Volume-ID mit allen gefundenen Labelreferenzen.

## Versions- und Testhärtung

- Buildrevision: `gnome39-phase4-fix9`.
- GHCR-Tags enthalten `GITHUB_RUN_NUMBER` und `GITHUB_RUN_ATTEMPT`.
- First-Login-Migrationsmarker: `2.7.0-rc1-fix9`.
- Neuer synthetischer Test für Bootmenü, Anaconda-Labelreferenzen, GDM-Enforcement und GNOME-50-Logo-Menu-Prüfung.
- Python-Dateien und Python-Heredocs in Shellskripten werden syntaktisch geprüft.

## Noch nicht bestätigt

- echter GitHub-Container-Build
- echter `bootc-image-builder`-ISO-Lauf
- Boot und Neuinstallation auf Hardware
- visuelle Bestätigung von GDM, Plymouth, Installer, Menülogo und Standardhintergrund

Der Paketstatus bleibt deshalb `QUELLCODE BESTÄTIGT` und nicht `STABLE`.

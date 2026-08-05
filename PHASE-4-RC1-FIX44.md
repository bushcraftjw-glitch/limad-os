# LiMaD OS 2.7.0 RC1 – FIX44

FIX44 bündelt die drei gezielt angeforderten Korrekturen, ohne die funktionierende AMD-/Bazzite-Basis, bestehende LiMaD-Apps oder die GitHub-Workflows auszutauschen.

## LiMaD-Installer

- Anaconda WebUI und GTK-Fallback erhalten ein gemeinsames dunkles LiMaD-Design.
- Verwendet ausschließlich das vorhandene Original-Logo `LiMaD-System-Logo-512.png`; es wird nicht nachgezeichnet.
- Dunkle Schwarz-/Violett-/Blau-Flächen, LiMaD-Wellenhintergrund, violette Auswahlzustände, Schaltflächen und Fortschrittsanzeigen.
- Branding wird in die Anaconda-, Cockpit- und Fedora-/Bazzite-Fallbackpfade des finalen `product.img` geschrieben.
- Boot- und EFI-Nachbearbeitung aus FIX22–FIX43 bleibt unverändert; nur `tools/brand-installer-iso.sh` besitzt dafür einen dokumentierten FIX44-Override im Schutzmanifest.

## Plymouth-Bootscreen

- LiMaD-Plymouth bleibt als Standardthema gesetzt.
- Ein einmaliger, verzögerter Systemdienst ergänzt `rhgb quiet` und aktiviert lokale initramfs-Erzeugung über `rpm-ostree initramfs --enable`.
- Kein direkter `dracut --force`-Aufruf im Image-Build.
- Erfolgsmarker: `/var/lib/limad/plymouth-initramfs-fix44.done`.
- Nach der einmaligen Deployment-Erzeugung ist ein weiterer Neustart nötig, damit der neue initramfs-Stand verwendet wird.

## LiMaD Klang / EasyEffects

- Benutzerpreset wird zusätzlich in den aktuellen EasyEffects-Datenpfad unter `~/.var/app/com.github.wwmm.easyeffects/data/easyeffects/output/` installiert.
- Vorhandene ältere Config-Pfade werden als Kompatibilitätsfallback weiterhin gepflegt.
- LiMaD Klang unterscheidet Installation, Programmversion, laufenden Prozess, echten lokalen Socket und geladenes Preset.
- Mindestversion EasyEffects 8.2.8 für vollständige externe Equalizer-Steuerung.
- Bass, Mitten und Höhen werden live über den lokalen `EasyEffectsServer` gesetzt.
- Preset-Laden wird über `get_last_loaded_preset:output` kontrolliert.
- Ein vorhandenes EasyEffects-Flatpak wird beim App-Setup aktualisiert.

## Versionsstand

- Produktversion: `2.7.0-rc1`
- Buildrevision: `gnome42-phase4-fix44`
- First-Login-Marker: `2.7.0-rc1-fix44`
- Flatpak-Marker: `default-flatpaks-fix44.done`

## Schutz und Prüfung

- Beide Dateien unter `.github/workflows/` sind gegenüber FIX43 bytegleich.
- Der vollständige lokale Testlauf umfasst 70 Shell-/Python-Prüfpfade plus den neuen FIX44-Regressionstest.
- Das finale ZIP wird dreimal in frische Ordner entpackt und dort mit `tests/validate.sh` geprüft.
- Jede Runde kontrolliert zusätzlich, dass keine `__pycache__`, `.pyc`, `.pyo`, `.cache` oder `node_modules` enthalten sind.

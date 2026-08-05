# LiMaD OS 2.7.0-rc1 FIX31

## Standard-Apps und Dock

FIX31 installiert beim ersten GNOME-Login automatisch drei Benutzer-Flatpaks aus Flathub:

- Zen Browser (`app.zen_browser.zen`, mit Rückfall auf die frühere ID)
- Zoom (`us.zoom.Zoom`)
- Bazaar (`io.github.kolunmi.Bazaar`)

Die Installation läuft im Benutzerkonto und verändert das unveränderliche bootc-/OSTree-System nicht. Bei fehlendem Netzwerk wird sie beim nächsten Login erneut versucht.

Die Startreihenfolge im Dock ist fest: Zen, LiMaDCut, Study, LiDrop, Windows, LiMaD Updates, Anycubic, Zoom, Bazaar, Terminal und Dateien. Danach folgen der Dash-to-Dock-Papierkorb und „Anwendungen anzeigen“.

FIX30s Verbot eines direkten `dracut --force` bleibt unverändert bestehen.

## Schutzumfang

Die zwei für FIX31 ausdrücklich geänderten Dateien `build_files/build.sh` und der zentrale GNOME-Default-Override wurden aus der unveränderten FIX22-Schutzliste genommen. Alle übrigen 396 geschützten Dateien bleiben weiterhin per SHA-256 und Dateimodus abgesichert.

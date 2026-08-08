# LiMaD OS 3.0 starter1-fix9 – Live-Boot-/Installer-Stabilität

Auslöser war der erste reale Hardwaretest von FIX8: Die GitHub-ISO wurde erfolgreich gebaut und hochgeladen, der Live-Start auf dem iMac zeigte kurz Ubuntu/Plymouth und blieb danach vor dem grafischen Live-Desktop schwarz.

FIX9 ändert deshalb nicht nur einen einzelnen GDM-Test, sondern den ISO-Layer-Aufbau:

- `minimal.squashfs` bleibt die unveränderte Ubuntu-Basis.
- `minimal.standard.squashfs` wird weiterhin als installiertes Zielsystem angepasst.
- `minimal.standard.live.squashfs` wird nun zusätzlich extrahiert, mit relevanten Änderungen des Standard-Layers abgeglichen und neu gebaut.
- Live-spezifische Paketdaten, Cloud-Seed und Ubuntu-Desktop-Installer-Dateien werden vom Abgleich ausgeschlossen.
- Die Live-Session erhält explizit die originale Ubuntu-GDM-GResource zurück; das installierte System behält das LiMaD-GDM-Branding.
- Beide GNOME/GDM-GResources werden vor dem Packen mit `gresource list` auf Lesbarkeit geprüft.
- Der Ubuntu-Desktop-Installer-Service muss im zusammengesetzten Live-RootFS vorhanden sein.
- GRUB wird für 10 Sekunden sichtbar gemacht.
- Ein eigener `LiMaD OS - Safe Graphics`-Eintrag mit `nomodeset` wird garantiert.
- Das fertige ISO wird nach dem Schreiben erneut auf beide SquashFS-Layer und die GRUB-Einträge geprüft.

Der Stand ist erst nach erfolgreichem GitHub-Build und erneutem Hardwaretest als live-boot-validiert zu betrachten.

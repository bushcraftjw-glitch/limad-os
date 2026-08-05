# LiMaD OS 2.6.1 – Phase 2 Prüfung

## A. Systemupdate

Der GitHub-Build erzeugt die ISO nur noch, wenn `ghcr.io/<Besitzer>/limad-os-gnome-fix16:latest` ohne Anmeldung gelesen werden kann.

Beim ersten Lauf kann der Build nach dem Push absichtlich stoppen. Dann auf GitHub:

1. Profil öffnen.
2. **Packages** öffnen.
3. Paket **limad-os-gnome-fix16** öffnen.
4. **Package settings** wählen.
5. **Change visibility** auf **Public** stellen.
6. Den fehlgeschlagenen GitHub-Job erneut starten.

Nach der Installation im Menü **LiMaD System aktualisieren** starten. Ein erfolgreicher Test endet ohne `unauthorized`.

## B. NWS Desktop

1. **Windows-Programme** öffnen.
2. `NWS-Desktop-Setup_8.2_1461.exe` wählen.
3. LiMaD erkennt NWS automatisch.
4. Windows-11-Modus, Core Fonts und .NET Framework 4.8 werden automatisch vorbereitet.
5. Danach startet der NWS-Installer.
6. Nach Abschluss wird höchstens 120 Sekunden auf Wine-Hintergrundprozesse gewartet. Die Oberfläche bleibt nicht mehr dauerhaft bei `wineserver -w` hängen.
7. Das erkannte NWS-Programm zum GNOME-Menü hinzufügen und starten.

Protokoll: `~/.local/share/limad-windows/install.log`

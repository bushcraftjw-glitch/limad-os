# LiMaD OS 2.7.0 RC1 – FIX47

FIX47 behebt die drei Laufzeitprobleme aus dem Test von FIX46, ohne die
funktionierende Bazzite-/AMD-Basis, die Apps oder die GitHub-Workflows zu
ersetzen.

## LiMaD Klang

- Die nicht existente Option `flatpak info --show-version` wurde entfernt.
- EasyEffects wird über `flatpak list --app --columns=application,version`
  erkannt; `flatpak info` dient nur noch als Fallback.
- Eine nicht gemeldete Versionsnummer wird nicht mehr als `0.0.0` behandelt.
- Nach dem Verbinden wird die lokale EasyEffects-API mit einem echten
  `get_property`-Aufruf geprüft.
- Nach jeder Änderung liest LiMaD Klang Bass- und Höhenwert zurück. Erst danach
  wird die Änderung als übernommen angezeigt.
- Die Mindestversion bleibt EasyEffects 8.2.8.

## Installer-Branding

- Die aktuelle Anaconda WebUI erhält LiMaD-Cockpit-Branding für die möglichen
  Laufzeit-IDs `limad`, `bazzite` und `fedora`.
- Das CSS verwendet den Anaconda-Wrapper `.anaconda` sowie PatternFly-5- und
  PatternFly-6-Klassen.
- Für den GTK-Fallback werden die dokumentierten Klassen `.logo-sidebar`,
  `.logo`, `.product-logo` und `AnacondaSpokeWindow #nav-box` verwendet.
- Anacondas vollständiges Basis-Stylesheet wird nicht mehr ersetzt.
- Das schmale LiMaD-Overlay wird unter den möglichen Produktnamen
  `limad.css`, `limad-os.css`, `bazzite.css` und `fedora.css` ausgeliefert.
- Das fertig erzeugte `product.img` wird vor dem ISO-Umbau mit `unsquashfs`
  auf alle Branding-Dateien geprüft.

## Plymouth-Bootscreen

- Kein `dracut --force` im Container-Build oder auf dem laufenden System.
- `rpm-ostree kargs` und `rpm-ostree initramfs --enable` laufen ausschließlich
  auf dem installierten OSTree-System.
- Bei einer belegten rpm-ostree-Transaktion wird kontrolliert wiederholt.
- Der Erfolgsmarker wird erst nach beiden erfolgreichen Transaktionen gesetzt.
- Eine Desktop-Benachrichtigung fordert den einmal nötigen Neustart an.
- Nach dem Neustart wird die Erinnerung automatisch entfernt.
- Live-/Installer-Umgebungen werden durch Kernel- und Dateisystembedingungen
  ausgeschlossen.

## Sicherer GitHub-Upload

- Standardziel: `bushcraftjw-glitch/limad-os`.
- Vor Commit und Upload wird über die GitHub-API geprüft, ob der Token wirklich
  Schreibzugriff auf das Ziel-Repository besitzt.
- Ein vorhandenes Repository wird niemals automatisch gelöscht. Die frühere
  `delete_repo`-Funktion wurde vollständig entfernt.
- Die Workflowdateien bleiben gegenüber FIX46 bytegleich.

## Aktive Versionsmarker

- Produktversion: `2.7.0-rc1`
- Buildrevision: `gnome42-phase4-fix47`
- First Login: `2.7.0-rc1-fix47`
- Flatpak-Status: `default-flatpaks-fix47.done`
- Plymouth-Status: `plymouth-initramfs-fix47.done`

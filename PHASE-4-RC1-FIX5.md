# LiMaD OS 2.7.0 RC1 – Fix 5

Löst die zwei Punkte aus FIX4, die dort bewusst offen gelassen wurden ("nicht
blind raten"), jetzt mit Web-Recherche statt Vermutung.

## 1. `gnome-shell-extension-logo-menu` fehlt in Fedora 44 – bestätigt, nicht vermutet

https://packages.fedoraproject.org/pkgs/gnome-shell-extension-logo-menu/gnome-shell-extension-logo-menu/
zeigt es: Das Paket ist **nur für Fedora Rawhide (24.8-2.fc45) gebaut**, nicht
für Fedora 44 stable. Kein Tippfehler, keine Umbenennung – es existiert dort
schlicht noch nicht.

**Fix:** neuer Build-Schritt `build_files/45-logomenu-extension.sh` installiert
die Extension system-weit direkt aus einem gepinnten GitHub-Release
(`v23.6_190125`, https://github.com/Aryan20/Logomenu/releases), genau nach der
im Upstream-README dokumentierten manuellen Installationsmethode, nur auf den
System- statt den Benutzerpfad umgelegt. Mit Fail-Fast-Prüfungen (uuid in
metadata.json, extension.js vorhanden, Schema-Kompilierung falls vorhanden).
`gnome-shell-extension-logo-menu` aus `10-packages.sh` entfernt,
`test-gnome-defaults.sh` und `build.sh` entsprechend angepasst.

**Unsicherheit, die ich nicht wegtesten kann:** Ich kenne den exakten
Asset-Dateinamen des Release-Zips nicht mit Sicherheit (aus der Makefile
abgeleitet: `logomenu@aryan_k.shell-extension.zip`) und konnte die URL nicht
selbst herunterladen (kein Netzwerkzugriff im Ausführungscontainer). Der
Build-Schritt bricht mit einer klaren FATAL-Meldung samt Link ab, falls die
URL falsch ist, statt still zu scheitern – das nächste GitHub-Build-Log zeigt
sofort, ob die URL stimmt.

`gnome-themes-extra` bleibt weiterhin unbehoben (niedrige Priorität: liefert
nur Legacy-GTK2-Theme-Assets, kein sichtbarer Effekt auf GTK3/4/libadwaita).

## 2. GDM-Theme "'-g' needs a root privilege" trotz Root-Build

Der obere Aufruf-Pfad `-g|--gdm` in `tweaks.sh` ruft intern eine
`full_sudo()`-Hilfsfunktion auf (Quelle: `libs/lib-core.sh` im
MacTahoe-GTK-Theme-Repository, https://github.com/vinceliuice/MacTahoe-gtk-theme).
Diese Art Hilfsfunktion prüft typischerweise nicht nur `EUID==0`, sondern
erwartet zusätzlich einen echten `sudo`-Aufruf (`SUDO_USER`/`SUDO_UID`
gesetzt), weil sie wissen muss, wessen Home-Verzeichnis sie bespielen soll.
Im Container läuft der Build zwar als root, aber nie über `sudo` – diese
Variablen sind leer.

**Fix:** `SUDO_USER=root SUDO_UID=0` vor dem `tweaks.sh -g`-Aufruf gesetzt,
genau das Muster, das ein echter `sudo`-Aufruf hinterlassen würde. Bewusst
minimal und leicht rückgängig zu machen.

**Unsicherheit:** Ich habe `lib-core.sh` selbst nicht einsehen können (wird
erst zur Build-Zeit geklont), daher ist das eine begründete, aber nicht
quellcodebestätigte Diagnose. Schlägt es weiterhin fehl, bleibt der bereits
vorhandene Auffangmechanismus (`WARNING: GDM theming failed, login screen
stays default`) aktiv – der Build bricht dadurch so oder so nicht ab.

## Erneut geprüft
- `tests/validate.sh` läuft auf frischer, unberührter Kopie komplett grün
  durch (21 statt 20 Prüfungen wären zu erwarten gewesen, tatsächlich bleibt
  es bei denselben 20 Prüfungen plus einer erweiterten Extension-Prüfung
  innerhalb von `test-gnome-defaults.sh` – kein separater neuer Testeintrag,
  da es sich um eine Ergänzung einer bestehenden Prüfung handelt).
- Alle Bash-Skripte unabhängig mit `bash -n` geprüft.

Nicht behauptet: dass diese beiden Punkte den nächsten GitHub-Build
tatsächlich zum Laufen bringen – nur der vorherige, tatsächlich bestätigte
Fehler (Wallpaper-Override, `find`-Syntax) ist bewiesen behoben. Das hier ist
die bestmögliche Korrektur ohne Zugriff auf einen echten Build-Lauf oder das
`lib-core.sh`-Quellskript. Der nächste Build-Log ist der eigentliche Beweis.

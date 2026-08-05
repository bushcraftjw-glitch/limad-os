# LiMaD OS 2.7.0 RC1 – Fix 4

Grundlage: der erste echte GitHub-Actions-Build-Log (nicht nur Offline-Validierung).
Zwei der vier dort sichtbaren Probleme sind mit Quellzugriff eindeutig behebbar und
wurden hier behoben. Zwei bleiben offen, weil ihre eigentliche Ursache außerhalb
dieses Pakets liegt (siehe unten) und ein Rateversuch das Risiko birgt, das
Symptom nur zu verschleiern statt es zu beheben.

## Behoben

1. **`tools`-losgelöster Syntaxfehler in `build_files/50-gnome-defaults.sh`**
   Ein literales `\n`-Zeichen (statt eines echten Zeilenumbruchs) im `find`-Aufruf
   für die Bazzite-Logo-Ersetzung führte zu `find: paths must precede expression:
   'n'` und damit zu `0 built-in Bazzite Logo Menu asset(s) replaced`. Behoben
   durch einen echten Backslash-Zeilenumbruch.

2. **Wallpaper-Default verliert gegen das Basis-Image**
   `96-limad-wallpaper.gschema.override` verlor beim `glib-compile-schemas`-Lauf
   gegen eine alphabetisch später sortierte Override-Datei aus dem Bazzite-
   Basisimage (Ziffern sortieren vor Buchstaben in ASCII). Ergebnis im echten
   Build: `FATAL: default wallpaper is file:///usr/share/backgrounds/
   convergence-dynamic.xml, expected .../LiMaD-Wallpaper-02-...`.
   Datei umbenannt zu `zz-limad-wallpaper.gschema.override`, damit sie garantiert
   zuletzt angewendet wird. Alle Referenzen (Build-Skript, `test-gnome-defaults.sh`,
   `90-verify.sh`) mit aktualisiert.

3. **Defensive Ergänzung (kein Build-Blocker, aber ein stiller Fehler):**
   Wenn ein Shell-Extension-Paket (z. B. `gnome-shell-extension-logo-menu`) im
   echten Build nicht installierbar ist, blieb es bisher trotzdem in
   `enabled-extensions` gelistet – GNOME zeigt dann eine tote Referenz, ohne dass
   der Build das meldet. `50-gnome-defaults.sh` prüft jetzt für alle vier
   LiMaD-Extensions, ob das Verzeichnis unter
   `/usr/share/gnome-shell/extensions/` tatsächlich existiert, und entfernt
   fehlende Einträge automatisch aus der Standardkonfiguration, statt sie
   stillschweigend stehen zu lassen.

## Bewusst NICHT (blind) gefixt

4. **`gnome-shell-extension-logo-menu` und `gnome-themes-extra` werden von
   `dnf` als "package not available" übersprungen.**
   Das ist kein Fehler in diesem Paket, sondern ein Fedora-44-Repository-Zustand
   zum Build-Zeitpunkt (22.07.2026) – möglicherweise wurde das Paket umbenannt,
   entfernt oder liegt jetzt nur noch bei extensions.gnome.org / COPR. Ich habe
   dafür Punkt 3 als Sicherheitsnetz ergänzt, aber den eigentlichen Paketnamen
   nicht geraten ersetzt, weil ein falscher Name den Fehler nur verschleiern
   würde. **Nächster Schritt:** im GitHub-Workflow `dnf5 repoquery
   gnome-shell-extension-logo-menu gnome-themes-extra` laufen lassen bzw. auf
   https://packages.fedoraproject.org nachsehen, welcher Name/welches Repo diese
   Pakete unter Fedora 44 aktuell führt.

5. **GDM-Theme schlägt mit `'-g' needs a root privilege` fehl, obwohl der Build
   als root läuft.**
   Das Skript `tweaks.sh` wird nicht in diesem Paket mitgeliefert (es wird live
   vom MacTahoe-Repository geklont), daher kann die eigentliche Root-Prüfung
   dieses Skripts hier nicht eingesehen und gezielt gepatcht werden. Vermutung:
   einer der zu Beginn des Builds installierten Kompatibilitäts-"Shims" (sudo,
   logname, ...) lässt `tweaks.sh`s internen Root-Check fehlschlagen. **Nächster
   Schritt:** den geklonten `tweaks.sh`-Quelltext im Build-Log/Runner inspizieren
   (`grep -n "needs a root" tweaks.sh` nach dem Checkout) und klären, ob `-g`
   selbst `sudo` aufruft.

## Erneut geprüft

- `tests/validate.sh` läuft auf einer frischen, unberührten Kopie vollständig
  grün durch (siehe unten).
- Alle Bash-Skripte unabhängig mit `bash -n` geprüft, keine Syntaxfehler.
- Das eingefügte Python-Snippet zur Extensions-Bereinigung wurde isoliert
  getestet (entfernt exakt den fehlenden Eintrag, lässt alles andere unverändert).

Nicht behauptet: erfolgreicher GitHub-Build oder Hardwaretest dieser Version.
Das kann erst der nächste echte Workflow-Lauf zeigen.

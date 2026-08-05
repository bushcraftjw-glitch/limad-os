# LiMaD OS 2.7.0 RC1 – Fix 6

Grundlage: der Build-Log vom echten fehlgeschlagenen Lauf mit FIX5. Zeigt,
dass beide FIX5-Annahmen zur Logo-Menu-URL bzw. zum GDM-Fix nicht zutrafen –
genau die Unsicherheit, die in FIX5 offen benannt wurde.

## 1. Logo-Menu-Download: echter 404, jetzt mit garantiert existierender URL

```
curl: (22) The requested URL returned error: 404
FATAL: could not download https://github.com/Aryan20/Logomenu/releases/download/v23.6_190125/logomenu@aryan_k.shell-extension.zip
```

Der Fail-Fast-Check hat genau wie vorgesehen funktioniert: harter, klarer
Abbruch statt stillem Fehlschlag. Ursachenanalyse: Das Release v23.6_190125
zeigt "Assets 2" auf der GitHub-Releases-Seite – das sind mit hoher
Wahrscheinlichkeit nur die automatisch generierten "Source code (zip/tar.gz)"
-Archive, kein manuell hochgeladenes gepacktes Extension-Zip. Der geratene
Asset-Name existierte schlicht nicht.

**Fix:** `build_files/45-logomenu-extension.sh` verwendet jetzt die
Tag-Quellcode-Archiv-URL
(`https://github.com/Aryan20/Logomenu/archive/refs/tags/<tag>.zip`), die für
jeden Tag garantiert existiert – nichts zu erraten. Das Repository-Root
selbst ist eine lauffähige, ungepackte Extension (metadata.json, extension.js
direkt im Root), daher ist kein `make build`/Pack-Schritt nötig. Das Skript
findet das einzige Top-Level-Verzeichnis im Archiv automatisch (GitHub nennt
es nicht immer exakt gleich), verifiziert `metadata.json`/`extension.js`,
und kopiert nur die tatsächlich benötigten Dateien in
`/usr/share/gnome-shell/extensions/logomenu@aryan_k/`. Die Extraktions- und
Verzeichniserkennungs-Logik wurde lokal gegen ein simuliertes Archiv mit
identischer Struktur getestet.

## 2. GDM-Fix Nummer 2 (SUDO_USER/SUDO_UID) hat ebenfalls NICHT gegriffen

```
ERROR: '-g' needs a root privilege. Please run this './tweaks.sh' as root
```

Unverändert trotz gesetzter Variablen. Ich habe daraufhin versucht, die
tatsächliche `full_sudo()`-Definition zu finden (öffentliche Doku zu diesem
Projekt kennt nur eine ältere `udo()`-Funktion mit anderem Verhalten – das
Projekt hat die Logik seither offenbar umbenannt oder umgeschrieben, ohne
dass ich den aktuellen Quelltext einsehen kann).

**Keine dritte Vermutung.** Nach zwei fehlgeschlagenen, jeweils begründeten
Versuchen ist ein weiterer Ratefix nicht sinnvoll – das Risiko, den
eigentlichen Fehler nur zu verschleiern, überwiegt den möglichen Nutzen.
Stattdessen gibt der Build jetzt vor dem `tweaks.sh -g`-Aufruf die tatsächliche
`full_sudo()`-Funktionsdefinition auf stdout aus (via `declare -f` nach dem
Sourcen beider Bibliotheksdateien). Der nächste Build-Log zeigt damit exakt,
was geprüft wird – das ist die Grundlage für einen echten, nicht geratenen
Fix. Bis dahin bleibt der bestehende Auffangmechanismus aktiv (`WARNING: GDM
theming failed, login screen stays default`), der Build bricht dadurch
weiterhin nicht ab.

## Erneut geprüft
- `tests/validate.sh` läuft auf frischer, unberührter Kopie komplett grün durch.
- Alle Bash-Skripte unabhängig mit `bash -n` geprüft.
- Die Archiv-Extraktions- und Top-Level-Verzeichniserkennung wurde gegen ein
  lokal erzeugtes Test-Zip mit identischer Struktur (ein Root-Ordner,
  metadata.json, extension.js, Resources/) verifiziert.

Nicht behauptet: dass Punkt 1 diesmal garantiert funktioniert (die URL-Form
ist diesmal aber nicht mehr geraten, sondern eine für jeden Tag garantiert
gültige GitHub-Eigenschaft) oder dass Punkt 2 in diesem Fix gelöst ist – nur
dass der nächste Log die Antwort liefert.

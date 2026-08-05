# LiMaD OS 2.7.0 RC1 – Fix 1

Korrigiert nach unabhängiger Prüfung:

- `tools/brand-installer-iso.sh`: Bash-Syntaxfehler bei der `xorriso -find`-Klammerung behoben (`\\(`/`\\)` zu `\(`/`\)`).
- `tests/test-shell-syntax.sh`: Syntaxprüfung auf den Ordner `tools/` erweitert.
- Alle Shell-Skripte zusätzlich unabhängig mit `bash -n` geprüft.
- Projektweite Offline-Validierung erneut vollständig ausgeführt.

Nicht behauptet: erfolgreicher GitHub-ISO-Build oder Hardwaretest. Diese Punkte bleiben praktisch zu bestätigen.

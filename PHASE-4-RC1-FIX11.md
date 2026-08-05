# LiMaD OS 2.7.0 RC1 FIX11

FIX11 behebt den im echten FIX10-Container-Build gefundenen Abbruch bei der Prüfung der Desktop-Dateien.

## Ursache

`de.limad.SystemUpdate.desktop` startete den System-Updater über `kgx`. Gleichzeitig prüfte das Buildskript den ersten Wert aus `Exec=` ausschließlich mit `[[ -x ... ]]`. Ein Programmname aus dem `PATH` ist jedoch kein Dateipfad und wurde deshalb selbst dann als nicht ausführbar bewertet, wenn das Programm vorhanden gewesen wäre. Außerdem ist ein fest verdrahtetes Terminal unnötig und von der jeweiligen GNOME-Basis abhängig.

## Korrektur

- Der Desktop-Eintrag startet jetzt direkt `/usr/local/bin/limad-system-update`.
- `Terminal=true` überlässt die Auswahl des installierten Terminals der Desktop-Umgebung.
- `TryExec` verweist auf das mitgelieferte absolute Programm.
- Die Buildprüfung unterscheidet jetzt zwischen absoluten Programmpfaden und Befehlen aus dem `PATH`.
- Mehrdeutige Hauptkategorien in mehreren LiMaD-Desktop-Dateien wurden bereinigt, damit Anwendungen nicht doppelt im Menü erscheinen.
- Ein eigener FIX11-Test verhindert die Rückkehr eines fest verdrahteten Terminalbefehls.

## Kennungen

- Buildrevision: `gnome42-phase4-fix12`
- First-Login-Migrationsmarker: `2.7.0-rc1-fix12`

# LiMaD OS 2.7.0 RC1 – FIX48

FIX48 behebt genau ein Problem: die eigentliche Ursache dafür, dass der
LiMaD-Plymouth-Bootscreen seit dem Umstieg auf die rpm-ostree-konforme
Aktivierung (FIX30 ff.) nie sichtbar wurde.

## Root Cause

`system_files/usr/local/sbin/limad-plymouth-initramfs` prüfte:

```
[[ -d /run/ostree-booted ]]
```

`/run/ostree-booted` ist eine von OSTree beim Boot angelegte leere
Marker-**Datei**, kein Verzeichnis. Der `-d`-Test war dadurch auf jedem
tatsächlich über OSTree gebooteten System immer falsch. Das Skript brach
sofort mit der Meldung „not an OSTree boot; leaving timer active“ ab –
**bevor** `rpm-ostree kargs --append-if-missing=rhgb --append-if-missing=quiet`
oder `rpm-ostree initramfs --enable` je ausgeführt wurden.

Damit wurde auf keinem realen Testsystem jemals ein neues Deployment mit
regeneriertem Initramfs gebaut. Alle bisherigen Symptome (Bootscreen fehlt
trotz korrekt installierter Theme-Dateien, trotz korrektem dracut-Modul,
trotz zweifachem Neustart) sind damit erklärt.

## Fix

```
[[ -e /run/ostree-booted ]]
```

`-e` prüft auf Existenz unabhängig vom Dateityp und ist damit korrekt für
einen Marker, der laut OSTree-Dokumentation als reguläre Datei angelegt wird.

## Zusätzlich

- Neuer Regressionstest in `tests/test-fix48-runtime-fixes.sh`: verbietet
  künftig einen `-d`-Test auf `/run/ostree-booted` und verlangt explizit den
  `-e`-Test im Quelltext.
- Keine sonstigen funktionalen Änderungen. LiMaD Klang, Installer-Branding
  und der abgesicherte GitHub-Upload aus FIX47 bleiben unverändert.

## Aktive Versionsmarker

- Produktversion: `2.7.0-rc1`
- Buildrevision: `gnome42-phase4-fix48`
- First Login: `2.7.0-rc1-fix48`
- Flatpak-Status: `default-flatpaks-fix48.done`
- Plymouth-Status: `plymouth-initramfs-fix48.done`

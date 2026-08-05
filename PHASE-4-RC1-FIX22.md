# Phase 4 RC1 – FIX22

## Behobener Fehler

Der Fedora-44-ISO-Bauer erzeugt in der EFI-GRUB-Konfiguration unter anderem:

```text
inst.ks=hd:LABEL=LIMAD_OS_270_RC1:/osbuild.ks
```

Dabei ist `LIMAD_OS_270_RC1` die Volume-ID. `:/osbuild.ks` ist ein Dateipfad auf diesem Medium. FIX21 hat beides als ein einziges Label ausgewertet und deshalb eine korrekte ISO abgelehnt.

## Korrektur

- Labelauswertung endet vor dem Doppelpunkt.
- Der Rewrite ersetzt ausschließlich den Labelteil.
- Der Kickstart-Pfad `:/osbuild.ks` bleibt bytegenau erhalten.
- Der Regressionstest prüft sowohl gültige als auch ungültige Labelwerte.

## Nicht geändert

Keine Änderungen an Apps, Themes, GNOME-Konfiguration, Wallpaper, Plymouth, Wine, NWS oder dem Container-Payload.

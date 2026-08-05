# LiMaD OS 2.8.0 RC1 – Build 1

Diese Version beginnt die 2.8-Reihe auf der stabilen FIX50-Basis.

## Laufzeitreparaturen

- Plymouth wird ausschließlich mit `rpm-ostree initramfs --enable` vorbereitet.
- LiMaD Klang lädt das lokale Preset auch dann, wenn der optionale EasyEffects-Steuerungsserver deaktiviert ist.
- Die direkte Socketsteuerung wird automatisch verwendet, sobald der Server erreichbar und funktionsfähig ist.
- LiDrop 0.11.0-preview5 überträgt Dateien als fortsetzbaren Stream statt in 256-KiB-Fetch-Blöcken und startet bei 45 Sekunden Stillstand automatisch neu.

## Versionsschema

- Produkt: `2.8.0-rc1`
- Revision: `gnome-phase5-build1`
- ISO: `LIMAD_OS_280_RC1`
- Container: `limad-os-gnome-280`

# LiMaD OS 2.7.0 RC1 FIX10

FIX10 behebt den im ersten echten FIX9-Container-Build gefundenen Konflikt bei den GNOME-Hintergrundvorgaben.

## Reproduzierter Fehler

Der Build erreichte erfolgreich MacTahoe, GDM, WhiteSur und Logo Menu für GNOME 50, brach anschließend aber kontrolliert ab:

```text
FATAL: default wallpaper is 'file:///usr/share/backgrounds/convergence-dynamic.xml', expected /usr/share/backgrounds/limad/LiMaD-Wallpaper-02-Logo-Zentriert-4K.png
```

Die Annahme, der Dateiname `zz-limad-wallpaper.gschema.override` würde zwangsläufig nach allen Vorgaben der Bazzite-Basis ausgewertet, war falsch.

## Korrektur

- Neuer Helfer `build_files/enforce-gnome-wallpaper.py`.
- Er erzeugt `zzzzzzzzzz-limad-wallpaper.gschema.override`.
- Zusätzlich normalisiert er in sämtlichen bereits vorhandenen `*.gschema.override`-Dateien die kollidierenden Schlüssel:
  - `org.gnome.desktop.background/picture-uri`
  - `org.gnome.desktop.background/picture-uri-dark`
  - `org.gnome.desktop.background/picture-options`
  - `org.gnome.desktop.screensaver/picture-uri`
  - `org.gnome.desktop.screensaver/picture-options`
- Dadurch verweist auch eine später ausgewertete Bazzite-Vorgabe auf das LiMaD-Wallpaper.
- Dconf-Systemvorgabe und First-Login-Migration bleiben als weitere unabhängige Ebenen bestehen.
- Ein synthetischer Test erzeugt bewusst eine alphabetisch spätere Upstream-Vorgabe mit `convergence-dynamic.xml` und bestätigt deren Ersetzung.

## Versionsstand

- Buildrevision: `gnome40-phase4-fix10`
- First-Login-Migrationsmarker: `2.7.0-rc1-fix10`

## Aussagegrenze

Die Offline-Prüfungen bestätigen Quellcode, Tests und Paketstruktur. Der erneute GitHub-Container- und ISO-Build bleibt erforderlich.

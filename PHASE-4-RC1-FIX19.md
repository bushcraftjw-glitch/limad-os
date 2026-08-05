# LiMaD OS 2.7.0 RC1 – FIX19 xorriso-Dateisuche

## Nachgewiesener Fehler

Der FIX18-Build erzeugte `images/install.img` und schrieb das vollständige ISO erfolgreich. Der nachgelagerte Quell-ISO-Prüfer meldete die Datei trotzdem als fehlend.

Die Ursache lag in allen drei ISO-Skripten: Sie verwendeten bei `xorriso -find` die Syntax `-print` aus dem Unix-Werkzeug `find`. `xorriso -find` verwendet stattdessen seine Standardaktion `echo` oder ausdrücklich `-exec echo --`. Der Fehler wurde verborgen, weil stderr verworfen und der Rückgabecode mit `|| true` neutralisiert wurde.

## Korrektur

- exakte ISO-Dateiprüfung mit `-find ... -exec echo --`
- Suche nach GRUB-/Boot-Konfigurationen ebenfalls mit `-exec echo --`
- Korrektur in Quellprüfung, Branding und Endprüfung
- Regressionstest verbietet die fehlerhafte `-print`-Variante
- System-, App-, Theme- und Branding-Nutzlasten aus FIX18 bleiben unverändert

Buildrevision: `gnome42-phase4-fix19`

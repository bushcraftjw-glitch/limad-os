# LiMaD OS 2.7.0 RC1 – FIX37

FIX37 übernimmt FIX36 vollständig und ergänzt den Medien- und Klangbereich.

## Neue Standardanwendungen

- Zoom bleibt als `us.zoom.Zoom` enthalten.
- YTMDesktop wird als `app.ytmdesktop.ytmdesktop` beim Benutzer installiert.
- EasyEffects wird als `com.github.wwmm.easyeffects` installiert.
- Alle Flatpaks bleiben benutzerbezogen; das unveränderliche bootc-System wird nicht durch eine System-Flatpak-Installation verändert.

## LiMaD Klang

- neue kompakte Oberfläche mit direkten Reglern für Bass, Mitten und Höhen
- Änderungen werden über den offiziellen lokalen EasyEffects-Server sofort angewendet
- Schnellprofile: Neutral, Musik, Mehr Bass, Klare Sprache und Mehr Höhen
- eigene Werte werden unter `~/.config/limad/klang.json` gespeichert
- automatischer Headroom reduziert Übersteuerung bei positiven Verstärkungen
- vollständige EasyEffects-Oberfläche bleibt über „Erweiterte Einstellungen“ erreichbar
- EasyEffects wird nach der Installation im Hintergrund gestartet
- ein mitgeliefertes 10-Band-Ausgangspreset sorgt dafür, dass die Regler direkt funktionieren

## Dock

Reihenfolge ergänzt um YTMDesktop und LiMaD Klang nach Zoom.

## Schutzumfang

- keine Änderung an `.github`, Workflows, Repository-Ziel oder Zugangsdaten
- FIX36-App-Stand, AirDrop-Härtung und alle bisherigen Funktionen bleiben erhalten

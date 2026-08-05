# LiMaD OS 2.8.0 RC2 Build 3 – LiLink & GStreamer

- einheitliches Windows-Programme-Symbol auf Notebook, iMac und allen Skalierungsstufen
- identisches freigegebenes Artwork für LiMaD-PNGs sowie LiMaD-/hicolor-SVG-Fallbacks
- GStreamer wird als verbindlicher Bestandteil ganz am Anfang des System-Builds installiert
- ergänzt `python3-gstreamer1` für die Python-GI-Anbindung
- ergänzt `gstreamer1-plugin-gtk4` und prüft `gtk4paintablesink`
- Build-Abbruch statt stiller Warnung, wenn der native Medien-Unterbau unvollständig ist
- zusätzlicher Laufzeittest für Playbin, GTK4-Sink, PipeWire und Standardkonverter
- LiLink 1.0.0-preview2 und alle bisherigen RC2-Build-2-Funktionen bleiben enthalten
- bestehende Geräte erhalten die Systemkomponenten über LiMaD Update/rpm-ostree

## Testgrenze

Quell-, Syntax-, Icon-, Paket- und Integrationsprüfungen laufen automatisiert. Die tatsächliche Audio-/Videowiedergabe und RDP-/Deskflow-Verbindung werden nach dem GitHub-ISO-Build zusätzlich auf Notebook und iMac geprüft.

## Versionen

- LiMaD OS: 2.8.0 RC2 Build 3
- GNOME: 50
- LiLink: 1.0.0-preview2
- LiMaD Study: 6.6.1
- LiDrop: 0.12.0-preview4
- Windows-Programme: 2.2.5

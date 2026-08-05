# LiLink 1.0.0-preview3 – Architektur und Sicherheit

## Zuständigkeiten

- `limad-link.service`: Geräteidentität, TLS-Endpunkt, Kopplung, Berechtigungen, Dateiübertragung und Handoff.
- `_limad-link._tcp`: lokale Geräteerkennung über Avahi.
- GNOME Remote Desktop: tatsächliche Bildschirmfreigabe und Fernsteuerung.
- FreeRDP: Client für die Verbindung zum Zielgerät.
- Deskflow: gemeinsame Maus und Tastatur; Wayland-Freigaben bleiben Aufgabe des Desktops.
- LiDrop-Verzeichnis `~/LiDrop`: Ziel für bewusst übertragene Dateien.
- GNOME-Shell-Erweiterung `lilink@limad.local`: Statussymbol und Schnellzugriff.

## Kopplung

Jedes Gerät erzeugt eine dauerhafte zufällige Geräte-ID und ein selbstsigniertes RSA-3072-Zertifikat. Die Kopplung verwendet einen sechsstelligen, fünf Minuten gültigen Einmalcode. Pro Quelladresse sind höchstens acht Versuche in fünf Minuten erlaubt. Nach erfolgreicher Kopplung speichern beide Seiten getrennte zufällige Eingangs- und Ausgangstoken sowie den SHA-256-Fingerabdruck des TLS-Zertifikats.

Vor jeder Remote-Aktion wird der aktuelle Zertifikatsfingerabdruck mit dem beim Koppeln gespeicherten Wert verglichen. Ein Zertifikatswechsel beendet die Verbindung und verlangt eine erneute Kopplung.

## Lokale Steuerung

Der lokale App-Zugriff verwendet ein bei jedem Dienststart neu erzeugtes Administrator-Token. Es liegt ausschließlich mit Benutzerrechten im Laufzeitverzeichnis und wird nur bei Loopback-Anfragen akzeptiert. Zustands- und Schlüsseldateien werden mit Berechtigung `0600`, Verzeichnisse mit `0700` angelegt.

## Bildschirmübernahme

LiLink aktiviert nicht selbst einen zweiten Streaming-Server. Das Zielgerät konfiguriert den vorhandenen GNOME-Remote-Desktop-Dienst über `grdctl`. Der FreeRDP-Client erhält Benutzername und Passwort über Standardeingabe, damit das Passwort nicht in der Prozessliste erscheint. Wenn LiLink die Freigabe selbst eingeschaltet hat, kann sie nach dem Verbindungsende automatisch wieder deaktiviert werden.

## Dateiübertragung

Dateien laufen ausschließlich über die gepinnte TLS-Verbindung. Übertragungen sind fortsetzbar, auf 4-MiB-Blöcke begrenzt und werden erst nach vollständiger Größen- und SHA-256-Prüfung aus der temporären Datei nach `~/LiDrop` verschoben. Dateinamen werden auf den Basisnamen reduziert und gegen NUL-/Pfadmanipulation bereinigt.

## Handoff

Preview 1 überträgt ein versioniertes Grundobjekt und kann App, URL oder Datei am Ziel öffnen. Exakte Zustände wie Study-Leseposition, Cut-Kameraansicht oder Browser-Tabgruppe sind noch nicht allgemein implementiert. Dafür benötigen die jeweiligen Anwendungen definierte Export-/Importadapter. Das wird nicht als fertige Prozessmigration bezeichnet.

## Netzwerkgrenze

Die automatische Suche ist für das lokale Netz vorgesehen. Der Dienst lehnt global routbare Quelladressen bereits auf Anwendungsebene ab und akzeptiert Loopback, private IPv4-/IPv6-Netze, Link-Local sowie den CGNAT-Bereich. LiLink konfiguriert keine Routerfreigabe. Fernzugriff außerhalb des lokalen Netzes gehört hinter ein separat verwaltetes VPN und benötigt dafür eine spätere ausdrückliche Netzfreigabe.

## Widerruf

Eine lokale Kopplung kann jederzeit entfernt werden. Danach akzeptiert das lokale Gerät den zugehörigen Eingangstoken nicht mehr. Für einen vollständig beidseitigen Widerruf muss die Kopplung auf beiden Geräten entfernt oder eine spätere gegenseitige Widerrufsbestätigung verwendet werden.

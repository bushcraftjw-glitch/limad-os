# LiLink 1.0.0-preview3

LiLink verbindet LiMaD-OS-Rechner im lokalen Netzwerk. Die App verwendet die vorhandene GNOME-RDP-Funktion für Bildschirmfreigabe und Fernsteuerung, Deskflow für gemeinsame Eingabegeräte und einen TLS-gesicherten LiLink-Dienst für Geräteerkennung, Kopplung, Dateiübergabe und Handoff.

## Sicherheit

- zufällige dauerhafte Geräte-ID
- selbst erzeugtes TLS-Zertifikat mit gepinntem SHA-256-Fingerabdruck
- einmaliger sechsstelliger Kopplungscode mit fünf Minuten Gültigkeit
- getrennte Bearer-Token je Richtung
- Gerätewiderruf
- Dateien mit SHA-256-Endprüfung
- Geheimnisse nur im Benutzerprofil mit Modus 0600

## Grenzen der Preview

- Eine laufende Anwendung wird nicht zwischen Rechnern verschoben.
- Handoff startet App, URL oder Datei bereits auf dem Zielgerät. Exakte Zustandsadapter für LiMaD Study und LiMaD Cut werden in den Apps selbst weiter ausgebaut.
- GNOME Remote Login ist eine systemweite Administratorfunktion und wird nicht stillschweigend aktiviert.
- Deskflow benötigt unter Wayland beim ersten Einsatz eine lokale Portal-/Eingabebestätigung.
- Reale RDP-, Wayland-, Mehrmonitor- und Zwei-Geräte-Tests müssen auf physischer Hardware erfolgen.

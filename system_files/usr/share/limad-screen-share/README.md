# LiMaD auf TV übertragen

Die Oberfläche bündelt drei Übertragungswege:

- Google TV und Chromecast über GNOME Network Displays
- Samsung- und andere Miracast-Empfänger über GNOME Network Displays
- Apple TV und AirPlay-kompatible Fernseher über das experimentelle Doubletake-Modul

Das AirPlay-Modul wird nur auf ausdrücklichen Benutzerwunsch gestartet. Die benötigten TCP- und UDP-Ports 60000 bis 60010 werden ausschließlich zur Laufzeit geöffnet und automatisch wieder geschlossen.

# LiMaD OS 2.8.0 RC1 – Build 2

Build 2 erweitert die bestätigte Build-1-Basis um eine protokollgetrennte Bildschirmübertragung.

## LiMaD Bildschirmfreigabe 1.0.0

- Google Cast und Miracast werden durch das Fedora-44-Paket `gnome-network-displays` bereitgestellt.
- Die LiMaD-Oberfläche startet die native Geräteauswahl für Google TV, Chromecast, Samsung und kompatible Miracast-Empfänger.
- Apple TV und AirPlay-kompatible Fernseher werden über Doubletake v0.4.0 angebunden.
- Der Quellstand ist auf Commit `364ea84247ce17a084ae15b9011409910e823e34` festgeschrieben und wird beim Build verifiziert.
- AirPlay ist ausdrücklich experimentell, startet nicht automatisch und ist nicht für produktive oder sicherheitskritische Netze freigegeben.
- TCP/UDP 60000-60010 werden nur nach Polkit-Bestätigung zur Laufzeit geöffnet und spätestens nach zwei Stunden entfernt.
- Die App kann ab Build 2 über das bestehende `.limad-update.zip`-Format aktualisiert werden.

## Versionsschema

- Produkt: `2.8.0-rc1`
- Revision: `gnome-phase5-build2`
- App: `LiMaD Bildschirmfreigabe 1.0.0`
- ISO: `LIMAD_OS_280_RC1`
- Container: `limad-os-gnome-280`

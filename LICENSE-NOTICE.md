# Lizenz- und Urheberhinweise

LiMaD OS ist eine Zusammenstellung. Die folgenden Bestandteile stammen von
Dritten und behalten ihre jeweilige Lizenz. Die vollständigen Lizenztexte und
der genaue Commit landen beim Bau im Image unter `/usr/share/limad-source/`.

## Basissystem

**Bazzite / Universal Blue** – <https://github.com/ublue-os/bazzite>
Lizenz: Apache-2.0 (Projektdateien) sowie die Lizenzen der enthaltenen
Fedora-Pakete. Basis-Image: `ghcr.io/ublue-os/bazzite-gnome:stable`.

## Design

**MacTahoe GTK Theme** – <https://github.com/vinceliuice/MacTahoe-gtk-theme>
Autor: Vinceliuice und Mitwirkende. Lizenz: MIT. Verwendeter Stand: Tag
`2026-05-24`. Wird beim Bau aus der Quelle übersetzt und als GTK-, GNOME-Shell-
und GDM-Design unter dem Namen `LiMaD` installiert.

**WhiteSur Icon Theme** – <https://github.com/vinceliuice/WhiteSur-icon-theme>
Autor: Vinceliuice und Mitwirkende. Lizenz: GPL-3.0-only. Verwendeter Stand:
Tag `2025-12-27`. Liefert sämtliche allgemeinen Icons.

Beide Projekte werden unverändert aus dem jeweiligen Release-Tag gebaut. Es
werden keine Dateien aus diesen Projekten in diesem Repository mitgeliefert.

## Bildschirmübertragung

**GNOME Network Displays** – <https://gitlab.gnome.org/GNOME/gnome-network-displays>  
Lizenz: GPL-3.0-or-later. Wird als Fedora-Systempaket eingebunden und stellt die native Google-Cast- und Miracast-Übertragung bereit.

**Doubletake** – <https://github.com/omarroth/doubletake>  
Lizenz: LGPL-3.0-or-later sowie GPL-3.0-or-later für übernommene Bestandteile. Verwendeter Stand: Tag `v0.4.0`, Commit `364ea84247ce17a084ae15b9011409910e823e34`. Doubletake wird ausschließlich als experimenteller AirPlay-Sender verwendet, nicht automatisch gestartet und nicht für produktive oder sicherheitskritische Umgebungen freigegeben. Lizenztexte und Herkunftsnachweis werden beim Build im Image installiert.

## Eigene Bestandteile

Die LiMaD-Programmicons (`system_files/usr/share/icons/LiMaD/`), die
Build-Skripte, die Prüfungen und die GNOME-Vorgaben sind Eigenentwicklung von
LiMaD. Das LiMaD-Logo und die Programmicons sind urheberrechtlich geschützt
und nicht Teil der oben genannten freien Lizenzen.

## Marken

macOS, Apple und Tahoe sind Marken von Apple Inc. LiMaD OS steht in keiner
Verbindung zu Apple. Die verwendeten Designs ahmen lediglich ein Erscheinungs-
bild nach und enthalten keine Apple-Bestandteile.


### OWL / AWDL
- Quelle: https://github.com/seemoo-lab/owl.git
- festgeschriebener Commit: `8e4e840b212ae5a09a8a99484be3ab18bad22fa7`
- Lizenz: GPL-3.0
- Zweck: experimentelle AWDL-Kompatibilität auf einer separaten geeigneten WLAN-Schnittstelle.

### OpenDrop
- Quelle: https://github.com/seemoo-lab/opendrop.git
- festgeschriebener Commit: `ae5ac821fb3b233df3ac800e4eb47f287f4422cf`
- Version: 0.13.0
- Lizenz: GPL-3.0
- Hinweis: experimentelle AirDrop-Kompatibilität; Kontakte-Modus ist nicht freigeschaltet.

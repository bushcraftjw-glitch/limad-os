# Phase 4 – RC1 FIX21

## Ursache

Der Fedora-44-`bootc-image-builder` erzeugt im aktuellen Anaconda-ISO-Pipelinepfad `images/install.img`, `.discinfo`, die Bootabbilder und `osbuild.ks`, aber keine `.treeinfo`. FIX20 behandelte `.treeinfo` trotzdem als Pflichtdatei und brach nach einem erfolgreichen ISO-Build ab.

## Änderung

- `.treeinfo` ist in Quell- und Ziel-ISO optional.
- Ist sie vorhanden, wird sie weiterhin validiert und bei Änderungen aktualisiert.
- Ist sie nicht vorhanden, bleibt das native Builder-Layout unverändert; es wird keine künstliche Produktmetadatei erzeugt.
- Kernel, Initramfs, EFI-Abbild, Bootkonfiguration, Volume-ID, Hybridstruktur und Medienprüfsumme werden weiterhin direkt geprüft.
- Fehlläufe laden zusätzlich die exakte ISO-Dateiliste sowie El-Torito-, GPT/MBR- und PVD-Berichte hoch.

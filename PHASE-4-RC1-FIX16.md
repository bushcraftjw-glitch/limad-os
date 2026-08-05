# LiMaD OS 2.7.0 RC1 – FIX16 tiefe ISO-Boot-Reparatur

## Auslöser

Auf realer UEFI-Hardware startete GRUB vom USB-Stick, konnte anschließend aber
`/images/pxeboot/vmlinuz` nicht finden. Fedora Media Writer war nicht die
Ursache: Der Fehler liegt vor dem Laden des Kernels innerhalb der ISO-Bootkette.

## Gefundene Fehlerklassen

1. Die ISO-Bezeichnung wurde bisher erst nach dem Bau verändert. Die im
   eingebetteten EFI-Abbild erzeugte GRUB-Konfiguration konnte dadurch weiterhin
   auf das alte Label zeigen.
2. FIX14 erkannte die GRUB-Kurzform `-l` nicht. Scheitert diese Suche, bleibt
   GRUB auf dem kleinen EFI-Abbild; dort existiert `/images/pxeboot/vmlinuz`
   nicht.
3. Das vorhandene Anaconda-`product.img` wurde vollständig durch ein minimales
   neues Abbild ersetzt. Dadurch konnten nicht gebrandete Installerbestandteile
   verloren gehen.
4. Nach Änderungen an `product.img` und `efiboot.img` wurden die Prüfsummen in
   `.treeinfo` nicht erneuert.
5. Nach der ISO-Nachbearbeitung wurde der eingebettete Medienprüfwert nicht neu
   erzeugt. Die Option „Medium testen“ konnte deshalb fehlschlagen.
6. Ein GRUB-Hintergrund wurde sehr früh in die EFI-Konfiguration eingefügt. Das
   war für das Booten unnötig und erhöhte das Fehlerrisiko.

## Umsetzung

- Native ISO-ID `LIMAD_OS_270_RC1` in `disk_config/iso.toml`.
- Abbruch, falls der ISO-Bauer diese ID nicht bereits korrekt erzeugt hat.
- Umschreiben und Audit von `-l`, `-L`, `--label`, `--fs-label`,
  `search.fs_label`, Labelvariablen, `inst.stage2`, `root=live:CDLABEL` und
  `root=live:LABEL`.
- Prüfung aller referenzierten Kernel- und Initramfs-Pfade gegen die fertige ISO.
- Erhaltung und Overlay des ursprünglichen `product.img` als Root mit
  SquashFS-Ownership-Sicherung.
- Aktualisierung der `.treeinfo`-SHA-256-Werte.
- Neuer Medienprüfwert mit `implantisomd5`; Prüfung mit `checkisomd5`.
- Prüfung von UEFI-El-Torito, Hybrid-MBR/GPT für USB-Medien, `BOOTX64.EFI` und `grubx64.efi`; die EFI-Binärdateien müssen vor und nach der Konfigurationsänderung bytegleich bleiben.
- Keine kosmetische Hintergrund-Injektion mehr in den frühen EFI-GRUB-Pfad.

## Nachweisgrenze

Die Offline-Prüfung kontrolliert die Projektlogik vollständig. Die endgültige
Bestätigung erfolgt erst mit der im GitHub-Workflow erzeugten ISO, weil erst dort
`bootc-image-builder`, das echte EFI-Abbild und die vollständige Kernel-/Initrd-
Nutzlast vorliegen. Die ISO wird vom Workflow nur als Artefakt veröffentlicht,
wenn der tiefe Binär-Audit erfolgreich ist.

Buildrevision: `gnome42-phase4-fix16`  
GHCR-Paket: `limad-os-gnome-fix16`

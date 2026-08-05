# LiMaD OS 2.7.0 RC1 – FIX15 EFI-Boot-Reparatur

FIX15 behebt den realen UEFI-Startfehler:

- GRUB verwendet im eingebetteten EFI-Systemabbild die Kurzoption `-l` für die ISO-Volume-ID.
- Die bisherige Nachbearbeitung ersetzte `--label` und `--fs-label`, aber nicht `-l`.
- Dadurch wurde die LiMaD-ISO-Partition nicht als GRUB-Root gesetzt. GRUB blieb auf dem EFI-Abbild und meldete anschließend, dass `/images/pxeboot/vmlinuz` nicht vorhanden sei.

Änderungen:

- `search ... -l <Volume-ID>` wird auf `LIMAD_OS_270_RC1` umgeschrieben.
- Normale und eingebettete EFI-`grub.cfg` werden auf lange und kurze Label-Schreibweisen geprüft.
- Referenzierte Kernel- und Initrd-Dateien müssen im fertigen ISO tatsächlich vorhanden sein.
- Die EFI-`grub.cfg` wird eindeutig überschrieben und wieder in `images/efiboot.img` gespeichert.
- Buildrevision `gnome42-phase4-fix15`, GHCR-Paket `limad-os-gnome-fix15`.

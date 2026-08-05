# LiMaD OS 2.7.0 RC1 – FIX17 BIB-Exit-Recovery

## Auslöser

Der reale GitHub-Lauf erzeugte die Anaconda-ISO vollständig und meldete:

- `Writing to ... install.iso completed successfully`
- `manifest - finished successfully`
- `Build complete!`
- `Results saved in .`

Der Containerlauf endete danach trotzdem mit Exitcode 5. Wegen `set -e` brach der Workflow sofort ab. Die erzeugte ISO wurde deshalb weder nachbearbeitet noch geprüft oder als Artefakt hochgeladen.

## Korrektur

- Der Buildercontainer verwendet keinen automatischen `--rm`-Abbau mehr. Er wird benannt und kontrolliert entfernt.
- `--output /output` ist explizit gesetzt.
- Der echte Exitcode des Buildercontainers wird über `PIPESTATUS[0]` erfasst.
- Exitcode 5 wird nicht pauschal ignoriert. Der Workflow fährt nur fort, wenn die erzeugte Quell-ISO zuvor folgende Pflichtprüfungen besteht:
  - korrekte Volume-ID `LIMAD_OS_270_RC1`
  - Kernel und Initramfs vorhanden und nicht leer
  - `product.img`, `efiboot.img` und `osbuild.ks` vorhanden
  - EFI-El-Torito-Eintrag vorhanden
  - Hybrid-MBR/GPT für USB-Boot vorhanden
  - eingebettete Medienprüfsumme gültig
  - EFI-`grub.cfg` vorhanden
  - alle EFI-Labelverweise stimmen mit der ISO-Volume-ID überein
  - EFI-Konfiguration verweist auf den vorhandenen Kernel und das Initramfs
- Andere von null verschiedene Exitcodes bleiben fatal.
- Branding und tiefe Endprüfung laufen in einem getrennten Schritt.
- Bei einem Fehler wird das vollständige Builderprotokoll als Diagnoseartefakt hochgeladen.

Buildrevision: `gnome42-phase4-fix17`  
GHCR-Paket: `limad-os-gnome-fix16` (bewusst weiterverwendet, damit die bereits bestätigte öffentliche Paketfreigabe erhalten bleibt)

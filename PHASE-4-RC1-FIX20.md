# LiMaD OS 2.7.0 RC1 – FIX20 ESP-GUID-Auswertung

Der FIX19-Lauf erzeugte die ISO erfolgreich. Die Quellprüfung verwarf sie anschließend, weil `xorriso -report_system_area plain` den EFI-Systempartitionstyp in der plattengespeicherten GUID-Darstellung `28732ac11ff8d211ba4b00a0c93ec93b` meldet und die Prüfung nur die kanonische Schreibweise `C12A7328-F81F-11D2-BA4B-00A0C93EC93B` erwartete.

FIX20 erkennt beide Darstellungen, beide von xorriso verwendeten Feldnamen (`GPT type GUID` und `GPT partition type GUID`) sowie die vorhandenen Fallbacks über `efiboot.img` und MBR-Typ `0xef`. Ein Regressionstest verwendet die tatsächliche GitHub-Ausgabe.

Buildrevision: `gnome42-phase4-fix20`

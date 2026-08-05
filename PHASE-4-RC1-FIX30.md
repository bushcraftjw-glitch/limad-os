# LiMaD OS 2.7.0-rc1 FIX30

## Bootc-/OSTree-initramfs-Rollback

FIX29 regenerierte die bereits vom Bazzite-Basisimage vorbereitete initramfs nachträglich mit `dracut --force`. Auf dem installierten System führte dies zu dracut Emergency Mode beim Start.

FIX30 entfernt diese manuelle Regenerierung vollständig. Kernel und initramfs bleiben Eigentum des bootc-/OSTree-Basis- und Updateprozesses. Das LiMaD-Plymouth-Theme, die Theme-Auswahl, die dracut-Konfiguration und alle zwölf Spinner-Dateien bleiben installiert.

Die GNOME-Branding-Prioritätskorrekturen aus FIX29 und die Dock-Korrektur aus FIX28 bleiben erhalten.

# LiMaD OS 2.7.0-rc1 FIX29

FIX29 repariert die Plymouth-Einbettung in die initramfs und priorisiert die LiMaD-GNOME-/dconf-Vorgaben zuverlässig hinter Fedora-/Bazzite-Overrides.

- Baut nach Auswahl des LiMaD-Plymouth-Themes jede installierte Kernel-initramfs neu.
- Nimmt alle zwölf Spinner-Bilder ausdrücklich in die Dracut-Konfiguration auf.
- Verwendet `zzzzzzzzzz-limad-defaults.gschema.override` als Hauptoverride.
- Verwendet `zzzzzzzzzz-limad-branding` als systemweites dconf-Fragment.
- Prüft das tatsächlich kompilierte GNOME-Shell-Theme im Build und Acceptance-Check.

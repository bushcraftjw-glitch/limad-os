# LiMaD OS 3.0 – GDM resource target detection (FIX8)

The Ubuntu 26.04 / GNOME 50 build reached MacTahoe GDM theming successfully,
but the previous validation watched only the generic resource
`/usr/share/gnome-shell/gnome-shell-theme.gresource`.

MacTahoe 2026-05-24 uses `install_only_gdm_theme()` for GNOME >= 48 and chooses
the first existing GDM resource in its own priority order. On Ubuntu this can be
the Yaru resource at:

`/usr/share/gnome-shell/theme/Yaru/gnome-shell-theme.gresource`

FIX8 therefore snapshots every supported existing GDM resource by canonical
path before the MacTahoe tweak, reruns the tweak, and requires at least one
candidate to have a changed SHA256 afterwards. The actually changed resource is
recorded in `/usr/share/limad/gdm-branding.env`.

This keeps the check strict while avoiding a false failure caused by watching a
resource MacTahoe did not modify.

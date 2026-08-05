# LiMaD OS 2.7.0 RC1 – FIX46

FIX46 übernimmt Installer, Plymouth-Bootscreen und LiMaD Klang aus FIX44 und stellt das GitHub-Ziel einheitlich auf das neue Repository um.

## GitHub-Ziel

- Besitzer: `bushcraftjw-glitch`
- Repository: `limad-os`
- URL: `https://github.com/bushcraftjw-glitch/limad-os.git`
- macOS- und Linux-Startskript verwenden dieses Ziel als Standard.
- `.github/workflows/build.yml` und `.github/workflows/theme-probe.yml` bleiben inhaltlich unverändert.

## Aktive Versionsmarker

- Buildrevision: `gnome42-phase4-fix46`
- First Login: `2.7.0-rc1-fix46`
- Flatpak-Status: `default-flatpaks-fix46.done`
- Plymouth-Status: `plymouth-initramfs-fix46.done`

## Unverändert enthalten

- LiMaD-Installerdesign
- rpm-ostree-konforme Plymouth-Reparatur
- LiMaD Klang und EasyEffects-Anbindung
- OWL-Zielbuild ohne GoogleTest
- alle Apps und AMD/Bazzite-Komponenten aus FIX44

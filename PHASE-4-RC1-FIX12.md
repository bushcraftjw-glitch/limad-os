# LiMaD OS 2.7.0-rc1 FIX12

## Behobener ISO-Blocker

`bootc-image-builder` bestimmt die Distribution über `ID` und `VERSION_ID` aus `/etc/os-release`.
FIX11 setzte `ID=limad`; dadurch suchte der ISO-Bauer nach der nicht vorhandenen Definition `limad-44`.

FIX12 bewahrt deshalb die technisch notwendige Fedora-Identität:

- `ID=fedora`
- `VERSION_ID=44` bleibt von der Basis erhalten

Die sichtbare LiMaD-Marke bleibt vollständig bestehen über:

- `NAME="LiMaD OS"`
- `PRETTY_NAME="LiMaD OS 2.7.0-rc1"`
- `BOOTLOADER_NAME`
- `VARIANT="LiMaD GNOME"`
- `VARIANT_ID=limad-gnome`
- Logos, Wallpaper, GDM und Plymouth

Buildrevision: `gnome42-phase4-fix12`.

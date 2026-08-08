# LiMaD OS 3.0 – verbindliche Build-Liste

Stand: `3.0.0-starter1`

## Basis
- Ubuntu 26.04 LTS (Resolute), AMD64.
- GNOME 50.
- Klassisches APT/DEB-System, kein rpm-ostree, bootc oder Bazzite-Unterbau.
- Flatpak/Flathub für geeignete Desktop-Apps.

## Design – Bestandsschutz
- Vorhandener LiMaD-Plymouth-Bootscreen bleibt bytegenau erhalten.
- MacTahoe/LiMaD GTK- und GNOME-Shell-Design bleibt erhalten.
- WhiteSur + LiMaD-Icon-Overlay bleibt erhalten.
- LiMaD-Wallpaper, Dock, LogoMenu und GDM-Branding bleiben erhalten.
- `tests/theme-lock.sha256` verhindert versehentliche Änderungen an Plymouth, Wallpapern und LiMaD-Icons.

## Installer
- Ubuntu-Installer-Bedienelemente werden nicht global per CSS überschrieben.
- Keine Anaconda/Fedora-Installer-CSS übernehmen.
- Keine globale weiße Textfarbe.
- LiMaD-Branding darf Produktname/Boottexte ändern, aber nicht die Lesbarkeit der Controls riskieren.

## LiMaD-Programme
- LiMaD Study 6.6.3.
- LiMaD Cut 1.1.4.
- LiDrop 0.12.0-preview8; unabhängig updatefähig.
- LiLink 1.0.0-preview3.
- LiNotes 1.0.0-preview2.
- LiSave 1.0.0-preview3 (SIZE-ANALYSIS-FIX).
- LiMaD auf TV übertragen 1.0.1.
- LiMaD Mail 1.8 = LiMaD-Integration auf Thunderbird-Basis.
- LiMaD Klang: LiMaD-Steuerung/Preset-Schicht für EasyEffects.
- Windows-Programme bleiben vorerst auf 2.2.6; neue NWS/PREFIX-Architektur erst nach stabiler Ubuntu-Basis.
- Anycubic Slicer Next 1.3.96 bleibt integriert.

## Unabhängige Updates
Nach jedem vollständigen ISO-Build werden zusätzlich eigenständige `.limad-update.zip` erzeugt für:
- LiMaD Cut
- LiMaD Study
- LiDrop
- LiLink
- LiNotes
- LiSave
- LiMaD auf TV übertragen
- LiMaD Mail
- LiMaD Klang
- Anycubic Slicer Next
- Windows-Programme

Die ISO ist nicht Voraussetzung für ein späteres App-Update.

## Standardprogramme
- Zen Browser
- LiMaD Mail / Thunderbird
- Zoom Workplace
- YouTube Music Desktop
- LibreOffice
- Anycubic Slicer Next
- EasyEffects / LiMaD Klang
- Bazaar
- Bottles vorerst als Ergänzung zur bestehenden Windows-Programme-Lösung

## Gaming
- Steam nativ.
- Steam Play / offizielles Proton wird von Steam verwaltet und bei Bedarf automatisch geladen.
- ProtonUp-Qt wird für GE-Proton/weitere Compatibility Tools automatisch bereitgestellt.
- Lutris nativ.
- GameMode nativ.
- Gamescope nativ.
- Vulkan 64-bit + 32-bit Runtime.

## Geräte/Netzwerk
- Deskflow automatisch über Flathub.
- CUPS, IPP, HPLIP, SANE/AirScan, Samba, Avahi.
- GNOME Remote Desktop / Connections / Network Displays.
- LiDrop und LiLink bleiben integriert.

## Freigaberegel
`starter1` ist ein Migrations-/Buildkandidat. Eine Version wird erst RC/final, wenn GitHub-ISO-Build, Live-Boot, Installer, installierter Boot, Plymouth, GNOME, Apps, Gaming, Netzwerk und Hardware real getestet wurden.

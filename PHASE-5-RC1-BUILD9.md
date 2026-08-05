# LiMaD OS 2.8.0 RC1 Build 9

Build 9 replaces the existing Windows-Programme implementation without adding a second application.

## Windows-Programme 2.0

- existing app ID `de.limad.WindowsApps` retained
- existing LiMaD Windows dock icon retained
- one window with Installieren, Meine Programme, Reparieren, Umgebungen, Protokoll and Einstellungen
- separate Wine WoW64 prefix for every installed application
- automatic EXE/MSI analysis with architecture, profile, runtime signals and compatibility warnings
- resumable dependency steps stored in `state.json`
- failed dependencies are logged and do not destroy the environment
- required and optional runtime retries
- automatic WebView2 and .NET Desktop Runtime provider support
- clear handling for Java, Access Database Engine, LocalDB, drivers, anti-cheat, dongles, UWP and MSIX
- per-application start menu launchers with the correct prefix
- repair and environment removal in the same window

## Preserved application baselines

- LiMaD Study 6.5.0
- LiDrop 0.12.0-preview4
- synchronized original LiDrop app/dock icon

## GitHub OCI runtime compatibility fix

- GitHub image and ISO jobs use a pinned upstream `runc` 1.4.2 instead of the runner's incompatible `crun`
- the runtime binary is downloaded from the official opencontainers/runc release
- SHA-256 is verified before installation
- Buildah, Podman image inspection, the keyed bootc-image-builder wrapper and the ISO builder use the same runtime
- the theme probe uses the same verified runtime
- offline tests guard version, checksum and workflow wiring

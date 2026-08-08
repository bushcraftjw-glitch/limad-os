# LiMaD OS 3.0 – Ubuntu 26.04 LTS GitHub Starter

Dieses Repository ist der neue Ubuntu-basierte Build-Unterbau für LiMaD OS.

**Version:** `3.0.0-starter1-fix4`  
**Basis:** Ubuntu 26.04 LTS AMD64 / GNOME 50  
**Ziel:** Den bestätigten LiMaD-Desktop und die LiMaD-Programme möglichst verlustfrei von Bazzite/Fedora auf Ubuntu migrieren.

## Was der GitHub-Build erzeugt

Nach erfolgreichem Workflow stehen zwei Artefakte bereit:

1. `LiMaD-OS-3.0-ISO`
   - `LiMaD-OS-3.0.0-starter1-fix4-amd64.iso`
   - SHA256-Datei
   - Build-Info
2. `LiMaD-OS-3.0-App-Updates`
   - separate `.limad-update.zip` für alle im LiMaD-Updater geführten Komponenten
   - SHA256-Dateien

## Linux Starter

```bash
chmod +x START-GITHUB-BUILD-LINUX.sh
./START-GITHUB-BUILD-LINUX.sh
```

Der Starter prüft die Quellen und verwendet standardmäßig das bestehende Repository **`bushcraftjw-glitch/limad-os`**. Benutzer/Organisation und Repository sind bereits vorausgefüllt und können bei Bedarf überschrieben werden. Die Anmeldung läuft über **GitHub CLI (`gh`)**. Beim ersten Start öffnet sich einmalig die GitHub-Anmeldung im Browser; danach bleibt der Zugang dauerhaft über GitHub CLI gespeichert. Der Starter fragt nicht mehr bei jedem Lauf nach einem Token.

## macOS Starter

Im Finder `START-GITHUB-BUILD-MAC.command` doppelklicken oder im Terminal:

```bash
chmod +x START-GITHUB-BUILD-MAC.command
./START-GITHUB-BUILD-MAC.command
```

macOS baut die Linux-ISO nicht lokal. Der Starter lädt die Quellen nach GitHub; der eigentliche Ubuntu-ISO-Build läuft auf dem GitHub-Linux-Runner.

## Standard-Repository

```text
https://github.com/bushcraftjw-glitch/limad-os
```

Der Linux- und macOS-Starter setzen dieses Repository automatisch als `origin`.

## GitHub-Anmeldung

Der Starter verwendet `gh auth`. Falls noch keine Anmeldung gespeichert ist, wird automatisch `gh auth login --hostname github.com --git-protocol https --web` gestartet. Danach richtet `gh auth setup-git` die Git-Anmeldung ein. Zugangsdaten werden **nicht** in diesem Repository oder in der Remote-URL abgelegt.

Bei einem bereits vorhandenen Repository wird zuerst dessen `main`-Historie eingelesen und der neue LiMaD-Stand als Fast-Forward darauf aufgebaut. Dadurch wird der frühere Fehler `main -> main (fetch first)` vermieden, ohne die bestehende GitHub-Historie per Force-Push zu überschreiben.

## Wichtige 3.0-Regeln

- Kein Bazzite, rpm-ostree oder bootc im neuen Buildpfad.
- Bootsplash/Plymouth, Wallpaper und LiMaD-Icons sind per SHA256-Lock geschützt.
- Der alte Installer-Kontrastfehler wird nicht portiert: keine globale Installer-CSS und kein Weiß-auf-Weiß-Theme.
- LiMaD-Apps sind unabhängig vom OS aktualisierbar.
- Windows-Programme bleiben zunächst auf der alten integrierten 2.2.6-Linie.
- Steam, Lutris, GameMode, Gamescope und Vulkan-Runtimes werden nativ installiert.
- Steam verwaltet offizielles Proton; ProtonUp-Qt wird zusätzlich für GE-Proton bereitgestellt.
- Deskflow wird automatisch über Flathub eingerichtet.

## Quellstruktur

```text
.github/workflows/        GitHub Actions
build_files/              Ubuntu-RootFS/ISO-Build
system_files/             LiMaD Systemdateien und Apps
tools/                    Updatepaket- und GitHub-Starter-Werkzeuge
tests/                    statische Schutz- und Migrationsprüfungen
docs/                     Buildregeln und Referenzen
```

## Sicherheits-/Qualitätsstatus

Der Repository-Stand wird statisch validiert. Ein vollständiger Ubuntu-ISO-Build ist erst dann technisch bestätigt, wenn der GitHub-Workflow einmal erfolgreich durchgelaufen ist. `starter1` ist deshalb absichtlich noch kein RC oder finales LiMaD OS 3.0.

Siehe `docs/BUILD-LIST-DE.md` für die verbindliche Migrationsliste.

## Ubuntu-26.04-Layer-Aufbau

Ubuntu 26.04 Desktop verwendet mehrere aufeinander aufbauende SquashFS-Schichten. Der Builder bearbeitet deshalb **nicht** einen unvollständigen Layer isoliert: Er setzt `minimal.squashfs` und `minimal.standard.squashfs` als Overlay zu einem vollständigen RootFS zusammen. Alle LiMaD-Änderungen werden ausschließlich in den Standard-Upper-Layer geschrieben und anschließend wieder als `minimal.standard.squashfs` gepackt. Die originalen Sprach-, Live- und Enhanced-Secure-Boot-Layer bleiben darüber erhalten.

## FIX5 – APT/CD-ROM Build-Korrektur
Beim GitHub-ISO-Build wird vor dem ersten `apt-get update` eine aus der Ubuntu-Live-ISO geerbte `file:/cdrom`/`cdrom:`-Paketquelle gezielt deaktiviert. Netzwerkquellen bleiben unverändert aktiv. Die Korrektur besitzt einen eigenen Preflight-Test.

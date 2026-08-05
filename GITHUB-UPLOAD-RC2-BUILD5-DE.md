# GitHub-Upload – LiMaD OS 2.8.0 RC2 Build 5

## 1. Fullpack entpacken

```bash
cd ~/Downloads
unzip 'LiMaD-OS-2.8.0-RC2-BUILD5-LINOTES-STUDY-GITHUB-ISO-FULLPACK.zip'
cd 'LiMaD-OS-2.8.0-RC2-BUILD5-GNOME50-LiNotes1.0.0-preview1-Study6.6.2-LiSave1.0.0-preview2-LiLink1.0.0-preview3-LiDrop0.12.0-preview4-FULL'
```

## 2. Uploadskript starten

```bash
chmod +x START-GITHUB-BUILD-LINUX.sh
./START-GITHUB-BUILD-LINUX.sh
```

Beim vorhandenen Repository **Aktualisieren** auswählen. Das Skript führt zuerst die Offline-Prüfung aus und überträgt anschließend den vollständigen Quellstand.

## 3. GitHub Actions

1. Repository `bushcraftjw-glitch/limad-os` öffnen.
2. Unter **Actions** den automatisch gestarteten Lauf beobachten.
3. Den Theme-Schnelltest vollständig grün abwarten beziehungsweise manuell starten.
4. Danach **Build LiMaD OS (GNOME)** mit ISO-Erstellung ausführen.
5. Die erzeugte ISO unter **Artifacts** herunterladen.

## 4. Release

Tag:

```text
v2.8.0-rc2-build5-linotes
```

Titel:

```text
LiMaD OS 2.8.0 RC2 Build 5 – LiNotes & Study
```

Das Release als **Pre-release** markieren. Als Beschreibung kann `GITHUB-RELEASE-RC2-BUILD5.md` verwendet werden.

## 5. Release-Dateien

- fertige ISO aus GitHub Actions
- SHA-256 der fertigen ISO
- vollständiges GitHub-/ISO-Fullpack
- Fullpack-SHA-256
- `VALIDIERUNG-RC2-BUILD5-LINOTES-STUDY.txt`
- `LINOTES-STUDY-HARDWARETEST-BUILD5-DE.md`

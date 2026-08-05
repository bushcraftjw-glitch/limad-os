# LiMaD OS 2.8.0 RC2 Build 5 – LiNotes and Study Watchtower update

Complete GitHub and ISO build source package based on RC2 Build 4.

## Build 5

- Native GTK4 **LiNotes 1.0.0-preview1** application
- folders, quick notes, pinned notes, search, list/gallery views and autosave
- attachments stored as ordinary files
- trash/restore, TXT/Markdown/HTML/RTF/ENEX import and TXT/Markdown/HTML export
- official Apple Notes access through iCloud in the German Zen Browser
- LiSave 1.0.0-preview2 integration for the LiNotes database and attachments
- LiLink 1.0.0-preview3 handoff integration
- LiMaD Study 6.6.2 with smaller muted Watchtower questions and bold question numbers
- current-week Watchtower study article resolution using dated-text links, article numbers and weekly ordering

All Build 4 functionality remains included: German Zen as the primary browser, LiSave, persistent `Downloads/LiDrop`, LiLink, mandatory GStreamer/GTK4 integration, GNOME Remote Desktop and the unified Windows-programs icon.

## Validation

```bash
bash tests/validate.sh
```

Offline validation covers source syntax, LiNotes storage operations and imports, Study week resolution, updater integration and all inherited regression areas. Real hardware and final GitHub ISO tests remain required.

## Build

```bash
chmod +x START-GITHUB-BUILD-LINUX.sh
./START-GITHUB-BUILD-LINUX.sh
```

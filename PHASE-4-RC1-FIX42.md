# LiMaD OS 2.7.0 RC1 – FIX42

FIX42 behebt den OWL-Buildabbruch nach erfolgreichem Erzeugen des OWL-Binaries.

- Build-Revision: `gnome42-phase4-fix42`
- OWL wird gezielt mit `--target owl` gebaut.
- Die von OWL ungeachtet von `BUILD_TESTING=OFF` eingebundenen GoogleTest-Ziele werden nicht mehr kompiliert.
- Die nicht fatalen `netutils.c`-Warnungen bleiben unverändert; der OWL-Runtime-Build wird dadurch nicht blockiert.
- GitHub-Workflowdateien bleiben unverändert.

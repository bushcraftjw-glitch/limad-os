# LiMaD OS 2.7.0 RC1 – FIX43

FIX43 verhindert den wiederholten Abbruch der lokalen Clean-Project-Prüfung durch erzeugte Python-Bytecode-Dateien.

- Build-Revision: `gnome42-phase4-fix43`
- First-Login-Marker: `2.7.0-rc1-fix43`
- Flatpak-Marker: `default-flatpaks-fix43.done`
- `__pycache__`, `.pyc` und `.pyo` werden vor lokaler Prüfung und Upload entfernt.
- OWL wird weiterhin ausschließlich über das Ziel `owl` gebaut; GoogleTest wird nicht kompiliert.
- GitHub-Workflowdateien bleiben unverändert.

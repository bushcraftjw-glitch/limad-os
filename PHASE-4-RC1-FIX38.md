# LiMaD OS 2.7.0 RC1 – FIX39

FIX39 übernimmt FIX37 vollständig und behebt den Abbruch beim Bau des optionalen
AirDrop-Unterbaus OWL mit CMake 4.

## Ursache

Der gepinnte OWL-Quellstand enthält eine ältere GoogleTest-Unterkomponente, deren
`cmake_minimum_required()` noch eine Richtlinien-Kompatibilität unter 3.5
anfordert. CMake 4 hat diese alte Kompatibilität entfernt und beendet deshalb
die Konfiguration in `googletest/CMakeLists.txt`.

## Korrektur

- OWL wird mit `-DCMAKE_POLICY_VERSION_MINIMUM=3.5` konfiguriert.
- Nicht benötigte OWL/GoogleTest-Tests werden mit `-DBUILD_TESTING=OFF` deaktiviert.
- OWL und OpenDrop bleiben auf denselben unveränderlichen Commits gepinnt.
- Es wird kein Upstream-Repository verändert und nichts zu GitHub zurückgeschrieben.
- Zoom, YTMDesktop, EasyEffects, LiMaD Klang und alle Apps aus FIX37 bleiben unverändert enthalten.

## Abgrenzung

Die Offline-Prüfung bestätigt die korrekte Build-Verdrahtung und Shell-Syntax.
Der vollständige OWL-Compile kann nur im GitHub-Image-Build mit Netzwerk und der
aktuellen Bazzite-Basis bestätigt werden.

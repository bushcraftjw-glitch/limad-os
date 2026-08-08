# LiMaD OS – Installer-Schrift-Kontrast-Fix

## Ursache

Der produktspezifische GTK-Anaconda-Overlay setzte für allgemeine Fenster,
Schaltflächen und Eingabefelder eine sehr helle Schriftfarbe. Der vollständige
Anaconda-Basisstil behielt auf einzelnen Installationsdialogen jedoch helle
Hintergründe bei. Dadurch entstand weiße beziehungsweise fast weiße Schrift auf
weißem Hintergrund. Besonders betroffen waren die Beschriftungen der unteren
Schaltflächen und Teile des Partitionierungsdialogs.

## Korrektur

Der LiMaD-Overlay färbt keine allgemeinen GTK-Widgets mehr um. Er beschränkt
sich jetzt auf:

- LiMaD-Logo und Hintergrundbilder,
- dunkle Navigationsbereiche mit ausdrücklich weißer Schrift,
- violette Primärschaltflächen mit ausdrücklich weißer Schrift,
- markierte Tabellenzeilen und Fortschrittsanzeigen.

Alle normalen Dialoge, Beschriftungen, Eingabefelder und sekundären
Schaltflächen verwenden wieder den vollständigen Anaconda-Basisstil. Dadurch
bleibt die Schrift sowohl in hellen als auch in dunklen Installer-Ansichten
lesbar.

## Prüfung

`tests/test-installer-text-contrast.sh` verhindert, dass die problematischen
breiten Regeln für allgemeine Fenster, Labels, Buttons oder Eingabefelder
später wieder eingeführt werden.

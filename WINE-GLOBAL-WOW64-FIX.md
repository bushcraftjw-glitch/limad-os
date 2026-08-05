# Globaler Wine-/WoW64-Fix

- Wine 11 verwendet für den gemeinsamen LiMaD-Prefix jetzt WINEARCH=wow64.
- Vor jeder Installation wird die 32-Bit-WoW64-Komponente syswow64/regedit.exe geprüft.
- Ein vorhandener unvollständiger Prefix wird durch wineboot im WoW64-Modus repariert; andernfalls erscheint eine klare Rücksetzmeldung.
- corefonts wird nicht mehr automatisch für EXE/MSI-Profile installiert. Fedora Wine liefert wine-winefonts systemweit mit.
- NWS-Erkennung und das vorhandene dotnet-Profil bleiben unverändert.

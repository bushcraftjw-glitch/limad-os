# Aktueller Zusatzstand – LiDrop 0.12.0-preview5

- direkte Dateiübertragung zwischen zwei LiMaD-OS-Rechnern
- Kopplung in beide Richtungen mit einem sechsstelligen Code
- automatische Erkennung über Avahi
- Fortschrittsanzeige, Wiederaufnahmebasis und SHA-256-Endprüfung
- Smartphone- und Browserübertragung bleiben erhalten

# LiMaD OS 2.8.0 RC2 Build 3 – LiLink & GStreamer

- Windows-Programme-Icon über alle Raster- und SVG-Fallbacks vereinheitlicht.
- GStreamer samt Python-Bindings und GTK4-Sink als verbindliche Basisinstallation ergänzt.
- `gtk4paintablesink`, Playbin, PipeWire und Python-GI werden während des Builds hart geprüft.
- Bestehende Build-2-Funktionen einschließlich LiLink bleiben unverändert enthalten.

# LiMaD OS 2.8.0 RC2 Build 2 – LiLink

- neue System-App **LiLink 1.0.0-preview2**
- automatische Erkennung anderer LiMaD-OS-Geräte über Avahi
- einmalige TLS-gesicherte Kopplung mit sechsstelliger Bestätigung
- native GNOME-RDP-Bildschirmübernahme über FreeRDP
- neues GNOME-Panel-Symbol mit großem und kleinem Monitor
- verschlüsselte Dateiübertragung mit Fortsetzung und SHA-256-Endprüfung
- Handoff-Grundgerüst für LiMaD Study, LiMaD Cut, LibreOffice, Medien und Zen Browser
- Deskflow-Integration für gemeinsame Maus und Tastatur
- Updateunterstützung über LiMaD Update; Systemkomponenten über rpm-ostree
- bestehende TV-Casting-App sichtbar in **LiMaD auf TV übertragen** umbenannt

## Testgrenze

Die Quell-, Syntax-, Paket-, Integrations- und Sicherheitstests laufen offline. Reale RDP-, Wayland-, Mehrmonitor- und Zwei-Geräte-Tests erfordern Notebook und iMac und sind deshalb separat dokumentiert.

# LiMaD OS – Änderungsprotokoll

## 2.8.0 RC1 Build 9 – Windows-Programme 2.0

- Vorhandene App `de.limad.WindowsApps` vollständig ersetzt, ohne zweiten Menüeintrag.
- Bestehendes Windows-Programme-Dock-Icon unverändert beibehalten.
- Ein Hauptfenster mit Installieren, Meine Programme, Reparieren, Umgebungen, Protokoll und Einstellungen.
- Eigener Wine-WoW64-Prefix pro Anwendung statt einer gemeinsamen Umgebung.
- EXE-/MSI-Analyse für Architektur, Profil, Runtimes und bekannte Wine-Grenzen.
- Wiederaufnehmbare Abhängigkeitsschritte mit Statusdatei und Wiederholungen.
- Abhängigkeitsfehler werden protokolliert; standardmäßig startet der Hauptinstaller trotzdem.
- Automatische Anbieter für WebView2 und .NET Desktop Runtime 6/8/9.
- Klare Behandlung für Java, Access Database Engine, LocalDB, Treiber, Anti-Cheat, Dongles, UWP und MSIX.
- Reparatur, Start, Menüeintrag und Löschen einer Umgebung innerhalb derselben App.
- LiMaD Study 6.5.0 und LiDrop 0.12.0-preview4 bleiben enthalten.

## 2.8.0 RC1 Build 2 – Bildschirmfreigabe

- Neue native Anwendung **LiMaD Bildschirmfreigabe 1.0.0**.
- Google TV und Chromecast über GNOME Network Displays.
- Samsung- und andere Miracast-Empfänger über dieselbe native GNOME-Geräteauswahl.
- Experimentelle Apple-TV-/AirPlay-Übertragung mit festgeschriebenem Doubletake v0.4.0, Geräteerkennung, optionaler PIN und Audio-Schalter.
- AirPlay bleibt standardmäßig inaktiv; Firewallports 60000-60010 werden nur temporär und nie permanent geöffnet.
- Eigene App-Updates für `de.limad.ScreenShare` sind ab Build 2 möglich.
- Neue Offline-Prüfung für Protokolltrennung, Source-Pinning, Polkit, Firewallhärtung, App-Paket und Icon.

## 2.7.0 RC1 FIX50

- LiMaD Study 6.2.2: vollständige Katalog-Sprachauswahl, sichtbare Literatursprache und einheitliches JW-/Bibel-Icon.
- LiMaD Cut 1.1.4: geschlossene Halbkugel für Boolean-Vereinigungen.
- First-Login-Hinweis für zusätzliche Programme.
- Terminal stabil an drittletzter Dock-Position.
- FIX49-Bootscreen, Installer und LiMaD Klang bleiben erhalten.

# FIX49 – bestätigter Bootscreen-Ablauf und robuster Audio-Fallback

- Automatisiert den auf echter Hardware erfolgreichen Befehl `rpm-ostree initramfs --enable`.
- Startet die einmalige Plymouth-Vorbereitung 45 Sekunden nach dem ersten installierten Boot.
- Schreibt den Erfolg in `/var/lib/limad/plymouth-initramfs-fix49.log` und fordert genau einen Neustart an.
- Startet EasyEffects 8 mit `--hide-window` statt des veralteten `--gapplication-service`.
- Sucht den lokalen Server sowohl direkt in `$XDG_RUNTIME_DIR` als auch in Flatpak-Unterordnern.
- Ergänzt einen echten Preset-Kompatibilitätsmodus, sodass Bass, Mitten und Höhen auch ohne erreichbaren Socket angewendet werden.
- Verhindert, dass der Login-Helfer geänderte LiMaD-Klangwerte wieder mit dem Neutral-Preset überschreibt.
- Synchronisiert alle aktiven Marker auf FIX49.

# FIX48 – Plymouth-Bootscreen: Ursache endlich gefunden

- Behebt den eigentlichen Grund, warum der Bootscreen seit FIX30 nie aktiviert
  wurde: `limad-plymouth-initramfs` prüfte `[[ -d /run/ostree-booted ]]`.
  `/run/ostree-booted` ist bei OSTree/bootc jedoch eine leere Marker-**Datei**,
  kein Verzeichnis. Der `-d`-Test war auf jedem echten System immer falsch,
  das Skript brach sofort mit „not an OSTree boot“ ab – **bevor**
  `rpm-ostree kargs` oder `rpm-ostree initramfs --enable` je liefen.
- Korrigiert auf `[[ -e /run/ostree-booted ]]`.
- Neuer Regressionstest in `tests/test-fix48-runtime-fixes.sh` verbietet
  künftig ausdrücklich einen `-d`-Test auf diesem Pfad.
- Keine weiteren funktionalen Änderungen gegenüber FIX47 (Klang, Installer-
  Branding, GitHub-Upload unverändert).
- Synchronisiert alle aktiven Marker auf FIX48.

## Ablauf nach der Installation (unverändert seit FIX46/47)

1. Erster Start des installierten Systems: noch kein Bootscreen (Basis-
   Initramfs aus dem Bazzite-Abbild).
2. Nach ca. 90 Sekunden bereitet ein Hintergrunddienst Kernel-Argumente und
   Initramfs vor (jetzt tatsächlich, da der Guard nicht mehr blockiert).
3. Eine Desktop-Benachrichtigung fordert einmalig zum Neustart auf.
4. Ab dem darauffolgenden Neustart sollte der LiMaD-Bootscreen erscheinen.

Kontrolle nach ca. 2 Minuten:
`sudo cat /var/lib/limad/plymouth-initramfs-fix48.log`
Am Ende sollte stehen: „One restart is required to boot the new deployment
and show the LiMaD splash.“

## Vorgänger

# FIX47 – Laufzeitreparaturen für Klang, Installer und Bootscreen

- Behebt die falsche EasyEffects-Anzeige `0.0.0`: Die Version wird jetzt über
  die echte Flatpak-App-Liste ermittelt; ein nicht vorhandenes
  `--show-version` wird nicht mehr verwendet.
- LiMaD Klang prüft den EasyEffects-Socket und liest geänderte Bass- und
  Höhenwerte zurück, bevor Erfolg gemeldet wird.
- Baut das Installerdesign über den offiziell vorgesehenen Cockpit-/Anaconda-
  WebUI-Brandingpfad für `limad`, `bazzite` und `fedora` ein.
- Verwendet im GTK-Fallback die echten Anaconda-Klassen und behält das komplette
  Anaconda-Basisstylesheet bei.
- Prüft die Inhalte des erzeugten `product.img`, bevor die ISO verändert wird.
- Macht die Plymouth-Aktivierung transaktionssicher, protokolliert Fehler und
  zeigt nach erfolgreicher Vorbereitung einen Neustarthinweis an.
- Verwendet weiterhin ausschließlich `rpm-ostree initramfs --enable`; kein
  `dracut --force`.
- Prüft GitHub-Schreibrechte vor Commit und Upload.
- Entfernt die automatische GitHub-Repository-Löschung vollständig.
- Synchronisiert alle aktiven Marker auf FIX47.

## Unverändert

- Bazzite-GNOME-/AMD-Basis
- alle LiMaD-Apps und Flatpak-Vorgaben
- Wine, Gaming, AirDrop/OWL und Anycubic
- `.github/workflows/build.yml`
- `.github/workflows/theme-probe.yml`

## Vorgänger

FIX46 machte die lokale macOS-Prüfung unabhängig von einer installierten
Pillow-Bibliothek und stellte das Standardziel auf
`bushcraftjw-glitch/limad-os` um.

## 2.8.0 RC1 Build 4

- basiert auf Build 2 mit LiMaD Bildschirmfreigabe
- LiMaD Study 6.3.1 direkt als Systemversion integriert
- LiDrop 0.12.0-preview1 direkt als Systemversion integriert
- LiDrop bleibt im Anwendungsmenü und in der Standard-Dock-Reihenfolge
- neuer Kontextmenüpunkt zum direkten Öffnen des LiDrop-Ordners
- native GNOME-Statusanzeige für LiDrop mit Schnellzugriff und Dienststeuerung

## 2.8.0 RC1 Build 6
- LiDrop-App-Icon systemweit auf das originale blaue App-Design mit weißen Sende-/Empfangspfeilen vereinheitlicht.
- Menü-, Dock-, Such-, Fenster-, Benachrichtigungs- und PWA-Icons aktualisiert.

# Build 7 – GNOME 50 Statusleiste und robuste Plymouth-Transaktion

- LiDrop-Statussymbol unterstützt GNOME Shell 50.3 ausdrücklich.
- Logo Menu erhält einen gezielten GNOME-50-Fix für `vfunc_event`.
- Plymouth wartet bei parallelen rpm-ostree-Transaktionen und verwendet den bestätigten Initramfs-Ablauf.

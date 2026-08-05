# LiMaD OS 2.7.0 RC1 – FIX14

FIX14 verwendet den neuen GHCR-Paketnamen `limad-os-gnome-fix14`.
Dadurch wird ein frisches GitHub-Container-Paket erzeugt und eine alte,
paketspezifische `write_package`-Sperre von `limad-os-gnome` umgangen.

Zusätzlich erkennt der Workflow die GHCR-Fehlertexte
`permission_denied: write_package` und `denied: permission_denied`
unmittelbar und zeigt die passende GitHub-Einstellung an.

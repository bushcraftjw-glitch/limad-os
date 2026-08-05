# LiMaD OS 2.7.0 RC1 – FIX18 aktuelles Anaconda-ISO-Layout

Der Builderlauf aus FIX17 war erfolgreich und lieferte Exitcode 0. Der anschließende LiMaD-Prüfer brach ab, weil er vor dem Branding zwingend `/images/product.img` erwartete.

Das aktuelle Fedora-44-Anaconda-ISO des verwendeten `bootc-image-builder` enthält als Installer-Stage2 `/images/install.img`. Ein `product.img` ist optional und wird erst für das LiMaD-Installerbranding ergänzt.

FIX18:

- prüft in der Quell-ISO `/images/install.img` statt eines noch nicht vorhandenen `product.img`,
- kontrolliert `stage2.mainimage = images/install.img` und dessen SHA-256-Metadatum in `.treeinfo`,
- erzeugt ein neues LiMaD-`product.img`, wenn die Quell-ISO keines enthält,
- erhält und erweitert ein vorhandenes `product.img` bei kompatiblen Builderversionen,
- fügt das LiMaD-Overlay in die finale ISO ein und aktualisiert `.treeinfo`,
- verlangt in der finalen ISO sowohl `images/install.img` als auch das LiMaD-`images/product.img`,
- ersetzt unzuverlässige `xorriso -ls`-Existenztests durch exakte Dateisuche.

Buildrevision: `gnome42-phase4-fix18`  
GHCR-Paket: `limad-os-gnome-fix16`

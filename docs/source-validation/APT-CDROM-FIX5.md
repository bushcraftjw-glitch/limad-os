# FIX5 – Ubuntu Live-Medium APT source

The Ubuntu 26.04 desktop ISO can expose a live-media package source such as
`file:/cdrom` / `cdrom:` inside the extracted root filesystem. In GitHub Actions
there is no mounted `/cdrom`, so `apt-get update` exits with code 100 even while
all network repositories are reachable.

FIX5 adds `build_files/10-apt-live-media-sources.sh`, executed before the first
`apt-get update`. It disables only live-media sources in legacy `.list` files
and deb822 `.sources` stanzas, preserves network mirrors, and fails closed if an
active live-media URI survives.

`tests/validate.sh` includes a unit test for both legacy and deb822 source forms.

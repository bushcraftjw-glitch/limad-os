# LiDrop Exact Icon Fix

The LiDrop header and GNOME dock now use the same canonical icon asset.

- Canonical source: `system_files/usr/share/limad-drop/web/assets/icon-512.png`
- Header rendering: the LiDrop `.brand-mark` loads this asset directly.
- Desktop identity: `de.limad.Drop.desktop` uses `Icon=de.limad.Drop`.
- LiMaD and hicolor icon themes contain derivatives of the canonical asset.
- All 512x512 launcher copies are byte-identical to the app asset.
- `tests/test-lidrop-exact-icon.sh` verifies hashes, icon identity and PNG dimensions.

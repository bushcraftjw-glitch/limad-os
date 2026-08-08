# LiMaD OS 3.0 – GDM usr-merge Fix (FIX7)

Ubuntu uses usr-merge, so a service found as `/lib/systemd/system/gdm3.service`
may canonicalize to `/usr/lib/systemd/system/gdm3.service` via `readlink -f`.

FIX6 compared the canonical `display-manager.service` target to the original,
non-canonical candidate string. This could report a false failure even when the
link pointed at the same GDM service.

FIX7 canonicalizes the selected GDM unit before creating and verifying the
`display-manager.service` symlink. The verification now prints expected and
actual canonical targets on failure.

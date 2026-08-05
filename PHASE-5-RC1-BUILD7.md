# LiMaD OS 2.8.0 RC1 – Build 7

Build 7 is based on Build 6 and fixes issues confirmed on GNOME Shell 50.3.

- LiDrop status extension declares GNOME Shell 50 support and no longer remains OUT OF DATE.
- LiDrop activation detects incompatible/error states without 18 pointless retries.
- Logo Menu's unsupported `super.vfunc_event()` fallback is patched to event propagation for GNOME 50.
- Plymouth keeps the hardware-confirmed rpm-ostree path and retries safely when another rpm-ostree transaction is active.
- Plymouth preparation starts after 120 seconds to reduce collisions with first-boot Bazzite transactions.

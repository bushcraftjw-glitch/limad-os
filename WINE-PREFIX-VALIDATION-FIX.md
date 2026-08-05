# Wine Prefix Validation Fix

- Fixes false failure after successful wineboot in Wine 11 WoW64.
- Prefix readiness no longer depends on syswow64/regedit.exe.
- Readiness now checks system.reg, user.reg and system32, followed by the existing executable health check.
- WINEARCH=wow64 is forced for every managed prefix.
- Windows-Programme version 2.0.1.

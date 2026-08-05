#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
grep -Eq 'LIMAD_OS_VERSION="(2\.[6-9]|[3-9][0-9]*)\.' "$ROOT/build_files/versions.env"
grep -q 'Öffentliche Update-Erreichbarkeit prüfen' "$ROOT/.github/workflows/build.yml"
grep -q 'skopeo inspect --authfile' "$ROOT/.github/workflows/build.yml"
grep -q '"nws"' "$ROOT/system_files/usr/share/limad-windows/recipe_engine.py"
grep -q '"dotnet48"' "$ROOT/system_files/usr/share/limad-windows/recipe_engine.py"
grep -q 'def apply_plan' "$ROOT/system_files/usr/share/limad-windows/installer.py"
grep -q 'dotnet48_ready' "$ROOT/system_files/usr/share/limad-windows/installer.py"
grep -q 'wait_for_installer_processes' "$ROOT/system_files/usr/share/limad-windows/installer.py"
grep -q 'max_seconds: int = 120' "$ROOT/system_files/usr/share/limad-windows/installer.py"
test -x "$ROOT/system_files/usr/local/bin/limad-system-update"
test -f "$ROOT/system_files/usr/share/applications/de.limad.SystemUpdate.desktop"
python3 - "$ROOT/system_files/usr/share/limad-windows/installer.py" "$ROOT/system_files/usr/share/limad-windows/recipe_engine.py" <<'PYCOMPILE'
import py_compile
import sys
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    for index, source in enumerate(sys.argv[1:], start=1):
        py_compile.compile(
            source,
            cfile=f"{tmp}/module-{index}.pyc",
            doraise=True,
        )
PYCOMPILE
echo 'Phase 2 update and NWS integration: PASS'

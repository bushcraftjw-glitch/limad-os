#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
source build_files/versions.env
[[ "$LIMAD_BUILD_REVISION" =~ ^gnome-rc2-build(4|5)$ || "$LIMAD_BUILD_REVISION" =~ ^gnome42-phase4-fix(36|37|38|39|41|42|43|44|45|46|47|48|49|50)$ ]]
for f in system_files/usr/local/bin/limad-app-runtime-repair system_files/usr/local/bin/limad-app-integrity-check system_files/usr/lib/systemd/user/limad-app-runtime-repair.service; do [[ -s "$f" ]]; done
grep -q 'enable limad-app-runtime-repair.service' build_files/70-limad-apps.sh
grep -q 'RuntimeMaxSec=600' system_files/usr/lib/systemd/system/limad-awdl@.service
grep -q 'RuntimeMaxSec=600' system_files/usr/lib/systemd/user/limad-opendrop-receive.service
grep -q 'Restart=no' system_files/usr/lib/systemd/system/limad-awdl@.service
grep -q 'Restart=no' system_files/usr/lib/systemd/user/limad-opendrop-receive.service
python3 - <<'PYCODE'
from pathlib import Path
for name in ['system_files/usr/local/bin/limad-app-runtime-repair','system_files/usr/local/bin/limad-app-integrity-check']:
 compile(Path(name).read_text(encoding='utf-8'),name,'exec')
PYCODE
# GitHub workflow files remain under the FIX22 frozen hash protection.
python3 - <<'PYCODE'
import json
from pathlib import Path
manifest=json.loads(Path('tests/fix22-protected-files.json').read_text())
paths={e['path'] for e in manifest['entries']}
assert '.github/workflows/build.yml' in paths
assert '.github/workflows/theme-probe.yml' in paths
PYCODE
echo "FIX36 Laufzeitreparatur, Integritätsprüfung und AirDrop-Zeitbegrenzung: PASS"

#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
fail(){ echo "FATAL: $*" >&2; exit 1; }
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

echo '[APP 1/7] Updater registry + required payload files'
python3 - <<'PY'
import json
from pathlib import Path
root=Path('system_files')
apps=json.loads(Path('system_files/usr/share/limad-updater/apps.json').read_text())['apps']
if len(apps) != 11:
    raise SystemExit(f'expected 11 updater apps, got {len(apps)}')
for app in apps:
    aid=app['app_id']
    launcher=root / app['launcher'].lstrip('/')
    if not launcher.is_file():
        raise SystemExit(f'{aid}: launcher missing: {app["launcher"]}')
    if aid == 'de.limad.AnycubicSlicerNext':
        continue
    sroot=root / app['system_root'].lstrip('/')
    if not sroot.is_dir():
        raise SystemExit(f'{aid}: system root missing: {app["system_root"]}')
    for rel in app.get('required',[]):
        if not (sroot/rel).exists():
            raise SystemExit(f'{aid}: required payload missing: {rel}')
    vf=app.get('system_version_file')
    if vf:
        p=root/vf.lstrip('/')
        if not p.is_file() or not p.read_text().strip():
            raise SystemExit(f'{aid}: VERSION missing/empty: {vf}')
print('Updater apps checked:', len(apps))
PY

echo '[APP 2/7] LiMaD Python source syntax'
python3 - <<'PY'
from pathlib import Path
roots=[
Path('system_files/usr/share/limad-study'), Path('system_files/usr/share/limad-drop'),
Path('system_files/usr/share/limad-link'), Path('system_files/usr/share/limad-notes'),
Path('system_files/usr/share/limad-save'), Path('system_files/usr/share/limad-screen-share'),
Path('system_files/usr/share/limad-klang'), Path('system_files/usr/share/limad-windows'),
Path('system_files/usr/share/limad-updater')]
count=0
for root in roots:
    for p in root.rglob('*.py'):
        compile(p.read_text(encoding='utf-8'), str(p), 'exec')
        count += 1
print('Python files syntax-checked:', count)
PY

echo '[APP 3/7] Version consistency: payload ↔ release manifest'
python3 - <<'PY'
import json
from pathlib import Path
apps=json.loads(Path('system_files/usr/share/limad-updater/apps.json').read_text())['apps']
manifest=json.loads(Path('RELEASE-MANIFEST.json').read_text())
vers={a['app_id']:a['version'] for a in manifest['independent_updates']['apps']}
root=Path('system_files')
for a in apps:
    aid=a['app_id']
    if aid not in vers: raise SystemExit(f'{aid}: missing from release manifest')
    if 'system_version_file' in a:
        actual=(root/a['system_version_file'].lstrip('/')).read_text().strip()
    else:
        actual=a['system_version']
    if actual != vers[aid]:
        raise SystemExit(f'{aid}: payload={actual}, manifest={vers[aid]}')
print('Versions matched:', len(apps))
PY

echo '[APP 4/7] Updater service references'
python3 - <<'PY'
import json
from pathlib import Path
apps=json.loads(Path('system_files/usr/share/limad-updater/apps.json').read_text())['apps']
base=Path('system_files/usr/lib/systemd/user')
for a in apps:
    for svc in a.get('restart_user_services',[]):
        if not (base/svc).is_file():
            raise SystemExit(f'{a["app_id"]}: referenced service missing: {svc}')
print('Service references: OK')
PY

echo '[APP 5/7] Anycubic vendored package integrity'
(cd build_files/vendor/anycubic && sha256sum -c SHA256SUMS >/dev/null)
source build_files/versions.env
cat build_files/vendor/anycubic/anycubicslicernext_${ANYCUBIC_DEB_VERSION}_amd64.deb.part00 \
    build_files/vendor/anycubic/anycubicslicernext_${ANYCUBIC_DEB_VERSION}_amd64.deb.part01 > "$TMP/anycubic.deb"
printf '%s  %s\n' "$ANYCUBIC_SOURCE_SHA256" "$TMP/anycubic.deb" | sha256sum -c - >/dev/null

echo '[APP 6/7] Existing standalone update ZIP integrity (LiDrop/LiSave)'
python3 - <<'PY'
import hashlib,json,zipfile
from pathlib import Path
for zpath in sorted(Path('updates').glob('*.limad-update.zip')):
    with zipfile.ZipFile(zpath) as z:
        m=json.loads(z.read('limad-update.json'))
        for f in m.get('files',[]):
            data=z.read(f['path'])
            got=hashlib.sha256(data).hexdigest()
            if got != f['sha256']:
                raise SystemExit(f'{zpath.name}: checksum mismatch: {f["path"]}')
        if not any(n.startswith('payload/') for n in z.namelist()):
            raise SystemExit(f'{zpath.name}: no payload')
        print(zpath.name, m['app_id'], m['version'])
PY

echo '[APP 7/7] Rebuild + validate source-based update ZIPs'
mkdir -p "$TMP/updates"
bash tools/build-all-updates.sh "$ROOT/system_files" "$TMP/updates" >/dev/null 2>"$TMP/update-build.err"
if [[ -s "$TMP/update-build.err" ]]; then
  if grep -vFx 'WARNUNG: Anycubic Slicer Next fehlt in RootFS: /usr/lib/limad/apps/anycubic-slicer-next' "$TMP/update-build.err" | grep -q .; then
    cat "$TMP/update-build.err" >&2
    fail 'unexpected warning while rebuilding source updates'
  fi
fi
echo 'Anycubic update payload is validated separately from the vendored DEB and is created after rootfs extraction.'
python3 - "$TMP/updates" <<'PY'
import hashlib,json,sys,zipfile
from pathlib import Path
out=Path(sys.argv[1])
zips=sorted(out.glob('*.limad-update.zip'))
# Anycubic is installed from its vendored DEB only during rootfs customization,
# so 10 source-based updates are expected at this preflight stage.
if len(zips) != 10:
    raise SystemExit(f'expected 10 source update ZIPs before Anycubic extraction, got {len(zips)}')
for p in zips:
    with zipfile.ZipFile(p) as z:
        m=json.loads(z.read('limad-update.json'))
        for f in m.get('files',[]):
            got=hashlib.sha256(z.read(f['path'])).hexdigest()
            if got != f['sha256']:
                raise SystemExit(f'{p.name}: checksum mismatch {f["path"]}')
print('Rebuilt update ZIPs validated:', len(zips))
PY

echo 'OK: LiMaD app/update preflight passed.'

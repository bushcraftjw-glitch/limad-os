#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
from pathlib import Path
import hashlib
import json
import stat
import sys
manifest = json.loads(Path('tests/fix22-protected-files.json').read_text())
expected_base = '56e2e53416a772b7753e7af45d0fbc969bea61e372ae657fc599cc04ea6b4a5e'
if manifest.get('base_sha256') != expected_base:
    raise SystemExit('FIX22 PROTECTION FAILED: wrong source archive checksum recorded')
errors=[]
overrides={item['path']: item for item in manifest.get('approved_overrides_280_build2', [])}
overrides.update({item['path']: item for item in manifest.get('approved_overrides_280_build9', [])})
overrides.update({item['path']: item for item in manifest.get('approved_overrides_rc2_build1', [])})
overrides.update({item['path']: item for item in manifest.get('approved_overrides_rc2_build2', [])})
overrides.update({item['path']: item for item in manifest.get('approved_overrides_rc2_build3', [])})
overrides.update({item['path']: item for item in manifest.get('approved_overrides_rc2_build4', [])})
overrides.update({item['path']: item for item in manifest.get('approved_overrides_rc2_build5', [])})
overrides.update({item['path']: item for item in manifest.get('approved_overrides_rc2_build5_current', [])})
for entry in manifest.get('entries', []):
    expected=overrides.get(entry['path'], entry)
    path=Path(entry['path'])
    if not path.is_file():
        errors.append(f'{path}: missing')
        continue
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    mode=oct(stat.S_IMODE(path.stat().st_mode))
    if digest != expected['sha256']:
        errors.append(f'{path}: content changed')
    if mode != expected['mode']:
        errors.append(f'{path}: mode {mode}, expected {expected["mode"]}')
if errors:
    for error in errors[:50]:
        print('FIX22 PROTECTION FAILED:', error, file=sys.stderr)
    raise SystemExit(1)
print(f'FIX22 protected baseline with approved LiMaD OS 2.8.0 RC2 Build 5 Current overrides: PASS ({len(manifest["entries"])} files, {len(overrides)} overrides)')
PY

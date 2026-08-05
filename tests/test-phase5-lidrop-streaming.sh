#!/usr/bin/env bash
set -Eeuo pipefail
export PYTHONDONTWRITEBYTECODE=1
cd "$(dirname "$0")/.."

APP=system_files/usr/share/limad-drop/web/app.js
BACKEND=system_files/usr/share/limad-drop/limad_dropd.py

[[ "$(cat system_files/usr/share/limad-drop/VERSION)" == "0.12.0-preview5" ]]
grep -q 'function uploadBodyXHR' "$APP"
grep -q 'new XMLHttpRequest' "$APP"
grep -q "X-LiMaD-Upload-Mode.*stream" "$APP"
grep -q 'file.slice(offset)' "$APP"
grep -q 'Date.now() - lastActivity > 45000' "$APP"
! grep -Eq '256[[:space:]]*\*[[:space:]]*1024|chunkSize[[:space:]]*=' "$APP"
grep -q 'UPLOAD_REQUEST_LIMIT = DEFAULT_MAX_SIZE' "$BACKEND"
grep -q 'self.connection.settimeout(90)' "$BACKEND"
grep -q 'self.send_header("Connection", "close")' "$BACKEND"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
HOME="$TMP/home" XDG_RUNTIME_DIR="$TMP/runtime" python3 - <<'PY'
import importlib.util
import io
import os
from pathlib import Path

Path(os.environ['HOME']).mkdir(parents=True)
Path(os.environ['XDG_RUNTIME_DIR']).mkdir(parents=True)
source = Path('system_files/usr/share/limad-drop/limad_dropd.py')
spec = importlib.util.spec_from_file_location('limad_dropd_stream_test', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
store = module.Store()
size = 17 * 1024 * 1024 + 9
transfer = store.init_transfer('outbound', None, {
    'name': 'stream-test.bin', 'size': size, 'lastModified': 28001, 'deviceId': ''
})
reader = io.BytesIO(b'Z' * size)
result = store.append_chunk(transfer['id'], 0, reader, size)
assert result['received'] == size, result
row = store.transfer(transfer['id'])
assert Path(row['temp_path']).stat().st_size == size
print('LiDrop streamed request >16 MiB: PASS')
PY

echo "LiDrop WebKitGTK streaming upload and 256-KiB stall regression: PASS"

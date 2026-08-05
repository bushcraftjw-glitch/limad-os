#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DAEMON="$ROOT/system_files/usr/share/limad-drop/limad_dropd.py"
[[ "$(cat "$ROOT/system_files/usr/share/limad-drop/VERSION")" == "0.12.0-preview5" ]]
grep -Fq 'CREATE TABLE IF NOT EXISTS peers' "$DAEMON"
grep -Fq '/api/peer/pair' "$DAEMON"
grep -Fq 'push_transfer_to_peer' "$DAEMON"
grep -Fq 'LiMaD OS zu LiMaD OS' "$ROOT/system_files/usr/share/limad-drop/web/app.js"

tmp="$(mktemp -d)"
trap 'jobs -p | xargs -r kill 2>/dev/null || true; rm -rf "$tmp"' EXIT
mkdir -p "$tmp/a/run" "$tmp/b/run" "$tmp/a/home" "$tmp/b/home"
LIMAD_DROP_DISABLE_NOTIFICATIONS=1 LIMAD_DROP_DISABLE_OPEN=1 LIMAD_DROP_PORT=48777 HOME="$tmp/a/home" XDG_RUNTIME_DIR="$tmp/a/run" XDG_CONFIG_HOME="$tmp/a/home/.config" XDG_DATA_HOME="$tmp/a/home/.local/share" XDG_CACHE_HOME="$tmp/a/home/.cache" XDG_STATE_HOME="$tmp/a/home/.local/state" python3 "$DAEMON" serve >"$tmp/a.log" 2>&1 &
pa=$!
LIMAD_DROP_DISABLE_NOTIFICATIONS=1 LIMAD_DROP_DISABLE_OPEN=1 LIMAD_DROP_PORT=48778 HOME="$tmp/b/home" XDG_RUNTIME_DIR="$tmp/b/run" XDG_CONFIG_HOME="$tmp/b/home/.config" XDG_DATA_HOME="$tmp/b/home/.local/share" XDG_CACHE_HOME="$tmp/b/home/.cache" XDG_STATE_HOME="$tmp/b/home/.local/state" python3 "$DAEMON" serve >"$tmp/b.log" 2>&1 &
pb=$!
for _ in $(seq 1 80); do [[ -s "$tmp/a/run/limad-drop.json" && -s "$tmp/b/run/limad-drop.json" ]] && break; sleep .1; done
python3 - "$tmp" <<'PYTEST'
import hashlib, json, pathlib, time, urllib.request, sys
base = pathlib.Path(sys.argv[1])
def runtime(side): return json.loads((base/side/'run/limad-drop.json').read_text())
def call(url, method='GET', payload=None, admin=''):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {'Content-Type':'application/json'} if payload is not None else {}
    if admin: headers['X-LiMaD-Admin'] = admin
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=20) as r: return json.loads(r.read())
a, b = runtime('a'), runtime('b')
state_b = call('http://127.0.0.1:48778/api/admin/state', admin=b['adminToken'])
paired = call('http://127.0.0.1:48777/api/admin/peer/connect', 'POST', {'address':'http://127.0.0.1:48778','code':state_b['pairing']['code']}, a['adminToken'])
peer_id = 'peer:' + paired['peer']['id']
state_a = call('http://127.0.0.1:48777/api/admin/state', admin=a['adminToken'])
state_b2 = call('http://127.0.0.1:48778/api/admin/state', admin=b['adminToken'])
assert len(state_a['peers']) == 1 and len(state_b2['peers']) == 1
content = (b'LiDrop OS-to-OS preview5\n' * 300000)
init = call('http://127.0.0.1:48777/api/upload/init', 'POST', {'direction':'outbound','deviceId':peer_id,'name':'os-to-os-test.bin','size':len(content),'lastModified':123}, a['adminToken'])
offset = 0
while offset < len(content):
    chunk = content[offset:offset+1024*1024]
    req = urllib.request.Request(f"http://127.0.0.1:48777/api/upload/{init['id']}?offset={offset}", data=chunk, headers={'X-LiMaD-Admin':a['adminToken'],'Content-Type':'application/octet-stream'}, method='PUT')
    with urllib.request.urlopen(req, timeout=30) as r: result=json.loads(r.read())
    offset = result['received']
call(f"http://127.0.0.1:48777/api/upload/{init['id']}/complete", 'POST', {}, a['adminToken'])
target = base/'b/home/Downloads/LiDrop/os-to-os-test.bin'
for _ in range(120):
    if target.exists() and target.stat().st_size == len(content): break
    time.sleep(.1)
assert target.read_bytes() == content
for _ in range(80):
    transfer = next(x for x in call('http://127.0.0.1:48777/api/admin/state', admin=a['adminToken'])['transfers'] if x['id']==init['id'])
    if transfer['status'] in {'downloaded','error'}: break
    time.sleep(.1)
assert transfer['status'] == 'downloaded', transfer
assert transfer['sha256'] == hashlib.sha256(content).hexdigest()
print('LiDrop bidirectional pairing and direct OS-to-OS transfer: PASS')
PYTEST
kill "$pa" "$pb" 2>/dev/null || true
wait "$pa" "$pb" 2>/dev/null || true
echo "LiDrop 0.12.0-preview5 OS-to-OS integration: PASS"

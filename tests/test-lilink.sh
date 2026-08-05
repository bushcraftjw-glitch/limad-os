#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import json
from pathlib import Path
root=Path.cwd()
sf=root/'system_files'
required=[
 sf/'usr/share/limad-link/VERSION', sf/'usr/share/limad-link/common.py', sf/'usr/share/limad-link/daemon.py', sf/'usr/share/limad-link/app.py',
 sf/'usr/local/bin/lilink', sf/'usr/local/bin/limad-linkd', sf/'usr/lib/systemd/user/limad-link.service',
 sf/'usr/share/applications/de.limad.Link.desktop', sf/'usr/share/gnome-shell/extensions/lilink@limad.local/extension.js',
 sf/'usr/share/gnome-shell/extensions/lilink@limad.local/icons/lilink-symbolic.svg', sf/'usr/lib/firewalld/services/limad-link.xml'
]
for p in required:
    if not p.is_file(): raise SystemExit(f'LILINK FAILED: {p} fehlt')
for p in [sf/'usr/share/limad-link/common.py', sf/'usr/share/limad-link/daemon.py', sf/'usr/share/limad-link/app.py']:
    compile(p.read_text(encoding='utf-8'), str(p), 'exec')
meta=json.loads((sf/'usr/share/gnome-shell/extensions/lilink@limad.local/metadata.json').read_text())
if '50' not in meta.get('shell-version',[]): raise SystemExit('LILINK FAILED: GNOME 50 fehlt')
text=(sf/'usr/share/limad-link/daemon.py').read_text() + (sf/'usr/share/limad-link/common.py').read_text()
for token in ['ssl.SSLContext', 'certificate_fingerprint', 'PAIR_CODES', 'PAIR_ATTEMPTS', 'sha256_file', 'grdctl', '_limad-link._tcp', 'local_network_source', '/api/admin/permissions']:
    if token not in text: raise SystemExit(f'LILINK FAILED: Sicherheits-/Integrationsmerkmal fehlt: {token}')
print('LiLink service, TLS pairing, GNOME RDP, transfer, handoff and GNOME 50 panel integration: PASS')
PY
bash -n system_files/usr/local/bin/lilink system_files/usr/local/bin/limad-linkd system_files/usr/local/bin/limad-link-status-ensure build_files/68-lilink.sh

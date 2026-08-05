#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
fail(){ echo "2.8.0 INHERITED APP INTEGRATION FAILED: $*" >&2; exit 1; }

source build_files/versions.env
[[ "$LIMAD_BUILD_REVISION" == 'gnome-rc2-build5' ]] || fail "revision mismatch"
[[ "$LIMAD_STUDY_VERSION" == '6.6.3' ]] || fail "Study build version mismatch"
[[ "$LIMAD_CUT_VERSION" == '1.1.4' ]] || fail "Cut build version mismatch"
[[ "$(<system_files/usr/share/limad-study/VERSION)" == '6.6.3' ]] || fail "Study payload version mismatch"
[[ "$(<system_files/usr/share/limad-cut/VERSION)" == '1.1.4' ]] || fail "Cut payload version mismatch"

grep -Fq 'data-i18n=' system_files/usr/share/limad-study/web/index.html || fail "explicit i18n keys missing"
grep -Fq "querySelectorAll?.('[data-i18n]" system_files/usr/share/limad-study/web/js/i18n.js || fail "i18n DOM binding missing"
grep -Fq 'document.documentElement.dir' system_files/usr/share/limad-study/web/js/i18n.js || fail "language direction handling missing"
grep -Fq 'i18n.js' system_files/usr/share/limad-study/web/index.html || fail "i18n module not loaded"

python3 - <<'PY'
from collections import Counter
from pathlib import Path
import gzip,hashlib,json,struct
root=Path('.')
# Seed really contains the full language catalog.
data=json.load(gzip.open(root/'system_files/usr/share/limad-study/seed/languages.json.gz','rt',encoding='utf-8'))
items=data.get('languages',[])
if len(items) < 1400: raise SystemExit(f'language seed incomplete: {len(items)}')
if not any(str(x.get('Direction','')).lower()=='rtl' for x in items): raise SystemExit('RTL language metadata missing')
# Every generated icon has a fixed checked hash and valid dimensions.
manifest=json.loads((root/'tests/fix50-study-icon-sha256.json').read_text())
for item in manifest['icons']:
 p=root/item['path']; raw=p.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=item['sha256']: raise SystemExit(f'icon hash mismatch: {p}')
 if raw[:8]!=b'\x89PNG\r\n\x1a\n' or raw[12:16]!=b'IHDR': raise SystemExit(f'invalid PNG: {p}')
 if list(struct.unpack('>II',raw[16:24]))!=item['size']: raise SystemExit(f'icon dimensions mismatch: {p}')
# Independently validate closed hemisphere topology: each edge occurs twice.
radial,vertical=64,32
vertices=[(0,0,12)]
for ring in range(1,vertical+1): vertices.extend([(ring,seg,0) for seg in range(radial)])
tri=[]
for seg in range(radial): tri.append((0,1+seg,1+(seg+1)%radial))
for ring in range(vertical-1):
 upper=1+ring*radial;lower=upper+radial
 for seg in range(radial):
  nxt=(seg+1)%radial;a,b,c,d=upper+seg,upper+nxt,lower+seg,lower+nxt
  tri.extend(((a,c,b),(b,c,d)))
center=len(vertices);vertices.append((0,0,0));equator=1+(vertical-1)*radial
for seg in range(radial):tri.append((center,equator+(seg+1)%radial,equator+seg))
edges=Counter()
for face in tri:
 for a,b in zip(face,(face[1],face[2],face[0])):edges[tuple(sorted((a,b)))]+=1
bad=[e for e,n in edges.items() if n!=2]
if bad:raise SystemExit(f'hemisphere is not watertight: {bad[:5]}')
PY

for html in system_files/usr/share/limad-cut/LiMaD_Cut_Offline_1.1.4_{DE,EN}.html; do
 [[ -f "$html" ]] || fail "missing $html"
 grep -Fq 'function limadClosedHemisphereGeometry' "$html" || fail "closed hemisphere helper missing"
 grep -Fq 'limadClosedHemisphereGeometry(12, 64, 32)' "$html" || fail "closed hemisphere not used"
 ! grep -Fq 'new u4(12, 64, 32, 0, Math.PI * 2, 0, Math.PI / 2)' "$html" || fail "old open hemisphere remains"
done

[[ -x system_files/usr/local/bin/limad-terminal ]] || fail "terminal launcher missing"
[[ -f system_files/usr/share/applications/de.limad.Terminal.desktop ]] || fail "terminal desktop entry missing"
grep -Fq 'LiMaD richtet zusätzliche Programme ein' system_files/usr/local/bin/limad-install-default-flatpaks || fail "first-login install notice missing"
python3 - <<'PY'
import ast,re
from pathlib import Path
for path in ('system_files/usr/local/bin/limad-first-login-setup','system_files/usr/local/bin/limad-install-default-flatpaks'):
 text=Path(path).read_text()
 match=re.search(r"(?:local desired|FAVORITES)=\"(\[.*?\])\"",text)
 if not match:raise SystemExit(f'dock list missing: {path}')
 value=match.group(1).replace('${zen_id}','app.zen_browser.zen').replace('${ZEN_ID}','app.zen_browser.zen')
 items=ast.literal_eval(value)
 if items[-3:]!=['de.limad.Terminal.desktop','io.github.kolunmi.Bazaar.desktop','org.gnome.Nautilus.desktop']:
  raise SystemExit(f'wrong dock tail in {path}: {items[-3:]}')
PY

echo "LiMaD OS 2.8.0 inherited Study/Cut/first-login integration: PASS"

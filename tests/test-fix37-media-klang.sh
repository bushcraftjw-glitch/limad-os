#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
fail() { echo "FIX37 MEDIA/KLANG FAILED: $*" >&2; exit 1; }

INSTALLER=system_files/usr/local/bin/limad-install-default-flatpaks
KLANG=system_files/usr/share/limad-klang/limad_klang.py
PRESET="system_files/usr/share/limad-klang/LiMaD Klang.json"
DESKTOP=system_files/usr/share/applications/de.limad.Klang.desktop

for id in us.zoom.Zoom app.ytmdesktop.ytmdesktop com.github.wwmm.easyeffects; do
  grep -Fq "$id" "$INSTALLER" || fail "default installer missing $id"
done
[[ -x system_files/usr/local/bin/limad-klang ]] || fail "LiMaD Klang launcher missing"
[[ -x system_files/usr/local/bin/limad-install-klang-preset ]] || fail "preset installer missing"
[[ -x system_files/usr/local/bin/limad-easyeffects-service ]] || fail "EasyEffects service helper missing"
[[ -f "$KLANG" ]] || fail "LiMaD Klang UI missing"
[[ -f "$PRESET" ]] || fail "LiMaD Klang preset missing"
[[ -f "$DESKTOP" ]] || fail "LiMaD Klang desktop file missing"
[[ -f system_files/etc/xdg/autostart/limad-easyeffects-service.desktop ]] || fail "EasyEffects autostart missing"
grep -Fq 'app.ytmdesktop.ytmdesktop.desktop' build_files/enforce-gnome-favorite-apps.py || fail "YTMDesktop not pinned"
grep -Fq 'de.limad.Klang.desktop' build_files/enforce-gnome-favorite-apps.py || fail "LiMaD Klang not pinned"
grep -Fq 'set_property:output:equalizer:0' "$KLANG" || fail "live equalizer control missing"
grep -Fq 'Mehr Höhen' "$KLANG" || fail "treble quick profile missing"
grep -Fq 'EasyEffectsServer' "$KLANG" || fail "EasyEffects local server integration missing"
python3 -m py_compile "$KLANG"
python3 - "$PRESET" <<'PY'
import json, sys
p=json.load(open(sys.argv[1], encoding='utf-8'))
out=p.get('output', {})
if out.get('plugins_order') != ['equalizer#0']:
    raise SystemExit('wrong plugins_order')
eq=out.get('equalizer#0', {})
if eq.get('num-bands') != 10:
    raise SystemExit('expected 10 equalizer bands')
for channel in ('left','right'):
    bands=eq.get(channel, {})
    if len(bands) != 10:
        raise SystemExit(f'{channel}: expected 10 bands, got {len(bands)}')
PY
bash -n system_files/usr/local/bin/limad-klang \
  system_files/usr/local/bin/limad-install-klang-preset \
  system_files/usr/local/bin/limad-easyeffects-service \
  "$INSTALLER"
echo "FIX37 Zoom, YTMDesktop and direct LiMaD Klang controls: PASS"

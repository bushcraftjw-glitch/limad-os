#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."

python3 - <<'PY'
from pathlib import Path
import json
root=Path('.')
required=[
 root/'system_files/usr/share/limad-save/core.py',
 root/'system_files/usr/share/limad-save/app.py',
 root/'system_files/usr/share/limad-save/cli.py',
 root/'system_files/usr/share/applications/de.limad.Save.desktop',
 root/'system_files/usr/lib/systemd/user/limad-save.service',
 root/'system_files/usr/lib/systemd/user/limad-save.timer',
 root/'system_files/usr/local/bin/limad-zen-deutsch-setup',
 root/'system_files/usr/local/bin/limad-user-folders-setup',
 root/'system_files/etc/xdg/autostart/limad-zen-deutsch.desktop',
 root/'system_files/etc/xdg/autostart/limad-user-folders.desktop',
 root/'system_files/usr/local/bin/limad-save-first-login-detect',
 root/'system_files/etc/xdg/autostart/limad-save-first-login.desktop',
]
for path in required:
    if not path.is_file(): raise SystemExit(f'BUILD4 FAILED: missing {path}')
for path in [root/'system_files/usr/share/limad-save/core.py',root/'system_files/usr/share/limad-save/app.py',root/'system_files/usr/share/limad-save/cli.py',root/'system_files/usr/local/bin/limad-zen-deutsch-setup',root/'system_files/usr/local/bin/limad-user-folders-setup',root/'system_files/usr/local/bin/limad-save-first-login-detect']:
    compile(path.read_text(encoding='utf-8'),str(path),'exec')
packages=(root/'build_files/10-packages.sh').read_text()
for token in ('restic','libsecret','FATAL: mandatory LiSave runtime could not be installed','secret-tool'):
    if token not in packages: raise SystemExit(f'BUILD4 FAILED: package wiring missing {token}')
build=(root/'build_files/build.sh').read_text()
if '69-lisave.sh' not in build or build.index('69-lisave.sh') > build.index('70-limad-apps.sh'):
    raise SystemExit('BUILD4 FAILED: LiSave build order wrong')
core=(root/'system_files/usr/share/limad-save/core.py').read_text()
for token in ('export_jwlibrary','restic','flatpak_manifest','dconf_exports','secret_store','scheduled','Downloads','LiLink Sync','Das LiSave-Ziel darf nicht im Benutzerordner liegen'):
    if token not in core: raise SystemExit(f'BUILD4 FAILED: LiSave feature missing {token}')
zen=(root/'system_files/usr/local/bin/limad-zen-deutsch-setup').read_text()
for token in ('intl.locale.requested','de-DE, de, en-US, en','spellchecker.dictionary','default-web-browser','app.zen_browser.zen'):
    if token not in zen: raise SystemExit(f'BUILD4 FAILED: Zen setup missing {token}')
drop=(root/'system_files/usr/share/limad-drop/limad_dropd.py').read_text()
link=(root/'system_files/usr/share/limad-link/daemon.py').read_text()
if 'xdg_download_dir(home) / "LiDrop"' not in drop or 'xdg_download_dir(Path.home()) / "LiDrop"' not in link:
    raise SystemExit('BUILD4 FAILED: LiDrop destination not unified under Downloads')
apps=json.loads((root/'system_files/usr/share/limad-updater/apps.json').read_text())
if not any(item.get('app_id')=='de.limad.Save' for item in apps['apps']):
    raise SystemExit('BUILD4 FAILED: LiSave missing in updater')
print('Build 4 static LiSave, Zen German and LiDrop Downloads integration: PASS')
PY

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/home/LiDrop" "$TMP/config" "$TMP/bin" "$TMP/usb"
printf 'alte Datei\n' > "$TMP/home/LiDrop/alt.txt"
HOME="$TMP/home" XDG_CONFIG_HOME="$TMP/config" python3 system_files/usr/local/bin/limad-user-folders-setup
[[ -f "$TMP/home/Downloads/LiDrop/alt.txt" ]] || { echo 'BUILD4 FAILED: old LiDrop file not migrated' >&2; exit 1; }
[[ -L "$TMP/home/LiDrop" ]] || { echo 'BUILD4 FAILED: legacy LiDrop compatibility link missing' >&2; exit 1; }
grep -Fq '/Downloads/LiDrop LiDrop' "$TMP/config/gtk-4.0/bookmarks" || { echo 'BUILD4 FAILED: Nautilus LiDrop bookmark missing' >&2; exit 1; }

cat > "$TMP/bin/flatpak" <<'PY'
#!/usr/bin/env python3
import sys
args=sys.argv[1:]
if args and args[0]=='list':
    print('app.zen_browser.zen\tflathub\t1.0\tuser')
sys.exit(0)
PY
cat > "$TMP/bin/dconf" <<'PY'
#!/usr/bin/env python3
import sys
if len(sys.argv)>1 and sys.argv[1]=='dump': print('[test]\nvalue=true')
sys.exit(0)
PY
cat > "$TMP/bin/rpm-ostree" <<'PY'
#!/usr/bin/env python3
print('{"deployments":[]}')
PY
for name in systemctl pkill xdg-settings xdg-mime secret-tool; do
cat > "$TMP/bin/$name" <<'PY'
#!/usr/bin/env python3
import sys
if 'lookup' in sys.argv: print('very-secure-password')
sys.exit(0)
PY
done
cat > "$TMP/bin/restic" <<'PY'
#!/usr/bin/env python3
from pathlib import Path
import json, shutil, sys, time
args=sys.argv[1:]
repo=Path(args[args.index('-r')+1])
i=args.index('--password-file')+2
cmd=args[i]
rest=args[i+1:]
repo.mkdir(parents=True,exist_ok=True)
data=repo/'fake-data'
snaps=repo/'snapshots.json'
if cmd=='init':
    (repo/'config').write_text('fake')
    print('created')
elif cmd=='snapshots':
    print(snaps.read_text() if snaps.exists() else '[]')
elif cmd=='backup':
    shutil.rmtree(data,ignore_errors=True); data.mkdir()
    sources=[]; j=0
    while j<len(rest):
        if rest[j] in ('--tag','--exclude-file'):
            j+=2; continue
        if rest[j]=='--json': j+=1; continue
        sources.append(Path(rest[j])); j+=1
    for source in sources:
        if not source.exists(): continue
        target=data/source.resolve().relative_to('/')
        target.parent.mkdir(parents=True,exist_ok=True)
        if source.is_dir(): shutil.copytree(source,target,dirs_exist_ok=True,symlinks=True)
        else: shutil.copy2(source,target)
    values=[{'id':'fake-snapshot','time':'2026-08-04T20:00:00Z','tags':['lisave']}]
    snaps.write_text(json.dumps(values))
    print('{"message_type":"summary","snapshot_id":"fake-snapshot"}')
elif cmd in ('forget','check'):
    print('ok')
elif cmd=='restore':
    target=Path(rest[rest.index('--target')+1])
    shutil.copytree(data,target,dirs_exist_ok=True,symlinks=True)
    print('restored')
else:
    print('unsupported',cmd,file=sys.stderr); sys.exit(2)
PY
chmod +x "$TMP/bin"/*

HOME="$TMP/home" XDG_CONFIG_HOME="$TMP/config" XDG_DATA_HOME="$TMP/home/.local/share" XDG_STATE_HOME="$TMP/home/.local/state" XDG_CACHE_HOME="$TMP/home/.cache" PATH="$TMP/bin:/usr/bin:/bin" python3 system_files/usr/local/bin/limad-zen-deutsch-setup
ZEN_JS="$TMP/home/.var/app/app.zen_browser.zen/zen/Profiles/limad.default-release/user.js"
[[ -f "$ZEN_JS" ]] || { echo 'BUILD4 FAILED: Zen German profile not created' >&2; exit 1; }
grep -Fq 'intl.locale.requested", "de"' "$ZEN_JS" || { echo 'BUILD4 FAILED: Zen German locale missing' >&2; exit 1; }

mkdir -p "$TMP/home/Documents" "$TMP/home/Downloads/LiDrop" "$TMP/home/.var/app/app.zen_browser.zen/zen/Profiles/limad.default-release"
printf 'Dokumentinhalt\n' > "$TMP/home/Documents/test.txt"
printf 'Zenprofil\n' > "$TMP/home/.var/app/app.zen_browser.zen/zen/Profiles/limad.default-release/profile.txt"
HOME="$TMP/home" XDG_CONFIG_HOME="$TMP/config" XDG_DATA_HOME="$TMP/home/.local/share" XDG_STATE_HOME="$TMP/home/.local/state" XDG_CACHE_HOME="$TMP/home/.cache" PATH="$TMP/bin:/usr/bin:/bin" PYTHONPATH="system_files/usr/share/limad-save" python3 - <<PY
from pathlib import Path
from core import backup, restore
categories={'documents':True,'zen':True,'mail':False,'study':False,'windows':False,'windows_full':False,'settings':False,'appsettings':False}
report=backup(Path('$TMP/usb'),'very-secure-password',categories)
Path('$TMP/home/Documents/test.txt').unlink()
Path('$TMP/home/.var/app/app.zen_browser.zen/zen/Profiles/limad.default-release/profile.txt').unlink()
result=restore(Path(report['bundle']),'very-secure-password',categories)
assert Path('$TMP/home/Documents/test.txt').read_text()=='Dokumentinhalt\n'
assert Path('$TMP/home/.var/app/app.zen_browser.zen/zen/Profiles/limad.default-release/profile.txt').read_text()=='Zenprofil\n'
assert result['ok'] is True
print('LiSave simulated manifest backup and clean-install restore: PASS')
PY

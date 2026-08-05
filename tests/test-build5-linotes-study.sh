#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
fail(){ echo "BUILD5 LINOTES/STUDY FAILED: $*" >&2; exit 1; }
source build_files/versions.env
[[ "$LIMAD_BUILD_REVISION" == "gnome-rc2-build5" ]] || fail "build revision"
[[ "$LIMAD_STUDY_VERSION" == "6.6.3" ]] || fail "Study version"
[[ "$LINOTES_VERSION" == "1.0.0-preview2" ]] || fail "LiNotes version"
[[ "$LISAVE_VERSION" == "1.0.0-preview2" ]] || fail "LiSave version"
[[ "$LILINK_VERSION" == "1.0.0-preview3" ]] || fail "LiLink version"

for file in \
 system_files/usr/share/limad-notes/app.py \
 system_files/usr/share/limad-notes/storage.py \
 system_files/usr/share/limad-notes/VERSION \
 system_files/usr/local/bin/limad-notes \
 system_files/usr/share/applications/de.limad.Notes.desktop \
 system_files/usr/share/metainfo/de.limad.Notes.metainfo.xml \
 system_files/usr/share/icons/hicolor/scalable/apps/de.limad.Notes.svg \
 system_files/usr/share/icons/LiMaD/scalable/apps/de.limad.Notes.svg \
 build_files/69-linotes.sh; do
 [[ -s "$file" ]] || fail "missing $file"
done
[[ -x system_files/usr/local/bin/limad-notes ]] || fail "launcher not executable"
[[ "$(<system_files/usr/share/limad-notes/VERSION)" == "$LINOTES_VERSION" ]] || fail "payload version"
python3 -m py_compile system_files/usr/share/limad-notes/app.py system_files/usr/share/limad-notes/storage.py
for size in 16 22 24 32 48 64 128 256 512; do
 [[ -s "system_files/usr/share/icons/hicolor/${size}x${size}/apps/de.limad.Notes.png" ]] || fail "hicolor icon $size"
 [[ -s "system_files/usr/share/icons/LiMaD/${size}x${size}/apps/de.limad.Notes.png" ]] || fail "LiMaD icon $size"
done

grep -Fq 'de.limad.Notes.desktop' system_files/usr/share/glib-2.0/schemas/zzzzzzzzzz-limad-defaults.gschema.override || fail "dock default"
grep -Fq 'de.limad.Notes.desktop' system_files/usr/local/bin/limad-first-login-setup || fail "first login"
grep -Fq 'de.limad.Notes.desktop' system_files/usr/local/bin/limad-install-default-flatpaks || fail "flatpak setup favorites"
grep -Fq '69-linotes.sh' build_files/build.sh || fail "build wiring"
grep -Fq '"de.limad.Notes": "LiNotes"' tools/build-limad-update.py || fail "update builder"

python3 - <<'PY'
import json
from pathlib import Path
apps=json.loads(Path('system_files/usr/share/limad-updater/apps.json').read_text())['apps']
entry=next((x for x in apps if x.get('app_id')=='de.limad.Notes'),None)
assert entry and entry['system_root']=='/usr/share/limad-notes'
assert set(entry['required'])=={'app.py','storage.py','VERSION'}
icons=json.loads(Path('system_files/usr/share/limad/limad-icons.manifest.json').read_text())['applications']['de.limad.Notes']
assert icons['scalable'] is True and 512 in icons['sizes'] and 'linotes' in icons['aliases']
release=json.loads(Path('RELEASE-MANIFEST.json').read_text())
assert release['version']=='2.8.0-rc2-gnome-rc2-build5'
assert release['components']['linotes']=='1.0.0-preview2'
assert release['components']['limad_study']=='6.6.3'
assert 'window.linotes-dark' in Path('system_files/usr/share/limad-notes/app.py').read_text()
css=Path('system_files/usr/share/limad-study/web/css/app.css').read_text()
assert 'LiMaD Study 6.6.3' in css and 'library-category>summary' in css
assert 'de.limad.Notes' in release['updater_apps']
PY

# LiNotes storage round trip, attachment handling, trash/restore and imports.
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/home" "$TMP/data" "$TMP/config" "$TMP/state"
HOME="$TMP/home" XDG_DATA_HOME="$TMP/data" XDG_CONFIG_HOME="$TMP/config" XDG_STATE_HOME="$TMP/state" \
PYTHONPATH="$PWD/system_files/usr/share/limad-notes" python3 - "$TMP" <<'PY'
from pathlib import Path
import sys
from storage import Store
root=Path(sys.argv[1])
store=Store(root/'notes.db')
folder=store.add_folder('Projekte')
note=store.create_note(folder['id'],'Testnotiz','Erste Zeile')
store.update_note(note['id'],'Geändert','Text\n☐ Aufgabe')
store.pin(note['id'],True)
assert store.note(note['id'])['pinned']==1
source=root/'anhang.txt'; source.write_text('Anhang',encoding='utf-8')
attached=store.add_attachment(note['id'],source)
assert Path(attached['path']).read_text()=='Anhang'
store.trash(note['id']); assert store.notes('deleted',deleted=True)
store.restore(note['id']); assert store.note(note['id'])['deleted_at'] is None
html=root/'import.html'; html.write_text('<h1>HTML Titel</h1><p>Inhalt</p>',encoding='utf-8')
rtf=root/'import.rtf'; rtf.write_text(r'{\rtf1\ansi RTF Titel\par Inhalt}',encoding='utf-8')
enex=root/'import.enex'; enex.write_text('<?xml version="1.0"?><en-export><note><title>ENEX Titel</title><content><![CDATA[<en-note>ENEX Inhalt</en-note>]]></content></note></en-export>',encoding='utf-8')
assert store.import_file(html)
assert 'RTF Titel' in store.import_file(rtf)[0]['body']
assert store.import_file(enex)[0]['title']=='ENEX Titel'
assert len(store.notes('all'))>=4
PY

# Study question typography and automatic current-week article resolution.
RENDER=system_files/usr/share/limad-study/src/limad_study/reader/render.py
MEETINGS=system_files/usr/share/limad-study/src/limad_study/meetings.py
grep -Fq 'font-size:.84em' "$RENDER" || fail "question font size"
grep -Fq 'normalizeWatchtowerQuestions' "$RENDER" || fail "question normalization"
grep -Fq 'limad-question-number' "$RENDER" || fail "bold question number"
grep -Fq 'def _article_number' "$MEETINGS" || fail "article number resolver"
grep -Fq 'current_week_row' "$MEETINGS" || fail "current week resolver"
HOME="$TMP/home" XDG_DATA_HOME="$TMP/data" XDG_CONFIG_HOME="$TMP/config" XDG_STATE_HOME="$TMP/state" \
PYTHONPATH="$PWD/system_files/usr/share/limad-study/src" python3 - <<'PY'
from datetime import date
from limad_study.meetings import _watchtower_article_for_week
class FakeDB:
    def rows(self, sql, params=()):
        if 'FROM documents d' in sql:
            return [
                {'id':'a1','source_document_id':101,'title':'Studienartikel 1','toc_title':'Studienartikel 1','subtitle':'','class_name':'','sort_order':10,'content_text':'','question_count':18},
                {'id':'a2','source_document_id':102,'title':'Studienartikel 2','toc_title':'Studienartikel 2','subtitle':'','class_name':'','sort_order':20,'content_text':'','question_count':18},
                {'id':'a3','source_document_id':103,'title':'Studienartikel 3','toc_title':'Studienartikel 3','subtitle':'','class_name':'','sort_order':30,'content_text':'','question_count':18},
            ]
        if 'date(end_date)>=date' in sql:
            return [{'source_dated_text_id':7,'document_source_id':103,'start_date':'2026-08-03','end_date':'2026-08-09','caption':'Wachtturm-Studium','content_html':'Studienartikel 3'}]
        if 'julianday(end_date)' in sql:
            return []
        raise AssertionError(sql)
article=_watchtower_article_for_week(FakeDB(),'wt',date(2026,8,3),date(2026,8,9))
assert article and article['id']=='a3', article
PY

# Render the actual reader HTML and validate the generated JavaScript syntax.
HOME="$TMP/home" XDG_DATA_HOME="$TMP/data" XDG_CONFIG_HOME="$TMP/config" XDG_STATE_HOME="$TMP/state" \
PYTHONPATH="$PWD/system_files/usr/share/limad-study/src" python3 - "$TMP/reader.js" <<'PY'
from pathlib import Path
import re,sys
from limad_study.reader.render import render_document
class FakeDB:
    def rows(self, sql, params=()):
        if 'FROM documents d JOIN publications p' in sql:
            return [{'id':1,'publication_id':'p1','source_document_id':1,'title':'Studienartikel 1','toc_title':'','class_name':'','content_html':'<p class="studyQuestion">1-2. Warum?</p><textarea></textarea>','publication_title':'Der Wachtturm','content_dir':'','key_symbol':'w','language_index':2}]
        return []
    def row(self, sql, params=()): return None
    def scalar(self, sql, params=()): return None
page=render_document(1,FakeDB())
assert 'reader-profile-watchtower-study' in page
assert 'normalizeWatchtowerQuestions' in page
assert r'\d{1,3}' in page
scripts=re.findall(r'<script>(.*?)</script>',page,re.S)
Path(sys.argv[1]).write_text('\n'.join(scripts),encoding='utf-8')
PY
if command -v node >/dev/null 2>&1; then node --check "$TMP/reader.js"; fi

grep -Fq '"notes": True' system_files/usr/share/limad-save/core.py || fail "LiSave category"
grep -Fq 'limad-notes' system_files/usr/share/limad-save/core.py || fail "LiSave source"
grep -Fq 'limad-notes' system_files/usr/share/limad-link/app.py || fail "LiLink app UI"
grep -Fq '"limad-notes":' system_files/usr/share/limad-link/daemon.py || fail "LiLink handoff command"

echo 'Build 5 LiNotes and Study Wachtturm integration: PASS'

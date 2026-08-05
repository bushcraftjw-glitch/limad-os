#!/usr/bin/env bash
# Upstream design sources must be pinned to published release tags, carry a
# licence and be wired into exactly the build helper that claims them.
set -Eeuo pipefail
cd "$(dirname "$0")/.."

python3 - <<'PY'
import json, re, sys
from pathlib import Path

lock = json.loads(Path('build_files/theme-sources.lock.json').read_text())
env = dict(
    re.findall(r'^([A-Z0-9_]+)="([^"]*)"$', Path('build_files/versions.env').read_text(), re.M)
)

def fail(msg):
    sys.exit(f'SOURCE LOCK FAILED: {msg}')

if not lock['policy']['floating_branches_forbidden']:
    fail('policy must forbid floating branches')

expected = {
    'mactahoe-gtk-theme': ('MACTAHOE_REPO', 'MACTAHOE_TAG', 'MACTAHOE_LICENSE'),
    'whitesur-icon-theme': ('WHITESUR_ICONS_REPO', 'WHITESUR_ICONS_TAG', 'WHITESUR_ICONS_LICENSE'),
}
seen = set()
for src in lock['sources']:
    sid = src['id']
    if sid not in expected:
        fail(f'unknown source id {sid}')
    seen.add(sid)
    repo_key, tag_key, lic_key = expected[sid]
    if env[repo_key] != src['upstream']:
        fail(f'{sid}: versions.env repo {env[repo_key]} != lock {src["upstream"]}')
    if env[tag_key] != src['tag']:
        fail(f'{sid}: versions.env tag {env[tag_key]} != lock {src["tag"]}')
    if env[lic_key] != src['license']:
        fail(f'{sid}: licence mismatch')
    if not re.fullmatch(r'v?\d{4}-\d{2}-\d{2}', src['tag']):
        fail(f'{sid}: tag {src["tag"]} does not look like a release tag')
    if src['tag'] in {'main', 'master', 'HEAD'}:
        fail(f'{sid}: floating branch')
    if not src.get('copyright_holder'):
        fail(f'{sid}: copyright holder missing')
    helper = Path(src['build_helper'])
    if not helper.is_file():
        fail(f'{sid}: build helper {helper} missing')
    text = helper.read_text()
    if src['upstream'] not in text and repo_key not in text:
        fail(f'{sid}: build helper does not reference the upstream repository')
    if tag_key not in text:
        fail(f'{sid}: build helper does not use the pinned tag variable')
    if '--depth 1 --branch' not in text:
        fail(f'{sid}: build helper must clone the pinned tag explicitly')
    if 'git describe --tags --exact-match' not in text:
        fail(f'{sid}: build helper must verify the checked out tag')

if seen != set(expected):
    fail(f'missing sources: {set(expected) - seen}')

base = lock['base_image']['reference']
if base != f'{env["BASE_IMAGE"]}:{env["BASE_IMAGE_TAG"]}':
    fail('base image reference does not match versions.env')
if 'gnome' not in base:
    fail('base image is not a GNOME image')
containerfile = Path('Containerfile').read_text()
if f'ARG BASE_IMAGE_REF={base}' not in containerfile:
    fail('Containerfile does not default to the locked base image')
if 'FROM ${BASE_IMAGE_REF}' not in containerfile:
    fail('Containerfile does not build from the BASE_IMAGE_REF argument')
if env.get('BASE_IMAGE_REF') != base:
    fail('BASE_IMAGE_REF does not match the locked base image')
if '--build-arg "BASE_IMAGE_REF=' not in Path('.github/workflows/build.yml').read_text():
    fail('the workflow never passes BASE_IMAGE_REF to the build')

if lock['limad_own_assets']['inherits'] != env['LIMAD_WHITESUR_ICON_NAME']:
    fail('own icon overlay does not inherit the locked WhiteSur theme')

print('Pinned theme sources, licences and base image: PASS')
PY

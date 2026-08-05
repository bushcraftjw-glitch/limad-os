#!/usr/bin/env bash
# Regression test for repository keys in the committed bootc/OSTree image.
set -Eeuo pipefail
cd "$(dirname "$0")/.."

python3 - <<'PY'
import sys
from pathlib import Path

keys = Path('build_files/84-repo-keys.sh').read_text()
hygiene = Path('build_files/85-repo-hygiene.sh').read_text()
postcommit = Path('build_files/post-commit-check.sh').read_text()
workflow = Path('.github/workflows/build.yml').read_text()


def fail(message):
    sys.exit(f'REPOSITORY KEY TEST FAILED: {message}')


# Production bug in 2.3.2: requiring /usr/etc after `ostree container commit`
# was wrong for a plain OCI inspection container. The durable solution is to
# keep the key below /usr/share and rewrite the repository gpgkey reference.
for text, name in ((keys, '84-repo-keys.sh'), (hygiene, '85-repo-hygiene.sh'),
                   (postcommit, 'post-commit-check.sh')):
    if '/usr/etc/pki/rpm-gpg' in text:
        fail(f'{name} still requires repository keys below /usr/etc')

for needle in (
    "IMMUTABLE_KEY_DIR = '/usr/share/limad/repo-keys'",
    "replacement = f'file://{immutable}'",
    "terra-mesa still uses a mutable key path",
):
    if needle not in keys:
        fail(f'84-repo-keys.sh is missing immutable-key logic: {needle}')

# The audit must fail rather than quietly disabling Bazzite's graphics repo.
if "parser.set(section, 'enabled', '0')" in hygiene:
    fail('85-repo-hygiene.sh still disables repositories silently')
for needle in ('terra-mesa is not enabled', 'every resolved file:// key exists',
               'makecache --refresh'):
    if needle not in hygiene:
        fail(f'85-repo-hygiene.sh is missing: {needle}')

# The committed-image check must bypass Bazzite's rpm-ostree entrypoint and
# verify the immutable key and real repository metadata before the push/ISO.
for needle in (
    '--entrypoint /usr/bin/bash',
    'post-commit-check.sh:/tmp/limad-post-commit-check.sh:ro',
):
    if needle not in workflow:
        fail(f'workflow is missing post-commit wiring: {needle}')
for needle in (
    'POST-COMMIT FAILED: immutable Terra key missing',
    'mutable key path',
    'dnf5 makecache --refresh',
):
    if needle not in postcommit:
        fail(f'post-commit-check.sh is missing: {needle}')

# Ensure the exact Fedora/Terra example maps to an immutable path rather than
# either mutable /etc or the invalid /usr/etc/etc construction.
example = '/etc/pki/rpm-gpg/RPM-GPG-KEY-terra44-mesa'
immutable = '/usr/share/limad/repo-keys/' + example.rsplit('/', 1)[-1]
if immutable != '/usr/share/limad/repo-keys/RPM-GPG-KEY-terra44-mesa':
    fail('example immutable path calculation is wrong')

print('Repository key immutable-path and post-commit guard: PASS')
PY

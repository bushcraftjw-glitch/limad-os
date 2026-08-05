#!/usr/bin/env bash
# Guard the workaround for bootc-image-builder issue #1188: ISO depsolve reads
# file:// GPG keys from the builder filesystem, not from the source bootc image.
set -Eeuo pipefail
cd "$(dirname "$0")/.."

python3 - <<'PY'
import sys
from pathlib import Path

helper = Path('build_files/prepare-bib-key-wrapper.sh')
workflow = Path('.github/workflows/build.yml').read_text()
repo_keys = Path('build_files/84-repo-keys.sh').read_text()


def fail(message):
    sys.exit(f'BIB KEY BRIDGE TEST FAILED: {message}')

if not helper.is_file():
    fail('prepare-bib-key-wrapper.sh is missing')
text = helper.read_text()

for needle in (
    'quay.io/centos-bootc/bootc-image-builder:latest',
    'copy_tree /usr/share/limad/repo-keys required',
    'copy_tree /usr/share/distribution-gpg-keys optional',
    'copy_tree /etc/pki/rpm-gpg optional',
    'COPY rootfs/ /',
    '"${PODMAN[@]}" build',
    'RPM-GPG-KEY-terra*-mesa',
):
    if needle not in text:
        fail(f'helper is missing `{needle}`')

for needle in (
    'Repository-Schlüssel für den ISO-Bauer bereitstellen',
    'prepare-bib-key-wrapper.sh',
    'LIMAD_BIB_IMAGE=',
    '"${LIMAD_BIB_IMAGE}"',
):
    if needle not in workflow:
        fail(f'workflow is missing `{needle}`')

# Running the upstream builder directly would recreate the exact Curl error 37
# seen with Bazzite's terra-mesa repository.
iso_marker = '- name: Build and validate source ISO'
try:
    iso_block = workflow.split(iso_marker, 1)[1].split('- name: Brand and verify final ISO', 1)[0]
except IndexError:
    fail('cannot locate ISO build step')
if 'quay.io/centos-bootc/bootc-image-builder:latest' in iso_block:
    fail('ISO step still runs the unkeyed upstream builder directly')
if '${LIMAD_BIB_IMAGE}' not in iso_block:
    fail('ISO step does not run the keyed wrapper')

# The OS image itself must continue to keep GPG verification enabled and must
# not disable terra-mesa just to make the installer build pass.
if "parser.set(section, 'enabled', '0')" in repo_keys:
    fail('repository key step disables an enabled repository')
if 'gpgcheck=0' in repo_keys or 'repo_gpgcheck=0' in repo_keys:
    fail('repository key step disables signature verification')

print('bootc-image-builder file-key bridge: PASS')
PY

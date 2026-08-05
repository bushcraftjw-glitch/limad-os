#!/usr/bin/env bash
# Make local repository signing keys immutable-image safe.
#
# Files added only below /etc may be visible during the mutable container build
# but disappear when a fresh deployment is created. Therefore missing file://
# keys are copied into /usr/share/limad/repo-keys and repository definitions are
# rewritten to that immutable path. The ISO workflow separately bridges these
# public keys into bootc-image-builder, whose current depsolver does not read
# file:// keys from the source image filesystem (upstream issue #1188).
set -Eeuo pipefail

echo ":: Making repository key references image-safe"

python3 - <<'PY'
import configparser
import glob
import os
import platform
import re
import shutil
import sys

KEY_POOL = '/usr/share/distribution-gpg-keys'
IMMUTABLE_KEY_DIR = '/usr/share/limad/repo-keys'
REPO_DIRS = (
    '/etc/yum.repos.d',
    '/usr/etc/yum.repos.d',
    '/etc/distro.repos.d',
    '/usr/share/dnf5/repos.d',
)

releasever = ''
with open('/etc/os-release', encoding='utf-8') as handle:
    for line in handle:
        if line.startswith('VERSION_ID='):
            releasever = line.split('=', 1)[1].strip().strip('"')
            break
basearch = platform.machine()

if not releasever:
    sys.exit('FATAL: VERSION_ID could not be read from /etc/os-release')
if not os.path.isdir(KEY_POOL):
    sys.exit(f'FATAL: repository key collection missing: {KEY_POOL}')


def expand(value: str) -> str:
    """Expand only the two variables supported by Fedora repo files."""
    value = value.replace('${releasever}', releasever)
    value = re.sub(r'\$releasever(?![A-Za-z0-9_])', releasever, value)
    value = value.replace('${basearch}', basearch)
    value = re.sub(r'\$basearch(?![A-Za-z0-9_])', basearch, value)
    return value


repo_files = []
for directory in REPO_DIRS:
    if os.path.isdir(directory):
        files = sorted(glob.glob(os.path.join(directory, '*.repo')))
        repo_files.extend(files)
        if files:
            print(f'   scanning {directory}')
if not repo_files:
    sys.exit('FATAL: no repository definitions found')

# Index the packaged key collection by file name.
pool = {}
for path in glob.glob(os.path.join(KEY_POOL, '**', '*'), recursive=True):
    if os.path.isfile(path):
        pool.setdefault(os.path.basename(path), path)
print(f'   {len(pool)} packaged keys available')

os.makedirs(IMMUTABLE_KEY_DIR, exist_ok=True)
rewritten = []
missing = []

for repo_file in repo_files:
    parser = configparser.RawConfigParser(interpolation=None)
    parser.optionxform = str
    try:
        with open(repo_file, encoding='utf-8') as handle:
            parser.read_file(handle)
    except (OSError, configparser.Error) as exc:
        print(f'   WARNING: cannot read {repo_file}: {exc}')
        continue

    file_changed = False
    for section in parser.sections():
        if parser.get(section, 'enabled', fallback='1').strip() != '1':
            continue

        raw_keys = parser.get(section, 'gpgkey', fallback='')
        if not raw_keys.strip():
            continue

        tokens = raw_keys.split()
        new_tokens = []
        section_changed = False

        for token in tokens:
            if not token.startswith('file://'):
                new_tokens.append(token)
                continue

            resolved = expand(token[len('file://'):])
            if '$' in resolved:
                # Unknown variables are left untouched. Guessing could damage a
                # valid repository definition.
                new_tokens.append(token)
                continue

            # Existing immutable keys are already safe.
            if resolved.startswith('/usr/') and os.path.isfile(resolved):
                new_tokens.append(token)
                continue

            source = pool.get(os.path.basename(resolved))
            if source is None:
                if os.path.isfile(resolved):
                    # The key exists only in a mutable location and no packaged
                    # source is available. Keep it for now; the audit step will
                    # detect if it disappears after the commit.
                    new_tokens.append(token)
                else:
                    missing.append((section, repo_file, resolved))
                    new_tokens.append(token)
                continue

            immutable = os.path.join(IMMUTABLE_KEY_DIR, os.path.basename(resolved))
            shutil.copyfile(source, immutable)
            os.chmod(immutable, 0o644)
            if not os.path.isfile(immutable) or os.path.getsize(immutable) == 0:
                sys.exit(f'FATAL: failed to install immutable key {immutable}')

            replacement = f'file://{immutable}'
            new_tokens.append(replacement)
            if replacement != token:
                section_changed = True
                rewritten.append((section, repo_file, token, replacement))

        if section_changed:
            parser.set(section, 'gpgkey', ' '.join(new_tokens))
            file_changed = True

    if file_changed:
        temporary = repo_file + '.limad-new'
        with open(temporary, 'w', encoding='utf-8') as handle:
            parser.write(handle, space_around_delimiters=False)
        os.chmod(temporary, os.stat(repo_file).st_mode & 0o777)
        os.replace(temporary, repo_file)

for section, repo_file, old, new in rewritten:
    print(f'   rewritten: {section} in {repo_file}')
    print(f'      {old}')
    print(f'      -> {new}')

for section, repo_file, target in missing:
    print(f'   unresolved: {section} in {repo_file} -> {target}')

# Terra Mesa is part of Bazzite's graphics stack. It must remain enabled and
# use the immutable key path; silently disabling it would alter the base OS.
terra_sections = []
for repo_file in repo_files:
    parser = configparser.RawConfigParser(interpolation=None)
    parser.optionxform = str
    try:
        parser.read(repo_file)
    except configparser.Error:
        continue
    if not parser.has_section('terra-mesa'):
        continue
    if parser.get('terra-mesa', 'enabled', fallback='1').strip() != '1':
        sys.exit(f'FATAL: terra-mesa was disabled in {repo_file}')
    keys = parser.get('terra-mesa', 'gpgkey', fallback='').split()
    local_paths = [expand(k[len('file://'):]) for k in keys if k.startswith('file://')]
    if not local_paths:
        sys.exit(f'FATAL: terra-mesa has no local signing key in {repo_file}')
    for path in local_paths:
        if not path.startswith(IMMUTABLE_KEY_DIR + '/'):
            sys.exit(
                f'FATAL: terra-mesa still uses a mutable key path in '
                f'{repo_file}: {path}'
            )
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            sys.exit(f'FATAL: terra-mesa immutable key missing: {path}')
    terra_sections.append(repo_file)

if not terra_sections:
    sys.exit('FATAL: enabled terra-mesa repository definition not found')

print(f'   terra-mesa uses immutable keys in {len(terra_sections)} definition(s)')
print(f'   immutable key directory: {IMMUTABLE_KEY_DIR}')
PY

echo ":: Repository key step done"

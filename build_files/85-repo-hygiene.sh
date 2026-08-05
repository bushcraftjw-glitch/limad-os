#!/usr/bin/env bash
# Audit every enabled repository after step 84 rewrote mutable key references.
# This step does not silently disable repositories: an unusable repository is
# a build error, especially for Bazzite's terra-mesa graphics stack.
set -Eeuo pipefail

echo ":: Auditing enabled repositories"

python3 - <<'PY'
import configparser
import glob
import os
import platform
import re
import sys

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


def expand(value: str) -> str:
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
    sys.exit('FATAL: no repository files found')

broken = []
enabled = 0
terra_enabled = False

for path in repo_files:
    parser = configparser.RawConfigParser(interpolation=None)
    parser.optionxform = str
    try:
        parser.read(path)
    except configparser.Error as exc:
        broken.append(f'{path}: cannot parse: {exc}')
        continue

    for section in parser.sections():
        if parser.get(section, 'enabled', fallback='1').strip() != '1':
            continue
        enabled += 1
        if section == 'terra-mesa':
            terra_enabled = True

        for token in parser.get(section, 'gpgkey', fallback='').split():
            if not token.startswith('file://'):
                continue
            resolved = expand(token[len('file://'):])
            if '$' in resolved:
                # Unknown variables are not interpreted as missing files.
                continue
            if not os.path.isfile(resolved) or os.path.getsize(resolved) == 0:
                broken.append(f'{section} in {path} -> {resolved}')

if enabled == 0:
    broken.append('no enabled repository definitions remain')
if not terra_enabled:
    broken.append('terra-mesa is not enabled')

if broken:
    for entry in broken:
        print(f'   BROKEN: {entry}')
    sys.exit('FATAL: an enabled repository points at an unusable local key')

print(f'   {enabled} enabled repository entries checked')
print('   every resolved file:// key exists')
PY

# Ask the package manager to do the same metadata operation the ISO builder
# performs. This catches malformed repository files and inaccessible remotes.
echo ":: Refreshing repository metadata as a real test"
DNF="dnf5"
command -v dnf5 >/dev/null 2>&1 || DNF="dnf"
if "$DNF" makecache --refresh >/tmp/limad-makecache.log 2>&1; then
  echo "   all enabled repositories answered"
else
  echo "   FATAL: at least one enabled repository is unusable" >&2
  tail -n 40 /tmp/limad-makecache.log | sed 's/^/   | /' >&2
  exit 1
fi

echo ":: Repository step done"

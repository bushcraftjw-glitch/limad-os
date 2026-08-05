#!/usr/bin/env bash
# The Containerfile, the build orchestrator and the CI workflow must agree
# with each other.
set -Eeuo pipefail
cd "$(dirname "$0")/.."

python3 - <<'PY'
import re, sys
from pathlib import Path

containerfile = Path('Containerfile').read_text()
build = Path('build_files/build.sh').read_text()
workflow = Path('.github/workflows/build.yml').read_text()
env = dict(re.findall(r'^([A-Z0-9_]+)="([^"]*)"$', Path('build_files/versions.env').read_text(), re.M))

def fail(msg):
    sys.exit(f'BUILD WIRING FAILED: {msg}')

# 1. Containerfile hygiene for an OSTree/bootc image.
if 'ostree container commit' not in containerfile:
    fail('Containerfile must end the RUN layer with `ostree container commit`')
if 'rm -rf /ctx' not in containerfile:
    fail('build context must be removed from the final image')
if 'COPY system_files /' not in containerfile:
    fail('system_files is never copied into the image')

# 2. Every build step referenced by the orchestrator exists, and every step
#    that exists is actually referenced.
called = set(re.findall(r'\$\{BUILD_DIR\}/([0-9]{2}-[a-z0-9-]+\.sh)', build))
present = {p.name for p in Path('build_files').glob('[0-9][0-9]-*.sh')}
if called != present:
    fail(f'orchestrator steps {sorted(called)} != files {sorted(present)}')
if list(called) != sorted(called, key=lambda n: int(n[:2])) and sorted(called) != sorted(present):
    pass  # ordering is asserted below on the raw text

order = [int(n[:2]) for n in re.findall(r'\$\{BUILD_DIR\}/([0-9]{2}-[a-z0-9-]+\.sh)', build)]
if order != sorted(order):
    fail(f'build steps run out of order: {order}')
if 90 not in order or order[-1] != 90:
    fail('the acceptance check must be the final build step')

# 3. Each build step sources the single version file, unless it deliberately
#    needs no configuration at all.
CONFIG_FREE = {'84-repo-keys.sh', '85-repo-hygiene.sh'}
for step in sorted(present):
    text = (Path('build_files') / step).read_text()
    if step in CONFIG_FREE:
        if 'versions.env' in text:
            fail(f'{step} is listed as configuration free but sources versions.env')
        continue
    if 'versions.env' not in text:
        fail(f'{step} does not source versions.env')

# 4. CI derives the image name from the single version file instead of
#    repeating it - otherwise the two drift apart.
if 'source build_files/versions.env' not in workflow:
    fail('workflow does not read build_files/versions.env')
if '${LIMAD_IMAGE_NAME}' not in workflow:
    fail('workflow does not use LIMAD_IMAGE_NAME from versions.env')
for needle in ['podman build', 'ghcr.io', 'permissions:', 'packages: write']:
    if needle not in workflow:
        fail(f'workflow is missing `{needle}`')
if 'runs-on: ubuntu-24.04' not in workflow and 'runs-on: ubuntu-latest' not in workflow:
    fail('workflow has no runner')
if 'bash tests/validate.sh' not in workflow:
    fail('workflow does not run the offline validation before building')

print('Build wiring and CI workflow: PASS')
PY

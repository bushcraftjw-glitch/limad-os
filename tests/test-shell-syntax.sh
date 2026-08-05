#!/usr/bin/env bash
# Every shipped script must parse, and every JSON file must be valid.
set -Eeuo pipefail
cd "$(dirname "$0")/.."

count=0
while IFS= read -r -d '' script; do
  bash -n "$script" || { echo "syntax error: $script" >&2; exit 1; }
  head -n 1 "$script" | grep -q '^#!' || { echo "missing shebang: $script" >&2; exit 1; }
  grep -q '^set -Eeuo pipefail$' "$script" || { echo "missing strict mode: $script" >&2; exit 1; }
  count=$((count + 1))
done < <(find build_files tests tools -type f -name '*.sh' -print0)

python3 - <<'PY'
import ast, json, pathlib, sys
for p in pathlib.Path('.').rglob('*.json'):
    if '.git' in p.parts:
        continue
    try:
        json.loads(p.read_text())
    except Exception as exc:
        sys.exit(f'invalid JSON: {p}: {exc}')
for p in pathlib.Path('.').rglob('*.py'):
    if '.git' in p.parts:
        continue
    try:
        ast.parse(p.read_text(), filename=str(p))
    except SyntaxError as exc:
        sys.exit(f'invalid Python: {p}: {exc}')
for p in pathlib.Path('.').rglob('*.sh'):
    if '.git' in p.parts:
        continue
    lines = p.read_text().splitlines()
    index = 0
    while index < len(lines):
        import re
        match = re.search(r"<<'(?P<marker>PY[A-Z0-9_]*)'", lines[index])
        if not match:
            index += 1
            continue
        marker = match.group('marker')
        start = index + 1
        end = start
        while end < len(lines) and lines[end] != marker:
            end += 1
        if end == len(lines):
            sys.exit(f'unterminated Python heredoc {marker} in {p}:{index+1}')
        try:
            ast.parse('\n'.join(lines[start:end]) + '\n', filename=f'{p}:{index+2}')
        except SyntaxError as exc:
            sys.exit(f'invalid Python heredoc in {p}:{index+2}: {exc}')
        index = end + 1
print('JSON files, Python files and Python heredocs valid')
PY

# The test suite and the starters also run on macOS, which still ships
# bash 3.2. Constructs introduced in bash 4 must not appear there.
portable_paths="tests START-GITHUB-BUILD-MAC.command START-GITHUB-BUILD-LINUX.sh"
for construct in 'mapfile' 'readarray' 'declare -A' '\${[A-Za-z_]*,,}' '\${[A-Za-z_]*\^\^}'; do
  if grep -RIn --exclude="$(basename "$0")" -E "$construct" $portable_paths 2>/dev/null | grep -q .; then
    echo "bash 4 only construct '${construct}' found in a file that must run on macOS:" >&2
    grep -RIn --exclude="$(basename "$0")" -E "$construct" $portable_paths >&2
    exit 1
  fi
done

echo "Shell syntax and strict-mode audit: PASS (${count} scripts, bash 3.2 clean)"

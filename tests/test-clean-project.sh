#!/usr/bin/env bash
# This project is a clean restart on GNOME. Nothing from the previous
# KDE/Plasma generation may creep back in, and no build residue is allowed.
set -Eeuo pipefail
cd "$(dirname "$0")/.."

fail() { echo "CLEAN PROJECT FAILED: $*" >&2; exit 1; }

# 1. No Plasma/KDE artefacts.
for pattern in plasma plasmoids aurorae kvantum kwinrc sddm look-and-feel latte; do
  if find . -path ./.git -prune -o -iname "*${pattern}*" -print | grep -q .; then
    fail "leftover from the KDE generation: *${pattern}*"
  fi
done
# The scan covers the whole repository including the test suite. Only the two
# tests that must name these patterns in order to search for them are excluded.
if grep -RIl -Ei \
     'kwriteconfig|plasmashell|kdecoration|Kvantum|aurorae|org\.kde\.plasma|look-and-feel|LiMaD-MacTahoe-Active|WhiteSur-Active' \
     --exclude='test-clean-project.sh' --exclude='test-limad-apps.sh' \
     system_files build_files tests Containerfile .github 2>/dev/null \
     | grep -q .; then
  fail 'KDE-specific references still present'
fi

# Every test must be part of the suite; an orphaned test is never run and rots.
while IFS= read -r t; do
  grep -Fq "tests/$(basename "$t")" tests/validate.sh \
    || fail "test $(basename "$t") is not registered in tests/validate.sh"
done < <(find tests -name 'test-*.sh')

# 2. No build or editor residue.
if find . -path ./.git -prune -o -type f \
     \( -name '*.iso' -o -name '*.zip' -o -name '*.bak' -o -name '*.old' -o -name '*~' \
        -o -name '.DS_Store' -o -name '*.orig' -o -name '*.rej' \) -print | grep -q .; then
  fail 'build or editor residue found'
fi
if find . -path ./.git -prune -o -type d \
     \( -name '__pycache__' -o -name 'node_modules' -o -name '.cache' \) -print | grep -q .; then
  fail 'residue directory found'
fi

# 3. Nothing large enough to trouble GitHub. The vendored Anycubic package is
#    deliberately split into parts that stay well below the 100 MB hard limit.
python3 - <<'PY'
from pathlib import Path
import sys
limit = 95 * 1024 * 1024
big = [(str(p), p.stat().st_size) for p in Path('.').rglob('*')
       if p.is_file() and '.git' not in p.parts and p.stat().st_size >= limit]
if big:
    sys.exit(f'file too large for GitHub: {big}')
parts = sorted(Path('build_files/vendor/anycubic').glob('*.deb.part[0-9][0-9]'))
if len(parts) != 2:
    sys.exit(f'expected exactly two Anycubic package parts, found {len(parts)}')
if list(Path('build_files/vendor/anycubic').glob('*.deb')):
    sys.exit('the reassembled Anycubic DEB must never be committed')
PY

# 4. Everything under system_files must be a real, non-empty file.
while IFS= read -r -d '' f; do
  [[ -s "$f" ]] || fail "empty file in system_files: $f"
done < <(find system_files -type f -print0)

# 5. The image must not ship .desktop launchers for programs it does not carry.
if find system_files -name '*.desktop' | grep -q .; then
  while IFS= read -r desktop; do
    exec_line="$(grep -m1 '^Exec=' "$desktop" | cut -d= -f2- | awk '{print $1}')"
    [[ -n "$exec_line" ]] || fail "$desktop has no Exec line"
    if [[ "$exec_line" == /* && ! -e "system_files${exec_line}" ]]; then
      fail "$desktop points at ${exec_line}, which this repository does not ship"
    fi
  done < <(find system_files -name '*.desktop')
fi

# In an OSTree image /root is a symlink to /var/roothome and /var is not
# populated during the build. Writing there breaks the build - and it once did.
# The pattern matches only absolute paths, so "$TMP/root/..." inside an
# extracted package tree stays allowed.
absolute_forbidden='(^|[[:space:]"'"'"'=(])(/root/|/var/home/|/var/roothome)'
if grep -RInE --exclude="$(basename "$0")" "$absolute_forbidden" build_files 2>/dev/null \
   | grep -Ev '^[^:]*:[0-9]+:[[:space:]]*#' | grep -q .; then
  echo "build scripts must not use /root or /var paths (not available in an OSTree image):" >&2
  grep -RInE --exclude="$(basename "$0")" "$absolute_forbidden" build_files >&2
  exit 1
fi

echo "Clean GNOME project audit: PASS"

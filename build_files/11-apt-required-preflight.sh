#!/usr/bin/env bash
set -Eeuo pipefail
LIST="${1:-/opt/limad-build/packages-required.txt}"
[[ -r "$LIST" ]] || { echo "FATAL: Paketliste fehlt: $LIST" >&2; exit 1; }

missing=()
checked=0
while IFS= read -r pkg; do
  [[ -n "$pkg" ]] || continue
  ((checked+=1))
  candidate="$(apt-cache policy "$pkg" 2>/dev/null | awk '/Candidate:/ {print $2; exit}')"
  if [[ -z "$candidate" || "$candidate" == "(none)" ]]; then
    missing+=("$pkg")
  fi
done < <(grep -Ev '^\s*(#|$)' "$LIST")

echo "APT Pflichtpakete geprüft: $checked"
if ((${#missing[@]})); then
  echo 'FATAL: Diese Pflichtpakete sind in den aktivierten Ubuntu-26.04-Quellen nicht auflösbar:' >&2
  printf '  - %s\n' "${missing[@]}" >&2
  exit 1
fi
echo 'APT Pflichtpaket-Preflight: OK'

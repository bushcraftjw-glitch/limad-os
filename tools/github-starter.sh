#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

printf '\nLiMaD OS 3.0 – GitHub Build Starter\n'
printf 'Basis: Ubuntu 26.04 LTS + GNOME 50\n\n'

for cmd in git curl sed; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "Fehlt: $cmd" >&2; exit 1; }
done
bash tests/validate.sh

ensure_gh() {
  if command -v gh >/dev/null 2>&1; then
    return 0
  fi

  echo
  echo 'GitHub CLI (gh) fehlt. Installation wird versucht …'
  if command -v brew >/dev/null 2>&1; then
    brew install gh
  elif command -v apt-get >/dev/null 2>&1; then
    command -v sudo >/dev/null 2>&1 || { echo 'sudo fehlt; GitHub CLI bitte manuell installieren.' >&2; exit 1; }
    sudo apt-get update
    sudo apt-get install -y gh
  else
    cat >&2 <<'MSG'
GitHub CLI (gh) konnte nicht automatisch installiert werden.
Bitte https://cli.github.com/ installieren und den Starter danach erneut starten.
MSG
    exit 1
  fi

  command -v gh >/dev/null 2>&1 || { echo 'GitHub CLI Installation fehlgeschlagen.' >&2; exit 1; }
}

ensure_gh

# Dauerhafte, vom GitHub-CLI verwaltete Anmeldung. Es wird absichtlich kein
# Token in diesem Repository, in origin oder in einem Starter-Skript gespeichert.
if ! gh auth status --hostname github.com >/dev/null 2>&1; then
  echo
  echo 'Einmalige GitHub-Anmeldung wird geöffnet.'
  echo 'Nach der Anmeldung bleibt der Zugang über GitHub CLI gespeichert.'
  gh auth login --hostname github.com --git-protocol https --web
fi
gh auth setup-git >/dev/null

LOGIN="$(gh api user --jq .login)"
[[ -n "$LOGIN" ]] || { echo 'GitHub Benutzername konnte nicht ermittelt werden.' >&2; exit 1; }
echo "GitHub angemeldet als: $LOGIN"

DEFAULT_OWNER="bushcraftjw-glitch"
DEFAULT_REPO="limad-os"
read -r -p "GitHub Benutzer/Organisation [$DEFAULT_OWNER]: " OWNER
OWNER="${OWNER:-$DEFAULT_OWNER}"
read -r -p "Repository [$DEFAULT_REPO]: " REPO
REPO="${REPO:-$DEFAULT_REPO}"
TARGET="$OWNER/$REPO"

if gh repo view "$TARGET" >/dev/null 2>&1; then
  echo "Repository $TARGET existiert bereits. Vorhandene Git-Historie wird erhalten."
else
  read -r -p "Repository privat? [J/n]: " PRIVATE_ANSWER
  case "${PRIVATE_ANSWER:-J}" in
    n|N|nein|NEIN) VISIBILITY=(--public) ;;
    *) VISIBILITY=(--private) ;;
  esac
  echo "Repository $TARGET wird angelegt …"
  gh repo create "$TARGET" "${VISIBILITY[@]}" \
    --description 'LiMaD OS 3.0 – Ubuntu 26.04 LTS + GNOME 50'
fi

# Immer aus dem gelieferten Starter-Stand ein sauberes lokales Git-Repository
# aufbauen. Bei einem bereits vorhandenen Remote wird dessen aktueller main-
# Commit als Eltern-Commit verwendet. Dadurch ist der Push ein Fast-Forward und
# der alte "fetch first"-Fehler tritt nicht mehr auf; die Remote-Historie bleibt.
rm -rf .git
git init -b main >/dev/null
git config user.name "${GIT_AUTHOR_NAME:-LiMaD Build Starter}"
git config user.email "${GIT_AUTHOR_EMAIL:-limad-build@users.noreply.github.com}"
git remote add origin "https://github.com/$TARGET.git"
git add -A

make_main_commit() {
  local tree parent remote_tree commit
  tree="$(git write-tree)"
  if git rev-parse --verify --quiet refs/remotes/origin/main >/dev/null; then
    parent="$(git rev-parse refs/remotes/origin/main)"
    remote_tree="$(git rev-parse refs/remotes/origin/main^{tree})"
    if [[ "$tree" == "$remote_tree" ]]; then
      git update-ref refs/heads/main "$parent"
      return 10
    fi
    commit="$(printf '%s\n' 'LiMaD OS 3.0 Ubuntu starter update' | git commit-tree "$tree" -p "$parent")"
  else
    commit="$(printf '%s\n' 'LiMaD OS 3.0 Ubuntu starter' | git commit-tree "$tree")"
  fi
  git update-ref refs/heads/main "$commit"
  return 0
}

# Remote zuerst laden. Ein leeres neues Repository hat noch keinen main-Branch.
git fetch --quiet origin main 2>/dev/null || true

PUSHED=false
UP_TO_DATE=false
for attempt in 1 2 3; do
  set +e
  make_main_commit
  COMMIT_STATUS=$?
  set -e

  if [[ $COMMIT_STATUS -eq 10 ]]; then
    UP_TO_DATE=true
    echo 'GitHub-Repository enthält bereits exakt diesen Starter-Stand.'
    break
  elif [[ $COMMIT_STATUS -ne 0 ]]; then
    echo 'Lokaler Git-Commit konnte nicht erzeugt werden.' >&2
    exit 1
  fi

  if git push -u origin main; then
    PUSHED=true
    break
  fi

  if [[ $attempt -lt 3 ]]; then
    echo 'Remote wurde zwischenzeitlich geändert. Neuer Stand wird geladen und der Push erneut aufgebaut …'
    git fetch --quiet origin main
  fi
done

if [[ "$PUSHED" != true && "$UP_TO_DATE" != true ]]; then
  echo 'GitHub Push ist nach drei Versuchen fehlgeschlagen.' >&2
  exit 1
fi

# Bei einem neuen Push startet der push-Trigger den Workflow automatisch.
# Wenn exakt derselbe Stand bereits online war, starten wir den Workflow explizit.
if [[ "$UP_TO_DATE" == true ]]; then
  echo 'Starte den GitHub-Build manuell, da kein neuer Commit nötig war …'
  gh workflow run build-limad-os.yml --repo "$TARGET"
fi

echo
echo 'GitHub Build wurde gestartet:'
URL="https://github.com/$TARGET/actions"
echo "$URL"
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL" >/dev/null 2>&1 || true
elif command -v open >/dev/null 2>&1; then
  open "$URL" >/dev/null 2>&1 || true
fi

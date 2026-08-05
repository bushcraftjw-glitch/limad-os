#!/usr/bin/env bash
# LiMaD OS – Build auf GitHub starten (macOS).
# Doppelklicken. Prüft das Projekt, legt das Repository bei Bedarf selbst an,
# lädt alles hoch und startet den Image- und ISO-Bau.
#
# Bewusst ohne bash-4-Konstrukte: macOS liefert bis heute bash 3.2 aus.
set -Eeuo pipefail
cd "$(dirname "$0")"

# shellcheck source=/dev/null
source build_files/versions.env

CONFIG_FILE=".github-target"
GITHUB_OWNER_DEFAULT="bushcraftjw-glitch"
GITHUB_REPO_DEFAULT="limad-os"
API="https://api.github.com"

if [[ -f "$CONFIG_FILE" ]]; then
  # shellcheck source=/dev/null
  source "$CONFIG_FILE"
fi
OWNER="${GITHUB_OWNER:-$GITHUB_OWNER_DEFAULT}"
REPO="${GITHUB_REPOSITORY_NAME:-$GITHUB_REPO_DEFAULT}"

abbruch() {
  echo
  echo "ABBRUCH: $*" >&2
  echo
  read -r -p "Mit Enter schließen." _
  exit 1
}

echo "=============================================="
echo " LiMaD OS ${LIMAD_OS_VERSION}-${LIMAD_BUILD_REVISION} (GNOME)"
echo "=============================================="
echo

command -v git >/dev/null 2>&1 || abbruch "git fehlt. Einmalig 'xcode-select --install' ausführen."
command -v curl >/dev/null 2>&1 || abbruch "curl fehlt."

echo "== 1/5 Lokale Prüfung =="
bash tests/validate.sh
echo

echo "== 2/5 Ziel =="
read -r -p "   GitHub-Konto [${OWNER}]: " eingabe || true
[[ -n "${eingabe:-}" ]] && OWNER="$eingabe"
eingabe=""
read -r -p "   Repository-Name [${REPO}]: " eingabe || true
[[ -n "${eingabe:-}" ]] && REPO="$eingabe"
echo
echo "   1) Neu anlegen     - nur wenn das Repository noch nicht existiert"
echo "   2) Aktualisieren   - vorhandenes Repository sicher aktualisieren (empfohlen)"
echo
read -r -p "   Auswahl [2]: " MODUS || true
[[ -n "${MODUS:-}" ]] || MODUS="2"
echo

# --------------------------------------------------------------------------
# Token-Ablage.
#
# Der Token wird nie im Projektverzeichnis abgelegt - er soll weder ins
# Repository noch in ein Archiv geraten. Auf dem Mac uebernimmt das der
# Schluesselbund, unter Linux der Passwortdienst der Arbeitsumgebung. Gibt es
# keinen von beiden, wird eine Datei nur fuer den eigenen Benutzer verwendet.
# --------------------------------------------------------------------------
KC_SERVICE="LiMaD OS Build"
KC_ACCOUNT="github-token"
TOKEN_DATEI="${HOME}/.config/limad/github-token"

token_laden() {
  if command -v security >/dev/null 2>&1; then
    security find-generic-password -s "$KC_SERVICE" -a "$KC_ACCOUNT" -w 2>/dev/null && return 0
  elif command -v secret-tool >/dev/null 2>&1; then
    secret-tool lookup service "$KC_SERVICE" account "$KC_ACCOUNT" 2>/dev/null && return 0
  fi
  [[ -f "$TOKEN_DATEI" ]] && cat "$TOKEN_DATEI" 2>/dev/null && return 0
  return 1
}

token_sichern() {
  if command -v security >/dev/null 2>&1; then
    security add-generic-password -U -s "$KC_SERVICE" -a "$KC_ACCOUNT" -w "$1" >/dev/null 2>&1 \
      && { echo "   im Schluesselbund gespeichert"; return 0; }
  elif command -v secret-tool >/dev/null 2>&1; then
    printf '%s' "$1" | secret-tool store --label="$KC_SERVICE" service "$KC_SERVICE" account "$KC_ACCOUNT" >/dev/null 2>&1 \
      && { echo "   im Passwortdienst gespeichert"; return 0; }
  fi
  mkdir -p "$(dirname "$TOKEN_DATEI")"
  ( umask 077; printf '%s\n' "$1" > "$TOKEN_DATEI" )
  chmod 600 "$TOKEN_DATEI"
  echo "   gespeichert in ${TOKEN_DATEI} (nur fuer dich lesbar)"
}

token_vergessen() {
  if command -v security >/dev/null 2>&1; then
    security delete-generic-password -s "$KC_SERVICE" -a "$KC_ACCOUNT" >/dev/null 2>&1 || true
  elif command -v secret-tool >/dev/null 2>&1; then
    secret-tool clear service "$KC_SERVICE" account "$KC_ACCOUNT" >/dev/null 2>&1 || true
  fi
  rm -f "$TOKEN_DATEI"
}

token_erfragen() {
  echo "   Es wird ein Personal Access Token benoetigt."
  echo "   github.com -> Settings -> Developer settings"
  echo "   -> Personal access tokens -> Tokens (classic)"
  echo "   Benoetigte Haken: 'repo' und 'workflow'"
  echo "   ('workflow' ist zwingend - sonst werden Dateien unter"
  echo "    .github/workflows/ abgelehnt.)"
  echo "   Die Eingabe bleibt unsichtbar."
  echo
  read -r -s -p "   Token: " TOKEN || true
  echo
  [[ -n "${TOKEN:-}" ]] || abbruch "Ohne Token kann das Repository nicht verwaltet werden."
  NEUER_TOKEN="ja"
}

echo "== 3/5 Anmeldung =="
NEUER_TOKEN="nein"
TOKEN="$(token_laden || true)"
if [[ -n "${TOKEN:-}" ]]; then
  echo "   gespeicherter Token gefunden"
else
  token_erfragen
fi

BODY="/tmp/limad-api-body.$$"
trap 'rm -f "$BODY"' EXIT

api() {
  # api METHODE PFAD [DATEN] -> gibt den HTTP-Status aus
  methode="$1"
  pfad="$2"
  daten="${3:-}"
  if [[ -n "$daten" ]]; then
    curl -sS -o "$BODY" -w '%{http_code}' -X "$methode" \
      -H "Authorization: Bearer ${TOKEN}" \
      -H "Accept: application/vnd.github+json" \
      -H "Content-Type: application/json" \
      -d "$daten" "${API}${pfad}"
  else
    curl -sS -o "$BODY" -w '%{http_code}' -X "$methode" \
      -H "Authorization: Bearer ${TOKEN}" \
      -H "Accept: application/vnd.github+json" "${API}${pfad}"
  fi
}

github_meldung() {
  sed -n 's/.*"message"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$BODY" | head -n 1
}

STATUS="$(api GET /user)"
if [[ "$STATUS" != "200" ]]; then
  echo "   Der gespeicherte Token wurde abgelehnt (HTTP ${STATUS}). $(github_meldung)"
  echo "   Er wird verworfen."
  token_vergessen
  echo
  token_erfragen
  STATUS="$(api GET /user)"
  [[ "$STATUS" == "200" ]] || abbruch "Der Token wurde von GitHub abgelehnt (HTTP ${STATUS}). $(github_meldung)"
fi
ANGEMELDET="$(sed -n 's/.*"login"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$BODY" | head -n 1)"
echo "   angemeldet als ${ANGEMELDET}"

if [[ "$NEUER_TOKEN" == "ja" ]]; then
  read -r -p "   Token fuer kuenftige Laeufe speichern? [J/n]: " SPEICHERN || true
  if [[ "${SPEICHERN:-}" != "n" && "${SPEICHERN:-}" != "N" ]]; then
    token_sichern "$TOKEN"
  fi
fi

echo
echo "== 4/5 Repository vorbereiten =="
STATUS="$(api GET "/repos/${OWNER}/${REPO}")"

if [[ "$MODUS" == "1" && "$STATUS" == "200" ]]; then
  echo "   ${OWNER}/${REPO} existiert bereits."
  echo "   Sicherheitsmodus: Das Repository wird niemals automatisch geloescht."
  echo "   Es wird stattdessen normal aktualisiert."
  MODUS="2"
fi

if [[ "$STATUS" == "404" ]]; then
  echo "   ${OWNER}/${REPO} wird angelegt"
  DATEN="{\"name\":\"${REPO}\",\"description\":\"LiMaD OS - Bazzite GNOME mit MacTahoe-Design\",\"private\":true,\"auto_init\":false,\"has_issues\":false,\"has_wiki\":false}"
  if [[ "$OWNER" == "$ANGEMELDET" ]]; then
    STATUS="$(api POST /user/repos "$DATEN")"
  else
    STATUS="$(api POST "/orgs/${OWNER}/repos" "$DATEN")"
  fi
  if [[ "$STATUS" != "201" ]]; then
    echo
    echo "   Anlegen nicht moeglich (HTTP ${STATUS}). GitHub meldet: $(github_meldung)"
    echo
    case "$STATUS" in
      403|404)
        echo "   Der Token ist gueltig, darf aber keine Repositories anlegen."
        echo "   Das ist bei 'Fine-grained tokens' der Normalfall - die koennen das"
        echo "   nur mit der Kontoberechtigung 'Administration'."
        echo
        echo "   Zwei Wege:"
        echo "   A) Klassischen Token verwenden:"
        echo "      Settings -> Developer settings -> Personal access tokens"
        echo "      -> Tokens (classic) -> Generate new token (classic)"
        echo "      Haken bei 'repo' und 'workflow'."
        echo "   B) Repository einmal von Hand anlegen:"
        echo "      https://github.com/new  ->  Name '${REPO}'"
        echo "      OHNE README, OHNE .gitignore, OHNE Lizenz."
        ;;
      422)
        echo "   Der Name '${REPO}' ist bereits vergeben oder ungueltig."
        ;;
    esac
    echo
    read -r -p "   Repository jetzt von Hand angelegt? Dann Enter (oder 'x' zum Abbrechen): " WEITER || true
    [[ "${WEITER:-}" == "x" ]] && abbruch "Auf Wunsch beendet."
    STATUS="$(api GET "/repos/${OWNER}/${REPO}")"
    [[ "$STATUS" == "200" ]] || abbruch "Das Repository ist weiterhin nicht erreichbar (HTTP ${STATUS})."
    echo "   gefunden"
  else
    echo "   angelegt"
  fi
elif [[ "$STATUS" == "200" ]]; then
  echo "   vorhanden, wird ueberschrieben"
else
  abbruch "Das Repository ist nicht erreichbar (HTTP ${STATUS})."
fi

# Refresh the repository response after create/delete handling.  The API body
# may otherwise still contain the response from a failed delete request.
STATUS="$(api GET "/repos/${OWNER}/${REPO}")"
[[ "$STATUS" == "200" ]] || abbruch "Repository-Berechtigungen konnten nicht geprüft werden (HTTP ${STATUS}). $(github_meldung)"

# Fail before creating a local commit when the stored token can read the
# repository but cannot push to it.  This prevents the late HTTP-403 that used
# to appear only after the complete validation and commit step.
CAN_PUSH="$(python3 - "$BODY" <<'PYREPO'
import json
import sys
try:
    data=json.load(open(sys.argv[1], encoding='utf-8'))
except Exception:
    print('unknown')
else:
    permissions=data.get('permissions') or {}
    print('true' if permissions.get('push') else 'false')
PYREPO
)"
if [[ "$CAN_PUSH" != "true" ]]; then
  abbruch "Der angemeldete GitHub-Token von ${ANGEMELDET} hat keinen Schreibzugriff auf ${OWNER}/${REPO}. Bitte einen Token des Eigentümers verwenden oder ${ANGEMELDET} als Mitarbeiter mit Schreibrecht hinzufügen."
fi

printf 'GITHUB_OWNER="%s"\nGITHUB_REPOSITORY_NAME="%s"\n' "$OWNER" "$REPO" > "$CONFIG_FILE"

echo
echo "== 5/5 Hochladen =="
if [[ ! -d .git ]]; then
  git init -b main >/dev/null
fi
git add -A
if git rev-parse HEAD >/dev/null 2>&1 && git diff --cached --quiet; then
  echo "   Keine Aenderungen gegenueber dem letzten Commit."
else
  git -c user.name="LiMaD Build" -c user.email="build@limad.local" \
    commit -q -m "LiMaD OS ${LIMAD_OS_VERSION}-${LIMAD_BUILD_REVISION} ($(date -u +%Y-%m-%dT%H:%M:%SZ))"
  echo "   Commit erstellt"
fi

echo "   Etwa 155 MB, das dauert je nach Leitung ein paar Minuten."
# Der Token steht nur in dieser einen Befehlszeile und landet nicht in der
# Git-Konfiguration.
PUSH_LOG="/tmp/limad-push.$$"
if git push --force \
     "https://x-access-token:${TOKEN}@github.com/${OWNER}/${REPO}.git" main \
     >"$PUSH_LOG" 2>&1; then
  echo "   hochgeladen"
  rm -f "$PUSH_LOG"
else
  echo
  if grep -q 'workflow' "$PUSH_LOG"; then
    echo "   GitHub hat das Hochladen abgelehnt: dem Token fehlt der Haken"
    echo "   'workflow'. Ohne ihn duerfen keine Dateien unter"
    echo "   .github/workflows/ angelegt oder geaendert werden."
    echo
    echo "   So beheben - der Token bleibt derselbe:"
    echo "   1. github.com -> Settings -> Developer settings"
    echo "   2. Personal access tokens -> Tokens (classic)"
    echo "   3. Den vorhandenen Token anklicken"
    echo "   4. Haken bei 'workflow' setzen"
    echo "   5. Unten 'Update token'"
    echo
    echo "   Danach dieses Skript erneut starten (Auswahl 2)."
  else
    echo "   Das Hochladen ist fehlgeschlagen:"
    tail -n 15 "$PUSH_LOG" | sed 's/^/   | /'
  fi
  rm -f "$PUSH_LOG"
  TOKEN=""
  unset TOKEN
  echo
  read -r -p "Mit Enter schliessen." _
  exit 1
fi
TOKEN=""
unset TOKEN

echo
echo "=============================================="
echo " Fertig. Der Build laeuft hier:"
echo "   https://github.com/${OWNER}/${REPO}/actions"
echo
echo " Empfehlung: zuerst 'Theme-Schnelltest' starten"
echo " (Actions -> Theme-Schnelltest -> Run workflow),"
echo " erst danach den vollstaendigen Build."
echo "=============================================="
echo
read -r -p "Mit Enter schliessen." _

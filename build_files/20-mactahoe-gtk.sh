#!/usr/bin/env bash
# Builds the MacTahoe GTK theme from the pinned upstream tag and installs it
# system-wide as "LiMaD".
#
# The upstream installer changes its accepted options between releases and
# reports rejected options only through its exit status. This step therefore
# tries a sequence of invocations from feature-rich to minimal, logs the full
# output of every attempt, and derives the produced theme names from what is
# actually on disk instead of assuming them.
set -Eeuo pipefail

# shellcheck source=/dev/null
source /opt/limad-build/versions.env

readonly WORK="/tmp/limad-build/mactahoe"
readonly SRC_SHARE="/usr/share/limad-source/mactahoe-gtk-theme"
readonly LOG="/tmp/limad-build/mactahoe-install.log"

echo ":: Cloning MacTahoe GTK theme ${MACTAHOE_TAG}"
rm -rf "$WORK"
mkdir -p "$(dirname "$WORK")"
git clone --depth 1 --branch "$MACTAHOE_TAG" "$MACTAHOE_REPO" "$WORK"

pushd "$WORK" >/dev/null

CHECKED_OUT="$(git describe --tags --exact-match 2>/dev/null || true)"
if [[ "$CHECKED_OUT" != "$MACTAHOE_TAG" ]]; then
  echo "FATAL: expected tag ${MACTAHOE_TAG}, got '${CHECKED_OUT}'" >&2
  exit 1
fi
COMMIT="$(git rev-parse HEAD)"
echo "   commit ${COMMIT}"

# ---------------------------------------------------------------------------
# Make the installer talk.
#
# The upstream libraries redirect their own stderr into a temporary file that
# is deleted again on exit, so a failure inside them leaves no trace at all.
# Neutralising that redirect is what turns "exit status 2 and silence" into an
# actual error message.
# ---------------------------------------------------------------------------
echo ":: Environment"
echo "   bash        $(bash --version | head -n1)"
echo "   repository  $(ls -1 | tr '\n' ' ')"
echo "   libs        $(ls -1 libs 2>/dev/null | tr '\n' ' ')"

# ---------------------------------------------------------------------------
# Container-safe identity.
#
# lib-core.sh determines the user with `logname`, which needs a login session
# and a utmp entry. A container build has neither, so MY_USERNAME ends up empty
# and the following `getent passwd ''` aborts the library under `set -Eeo
# pipefail` - before a single option is ever parsed.
# ---------------------------------------------------------------------------
export USER="root"
export LOGNAME="root"
export SUDO_USER="root"
export HOME="${HOME:-/root}"
echo ":: Identity for the installer: USER=${USER} HOME=${HOME} UID=${UID}"

# ---------------------------------------------------------------------------
# Terminal.
#
# A container build has no terminal, so TERM is unset. The installer restores
# the cursor and clears the screen after every message; both fail without TERM,
# and because the upstream libraries run with `set -Eeo pipefail` and
# `trap signal_error ERR`, that purely cosmetic failure aborts the whole run.
# ---------------------------------------------------------------------------
export TERM="${TERM:-xterm-256color}"

# ---------------------------------------------------------------------------
# Shims.
#
# `sudo`  - the installer probes privileges with it, which cannot work in a
#           container without a terminal even though the build is already root.
# `setterm`, `clear`, `tput` - cosmetic terminal commands that must never be
#           able to fail the build.
# All of them live in a temporary directory and never enter the image.
# ---------------------------------------------------------------------------
readonly SHIM_DIR="/tmp/limad-build/shim"
install -d "$SHIM_DIR"

cat > "${SHIM_DIR}/sudo" <<'SHIM'
#!/usr/bin/env bash
# LiMaD build shim: the build already runs as root.
while [[ $# -gt 0 ]]; do
  case "$1" in
    -v|-n|-E|-H|-k|-S|-i|-s) shift ;;
    -u|-g|-p) shift 2 ;;
    --) shift; break ;;
    -*) shift ;;
    *) break ;;
  esac
done
(($# == 0)) && exit 0
exec "$@"
SHIM

for cosmetic in setterm clear reset; do
  cat > "${SHIM_DIR}/${cosmetic}" <<'SHIM'
#!/usr/bin/env bash
# LiMaD build shim: no terminal here, so this is a no-op that always succeeds.
exit 0
SHIM
done

cat > "${SHIM_DIR}/tput" <<'SHIM'
#!/usr/bin/env bash
# LiMaD build shim: answer the few queries that matter, never fail.
case "${1:-}" in
  cols) echo 100 ;;
  lines) echo 40 ;;
esac
exit 0
SHIM

chmod 0755 "${SHIM_DIR}"/*
export PATH="${SHIM_DIR}:${PATH}"
echo ":: shims active: sudo, setterm, clear, reset, tput (TERM=${TERM})"

echo ":: Making the user detection container-safe"
if grep -rqn '\blogname\b' libs/ *.sh 2>/dev/null; then
  grep -rn '\blogname\b' libs/ *.sh 2>/dev/null | sed 's/^/   | /' || true
  find libs -type f -name '*.sh' -print0 2>/dev/null | xargs -0 --no-run-if-empty \
    sed -i 's/\blogname\b/id -un/g'
  sed -i 's/\blogname\b/id -un/g' install.sh tweaks.sh 2>/dev/null || true
  echo "   replaced logname with 'id -un'"
else
  echo "   no logname call found"
fi

echo ":: Disabling the internal stderr redirect of the upstream libraries"
REDIRECTS="$(grep -rn 'exec[[:space:]]*2>' libs/ *.sh 2>/dev/null || true)"
if [[ -n "$REDIRECTS" ]]; then
  printf '   found: %s\n' "$REDIRECTS"
  # The redirect can sit anywhere in a line, e.g. `mkdir -p "$D"; exec 2> "$F"`.
  find libs -type f -name '*.sh' -print0 2>/dev/null | xargs -0 --no-run-if-empty \
    sed -i 's|exec[[:space:]]*2>[[:space:]]*[^;&|]*|: # LiMaD stderr redirect disabled|g'
  sed -i 's|exec[[:space:]]*2>[[:space:]]*[^;&|]*|: # LiMaD stderr redirect disabled|g' \
    install.sh tweaks.sh 2>/dev/null || true
  if grep -rqn 'exec[[:space:]]*2>' libs/ *.sh 2>/dev/null; then
    echo "   WARNING: a redirect survived:" >&2
    grep -rn 'exec[[:space:]]*2>' libs/ *.sh 2>/dev/null | sed 's/^/   | /' >&2
  else
    echo "   disabled"
  fi
else
  echo "   none found"
fi

# Can the libraries even be loaded? This is where a silent failure hides.
echo ":: Loading the installer libraries"
if bash -c 'set -x; REPO_DIR="$PWD"; source ./libs/lib-install.sh
            echo "LIBS_OK MY_USERNAME=${MY_USERNAME:-unset} MY_HOME=${MY_HOME:-unset}"' \
     >"$LOG" 2>&1; then
  echo "   libraries load cleanly"
  grep -m1 'LIBS_OK' "$LOG" | sed 's/^/   | /' || true
else
  echo "   LIBRARIES FAILED TO LOAD - trace follows:"
  tail -n 40 "$LOG" | sed 's/^/   | /'
fi

# Record which options this release actually understands.
echo ":: Installer options of this release"
./install.sh --help >"$LOG" 2>&1 || true
if [[ -s "$LOG" ]]; then
  sed 's/^/   | /' "$LOG"
else
  echo "   | (the installer produced no output at all)"
fi

# A failed attempt can leave a half-written theme behind. Every attempt
# therefore starts from a clean slate, so the name detection below can only
# ever find the result of the attempt that actually succeeded.
# Every attempt installs into a staging directory first. Only the result of a
# successful attempt is copied into the image, so a half-written theme can
# never reach /usr/share/themes.
readonly STAGE="/tmp/limad-theme-stage"

clean_themes() {
  rm -rf "$STAGE"
  install -d "$STAGE"
}

run_attempt() {
  local label="$1"; shift
  local code=0
  echo ":: Attempt: ${label}"
  echo "   ./install.sh $*"
  clean_themes
  ./install.sh "$@" >"$LOG" 2>&1 || code=$?
  if ((code == 0)); then
    echo "   succeeded"
    return 0
  fi
  echo "   failed with exit status ${code}; last lines of its output:"
  tail -n 30 "$LOG" 2>/dev/null | sed 's/^/   | /' || true
  # Whatever the installer still wrote into its own error log.
  local upstream_log
  upstream_log="$(find /tmp -maxdepth 3 -name 'error_log.txt' -newer "$LOG" 2>/dev/null | head -n1)"
  if [[ -n "$upstream_log" && -s "$upstream_log" ]]; then
    echo "   installer error log:"
    tail -n 30 "$upstream_log" | sed 's/^/   > /'
  fi
  # Remove whatever this attempt managed to write before failing.
  clean_themes
  return 1
}

# Ordered from the full LiMaD look down to a plain dark theme. The first
# attempt that succeeds wins; only if every attempt fails does the build stop.
INSTALLED=0
# "--silent-mode" is deliberately absent: it makes the installer probe sudo,
# which fails in a container, and it provides nothing a build needs.
ATTEMPTS=(
  "full look|-d|${STAGE}|-n|${LIMAD_GTK_THEME_NAME}|-c|dark|-t|purple|--round"
  "without accent colour|-d|${STAGE}|-n|${LIMAD_GTK_THEME_NAME}|-c|dark|--round"
  "without rounded windows|-d|${STAGE}|-n|${LIMAD_GTK_THEME_NAME}|-c|dark"
  "dark, single opacity|-d|${STAGE}|-n|${LIMAD_GTK_THEME_NAME}|-c|dark|-o|normal"
  "defaults only|-d|${STAGE}|-n|${LIMAD_GTK_THEME_NAME}"
)
for attempt in "${ATTEMPTS[@]}"; do
  IFS='|' read -r -a parts <<< "$attempt"
  label="${parts[0]}"
  if run_attempt "$label" "${parts[@]:1}"; then
    INSTALLED=1
    break
  fi
done

if [[ "$INSTALLED" != "1" ]]; then
  echo "FATAL: the MacTahoe installer rejected every supported option set." >&2
  echo "       See the option list printed above to adjust 20-mactahoe-gtk.sh." >&2
  exit 1
fi

echo ":: Publishing the staged theme into the image"
mapfile -t STAGED < <(find "$STAGE" -maxdepth 1 -mindepth 1 -type d -printf '%f\n' | sort)
if ((${#STAGED[@]} == 0)); then
  echo "FATAL: the installer reported success but staged no theme" >&2
  exit 1
fi
echo "   staged: ${STAGED[*]}"
install -d /usr/share/themes
for staged in "${STAGED[@]}"; do
  rm -rf "/usr/share/themes/${staged}"
  cp -a "${STAGE}/${staged}" /usr/share/themes/
done
rm -rf "$STAGE"

# Derive the real theme names. Upstream appends colour, opacity and accent to
# the base name, so the result is not predictable across releases.
mapfile -t THEMES < <(find /usr/share/themes -maxdepth 1 -type d -name "${LIMAD_GTK_THEME_NAME}*" -printf '%f\n' | sort)
if ((${#THEMES[@]} == 0)); then
  echo "FATAL: the installer reported success but produced no theme directory" >&2
  ls -1 /usr/share/themes >&2
  exit 1
fi
echo ":: Installed themes: ${THEMES[*]}"

GTK_THEME_ACTUAL=""
for candidate in "${THEMES[@]}"; do
  if [[ "$candidate" == "${LIMAD_GTK_THEME_NAME}-Dark" ]]; then
    GTK_THEME_ACTUAL="$candidate"
    break
  fi
done
if [[ -z "$GTK_THEME_ACTUAL" ]]; then
  for candidate in "${THEMES[@]}"; do
    if [[ "$candidate" == *Dark* ]]; then
      GTK_THEME_ACTUAL="$candidate"
      break
    fi
  done
fi
[[ -n "$GTK_THEME_ACTUAL" ]] || GTK_THEME_ACTUAL="${THEMES[0]}"

SHELL_THEME_ACTUAL="$GTK_THEME_ACTUAL"
for candidate in "${THEMES[@]}"; do
  if [[ -f "/usr/share/themes/${candidate}/gnome-shell/gnome-shell.css" ]]; then
    SHELL_THEME_ACTUAL="$candidate"
    [[ "$candidate" == *Dark* ]] && break
  fi
done

install -d /usr/share/limad
cat > /usr/share/limad/theme-names.env <<EOF
LIMAD_GTK_THEME_ACTUAL="${GTK_THEME_ACTUAL}"
LIMAD_SHELL_THEME_ACTUAL="${SHELL_THEME_ACTUAL}"
EOF
echo ":: GTK theme:   ${GTK_THEME_ACTUAL}"
echo ":: Shell theme: ${SHELL_THEME_ACTUAL}"

# GNOME shell tweaks are cosmetic; a rejected option must not fail the build.
echo ":: Applying gnome-shell tweaks"
for shell_args in "-d /usr/share/themes -n ${LIMAD_GTK_THEME_NAME} -c dark --shell -i simple" \
                  "-d /usr/share/themes -n ${LIMAD_GTK_THEME_NAME} -c dark --shell"; do
  # shellcheck disable=SC2086
  if ./install.sh $shell_args >"$LOG" 2>&1; then
    echo "   applied: ${shell_args}"
    break
  fi
  echo "   skipped: ${shell_args}"
done

# libadwaita / GTK 4 applications cannot be themed through settings, so the
# theme files are placed into the skeleton config every new user inherits.
echo ":: Installing the libadwaita (GTK 4) theme into /etc/skel"
# Upstream deliberately refuses "--libadwaita" when running as root
# ("Do not run '--libadwaita' option with sudo!"), and a container build is
# always root. The theme files are therefore copied directly.
install -d /etc/skel/.config
if [[ -d "/usr/share/themes/${GTK_THEME_ACTUAL}/gtk-4.0" ]]; then
  rm -rf /etc/skel/.config/gtk-4.0
  install -d /etc/skel/.config/gtk-4.0
  cp -a "/usr/share/themes/${GTK_THEME_ACTUAL}/gtk-4.0/." /etc/skel/.config/gtk-4.0/
  echo "   copied from ${GTK_THEME_ACTUAL}"
else
  echo "   WARNING: ${GTK_THEME_ACTUAL} has no gtk-4.0 directory" >&2
fi

if [[ "${LIMAD_INSTALL_GDM_THEME}" == "1" ]]; then
  echo ":: Applying LiMaD MacTahoe branding to Ubuntu GDM"

  GDM_UNIT=""
  for candidate in /usr/lib/systemd/system/gdm3.service /lib/systemd/system/gdm3.service /usr/lib/systemd/system/gdm.service; do
    if [[ -f "$candidate" ]]; then
      # Canonicalize because Ubuntu uses usr-merge: /lib may resolve to /usr/lib.
      # Comparing a raw /lib path with readlink -f (/usr/lib) produced a false failure.
      GDM_UNIT="$(readlink -f "$candidate")"
      break
    fi
  done
  [[ -n "$GDM_UNIT" && -f "$GDM_UNIT" ]] || { echo "FATAL: Ubuntu GDM service is missing" >&2; exit 1; }

  systemctl disable sddm.service plasmalogin.service >/dev/null 2>&1 || true
  systemctl enable "$(basename "$GDM_UNIT")" >/dev/null 2>&1 || true
  install -d /etc/systemd/system
  ln -sfn "$GDM_UNIT" /etc/systemd/system/display-manager.service
  ACTIVE_DM="$(readlink -f /etc/systemd/system/display-manager.service || true)"
  if [[ -z "$ACTIVE_DM" || "$ACTIVE_DM" != "$GDM_UNIT" ]]; then
    echo "FATAL: display manager link was not set to canonical GDM service" >&2
    echo "       expected: $GDM_UNIT" >&2
    echo "       actual:   ${ACTIVE_DM:-<unresolved>}" >&2
    exit 1
  fi
  echo "   GDM service: ${ACTIVE_DM}"

  GDM_BACKGROUND="/usr/share/backgrounds/limad/${LIMAD_DEFAULT_WALLPAPER}"
  [[ -s "$GDM_BACKGROUND" ]] || { echo "FATAL: LiMaD GDM background missing: $GDM_BACKGROUND" >&2; exit 1; }

  # MacTahoe does not necessarily overwrite the generic GNOME Shell resource.
  # On Ubuntu/Yaru it prefers the Yaru GDM resource; on other GNOME systems it
  # can use /etc/alternatives or the generic resource. Snapshot every existing
  # candidate by canonical path, then verify which resource actually changed.
  # This mirrors the target selection used by MacTahoe's install_only_gdm_theme().
  GDM_RESOURCE_CANDIDATES=(
    /usr/share/gnome-shell/theme/Pop/gnome-shell-theme.gresource
    /usr/share/gnome-shell/theme/Yaru/gnome-shell-theme.gresource
    /usr/share/gnome-shell/theme/ZorinBlue-Dark/gnome-shell-theme.gresource
    /usr/share/gnome-shell/theme/ZorinBlue-Light/gnome-shell-theme.gresource
    /usr/share/gnome-shell/gnome-shell-theme.gresource
    /etc/alternatives/gdm3-theme.gresource
  )
  declare -A GDM_RESOURCE_BEFORE=()
  for candidate in "${GDM_RESOURCE_CANDIDATES[@]}"; do
    [[ -e "$candidate" ]] || continue
    canonical="$(readlink -f "$candidate" 2>/dev/null || true)"
    [[ -n "$canonical" && -s "$canonical" ]] || continue
    if [[ -z "${GDM_RESOURCE_BEFORE[$canonical]+x}" ]]; then
      GDM_RESOURCE_BEFORE["$canonical"]="$(sha256sum "$canonical" | awk '{print $1}')"
      echo "   GDM resource candidate: ${canonical}"
    fi
  done
  ((${#GDM_RESOURCE_BEFORE[@]} > 0)) || { echo "FATAL: no usable GNOME/GDM theme resource found" >&2; exit 1; }

  if ! ./tweaks.sh -g -b "$GDM_BACKGROUND" -nd -nb -c dark -t purple >"$LOG" 2>&1; then
    echo "FATAL: MacTahoe GDM theming failed on Ubuntu" >&2
    tail -n 40 "$LOG" 2>/dev/null | sed 's/^/   | /' >&2 || true
    exit 1
  fi

  GDM_RESOURCE=""
  BEFORE_SHA256=""
  AFTER_SHA256=""
  for canonical in "${!GDM_RESOURCE_BEFORE[@]}"; do
    [[ -s "$canonical" ]] || continue
    after="$(sha256sum "$canonical" | awk '{print $1}')"
    if [[ "$after" != "${GDM_RESOURCE_BEFORE[$canonical]}" ]]; then
      GDM_RESOURCE="$canonical"
      BEFORE_SHA256="${GDM_RESOURCE_BEFORE[$canonical]}"
      AFTER_SHA256="$after"
      break
    fi
  done
  if [[ -z "$GDM_RESOURCE" ]]; then
    echo "FATAL: MacTahoe reported success but none of the GDM resource candidates changed" >&2
    echo "       candidates checked:" >&2
    for canonical in "${!GDM_RESOURCE_BEFORE[@]}"; do
      echo "       - $canonical" >&2
    done
    tail -n 40 "$LOG" 2>/dev/null | sed 's/^/   | /' >&2 || true
    exit 1
  fi
  echo "   Branded GDM resource: ${GDM_RESOURCE}"

  install -d /usr/share/limad
  cat > /usr/share/limad/gdm-branding.env <<EOF
LIMAD_DISPLAY_MANAGER="gdm"
LIMAD_GDM_SERVICE="${ACTIVE_DM}"
LIMAD_GDM_RESOURCE="${GDM_RESOURCE}"
LIMAD_GDM_ORIGINAL_SHA256="${BEFORE_SHA256}"
LIMAD_GDM_BRANDED_SHA256="${AFTER_SHA256}"
LIMAD_GDM_BACKGROUND="${GDM_BACKGROUND}"
EOF
  echo "   GDM theme applied with LiMaD background"
fi

if [[ "${LIMAD_INSTALL_WALLPAPER}" == "1" && -d wallpaper ]]; then
  echo ":: Installing MacTahoe wallpapers"
  # Kept apart from the LiMaD wallpapers so the default selection below can
  # never accidentally pick one of them.
  install -d /usr/share/backgrounds/limad/mactahoe
  find wallpaper -maxdepth 1 -type f \( -name '*.jpg' -o -name '*.jpeg' -o -name '*.png' \) \
    -exec install -m 0644 {} /usr/share/backgrounds/limad/mactahoe/ \;
fi

install -d "$SRC_SHARE"
for f in COPYING LICENSE README.md; do
  [[ -f "$f" ]] && install -m 0644 "$f" "$SRC_SHARE/"
done
cat > "$SRC_SHARE/PROVENANCE.txt" <<EOF
MacTahoe GTK Theme
Upstream: ${MACTAHOE_REPO}
Tag:      ${MACTAHOE_TAG}
Commit:   ${COMMIT}
License:  ${MACTAHOE_LICENSE}
Author:   Vinceliuice and contributors
Installed as GTK theme "${GTK_THEME_ACTUAL}" and shell theme "${SHELL_THEME_ACTUAL}".
EOF

popd >/dev/null
rm -rf "$WORK" "$SHIM_DIR"

echo ":: MacTahoe step done"

#!/usr/bin/env bash
set -Eeuo pipefail
source /ctx/build_files/versions.env

echo ":: Installing LiSave ${LISAVE_VERSION}"
for file in \
  /usr/share/limad-save/VERSION \
  /usr/share/limad-save/core.py \
  /usr/share/limad-save/cli.py \
  /usr/share/limad-save/app.py \
  /usr/local/bin/limad-save \
  /usr/local/bin/limad-save-cli \
  /usr/local/bin/limad-save-first-login-detect \
  /usr/share/applications/de.limad.Save.desktop \
  /usr/lib/systemd/user/limad-save.service \
  /usr/lib/systemd/user/limad-save.timer; do
  [[ -s "$file" ]] || { echo "FATAL: LiSave file missing: $file" >&2; exit 1; }
done
[[ "$(tr -d '[:space:]' </usr/share/limad-save/VERSION)" == "$LISAVE_VERSION" ]] || { echo "FATAL: LiSave version mismatch" >&2; exit 1; }
chmod 0755 /usr/local/bin/limad-save /usr/local/bin/limad-save-cli /usr/local/bin/limad-save-first-login-detect /usr/share/limad-save/cli.py /usr/share/limad-save/app.py
chmod 0644 /usr/share/applications/de.limad.Save.desktop /usr/lib/systemd/user/limad-save.service /usr/lib/systemd/user/limad-save.timer
python3 -m py_compile /usr/share/limad-save/core.py /usr/share/limad-save/cli.py /usr/share/limad-save/app.py
desktop-file-validate /usr/share/applications/de.limad.Save.desktop
command -v restic >/dev/null 2>&1 || { echo "FATAL: restic missing for LiSave" >&2; exit 1; }
command -v secret-tool >/dev/null 2>&1 || { echo "FATAL: secret-tool missing for LiSave" >&2; exit 1; }
systemctl --global disable limad-save.timer 2>/dev/null || true
echo ":: LiSave step done"

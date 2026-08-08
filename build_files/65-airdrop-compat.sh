#!/usr/bin/env bash
# Build the optional Linux AirDrop compatibility stack from pinned upstream commits.
# The components are installed but never enabled automatically: OWL takes exclusive
# control of its Wi-Fi interface and must only use a separate compatible adapter.
set -Eeuo pipefail
source /opt/limad-build/versions.env

echo ":: Building optional AirDrop compatibility stack"
work=/tmp/limad-airdrop-build
install_root=/usr/libexec/limad-airdrop
backend="$install_root/backend"
venv="$install_root/venv"
rm -rf "$work" "$install_root"
install -d -m 0755 "$work" "$backend" /usr/share/licenses/limad-airdrop /usr/share/limad-source

clone_at_commit() {
  local repo=$1 commit=$2 dest=$3
  git clone --no-checkout --filter=blob:none "$repo" "$dest"
  git -C "$dest" checkout --detach "$commit"
}

clone_at_commit "$OWL_REPO" "$OWL_COMMIT" "$work/owl"
git -C "$work/owl" submodule update --init --recursive
# CMake 4 no longer accepts policy compatibility below 3.5. The pinned OWL
# checkout contains an old bundled GoogleTest CMakeLists.txt, so explicitly set
# the minimum policy level for this isolated build. BUILD_TESTING is disabled
# because LiMaD only needs the OWL runtime binary in the image.
cmake -S "$work/owl" -B "$work/owl/build" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=/usr \
  -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
  -DBUILD_TESTING=OFF
# The upstream project adds bundled GoogleTest targets unconditionally, so
# BUILD_TESTING=OFF alone is insufficient. Build only the OWL runtime target;
# this avoids compiling gtest while still producing the required daemon.
cmake --build "$work/owl/build" --target owl --parallel "$(nproc)"
owl_bin="$(find "$work/owl/build" -type f -name owl -perm /111 -print -quit)"
[[ -n "$owl_bin" ]] || { echo "FATAL: OWL binary was not produced" >&2; exit 1; }
install -m 0755 "$owl_bin" "$backend/owl"
install -m 0644 "$work/owl/COPYING" /usr/share/licenses/limad-airdrop/OWL-COPYING

clone_at_commit "$OPENDROP_REPO" "$OPENDROP_COMMIT" "$work/opendrop"
python3 -m venv --system-site-packages "$venv"
"$venv/bin/python" -m pip install --no-cache-dir --upgrade pip setuptools wheel
"$venv/bin/python" -m pip install --no-cache-dir "$work/opendrop"
cat > "$backend/opendrop" <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail
exec "$venv/bin/opendrop" "\$@"
EOF
chmod 0755 "$backend/opendrop"
if [[ -f "$work/opendrop/LICENSE" ]]; then
  install -m 0644 "$work/opendrop/LICENSE" /usr/share/licenses/limad-airdrop/OpenDrop-LICENSE
elif [[ -f "$work/opendrop/COPYING" ]]; then
  install -m 0644 "$work/opendrop/COPYING" /usr/share/licenses/limad-airdrop/OpenDrop-COPYING
fi

cat > /usr/share/limad-source/airdrop-sources.txt <<EOF
OWL_REPO=$OWL_REPO
OWL_COMMIT=$OWL_COMMIT
OPENDROP_REPO=$OPENDROP_REPO
OPENDROP_COMMIT=$OPENDROP_COMMIT
OPENDROP_VERSION=$OPENDROP_VERSION
EOF

"$backend/owl" -h >/dev/null 2>&1 || true
"$backend/opendrop" -h >/dev/null
rm -rf "$work"
echo ":: AirDrop components installed (inactive until hardware passes the safety check)"

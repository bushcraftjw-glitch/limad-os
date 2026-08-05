#!/usr/bin/env bash
set -Eeuo pipefail
source /ctx/build_files/versions.env

echo ":: Applying LiMaD identity and bootloader branding"
OS_RELEASE=/usr/lib/os-release
[[ -s "$OS_RELEASE" ]] || { echo "FATAL: ${OS_RELEASE} missing" >&2; exit 1; }
python3 - "$OS_RELEASE" "$LIMAD_OS_VERSION" <<'PY2'
from pathlib import Path
import sys
path=Path(sys.argv[1]); version=sys.argv[2]
lines=path.read_text().splitlines()
replacements={
    'ID': 'fedora',
    'ID_LIKE': '"fedora"',
    'NAME': '"LiMaD OS"',
    'PRETTY_NAME': f'"LiMaD OS {version}"',
    'LOGO': 'de.limad.Logo',
    'DEFAULT_HOSTNAME': 'limad',
    'BOOTLOADER_NAME': f'"LiMaD OS {version}"',
    'VARIANT': '"LiMaD GNOME"',
    'VARIANT_ID': 'limad-gnome',
}
out=[]; seen=set()
for line in lines:
    key=line.split('=',1)[0] if '=' in line else ''
    if key in replacements:
        out.append(f'{key}={replacements[key]}'); seen.add(key)
    else:
        out.append(line)
for key,value in replacements.items():
    if key not in seen: out.append(f'{key}={value}')
path.write_text('\n'.join(out)+'\n')
PY2
rm -f /etc/os-release
ln -s ../usr/lib/os-release /etc/os-release

install -d /usr/share/pixmaps /usr/share/limad/branding /etc/fastfetch /usr/share/cockpit/static
readonly LIMAD_LOGO=/usr/share/icons/LiMaD/512x512/apps/de.limad.Logo.png
install -m 0644 "$LIMAD_LOGO" /usr/share/pixmaps/de.limad.Logo.png
install -m 0644 "$LIMAD_LOGO" /usr/share/limad/branding/LiMaD-System-Logo-512.png
for branding_id in limad bazzite fedora; do
  branding_dir="/usr/share/cockpit/branding/${branding_id}"
  install -d "$branding_dir"
  install -m 0644 "$LIMAD_LOGO" "$branding_dir/logo.png"
  cat > "$branding_dir/branding.css" <<'CSS'
#badge { inline-size: 225px; block-size: 80px; background: url("logo.png") center/contain no-repeat; }
#brand::before { content: "LiMaD OS"; }
.anaconda {
  --brand-default-light: #c89cff;
  --brand-default: #8f4ff0;
  --brand-default-dark: #5a24a5;
}
.anaconda .logo { background-image: url("logo.png"); background-size: contain; }
:not(.pf-v6-theme-dark) .anaconda { --pf-t--global--color--brand--default: var(--brand-default); --pf-t--global--color--brand--hover: var(--brand-default-dark); }
.pf-v6-theme-dark .anaconda { --pf-t--global--color--brand--default: var(--brand-default-light); --pf-t--global--color--brand--hover: var(--brand-default); }
CSS
done
install -m 0644 /usr/share/cockpit/branding/limad/branding.css /usr/share/cockpit/static/branding.css
install -m 0644 "$LIMAD_LOGO" /usr/share/cockpit/static/logo.png

cat > /etc/fastfetch/config.jsonc <<'JSON'
{
  "$schema": "https://github.com/fastfetch-cli/fastfetch/raw/dev/doc/json_schema.json",
  "logo": {
    "type": "file",
    "source": "/usr/share/pixmaps/de.limad.Logo.png",
    "height": 12,
    "padding": { "right": 2 }
  },
  "display": { "separator": "  " },
  "modules": [
    "title", "separator", "os", "host", "kernel", "uptime",
    "packages", "shell", "display", "de", "wm", "terminal",
    "cpu", "gpu", "memory", "disk", "localip", "break", "colors"
  ]
}
JSON

cat > /usr/share/limad/branding/identity.env <<EOF
PRODUCT_NAME=LiMaD OS
PRODUCT_VERSION=${LIMAD_OS_VERSION}
LOGO=/usr/share/pixmaps/de.limad.Logo.png
BOOT_SPLASH=/usr/share/plymouth/themes/limad/boot-splash.png
DEFAULT_WALLPAPER=/usr/share/backgrounds/limad/${LIMAD_DEFAULT_WALLPAPER}
EOF

grep -q '^ID=fedora$' "$OS_RELEASE" || { echo "FATAL: Fedora compatibility ID not preserved" >&2; exit 1; }
grep -q '^ID_LIKE="fedora"$' "$OS_RELEASE" || { echo "FATAL: LiMaD ID_LIKE not written" >&2; exit 1; }
grep -q '^NAME="LiMaD OS"$' "$OS_RELEASE" || { echo "FATAL: LiMaD name not written" >&2; exit 1; }
grep -q '^BOOTLOADER_NAME="LiMaD OS ' "$OS_RELEASE" || { echo "FATAL: bootloader title not written" >&2; exit 1; }
echo ":: LiMaD identity active"

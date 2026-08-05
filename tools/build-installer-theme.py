#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

try:
    from PIL import Image, ImageEnhance
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Pillow (PIL) fehlt. Die lokale Quellpruefung funktioniert ohne Pillow; "
        "fuer die Bildgenerierung 'python3 -m pip install Pillow' verwenden. "
        "Der GitHub-Workflow installiert python3-pil automatisch."
    ) from exc

if len(sys.argv) != 4:
    raise SystemExit("usage: build-installer-theme.py LOGO WALLPAPER OUTPUT_DIR")

logo_path, wallpaper_path, out_dir = map(Path, sys.argv[1:])
out_dir.mkdir(parents=True, exist_ok=True)
logo = Image.open(logo_path).convert("RGBA")
wall = Image.open(wallpaper_path).convert("RGB")


def transparent_logo(size: tuple[int, int], max_logo: tuple[int, int]) -> Image.Image:
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    item = logo.copy()
    item.thumbnail(max_logo, Image.Resampling.LANCZOS)
    image.alpha_composite(item, ((size[0] - item.width) // 2, (size[1] - item.height) // 2))
    return image


def cover(source: Image.Image, size: tuple[int, int]) -> Image.Image:
    ratio = max(size[0] / source.width, size[1] / source.height)
    scaled = source.resize(
        (round(source.width * ratio), round(source.height * ratio)),
        Image.Resampling.LANCZOS,
    )
    left = (scaled.width - size[0]) // 2
    top = (scaled.height - size[1]) // 2
    return scaled.crop((left, top, left + size[0], top + size[1]))


transparent_logo((300, 150), (126, 126)).save(out_dir / "sidebar-logo.png", optimize=True)
transparent_logo((320, 128), (96, 96)).save(out_dir / "product-logo.png", optimize=True)
transparent_logo((512, 512), (420, 420)).save(out_dir / "logo.png", optimize=True)

sidebar = cover(wall, (384, 1080)).convert("RGBA")
sidebar = ImageEnhance.Brightness(sidebar).enhance(0.42)
sidebar = Image.alpha_composite(sidebar, Image.new("RGBA", sidebar.size, (5, 4, 15, 118)))
sidebar.save(out_dir / "sidebar-bg.png", optimize=True)

topbar = cover(wall, (1920, 112)).convert("RGBA")
topbar = ImageEnhance.Brightness(topbar).enhance(0.32)
topbar = Image.alpha_composite(topbar, Image.new("RGBA", topbar.size, (6, 5, 16, 110)))
topbar.save(out_dir / "topbar-bg.png", optimize=True)

# Anaconda WebUI consumes the Cockpit branding.css for the detected OS ID.
# Keep the official .anaconda wrapper and PatternFly theme mappings, then add
# LiMaD-specific dark surfaces.  The CSS is copied for limad, bazzite and fedora
# by brand-installer-iso.sh so the runtime profile cannot fall back to Fedora.
web_css = r'''/* LiMaD OS Anaconda WebUI branding. */
.anaconda {
  --brand-default-light: #b785ff;
  --brand-default: #8b3dff;
  --brand-default-dark: #5620ad;
  --limad-bg: #090811;
  --limad-surface: #14121c;
  --limad-card: #1a1724;
  --limad-border: #3b3449;
  --limad-text: #f7f3ff;
  --limad-muted: #bcb2c9;
  --pf-t--global--background--color--primary--default: var(--limad-bg);
  --pf-t--global--background--color--secondary--default: var(--limad-surface);
  --pf-t--global--background--color--floating--default: var(--limad-card);
  --pf-t--global--border--color--default: var(--limad-border);
  --pf-t--global--text--color--regular: var(--limad-text);
  --pf-t--global--text--color--subtle: var(--limad-muted);
  background: var(--limad-bg);
  color: var(--limad-text);
}

.anaconda .logo {
  background-image: url("logo.png") !important;
  background-position: center !important;
  background-repeat: no-repeat !important;
  background-size: contain !important;
}

:not(.pf-v6-theme-dark) .anaconda {
  --pf-t--global--color--brand--default: var(--brand-default);
  --pf-t--global--color--brand--hover: var(--brand-default-dark);
}

.pf-v6-theme-dark .anaconda,
.pf-v5-theme-dark .anaconda,
.anaconda {
  --pf-t--global--color--brand--default: var(--brand-default-light);
  --pf-t--global--color--brand--hover: var(--brand-default);
  color-scheme: dark;
}

html, body, #app,
.anaconda .pf-v6-c-page,
.anaconda .pf-v5-c-page,
.anaconda .pf-v6-c-page__main,
.anaconda .pf-v5-c-page__main {
  background: var(--limad-bg) !important;
  color: var(--limad-text) !important;
}

.anaconda .pf-v6-c-page__sidebar,
.anaconda .pf-v5-c-page__sidebar {
  background-color: #080611 !important;
  background-image: linear-gradient(rgba(5,4,15,.24), rgba(5,4,15,.78)), url("sidebar-bg.png") !important;
  background-position: center !important;
  background-size: cover !important;
  border-inline-end: 1px solid rgba(139,61,255,.34) !important;
}

.anaconda .pf-v6-c-masthead,
.anaconda .pf-v5-c-masthead {
  background-color: #0b0915 !important;
  background-image: linear-gradient(90deg,rgba(6,5,15,.90),rgba(8,7,18,.46)), url("topbar-bg.png") !important;
  background-position: center !important;
  background-size: cover !important;
  border-block-end: 1px solid rgba(139,61,255,.28) !important;
}

.anaconda .pf-v6-c-card,
.anaconda .pf-v5-c-card,
.anaconda .pf-v6-c-tile,
.anaconda .pf-v5-c-tile,
.anaconda .pf-v6-c-panel,
.anaconda .pf-v5-c-panel,
.anaconda [data-ouia-component-type="PF6/Card"],
.anaconda [data-ouia-component-type="PF5/Card"] {
  background: linear-gradient(145deg, #1b1825, #121019) !important;
  border: 1px solid var(--limad-border) !important;
  border-radius: 14px !important;
  box-shadow: 0 10px 30px rgba(0,0,0,.22) !important;
  color: var(--limad-text) !important;
}

.anaconda .pf-v6-c-button.pf-m-primary,
.anaconda .pf-v5-c-button.pf-m-primary {
  background: linear-gradient(135deg, var(--brand-default), #566dff) !important;
  border: 0 !important;
  border-radius: 10px !important;
  color: #fff !important;
  box-shadow: 0 8px 24px rgba(111,45,222,.28) !important;
}

.anaconda .pf-v6-c-button.pf-m-secondary,
.anaconda .pf-v5-c-button.pf-m-secondary,
.anaconda .pf-v6-c-button.pf-m-tertiary,
.anaconda .pf-v5-c-button.pf-m-tertiary {
  background: #17151f !important;
  border-color: #494153 !important;
  color: var(--limad-text) !important;
  border-radius: 10px !important;
}

.anaconda .pf-v6-c-nav__link.pf-m-current,
.anaconda .pf-v5-c-nav__link.pf-m-current,
.anaconda [aria-current="page"] {
  background: linear-gradient(90deg, rgba(139,61,255,.68), rgba(86,32,173,.46)) !important;
  border: 1px solid rgba(183,133,255,.58) !important;
  color: #fff !important;
  border-radius: 10px !important;
}

.anaconda .pf-v6-c-progress__indicator,
.anaconda .pf-v5-c-progress__indicator {
  background: linear-gradient(90deg, var(--brand-default), #566dff) !important;
}

.anaconda .pf-v6-c-form-control,
.anaconda .pf-v5-c-form-control,
.anaconda input,
.anaconda select,
.anaconda textarea {
  background: #12101a !important;
  color: var(--limad-text) !important;
  border-color: #493f59 !important;
  border-radius: 9px !important;
}

.anaconda .pf-v6-c-title,
.anaconda .pf-v5-c-title,
.anaconda h1,
.anaconda h2,
.anaconda h3 {
  color: var(--limad-text) !important;
}

.anaconda .pf-v6-c-content,
.anaconda .pf-v5-c-content,
.anaconda .pf-v6-c-helper-text,
.anaconda .pf-v5-c-helper-text {
  color: var(--limad-muted) !important;
}
'''
(out_dir / "branding.css").write_text(web_css, encoding="utf-8")

# This is a product-specific overlay.  It must be selected with
# product-specific GTK stylesheet instead of replacing Anaconda's complete
# base stylesheet.  The selector names follow the documented GTK UI classes.
gtk_css = r'''/* LiMaD OS product overlay for GTK Anaconda. */
@define-color product_bg_color #080611;
@define-color limad_bg #090811;
@define-color limad_surface #17141f;
@define-color limad_border #3b3449;
@define-color limad_text #f7f3ff;
@define-color limad_muted #bcb2c9;
@define-color limad_purple #8b3dff;
@define-color limad_blue #566dff;

.logo-sidebar {
  background-image: url('/usr/share/anaconda/pixmaps/sidebar-bg.png');
  background-color: @product_bg_color;
  background-repeat: no-repeat;
  color: @limad_text;
}
.logo {
  background-image: url('/usr/share/anaconda/pixmaps/sidebar-logo.png');
  background-position: 50% 20px;
  background-repeat: no-repeat;
  background-color: transparent;
}
.product-logo {
  background-image: url('/usr/share/anaconda/pixmaps/product-logo.png');
  background-position: center;
  background-repeat: no-repeat;
  background-color: transparent;
}
AnacondaSpokeWindow #nav-box,
AnacondaHubWindow #nav-box,
AnacondaWindow #nav-box {
  background-color: @product_bg_color;
  background-image: url('/usr/share/anaconda/pixmaps/topbar-bg.png');
  background-repeat: no-repeat;
  color: @limad_text;
}
AnacondaSpokeWindow,
AnacondaHubWindow,
AnacondaWindow,
window.background {
  background-color: @limad_bg;
  color: @limad_text;
}
headerbar,
.titlebar {
  background-image: linear-gradient(to right, #0a0912, #151025);
  color: @limad_text;
  border-bottom: 1px solid #392d50;
}
button {
  background-color: @limad_surface;
  color: @limad_text;
  border-color: @limad_border;
  border-radius: 8px;
}
button:hover {
  border-color: @limad_purple;
}
button.suggested-action,
button.default,
.suggested-action {
  background-image: linear-gradient(to right, @limad_purple, @limad_blue);
  color: white;
  border-color: transparent;
  border-radius: 8px;
}
entry,
textview,
treeview,
list,
row,
.view {
  background-color: @limad_surface;
  color: @limad_text;
  border-color: @limad_border;
}
row:selected,
treeview:selected,
.view:selected {
  background-color: @limad_purple;
  color: white;
}
progressbar progress,
levelbar block.filled {
  background-image: linear-gradient(to right, @limad_purple, @limad_blue);
}
.dim-label,
.subtitle,
label.dim-label {
  color: @limad_muted;
}
'''
(out_dir / "limad-anaconda.css").write_text(gtk_css, encoding="utf-8")
# Kept as an alias for old tooling, but brand-installer-iso.sh no longer
# overwrites Anaconda's base /usr/share/anaconda/anaconda-gtk.css.
(out_dir / "anaconda-gtk.css").write_text(gtk_css, encoding="utf-8")

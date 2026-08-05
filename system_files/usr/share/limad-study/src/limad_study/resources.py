from __future__ import annotations
import os
from pathlib import Path


def resource_root() -> Path:
    override = os.environ.get("LIMAD_STUDY_RESOURCE_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    package = Path(__file__).resolve()
    candidates = [package.parents[2], package.parents[1], Path("/app/share/limad-study"), Path("/usr/share/limad-study")]
    for candidate in candidates:
        if (candidate / "web" / "index.html").is_file():
            return candidate
    return package.parents[2]

ROOT = resource_root()
WEB_ROOT = ROOT / "web"
SEED_ROOT = ROOT / "seed"

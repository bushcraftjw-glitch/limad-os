from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class Paths:
    root: Path
    data: Path
    cache: Path
    config: Path
    publications: Path
    backups: Path
    downloads: Path
    covers: Path
    catalog: Path
    logs: Path
    database: Path


def resolve_paths() -> Paths:
    override = os.environ.get("LIMAD_STUDY_DATA")
    if override:
        data = Path(override).expanduser().resolve()
        root = data.parent
    else:
        data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
        data = data_home / "limad-study"
        root = data.parent
    cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "limad-study"
    config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "limad-study"
    paths = Paths(
        root=root,
        data=data,
        cache=cache,
        config=config,
        publications=data / "publications",
        backups=data / "backups",
        downloads=data / "downloads",
        covers=cache / "covers",
        catalog=data / "catalog",
        logs=cache / "logs",
        database=data / "study.db",
    )
    for path in [paths.data, paths.cache, paths.config, paths.publications, paths.backups, paths.downloads, paths.covers, paths.catalog, paths.logs]:
        path.mkdir(parents=True, exist_ok=True)
    return paths

PATHS = resolve_paths()

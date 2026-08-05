from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path
from . import APP_NAME, VERSION


def main() -> int:
    parser = argparse.ArgumentParser(prog="limad-study", description="LiMaD Study Linux")
    parser.add_argument("files", nargs="*", help="JWPUB- oder JWL-Library-Dateien")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--data-dir")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {VERSION}")
    parser.add_argument("--prepare-only", action="store_true", help="Mitgelieferte Inhalte installieren und danach beenden")
    parser.add_argument("--skip-bundled", action="store_true", help="Mitgelieferte Publikationen beim Start nicht prüfen")
    args = parser.parse_args()
    if args.data_dir:
        os.environ["LIMAD_STUDY_DATA"] = str(Path(args.data_dir).expanduser())
    from .seed_data import ensure_seed
    from .importers import import_jwlibrary, import_jwpub
    from .bundled import ensure_bundled_publications
    ensure_seed()
    bundled = {"ok": True, "skipped": True}
    if not args.skip_bundled:
        bundled = ensure_bundled_publications(strict=args.prepare_only)
    for value in args.files:
        path = Path(value).expanduser().resolve()
        if path.suffix.lower() == ".jwpub":
            import_jwpub(path)
        elif path.suffix.lower() in {".jwlibrary", ".jwlplaylist"}:
            import_jwlibrary(path)
        else:
            print(f"Nicht unterstützte Datei: {path}", file=sys.stderr)
    if args.prepare_only:
        import json
        print(json.dumps({"ok": True, "version": VERSION, "bundled": bundled}, ensure_ascii=False, indent=2))
        return 0
    from .shell import launch
    return launch(port=args.port)

if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from core import DEFAULT_CATEGORIES, LiSaveError, analyze, backup, configure_automatic, restore, scheduled, verify


def emit(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(prog="limad-save-cli")
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("analyze")
    scan.add_argument("--json", action="store_true")
    create = sub.add_parser("backup")
    create.add_argument("target")
    create.add_argument("--password", required=True)
    recover = sub.add_parser("restore")
    recover.add_argument("target")
    recover.add_argument("--password", required=True)
    check = sub.add_parser("verify")
    check.add_argument("target")
    check.add_argument("--password", required=True)
    check.add_argument("--full", action="store_true")
    auto = sub.add_parser("configure")
    auto.add_argument("target")
    auto.add_argument("--password", required=True)
    auto.add_argument("--enable", action="store_true")
    auto.add_argument("--disable", action="store_true")
    sub.add_parser("scheduled")
    sub.add_parser("pre-update")
    args = parser.parse_args()
    try:
        if args.command == "analyze":
            result = analyze(DEFAULT_CATEGORIES)
        elif args.command == "backup":
            result = backup(Path(args.target), args.password, DEFAULT_CATEGORIES, emit)
        elif args.command == "restore":
            result = restore(Path(args.target), args.password, DEFAULT_CATEGORIES, emit)
        elif args.command == "verify":
            result = verify(Path(args.target), args.password, args.full)
        elif args.command == "configure":
            result = configure_automatic(Path(args.target), args.password, DEFAULT_CATEGORIES, args.enable and not args.disable)
        elif args.command == "scheduled":
            result = scheduled("timer", emit)
        else:
            result = scheduled("pre-update", emit)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except LiSaveError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

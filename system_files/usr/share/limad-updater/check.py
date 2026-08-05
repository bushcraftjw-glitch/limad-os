#!/usr/bin/env python3
import json
import shutil
import subprocess
from pathlib import Path

from backend import scan_updates, state_home


def main():
    updates = {app_id: item for app_id, item in scan_updates().items() if item}
    state_file = state_home() / "limad-updater" / "notifications.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        previous = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        previous = {}
    current = {app_id: item["version"] for app_id, item in updates.items()}
    new_items = [item for app_id, item in updates.items() if previous.get(app_id) != item["version"]]
    state_file.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if new_items and shutil.which("notify-send"):
        names = ", ".join(f"{item['name']} {item['version']}" for item in new_items)
        subprocess.run(
            [
                "notify-send",
                "LiMaD-App-Updates verfügbar",
                f"Gefunden: {names}. Öffne „LiMaD Updates“ zur Installation.",
                "--icon=system-software-update",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

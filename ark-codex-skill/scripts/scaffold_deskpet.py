#!/usr/bin/env python3
"""Copy the deskpet app template into a new project and write initial settings."""

import argparse
import json
import shutil
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
APP_TEMPLATE = SKILL_DIR / "assets" / "deskpet-app"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument(
        "--pet",
        default="予愿安洁莉娜",
        help="initial pet name (default: bundled 予愿安洁莉娜)",
    )
    args = parser.parse_args()

    target = Path(args.target)
    if target.exists() and any(target.iterdir()):
        parser.error("target must be empty; refusing to overwrite an existing deskpet")
    target.mkdir(parents=True, exist_ok=True)
    for item in APP_TEMPLATE.iterdir():
        dest = target / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)
    (target / "pets").mkdir(exist_ok=True)

    settings = {
        "speed": 1.0,
        "subtitle_length": "medium",
        "subtitle_size": 19,
        "bar_length": 100,
        "mini_mode": False,
        "auto_hide_fullscreen": False,
        "locked": True,
        "scale": 1.0,
        "pos_x": None,
        "pos_y": None,
        "pet": args.pet or "予愿安洁莉娜",
        "pet_states": {},
        "autostart_with_codex": False,
        "subtitle_language": "zh",
        "status_actions": True,
        "monitor_thread_id": None,
    }
    (target / "settings.json").write_text(
        json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("scaffolded deskpet project at", target)


if __name__ == "__main__":
    main()

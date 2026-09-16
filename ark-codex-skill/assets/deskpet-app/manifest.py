import json
import os
import shutil

from config import PETS_DIR


def _migrate_manifest(pet_name, data):
    pet_dir = os.path.join(PETS_DIR, pet_name)
    frames_dir = os.path.join(pet_dir, "frames")
    group_dir = os.path.join(frames_dir, "基建")
    if os.path.isdir(os.path.join(frames_dir, "idle")):
        os.makedirs(group_dir, exist_ok=True)
        for entry in os.listdir(frames_dir):
            entry_path = os.path.join(frames_dir, entry)
            if os.path.isdir(entry_path) and entry != "基建":
                shutil.move(entry_path, os.path.join(group_dir, entry))
    new_data = {
        "fps": data.get("fps", 20),
        "size": data.get("size", 1000),
        "groups": {"基建": data["states"]},
    }
    with open(os.path.join(pet_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)
    return new_data


def load_manifest(pet_name):
    path = os.path.join(PETS_DIR, pet_name, "manifest.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if "groups" not in data and "states" in data:
        data = _migrate_manifest(pet_name, data)
    return data

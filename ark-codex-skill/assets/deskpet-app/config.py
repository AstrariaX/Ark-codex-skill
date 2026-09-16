import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PETS_DIR = os.path.join(BASE_DIR, "pets")
SOUNDS_DIR = os.path.join(BASE_DIR, "sounds")
ERROR_LOG = os.path.join(BASE_DIR, "pet_error.log")
SETTINGS_PATH = os.path.join(BASE_DIR, "settings.json")
PID_FILE = os.path.join(BASE_DIR, "pet.pid")
SHUTDOWN_FLAG = os.path.join(BASE_DIR, "pet_shutdown.flag")
DISABLED_FLAG = os.path.join(BASE_DIR, "pet_disabled.flag")
SHOW_FLAG = os.path.join(BASE_DIR, "pet_show.flag")
HIDE_FLAG = os.path.join(BASE_DIR, "pet_hide.flag")
WATCHER_PATH = os.path.join(BASE_DIR, "codex_pet_launcher.pyw")
if sys.platform == 'darwin':
    PYW_PATH = os.path.join(BASE_DIR, ".venv", "bin", "python")
    PYTHON_PATH = PYW_PATH
else:
    PYW_PATH = os.path.join(BASE_DIR, ".venv", "Scripts", "pythonw.exe")
    PYTHON_PATH = os.path.join(BASE_DIR, ".venv", "Scripts", "python.exe")
SKILL_SCRIPTS = os.path.join(
    os.path.expanduser("~"), ".claude", "skills", "ark-codex-skill", "scripts"
)
WEBM_DIR = os.path.join(BASE_DIR, "work", "webm")

LOOP_STATES = {"idle", "move", "sit", "sleep"}
STANDARD_ANIMS = {"idle", "sit", "sleep", "move", "interact"}

PAD = 12
STATUS_H = 46
MIN_SCALE = 0.3
MAX_SCALE = 2.0
PHYSICS_INTERVAL = 33
WINDOW_SCAN_INTERVAL = 250
REPULSION_QUANTITY = 500_000.0
REPULSION_MAX_DIST = 200.0

SPEED_OPTIONS = [
    ("0.5x", 0.5),
    ("0.75x", 0.75),
    ("1.0x", 1.0),
    ("1.25x", 1.25),
    ("1.5x", 1.5),
]

SUBTITLE_LEVELS = {
    "short": {
        "label": "简短",
        "task_limit": 14,
        "show_model": False,
        "show_progress": False,
    },
    "medium": {
        "label": "标准",
        "task_limit": 36,
        "show_model": True,
        "show_progress": False,
    },
    "long": {
        "label": "详细",
        "task_limit": 80,
        "show_model": True,
        "show_progress": True,
    },
}

DEFAULT_SETTINGS = {
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
    "pet": None,
    "active_pets": [],
    "pet_states": {},
    "autostart_with_codex": False,
    "behavior_ai_activation": 4,
    "behavior_allow_sit": True,
    "behavior_allow_sleep": True,
    "behavior_allow_walk": True,
    "physic_gravity": 800,
    "behavior_walk_speed": 60.0,
    "display_multi_monitors": True,
    "behavior_do_peer_repulsion": True,
    "sound_enabled": True,
    "sound_volume": 50,
    "render_outline": "dragging",
    "render_outline_color": "#FFFF00",
    "render_outline_width": 2,
    "opacity_dim": 0.75,
}

pet_windows = []


def _next_instance_key(pet_name):
    existing = {pw.instance_key for pw in pet_windows}
    if pet_name not in existing:
        return pet_name
    n = 2
    while f"{pet_name}#{n}" in existing:
        n += 1
    return f"{pet_name}#{n}"


def load_settings():
    data = dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            data.update(json.load(f))
    except Exception:
        pass
    return data


def save_settings(data):
    tmp = SETTINGS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SETTINGS_PATH)


def list_pets():
    pets = []
    if not os.path.isdir(PETS_DIR):
        return pets
    for name in sorted(os.listdir(PETS_DIR)):
        if os.path.isfile(os.path.join(PETS_DIR, name, "manifest.json")):
            pets.append(name)
    return pets


def resolve_active_pets(settings):
    pets = list_pets()
    active = settings.get("active_pets") or []
    active = [p for p in active if p in pets]
    if not active:
        name = settings.get("pet")
        if name in pets:
            active = [name]
        elif pets:
            active = [pets[0]]
    return active


def remove_pid_file():
    try:
        os.remove(PID_FILE)
    except OSError:
        pass


def remove_disabled_flag():
    try:
        os.remove(DISABLED_FLAG)
    except OSError:
        pass

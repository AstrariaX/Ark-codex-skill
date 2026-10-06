---
name: ark-codex-skill
description: Create or extend transparent desktop pets for Arknights operators using PRTS model exports. Use when the user asks to make a deskpet from an Arknights operator, download operator model/WebM animations, add an operator to the deskpet library, or switch the deskpet character.
---

# Arknights Deskpet

Build a transparent Codex deskpet from PRTS operator models and add it to a reusable deskpet library.

## Workflow

1. Confirm operator name and optional skin. If no skin is given, use the default (默认).
2. Resolve the operator page title on PRTS, then export base (基建) WebM animations: `Default`, `Interact`, `Move`, `Relax`, `Sit`, `Sleep`.
3. Process the WebM files into 1000x1000 transparent PNG frames at 20fps and write `pets/<operator>/manifest.json`.
   If a repeating animation jumps at the seam, prepare its loop interval and transition frames with `scripts/prepare_loops.py`, then visually preview the result. See `references/animation-loops.md` for dependencies and manual interval selection.
4. Add the pet to the deskpet library and launch it. The app supports right-click switching through the `桌宠库` menu.

## Quick Start on a Fresh Machine

The deskpet is a Windows Python app. Python 3.10+ and network access to `prts.wiki` are required. Do not use a global environment; always create a project-local `.venv`.

```bash
# 1. Scaffold a new deskpet project and its venv
python scripts/scaffold_deskpet.py --target <project-dir> --pet "<operator>"
python scripts/setup_env.py <project-dir>

# 2. Export WebM from PRTS (default skin unless --skin is given)
python scripts/prts_export.py "<operator>" [--skin "<skin>"] --out <project-dir>/work/webm

# 3. Convert WebM to transparent frames and add to the pet library
python scripts/process_webm.py --src <project-dir>/work/webm --name "<operator>" --out <project-dir>/pets/<operator>

# 4. Launch
<project-dir>/启动桌宠.bat
```

## Scripts

- `scripts/scaffold_deskpet.py` copies the app template into a project and writes an initial `settings.json`.
- `scripts/setup_env.py` creates `.venv`, installs `PySide6` and `playwright`, and optionally installs Playwright Chromium.
- `scripts/prts_export.py` automates the PRTS model viewer: loads the model, selects skin/model group/animation, and downloads WebM files.
- `scripts/process_webm.py` decodes WebM in Chromium, extracts transparent PNG frames, computes bounding boxes, and writes the pet manifest.
- `scripts/prepare_loops.py` selects repeating frame intervals and appends optical-flow transitions for idle, move, sit, and sleep. It has optional processing dependencies in `scripts/requirements-loops.txt`.
- `scripts/create_shortcuts.py` creates 打开桌宠 shortcuts on the Desktop and in the Start Menu.

## Notes

- The PRTS `Default` WebM export is often a broken 110-byte file. Keep it in `webm/` for reference, but do not map it to a state.
- If PRTS changes its viewer DOM, update `references/prts-ui.md` and the selectors inside `scripts/prts_export.py`.
- The generated app remembers position, size, and speed per pet, supports a mini mode, and can auto-hide in fullscreen.
- A lightweight watcher spawns a separate tray process while ChatGPT/Codex runs. The tray offers `显示桌宠`, `隐藏桌宠` (closes the pet), `开机自启动`, and `退出` (closes pet, tray, and watcher). The tray disappears when the app closes.
- The app template ships with 予愿安洁莉娜 as the initial pet, so a fresh project can launch immediately.

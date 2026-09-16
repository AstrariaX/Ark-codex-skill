---
name: ark-codex-skill
description: Create or extend transparent desktop pets for Arknights operators using PRTS model exports. Use when the user asks to make a deskpet from an Arknights operator, download operator model/WebM animations, add an operator to the deskpet library, add an animation group, or switch the deskpet character.
---

# Arknights Deskpet

Build transparent desktop pets from PRTS operator models with multi-group animation support, inspired by [Ark-Pets](https://github.com/isHarryh/Ark-Pets) AnimStage concept.

## Workflow

1. Confirm operator name and optional skin. If no skin is given, use the default (默认).
2. Confirm animation group: 基建 (base), 正面 (front), or 背面 (back). Default is 基建.
3. Resolve the operator page title on PRTS, then export WebM animations for the chosen group.
   - 基建: `Default`, `Interact`, `Move`, `Relax`, `Sit`, `Sleep`
   - 正面/背面: `Idle`, `Attack`, `Die`, `Start`, `Skill_1`, `Skill_2`, etc. (dynamic — all available animations are exported)
4. Process the WebM files into 1000x1000 transparent PNG frames at 60fps and write to `pets/<operator>/frames/<group>/`. Update `pets/<operator>/manifest.json` with cumulative group data.
5. Add the pet to the deskpet library and launch it. The app supports multi-pet, multi-group switching via right-click menu.

## Quick Start on a Fresh Machine

The deskpet is a Windows Python app. Python 3.10+ and network access to `prts.wiki` are required. Do not use a global environment; always create a project-local `.venv`.

```bash
# 1. Scaffold a new deskpet project and its venv
python scripts/scaffold_deskpet.py --target <project-dir> --pet "<operator>"
python scripts/setup_env.py <project-dir>

# 2. Export WebM from PRTS (default skin unless --skin is given)
python scripts/prts_export.py "<operator>" [--skin "<skin>"] [--group "正面"] --out <project-dir>/work/webm

# 3. Convert WebM to transparent frames and add to the pet library
python scripts/process_webm.py --src <project-dir>/work/webm --name "<operator>" --group "基建" --out <project-dir>/pets/<operator>

# 4. Launch (or manually: pythonw main.py)
<project-dir>/启动桌宠.bat
```

Multiple groups can be added incrementally — each run of step 2-3 with a different `--group` value adds to the existing manifest without overwriting other groups.

## Scripts

- `scripts/scaffold_deskpet.py` copies the app template into a project and writes an initial `settings.json`.
- `scripts/setup_env.py` creates `.venv`, installs `PySide6`, `playwright`, and optionally installs Playwright Chromium.
- `scripts/prts_export.py` automates the PRTS model viewer: loads the model, selects skin/model group/animation, and downloads WebM files. Supports `--group` for 基建/正面/背面.
- `scripts/process_webm.py` decodes WebM in Chromium, extracts transparent PNG frames at 60fps, computes bounding boxes, and writes the pet manifest in cumulative groups format. Dynamic state mapping via PASSTHROUGH_TOKENS handles unmapped animations (Skill, Die, Start, Attack).
- `scripts/create_shortcuts.py` creates 打开桌宠 shortcuts on the Desktop and in the Start Menu.

## App Modules

- `main.py` — Main application: multi-pet windows, multi-group animation, context menus, settings, character management, action settings panel.
- `behavior.py` — Markov stochastic matrix for autonomous behavior transitions (idle → walk → sit → sleep etc.).
- `physics.py` — 2D physics engine: gravity, ground collision, multi-monitor boundaries, peer repulsion.
- `window_detect.py` — Win32 fullscreen window detection for auto-hide.
- `codex_monitor.py` — Monitors both Claude Code (`~/.claude/projects/`) and Codex (`~/.codex/sessions/`) sessions, displays active task in subtitle. Also supports manual launch without any host program.

## Notes

- The PRTS `Default` WebM export is often a broken 110-byte file. Keep it in `webm/` for reference, but do not map it to a state.
- If PRTS changes its viewer DOM, update `references/prts-ui.md` and the selectors inside `scripts/prts_export.py`.
- The app supports multiple concurrent pets, each with independent behavior, physics, and animation state.
- A lightweight watcher spawns a separate tray process while Claude Code / Codex / ChatGPT runs. The pet can also run standalone without any host program (`pythonw main.py`).
- The app template ships with 予愿安洁莉娜 as the initial pet, so a fresh project can launch immediately.

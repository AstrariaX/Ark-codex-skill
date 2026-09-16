import os

from PySide6.QtGui import QAction, QIcon
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

import config
from config import PETS_DIR, pet_windows
from sound import ensure_sounds


def setup_tray(first_pet):
    base = os.path.join(PETS_DIR, first_pet, "frames")
    icon_path = ""
    for g in os.listdir(base) if os.path.isdir(base) else []:
        p = os.path.join(base, g, "idle", "frame_0000.png")
        if os.path.isfile(p):
            icon_path = p
            break
    icon = QIcon(icon_path) if icon_path else QIcon()
    tray = QSystemTrayIcon(icon)
    tray_menu = QMenu()
    tray_menu.addAction("显示桌宠", lambda: _show_all())
    tray_menu.addAction("隐藏到托盘", lambda: _hide_all())
    trans_action = QAction("透明穿透 (Ctrl+Shift+T)", checkable=True)
    trans_action.triggered.connect(lambda: _toggle_transparent_all())
    tray_menu.addAction(trans_action)
    tray_menu.addSeparator()
    tray_menu.addAction("完全退出", lambda: _quit_all())
    tray.setContextMenu(tray_menu)
    tray.activated.connect(lambda reason: _tray_activated(reason))
    tray.setToolTip("Claude Code 桌宠")
    tray.show()
    return tray


def _show_all():
    for pw in pet_windows:
        pw.tray_hidden = False
        pw.show()
        pw.raise_()


def _hide_all():
    for pw in pet_windows:
        pw.tray_hidden = True
        pw.hide()


def _toggle_transparent_all():
    for pw in pet_windows:
        pw.toggle_transparent()


def _quit_all():
    if pet_windows:
        pet_windows[0].quit_pet()


def _tray_activated(reason):
    if reason == QSystemTrayIcon.ActivationReason.Trigger:
        if pet_windows and pet_windows[0].tray_hidden:
            _show_all()
        else:
            _hide_all()


def load_sound_effects():
    drop_path, click_path = ensure_sounds()
    effects = {}
    drop_fx = QSoundEffect()
    drop_fx.setSource(QUrl.fromLocalFile(os.path.abspath(drop_path)))
    effects["drop"] = drop_fx
    click_fx = QSoundEffect()
    click_fx.setSource(QUrl.fromLocalFile(os.path.abspath(click_path)))
    effects["click"] = click_fx
    return effects

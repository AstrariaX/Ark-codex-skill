import atexit
import ctypes
import json
import os
import random
import sys
import time
import winreg
from ctypes import wintypes

from PySide6.QtCore import QRectF, QPointF, Qt, QTimer
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QFontMetrics,
    QTextLayout,
    QTextOption,
    QGuiApplication,
    QImage,
    QPainter,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QSlider,
    QVBoxLayout,
    QWidget,
)

import monitor_events as codex_monitor
from single_instance import InstanceLock

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PETS_DIR = os.path.join(BASE_DIR, "pets")
ERROR_LOG = os.path.join(BASE_DIR, "pet_error.log")
SETTINGS_PATH = os.path.join(BASE_DIR, "settings.json")
PID_FILE = os.path.join(BASE_DIR, "pet.pid")
SHUTDOWN_FLAG = os.path.join(BASE_DIR, "pet_shutdown.flag")
DISABLED_FLAG = os.path.join(BASE_DIR, "pet_disabled.flag")
SHOW_FLAG = os.path.join(BASE_DIR, "pet_show.flag")
HIDE_FLAG = os.path.join(BASE_DIR, "pet_hide.flag")
WATCHER_PATH = os.path.join(BASE_DIR, "codex_pet_launcher.pyw")
PYW_PATH = os.path.join(BASE_DIR, ".venv", "Scripts", "pythonw.exe")

PAD = 12
STATUS_H = 46
MIN_SCALE = 0.3
MAX_SCALE = 2.0

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
    "pet_states": {},
    "autostart_with_codex": False,
    "subtitle_language": "zh",
    "status_actions": True,
    "monitor_thread_id": None,
}


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


def resolve_active_pet(settings):
    pets = list_pets()
    name = settings.get("pet")
    if name in pets:
        return name
    return pets[0] if pets else None


_initial_settings = load_settings()
ACTIVE_PET = resolve_active_pet(_initial_settings)
FRAMES_DIR = os.path.join(PETS_DIR, ACTIVE_PET, "frames")
MANIFEST_PATH = os.path.join(PETS_DIR, ACTIVE_PET, "manifest.json")

with open(MANIFEST_PATH, encoding="utf-8") as f:
    MANIFEST = json.load(f)

FPS = int(MANIFEST["fps"])


def switch_pet(name):
    global ACTIVE_PET, FRAMES_DIR, MANIFEST_PATH, MANIFEST, FPS
    if name not in list_pets():
        return False
    ACTIVE_PET = name
    FRAMES_DIR = os.path.join(PETS_DIR, name, "frames")
    MANIFEST_PATH = os.path.join(PETS_DIR, name, "manifest.json")
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        MANIFEST = json.load(f)
    FPS = int(MANIFEST["fps"])
    return True


RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "CodexDeskpetWatcher"


def legacy_startup_entry_path():
    appdata = os.environ.get("APPDATA", "")
    return os.path.join(
        appdata,
        "Microsoft",
        "Windows",
        "Start Menu",
        "Programs",
        "Startup",
        "CodexDeskpetAutoStart.vbs",
    )


def set_autostart(enabled):
    legacy = legacy_startup_entry_path()
    try:
        if os.path.exists(legacy):
            os.remove(legacy)
    except OSError:
        pass
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY_PATH,
            0,
            winreg.KEY_SET_VALUE,
        )
        try:
            if enabled:
                command = f'"{PYW_PATH}" "{WATCHER_PATH}"'
                winreg.SetValueEx(
                    key, RUN_VALUE_NAME, 0, winreg.REG_SZ, command
                )
            else:
                try:
                    winreg.DeleteValue(key, RUN_VALUE_NAME)
                except FileNotFoundError:
                    pass
        finally:
            winreg.CloseKey(key)
    except OSError:
        return False
    return True


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


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Codex 桌宠设置")
        self.setModal(True)
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.speed_combo = QComboBox()
        for label, value in SPEED_OPTIONS:
            self.speed_combo.addItem(label, value)
        self.speed_combo.setCurrentIndex(
            self._index_for_value(settings.get("speed", 1.0))
        )

        self.subtitle_combo = QComboBox()
        for key, info in SUBTITLE_LEVELS.items():
            self.subtitle_combo.addItem(info["label"], key)
        self.subtitle_combo.setCurrentIndex(
            self._index_for_key(settings.get("subtitle_length", "medium"))
        )

        self.autostart_check = QCheckBox(
            "随 Codex 启动（登录后监听，检测到 Codex 再启动桌宠）"
        )
        self.language_combo = QComboBox()
        self.language_combo.addItem("中文", "zh")
        self.language_combo.addItem("English", "en")
        self.language_combo.setCurrentIndex(1 if settings.get("subtitle_language") == "en" else 0)
        self.thread_edit = QLineEdit(settings.get("monitor_thread_id") or "")
        self.thread_edit.setPlaceholderText("留空：监听所有本地任务")
        self.actions_check = QCheckBox("根据任务状态切换动作")
        self.actions_check.setChecked(settings.get("status_actions", True))
        self.autostart_check.setChecked(
            bool(settings.get("autostart_with_codex", False))
        )

        self.mini_check = QCheckBox("迷你模式（隐藏字幕条）")
        self.mini_check.setChecked(bool(settings.get("mini_mode", False)))
        self.fullscreen_check = QCheckBox("全屏应用时自动隐藏")
        self.fullscreen_check.setChecked(
            bool(settings.get("auto_hide_fullscreen", False))
        )

        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(14, 26)
        self.size_slider.setValue(int(settings.get("subtitle_size", 19)))
        self.size_value = QLabel(f"{self.size_slider.value()}px")
        self.size_slider.valueChanged.connect(
            lambda value: self.size_value.setText(f"{value}px")
        )
        size_row = QWidget()
        size_layout = QHBoxLayout(size_row)
        size_layout.setContentsMargins(0, 0, 0, 0)
        size_layout.addWidget(self.size_slider, 1)
        size_layout.addWidget(self.size_value)

        self.bar_slider = QSlider(Qt.Horizontal)
        self.bar_slider.setRange(40, 100)
        self.bar_slider.setValue(int(settings.get("bar_length", 100)))
        self.bar_value = QLabel(f"{self.bar_slider.value()}%")
        self.bar_slider.valueChanged.connect(
            lambda value: self.bar_value.setText(f"{value}%")
        )
        bar_row = QWidget()
        bar_layout = QHBoxLayout(bar_row)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.addWidget(self.bar_slider, 1)
        bar_layout.addWidget(self.bar_value)

        form.addRow("动作倍速", self.speed_combo)
        form.addRow("字幕语言 / Language", self.language_combo)
        form.addRow("跟踪任务 ID", self.thread_edit)
        form.addRow("", self.actions_check)
        form.addRow("字幕大小", size_row)
        form.addRow("字条长度", bar_row)
        form.addRow("", self.mini_check)
        form.addRow("", self.fullscreen_check)
        form.addRow("", self.autostart_check)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _index_for_value(value):
        for i, (_, speed) in enumerate(SPEED_OPTIONS):
            if abs(speed - float(value)) < 1e-6:
                return i
        return 2

    @staticmethod
    def _index_for_key(key):
        keys = list(SUBTITLE_LEVELS.keys())
        return keys.index(key) if key in keys else 1

    def values(self):
        return {
            "speed": self.speed_combo.currentData(),
            "subtitle_length": self.subtitle_combo.currentData(),
            "subtitle_language": self.language_combo.currentData(),
            "monitor_thread_id": self.thread_edit.text().strip() or None,
            "status_actions": self.actions_check.isChecked(),
            "subtitle_size": self.size_slider.value(),
            "bar_length": self.bar_slider.value(),
            "mini_mode": self.mini_check.isChecked(),
            "auto_hide_fullscreen": self.fullscreen_check.isChecked(),
            "autostart_with_codex": self.autostart_check.isChecked(),
        }


class PetWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setMouseTracking(True)

        self.settings = load_settings()
        self.pet_name = ACTIVE_PET
        pet_states = self.settings.get("pet_states") or {}
        pet_state = pet_states.get(self.pet_name, {})
        self.pet_state = pet_state
        self.speed = float(
            pet_state.get("speed", self.settings.get("speed", 1.0))
        )
        self.show_status = not bool(self.settings.get("mini_mode", False))
        self.auto_hide_fullscreen = bool(
            self.settings.get("auto_hide_fullscreen", False)
        )
        self.subtitle_length = self.settings.get("subtitle_length", "medium")
        self.subtitle_size = max(
            14, min(26, int(self.settings.get("subtitle_size", 19)))
        )
        self.bar_length = max(
            40, min(100, int(self.settings.get("bar_length", 100)))
        )
        self.locked = bool(self.settings.get("locked", True))

        self.state = "idle"
        self.frame_index = 0
        self.scale = max(
            MIN_SCALE,
            min(
                MAX_SCALE,
                float(
                    pet_state.get(
                        "scale", self.settings.get("scale", 1.0)
                    )
                ),
            ),
        )
        self.cache = {}
        self.drag = False
        self.pre_drag_state = "idle"
        self.pre_drag_hold = False
        self.hold_state = False
        self.press_global = None
        self.press_window = None
        self.press_time = 0
        self.status_text = "Codex 待机"
        self.status_active = False
        self.status_event_key = None
        self.caption_event_key = None
        self.completed_caption_deadline = None
        self.tray_hidden = False

        self.timer = QTimer(self)
        self.timer.setInterval(self.tick_ms())
        self.timer.timeout.connect(self.next_frame)
        self.timer.start()

        self.sit_timer = QTimer(self)
        self.sit_timer.setSingleShot(True)
        self.sit_timer.timeout.connect(
            lambda: self.set_state("sit", hold=True)
        )

        self.sleep_timer = QTimer(self)
        self.sleep_timer.setSingleShot(True)
        self.sleep_timer.timeout.connect(
            lambda: self.set_state("sleep", hold=True)
        )

        self.status_timer = QTimer(self)
        self.status_timer.setInterval(250)
        self.status_timer.timeout.connect(self.refresh_status)
        self.status_timer.start()

        self.fullscreen_timer = QTimer(self)
        self.fullscreen_timer.setInterval(2000)
        self.fullscreen_timer.timeout.connect(self.check_fullscreen)
        self.fullscreen_timer.start()

        self.set_state("idle")
        screen = QGuiApplication.primaryScreen().availableGeometry()
        pos_x = pet_state.get("pos_x")
        if pos_x is None:
            pos_x = self.settings.get("pos_x")
        pos_y = pet_state.get("pos_y")
        if pos_y is None:
            pos_y = self.settings.get("pos_y")
        if pos_x is not None and pos_y is not None:
            pos_x = int(pos_x)
            pos_y = int(pos_y)
            pos_x = max(
                screen.x() - self.width() + 60,
                min(pos_x, screen.x() + screen.width() - 60),
            )
            pos_y = max(
                screen.y() - self.height() + 60,
                min(pos_y, screen.y() + screen.height() - 60),
            )
            self.move(pos_x, pos_y)
        else:
            self.move(
                screen.x() + (screen.width() - self.width()) // 2,
                screen.y() + screen.height() - self.height(),
            )
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.save_position)
        self.refresh_status()
        self.ensure_on_screen()
        self.show()

    def ensure_on_screen(self):
        screen = QGuiApplication.screenAt(self.geometry().center()) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        x = max(area.left(), min(self.x(), area.right() - self.width() + 1))
        y = max(area.top(), min(self.y(), area.bottom() - self.height() + 1))
        self.move(x, y)

    def tick_ms(self):
        return max(10, int(round(1000 / FPS / self.speed)))

    def state_info(self, name):
        return MANIFEST["states"][name]

    def apply_geometry(self):
        info = self.state_info(self.state)
        old_x, old_y = self.x(), self.y()
        old_w, old_h = self.width(), self.height()
        bx, by, bx2, by2 = info["bbox"]
        width = int((bx2 - bx + 1) * self.scale) + PAD * 2
        if self.show_status and self.status_text:
            width = max(240, width)
        status_extra = self.subtitle_height(width) if self.show_status and self.status_text else 0
        height = int((by2 - by + 1) * self.scale) + PAD * 2 + status_extra
        self.resize(width, height)
        bottom_center_x = old_x + old_w / 2
        bottom_y = old_y + old_h
        self.move(
            int(bottom_center_x - width / 2),
            int(bottom_y - height),
        )
        if self.isVisible() and not self.drag:
            self.ensure_on_screen()

    def subtitle_layout(self, width):
        bar_width = min(width - 12, max(120, int((width - 12) * self.bar_length / 100.0)))
        key = (self.status_text, self.subtitle_size, bar_width)
        if getattr(self, '_subtitle_layout_key', None) != key:
            font = QFont()
            font.setPixelSize(self.subtitle_size)
            layout = QTextLayout(self.status_text, font)
            option = QTextOption()
            option.setAlignment(Qt.AlignHCenter)
            option.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
            layout.setTextOption(option)
            layout.beginLayout()
            height = 0
            while True:
                line = layout.createLine()
                if not line.isValid():
                    break
                line.setLineWidth(max(1, bar_width - 16))
                line.setPosition(QPointF(0, height))
                height += line.height()
            layout.endLayout()
            self._subtitle_layout_key = key
            self._subtitle_layout = (layout, bar_width, max(STATUS_H, int(height + 25)))
        return self._subtitle_layout

    def subtitle_height(self, width):
        return self.subtitle_layout(width)[2]

    def set_state(self, name, hold=False):
        if name not in MANIFEST["states"]:
            return
        self.state = name
        self.hold_state = hold
        self.frame_index = 0
        self.cache.clear()
        self.apply_geometry()
        self.schedule_idle()
        self.update()

    def schedule_idle(self):
        self.sit_timer.stop()
        self.sleep_timer.stop()
        if self.state == "sleep" or (self.status_active and self.settings.get("status_actions", True)):
            return
        self.sit_timer.start(40000 + random.randint(0, 20000))
        self.sleep_timer.start(90000)

    def frame_path(self, index):
        pad = str(index).zfill(4)
        return os.path.join(FRAMES_DIR, self.state, f"frame_{pad}.png")

    def current_image(self):
        cached = self.cache.get(self.frame_index)
        if cached is not None:
            return cached
        image = QImage(self.frame_path(self.frame_index))
        if not image.isNull():
            if len(self.cache) > 5:
                self.cache.clear()
            self.cache[self.frame_index] = image
        return image

    def next_frame(self):
        info = self.state_info(self.state)
        count = info["count"]
        if self.state == "sleep":
            if not self.hold_state and self.frame_index >= count - 1:
                self.update()
                return
            self.frame_index = (self.frame_index + 1) % count
        elif self.state in ("interact", "sit"):
            if not self.hold_state and self.frame_index >= count - 1:
                self.set_state("idle")
                return
            self.frame_index = (self.frame_index + 1) % count
        else:
            self.frame_index = (self.frame_index + 1) % count
        self.update()

    def paintEvent(self, event):
        info = self.state_info(self.state)
        bx, by, bx2, _ = info["bbox"]
        image = self.current_image()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        status_extra = self.subtitle_height(self.width()) if self.show_status and self.status_text else 0
        if not image.isNull():
            target = QRectF(
                (self.width() - (bx2-bx+1)*self.scale)/2 - bx * self.scale,
                status_extra + PAD - by * self.scale,
                image.width() * self.scale,
                image.height() * self.scale,
            )
            painter.save()
            painter.setClipRect(QRectF(0, status_extra, self.width(), self.height()-status_extra))
            painter.drawImage(target, image)
            painter.restore()

        if self.show_status and self.status_text:
            layout, bar_width, subtitle_height = self.subtitle_layout(self.width())
            bar = QRectF((self.width()-bar_width)/2, 4, bar_width, subtitle_height - 8)
            painter.setPen(QColor(255, 255, 255))
            text_height = layout.boundingRect().height()
            layout.draw(painter, QPointF(bar.left()+8, bar.top()+(bar.height()-text_height)/2))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag = False
            self.pre_drag_state = self.state
            self.pre_drag_hold = self.hold_state
            self.press_global = event.globalPosition().toPoint()
            self.press_window = self.pos()
            self.press_time = time.monotonic()

    def mouseMoveEvent(self, event):
        if self.press_global is None:
            return
        if self.locked:
            return
        current = event.globalPosition().toPoint()
        dx = current.x() - self.press_global.x()
        dy = current.y() - self.press_global.y()
        if not self.drag and (dx * dx + dy * dy) > 36:
            self.drag = True
            self.sit_timer.stop()
            self.sleep_timer.stop()
            if self.state != "move":
                self.set_state("move")
        if self.drag and not (event.buttons() & Qt.LeftButton):
            self.drag = False
            self.press_global = None
            self.press_window = None
            target = (
                self.pre_drag_state
                if self.pre_drag_state in MANIFEST["states"]
                else "idle"
            )
            self.set_state(target, hold=self.pre_drag_hold)
        elif self.drag:
            self.move(self.press_window.x() + dx, self.press_window.y() + dy)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        if self.drag:
            self.drag = False
            self.press_global = None
            self.press_window = None
            target = (
                self.pre_drag_state
                if self.pre_drag_state in MANIFEST["states"]
                else "idle"
            )
            self.set_state(target, hold=self.pre_drag_hold)
            self.save_pet_state()
            return
        if self.press_global is None:
            return
        current = event.globalPosition().toPoint()
        moved = (current.x() - self.press_global.x()) ** 2 + (
            current.y() - self.press_global.y()
        ) ** 2
        held = time.monotonic() - self.press_time
        self.press_global = None
        self.press_window = None
        if held < 0.5 and moved < 36:
            self.set_state("interact")

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggle_mini()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addAction(
            QAction(
                "坐下",
                self,
                triggered=lambda: self.set_state("sit", hold=True),
            )
        )
        menu.addAction(
            QAction(
                "放松",
                self,
                triggered=lambda: self.set_state("idle", hold=True),
            )
        )
        menu.addAction(
            QAction(
                "睡觉",
                self,
                triggered=lambda: self.set_state("sleep", hold=True),
            )
        )
        menu.addSeparator()
        pet_menu = menu.addMenu("桌宠库")
        for name in list_pets():
            action = QAction(name, self, checkable=True)
            action.setChecked(name == self.pet_name)
            action.triggered.connect(
                lambda checked=False, n=name: self.select_pet(n)
            )
            pet_menu.addAction(action)
        menu.addSeparator()
        mini_action = QAction("迷你模式（隐藏字幕）", self, checkable=True)
        mini_action.setChecked(not self.show_status)
        mini_action.triggered.connect(self.toggle_mini)
        menu.addAction(mini_action)
        full_action = QAction("全屏应用时自动隐藏", self, checkable=True)
        full_action.setChecked(self.auto_hide_fullscreen)
        full_action.triggered.connect(self.toggle_fullscreen_auto_hide)
        menu.addAction(full_action)
        menu.addSeparator()
        menu.addAction(
            QAction(
                "解锁拖动" if self.locked else "锁定拖动",
                self,
                triggered=self.toggle_lock,
            )
        )
        menu.addSeparator()
        menu.addAction(QAction("设置...", self, triggered=self.open_settings))
        menu.addSeparator()
        menu.addAction(QAction("放大", self, triggered=self.scale_up))
        menu.addAction(QAction("缩小", self, triggered=self.scale_down))
        menu.addSeparator()
        menu.addAction(
            QAction("隐藏到托盘", self, triggered=self.hide_to_tray)
        )
        menu.addAction(
            QAction("完全退出", self, triggered=self.quit_pet)
        )
        menu.exec(event.globalPos())

    def scale_up(self):
        self.set_scale(self.scale + 0.1)

    def scale_down(self):
        self.set_scale(self.scale - 0.1)

    def set_scale(self, value):
        self.scale = max(MIN_SCALE, min(MAX_SCALE, round(value, 1)))
        self.apply_geometry()
        self.settings["scale"] = self.scale
        self.save_pet_state()
        self.update()

    def select_pet(self, name):
        if name == self.pet_name or not switch_pet(name):
            return
        self.save_pet_state()
        self.pet_name = name
        self.settings["pet"] = name
        pet_state = (self.settings.get("pet_states") or {}).get(name, {})
        self.scale = max(
            MIN_SCALE,
            min(
                MAX_SCALE,
                float(
                    pet_state.get(
                        "scale", self.settings.get("scale", 1.0)
                    )
                ),
            ),
        )
        self.speed = float(
            pet_state.get("speed", self.settings.get("speed", 1.0))
        )
        self.cache.clear()
        self.timer.setInterval(self.tick_ms())
        self.set_state("idle", hold=False)
        screen = QGuiApplication.primaryScreen().availableGeometry()
        pos_x = pet_state.get("pos_x")
        if pos_x is None:
            pos_x = self.settings.get("pos_x")
        pos_y = pet_state.get("pos_y")
        if pos_y is None:
            pos_y = self.settings.get("pos_y")
        if pos_x is not None and pos_y is not None:
            pos_x = max(
                screen.x() - self.width() + 60,
                min(int(pos_x), screen.x() + screen.width() - 60),
            )
            pos_y = max(
                screen.y() - self.height() + 60,
                min(int(pos_y), screen.y() + screen.height() - 60),
            )
            self.move(pos_x, pos_y)
        else:
            self.move(
                screen.x() + (screen.width() - self.width()) // 2,
                screen.y() + screen.height() - self.height(),
            )
        self.refresh_status()
        self.update()

    def save_pet_state(self):
        pet_states = self.settings.setdefault("pet_states", {})
        pet_states[self.pet_name] = {
            "scale": self.scale,
            "speed": self.speed,
            "pos_x": self.x(),
            "pos_y": self.y(),
        }
        self.settings["scale"] = self.scale
        self.settings["pos_x"] = self.x()
        self.settings["pos_y"] = self.y()
        save_settings(self.settings)

    def save_position(self):
        self.save_pet_state()

    def toggle_mini(self):
        self.show_status = not self.show_status
        self.settings["mini_mode"] = not self.show_status
        save_settings(self.settings)
        self.apply_geometry()
        self.update()

    def toggle_fullscreen_auto_hide(self):
        self.auto_hide_fullscreen = not self.auto_hide_fullscreen
        self.settings["auto_hide_fullscreen"] = self.auto_hide_fullscreen
        save_settings(self.settings)
        self.check_fullscreen()

    def check_fullscreen(self):
        if self.tray_hidden:
            return
        if not self.auto_hide_fullscreen:
            if not self.isVisible():
                self.show()
            return
        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.GetWindowRect.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.RECT),
        ]
        hwnd = user32.GetForegroundWindow()
        if not hwnd or hwnd == int(self.winId()):
            if not self.isVisible():
                self.show()
            return
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        screen = QGuiApplication.primaryScreen().geometry()
        full = (
            rect.left <= screen.x()
            and rect.top <= screen.y()
            and rect.right >= screen.x() + screen.width()
            and rect.bottom >= screen.y() + screen.height()
        )
        if full:
            self.hide()
        elif not self.isVisible():
            self.show()

    def hide_to_tray(self):
        self.tray_hidden = True
        self.hide()

    def show_from_tray(self):
        self.tray_hidden = False
        self.ensure_on_screen()
        self.show()
        self.raise_()
        self.activateWindow()

    def quit_pet(self):
        try:
            with open(DISABLED_FLAG, "w", encoding="utf-8") as f:
                f.write("1")
        except OSError:
            pass
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def toggle_lock(self):
        self.locked = not self.locked
        self.settings["locked"] = self.locked
        save_settings(self.settings)
        self.drag = False
        self.press_global = None
        self.press_window = None

    def open_settings(self):
        self.settings["speed"] = self.speed
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() != QDialog.Accepted:
            return
        data = dialog.values()
        if (data["monitor_thread_id"] != self.settings.get("monitor_thread_id") or
                data["status_actions"] != self.settings.get("status_actions", True)):
            self.status_event_key = None
            self.status_active = False
            self.set_state("idle")
        old_autostart = bool(self.settings.get("autostart_with_codex", False))
        merged = dict(self.settings)
        merged.update(data)
        self.settings = merged
        save_settings(merged)
        self.speed = float(data["speed"])
        self.subtitle_length = data["subtitle_length"]
        self.subtitle_size = int(data["subtitle_size"])
        self.bar_length = int(data["bar_length"])
        self.show_status = not bool(data["mini_mode"])
        self.auto_hide_fullscreen = bool(data["auto_hide_fullscreen"])
        self.timer.setInterval(self.tick_ms())
        if bool(data["autostart_with_codex"]) != old_autostart:
            if not set_autostart(bool(data["autostart_with_codex"])):
                QMessageBox.warning(
                    self,
                    "Codex 桌宠",
                    "随 Codex 启动设置写入失败，请检查系统权限。",
                )
        self.save_pet_state()
        self.refresh_status()
        self.update()

    @staticmethod
    def _cut(text, limit):
        text = " ".join(text.split())
        if len(text) <= limit:
            return text
        return text[: max(0, limit - 1)] + "…"

    @staticmethod
    def _format_elapsed(seconds, language="zh"):
        seconds = int(seconds)
        minutes, sec = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if language == "en":
            if hours:
                return f"{hours}h {minutes}m"
            if minutes:
                return f"{minutes}m {sec}s"
            return f"{sec}s"
        if hours:
            return f"{hours}小时{minutes}分"
        if minutes:
            return f"{minutes}分{sec}秒"
        return f"{sec}秒"

    @staticmethod
    def _format_tokens(count):
        if count >= 1_000_000:
            return f"{count / 1_000_000:.1f}M"
        if count >= 1_000:
            return f"{count / 1_000:.1f}k"
        return str(count)

    def refresh_status(self):
        if os.path.exists(HIDE_FLAG):
            try:
                os.remove(HIDE_FLAG)
            except OSError:
                pass
            self.hide_to_tray()
        if os.path.exists(SHOW_FLAG):
            try:
                os.remove(SHOW_FLAG)
            except OSError:
                pass
            self.show_from_tray()
        if os.path.exists(SHUTDOWN_FLAG):
            try:
                os.remove(SHUTDOWN_FLAG)
            except OSError:
                pass
            app = QApplication.instance()
            if app is not None:
                app.quit()
            return
        status = codex_monitor.get_codex_status(self.settings.get("monitor_thread_id"))
        self.status_active = bool(status.get("active"))
        event_key = status.get("event_key")
        caption_key = (event_key, status.get("phase"), self.status_active)
        if caption_key != self.caption_event_key:
            self.caption_event_key = caption_key
            self.completed_caption_deadline = (
                time.monotonic() + 10.0
                if status.get("phase") == "completed" and not self.status_active
                else None
            )
        if (self.settings.get("status_actions", True) and event_key
                and event_key != self.status_event_key and not self.drag):
            self.status_event_key = event_key
            phase = status.get("phase")
            if phase == "running":
                self.set_state("move", hold=True)
            elif phase == "completed":
                self.set_state("interact")
            elif phase in ("interrupted", "failed"):
                self.set_state("sit", hold=True)
        english = self.settings.get("subtitle_language", "zh") == "en"
        if self.status_active:
            base = "Codex Running" if english else "Codex 运行中"
        else:
            labels = ({"completed": "Codex Completed", "interrupted": "Codex Interrupted",
                       "failed": "Codex Failed", "unknown": "Codex Status unknown"} if english else
                      {"completed": "Codex 已完成", "interrupted": "Codex 已中断",
                       "failed": "Codex 失败", "unknown": "Codex 状态未知"})
            base = labels.get(status.get("phase"), "Codex Idle" if english else "Codex 待机")
        self.status_text = base
        if (self.completed_caption_deadline is not None
                and time.monotonic() >= self.completed_caption_deadline):
            self.status_text = ""
        self.apply_geometry()
        self.update()


def main():
    instance_lock = InstanceLock(BASE_DIR)
    if not instance_lock.acquire():
        with open(SHOW_FLAG, "w", encoding="utf-8"):
            pass
        return 0
    atexit.register(instance_lock.close)
    with open(PID_FILE, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
    atexit.register(remove_pid_file)
    remove_disabled_flag()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    PetWindow()
    return app.exec()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.ctime()}\n")
            import traceback

            traceback.print_exc(file=f)
        raise

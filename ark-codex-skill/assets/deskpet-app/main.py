import atexit
import json
import os
import sys
import random
import time

IS_WINDOWS = sys.platform == 'win32'
IS_MACOS = sys.platform == 'darwin'

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes
    import winreg

from PySide6.QtCore import QPointF, QRectF, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QAction, QColor, QFont, QFontMetrics, QGuiApplication, QIcon, QImage, QPainter,
)
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMenu, QMessageBox, QProgressDialog,
    QPushButton, QScrollArea, QSlider, QSystemTrayIcon, QTabWidget,
    QVBoxLayout, QWidget,
)

from config import (
    BASE_DIR, PETS_DIR, SOUNDS_DIR, ERROR_LOG, SETTINGS_PATH,
    PID_FILE, SHUTDOWN_FLAG, DISABLED_FLAG, SHOW_FLAG, HIDE_FLAG,
    WATCHER_PATH, PYW_PATH, PYTHON_PATH, SKILL_SCRIPTS, WEBM_DIR,
    LOOP_STATES, STANDARD_ANIMS, PAD, STATUS_H, MIN_SCALE, MAX_SCALE,
    PHYSICS_INTERVAL, WINDOW_SCAN_INTERVAL, REPULSION_QUANTITY, REPULSION_MAX_DIST,
    SPEED_OPTIONS, SUBTITLE_LEVELS, DEFAULT_SETTINGS,
    pet_windows, _next_instance_key, load_settings, save_settings,
    list_pets, resolve_active_pets, remove_pid_file, remove_disabled_flag,
)
from manifest import load_manifest
from sound import ensure_sounds
from screen import get_world_areas, get_max_screen_bottom
from bubble import DEFAULT_LINES, BubbleWidget
from prts import fetch_prts_lines
from fetch_worker import FetchWorker
from dialogs import SettingsDialog
from tray import setup_tray, load_sound_effects, _toggle_transparent_all

import codex_monitor
from behavior import MIN_DURATION, STATE_TO_ANIM, State, StochasticMatrix
from physics import Plane
import window_detect

if IS_WINDOWS:
    WM_HOTKEY = 0x0312
    HOTKEY_TRANSPARENT = 1
    MOD_CTRL_SHIFT = 0x0002 | 0x0004  # CTRL + SHIFT
    VK_T = 0x54

if IS_WINDOWS:
    RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
    RUN_VALUE_NAME = "ClaudeCodeDeskpetWatcher"

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
elif IS_MACOS:
    def set_autostart(enabled):
        import plistlib
        plist_dir = os.path.expanduser("~/Library/LaunchAgents")
        plist_path = os.path.join(plist_dir, "com.deskpet.ark.plist")
        if enabled:
            os.makedirs(plist_dir, exist_ok=True)
            plist = {
                'Label': 'com.deskpet.ark',
                'ProgramArguments': [PYW_PATH, os.path.join(BASE_DIR, 'main.py')],
                'RunAtLoad': True,
            }
            with open(plist_path, 'wb') as f:
                plistlib.dump(plist, f)
        else:
            try:
                os.remove(plist_path)
            except OSError:
                pass
        return True
else:
    def set_autostart(enabled):
        return False


class PetWindow(QWidget):
    def __init__(self, pet_name, settings, sound_effects=None, instance_key=None):
        super().__init__()
        wflags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        if IS_WINDOWS:
            wflags |= Qt.Tool
        else:
            wflags |= Qt.Window
        self.setWindowFlags(wflags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setMouseTracking(True)

        self.settings = settings
        self.pet_name = pet_name
        self.instance_key = instance_key or pet_name
        self.manifest = load_manifest(pet_name)
        self.fps = int(self.manifest["fps"])
        self.available_groups = list(self.manifest.get("groups", {}).keys())
        self.active_groups = list(self.available_groups) or ["基建"]
        self._state_group_map = {}
        self._rebuild_state_group_map()

        pet_states = self.settings.get("pet_states") or {}
        pet_state = pet_states.get(self.instance_key, {})
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
        self._applied_ref_x = self.manifest.get("size", 1000) / 2
        self._applied_bx = self.state_info("idle")["bbox"][0]
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
        self.status_text = "待机"
        self.status_active = False
        self.tray_hidden = False
        self.fetch_worker = None
        self.mobility = 0
        self.facing = 1
        self.behavior_state = State.IDLE
        self.transparent_mode = False
        self.outline_color = QColor(self.settings.get("render_outline_color", "#FFFF00"))
        self.outline_width = int(self.settings.get("render_outline_width", 2))
        self._outline_cache = {}
        self._last_physics_time = time.monotonic()
        self.sound_fx = sound_effects

        self.matrix = StochasticMatrix()
        self._reconfigure_matrix()

        multi_mon = bool(self.settings.get("display_multi_monitors", True))
        self.plane = Plane()
        self.plane.gravity = float(self.settings.get("physic_gravity", 800))
        self.plane.set_world(get_world_areas(multi_mon))
        self.walk_speed = float(self.settings.get("behavior_walk_speed", 60.0))

        self.timer = QTimer(self)
        self.timer.setInterval(self.tick_ms())
        self.timer.timeout.connect(self.next_frame)
        self.timer.start()

        self.physics_timer = QTimer(self)
        self.physics_timer.setInterval(PHYSICS_INTERVAL)
        self.physics_timer.timeout.connect(self.update_physics)
        self.physics_timer.start()

        self.behavior_timer = QTimer(self)
        self.behavior_timer.setSingleShot(True)
        self.behavior_timer.timeout.connect(self.on_behavior_expired)

        self.window_scan_timer = QTimer(self)
        self.window_scan_timer.setInterval(WINDOW_SCAN_INTERVAL)
        self.window_scan_timer.timeout.connect(self.scan_windows)
        self.window_scan_timer.start()

        self.status_timer = QTimer(self)
        self.status_timer.setInterval(2000)
        self.status_timer.timeout.connect(self.refresh_status)
        self.status_timer.start()

        self.fullscreen_timer = QTimer(self)
        self.fullscreen_timer.setInterval(2000)
        self.fullscreen_timer.timeout.connect(self.check_fullscreen)
        self.fullscreen_timer.start()

        self.bubble = BubbleWidget(self)
        lines_path = os.path.join(PETS_DIR, self.pet_name, "lines.txt")
        try:
            with open(lines_path, encoding="utf-8") as f:
                self._lines = [l.strip() for l in f if l.strip()]
        except OSError:
            self._lines = list(DEFAULT_LINES)

        self.set_state("idle")
        pos_x = pet_state.get("pos_x")
        if pos_x is None:
            pos_x = self.settings.get("pos_x")
        pos_y = pet_state.get("pos_y")
        if pos_y is None:
            pos_y = self.settings.get("pos_y")
        screen = QGuiApplication.primaryScreen().availableGeometry()
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
            self._sync_plane_from_widget()
        else:
            self.move(
                screen.x() + (screen.width() - self.width()) // 2,
                screen.y() + screen.height() - self.height(),
            )
            self._sync_plane_from_widget()
        self.plane.set_obj_size(self.width(), self.height())
        self._schedule_behavior()
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.save_position)
        self.refresh_status()
        self.show()

    def _sync_plane_from_widget(self):
        screen_bottom = get_max_screen_bottom()
        wx, wy = self.x(), self.y()
        plane_x = float(wx)
        plane_y = float(screen_bottom - wy - self.height())
        self.plane.change_position(plane_x, plane_y)

    def _sync_widget_from_plane(self):
        screen_bottom = get_max_screen_bottom()
        wx = int(self.plane.x)
        wy = int(screen_bottom - self.plane.y - self.height())
        self.move(wx, wy)
        if self.bubble.isVisible():
            self.bubble._reposition()

    def tick_ms(self):
        return max(10, int(round(1000 / self.fps / self.speed)))

    def state_info(self, name):
        g = self._current_state_group.get(name)
        if not g:
            g = self._state_group_map.get(name, self.active_groups[:1])[0]
        return self.manifest["groups"][g][name]

    def apply_geometry(self):
        info = self.state_info(self.state)
        old_x, old_y = self.x(), self.y()
        old_w, old_h = self.width(), self.height()
        bx, by, bx2, by2 = info["bbox"]
        y_off = info.get("y_offset", 0)
        x_off = info.get("x_offset", 0)
        by2 += y_off
        canvas_cx = self.manifest.get("size", 1000) / 2
        ref_x = canvas_cx + x_off
        width = int((bx2 - bx + 1) * self.scale) + PAD * 2
        status_extra = STATUS_H if self.show_status else 0
        height = int((by2 - by + 1) * self.scale) + PAD * 2 + status_extra
        self.resize(width, height)
        anchor_x = old_x + PAD + (self._applied_ref_x - self._applied_bx) * self.scale
        bottom_y = old_y + old_h
        new_x = int(anchor_x - PAD - (ref_x - bx) * self.scale)
        new_y = int(bottom_y - height)
        self.move(new_x, new_y)
        self._applied_ref_x = ref_x
        self._applied_bx = bx
        self.plane.set_obj_size(width, height)
        self._sync_plane_from_widget()

    def set_state(self, name, hold=False, group=None):
        if name not in self._state_group_map:
            return
        self._current_state_group[name] = group or self._pick_group_for_state(name)
        self.state = name
        self.hold_state = hold
        self.frame_index = 0
        self.cache.clear()
        self._outline_cache.clear()
        self.apply_geometry()
        self.update()

    def _schedule_behavior(self):
        info = self.state_info(self.state)
        count = info["count"]
        duration_s = max(MIN_DURATION, count / self.fps / self.speed)
        if self.state in ("sit", "sleep"):
            duration_s = max(duration_s, 5.0 + 3.0 * (self.state == "sleep"))
        self.behavior_timer.start(int(duration_s * 1000))

    def on_behavior_expired(self):
        if self.hold_state or self.drag:
            self._schedule_behavior()
            return
        new_state = self.matrix.transition(self.behavior_state)
        self.behavior_state = new_state
        anim_name, mob = STATE_TO_ANIM[new_state]
        self.mobility = mob
        if anim_name == "interact" and self._extra_anims:
            pool = list(self._extra_anims)
            if "interact" in self._state_group_map:
                pool.append("interact")
            chosen = random.choice(pool)
            self.set_state(chosen)
        elif anim_name in self._state_group_map:
            self.set_state(anim_name)
        else:
            self.set_state("idle")
            self.mobility = 0
        self._sync_plane_from_widget()
        self._schedule_behavior()
        if anim_name in ("idle", "sit") and self._lines and random.random() < 0.2:
            self._show_random_line()

    def _should_show_outline(self):
        mode = self.settings.get("render_outline", "dragging")
        if mode == "always":
            return True
        if mode == "dragging":
            return self.drag
        if mode == "pressing":
            return self.press_global is not None
        return False

    def _get_outline_image(self, image):
        key = (self.frame_index, self.facing < 0)
        cached = self._outline_cache.get(key)
        if cached is not None:
            return cached
        outline = QImage(image.size(), QImage.Format.Format_ARGB32_Premultiplied)
        outline.fill(Qt.transparent)
        p = QPainter(outline)
        p.drawImage(0, 0, image)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        p.fillRect(outline.rect(), self.outline_color)
        p.end()
        if len(self._outline_cache) > 10:
            self._outline_cache.clear()
        self._outline_cache[key] = outline
        return outline

    def toggle_transparent(self):
        self.transparent_mode = not self.transparent_mode
        if IS_WINDOWS:
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            GWL_EXSTYLE = -20
            WS_EX_TRANSPARENT = 0x00000020
            ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if self.transparent_mode:
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style | WS_EX_TRANSPARENT)
            else:
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style & ~WS_EX_TRANSPARENT)
        else:
            self.setAttribute(Qt.WA_TransparentForMouseEvents, self.transparent_mode)
        if self.transparent_mode:
            self.setWindowOpacity(float(self.settings.get("opacity_dim", 0.75)))
        else:
            self.setWindowOpacity(1.0)

    def _play_sound(self, name):
        if not self.sound_fx:
            return
        if not self.settings.get("sound_enabled", True):
            return
        fx = self.sound_fx.get(name)
        if fx:
            vol = max(0, min(100, int(self.settings.get("sound_volume", 50))))
            fx.setVolume(vol / 100.0)
            fx.play()

    def update_physics(self):
        if self.drag:
            return
        now = time.monotonic()
        dt = min(now - self._last_physics_time, 0.1)
        self._last_physics_time = now

        self._update_peer_charges()
        self.plane.update(dt)

        if self.mobility != 0:
            walk_dx = self.walk_speed * self.scale * self.mobility * dt
            self.plane.x = self.plane._limit_x(self.plane.x + walk_dx)

        if self.mobility != 0:
            self.facing = 1 if self.mobility > 0 else -1
            if self.mobility > 0 and self.plane.x >= self.plane.border_right() - self.plane.obj_w:
                self.mobility = -self.mobility
                self.facing = -1
                if self.behavior_state == State.MOVE_R:
                    self.behavior_state = State.MOVE_L
            elif self.mobility < 0 and self.plane.x <= self.plane.border_left():
                self.mobility = -self.mobility
                self.facing = 1
                if self.behavior_state == State.MOVE_L:
                    self.behavior_state = State.MOVE_R

        if self.plane.is_dropped:
            self.set_state("interact")
            self.mobility = 0
            self._schedule_behavior()
            self._play_sound("drop")

        self._sync_widget_from_plane()

    def _update_peer_charges(self):
        self.plane.point_charges.clear()
        if not self.settings.get("behavior_do_peer_repulsion", True):
            return
        my_cx = self.plane.x + self.plane.obj_w / 2
        for pw in pet_windows:
            if pw is self:
                continue
            cx = pw.plane.x + pw.plane.obj_w / 2
            if abs(my_cx - cx) > REPULSION_MAX_DIST:
                continue
            cy = pw.plane.y + pw.plane.obj_h / 2
            self.plane.set_point_charge(cy, cx, REPULSION_QUANTITY)

    def scan_windows(self):
        screen_bottom = get_max_screen_bottom()
        try:
            barriers = window_detect.find_barriers(
                self.x(), self.width(), None, screen_bottom
            )
            self.plane.barriers = barriers
        except Exception:
            self.plane.barriers = []

    def frame_path(self, index):
        pad = str(index).zfill(4)
        frames_dir = self._frames_dir_for_state(self.state)
        return os.path.join(frames_dir, self.state, f"frame_{pad}.png")

    def current_image(self):
        cached = self.cache.get(self.frame_index)
        if cached is not None:
            return cached
        image = QImage(self.frame_path(self.frame_index))
        if not image.isNull():
            w = int(image.width() * self.scale)
            h = int(image.height() * self.scale)
            scaled = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
            scaled.fill(Qt.transparent)
            p = QPainter(scaled)
            p.setRenderHint(QPainter.SmoothPixmapTransform)
            p.drawImage(QRectF(0, 0, w, h), image)
            p.end()
            if len(self.cache) > 5:
                self.cache.clear()
            self.cache[self.frame_index] = scaled
            return scaled
        return image

    def next_frame(self):
        info = self.state_info(self.state)
        count = info["count"]
        is_loop = info.get("loop", self.state in LOOP_STATES)
        if is_loop:
            self.frame_index = (self.frame_index + 1) % count
        elif self.frame_index >= count - 1:
            self.set_state("idle")
            self._sync_widget_from_plane()
            self.mobility = 0
            self.behavior_state = State.IDLE
            self._schedule_behavior()
            return
        else:
            self.frame_index += 1
        self.update()

    def paintEvent(self, event):
        info = self.state_info(self.state)
        bx, by, _, _ = info["bbox"]
        image = self.current_image()
        painter = QPainter(self)
        status_extra = STATUS_H if self.show_status else 0
        if not image.isNull():
            draw_img = image
            if self.facing < 0:
                draw_img = image.mirrored(True, False)
            dx = int(PAD - bx * self.scale)
            dy = int(status_extra + PAD - by * self.scale)
            if self._should_show_outline():
                outline_img = self._get_outline_image(draw_img)
                ow = int(self.outline_width * self.scale)
                for ox, oy in [(-ow, 0), (ow, 0), (0, -ow), (0, ow)]:
                    painter.drawImage(dx + ox, dy + oy, outline_img)
            painter.drawImage(dx, dy, draw_img)

        if self.show_status:
            bar_width = max(
                120, int((self.width() - 12) * self.bar_length / 100.0)
            )
            bar = QRectF(6, 4, bar_width, STATUS_H - 8)
            if self.status_active:
                painter.setBrush(QColor(30, 120, 70, 190))
            else:
                painter.setBrush(QColor(25, 25, 25, 170))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(bar, 8, 8)

            font = QFont()
            font.setPixelSize(self.subtitle_size)
            painter.setFont(font)
            metrics = QFontMetrics(font)
            elided = metrics.elidedText(
                self.status_text, Qt.ElideRight, int(bar.width() - 16)
            )
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(
                bar.adjusted(8, 0, -8, 0),
                Qt.AlignVCenter | Qt.AlignLeft,
                elided,
            )

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag = False
            self.pre_drag_state = self.state
            self.pre_drag_hold = self.hold_state
            self.press_global = event.globalPosition().toPoint()
            self.press_window = self.pos()
            self.press_time = time.monotonic()
            self.mobility = 0

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
            self.behavior_timer.stop()
            if self.state != "move":
                self.set_state("move")
        if self.drag and not (event.buttons() & Qt.LeftButton):
            self._end_drag()
        elif self.drag:
            self.move(self.press_window.x() + dx, self.press_window.y() + dy)

    def _end_drag(self):
        self.drag = False
        self.press_global = None
        self.press_window = None
        self._sync_plane_from_widget()
        self.plane.vy = 0
        self._last_physics_time = time.monotonic()
        self.set_state("idle")
        self.behavior_state = State.IDLE
        self.mobility = 0
        self._schedule_behavior()
        self.save_pet_state()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        if self.drag:
            self._end_drag()
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
            self.behavior_state = State.INTERACT
            self._schedule_behavior()
            self._play_sound("click")
            if self._lines:
                self._show_random_line()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggle_mini()

    def contextMenuEvent(self, event):
        if self.mobility != 0:
            self.mobility = 0
            self.behavior_state = State.IDLE
            self.set_state("idle")
            self._schedule_behavior()
        menu = QMenu(self)
        state_labels = [
            ("idle", "放松"),
            ("sit", "坐下"),
            ("sleep", "睡觉"),
            ("interact", "互动"),
            ("move", "散步"),
        ]
        known_states = {k for k, _ in state_labels}
        groups = self.manifest.get("groups", {})
        for g in self.active_groups:
            g_states = groups.get(g, {})
            sub = menu.addMenu(g)
            for key, label in state_labels:
                if key in g_states:
                    sub.addAction(
                        QAction(label, self, triggered=lambda _, k=key, gn=g: self._manual_state(k, gn))
                    )
            for key in sorted(g_states.keys()):
                if key not in known_states:
                    sub.addAction(
                        QAction(key, self, triggered=lambda _, k=key, gn=g: self._manual_state(k, gn))
                    )
        face_label = "面朝左 ←" if self.facing > 0 else "面朝右 →"
        menu.addAction(QAction(face_label, self, triggered=self._flip_facing))
        menu.addSeparator()
        menu.addAction(QAction(f"再来一个 {self.pet_name}", self, triggered=self._spawn_clone))
        if len(pet_windows) > 1:
            menu.addAction(QAction("移除此宠物", self, triggered=self._remove_self))
        pet_menu = menu.addMenu("桌宠库")
        active_names = [pw.pet_name for pw in pet_windows]
        for name in list_pets():
            action = QAction(name, self, checkable=True)
            action.setChecked(name in active_names)
            action.triggered.connect(
                lambda checked, n=name: self._toggle_pet(n, checked)
            )
            pet_menu.addAction(action)
        pet_menu.addSeparator()
        pet_menu.addAction(
            QAction("角色管理...", self, triggered=self._manage_pets_dialog)
        )
        if self.available_groups:
            group_menu = menu.addMenu("动画组")
            for g in self.available_groups:
                action = QAction(g, self, checkable=True)
                action.setChecked(g in self.active_groups)
                action.triggered.connect(
                    lambda checked, gn=g: self.toggle_group(gn)
                )
                group_menu.addAction(action)
        menu.addAction(QAction("动作设置...", self, triggered=self._action_settings_dialog))
        menu.addAction(QAction("获取PRTS台词", self, triggered=self._fetch_prts_lines))
        menu.addSeparator()
        mini_action = QAction("迷你模式（隐藏字幕）", self, checkable=True)
        mini_action.setChecked(not self.show_status)
        mini_action.triggered.connect(self.toggle_mini)
        menu.addAction(mini_action)
        full_action = QAction("全屏应用时自动隐藏", self, checkable=True)
        full_action.setChecked(self.auto_hide_fullscreen)
        full_action.triggered.connect(self.toggle_fullscreen_auto_hide)
        menu.addAction(full_action)
        trans_action = QAction("透明穿透 (Ctrl+Shift+T)", self, checkable=True)
        trans_action.setChecked(self.transparent_mode)
        trans_action.triggered.connect(lambda: _toggle_transparent_all())
        menu.addAction(trans_action)
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
            QAction("隐藏到托盘", self, triggered=self._hide_all_to_tray)
        )
        menu.addAction(
            QAction("完全退出", self, triggered=self.quit_pet)
        )
        menu.exec(event.globalPos())

    def _spawn_clone(self):
        key = _next_instance_key(self.pet_name)
        pw = PetWindow(self.pet_name, self.settings, self.sound_fx, instance_key=key)
        pet_windows.append(pw)
        self._save_active_pets()

    def _remove_self(self):
        if len(pet_windows) <= 1:
            return
        pet_windows.remove(self)
        self.save_pet_state()
        self._save_active_pets()
        QTimer.singleShot(0, self.close)
        QTimer.singleShot(0, self.deleteLater)

    def _toggle_pet(self, name, checked):
        if checked:
            for pw in pet_windows:
                if pw.pet_name == name:
                    return
            pw = PetWindow(name, self.settings, self.sound_fx)
            pet_windows.append(pw)
        else:
            if len(pet_windows) <= 1:
                return
            for pw in pet_windows:
                if pw.pet_name == name:
                    pet_windows.remove(pw)
                    pw.save_pet_state()
                    QTimer.singleShot(0, pw.close)
                    QTimer.singleShot(0, pw.deleteLater)
                    break
        self._save_active_pets()

    def _save_active_pets(self):
        self.settings["active_pets"] = [pw.pet_name for pw in pet_windows]
        save_settings(self.settings)

    def _manual_state(self, name, group=None):
        self.behavior_timer.stop()
        state_map = {
            "idle": (State.IDLE, 0),
            "sit": (State.SIT, 0),
            "sleep": (State.SLEEP, 0),
            "interact": (State.INTERACT, 0),
            "move": (State.MOVE_R if self.facing > 0 else State.MOVE_L, self.facing),
        }
        st, mob = state_map.get(name, (State.IDLE, 0))
        self.mobility = mob
        self.set_state(name, hold=True, group=group)
        self.behavior_state = st

    def _flip_facing(self):
        self.facing = -self.facing
        if self.mobility != 0:
            self.mobility = -self.mobility
        self.update()

    def scale_up(self):
        self.set_scale(self.scale + 0.1)

    def scale_down(self):
        self.set_scale(self.scale - 0.1)

    def set_scale(self, value):
        self.scale = max(MIN_SCALE, min(MAX_SCALE, round(value, 1)))
        self.cache.clear()
        self._outline_cache.clear()
        self.apply_geometry()
        self.settings["scale"] = self.scale
        self.save_pet_state()
        self.update()

    def _rebuild_state_group_map(self):
        self._state_group_map = {}
        groups = self.manifest.get("groups", {})
        for g in self.active_groups:
            for state in groups.get(g, {}):
                self._state_group_map.setdefault(state, [])
                if g not in self._state_group_map[state]:
                    self._state_group_map[state].append(g)
        self._extra_anims = []
        for s in self._state_group_map:
            if s in STANDARD_ANIMS:
                continue
            for g in self._state_group_map[s]:
                info = groups.get(g, {}).get(s, {})
                if info.get("auto_play", True):
                    self._extra_anims.append(s)
                    break
        self._current_state_group = {}

    def _pick_group_for_state(self, state):
        candidates = self._state_group_map.get(state, self.active_groups[:1])
        if len(candidates) == 1:
            return candidates[0]
        return random.choice(candidates)

    def _frames_dir_for_state(self, state):
        g = self._current_state_group.get(state)
        if not g:
            g = self._state_group_map.get(state, self.active_groups[:1])[0]
        return os.path.join(PETS_DIR, self.pet_name, "frames", g)

    def _reconfigure_matrix(self):
        self.matrix = StochasticMatrix()
        available = set(self._state_group_map.keys())
        if not self.settings.get("behavior_allow_sit", True):
            available.discard("sit")
        if not self.settings.get("behavior_allow_sleep", True):
            available.discard("sleep")
        if not self.settings.get("behavior_allow_walk", True):
            available.discard("move")
        self.matrix.configure(
            available,
            self.settings.get("behavior_ai_activation", 4),
        )
        if self._extra_anims:
            for row in self.matrix.weights:
                row[State.INTERACT] = round(row[State.INTERACT] * 5)

    def toggle_group(self, group_name):
        if group_name in self.active_groups:
            if len(self.active_groups) <= 1:
                return
            self.active_groups.remove(group_name)
        else:
            if group_name not in self.manifest.get("groups", {}):
                return
            self.active_groups.append(group_name)
        self._rebuild_state_group_map()
        self.cache.clear()
        self._outline_cache.clear()
        self._reconfigure_matrix()
        if self.state not in self._state_group_map:
            self.set_state("idle")
            self.mobility = 0
            self.behavior_state = State.IDLE
        self.apply_geometry()

    def _refresh_manifest(self):
        self.manifest = load_manifest(self.pet_name)
        self.available_groups = list(self.manifest.get("groups", {}).keys())
        for g in list(self.active_groups):
            if g not in self.available_groups:
                self.active_groups.remove(g)
        for g in self.available_groups:
            if g not in self.active_groups:
                self.active_groups.append(g)
        self._rebuild_state_group_map()
        self._reconfigure_matrix()

    def _refresh_manage_pet_list(self):
        pl = getattr(self, "_manage_pet_list", None)
        if not pl:
            return
        active_names = [pw.pet_name for pw in pet_windows]
        pl.clear()
        for name in list_pets():
            item = QListWidgetItem(name)
            item.setCheckState(Qt.Checked if name in active_names else Qt.Unchecked)
            manifest_path = os.path.join(PETS_DIR, name, "manifest.json")
            if os.path.isfile(manifest_path):
                with open(manifest_path, encoding="utf-8") as f:
                    m = json.load(f)
                groups = list(m.get("groups", {}).keys())
                item.setToolTip("动画组: " + ", ".join(groups))
                item.setText(f"{name}  [{', '.join(groups)}]")
            pl.addItem(item)

    def _show_random_line(self):
        if not self._lines:
            return
        line = random.choice(self._lines)
        dr_name = self.settings.get("doctor_name", "博士")
        line = line.replace("{博士}", dr_name)
        self.bubble.show_text(line)

    def _fetch_prts_lines(self):
        lines_path = os.path.join(PETS_DIR, self.pet_name, "lines.txt")
        if os.path.isfile(lines_path):
            r = QMessageBox.question(
                self, "获取PRTS台词",
                f"已存在 lines.txt（{len(self._lines)} 条），是否覆盖？",
            )
            if r != QMessageBox.Yes:
                return
        lines = fetch_prts_lines(self.pet_name)
        if not lines:
            self.bubble.show_text("获取失败或无台词", 2000)
            return
        with open(lines_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        self._lines = lines
        self.bubble.show_text(f"已获取 {len(lines)} 条台词", 2500)

    def _action_settings_dialog(self):
        orig_state = self.state
        orig_group = self._current_state_group.get(self.state)
        orig_hold = self.hold_state
        dlg = QDialog(self)
        dlg.setWindowTitle(f"动作设置 - {self.pet_name}")
        dlg.setMinimumWidth(420)
        layout = QVBoxLayout(dlg)
        groups = self.manifest.get("groups", {})
        tabs = QTabWidget()
        widgets = []
        state_labels = {
            "idle": "放松", "sit": "坐下", "sleep": "睡觉",
            "interact": "互动", "move": "散步",
        }

        def preview(g, s):
            self.set_state(s, hold=True, group=g)

        for g_name in self.available_groups:
            g_states = groups.get(g_name, {})
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            container = QWidget()
            vl = QVBoxLayout(container)
            for state_key in sorted(g_states.keys()):
                info = g_states[state_key]
                label = state_labels.get(state_key, state_key)
                is_loop = info.get("loop", state_key in LOOP_STATES)
                is_extra = state_key not in STANDARD_ANIMS
                auto_play = info.get("auto_play", True) if is_extra else None
                y_off = info.get("y_offset", 0)
                x_off = info.get("x_offset", 0)
                row = QHBoxLayout()
                prev_btn = QPushButton("预览")
                prev_btn.setFixedWidth(40)
                prev_btn.clicked.connect(
                    lambda _, g=g_name, s=state_key: preview(g, s)
                )
                row.addWidget(prev_btn)
                cb = QCheckBox(f"{label}  —  循环")
                cb.setChecked(is_loop)
                row.addWidget(cb)
                ap_cb = None
                if is_extra:
                    ap_cb = QCheckBox("待机")
                    ap_cb.setChecked(auto_play)
                    ap_cb.setToolTip("加入待机动作队列")
                    row.addWidget(ap_cb)
                row.addStretch()
                off_label = QLabel(f"X:{x_off} Y:{y_off}")
                row.addWidget(off_label)
                adj_btn = QPushButton("调整轴线")
                adj_btn.setFixedWidth(70)
                row.addWidget(adj_btn)
                widgets.append({
                    "group": g_name, "state": state_key,
                    "cb": cb, "ap_cb": ap_cb, "off_label": off_label,
                    "y_offset": y_off, "x_offset": x_off,
                })
                idx = len(widgets) - 1
                adj_btn.clicked.connect(
                    lambda _, i=idx: self._ground_line_editor(widgets[i], dlg)
                )
                vl.addLayout(row)
            vl.addStretch()
            scroll.setWidget(container)
            tabs.addTab(scroll, g_name)
        layout.addWidget(tabs)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)
        accepted = dlg.exec() == QDialog.Accepted
        self.set_state(orig_state, hold=orig_hold, group=orig_group)
        if not accepted:
            return
        for w in widgets:
            g, s = w["group"], w["state"]
            default_loop = s in LOOP_STATES
            if w["cb"].isChecked() != default_loop:
                self.manifest["groups"][g][s]["loop"] = w["cb"].isChecked()
            elif "loop" in self.manifest["groups"][g][s]:
                del self.manifest["groups"][g][s]["loop"]
            if w["ap_cb"] is not None:
                if not w["ap_cb"].isChecked():
                    self.manifest["groups"][g][s]["auto_play"] = False
                elif "auto_play" in self.manifest["groups"][g][s]:
                    del self.manifest["groups"][g][s]["auto_play"]
            if w["y_offset"] != 0:
                self.manifest["groups"][g][s]["y_offset"] = w["y_offset"]
            elif "y_offset" in self.manifest["groups"][g][s]:
                del self.manifest["groups"][g][s]["y_offset"]
            if w["x_offset"] != 0:
                self.manifest["groups"][g][s]["x_offset"] = w["x_offset"]
            elif "x_offset" in self.manifest["groups"][g][s]:
                del self.manifest["groups"][g][s]["x_offset"]
        manifest_path = os.path.join(PETS_DIR, self.pet_name, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(self.manifest, f, ensure_ascii=False, indent=2)
        self._rebuild_state_group_map()
        self._reconfigure_matrix()

    def _ground_line_editor(self, widget_info, parent):
        g = widget_info["group"]
        s = widget_info["state"]
        info = self.manifest["groups"][g][s]
        bx, by, bx2, by2 = info["bbox"]
        frames_dir = os.path.join(PETS_DIR, self.pet_name, "frames", g, s)
        frame_files = sorted(
            f for f in os.listdir(frames_dir) if f.endswith(".png")
        ) if os.path.isdir(frames_dir) else []
        if not frame_files:
            return
        frame_images = []
        for ff in frame_files:
            img = QImage(os.path.join(frames_dir, ff))
            if not img.isNull():
                frame_images.append(img)
        if not frame_images:
            return
        preview_h = 500
        preview_w = 500
        img_scale = min(preview_w / frame_images[0].width(), preview_h / frame_images[0].height())
        bbox_center_x = (bx + bx2) / 2

        class GroundLineWidget(QWidget):
            def __init__(self, parent_widget=None):
                super().__init__(parent_widget)
                self.setFixedSize(preview_w, preview_h)
                self.ground_y = by2 + widget_info["y_offset"]
                self.center_x = bbox_center_x + widget_info["x_offset"]
                self.dragging_h = False
                self.dragging_v = False
                self.frame_idx = 0

            def paintEvent(self, event):
                src_img = frame_images[self.frame_idx]
                p = QPainter(self)
                p.fillRect(self.rect(), QColor(40, 40, 40))
                p.setRenderHint(QPainter.SmoothPixmapTransform)
                iw = src_img.width() * img_scale
                ih = src_img.height() * img_scale
                ix = (preview_w - iw) / 2
                iy = (preview_h - ih) / 2
                p.drawImage(QRectF(ix, iy, iw, ih), src_img)

                gy = iy + self.ground_y * img_scale
                p.setPen(QColor(255, 50, 50, 200))
                p.drawLine(0, int(gy), preview_w, int(gy))
                p.setPen(QColor(255, 255, 255))
                p.drawText(5, int(gy) - 4, f"地面Y: {self.ground_y}")

                ref_y = iy + by2 * img_scale
                p.setPen(QColor(100, 200, 100, 120))
                p.drawLine(0, int(ref_y), preview_w, int(ref_y))
                p.drawText(5, int(ref_y) + 14, f"bbox底: {by2}")

                cx = ix + self.center_x * img_scale
                p.setPen(QColor(255, 50, 50, 200))
                p.drawLine(int(cx), 0, int(cx), preview_h)
                p.drawText(int(cx) + 3, 15, f"中轴X: {int(self.center_x)}")

                ref_cx = ix + bbox_center_x * img_scale
                p.setPen(QColor(100, 200, 100, 120))
                p.drawLine(int(ref_cx), 0, int(ref_cx), preview_h)
                p.drawText(int(ref_cx) + 3, 30, f"bbox中: {int(bbox_center_x)}")
                p.end()

            def mousePressEvent(self, event):
                mx, my = event.position().x(), event.position().y()
                iw = frame_images[0].width() * img_scale
                ih = frame_images[0].height() * img_scale
                ix = (preview_w - iw) / 2
                iy = (preview_h - ih) / 2
                gy = iy + self.ground_y * img_scale
                cx = ix + self.center_x * img_scale
                if abs(my - gy) < 10:
                    self.dragging_h = True
                elif abs(mx - cx) < 10:
                    self.dragging_v = True
                else:
                    dist_h = abs(my - gy)
                    dist_v = abs(mx - cx)
                    if dist_h < dist_v:
                        self.dragging_h = True
                    else:
                        self.dragging_v = True
                self._update_pos(mx, my)

            def mouseMoveEvent(self, event):
                if self.dragging_h or self.dragging_v:
                    self._update_pos(event.position().x(), event.position().y())

            def mouseReleaseEvent(self, event):
                self.dragging_h = False
                self.dragging_v = False

            def _update_pos(self, mouse_x, mouse_y):
                iw = frame_images[0].width() * img_scale
                ih = frame_images[0].height() * img_scale
                ix = (preview_w - iw) / 2
                iy = (preview_h - ih) / 2
                if self.dragging_h:
                    raw = (mouse_y - iy) / img_scale
                    self.ground_y = max(0, min(frame_images[0].height() - 1, int(raw)))
                if self.dragging_v:
                    raw = (mouse_x - ix) / img_scale
                    self.center_x = max(0, min(frame_images[0].width() - 1, raw))
                self.update()

        dlg = QDialog(parent)
        dlg.setWindowTitle(f"调整轴线 - {s}")
        vl = QVBoxLayout(dlg)
        vl.addWidget(QLabel("红色横线=地面，红色竖线=中轴（绿线=原始bbox参考）"))
        gw = GroundLineWidget(dlg)
        vl.addWidget(gw)

        total = len(frame_images)
        ctl = QHBoxLayout()
        play_btn = QPushButton("⏸")
        play_btn.setFixedWidth(32)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, total - 1)
        frame_label = QLabel(f"0/{total}")
        frame_label.setFixedWidth(70)
        ctl.addWidget(play_btn)
        ctl.addWidget(slider)
        ctl.addWidget(frame_label)
        vl.addLayout(ctl)

        playing = [True]
        timer = QTimer(dlg)
        tick = max(10, int(round(1000 / self.fps)))
        timer.setInterval(tick)

        def on_tick():
            idx = (gw.frame_idx + 1) % total
            gw.frame_idx = idx
            slider.setValue(idx)
            frame_label.setText(f"{idx}/{total}")
            gw.update()

        def on_slider(val):
            gw.frame_idx = val
            frame_label.setText(f"{val}/{total}")
            gw.update()

        def toggle_play():
            playing[0] = not playing[0]
            if playing[0]:
                play_btn.setText("⏸")
                timer.start()
            else:
                play_btn.setText("▶")
                timer.stop()

        timer.timeout.connect(on_tick)
        slider.valueChanged.connect(on_slider)
        play_btn.clicked.connect(toggle_play)
        timer.start()

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        vl.addWidget(btns)
        result = dlg.exec()
        timer.stop()
        if result == QDialog.Accepted:
            widget_info["y_offset"] = gw.ground_y - by2
            widget_info["x_offset"] = int(gw.center_x - bbox_center_x)
            widget_info["off_label"].setText(f"X:{widget_info['x_offset']} Y:{widget_info['y_offset']}")

    def _manage_pets_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("角色管理")
        dlg.setMinimumWidth(420)
        layout = QVBoxLayout(dlg)

        pets = list_pets()
        active_names = [pw.pet_name for pw in pet_windows]

        grp_active = QGroupBox("已有角色")
        gl = QVBoxLayout(grp_active)
        pet_list = QListWidget()
        for name in pets:
            item = QListWidgetItem(name)
            item.setCheckState(Qt.Checked if name in active_names else Qt.Unchecked)
            manifest_path = os.path.join(PETS_DIR, name, "manifest.json")
            if os.path.isfile(manifest_path):
                with open(manifest_path, encoding="utf-8") as f:
                    m = json.load(f)
                groups = list(m.get("groups", {}).keys())
                item.setToolTip("动画组: " + ", ".join(groups))
                item.setText(f"{name}  [{', '.join(groups)}]")
            pet_list.addItem(item)
        gl.addWidget(pet_list)
        layout.addWidget(grp_active)

        grp_add = QGroupBox("下载动画")
        al = QVBoxLayout(grp_add)
        form = QFormLayout()
        name_edit = QLineEdit()
        name_edit.setPlaceholderText("干员名（可选：干员名 皮肤 皮肤名）")
        form.addRow("干员名:", name_edit)
        group_checks = {}
        gc_layout = QHBoxLayout()
        for gn in ["基建", "正面", "背面"]:
            cb = QCheckBox(gn)
            if gn == "基建":
                cb.setChecked(True)
            group_checks[gn] = cb
            gc_layout.addWidget(cb)
        form.addRow("模型组:", gc_layout)
        al.addLayout(form)
        btn_row = QHBoxLayout()
        dl_btn = QPushButton("下载动画")
        lines_btn = QPushButton("获取PRTS台词")
        btn_row.addWidget(dl_btn)
        btn_row.addWidget(lines_btn)
        al.addLayout(btn_row)
        layout.addWidget(grp_add)

        def on_pet_selected():
            items = pet_list.selectedItems()
            if items:
                raw = items[0].text().split("[")[0].strip()
                name_edit.setText(raw)

        pet_list.itemClicked.connect(on_pet_selected)

        self._manage_dlg = dlg
        self._manage_pet_list = pet_list
        self._manage_name_edit = name_edit
        self._manage_group_checks = group_checks

        def on_download():
            text = name_edit.text().strip()
            selected_groups = [g for g, cb in group_checks.items() if cb.isChecked()]
            if not text or not selected_groups:
                return
            parts = text.split("皮肤")
            operator = parts[0].strip()
            skin = parts[1].strip() if len(parts) > 1 else None
            if not operator:
                return
            if self.fetch_worker and self.fetch_worker.isRunning():
                QMessageBox.information(dlg, "下载", "正在拉取中，请稍候...")
                return
            self._pending_groups = list(selected_groups)
            self._pending_operator = operator
            self._pending_skin = skin
            _start_next_group(self)

        def _start_next_group(pet_win):
            if not pet_win._pending_groups:
                return
            group = pet_win._pending_groups.pop(0)
            op = pet_win._pending_operator
            skin = pet_win._pending_skin
            pet_win.fetch_progress = QProgressDialog(
                f"正在准备 {op} ({group}) ...", "取消", 0, 3, dlg
            )
            pet_win.fetch_progress.setWindowTitle("下载动画")
            pet_win.fetch_progress.setMinimumWidth(320)
            pet_win.fetch_progress.setMinimumDuration(0)
            pet_win.fetch_progress.setValue(0)
            pet_win.fetch_progress.canceled.connect(pet_win._cancel_fetch)
            pet_win.fetch_worker = FetchWorker(op, skin, group)
            pet_win.fetch_worker.progress.connect(pet_win._on_fetch_progress)
            pet_win.fetch_worker.finished.connect(
                lambda msg, ok: _on_group_done(pet_win, msg, ok)
            )
            pet_win.fetch_worker.start()

        def _on_group_done(pet_win, msg, success):
            pet_win._on_fetch_finished(msg, success)
            if success and pet_win._pending_groups:
                _start_next_group(pet_win)

        def on_fetch_lines():
            text = name_edit.text().strip()
            if not text:
                return
            operator = text.split("皮肤")[0].strip()
            if not operator:
                return
            lines_path = os.path.join(PETS_DIR, operator, "lines.txt")
            if os.path.isfile(lines_path):
                r = QMessageBox.question(
                    dlg, "获取PRTS台词",
                    f"{operator} 已有台词文件，是否覆盖？",
                )
                if r != QMessageBox.Yes:
                    return
            lines = fetch_prts_lines(operator)
            if not lines:
                QMessageBox.warning(dlg, "获取台词", "获取失败或无台词")
                return
            os.makedirs(os.path.join(PETS_DIR, operator), exist_ok=True)
            with open(lines_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            if operator == self.pet_name:
                self._lines = lines
            QMessageBox.information(dlg, "获取台词", f"已获取 {len(lines)} 条台词")

        dl_btn.clicked.connect(on_download)
        lines_btn.clicked.connect(on_fetch_lines)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        dlg.exec()

        for i in range(pet_list.count()):
            item = pet_list.item(i)
            raw = item.text().split("[")[0].strip()
            checked = item.checkState() == Qt.Checked
            is_active = raw in [pw.pet_name for pw in pet_windows]
            if checked and not is_active:
                self._toggle_pet(raw, True)
            elif not checked and is_active:
                self._toggle_pet(raw, False)

    def _cancel_fetch(self):
        if self.fetch_worker and self.fetch_worker.isRunning():
            self.fetch_worker.terminate()

    def _on_fetch_progress(self, msg):
        self.status_text = msg
        self.status_active = True
        self.update()
        if hasattr(self, "fetch_progress") and self.fetch_progress:
            step = self.fetch_progress.value() + 1
            self.fetch_progress.setValue(min(step, 2))
            self.fetch_progress.setLabelText(msg)

    def _on_fetch_finished(self, msg, success):
        self.status_text = msg
        self.status_active = False
        self.update()
        if hasattr(self, "fetch_progress") and self.fetch_progress:
            self.fetch_progress.setValue(3)
            self.fetch_progress.close()
            self.fetch_progress = None
        if success:
            QMessageBox.information(self, "添加角色", msg)
            self._refresh_manifest()
            self._refresh_manage_pet_list()
            QTimer.singleShot(500, self.refresh_status)
        else:
            QMessageBox.warning(self, "添加角色", msg)

    def save_pet_state(self):
        pet_states = self.settings.setdefault("pet_states", {})
        pet_states[self.instance_key] = {
            "scale": self.scale,
            "speed": self.speed,
            "pos_x": self.x(),
            "pos_y": self.y(),
        }
        self.settings["active_pets"] = [pw.pet_name for pw in pet_windows]
        save_settings(self.settings)

    def save_position(self):
        self.save_pet_state()

    def toggle_mini(self):
        self.show_status = not self.show_status
        self.settings["mini_mode"] = not self.show_status
        save_settings(self.settings)
        for pw in pet_windows:
            pw.show_status = self.show_status
            pw.apply_geometry()
            pw.update()

    def toggle_fullscreen_auto_hide(self):
        self.auto_hide_fullscreen = not self.auto_hide_fullscreen
        self.settings["auto_hide_fullscreen"] = self.auto_hide_fullscreen
        save_settings(self.settings)
        for pw in pet_windows:
            pw.auto_hide_fullscreen = self.auto_hide_fullscreen
        self.check_fullscreen()

    def check_fullscreen(self):
        if self.tray_hidden:
            return
        if not self.auto_hide_fullscreen:
            if not self.isVisible():
                self.show()
            return
        is_full = False
        if IS_WINDOWS:
            user32 = ctypes.windll.user32
            user32.GetForegroundWindow.restype = wintypes.HWND
            user32.GetWindowRect.argtypes = [
                wintypes.HWND,
                ctypes.POINTER(wintypes.RECT),
            ]
            hwnd = user32.GetForegroundWindow()
            if not hwnd or hwnd == int(self.winId()):
                pass
            else:
                rect = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                screen = QGuiApplication.primaryScreen().geometry()
                is_full = (
                    rect.left <= screen.x()
                    and rect.top <= screen.y()
                    and rect.right >= screen.x() + screen.width()
                    and rect.bottom >= screen.y() + screen.height()
                )
        if is_full:
            self.hide()
        elif not self.isVisible():
            self.show()

    def _hide_all_to_tray(self):
        for pw in pet_windows:
            pw.tray_hidden = True
            pw.hide()

    def _show_all_from_tray(self):
        for pw in pet_windows:
            pw.tray_hidden = False
            pw.show()
            pw.raise_()

    def hide_to_tray(self):
        self.tray_hidden = True
        self.hide()

    def show_from_tray(self):
        self.tray_hidden = False
        self.show()
        self.raise_()
        self.activateWindow()

    def quit_pet(self):
        for pw in pet_windows:
            pw.save_pet_state()
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
        for pw in pet_windows:
            pw.locked = self.locked
        self.drag = False
        self.press_global = None
        self.press_window = None

    def open_settings(self):
        self.settings["speed"] = self.speed
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() != QDialog.Accepted:
            return
        data = dialog.values()
        old_autostart = bool(self.settings.get("autostart_with_codex", False))
        merged = dict(self.settings)
        merged.update(data)
        self.settings = merged
        save_settings(merged)
        for pw in pet_windows:
            pw.settings = merged
            pw.speed = float(data["speed"])
            pw.subtitle_length = data["subtitle_length"]
            pw.subtitle_size = int(data["subtitle_size"])
            pw.bar_length = int(data["bar_length"])
            pw.show_status = not bool(data["mini_mode"])
            pw.auto_hide_fullscreen = bool(data["auto_hide_fullscreen"])
            pw.locked = bool(self.settings.get("locked", True))
            pw.timer.setInterval(pw.tick_ms())
            pw._reconfigure_matrix()
            pw.walk_speed = float(data.get("behavior_walk_speed", pw.walk_speed))
            pw.plane.gravity = float(data.get("physic_gravity", pw.plane.gravity))
            multi_mon = bool(data.get("display_multi_monitors", True))
            pw.plane.set_world(get_world_areas(multi_mon))
            pw.apply_geometry()
            pw.update()
        if bool(data["autostart_with_codex"]) != old_autostart:
            if not set_autostart(bool(data["autostart_with_codex"])):
                QMessageBox.warning(
                    self,
                    "Claude Code 桌宠",
                    "随 Claude Code 启动设置写入失败，请检查系统权限。",
                )
        self.save_pet_state()
        self.refresh_status()

    @staticmethod
    def _cut(text, limit):
        text = " ".join(text.split())
        if len(text) <= limit:
            return text
        return text[: max(0, limit - 1)] + "…"

    @staticmethod
    def _format_elapsed(seconds):
        seconds = int(seconds)
        minutes, sec = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
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
            self._hide_all_to_tray()
        if os.path.exists(SHOW_FLAG):
            try:
                os.remove(SHOW_FLAG)
            except OSError:
                pass
            self._show_all_from_tray()
        if os.path.exists(SHUTDOWN_FLAG):
            try:
                os.remove(SHUTDOWN_FLAG)
            except OSError:
                pass
            app = QApplication.instance()
            if app is not None:
                app.quit()
            return
        status = codex_monitor.get_codex_status()
        self.status_active = bool(status.get("active"))
        level = SUBTITLE_LEVELS.get(
            self.subtitle_length, SUBTITLE_LEVELS["medium"]
        )
        if self.status_active:
            base = "运行中"
        else:
            base = "待机"
        parts = [base]
        if self.status_active:
            elapsed = status.get("elapsed")
            if elapsed is not None:
                parts.append(f"已运行 {self._format_elapsed(elapsed)}")
            tokens = status.get("tokens")
            if tokens is not None:
                parts.append(f"Token {self._format_tokens(tokens)}")
        task = status.get("task")
        if task:
            parts.append(self._cut(task, level["task_limit"]))
        if level["show_model"]:
            model = status.get("model")
            if model:
                parts.append(f"模型 {self._cut(model, 24)}")
        if level["show_progress"]:
            last_finished = status.get("last_finished")
            if last_finished:
                parts.append(f"上次完成 {last_finished}")
            progress = status.get("progress")
            if progress:
                parts.append(self._cut(progress, 80))
        self.status_text = " · ".join(parts)
        self.update()


if IS_WINDOWS:
    class HotkeyThread(QThread):
        triggered = Signal()

        def __init__(self):
            super().__init__()
            self._thread_id = None

        def run(self):
            self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
            user32 = ctypes.windll.user32
            user32.RegisterHotKey(None, HOTKEY_TRANSPARENT, MOD_CTRL_SHIFT, VK_T)
            msg = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_TRANSPARENT:
                    self.triggered.emit()
            user32.UnregisterHotKey(None, HOTKEY_TRANSPARENT)

        def stop(self):
            if self._thread_id:
                ctypes.windll.user32.PostThreadMessageW(
                    self._thread_id, 0x0012, 0, 0  # WM_QUIT
                )


def main():
    with open(PID_FILE, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
    atexit.register(remove_pid_file)
    remove_disabled_flag()
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    settings = load_settings()
    sound_fx = load_sound_effects()
    active = resolve_active_pets(settings)

    tray = setup_tray(active[0])

    hotkey_thread = None
    if IS_WINDOWS:
        hotkey_thread = HotkeyThread()
        hotkey_thread.triggered.connect(_toggle_transparent_all)
        hotkey_thread.start()

    for name in active:
        key = _next_instance_key(name)
        pw = PetWindow(name, settings, sound_fx, instance_key=key)
        pet_windows.append(pw)

    result = app.exec()
    if hotkey_thread:
        hotkey_thread.stop()
        hotkey_thread.wait(2000)
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.ctime()}\n")
            import traceback

            traceback.print_exc(file=f)
        raise

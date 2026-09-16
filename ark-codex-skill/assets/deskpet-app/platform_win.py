import ctypes
import ctypes.wintypes as wintypes
import os
import subprocess
import winreg

from PySide6.QtCore import Qt, QThread, Signal

from platform_base import PlatformHelper
from config import PYW_PATH, WATCHER_PATH

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "ClaudeCodeDeskpetWatcher"

WM_HOTKEY = 0x0312
HOTKEY_TRANSPARENT = 1
MOD_CTRL_SHIFT = 0x0002 | 0x0004
VK_T = 0x54

CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW


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


class WinHelper(PlatformHelper):
    def window_flags(self):
        return Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool

    def set_autostart(self, enabled):
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

    def set_click_through(self, widget, enabled):
        hwnd = int(widget.winId())
        user32 = ctypes.windll.user32
        GWL_EXSTYLE = -20
        WS_EX_TRANSPARENT = 0x00000020
        ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if enabled:
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style | WS_EX_TRANSPARENT)
        else:
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style & ~WS_EX_TRANSPARENT)

    def check_fullscreen(self):
        from PySide6.QtGui import QGuiApplication
        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.GetWindowRect.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.RECT),
        ]
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        screen = QGuiApplication.primaryScreen().geometry()
        return (
            rect.left <= screen.x()
            and rect.top <= screen.y()
            and rect.right >= screen.x() + screen.width()
            and rect.bottom >= screen.y() + screen.height()
        )

    def create_hotkey_thread(self, callback):
        thread = HotkeyThread()
        thread.triggered.connect(callback)
        return thread

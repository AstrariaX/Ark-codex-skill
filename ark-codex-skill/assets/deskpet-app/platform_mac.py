import os
import plistlib
import subprocess

from PySide6.QtCore import Qt

from platform_base import PlatformHelper


class MacHelper(PlatformHelper):
    def window_flags(self):
        return Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Window

    def set_autostart(self, enabled):
        plist_dir = os.path.expanduser("~/Library/LaunchAgents")
        plist_path = os.path.join(plist_dir, "com.deskpet.ark.plist")
        if enabled:
            os.makedirs(plist_dir, exist_ok=True)
            from config import PYW_PATH, BASE_DIR
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

    def check_fullscreen(self):
        try:
            result = subprocess.run(
                ['osascript', '-e',
                 'tell application "System Events" to get name of first application process whose frontmost is true'],
                capture_output=True, text=True, timeout=1)
            return False
        except Exception:
            return False

    def set_click_through(self, widget, enabled):
        widget.setAttribute(Qt.WA_TransparentForMouseEvents, enabled)

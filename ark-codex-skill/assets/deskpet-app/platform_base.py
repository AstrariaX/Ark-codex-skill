import sys


class PlatformHelper:
    def set_autostart(self, enabled):
        return False

    def autostart_enabled(self):
        return False

    def set_click_through(self, widget, enabled):
        pass

    def check_fullscreen(self):
        return False

    def create_hotkey_thread(self, callback):
        return None

    def window_flags(self):
        from PySide6.QtCore import Qt
        return Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool


def get_platform():
    if sys.platform == 'darwin':
        from platform_mac import MacHelper
        return MacHelper()
    from platform_win import WinHelper
    return WinHelper()

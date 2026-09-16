import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080


def _is_visible(hwnd):
    if not user32.IsWindowVisible(hwnd):
        return False
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    if rect.top == rect.bottom or rect.left == rect.right:
        return False
    return True


def _get_rect(hwnd):
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def _get_text(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    return buf.value


def enum_windows():
    results = []

    @WNDENUMPROC
    def callback(hwnd, _lparam):
        if user32.IsWindow(hwnd) and _is_visible(hwnd):
            ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if ex_style & WS_EX_TOOLWINDOW:
                return True
            left, top, right, bottom = _get_rect(hwnd)
            width = right - left
            height = bottom - top
            if width > 0 and height > 0:
                title = _get_text(hwnd)
                results.append((hwnd, title, left, top, right, bottom))
        return True

    user32.EnumWindows(callback, 0)
    return results


def find_barriers(pet_x, pet_width, pet_hwnd_title, screen_bottom):
    windows = enum_windows()
    barriers = []
    pet_left = pet_x
    pet_right = pet_x + pet_width
    for hwnd, title, left, top, right, bottom in windows:
        if title and pet_hwnd_title and title == pet_hwnd_title:
            continue
        wnd_width = right - left
        if left < pet_right and pet_left < right:
            screen_y = screen_bottom - top
            barriers.append((screen_y, left, wnd_width))
    return barriers

from PySide6.QtGui import QGuiApplication


def get_world_areas(multi_monitors=True):
    screens = QGuiApplication.screens()
    if not multi_monitors:
        screens = screens[:1]
    areas = []
    for scr in screens:
        geo = scr.availableGeometry()
        left = geo.x()
        right = geo.x() + geo.width()
        bottom_y = 0
        top_y = geo.y() + geo.height()
        areas.append((left, right, bottom_y, top_y))
    return areas


def get_max_screen_bottom():
    bottom = 0
    for scr in QGuiApplication.screens():
        geo = scr.availableGeometry()
        b = geo.y() + geo.height()
        if b > bottom:
            bottom = b
    return bottom

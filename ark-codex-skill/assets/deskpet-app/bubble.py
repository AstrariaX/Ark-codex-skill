from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QWidget

DEFAULT_LINES = [
    "今天也要加油哦",
    "……",
    "有点困了",
    "在看什么呢？",
    "要休息一下吗",
    "哼哼~",
    "博士，工作辛苦了",
    "别忘了喝水",
]


class BubbleWidget(QWidget):
    def __init__(self, parent_pet):
        super().__init__(None)
        self.setWindowFlags(
            Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._pet = parent_pet
        self._text = ""
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)
        self._font = QFont("Microsoft YaHei", 9)

    def show_text(self, text, duration_ms=3500):
        self._text = text
        fm = QFontMetrics(self._font)
        tw = fm.horizontalAdvance(text) + 24
        self.setFixedSize(max(tw, 60), 40)
        self._reposition()
        self.show()
        self.update()
        self._hide_timer.start(duration_ms)

    def _reposition(self):
        pet = self._pet
        cx = pet.x() + pet.width() // 2
        self.move(cx - self.width() // 2, pet.y() - self.height() - 2)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        tri_h = 6
        body = QRectF(0, 0, w, h - tri_h)
        p.setBrush(QColor(30, 30, 30, 210))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(body, 8, 8)
        tri = [
            QPointF(w / 2 - 5, h - tri_h),
            QPointF(w / 2 + 5, h - tri_h),
            QPointF(w / 2, h),
        ]
        p.drawPolygon(tri)
        p.setPen(QColor(255, 255, 255))
        p.setFont(self._font)
        p.drawText(body, Qt.AlignCenter, self._text)
        p.end()

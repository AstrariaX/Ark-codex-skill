from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from config import SPEED_OPTIONS, SUBTITLE_LEVELS


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Claude Code 桌宠设置")
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
            "随 Claude Code 启动（登录后监听，检测到 Claude Code 再启动桌宠）"
        )
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

        self.activation_slider = QSlider(Qt.Horizontal)
        self.activation_slider.setRange(0, 16)
        self.activation_slider.setValue(
            int(settings.get("behavior_ai_activation", 4))
        )
        self.activation_value = QLabel(str(self.activation_slider.value()))
        self.activation_slider.valueChanged.connect(
            lambda v: self.activation_value.setText(str(v))
        )
        act_row = QWidget()
        act_layout = QHBoxLayout(act_row)
        act_layout.setContentsMargins(0, 0, 0, 0)
        act_layout.addWidget(self.activation_slider, 1)
        act_layout.addWidget(self.activation_value)

        self.walk_speed_slider = QSlider(Qt.Horizontal)
        self.walk_speed_slider.setRange(20, 200)
        self.walk_speed_slider.setValue(
            int(settings.get("behavior_walk_speed", 60))
        )
        self.walk_speed_value = QLabel(str(self.walk_speed_slider.value()))
        self.walk_speed_slider.valueChanged.connect(
            lambda v: self.walk_speed_value.setText(str(v))
        )
        walk_row = QWidget()
        walk_layout = QHBoxLayout(walk_row)
        walk_layout.setContentsMargins(0, 0, 0, 0)
        walk_layout.addWidget(self.walk_speed_slider, 1)
        walk_layout.addWidget(self.walk_speed_value)

        self.gravity_slider = QSlider(Qt.Horizontal)
        self.gravity_slider.setRange(200, 2000)
        self.gravity_slider.setSingleStep(100)
        self.gravity_slider.setValue(
            int(settings.get("physic_gravity", 800))
        )
        self.gravity_value = QLabel(str(self.gravity_slider.value()))
        self.gravity_slider.valueChanged.connect(
            lambda v: self.gravity_value.setText(str(v))
        )
        grav_row = QWidget()
        grav_layout = QHBoxLayout(grav_row)
        grav_layout.setContentsMargins(0, 0, 0, 0)
        grav_layout.addWidget(self.gravity_slider, 1)
        grav_layout.addWidget(self.gravity_value)

        self.sound_check = QCheckBox("启用音效")
        self.sound_check.setChecked(bool(settings.get("sound_enabled", True)))
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(int(settings.get("sound_volume", 50)))
        self.volume_value = QLabel(f"{self.volume_slider.value()}%")
        self.volume_slider.valueChanged.connect(
            lambda v: self.volume_value.setText(f"{v}%")
        )
        vol_row = QWidget()
        vol_layout = QHBoxLayout(vol_row)
        vol_layout.setContentsMargins(0, 0, 0, 0)
        vol_layout.addWidget(self.volume_slider, 1)
        vol_layout.addWidget(self.volume_value)

        self.allow_sit_check = QCheckBox("允许坐下")
        self.allow_sit_check.setChecked(
            bool(settings.get("behavior_allow_sit", True))
        )
        self.allow_sleep_check = QCheckBox("允许睡觉")
        self.allow_sleep_check.setChecked(
            bool(settings.get("behavior_allow_sleep", True))
        )
        self.allow_walk_check = QCheckBox("允许行走")
        self.allow_walk_check.setChecked(
            bool(settings.get("behavior_allow_walk", True))
        )
        self.repulsion_check = QCheckBox("宠物间互斥")
        self.repulsion_check.setChecked(
            bool(settings.get("behavior_do_peer_repulsion", True))
        )
        self.multi_mon_check = QCheckBox("多显示器支持")
        self.multi_mon_check.setChecked(
            bool(settings.get("display_multi_monitors", True))
        )

        form.addRow("动作倍速", self.speed_combo)
        form.addRow("字幕长度", self.subtitle_combo)
        form.addRow("字幕大小", size_row)
        form.addRow("字条长度", bar_row)
        form.addRow("行为活跃度", act_row)
        form.addRow("行走速度", walk_row)
        form.addRow("重力加速度", grav_row)
        form.addRow("", self.sound_check)
        form.addRow("音量", vol_row)
        form.addRow("", self.allow_sit_check)
        form.addRow("", self.allow_sleep_check)
        form.addRow("", self.allow_walk_check)
        form.addRow("", self.repulsion_check)
        form.addRow("", self.multi_mon_check)
        form.addRow("", self.mini_check)
        form.addRow("", self.fullscreen_check)
        form.addRow("", self.autostart_check)
        self.doctor_name_edit = QLineEdit(settings.get("doctor_name", "博士"))
        self.doctor_name_edit.setPlaceholderText("博士")
        self.doctor_name_edit.setMaximumWidth(120)
        form.addRow("博士名称", self.doctor_name_edit)
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
            "subtitle_size": self.size_slider.value(),
            "bar_length": self.bar_slider.value(),
            "mini_mode": self.mini_check.isChecked(),
            "auto_hide_fullscreen": self.fullscreen_check.isChecked(),
            "autostart_with_codex": self.autostart_check.isChecked(),
            "behavior_ai_activation": self.activation_slider.value(),
            "behavior_allow_sit": self.allow_sit_check.isChecked(),
            "behavior_allow_sleep": self.allow_sleep_check.isChecked(),
            "behavior_allow_walk": self.allow_walk_check.isChecked(),
            "behavior_walk_speed": self.walk_speed_slider.value(),
            "physic_gravity": self.gravity_slider.value(),
            "sound_enabled": self.sound_check.isChecked(),
            "sound_volume": self.volume_slider.value(),
            "behavior_do_peer_repulsion": self.repulsion_check.isChecked(),
            "display_multi_monitors": self.multi_mon_check.isChecked(),
            "doctor_name": self.doctor_name_edit.text().strip() or "博士",
        }

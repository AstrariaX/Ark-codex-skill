import os
import subprocess
import sys

from PySide6.QtCore import QThread, Signal

from config import SKILL_SCRIPTS, PYTHON_PATH, WEBM_DIR, PETS_DIR


class FetchWorker(QThread):
    progress = Signal(str)
    finished = Signal(str, bool)

    def __init__(self, operator, skin=None, group=None):
        super().__init__()
        self.operator = operator
        self.skin = skin
        self.group = group or "基建"
        self.pet_name = f"{operator}-{skin}" if skin else operator

    def run(self):
        export_script = os.path.join(SKILL_SCRIPTS, "prts_export.py")
        process_script = os.path.join(SKILL_SCRIPTS, "process_webm.py")
        if not os.path.isfile(export_script):
            self.finished.emit("skill 脚本未找到", False)
            return
        self.progress.emit(f"正在导出 {self.pet_name} ({self.group}) ...")
        cmd = [PYTHON_PATH, export_script, self.operator, "--out", WEBM_DIR,
               "--group", self.group]
        if self.skin:
            cmd += ["--skin", self.skin]
        creation_flags = 0
        if sys.platform == 'win32':
            creation_flags = subprocess.CREATE_NO_WINDOW
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=300,
                           creationflags=creation_flags)
        except Exception as e:
            self.finished.emit(f"导出失败: {e}", False)
            return
        self.progress.emit(f"正在转换 {self.pet_name} 帧...")
        filter_name = f"{self.operator}-{self.skin}" if self.skin else self.operator
        pet_dir = os.path.join(PETS_DIR, self.pet_name)
        cmd2 = [
            PYTHON_PATH, process_script,
            "--src", WEBM_DIR, "--name", filter_name, "--out", pet_dir,
            "--group", self.group,
        ]
        try:
            subprocess.run(cmd2, check=True, capture_output=True, timeout=300,
                           creationflags=creation_flags)
        except Exception as e:
            self.finished.emit(f"转换失败: {e}", False)
            return
        self.finished.emit(f"{self.pet_name} 已入库", True)

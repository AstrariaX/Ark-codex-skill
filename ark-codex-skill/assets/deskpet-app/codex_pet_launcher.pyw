import ctypes
import os
import subprocess
import time
from ctypes import wintypes

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PYW_PATH = os.path.join(BASE_DIR, ".venv", "Scripts", "pythonw.exe")
MAIN_PATH = os.path.join(BASE_DIR, "main.py")
TRAY_PATH = os.path.join(BASE_DIR, "codex_tray.pyw")
PID_FILE = os.path.join(BASE_DIR, "pet.pid")
WATCHER_PID_FILE = os.path.join(BASE_DIR, "watcher.pid")
TRAY_PID_FILE = os.path.join(BASE_DIR, "tray.pid")
SHUTDOWN_FLAG = os.path.join(BASE_DIR, "pet_shutdown.flag")
DISABLED_FLAG = os.path.join(BASE_DIR, "pet_disabled.flag")
TRAY_STOP_FLAG = os.path.join(BASE_DIR, "tray_stop.flag")
WATCHER_EXIT_FLAG = os.path.join(BASE_DIR, "watcher_exit.flag")
POLL_SECONDS = 3
HOST_NAMES = {"chatgpt.exe", "codex.exe", "claude.exe"}

TH32CS_SNAPPROCESS = 0x00000002
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_TERMINATE = 0x0001

kernel32 = ctypes.windll.kernel32


class ProcessEntry32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


def process_names():
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == wintypes.HANDLE(-1).value:
        return []
    names = []
    entry = ProcessEntry32W()
    entry.dwSize = ctypes.sizeof(ProcessEntry32W)
    ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
    while ok:
        names.append(entry.szExeFile.lower())
        ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    kernel32.CloseHandle(snapshot)
    return names


def pid_alive(pid):
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    ]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    kernel32.CloseHandle(handle)
    return True


def read_pid(path):
    try:
        with open(path, encoding="utf-8") as f:
            return int(f.read().strip())
    except Exception:
        return None


def pet_running():
    pid = read_pid(PID_FILE)
    return pid is not None and pid_alive(pid)


def tray_running():
    pid = read_pid(TRAY_PID_FILE)
    return pid is not None and pid_alive(pid)


def launch(path, args):
    subprocess.Popen(
        [path] + args,
        cwd=BASE_DIR,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def launch_pet():
    launch(PYW_PATH, [MAIN_PATH])


def start_tray():
    if not tray_running():
        launch(PYW_PATH, [TRAY_PATH])


def write_flag(path):
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("1")
    except OSError:
        pass


def remove_flag(path):
    try:
        os.remove(path)
    except OSError:
        pass


def terminate_pid(pid):
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    ]
    kernel32.TerminateProcess.restype = wintypes.BOOL
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
    if handle:
        kernel32.TerminateProcess(handle, 0)
        kernel32.CloseHandle(handle)


def close_pet():
    if not pet_running():
        return True
    write_flag(SHUTDOWN_FLAG)
    deadline = time.time() + 6
    while time.time() < deadline:
        if not pet_running():
            return True
        time.sleep(0.3)
    pid = read_pid(PID_FILE)
    if pid is not None:
        terminate_pid(pid)
    return not pet_running()


def stop_tray():
    if not tray_running():
        return True
    write_flag(TRAY_STOP_FLAG)
    deadline = time.time() + 4
    while time.time() < deadline:
        if not tray_running():
            return True
        time.sleep(0.2)
    pid = read_pid(TRAY_PID_FILE)
    if pid is not None:
        terminate_pid(pid)
    return not tray_running()


def host_running():
    names = set(process_names())
    return bool(names & HOST_NAMES)


def disabled():
    return os.path.exists(DISABLED_FLAG)


def watcher_already_running():
    pid = read_pid(WATCHER_PID_FILE)
    return pid is not None and pid_alive(pid)


def main():
    if watcher_already_running():
        return
    with open(WATCHER_PID_FILE, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
    was_host = False
    try:
        while True:
            if os.path.exists(WATCHER_EXIT_FLAG):
                remove_flag(WATCHER_EXIT_FLAG)
                close_pet()
                stop_tray()
                break
            host = host_running()
            if host:
                if not was_host:
                    remove_flag(DISABLED_FLAG)
                if not tray_running():
                    start_tray()
                if not pet_running() and not disabled():
                    launch_pet()
            else:
                if pet_running():
                    close_pet()
                if tray_running():
                    stop_tray()
            was_host = host
            time.sleep(POLL_SECONDS)
    finally:
        remove_flag(WATCHER_PID_FILE)


if __name__ == "__main__":
    main()

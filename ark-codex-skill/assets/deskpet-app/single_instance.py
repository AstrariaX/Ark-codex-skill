"""Windows named mutex: one pet per installation, automatically released on exit."""
import ctypes
import hashlib
import os
from ctypes import wintypes


class InstanceLock:
    def __init__(self, directory):
        canonical = os.path.normcase(os.path.realpath(directory))
        digest = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
        self.name = 'Local\\ArkDeskpet-' + digest
        self.handle = None
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        self.api.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        self.api.CreateMutexW.restype = wintypes.HANDLE
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.api.CloseHandle.restype = wintypes.BOOL

    def acquire(self):
        if self.handle is not None:
            return True
        ctypes.set_last_error(0)
        handle = self.api.CreateMutexW(None, False, self.name)
        error = ctypes.get_last_error()
        if not handle:
            raise ctypes.WinError(error)
        if error == 183:  # ERROR_ALREADY_EXISTS
            self.api.CloseHandle(handle)
            return False
        self.handle = handle
        return True

    def close(self):
        if self.handle is not None:
            self.api.CloseHandle(self.handle)
            self.handle = None

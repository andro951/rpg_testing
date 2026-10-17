"""Read-only Windows process liveness without os.kill(pid, 0)."""
import ctypes
from ctypes import wintypes
api=ctypes.WinDLL('kernel32',use_last_error=True)
api.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];api.OpenProcess.restype=wintypes.HANDLE
api.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)];api.GetExitCodeProcess.restype=wintypes.BOOL
api.CloseHandle.argtypes=[wintypes.HANDLE];api.CloseHandle.restype=wintypes.BOOL
def is_running(pid):
 if type(pid)is not int or pid<=0:raise ValueError('A positive process ID is required')
 handle=api.OpenProcess(0x1000,False,pid)
 if not handle:
  error=ctypes.get_last_error()
  if error in(87,1168):return False
  raise ctypes.WinError(error)
 try:
  code=wintypes.DWORD()
  if not api.GetExitCodeProcess(handle,ctypes.byref(code)):raise ctypes.WinError(ctypes.get_last_error())
  return code.value==259
 finally:api.CloseHandle(handle)

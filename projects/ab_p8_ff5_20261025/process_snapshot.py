import ctypes,json,os
from ctypes import wintypes
class ENTRY(ctypes.Structure):
    _fields_=[('dwSize',wintypes.DWORD),('cntUsage',wintypes.DWORD),('th32ProcessID',wintypes.DWORD),('th32DefaultHeapID',ctypes.c_size_t),('th32ModuleID',wintypes.DWORD),('cntThreads',wintypes.DWORD),('th32ParentProcessID',wintypes.DWORD),('pcPriClassBase',wintypes.LONG),('dwFlags',wintypes.DWORD),('szExeFile',wintypes.WCHAR*260)]
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.CreateToolhelp32Snapshot.restype=wintypes.HANDLE
k.Process32FirstW.argtypes=[wintypes.HANDLE,ctypes.POINTER(ENTRY)]
k.Process32NextW.argtypes=[wintypes.HANDLE,ctypes.POINTER(ENTRY)]
k.CloseHandle.argtypes=[wintypes.HANDLE]
def snapshot():
    handle=k.CreateToolhelp32Snapshot(2,0)
    assert handle!=ctypes.c_void_p(-1).value
    e=ENTRY();e.dwSize=ctypes.sizeof(e);rows=[]
    try:
        ok=k.Process32FirstW(handle,ctypes.byref(e))
        while ok:
            rows.append({'pid':int(e.th32ProcessID),'ppid':int(e.th32ParentProcessID),'name':e.szExeFile})
            ok=k.Process32NextW(handle,ctypes.byref(e))
    finally:k.CloseHandle(handle)
    return rows
if __name__=='__main__':
    print(json.dumps([x for x in snapshot() if x['name'].lower() in ('python.exe','vvp.exe','pds_shell.exe')],indent=2))

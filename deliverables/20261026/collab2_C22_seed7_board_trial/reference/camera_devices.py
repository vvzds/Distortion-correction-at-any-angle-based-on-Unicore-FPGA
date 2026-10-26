"""Enumerate DirectShow video inputs by name; no capture or settings changes."""
import ctypes as C
import json
import uuid


class GUID(C.Structure):
    _fields_ = [('raw', C.c_ubyte * 16)]

    def __init__(self, value):
        super().__init__()
        self.raw[:] = uuid.UUID(value).bytes_le


class VariantValue(C.Union):
    _fields_ = [('bstr', C.c_void_p), ('storage', C.c_ubyte * (16 if C.sizeof(C.c_void_p) == 8 else 8))]


class VARIANT(C.Structure):
    _fields_ = [('vt', C.c_ushort), ('r1', C.c_ushort), ('r2', C.c_ushort),
                ('r3', C.c_ushort), ('value', VariantValue)]


def method(ptr, index, restype, *args):
    vtable = C.cast(ptr, C.POINTER(C.POINTER(C.c_void_p))).contents
    return C.WINFUNCTYPE(restype, C.c_void_p, *args)(vtable[index])


def release(ptr):
    if ptr.value:
        method(ptr, 2, C.c_ulong)(ptr)


def enumerate_cameras():
    ole = C.OleDLL('ole32')
    aut = C.OleDLL('oleaut32')
    initialized = False
    creator, enum = C.c_void_p(), C.c_void_p()
    try:
        ole.CoInitialize(None)
        initialized = True
        ole.CoCreateInstance(C.byref(GUID('62BE5D10-60EB-11D0-BD3B-00A0C911CE86')),
                             None, 1, C.byref(GUID('29840822-5B84-11D0-BD3B-00A0C911CE86')),
                             C.byref(creator))
        code = method(creator, 3, C.c_long, C.POINTER(GUID), C.POINTER(C.c_void_p), C.c_ulong)(
            creator, C.byref(GUID('860BB310-5D01-11D0-BD3B-00A0C911CE86')), C.byref(enum), 0)
        if code == 1:
            return []
        if code < 0:
            raise RuntimeError('CreateClassEnumerator HRESULT=%08X' % (code & 0xffffffff))
        rows = []
        while True:
            moniker, bag = C.c_void_p(), C.c_void_p()
            fetched = C.c_ulong()
            code = method(enum, 3, C.c_long, C.c_ulong, C.POINTER(C.c_void_p), C.POINTER(C.c_ulong))(
                enum, 1, C.byref(moniker), C.byref(fetched))
            if code == 1:
                break
            if code < 0:
                raise RuntimeError('Enumerator Next failed')
            row = dict(index=len(rows))
            try:
                code = method(moniker, 9, C.c_long, C.c_void_p, C.c_void_p, C.POINTER(GUID), C.POINTER(C.c_void_p))(
                    moniker, None, None, C.byref(GUID('55272A00-42CB-11CE-8135-00AA004BB851')), C.byref(bag))
                if code < 0:
                    raise RuntimeError('BindToStorage failed')
                for key in ('FriendlyName', 'DevicePath'):
                    value = VARIANT()
                    try:
                        code = method(bag, 3, C.c_long, C.c_wchar_p, C.POINTER(VARIANT), C.c_void_p)(
                            bag, key, C.byref(value), None)
                        if code >= 0 and value.vt == 8:
                            row[key] = C.wstring_at(value.value.bstr)
                    finally:
                        aut.VariantClear(C.byref(value))
                rows.append(row)
            finally:
                release(bag)
                release(moniker)
        return rows
    finally:
        release(enum)
        release(creator)
        if initialized:
            ole.CoUninitialize()


if __name__ == '__main__':
    print(json.dumps(enumerate_cameras(), ensure_ascii=False, indent=2))

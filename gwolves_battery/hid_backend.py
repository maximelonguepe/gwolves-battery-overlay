"""Native Windows HID access through ctypes (hid.dll + setupapi.dll).

No external dependencies: no hidapi, no pywin32, no compiler.
"""
import ctypes as C
from ctypes import wintypes

if C.sizeof(C.c_void_p) not in (4, 8):  # pragma: no cover
    raise RuntimeError("Unsupported architecture")

setupapi = C.WinDLL("setupapi")
hid = C.WinDLL("hid")
kernel32 = C.WinDLL("kernel32")

DIGCF_PRESENT = 0x02
DIGCF_DEVICEINTERFACE = 0x10
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = C.c_void_p(-1).value


class GUID(C.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", wintypes.BYTE * 8)]


class SP_DEVICE_INTERFACE_DATA(C.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("InterfaceClassGuid", GUID),
                ("Flags", wintypes.DWORD), ("Reserved", C.POINTER(C.c_ulong))]


class SP_DEVICE_INTERFACE_DETAIL_DATA_W(C.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("DevicePath", C.c_wchar * 1024)]


class HIDD_ATTRIBUTES(C.Structure):
    _fields_ = [("Size", C.c_ulong), ("VendorID", C.c_ushort),
                ("ProductID", C.c_ushort), ("VersionNumber", C.c_ushort)]


class HIDP_CAPS(C.Structure):
    _fields_ = [("Usage", C.c_ushort), ("UsagePage", C.c_ushort),
                ("InputReportByteLength", C.c_ushort),
                ("OutputReportByteLength", C.c_ushort),
                ("FeatureReportByteLength", C.c_ushort),
                ("Reserved", C.c_ushort * 17),
                ("NumberLinkCollectionNodes", C.c_ushort),
                ("NumberInputButtonCaps", C.c_ushort),
                ("NumberInputValueCaps", C.c_ushort),
                ("NumberInputDataIndices", C.c_ushort),
                ("NumberOutputButtonCaps", C.c_ushort),
                ("NumberOutputValueCaps", C.c_ushort),
                ("NumberOutputDataIndices", C.c_ushort),
                ("NumberFeatureButtonCaps", C.c_ushort),
                ("NumberFeatureValueCaps", C.c_ushort),
                ("NumberFeatureDataIndices", C.c_ushort)]


hid.HidD_GetHidGuid.argtypes = [C.POINTER(GUID)]
hid.HidD_GetAttributes.argtypes = [wintypes.HANDLE, C.POINTER(HIDD_ATTRIBUTES)]
hid.HidD_GetAttributes.restype = wintypes.BOOLEAN
hid.HidD_GetPreparsedData.argtypes = [wintypes.HANDLE, C.POINTER(C.c_void_p)]
hid.HidD_GetPreparsedData.restype = wintypes.BOOLEAN
hid.HidD_FreePreparsedData.argtypes = [C.c_void_p]
hid.HidP_GetCaps.argtypes = [C.c_void_p, C.POINTER(HIDP_CAPS)]
hid.HidD_SetFeature.argtypes = [wintypes.HANDLE, C.c_void_p, C.c_ulong]
hid.HidD_SetFeature.restype = wintypes.BOOLEAN
hid.HidD_GetFeature.argtypes = [wintypes.HANDLE, C.c_void_p, C.c_ulong]
hid.HidD_GetFeature.restype = wintypes.BOOLEAN
hid.HidD_GetProductString.argtypes = [wintypes.HANDLE, C.c_void_p, C.c_ulong]
hid.HidD_GetProductString.restype = wintypes.BOOLEAN
hid.HidD_GetManufacturerString.argtypes = [wintypes.HANDLE, C.c_void_p, C.c_ulong]
hid.HidD_GetManufacturerString.restype = wintypes.BOOLEAN

kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                 C.c_void_p, wintypes.DWORD, wintypes.DWORD,
                                 wintypes.HANDLE]
kernel32.CreateFileW.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

FILE_FLAG_OVERLAPPED = 0x40000000
ERROR_IO_PENDING = 997
WAIT_OBJECT_0 = 0


class OVERLAPPED(C.Structure):
    _fields_ = [("Internal", C.c_void_p), ("InternalHigh", C.c_void_p),
                ("Offset", wintypes.DWORD), ("OffsetHigh", wintypes.DWORD),
                ("hEvent", wintypes.HANDLE)]


kernel32.CreateEventW.argtypes = [C.c_void_p, wintypes.BOOL, wintypes.BOOL,
                                  wintypes.LPCWSTR]
kernel32.CreateEventW.restype = wintypes.HANDLE
kernel32.WriteFile.argtypes = [wintypes.HANDLE, C.c_void_p, wintypes.DWORD,
                               C.POINTER(wintypes.DWORD), C.c_void_p]
kernel32.WriteFile.restype = wintypes.BOOL
kernel32.ReadFile.argtypes = [wintypes.HANDLE, C.c_void_p, wintypes.DWORD,
                              C.POINTER(wintypes.DWORD), C.c_void_p]
kernel32.ReadFile.restype = wintypes.BOOL
kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.WaitForSingleObject.restype = wintypes.DWORD
kernel32.CancelIo.argtypes = [wintypes.HANDLE]
kernel32.ResetEvent.argtypes = [wintypes.HANDLE]
kernel32.ResetEvent.restype = wintypes.BOOL
kernel32.GetOverlappedResult.argtypes = [wintypes.HANDLE, C.c_void_p,
                                         C.POINTER(wintypes.DWORD),
                                         wintypes.BOOL]
kernel32.GetOverlappedResult.restype = wintypes.BOOL

# Without an explicit restype, ctypes truncates the 64-bit handle to a signed
# 32-bit int and enumeration silently returns no devices.
setupapi.SetupDiGetClassDevsW.argtypes = [C.POINTER(GUID), wintypes.LPCWSTR,
                                          wintypes.HWND, wintypes.DWORD]
setupapi.SetupDiGetClassDevsW.restype = wintypes.HANDLE
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [
    wintypes.HANDLE, C.c_void_p, C.POINTER(GUID), wintypes.DWORD,
    C.POINTER(SP_DEVICE_INTERFACE_DATA)]
setupapi.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [
    wintypes.HANDLE, C.POINTER(SP_DEVICE_INTERFACE_DATA), C.c_void_p,
    wintypes.DWORD, C.POINTER(wintypes.DWORD), C.c_void_p]
setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [wintypes.HANDLE]
setupapi.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL


class DeviceInfo(object):
    __slots__ = ("path", "vendor_id", "product_id", "usage_page", "usage",
                 "feature_length", "input_length", "output_length",
                 "product", "manufacturer")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    def __repr__(self):
        return "<DeviceInfo %04X:%04X usage=%04X:%04X feature=%d %r>" % (
            self.vendor_id, self.product_id, self.usage_page, self.usage,
            self.feature_length or 0, self.product)


def _interface_paths():
    guid = GUID()
    hid.HidD_GetHidGuid(C.byref(guid))
    hdev = setupapi.SetupDiGetClassDevsW(C.byref(guid), None, None,
                                         DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    paths, idx = [], 0
    while True:
        did = SP_DEVICE_INTERFACE_DATA()
        did.cbSize = C.sizeof(SP_DEVICE_INTERFACE_DATA)
        if not setupapi.SetupDiEnumDeviceInterfaces(hdev, None, C.byref(guid),
                                                    idx, C.byref(did)):
            break
        detail = SP_DEVICE_INTERFACE_DETAIL_DATA_W()
        detail.cbSize = 8 if C.sizeof(C.c_void_p) == 8 else 6
        needed = wintypes.DWORD()
        setupapi.SetupDiGetDeviceInterfaceDetailW(
            hdev, C.byref(did), C.byref(detail), C.sizeof(detail),
            C.byref(needed), None)
        if detail.DevicePath:
            paths.append(detail.DevicePath)
        idx += 1
    setupapi.SetupDiDestroyDeviceInfoList(hdev)
    return paths


def _open_handle(path, overlapped=False):
    """Windows denies GENERIC_READ|WRITE on mouse/keyboard collections;
    zero access is enough for HidD_GetFeature / HidD_SetFeature.

    `overlapped` is required to read input reports with a timeout, and needs
    real read/write access, so no zero-access fallback applies there.
    """
    flags = FILE_FLAG_OVERLAPPED if overlapped else 0
    accesses = (GENERIC_READ | GENERIC_WRITE,) if overlapped \
        else (GENERIC_READ | GENERIC_WRITE, 0)
    for access in accesses:
        handle = kernel32.CreateFileW(path, access,
                                      FILE_SHARE_READ | FILE_SHARE_WRITE, None,
                                      OPEN_EXISTING, flags, None)
        if handle and handle != INVALID_HANDLE_VALUE:
            return handle
    return None


def _describe(handle, path):
    attrs = HIDD_ATTRIBUTES()
    attrs.Size = C.sizeof(HIDD_ATTRIBUTES)
    if not hid.HidD_GetAttributes(handle, C.byref(attrs)):
        return None
    preparsed = C.c_void_p()
    caps = HIDP_CAPS()
    if hid.HidD_GetPreparsedData(handle, C.byref(preparsed)):
        hid.HidP_GetCaps(preparsed, C.byref(caps))
        hid.HidD_FreePreparsedData(preparsed)
    product = C.create_unicode_buffer(256)
    hid.HidD_GetProductString(handle, product, 512)
    maker = C.create_unicode_buffer(256)
    hid.HidD_GetManufacturerString(handle, maker, 512)
    return DeviceInfo(path=path, vendor_id=attrs.VendorID,
                      product_id=attrs.ProductID, usage_page=caps.UsagePage,
                      usage=caps.Usage,
                      feature_length=caps.FeatureReportByteLength,
                      input_length=caps.InputReportByteLength,
                      output_length=caps.OutputReportByteLength,
                      product=product.value, manufacturer=maker.value)


def enumerate_devices(vendor_id=None, product_id=None):
    """List present HID interfaces, filtered when vid/pid are given."""
    found = []
    for path in _interface_paths():
        handle = _open_handle(path)
        if not handle:
            continue
        try:
            info = _describe(handle, path)
        finally:
            kernel32.CloseHandle(handle)
        if info is None:
            continue
        if vendor_id is not None and info.vendor_id != vendor_id:
            continue
        if product_id is not None and info.product_id != product_id:
            continue
        found.append(info)
    return found


def find_control_interface(vendor_id, product_id, feature_length):
    """Vendor interface exposing a feature report of at least `feature_length`."""
    for info in enumerate_devices(vendor_id, product_id):
        if (info.feature_length or 0) >= feature_length:
            return info
    return None


def find_io_interface(vendor_id, product_id, report_length):
    """Vendor interface exchanging input/output reports of `report_length`.

    Used by devices that talk over interrupt reports instead of feature
    reports. Vendor usage pages start at 0xFF00.
    """
    for info in enumerate_devices(vendor_id, product_id):
        if (info.input_length == report_length
                and info.output_length == report_length
                and (info.usage_page or 0) >= 0xFF00):
            return info
    return None


class HidDevice(object):
    """Context manager around a HID handle.

    Pass `overlapped=True` to exchange input/output reports; the default
    suffices for feature reports.
    """

    def __init__(self, path, overlapped=False):
        self.path = path
        self.overlapped = overlapped
        self._handle = None
        self._event = None
        # Holds the buffer and OVERLAPPED of a read still owned by the kernel.
        self._pending = None

    def __enter__(self):
        self._handle = _open_handle(self.path, self.overlapped)
        if not self._handle:
            raise OSError("Cannot open device: %s" % self.path)
        if self.overlapped:
            self._event = kernel32.CreateEventW(None, True, False, None)
        return self

    def __exit__(self, *exc):
        if self._handle:
            self._drop_pending()
            kernel32.CloseHandle(self._handle)
            self._handle = None
        if self._event:
            kernel32.CloseHandle(self._event)
            self._event = None
        return False

    def _drop_pending(self):
        """Cancel an outstanding read and wait for the kernel to be done.

        CancelIo only *requests* cancellation. Releasing the buffer before the
        operation has actually finished lets the kernel write into freed
        memory, which crashes the process.
        """
        if self._pending is None:
            return
        kernel32.CancelIo(self._handle)
        read = wintypes.DWORD(0)
        kernel32.GetOverlappedResult(self._handle,
                                     C.byref(self._pending["ov"]),
                                     C.byref(read), True)
        self._pending = None

    def write_output(self, data, timeout_ms=1000):
        """Send an output report. `data` starts with the report ID."""
        buf = C.create_string_buffer(bytes(data), len(data))
        ov = OVERLAPPED()
        ov.hEvent = kernel32.CreateEventW(None, True, False, None)
        try:
            ok = kernel32.WriteFile(self._handle, buf, len(data), None,
                                    C.byref(ov))
            if not ok and kernel32.GetLastError() != ERROR_IO_PENDING:
                return False
            return kernel32.WaitForSingleObject(ov.hEvent,
                                                timeout_ms) == WAIT_OBJECT_0
        finally:
            kernel32.CloseHandle(ov.hEvent)

    def begin_read(self, length):
        """Arm a read before writing, so a fast reply cannot be missed.

        The buffer is kept on the instance, not returned, so it cannot be
        collected while the kernel still owns it.
        """
        self._drop_pending()
        pending = {"buf": C.create_string_buffer(length),
                   "ov": OVERLAPPED(), "len": length}
        kernel32.ResetEvent(self._event)
        pending["ov"].hEvent = self._event
        ok = kernel32.ReadFile(self._handle, pending["buf"], length, None,
                               C.byref(pending["ov"]))
        if not ok and kernel32.GetLastError() != ERROR_IO_PENDING:
            return False
        self._pending = pending
        return True

    def finish_read(self, timeout_ms=200):
        """Wait for the armed read. Returns the report, or None on timeout.

        On timeout the read stays armed, so calling again simply keeps
        waiting; the buffer remains owned by the instance throughout.
        """
        if self._pending is None:
            return None
        if kernel32.WaitForSingleObject(self._event,
                                        timeout_ms) != WAIT_OBJECT_0:
            return None
        read = wintypes.DWORD(0)
        pending, self._pending = self._pending, None
        if not kernel32.GetOverlappedResult(self._handle,
                                            C.byref(pending["ov"]),
                                            C.byref(read), False):
            return None
        return bytearray(pending["buf"].raw[:read.value])

    def set_feature(self, data):
        buf = C.create_string_buffer(bytes(data), len(data))
        return bool(hid.HidD_SetFeature(self._handle, buf, len(data)))

    def get_feature(self, length, report_id=0):
        buf = C.create_string_buffer(length)
        buf[0] = bytes([report_id])
        if not hid.HidD_GetFeature(self._handle, buf, length):
            return None
        return bytearray(buf.raw[:length])

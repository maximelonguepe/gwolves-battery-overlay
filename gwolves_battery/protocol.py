"""Battery protocols of the mouse.xyz web driver.

Reconstructed from the public JavaScript bundle served by https://mouse.xyz.
See docs/PROTOCOL.md for the full write-up.

Two unrelated families are in use, and a device speaks exactly one of them:

`feature` — 64-byte payload carried in a 65-byte feature report.
    Request  : payload[2] = device_id, payload[3] = 2, payload[5] = 0x83
    Response : raw[1] = 0xA1, raw[6] = 0x83, raw[7] = charging, raw[8] = percent

`compx` — 16-byte payload carried in interrupt reports under report ID 8,
    with a checksum in the last byte. The reply arrives as an input report
    rather than as the answer to a read.
    Request  : payload[0] = 0x04, payload[15] = checksum
    Response : data[0] = 0x04, data[5] = percent, data[6] = charging,
               data[7..8] = battery voltage in mV (big endian)

Both command bytes are reads. No write command is ever issued.
"""
import time

from .hid_backend import (HidDevice, find_control_interface,
                          find_io_interface)

# -- feature family -------------------------------------------------------

CMD_GET_BATTERY = 0x83
RESPONSE_HEADER = 0xA1
PAYLOAD_SIZE = 64

# -- compx family ---------------------------------------------------------

COMPX_REPORT_ID = 8
COMPX_REPORT_LENGTH = 17
COMPX_PAYLOAD_SIZE = 16
COMPX_CMD_BATTERY = 0x04

PROTOCOLS = ("feature", "compx")


class BatteryStatus(object):
    __slots__ = ("percent", "charging", "voltage_mv")

    def __init__(self, percent, charging, voltage_mv=None):
        self.percent = percent
        self.charging = charging
        self.voltage_mv = voltage_mv

    def __repr__(self):
        return "BatteryStatus(percent=%r, charging=%r, voltage_mv=%r)" % (
            self.percent, self.charging, self.voltage_mv)


# ------------------------------------------------------------- feature

def build_request(device_id, feature_length):
    """Build the full feature buffer (report ID + payload)."""
    payload = bytearray(PAYLOAD_SIZE)
    payload[2] = device_id
    payload[3] = 2
    payload[5] = CMD_GET_BATTERY
    buf = bytearray(feature_length)
    buf[0] = 0  # report ID
    buf[1:1 + PAYLOAD_SIZE] = payload
    return buf


def parse_response(raw):
    """Parse a feature-family reply. Returns BatteryStatus or None."""
    if raw is None or len(raw) < 9:
        return None
    if raw[1] != RESPONSE_HEADER or raw[6] != CMD_GET_BATTERY:
        return None
    percent = raw[8]
    if not 0 <= percent <= 100:
        return None
    return BatteryStatus(percent, bool(raw[7]))


def _read_feature(cfg, info, want_raw=False):
    dev, poll = cfg["device"], cfg["polling"]
    flen = int(dev["feature_report_length"])
    length = min(flen, info.feature_length or flen)
    request = build_request(int(dev["device_id"]), length)
    delay = max(0.0, float(poll["response_delay_ms"]) / 1000.0)
    try:
        with HidDevice(info.path) as handle:
            for _ in range(max(1, int(poll["retries"]))):
                if not handle.set_feature(request):
                    time.sleep(0.05)
                    continue
                time.sleep(delay)
                raw = handle.get_feature(length)
                if raw is not None and raw[1] == RESPONSE_HEADER:
                    return raw if want_raw else parse_response(raw)
                time.sleep(0.05)
    except OSError:
        return None
    return None


# --------------------------------------------------------------- compx

def compx_checksum(payload):
    """Last byte of a compx frame.

    The driver computes `85 - sum(payload[0:15])` then subtracts the report
    ID before storing it, and the store truncates to 8 bits.
    """
    return (85 - (sum(payload[:15]) & 0xFF) - COMPX_REPORT_ID) & 0xFF


def compx_build(command):
    """Build the full compx buffer (report ID + 16-byte payload)."""
    payload = bytearray(COMPX_PAYLOAD_SIZE)
    payload[0] = command
    payload[15] = compx_checksum(payload)
    buf = bytearray(COMPX_REPORT_LENGTH)
    buf[0] = COMPX_REPORT_ID
    buf[1:1 + COMPX_PAYLOAD_SIZE] = payload
    return buf


def compx_parse(raw):
    """Parse a compx reply. Returns BatteryStatus or None.

    `raw` keeps the report ID at offset 0, so the driver's `data[i]` is our
    `raw[i + 1]`.
    """
    if raw is None or len(raw) < 10:
        return None
    if raw[1] != COMPX_CMD_BATTERY:
        return None
    percent = raw[6]
    if not 0 <= percent <= 100:
        return None
    voltage = (raw[8] << 8) | raw[9]
    return BatteryStatus(percent, bool(raw[7]), voltage or None)


def _read_compx(cfg, info, want_raw=False):
    poll = cfg["polling"]
    request = compx_build(COMPX_CMD_BATTERY)
    deadline_ms = max(200, int(poll["response_delay_ms"]) * 8)
    try:
        with HidDevice(info.path, overlapped=True) as handle:
            for _ in range(max(1, int(poll["retries"]))):
                # Arm the read first: the reply can land before write returns.
                pending = handle.begin_read(COMPX_REPORT_LENGTH)
                if pending is None:
                    return None
                if not handle.write_output(request):
                    return None
                waited = 0
                while waited < deadline_ms:
                    raw = handle.finish_read(pending, 50)
                    waited += 50
                    if raw is None:
                        continue
                    if len(raw) >= 2 and raw[1] == COMPX_CMD_BATTERY:
                        return raw if want_raw else compx_parse(raw)
                    # Unrelated traffic on this interface: keep listening.
                    pending = handle.begin_read(COMPX_REPORT_LENGTH)
                    if pending is None:
                        break
    except OSError:
        return None
    return None


# ------------------------------------------------------------ dispatch

def find_device(cfg):
    """Locate the control interface and the protocol it speaks.

    Returns (DeviceInfo, protocol_name) or (None, None). Every configured
    product ID is tried, since a mouse changes ID when plugged in.
    """
    from .config import as_int, as_int_list

    dev = cfg["device"]
    vid = as_int(dev["vendor_id"])
    flen = int(dev["feature_report_length"])
    wanted = str(dev.get("protocol", "auto")).lower()

    for pid in as_int_list(dev["product_id"]):
        if wanted in ("auto", "feature"):
            info = find_control_interface(vid, pid, flen)
            if info is not None:
                return info, "feature"
        if wanted in ("auto", "compx"):
            info = find_io_interface(vid, pid, COMPX_REPORT_LENGTH)
            if info is not None:
                return info, "compx"
    return None, None


def read_raw(cfg, device_info=None, protocol=None):
    """Return the raw reply frame, for protocol diagnostics."""
    if device_info is None or protocol is None:
        device_info, protocol = find_device(cfg)
    if device_info is None:
        return None
    reader = _read_compx if protocol == "compx" else _read_feature
    return reader(cfg, device_info, want_raw=True)


def read_battery(cfg, device_info=None, protocol=None):
    """Read the battery level. Returns BatteryStatus, or None if unavailable."""
    if device_info is None or protocol is None:
        device_info, protocol = find_device(cfg)
    if device_info is None:
        return None
    reader = _read_compx if protocol == "compx" else _read_feature
    return reader(cfg, device_info)

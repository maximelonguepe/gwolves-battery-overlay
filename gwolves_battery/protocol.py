"""Battery protocol of the mouse.xyz web driver.

Reconstructed from the public JavaScript bundle served by https://mouse.xyz
(the `getBatPer` function). See docs/PROTOCOL.md for the full write-up.

Request  : feature report, report ID 0, 64-byte payload
             payload[2] = device_id (2 = the mouse)
             payload[3] = 2
             payload[5] = 0x83  (CMD_GET_BATTERY)
Response : raw[1] = 0xA1   header
           raw[6] = 0x83   command echo
           raw[7] = charging flag (0 = on battery)
           raw[8] = battery percentage

Protocol convention: a command byte with the high bit set is a read (0x80
polling rate, 0x81 firmware, 0x83 battery); low values are writes. This
module only ever issues read commands.
"""
import time

from .hid_backend import HidDevice, find_control_interface

CMD_GET_BATTERY = 0x83
RESPONSE_HEADER = 0xA1
PAYLOAD_SIZE = 64


class BatteryStatus(object):
    __slots__ = ("percent", "charging")

    def __init__(self, percent, charging):
        self.percent = percent
        self.charging = charging

    def __repr__(self):
        return "BatteryStatus(percent=%r, charging=%r)" % (self.percent,
                                                           self.charging)


def build_request(device_id, feature_length):
    """Build the full buffer (report ID + payload)."""
    payload = bytearray(PAYLOAD_SIZE)
    payload[2] = device_id
    payload[3] = 2
    payload[5] = CMD_GET_BATTERY
    buf = bytearray(feature_length)
    buf[0] = 0  # report ID
    buf[1:1 + PAYLOAD_SIZE] = payload
    return buf


def parse_response(raw):
    """Return a BatteryStatus, or None if the frame does not match."""
    if raw is None or len(raw) < 9:
        return None
    if raw[1] != RESPONSE_HEADER or raw[6] != CMD_GET_BATTERY:
        return None
    percent = raw[8]
    if not 0 <= percent <= 100:
        return None
    return BatteryStatus(percent, bool(raw[7]))


def read_raw(cfg, device_info=None):
    """Return the raw response frame, for protocol diagnostics.

    Useful to identify which byte carries a piece of state on a model whose
    layout differs, or has not been confirmed yet.
    """
    from .config import as_int

    dev = cfg["device"]
    poll = cfg["polling"]
    info = device_info or find_control_interface(
        as_int(dev["vendor_id"]), as_int(dev["product_id"]),
        int(dev["feature_report_length"]))
    if info is None:
        return None

    length = min(int(dev["feature_report_length"]),
                 info.feature_length or int(dev["feature_report_length"]))
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
                    return raw
                time.sleep(0.05)
    except OSError:
        return None
    return None


def read_battery(cfg, device_info=None):
    """Read the battery level. Returns a BatteryStatus, or None if unavailable.

    `cfg` is the full configuration; passing `device_info` skips re-enumeration.
    """
    from .config import as_int

    dev = cfg["device"]
    poll = cfg["polling"]
    vid = as_int(dev["vendor_id"])
    pid = as_int(dev["product_id"])
    flen = int(dev["feature_report_length"])

    info = device_info or find_control_interface(vid, pid, flen)
    if info is None:
        return None

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
                status = parse_response(handle.get_feature(length))
                if status is not None:
                    return status
                time.sleep(0.05)
    except OSError:
        return None
    return None

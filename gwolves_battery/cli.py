"""Command line entry point."""
import argparse
import sys

from . import __version__, config as cfgmod
from .hid_backend import enumerate_devices
from .protocol import read_battery


def build_parser():
    parser = argparse.ArgumentParser(
        prog="gwolves-battery",
        description="Battery overlay for wireless mice compatible with the "
                    "mouse.xyz web driver.")
    parser.add_argument("--version", action="version",
                        version="%(prog)s " + __version__)
    parser.add_argument("--config", metavar="PATH",
                        help="use an alternate configuration file")
    parser.add_argument("--no-save", action="store_true",
                        help="never write settings (position, style...) to disk")

    actions = parser.add_argument_group("actions")
    actions.add_argument("--once", action="store_true",
                         help="print the battery level once and exit")
    actions.add_argument("--watch", action="store_true",
                         help="print continuously to the console, no overlay")
    actions.add_argument("--list-devices", action="store_true",
                         help="list HID interfaces to find your VID/PID")
    actions.add_argument("--dump-config", action="store_true",
                         help="print the effective configuration as JSON")
    actions.add_argument("--raw", action="store_true",
                         help="print the raw response frame once, for diagnostics")
    actions.add_argument("--watch-raw", type=int, metavar="SECONDS",
                         nargs="?", const=120,
                         help="sample raw frames and report which bytes change "
                              "(default 120s); plug or unplug the cable while "
                              "it runs to locate the charging byte")

    device = parser.add_argument_group("device")
    device.add_argument("--vid", metavar="ID", help="vendor ID, e.g. 0x33E4")
    device.add_argument("--pid", metavar="ID", help="product ID, e.g. 0x3517")
    device.add_argument("--device-id", type=int, metavar="N",
                        help="protocol deviceID byte (default 2)")
    device.add_argument("--feature-length", type=int, metavar="N",
                        help="feature report length, report ID included")

    ui = parser.add_argument_group("display")
    ui.add_argument("--style", choices=("pill", "ring", "minimal"))
    ui.add_argument("--font-size", type=int, metavar="N")
    ui.add_argument("--font-family", metavar="NAME")
    ui.add_argument("--opacity", type=float, metavar="F", help="0.1 to 1.0")
    ui.add_argument("--position", metavar="X,Y",
                    help="initial position, e.g. 40,40")
    ui.add_argument("--interval", type=int, metavar="SECONDS",
                    help="polling interval (default 120)")
    return parser


def apply_overrides(cfg, args):
    device, overlay, polling = cfg["device"], cfg["overlay"], cfg["polling"]
    if args.vid:
        device["vendor_id"] = args.vid
    if args.pid:
        device["product_id"] = args.pid
    if args.device_id is not None:
        device["device_id"] = args.device_id
    if args.feature_length is not None:
        device["feature_report_length"] = args.feature_length
    if args.style:
        overlay["style"] = args.style
    if args.font_size is not None:
        overlay["font_size"] = args.font_size
    if args.font_family:
        overlay["font_family"] = args.font_family
    if args.opacity is not None:
        overlay["opacity"] = args.opacity
    if args.position:
        try:
            x, y = (int(v) for v in args.position.split(",", 1))
            overlay["x"], overlay["y"] = x, y
        except ValueError:
            raise SystemExit("--position expects X,Y (e.g. 40,40)")
    if args.interval is not None:
        polling["interval_seconds"] = args.interval
    return cfg


def cmd_list_devices():
    devices = enumerate_devices()
    if not devices:
        print("No HID interface detected.")
        return 1
    print("%-9s %-9s %-11s %-7s %s" %
          ("VID", "PID", "USAGE", "FEATURE", "PRODUCT"))
    print("-" * 78)
    for info in sorted(devices, key=lambda i: (i.vendor_id, i.product_id)):
        marker = "  <-- candidate" if (info.feature_length or 0) >= 65 else ""
        print("0x%04X    0x%04X    %04X:%04X   %-7s %s%s" %
              (info.vendor_id, info.product_id, info.usage_page, info.usage,
               info.feature_length or 0, (info.product or "")[:34], marker))
    print("\nRows marked 'candidate' expose a feature report of 65+ bytes, "
          "which is\nthe vendor interface the protocol runs on.")
    return 0


def cmd_once(cfg):
    status = read_battery(cfg)
    if status is None:
        print("Mouse not found or powered off.", file=sys.stderr)
        return 1
    print("Battery: %d%%%s" % (status.percent,
                               "  (charging)" if status.charging else ""))
    return 0


def _hex(frame, count=12):
    return " ".join("%02X" % b for b in frame[:count])


def cmd_raw(cfg):
    from .protocol import read_raw
    frame = read_raw(cfg)
    if frame is None:
        print("Mouse not found or powered off.", file=sys.stderr)
        return 1
    print("raw   : %s" % _hex(frame, 16))
    print("index :  0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15")
    print("\nheader   raw[1] = 0x%02X" % frame[1])
    print("echo     raw[6] = 0x%02X" % frame[6])
    print("raw[7]          = %d   (assumed charging flag, unconfirmed)"
          % frame[7])
    print("raw[8]          = %d   (battery percentage)" % frame[8])
    return 0


def cmd_watch_raw(cfg, duration):
    import time
    from .protocol import read_raw

    interval = 3
    print("Sampling for %ds every %ds. Plug or unplug the cable while it runs."
          % (duration, interval))
    print("A conclusive test needs the battery below ~95%: at full charge the\n"
          "charging circuit stops, so a charging flag would read 0 anyway.\n")

    samples = []
    start = time.time()
    try:
        while time.time() - start < duration:
            frame = read_raw(cfg)
            stamp = time.strftime("%H:%M:%S")
            if frame is None:
                print("%s  no response (mouse asleep?)" % stamp)
            else:
                print("%s  %s   -> [7]=%-3d [8]=%-3d"
                      % (stamp, _hex(frame), frame[7], frame[8]))
                samples.append(bytes(frame[:16]))
            time.sleep(interval)
    except KeyboardInterrupt:
        pass

    print()
    if len(samples) < 2:
        print("Not enough valid samples to compare.")
        return 1
    changed = [(i, sorted({s[i] for s in samples})) for i in range(16)]
    changed = [(i, v) for i, v in changed if len(v) > 1]
    if not changed:
        print("No byte changed across %d samples." % len(samples))
        return 0
    print("Bytes that changed:")
    for i, values in changed:
        print("   raw[%d] : %s" % (i, " -> ".join(str(v) for v in values)))
    return 0


def cmd_watch(cfg):
    import time
    interval = max(5, int(cfg["polling"]["interval_seconds"]))
    print("Polling every %ds. Press Ctrl+C to stop." % interval)
    try:
        while True:
            status = read_battery(cfg)
            stamp = time.strftime("%H:%M:%S")
            if status is None:
                print("%s  --  (unavailable)" % stamp)
            else:
                print("%s  %3d%%%s" % (stamp, status.percent,
                                       "  charging" if status.charging else ""))
            time.sleep(interval)
    except KeyboardInterrupt:
        return 0


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.list_devices:
        return cmd_list_devices()

    try:
        cfg, path = cfgmod.load(args.config)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    cfg = apply_overrides(cfg, args)

    if args.dump_config:
        import json
        print("# effective configuration (file: %s)" % path)
        print(json.dumps(cfg, indent=2, ensure_ascii=False))
        return 0
    if args.raw:
        return cmd_raw(cfg)
    if args.watch_raw is not None:
        return cmd_watch_raw(cfg, args.watch_raw)
    if args.once:
        return cmd_once(cfg)
    if args.watch:
        return cmd_watch(cfg)

    from .overlay import Overlay
    Overlay(cfg, False if args.no_save else path).run()
    return 0

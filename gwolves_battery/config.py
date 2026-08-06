"""Configuration loading, merging and persistence."""
import copy
import json
import os

APP_DIR_NAME = "gwolves-battery"

DEFAULTS = {
    "device": {
        # Defaults target the G-Wolves Fenrir/Lycan Asym 8K (2.4 GHz dongle).
        # Run `python -m gwolves_battery --list-devices` to find the
        # identifiers of a different mouse.
        "vendor_id": "0x33E4",
        "product_id": "0x3517",
        # HID feature report size, report ID included. 65 = 1 + 64.
        "feature_report_length": 65,
        # Protocol deviceID byte (payload[2]). 2 means the mouse itself.
        "device_id": 2,
    },
    "polling": {
        "interval_seconds": 120,
        # Exchanges attempted before giving up on a single read.
        "retries": 4,
        # Wait between sending the command and reading the reply.
        "response_delay_ms": 100,
    },
    "overlay": {
        "style": "pill",          # pill | ring | minimal
        "x": 40,
        "y": 40,
        "font_family": "Segoe UI",
        "font_size": 20,
        "opacity": 0.92,          # 0.1 to 1.0
        "always_on_top": True,
    },
    "colors": {
        # First rule whose `max` is >= the current percentage wins.
        "thresholds": [
            {"max": 15, "color": "#ff5f57"},
            {"max": 30, "color": "#ffb340"},
            {"max": 100, "color": "#4ade80"},
        ],
        "unknown": "#6b7078",
        "background": "#15161a",
        "border": "#2c2f36",
        "track": "#24262c",
        "cell_background": "#0c0d10",
        "cell_border": "#4a4f59",
        "text": "#f0f2f5",
        "charging": "#ffe066",
        "outline": "#000000",
    },
}

# Legacy flat schema (v0) -> current nested schema.
_LEGACY_KEYS = {
    "x": ("overlay", "x"),
    "y": ("overlay", "y"),
    "font_size": ("overlay", "font_size"),
    "style": ("overlay", "style"),
    "alpha": ("overlay", "opacity"),
    "poll_seconds": ("polling", "interval_seconds"),
}


def default_config_path():
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or \
            os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, APP_DIR_NAME, "config.json")


def _deep_merge(base, override):
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _migrate_legacy(raw):
    """Lift flat keys from an older config into the current schema."""
    if not raw or any(k in raw for k in ("device", "polling", "overlay", "colors")):
        return raw
    migrated = {}
    for flat, (section, key) in _LEGACY_KEYS.items():
        if flat in raw:
            migrated.setdefault(section, {})[key] = raw[flat]
    return migrated


def load(path=None):
    """Return (merged_config, path_used)."""
    path = path or default_config_path()
    raw = {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except FileNotFoundError:
        pass
    except (ValueError, OSError) as exc:
        raise RuntimeError("Cannot read config (%s): %s" % (path, exc))
    return _deep_merge(DEFAULTS, _migrate_legacy(raw)), path


def save(cfg, path=None):
    path = path or default_config_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(cfg, handle, indent=2, ensure_ascii=False)
        return True
    except OSError:
        return False


def as_int(value):
    """Accept 13284, '13284' or '0x33E4'."""
    if isinstance(value, int):
        return value
    text = str(value).strip()
    return int(text, 16) if text.lower().startswith("0x") else int(text, 10)


def level_color(pct, colors):
    if pct is None:
        return colors["unknown"]
    for rule in sorted(colors["thresholds"], key=lambda r: r["max"]):
        if pct <= rule["max"]:
            return rule["color"]
    return colors["thresholds"][-1]["color"]

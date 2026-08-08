# gwolves-battery-overlay

A desktop overlay that permanently shows the battery level of wireless mice
driven by the [mouse.xyz](https://mouse.xyz) web driver — including the
**G-Wolves Lycan / Fenrir Asym 8K**.

These mice expose **no** standard HID battery: Windows does not show a level,
HWiNFO cannot see one, and the only official way to check is to open the web
configurator and click "Refresh". This project reads the value directly by
talking to the mouse's vendor interface.

- **No dependencies.** Python 3.7+ and its standard library, nothing else.
  No `hidapi`, no `pywin32`, no compiler.
- **Read-only.** A single command is ever sent, `0x83`, the same one the
  official driver uses. The device is never written to.
- **Fully configurable**: VID/PID, colours, thresholds, style, position,
  interval — through a config file or the command line.

The protocol, undocumented publicly until now, is written up in
[`docs/PROTOCOL.md`](docs/PROTOCOL.md).

## Requirements

- Windows (HID access goes through `hid.dll` / `setupapi.dll`)
- Python 3.7 or newer, with Tkinter (bundled with the official installer)

## Quick start

```bash
git clone https://github.com/<user>/gwolves-battery-overlay.git
cd gwolves-battery-overlay
python -m gwolves_battery --once
```

If a level is printed, start the overlay:

```bash
pythonw overlay.pyw
```

- **Left-click and drag** to move it (the position is remembered)
- **Right-click** for style, size, opacity, refresh and quit

## Your mouse is not detected?

The defaults target `0x33E4:0x3517`. For any other model:

```bash
python -m gwolves_battery --list-devices
```

Rows marked `<-- candidate` expose a feature report of 65 bytes or more, which
is the vendor interface the protocol runs on. Then retry with your own
identifiers:

```bash
python -m gwolves_battery --vid 0xXXXX --pid 0xYYYY --once
```

If that works, save them in your configuration. If the mouse stays silent, the
"Variants not implemented" section of [`docs/PROTOCOL.md`](docs/PROTOCOL.md)
describes two other protocol families found in the driver.

## Configuration

The file is read from `%LOCALAPPDATA%\gwolves-battery\config.json`
(`~/.config/gwolves-battery/config.json` elsewhere) and created the first time
a setting changes. [`config.example.json`](config.example.json) lists every key
with its default.

### `device`

| Key | Default | Description |
|---|---|---|
| `vendor_id` | `"0x33E4"` | Vendor ID. Accepts `"0x33E4"` or `13284`. |
| `product_id` | `["0x3517", "0x3508"]` | Product ID, or a list tried in order. A mouse usually changes ID when plugged in: `0x3517` is the dongle, `0x3508` wired. |
| `feature_report_length` | `65` | Feature report size, report ID included. |
| `device_id` | `2` | Protocol `deviceID` byte. `2` is the mouse. |

### `polling`

| Key | Default | Description |
|---|---|---|
| `interval_seconds` | `120` | Delay between two reads. |
| `retries` | `4` | Exchanges attempted before giving up on a read. |
| `response_delay_ms` | `100` | Wait between command and reply. |

Every read travels over the 2.4 GHz link. A short interval queries the mouse
more often; 120 s is a sensible compromise, as a battery does not move fast.

### `overlay`

| Key | Default | Description |
|---|---|---|
| `style` | `"pill"` | `pill`, `ring` or `minimal`. |
| `x`, `y` | `40`, `40` | Screen position, updated when dragged. |
| `font_family` | `"Segoe UI"` | Font. |
| `font_size` | `20` | Every graphical element scales with it. |
| `opacity` | `0.92` | From `0.1` to `1.0`. |
| `always_on_top` | `true` | Keep above other windows. |

### `colors`

`thresholds` is a list of rules evaluated by ascending `max`: the first one
whose `max` is greater than or equal to the current percentage wins. The other
keys (`background`, `border`, `track`, `text`, `charging`…) control the rest of
the rendering.

```json
"thresholds": [
  { "max": 15,  "color": "#ff5f57" },
  { "max": 30,  "color": "#ffb340" },
  { "max": 100, "color": "#4ade80" }
]
```

## Command line

Any command-line option takes precedence over the config file.

```
--once                  print the battery level once and exit
--watch                 print continuously to the console, no overlay
--list-devices          list present HID interfaces
--dump-config           print the effective configuration
--raw                   print the raw response frame once
--watch-raw [SECONDS]   sample raw frames and report which bytes change
--config PATH           use an alternate configuration file
--no-save               never write settings to disk

--vid ID                vendor ID, e.g. 0x33E4
--pid ID                product ID, e.g. 0x3517
--device-id N           protocol deviceID byte
--feature-length N      feature report length

--style {pill,ring,minimal}
--font-size N
--font-family NAME
--opacity F             0.1 to 1.0
--position X,Y
--interval SECONDS
```

Example — a compact, semi-transparent ring in the top-right corner of a
3440 px screen, without touching the saved configuration:

```bash
pythonw overlay.pyw --style ring --font-size 16 --opacity 0.7 --position 3300,20 --no-save
```

## Start with Windows

Open `shell:startup` (Win+R) and drop a shortcut in there pointing to:

```
C:\path\to\pythonw.exe  "C:\path\to\overlay.pyw"
```

Delete the shortcut to disable it.

## Safety

The protocol includes destructive commands, notably `0xB0` (enter bootloader)
and the firmware-writing routines. **This project does not use them.** The only
frame it sends is `0x83`, a read, identical to the one the official driver
sends on every "Refresh" click.

If you explore the protocol yourself, never sweep command numbers at random on
a real device.

## Known limitations

- **Windows only.** The HID backend calls the Win32 API. A Linux port over
  `hidraw` would be straightforward but is not done.
- **One device at a time.**
- **Overlays do not show over exclusive-fullscreen games.** Windows draws
  those above every other window, "always on top" included. Switch the game to
  borderless windowed mode if you need the level visible while playing.
- If your mouse answers on one connection but not the other, add its wired
  product ID to the `product_id` list — `--list-devices` shows it while the
  cable is plugged in.
- Tkinter rendering is not antialiased, so rounded corners can look slightly
  jagged at large sizes.

## Acknowledgements

Protocol reconstructed from the public JavaScript bundle of `mouse.xyz`. This
project is not affiliated with G-Wolves nor with the web driver's authors.

## License

MIT — see [LICENSE](LICENSE).

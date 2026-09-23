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
- **Read-only.** Only a battery-read command is ever sent, the same one the
  official driver uses. No setting, firmware or bootloader command is issued.
- **Keeps reading while charging.** Plugging the cable in makes the mouse
  switch product ID and drop its dongle, which is enough to blind a tool that
  only knows the wireless one. Both are tried, so the level stays visible and
  the charging state is reported.
- **Fully configurable**: VID/PID, colours, thresholds, style, position,
  interval — through a config file or the command line.

Both protocol families these mice use, undocumented publicly until now, are
written up in [`docs/PROTOCOL.md`](docs/PROTOCOL.md).

## Requirements

- Windows (HID access goes through `hid.dll` / `setupapi.dll`)
- Python 3.7 or newer, with Tkinter (bundled with the official installer)

## Quick start

```bash
git clone https://github.com/maximelonguepe/gwolves-battery-overlay.git
```

```bash
cd gwolves-battery-overlay && python -m gwolves_battery --once
```

> **Wake the mouse first.** A sleeping mouse answers nothing, and the tool
> cannot tell that apart from an unsupported device. Move it, click it, then
> run the command.

If a level is printed, start the overlay:

```bash
pythonw overlay.pyw
```

- **Left-click and drag** to move it (the position is remembered)
- **Right-click** for style, size, opacity, refresh and quit

## Tested hardware

| Mouse | VID:PID | Protocol | Status |
|---|---|---|---|
| G-Wolves Fenrir / Lycan Asym 8K | `0x33E4:0x3517` dongle, `0x33E4:0x3508` wired | `feature` | verified, wireless and charging |
| G-Wolves Fenrir Pro (Receiver RS) | `0x33E4:0x3854` | `compx` | verified, reports voltage too |
| HSK Pro | — | `feature` | reported working by a user |

`mouse.xyz` is a white-label driver shared by several brands, so other models
are likely to work. If yours does, a pull request adding it to this table is
welcome.

### Two protocols

Devices split into two families that share nothing but the vendor:

- **`feature`** — a 65-byte feature report carries the request and the reply.
- **`compx`** — 17-byte interrupt reports under report ID 8, with a checksum,
  and the reply arrives asynchronously as an input report. These devices also
  report the **battery voltage in mV**.

`protocol` defaults to `auto`, which picks the right one from the HID
descriptors, so there is normally nothing to set. `--list-devices` labels each
candidate interface with the family it belongs to.

## Your mouse is not detected?

**Check the mouse is awake first** — a sleeping mouse answers nothing, and
that looks exactly like an unsupported device.

The defaults target `0x33E4:0x3517`. For any other model:

```bash
python -m gwolves_battery --list-devices
```

Marked rows are the vendor interface a protocol runs on — `<-- feature` for a
65-byte feature report, `<-- compx` for 17-byte input and output reports. Then
retry with your own identifiers:

```bash
python -m gwolves_battery --vid 0xXXXX --pid 0xYYYY --once
```

If that works, save them in your configuration. If the mouse stays silent,
section 7 of [`docs/PROTOCOL.md`](docs/PROTOCOL.md) describes a third, legacy
protocol family found in the driver but not implemented here.

## Configuration

The file is read from `%LOCALAPPDATA%\gwolves-battery\config.json`
(`~/.config/gwolves-battery/config.json` elsewhere) and created the first time
a setting changes. [`config.example.json`](config.example.json) lists every key
with its default.

### `device`

| Key | Default | Description |
|---|---|---|
| `vendor_id` | `"0x33E4"` | Vendor ID. Accepts `"0x33E4"` or `13284`. |
| `product_id` | `["0x3517", "0x3508", "0x3854"]` | Product ID, or a list tried in order. A mouse usually changes ID when plugged in: `0x3517` is the dongle, `0x3508` wired. |
| `protocol` | `"auto"` | `auto`, `feature` or `compx`. `auto` detects the family from the HID descriptors. |
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
frames it sends are battery reads — `0x83` for the `feature` family, `0x04` for
`compx` — identical to what the official driver sends on every "Refresh" click.

If you explore the protocol yourself, never sweep command numbers at random on
a real device.

## Debugging a silent overlay

`pythonw` has no console, so a failing poll leaves no trace. Set `GWB_DEBUG=1`
and the overlay appends every poll result to
`%LOCALAPPDATA%\gwolves-battery\debug.log`:

```bash
set GWB_DEBUG=1 && pythonw overlay.pyw
```

```
18:17:55  read -> BatteryStatus(percent=90, charging=False, voltage_mv=4063)
18:18:05  read -> None
```

`None` almost always means the mouse is asleep. After a failed read the
overlay retries in 15 s instead of waiting a full interval, so it recovers
shortly after the mouse wakes.

## Known limitations

- **A sleeping mouse reads as absent.** There is no way to tell "asleep" from
  "not there" over this protocol, so the overlay shows `--%` until the mouse
  wakes up, then recovers on its own.
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

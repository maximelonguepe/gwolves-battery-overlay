# Battery protocol (`mouse.xyz` web driver)

This document describes the HID protocol used to read the battery level of
wireless mice driven by the **[mouse.xyz](https://mouse.xyz)** web driver.

It was reconstructed by reading the site's public JavaScript bundle
(`static/js/index-*.js`), which drives the device through the WebHID API. No
USB capture was needed: the driver's code is shipped in the clear to the
browser.

Verified on a **G-Wolves Fenrir/Lycan Asym 8K** (`0x33E4:0x3517` over the
2.4 GHz dongle, `0x33E4:0x3508` wired). `mouse.xyz` is a *white-label* driver
shared by several brands, and the protocol has since been reported working on
an **HSK Pro** as well, so it is not specific to one vendor.

---

## 1. Which interface to talk to

The device exposes several HID collections. The one carrying the protocol is
the **vendor interface**:

| Property | Value |
|---|---|
| Interface | `MI_02` |
| Usage page | `0xFFFF` (vendor-defined) |
| Usage | `0x0000` |
| Feature report length | **65** bytes (1 report ID + 64 payload) |

The driver selects it by looking for the first collection whose
`featureReport` has a `reportCount` of 64. The equivalent practical rule:
**the only interface on the device whose `FeatureReportByteLength >= 65`**.

The other collections (mouse, keyboard, consumer control) expose no feature
report and do not answer.

## 2. Request frame

Sent with `HidD_SetFeature` / `sendFeatureReport(0, …)`, report ID `0`.

```
byte : 0    1    2    3    4    5    6  ... 64
       RID  --   DEV  02   --   CMD  --     --
```

| Field | Offset (full buffer) | Value | Purpose |
|---|---|---|---|
| `RID` | 0 | `0x00` | report ID |
| `DEV` | 3 | `0x02` | device identifier (2 = the mouse) |
| — | 4 | `0x02` | constant |
| `CMD` | 6 | `0x83` | "read battery" command |

Expressed as indices into the 64-byte payload the way the JavaScript does
(`payload[i] == buffer[i+1]`): `payload[2]=2`, `payload[3]=2`,
`payload[5]=0x83`. Every other byte is zero.

## 3. Response frame

Read with `HidD_GetFeature` / `receiveFeatureReport(0)` after ~100 ms.

```
00 A1 00 02 02 00 83 00 3C 00 00 ...
   ^^          ^^    ^^ ^^ ^^
   header      cst  echo |  percentage
                         charging
```

| Field | Offset | Description |
|---|---|---|
| header | 1 | `0xA1` — marks a valid response |
| — | 4 | `0x02` |
| echo | 6 | `0x83` — command echo |
| charging | 7 | `0` = on battery, `1` = charging |
| **level** | **8** | **percentage, 0–100** |

Both fields are confirmed on hardware: `raw[7] = 0` with `raw[8] = 100` on
battery, and `raw[7] = 1` with `raw[8] = 95` with the cable plugged in.

Real sample: `raw[8] = 0x3C = 60`, at the very moment the official interface
displayed 60 %. The driver rounds its display to 5 % steps, but the value on
the wire is the exact percentage.

### Header offset

The JavaScript tests two alignments (`a[1]==0xA1` **or** `a[0]==0xA1`) because
`receiveFeatureReport` may or may not include the report ID depending on the
implementation. With the Win32 API the report ID is **always** present at
offset 0, so only `raw[1] == 0xA1` is relevant.

## 4. The product ID changes when the cable is plugged in

This one is easy to miss and makes a tool appear broken exactly when the
battery matters most.

Plugging the USB cable in does not simply add a second connection: the mouse
**stops answering through its dongle** and enumerates as a different product.
On the reference hardware:

| Connection | VID:PID |
|---|---|
| 2.4 GHz dongle | `0x33E4:0x3517` |
| USB cable (wired) | `0x33E4:0x3508` |

The dongle's interfaces disappear from enumeration entirely, so a tool that
only knows the wireless PID goes silent the moment charging starts. The
protocol itself is unchanged — same vendor interface, same `0x83` command,
same response layout.

This is why `product_id` accepts a list of candidates, tried in order.

## 5. General command convention

The command byte follows a clear rule throughout the protocol:

| High bit | Meaning | Examples |
|---|---|---|
| 1 (`0x80`+) | **read** | `0x80` polling rate, `0x81` firmware, `0x83` battery, `0x85` profile |
| 0 | **write** | `0x00` set polling rate, `0x05` set profile |

> **Warning.** The same protocol exposes destructive commands, notably `0xB0`
> (`enterBL`, enter bootloader) and the firmware-writing routines. This
> project only ever issues `0x83`. Never sweep command numbers at random on a
> real device.

## 6. Variants not implemented

The bundle contains two other protocol families, present for other hardware
generations:

- **Legacy protocol** (`getOldBattery`): `payload[1]=2`, `payload[2]=0x8F`,
  response `0xA1 0x02 0x8F` followed by two bytes.
- **Compx family**: 16-byte reports, command `0x04`, with an extra 16-bit
  field at offsets 7–8 that looks like a voltage in mV.

Neither is needed for the hardware targeted here, but they are worth trying if
your mouse does not answer `0x83`.

## 7. Win32 implementation notes

Two pitfalls worth recording for anyone reimplementing this:

- **`SetupDiGetClassDevsW` needs an explicit `restype`.** Without it, ctypes
  truncates the 64-bit handle to a signed 32-bit int and enumeration returns
  zero devices, with no error raised.
- **`CreateFileW` fails with `GENERIC_READ|GENERIC_WRITE`** on mouse and
  keyboard collections, which Windows keeps for exclusive access. Fall back to
  `dwDesiredAccess = 0`, which is still sufficient for `HidD_GetFeature` and
  `HidD_SetFeature`.

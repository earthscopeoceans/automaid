> **AI-written documentation — non-authoritative.** Verify timing definitions against the linked source code and SEED manual before relying on them.

# Clock timing matrix

Use **`t_mer` = uncorrected MERMAID time** and **`t_gps` = GPS-reference time for the same instant**.

For GPS rows, these describe the synchronization measurement. For Recording
rows, use the original recording's first sample; its `t_gps` is **estimated**
through the existing clock-correction model. The GeoCSV names below are the
schema 1.0.0 names; their existing source variables, values
and signs are unchanged.

| Context | Quantity | Definition | MERMAID ahead: `t_mer > t_gps` | MERMAID behind: `t_mer < t_gps` |
| --- | --- | --- | --- | --- |
| GPS | `gps.clockdrift` — manual's drift | `t_gps - t_mer` | Negative | Positive |
| GPS | `gps.mseed_time_delay` | `t_mer - t_gps` | Positive | Negative |
| Position GeoCSV row | `ClockOffset` | `t_mer - t_gps` | Positive | Negative |
| Recording | `event.clockdrift_correction` | Estimated `t_gps - t_mer` | Negative | Positive |
| Recording | `event.mseed_time_correction` | Estimated `t_gps - t_mer` | Negative | Positive |
| Recording GeoCSV row | `TimeCorrectionApplied` | Estimated `t_gps - t_mer` | Negative | Positive |
| Recording | `corrected_starttime` / GeoCSV `Time` | `t_mer + (t_gps - t_mer) = t_gps` | Moves earlier | Moves later |
| MiniSEED fixed header | Field 16: correction, in 0.0001-second ticks | `round_half_even(decimal(t_gps - t_mer) * 10000)` | Negative or zero after rounding | Positive or zero after rounding |

**The GPS and Recording differences refer to different epochs. Their signs
follow the same definitions, but their magnitudes need not match.**

The MiniSEED applied bit is separate from that numeric correction:

| Applied bit | Stored start time, using the first record | Reader behavior |
| --- | --- | --- |
| `0` — not applied | `t_mer` | Adds the stored correction: approximately `t_mer + (t_gps - t_mer) ≈ t_gps`, subject to header quantization |
| `1` — already applied; normal automaid output | `t_gps` | Uses `t_gps` directly; **does not add the correction again** |

A concrete sign check, illustrative rather than measured data:

| Case | `t_mer` | `t_gps` | Manual drift | `ClockOffset` | `TimeCorrectionApplied` |
| --- | --- | --- | --- | --- | --- |
| MERMAID ahead | `12:00:02` | `12:00:00` | `-2 s` | `+2 s` | `-2 s` |
| MERMAID behind | `11:59:58` | `12:00:00` | `+2 s` | `-2 s` | `+2 s` |

## Sources and limits

- [GPS drift/delay](../scripts/gps.py): `mseed_time_delay = -clockdrift`.
- [Recording correction and addition](../scripts/events.py): `mseed_time_correction = clockdrift_correction`, then `corrected_starttime = uncorrected_starttime + clockdrift_correction`.
- [MiniSEED serialization](../scripts/utils.py): nearest-0.0001-second rounding with decimal ties to even, finite/signed-32-bit checks before mutation, applied-bit setting and per-record correction metadata.
- [SEED v2.4 manual](https://www.fdsn.org/pdf/SEEDManual_V2.4.pdf), printed pages 33 and 109: signed LONG representation, correction units and applied-bit semantics. The fixed-header addition rule was separately verified in ObsPy/libmseed source and synthetic records; it is not an explicit equation in that manual paragraph. Blockette 57 on page 77 uses a distinct filter-correction convention.

## Serialization and verification

The GeoCSV writer reads ClockOffset from `gps.mseed_time_delay`,
TimeCorrectionApplied from `event.mseed_time_correction`, and Recording Time
from the already corrected source Stats. UTC strings have six fractional
digits, rounded to the nearest microsecond with exact decimal ties to even.

The MiniSEED helper rounds the decimal spelling of the supplied correction to
0.0001-second ticks with exact ties to even. Non-finite values and rounded ticks
outside signed 32-bit range raise before file mutation. Maximum quantization
error is 50 microseconds. This serializes correction history; it does not round
waveform timestamps or change the clock model or GeoCSV value.

After writing, an independent read-back pass requires the applied bit and
expected integer correction on every record, including zero corrections.
A mismatch raises with filename, one-based record number, byte offset,
expected ticks and observed flags/ticks. Writes are not rolled back on failure.

The helper supports normal big-endian, uniform-record-length writer output.
ObsPy 1.4.1's flag setter decodes headers as big-endian; little-endian input can
fail. The initial record count is inferred from file size and first-record
length, making mixed record lengths unsafe. Read-back does not establish
support for those inputs. These limitations require a separately scoped fix.

Clock drift means accumulated GPS-minus-instrument offset, not GPS oscillator
rate error. `mseed_time_delay` is an internal clock-offset variable, not a named
MiniSEED fixed-header field or SEED Blockette 57 filter delay. Positive
fixed-header correction moves a timestamp later; Blockette 57 uses a distinct
filter-correction convention. Recording corrections do not alter GPS, pressure
or crossing epochs.

See [producer source rules](geocsv.md) and the publisher's
[artifact-bound verification records](../../mermaid-publisher/docs/geocsv/evidence.md).

The cycle GPS eligibility guard compares signed `clockdrift < 5` and does not
apply an absolute-value bound. Its treatment of large negative offsets remains
a scientific review question; do not reinterpret it as `abs(clockdrift) < 5`
or change it during documentation work.

## Observed P0008 ClockOffset anomalies

A review on 2026-11-12 identified eight anomalously large negative `ClockOffset`
values in four pairs of `Measurement:Position:u-blox_NEO-M8N` rows. The reviewed
file was `/Users/jdsimon/Desktop/wip/452.020-P-08.geocsv`, with schema
`MERMAID GeoCSV v1.0.0-rc1`, producer `automaid v4.10.0` and creation timestamp
`2026-11-05T23:41:47.235000Z`.

The file's SHA-256 is
`2b69cc1655b6126dff5786c50d7532f438f7a935ce6c42ad21dccbad2689625b`.
Line numbers below are one-based physical file lines, including the comment
and column headers. Offsets are the exact serialized values in seconds.

| Source line | GPS row Time (UTC) | ClockOffset (s) |
| --- | --- | --- |
| 9826 | 2020-05-02T06:05:46.000000Z | -1587046398.421204 |
| 9827 | 2020-05-02T06:05:57.000000Z | -1587046398.421204 |
| 15295 | 2021-04-05T13:58:00.000000Z | -1616173526.566926 |
| 15296 | 2021-04-05T13:58:11.000000Z | -1616173526.566926 |
| 15645 | 2021-04-22T15:15:46.000000Z | -1617788518.512238 |
| 15646 | 2021-04-22T15:15:57.000000Z | -1617788518.512238 |
| 16952 | 2021-07-08T17:34:22.000000Z | -1624412535.300324 |
| 16953 | 2021-07-08T17:34:33.000000Z | -1624412535.300324 |

The current `mermaid-geocsv` reader accepted the full file's 23,081 rows during
the review. These finite numeric values passed its validation. Their origin
and any effect on derived positions or waveform time corrections remain
unresolved. Source diagnosis and corrective action are pending.

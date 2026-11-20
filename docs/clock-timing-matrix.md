> **AI-written documentation — non-authoritative.** Verify timing definitions against the linked source code and SEED manual before relying on them.

# Clock timing matrix

Use **`t_mer` = uncorrected MERMAID time** and **`t_gps` = GPS-reference time for the same instant**.

For GPS rows, these describe the synchronization measurement. For Recording
rows, use the original recording's first sample; its `t_gps` is **estimated**
through the existing clock-correction model. The GeoCSV names below are the
development rc2 names; their existing source variables, values
and signs are unchanged.

| Context | Quantity | Definition | MERMAID ahead: `t_mer > t_gps` | MERMAID behind: `t_mer < t_gps` |
| --- | --- | --- | --- | --- |
| GPS | `gps.clockdrift` — manual's drift | `t_gps - t_mer` | Negative | Positive |
| GPS | `gps.mseed_time_delay` | `t_mer - t_gps` | Positive | Negative |
| GPS GeoCSV row | `clock_offset` | `t_mer - t_gps` | Positive | Negative |
| Recording | `event.clockdrift_correction` | Estimated `t_gps - t_mer` | Negative | Positive |
| Recording | `event.mseed_time_correction` | Estimated `t_gps - t_mer` | Negative | Positive |
| Waveform GeoCSV row | `time_correction_applied` | Estimated `t_gps - t_mer` | Negative | Positive |
| Recording | `corrected_starttime` / GeoCSV `derived_time` | `t_mer + (t_gps - t_mer) = t_gps` | Moves earlier | Moves later |
| MiniSEED fixed header | Field 16: correction, in 0.0001-second ticks | `round_half_even(decimal(t_gps - t_mer) * 10000)` | Negative or zero after rounding | Positive or zero after rounding |

**The GPS and Recording differences refer to different epochs. Their signs
follow the same definitions, but their magnitudes need not match.**

The MiniSEED applied bit is separate from that numeric correction:

| Applied bit | Stored start time, using the first record | Reader behavior |
| --- | --- | --- |
| `0` — not applied | `t_mer` | Adds the stored correction: approximately `t_mer + (t_gps - t_mer) ≈ t_gps`, subject to header quantization |
| `1` — already applied; normal automaid output | `t_gps` | Uses `t_gps` directly; **does not add the correction again** |

A concrete sign check, illustrative rather than measured data:

| Case | `t_mer` | `t_gps` | Manual drift | `clock_offset` | `time_correction_applied` |
| --- | --- | --- | --- | --- | --- |
| MERMAID ahead | `12:00:02` | `12:00:00` | `-2 s` | `+2 s` | `-2 s` |
| MERMAID behind | `11:59:58` | `12:00:00` | `+2 s` | `-2 s` | `+2 s` |

## Sources and limits

- [GPS drift/delay](../scripts/gps.py): `mseed_time_delay = -clockdrift`.
- [Recording correction and addition](../scripts/events.py): `mseed_time_correction = clockdrift_correction`, then `corrected_starttime = uncorrected_starttime + clockdrift_correction`.
- [MiniSEED serialization](../scripts/utils.py): nearest-0.0001-second rounding with decimal ties to even, finite/signed-32-bit checks before mutation, applied-bit setting and per-record correction metadata.
- [SEED v2.4 manual](https://www.fdsn.org/pdf/SEEDManual_V2.4.pdf), printed pages 33 and 109: signed LONG representation, correction units and applied-bit semantics. The fixed-header addition rule was separately verified in ObsPy/libmseed source and synthetic records; it is not an explicit equation in that manual paragraph. Blockette 57 on page 77 uses a distinct filter-correction convention.

## Serialization and verification

The GeoCSV writer reads `clock_offset` from `gps.mseed_time_delay`,
`time_correction_applied` from `event.mseed_time_correction`, and waveform
`derived_time` from the already corrected source Stats. GPS and pressure
`measured_time` and crossing `derived_time` receive no clock correction.
Crossing `time_correction_applied` cells are empty because no correction
operation is recorded for those rows.
UTC strings have six fractional
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

From v4.11.3, the cycle GPS eligibility guard requires finite
`abs(clockdrift) < 10` at both original clock anchors. Exactly ten seconds in
either direction fails. Finite oscillator frequencies between 3,000,000 and
4,000,000 Hz inclusive are also required at those anchors. Other GPS position
inputs retain their previous handling without a frequency or clock-drift
filter. Raw observations remain available in measurement outputs. Eligibility
uses only the candidates already assigned to that cycle, and an invalid last
pre-dive or first post-dive clock anchor invalidates correction and normal
position interpolation for that cycle. The existing proximity/count gate over
synchronization entries is retained. See the
[scientific release review](scientific-release-review.md) for remaining questions.

## Observed P0008 clock offset anomalies

A review on 2026-11-12 identified eight GPS fixes with anomalous negative
offsets. Fix pairs on 2020-05-02, 2021-04-05, 2021-04-22 and 2021-07-08
each shared an offset of about −1.59 to −1.62 billion seconds. The origin of
these values and any effect on estimated positions or waveform corrections
remain unresolved. Recheck the source logs and corresponding rc2 GPS fixes
after the rebuild.

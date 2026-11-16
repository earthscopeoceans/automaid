# GeoCSV event-row deduplication

## Purpose

GeoCSV is distributed as a table of event metadata.  Its event rows must be
unique, but a repeated-looking row does not by itself prove that the underlying
MERMAID event data are redundant.  Since August 2026, automaid resolves this
explicitly when writing `geo_DET.csv`, `geo_REQ.csv`, and `geo_DET_REQ.csv`.

## What is compared

The deduplication candidate is an identical rendered GeoCSV
`waveform` row.  For every such candidate, automaid compares the raw bytes extracted from
the event's `<EVENT>` block:

```python
event.mer_binary_header
event.mer_binary_binary
```

Both must be byte-for-byte equal for two events to be considered duplicates.
The enclosing `.MER` filename and its `<ENVIRONMENT>` block are intentionally
not part of this identity: the same transmitted event can occur in multiple
MER files with different filenames or environment metadata.

## Outcomes

| GeoCSV row | Raw event header and payload | Output |
| --- | --- | --- |
| unique | any | write the row |
| duplicated | both identical | write one row |
| duplicated | header or payload differs | write the first row, warn, and write a clash report |

The last case preserves the GeoCSV uniqueness requirement while making the
potentially non-redundant source data reviewable.  It is not silently treated
as a true duplicate.

## Clash reports

If distinct event data render to one GeoCSV row, automaid prints a warning at
the end of `GeoCSV.write()` and writes the corresponding report beside the
GeoCSV files:

```text
geo_DET-CLASHES.md
geo_REQ-CLASHES.md
geo_DET_REQ-CLASHES.md
```

Only outputs containing a clash receive a report.  Each report contains the
rendered GeoCSV row and, for every distinct event-data variant, the source MER
filenames, SHA-256 hashes of the raw header and payload, and payload byte
count.  Hashes are evidence for human review; the program itself uses direct
byte equality, not hash equality, to decide whether event data are identical.

## W0118 example

The 2025-05-13 W0118 case has seven MER transmissions for one event time.
Five contain identical 6,402-sample event data and two contain identical
12,804-sample event data.  The two sample counts correspond to different raw
event headers and payloads, so the expected GeoCSV result is two rows, not one
and not seven.  Neither group is a clash because duplicates within each group
have identical header and payload bytes.

| Event data | MER files | Result |
|---|---|---|
| 160 s, 6,402 samples | `0118_693FC789.MER`, `0118_693FD635.MER`, `0118_693FE5F4.MER`, `0118_69400B35.MER`, `0118_693FDDB3.MER` | Five exact retransmissions of one event |
| 320 s, 12,804 samples | `0118_693A912F.MER`, `0118_693AA155.MER` | Two exact retransmissions of a longer event |

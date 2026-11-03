> **AI-written documentation — non-authoritative.** Verify scientific and operational details against the linked contracts and source before relying on them.

# MERMAID GeoCSV production

Automaid writes station metadata and original waveform descriptions to the
controlled [MERMAID GeoCSV schema 1.0.0](../../mermaid-geocsv/docs/format-spec.md).
Schema and software versions are independent. The writer records its actual
version from `scripts/setup.py` in derivation and interpolation identifiers.

## Workflow and ownership

1. Automaid processes MER/LOG inputs and writes MiniSEED, SAC and GeoCSV under
   the configured processed root. Each instrument's `geo_DET_REQ.csv` combines
   detected and requested recording metadata; `geo_DET.csv` and `geo_REQ.csv`
   contain the corresponding subsets.
2. `mermaid-geocsv` owns the payload schema, parsing, download client and
   waveform association. It preserves source values and never supplies missing
   scientific metadata from defaults or another record.
3. `mermaid-publisher` freezes verbatim payloads, validates every original
   MiniSEED/SAC pair in the selected scope, gates publication, transfers bytes,
   activates testing latest last and records the publication in its archive.
4. `bathymetrix-site` serves exact bytes through a read-only Worker. Clients
   fetch a manifest-pinned snapshot, read it, associate MiniSEED-derived traces,
   optionally create SAC station headers, and write with ObsPy.

See the [publication contract](../../mermaid-publisher/docs/geocsv/contract.md),
[maintainer workflow](../../mermaid-publisher/docs/geocsv/workflow.md),
[hosting runbook](../../bathymetrix-site/docs/geocsv-hosting.md) and
[association reference](../../mermaid-geocsv/docs/obspy-association.md).
Hosted data remain testing only; scientific acceptance does not authorize
production activation. [Publication evidence](../../mermaid-publisher/docs/geocsv/evidence.md)
identifies the validated artifacts and their software.

## Scientific source rules

Recording Time is the corrected first-sample epoch in the source trace Stats.
`TimeCorrectionApplied` is `event.mseed_time_correction`, already added to the
uncorrected start. `ClockOffset` is `gps.mseed_time_delay = -gps.clockdrift`.
Never apply the correction a second time. See the [clock matrix](clock-timing-matrix.md).
Six-digit UTC formatting rounds to the nearest microsecond with decimal ties
to even; display width does not establish clock accuracy.

Recording sampling frequency comes from the assigned acquisition-dive
`ENVIRONMENT/TRUE_SAMPLE_FREQ FS_Hz`, with the product's decimation applied.
It is not selected from a repeated EVENT header or inferred from DET/REQ
classification. [P0006 source evidence](../notes/p0006-historical-sample-frequencies/README.md)
records discrepancies whose cause remains unresolved.

Recording Elevation is explicitly numeric zero metres: an adopted sea-level
reference, not the submerged sensor elevation. Recording WaterPressure retains
source pressure; REQ pressure can be absent. Pressure divided by 100
approximates station depth in metres positive down. Pressure-Absolute sensor
readings preserve finite signed gauge error; Recording and Crossing pressures
remain nonnegative. No atmospheric, density, geoid or tidal correction is inferred.

The configured upper mixed-layer boundary is approximately 50 m deep; it is
not detected from a measured temperature profile. Descent exits its base and
ascent enters it. Crossing WaterPressure is configured depth multiplied by 100,
a boundary proxy rather than a sensor measurement. The GPS interpolation
stability fallback can retain an anchor position and its epoch instead of a
crossing estimate. A Crossing Time therefore need not be the physical crossing
epoch. Preserve this behavior and the existing interpolation model. Faster horizontal
drift in the upper layer is empirical; the model imposes no fixed velocity
ratio. Scientific context: [Nolet et al. (2024), pp. 2369, 2372](https://doi.org/10.1785/0220230377).

## Ordering, deduplication and review

The writer sorts chronologically. Identical raw event headers and payloads
are deduplicated. Distinct raw events that render one identical row are saved
in adjacent `geo_DET_REQ-CLASHES.md`, `geo_DET-CLASHES.md` or
`geo_REQ-CLASHES.md` reports; the CSV contains the first rendered row.
Review clashes without silently changing source values or sampling-frequency
precedence. Repeated original waveforms can independently associate with one
Recording row.

## Safe verification

Canonical `$MERMAID/processed` products and mirrors are read-only verification
inputs. Use conda `pymaid3.10` for automaid; the checkout's `scripts/setup.py`
is the source-version authority. A saved-cycle writer check must supply an
explicit temporary output path to `GeoCSV(saved_cycles).write(...)`.
Do not run the processing entry point or rebuild mirrors merely to inspect
GeoCSV. Candidate creation and exhaustive verification belong to the publisher;
use a separate workspace and fresh reports for changed bytes.

## Bound JSON clash report

Version v4.7.0 also writes geocsv-clash.json beside the combined GeoCSV on every
generation, including zero clashes. It binds the exact GeoCSV SHA-256 and uses
zero-based source_index / one-based physical source_line. Clash entries list all
MiniSEED basenames, distinct raw event header/payload variant_count, every
qualified header field difference with exact source string values, and
payload_bytes_identical. Missing header attributes use present=false without a
value. Raw header differences outside parsed attributes remain raw_header evidence.
Payload equality describes raw DATA bytes; it does not compare decoded samples.

The producer owns this analysis. The publisher does not call automaid or inspect
MER provenance; it checks report binding, references and MiniSEED associations.
Clashes are permitted. Owner review precedes entry into publication. The old
Markdown reports remain producer detail. No processed tree regeneration is
implicit in a source update. See the publisher's
[report contract](../../mermaid-publisher/docs/geocsv/publication-reports.md).

## Producer investigations retained from the consumer review

## MERMAID sampling-rate follow-up

Compare raw MER timing quantities and units, writer inputs and serialized
rates, encoded MiniSEED rates, and ObsPy output. Establish whether differences
arise from upstream formatting, waveform encoding, or reader conversion.
Stored microseconds and six-decimal rates do not independently establish
measurement accuracy. Rate computed from ObsPy's rate-derived endtime is
not independent evidence.

The [fixture evidence](../../mermaid-geocsv/data/fixtures/association/README.md#tolerance-evidence)
supports the current agreement criterion for the checked sample. It does not
settle raw-MER precision across producers and instrument generations. Reading
preserves supplied rates; upstream corrections belong in the producer.


### Instrument and product evidence

Verify the hardware generations affected by reported REQ sampling-rate/time
shifts and whether reconstruction uses acquisition-time or request-time rate.
Claims that DET timing is more accurate, REQ location is less certain, and
current hardware fixes earlier behavior require instrument-specific evidence.
Do not generalize those claims across the archive.

Check source MER classification and scale for the non-20-Hz DET.WLT2 example;
the processed-header audit did not independently inspect every raw MER header.
Preserve historical location codes as source evidence. The
[product reference](../../mermaid-geocsv/docs/mermaid-data-quality.md) distinguishes requested RAW events
from recovered continuous-buffer data.

Resolve the missing P0006 buffer average rate and verify the P0023 value and
the proposed Pipatprathanporn & Simon (2022) citation. Identify the incomplete
Ivy reference and verify Nolet et al. (2024). The supplied MERMAID manual
reference 452.000.852, Version 00, reportedly uses 101 mbar per metre;
independent verification is pending. Current SAC mapping follows automaid's
100 mbar per metre approximation for MERMAID receiver (station) depth in SAC
`stdp`. This question concerns the station-depth approximation; earthquake-source
metadata and `ev*` projections remain outside package scope.

## IcCycle and Init exclusion

From v4.9.1, GeoCSV collection skips every cycle whose `directory_name`
contains `IcCycle` or `Init`, case-insensitively, before collecting GPS,
pressure, Recording or crossing rows. IcCycle outputs use preliminary location
inputs; Init outputs are excluded as a precaution. Recording collection also
excludes events whose processed filename contains either substring, regardless
of case. Excluded events do not enter the combined clash report. The existing
per-event preliminary-location exclusion remains in effect for other events.
GPS/cycle algorithms, cleanup and waveform files are unchanged by this writer
policy.

Publisher 0.6.2 independently excludes both substrings in waveform directory
names and filenames, case-insensitively. Fresh producer output is required to
align GeoCSV Recording coverage with that scope; old GeoCSV payloads are never
edited by the publisher. Regeneration needs a new creation identity and fresh
validation evidence. Source changes do not regenerate protected processed
products or establish new corpus acceptance.

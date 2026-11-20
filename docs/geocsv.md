> **AI-written documentation — non-authoritative.** Verify scientific and operational details against the linked contracts and source before relying on them.

# MERMAID GeoCSV production

Automaid emits [MERMAID GeoCSV 1.0.0-rc2](../../mermaid-geocsv/docs/format-spec.md).
Schema and software versions are independent. The producer header
records the automaid version from `scripts/setup.py`.

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

## Version v4.11.3 eligibility and exclusions

The original last pre-dive and first post-dive clock anchors require finite
oscillator frequency between 3,000,000 and 4,000,000 Hz inclusive and finite
absolute clock drift below ten seconds. Exactly ten seconds fails. Failure
invalidates clock correction and normal position interpolation for the cycle;
an invalid anchor is not replaced. Raw GPS objects and measurement rows retain
their original values. The GPS text/CSV writer formats missing values with
local variables and preserves the source objects.

Ten seconds is an arbitrary, deliberately loose screening cutoff. The
scientifically appropriate maximum remains an open question.

Cycle membership and the original pre-dive/post-dive lists are preserved.
Position estimates use those original lists without applying clock frequency
or clock-drift filters to every input. The existing proximity/count gate still
counts synchronization-list entries, which require both clock fields to be
present but need not each pass the clock-anchor validity checks. Velocity and
extrapolation duration have no automatic acceptance cutoff. The interpolation
stability fallback is retained. Whether a zero-frequency synchronization also
invalidates its associated position or GPS epoch remains an
[open question](scientific-release-review.md#open-scientific-questions).

DET source pressure of zero triggers temporary waveform exclusion pending
instrument review. MiniSEED, SAC, waveform plots, waveform metadata tables and
all GeoCSV waveform variants omit that event. Missing REQ pressure remains
permitted. Waveform filenames use `is_requested`, including a present `TRIG=0`.

Each GeoCSV generation writes two adjacent local review sidecars, including
empty files when there are no corresponding decisions. `gps-validation.jsonl`
contains one entry per revalidated cycle with eligibility, original position
counts, synchronization-entry counts, cycle reasons and rejected clock anchors.
Its `validation_scope` is `clock_anchors`; other position inputs are not
filtered. Numerical rejected GPS fields use strings, preserving non-finite
legacy missing values explicitly.
`excluded-waveforms.jsonl` contains one entry per withheld source Event within
its cycle. Entries include reason codes, source MER, zero-based EVENT block
index when available, raw header and payload SHA-256, acquisition MER, LOG files,
available times, literal source pressure in dbar, converted pressure in mbar
and intended MiniSEED/SAC basenames when available. Old saved Event objects can
lack the EVENT block index; their source hashes still identify the retained
header and payload. These sidecars are local review evidence outside the rc2
payload and publication contract.

Revalidation clears calculated event and cycle metadata before recomputing it.
Canonical saved cycles can therefore be reprocessed into a fresh explicit
output directory using the current calculation methods, without decoding their
samples or writing other products. Existing saved cycles require revalidation
to apply the new GPS policy; the GeoCSV zero-pressure guard also applies when
writing older saved events directly. A GeoCSV-only comparison does not generate
updated waveform files.

## Scientific source rules

Waveform `derived_time` is the corrected first-sample epoch in the source trace
Stats. `time_correction_applied` is `event.mseed_time_correction`, already added
to the uncorrected start. GPS `clock_offset` is
`gps.mseed_time_delay = -gps.clockdrift`.
Never apply the correction a second time. See the [clock matrix](clock-timing-matrix.md).
Six-digit UTC formatting rounds to the nearest microsecond with decimal ties
to even; display width does not establish clock accuracy.

The rc2 column order is:

```csv
type,measured_time,derived_time,network,station,location,channel,data_quality,measured_latitude,measured_longitude,estimated_latitude,estimated_longitude,measured_pressure,estimated_pressure,sample_rate,sample_count,clock_offset,time_correction_applied
```

`type` is `gps`, `pressure`, `downcrossing`, `upcrossing` or `waveform`.
GPS and pressure rows use `measured_time`; crossings and waveforms use
`derived_time`. Only GPS rows have measured coordinates. The writer retains
the waveform's source Location string, including `00`. Sensor and MERMAID model
descriptions and the former sea-level Elevation field are absent from rc2.

| Row type | Populated scientific fields |
| --- | --- |
| `gps` | `measured_time`, measured coordinates, optional `clock_offset` |
| `pressure` | `measured_time`, `measured_pressure`, optional estimated coordinates |
| `downcrossing`, `upcrossing` | `derived_time`, estimated coordinates and pressure; `time_correction_applied` is empty |
| `waveform` | `derived_time`, estimated coordinates, `location`, `channel`, `data_quality`, `sample_rate`, `sample_count`, `time_correction_applied`; measured pressure is required for DET and optional for REQ |

Every row retains its source `network` and `station`. Blank cells indicate
unavailable or inapplicable values; no zero is inferred for missing pressure.

Recording sampling frequency comes from the assigned acquisition-dive
`ENVIRONMENT/TRUE_SAMPLE_FREQ FS_Hz`, with the product's decimation applied.
It is not selected from a repeated EVENT header or inferred from DET/REQ
classification. [P0006 source evidence](../notes/p0006-historical-sample-frequencies/README.md)
records discrepancies whose cause remains unresolved.

Pressure rows preserve finite signed gauge readings as `measured_pressure` in
mbar. DET waveform rows preserve their source pressure in the same column;
REQ waveform pressure can be absent. Crossing `estimated_pressure` is a
configured boundary proxy, not a sensor reading. Shared conversions in
[`utils.py`](../scripts/utils.py) use the exact 100 mbar per dbar relation and
the explicit approximation that 1 dbar corresponds to 1 m of water depth.
The same helpers supply the mixed-layer pressure threshold, SAC receiver depth
and dive-plot depth.
Waveform and crossing pressures remain nonnegative. No atmospheric, density,
geoid or tidal correction is inferred.

The configured upper mixed-layer boundary is approximately 50 m deep; it is
not detected from a measured temperature profile. Descent exits its base and
ascent enters it. Crossing `estimated_pressure` converts the configured depth
to mbar using that shared approximation and is a boundary proxy rather than a
sensor measurement. The GPS interpolation
stability fallback can retain an anchor position and its epoch instead of a
crossing estimate. Crossing `derived_time` therefore need not be the physical crossing
epoch. Preserve this behavior and the existing interpolation model. Faster horizontal
drift in the upper layer is empirical; the model imposes no fixed velocity
ratio. Scientific context: [Nolet et al. (2024), pp. 2369, 2372](https://doi.org/10.1785/0220230377).

For cycles eligible for the existing full-dive GPS location calculation,
pressure rows also carry estimated coordinates at their uncorrected measured
times. The writer evaluates the existing piecewise surface, deep-water and
ascent segments only when both their physical phase and retained anchor epochs
bracket the measurement. Surface-layer positions use the original pre-dive or
post-dive GPS fixes so a second 20 m fallback is not applied to already
interpolated endpoints. The deep segment uses the same anchors as waveforms.
A missing or fallback position at the requested epoch leaves both estimated coordinates
empty. Init and IcCycle pressure rows remain measurements without these
estimates. Pressure times and waveform locations are not changed.

For each emitted waveform row, the writer evaluates that same dive trajectory
at the corrected first-sample time and requires the six-decimal estimated
coordinates to match the source trace Stats. If no bounded at-time estimate is
available, it checks against the event calculation's original anchor pair
without changing the waveform. The check compares position, not the helper's
returned epoch; the retained-anchor fallback is preserved.

## Ordering, deduplication and review

The writer sorts chronologically. Identical raw event headers and payloads
are deduplicated. Distinct raw events that render one identical row are saved
in adjacent `geo_DET_REQ-CLASHES.md`, `geo_DET-CLASHES.md` or
`geo_REQ-CLASHES.md` reports; the CSV contains the first rendered row.
Review clashes without silently changing source values or sampling-frequency
precedence. Repeated original waveforms can independently associate with one
`waveform` row.

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

The [fixture evidence](../../mermaid-geocsv/data/fixtures/schema-1.0.0-rc2/README.md)
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
shared pressure-to-depth approximation for MERMAID receiver (station) depth in SAC
`stdp`. This question concerns the station-depth approximation; earthquake-source
metadata and `ev*` projections remain outside package scope.

## Measurement retention and derived-row exclusion

From v4.9.2, GeoCSV collects GPS and pressure measurements from
every cycle, including Init and IcCycle wherever they occur. Identical repeated
pressure log messages still produce one row. Recording and
crossing rows are excluded from cycles whose `directory_name` contains
`IcCycle` or `Init`, case-insensitively. IcCycle derived outputs use preliminary
location inputs; Init derived outputs are excluded as a precaution. Recording
collection also excludes events whose processed filename contains either
substring, regardless of case. Excluded events do not enter the combined clash
report. The existing per-event preliminary-location exclusion remains in effect
for other events.
GPS/cycle algorithms, cleanup and waveform files are unchanged by this writer
policy.

`main.py` passes its resolved `filterDate` bounds into the writer as `begin`
and `end`. All formatted rows are selected with inclusive begin and exclusive
end (`begin <= row epoch < end`, using the populated time column). The earliest and latest GPS measurements retained
in that window then bound every normal output row, inclusively. This is a
GeoCSV writing policy; LOG selection and waveform exports are unchanged.
No additional GPS or pressure observations are inferred.

Excluded formatted rows from the combined DET/REQ dataset are written, sorted
and deduplicated under the existing row rules, to
`outside_filterDate_gps.geocsv` beside the normal files. It has the full schema
header, creation identity and producer description. Console counts identify excluded
row types. It includes rows outside either the deployment window or
retained GPS span; Init/IcCycle derived rows are never collected into either
output. With no GPS in the deployment window, the normal files are recordless
and all collected rows go to the sidecar. The normal clash report binds only
the normal combined file. The sidecar is local audit evidence and is not a
publication payload.

Saved-cycle callers can omit both bounds to apply only GPS bracketing; supplying
one bound without the other or a non-increasing window raises an error.

Publisher 0.6.1 independently excludes both substrings in waveform directory
names and filenames, case-insensitively. Fresh producer output is required to
align GeoCSV Recording coverage with that scope; old GeoCSV payloads are never
edited by the publisher. Regeneration needs a new creation identity and fresh
validation evidence. Source changes do not regenerate protected processed
products or establish new corpus acceptance.

## PPHC header and testing schema

The development writer emits dataset-first GeoCSV 2.0 with `schema: MERMAID
GeoCSV v1.0.0-rc2`, padded comment keywords, unquoted comma/LF declarations and
producer/publisher/hoster/consumer project descriptions. `references` is reserved
for the describing paper and omitted until its DOI exists. The rc2 workflow uses consumer 0.30.0
and publisher 0.9.0 with validation report schema 6.

Create a fresh candidate from the completed processed rebuild and validate all
original waveform pairs using the [publisher workflow](../../mermaid-publisher/docs/geocsv/workflow.md).

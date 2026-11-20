> **AI-written documentation**

# Relevance: v4.3.2 is the last version that created mSEED and GeoCSV deposited
# with EarthScope DMC in mid 2025.

# Automaid scientific design from v4.3.2 to v4.11.3

Comparison date: 2026-11-20.

The main scientific model is retained: associate recordings with acquisition
dives, reconstruct their first-sample times using measured sampling frequency,
estimate clock corrections from GPS synchronizations, and estimate receiver
positions using a configured two-layer trajectory. The largest changes concern
which calculations and products are eligible, how measured and derived values
are distinguished, numerical serialization, and preservation of source evidence.
The present code does not establish a new instrument timing or ocean-drift model.

## Comparison endpoints

| Endpoint | Exact source revision | Meaning |
| --- | --- | --- |
| v4.3.2 | `9c545790c4a3b6d1ba797536f3cd461fc0ae55ab` | Tag dated 2025-06-09 |
| Present | `fbdb291f4cf4d5e107142fc636eafb53eadba754` | HEAD dated 2026-11-20; `scripts/setup.py` reports `v4.11.3`; working tree initially clean |

**The present is newer than the `v4.11.3` tag.** That tag points to
`b86ea6745db5453beff0cb2dc983f842b0f44cb4`. The symmetric ten-second clock
screen, zero-pressure exclusions and decision reports were committed afterward
in `564a0c9`, without a further version-string change. Consequently, the label
`v4.11.3` alone does not identify the scientific behavior compared here.

The comparison uses endpoint source, rather than inferring behavior from
intermediate commit subjects. It describes code behavior; it does not imply
that canonical processed products have been regenerated with HEAD.

## Principal differences

| Scientific concern | v4.3.2 | Present |
| --- | --- | --- |
| Selected GPS clock anchors | Last pre-dive and first post-dive synchronization; frequency 3–4 MHz; signed `clockdrift < 5 s` | Same anchors and frequency range; explicit finite checks and `abs(clockdrift) < 10 s` |
| Position eligibility | Clock-anchor eligibility, then two synchronization entries within 5,400 s on each side | Same count/proximity design; no general clock-quality filter on all position inputs |
| Position model | Configured 50 m boundary, surface extrapolation and linear drift between submerged anchors | Retained, with an emergency-cycle exception and corrected longitude wrapping |
| Interpolation stability | Retains an input position **and its epoch** when the selected fixes are less than 20 m apart | Retained intentionally |
| Zero DET source pressure | No dedicated exclusion | Temporary exclusion from newly generated waveform products and GeoCSV waveform rows |
| GeoCSV scientific representation | 16 columns; method strings; one time, coordinate pair and pressure field | Sole supported payload is 18-column MERMAID GeoCSV 1.0.0-rc2, separating measured and derived quantities |
| GeoCSV time scope | Only pressure rows clipped strictly inside the GPS span | Every collected row bounded by deployment and retained GPS span; outside rows saved separately |
| GeoCSV numerical representation | Numeric narrowing to float32; millisecond timestamp truncation; sample rate to one decimal | Binary64 formatting; microsecond rounding; sample rate to six decimals; typed missingness and validation |
| BIN and source provenance | BIN decoding and LOG/MER association already present; flat working copies removed during cleanup | Retained MER/LOG/BIN copies and fragments; decoded LOG precedence made explicit; server-tree integrity checks |
| Scientific review evidence | Text diagnostics and output consistency checks | Adds GPS decision/exclusion JSONL and payload-bound clash evidence; independent consumer/publisher workflow |

## GPS gating and clock correction

### Two different eligibility decisions

Both endpoints distinguish clock-correction eligibility from normal location
interpolation eligibility. With the default settings, the calculation proceeds
as follows:

1. Use the cycle's existing pre-dive and post-dive synchronization lists.
   Membership requires non-missing clock drift and oscillator frequency.
2. Check the **last** pre-dive synchronization and **first** post-dive
   synchronization as clock anchors. An invalid selected anchor invalidates
   the cycle's clock correction and normal location interpolation. Neither
   endpoint searches for a replacement anchor or borrows from another cycle.
3. Once the anchors pass, require at least two synchronization-list entries
   less than 5,400 s before departure and less than 5,400 s after surfacing.
   A separation of exactly 5,400 s does not pass. Failing this count can leave
   clock correction eligible while normal location interpolation is ineligible.
4. Calculate positions from the original position lists, which can include
   fixes without usable synchronization metadata.

The count is **entries, not independently identified observations**. LOG and
MER representations are concatenated and sorted by `merge_gps_list()`; that
function does not reconcile them into one observation. Repeated representations
can satisfy the count. Non-anchor synchronization entries contributing to the
count are not individually required to pass the anchor frequency/drift checks.
Neither endpoint applies an HDOP/VDOP acceptance threshold.

The old signed inequality was not a five-second magnitude limit: a drift of
`-90 s` could pass while `+5 s` failed, provided the other conditions passed.
The present screen rejects both signs at magnitude 10 s or greater, but also
admits positive drifts from 5 s to just below 10 s that the old screen rejected.
It therefore changes eligibility in both directions. Ten seconds is documented
as an arbitrary, loose screening bound whose scientific justification remains
open. The oscillator interval remains inclusive, 3,000,000–4,000,000 Hz.

The present validation resets calculated cycle anchors and event metadata
before recomputation, preventing stale positions or Stats from surviving a
failed revalidation. `write_gps()` now formats absent values with local
variables instead of replacing `None` on the source GPS objects with NaN.
These changes support repeatable processing of saved cycles without changing
their observations or decoded samples.

Sources: [cycle validation and calculation](../scripts/cycles.py),
[GPS parsing, merging and clock checks](../scripts/gps.py), and
[scientific release review](../docs/scientific-release-review.md).

### The clock model and sign convention are retained

Let `t_b` and `t_a` be the pre-dive and post-dive GPS anchor epochs, `t_u` the
uncorrected recording first-sample epoch, and `d_a` the post-dive
GPS-minus-instrument clock drift. Both endpoints implement:

```text
fraction = (t_u - t_b) / (t_a - t_b)
correction = d_a * fraction
corrected_start = t_u + correction
```

This assumes a successful pre-dive reset and accumulated drift over the dive.
It does **not** interpolate between the two measured drift values: the pre-dive
drift is an eligibility input, but is not added as an intercept. The revised
gate does not resolve reset continuity, residual offset or firmware epoch
semantics.

GPS `mseed_time_delay`, now exported as `clock_offset`, is instrument time
minus GPS time. Waveform `mseed_time_correction`, now exported as
`time_correction_applied`, is estimated GPS time minus instrument time at the
recording epoch. These concern different instants and need not have equal
magnitudes. The waveform start already includes its correction. GPS and LOG
pressure measurement epochs, and modeled crossing epochs, do not receive the
recording correction.

Sources: [event timing](../scripts/events.py) and the
[clock timing matrix](../docs/clock-timing-matrix.md).

## Receiver position and pressure design

Both endpoints use a configured boundary of approximately 50 m rather than a
thermocline detected from CTD data. They estimate departure and surfacing
positions from surface GPS fixes, estimate boundary-crossing times from pressure
versus time, extrapolate surface positions to those crossings, and interpolate
recording positions between the resulting submerged anchors. Shallow dives use
the departure/surfacing pair. Latitude and longitude are interpolated in angular
coordinates; this remains a simple trajectory approximation, without a fitted
current model, fixed surface/deep velocity ratio or propagated uncertainty.

The meaningful changes and retained assumptions are:

- **Longitude wrapping is corrected.** v4.3.2 converted longitudes to
  `[0, 360)` before subtraction. That handles some antimeridian cases but
  mishandles prime-meridian crossings: `-1°` to `+1°` becomes `359°` to `1°`.
  The present uses the shortest signed longitude difference and wraps results
  to `[-180, 180)`.
- **Emergency cycles bypass the two-layer branch.** The present requires both
  a pressure maximum beyond the configured boundary and no emergency triggers
  for that branch. An otherwise GPS-eligible emergency cycle uses the
  departure/surfacing anchor pair. v4.3.2 selected the branch by depth alone.
- **The stability fallback is unchanged.** The GPS helper tries to obtain
  adequate temporal/spatial separation for extrapolation. If the retained
  pair remains less than 20 m apart, it returns the reference anchor's
  coordinates and epoch. A one-fix input also retains that fix's epoch.
  Substituting the requested epoch would change the scientific behavior.
  A GeoCSV crossing time can consequently be a retained anchor epoch rather
  than the estimated physical crossing time.
- **Pressure conversions are centralized, not replaced.** `1 dbar = 100 mbar`
  is an exact unit relation; `1 dbar ≈ 1 m` is the retained depth approximation.
  Current shared helpers supply the layer threshold, DET SAC receiver depth
  and plotting conversions. There is no new density/gravity calculation or
  atmospheric, tidal or geoid correction. Signed LOG gauge readings remain
  measurements; the configured crossing pressure is a proxy.
- **Layer terminology is clarified.** Legacy code calls the upper mixed layer
  the “surface layer” and the deeper layer the “mixed layer.” Current comments
  and documentation identify that reversal without changing the model.

Both endpoints default to `preliminary_location_ok = False`. Enabling that
option uses weaker position inputs when normal eligibility fails; preliminary
waveforms are excluded from normal GeoCSV waveform rows. Neither endpoint
automatically rejects a trajectory based on horizontal velocity or extrapolation
duration. The present cycle calculations pass copies into the interpolation
helper so its in-place sorting does not reorder the original candidate lists.

Sources: [trajectory construction](../scripts/cycles.py),
[interpolation](../scripts/gps.py), [conversions](../scripts/utils.py), and
[producer scientific source rules](../docs/geocsv.md).

## GeoCSV representation and gating

### Scientific fields and precision

v4.3.2 used `MethodIdentifier` strings to distinguish GPS, pressure, event
algorithm and thermocline algorithm rows. Its 16-column table shared
`StartTime`, `Latitude`, `Longitude` and `WaterPressure` across measurements and
estimates. Both crossing directions used the same method identifier. It also
carried `Elevation` with missing values and an `InstrumentDescription` repeated
on rows. Sensor names were embedded in measurement method identifiers.

The present supports only MERMAID GeoCSV 1.0.0-rc2, in a dataset-first GeoCSV
2.0 container. Its five types are `gps`, `pressure`, `downcrossing`,
`upcrossing` and `waveform`. The exact columns are:

```csv
type,measured_time,derived_time,network,station,location,channel,data_quality,measured_latitude,measured_longitude,estimated_latitude,estimated_longitude,measured_pressure,estimated_pressure,sample_rate,sample_count,clock_offset,time_correction_applied
```

GPS and pressure use measured times; crossings and waveforms use derived times.
Only GPS rows have measured coordinates. Waveform coordinates are estimated
receiver positions at the corrected first sample, not earthquake coordinates.
Crossings have estimated boundary pressure; pressure and waveform rows carry
measured pressure where available. Missing REQ pressure remains missing.
Elevation, row-level instrument descriptions and method identifiers are removed;
the header records the instrument serial and producer version. This is an
incompatible payload change, not a rename-only migration. The current reader
does not provide a legacy-schema fallback.

The old writer narrowed numerical values through `np.float32`, formatted rates
to one decimal and truncated UTC strings to milliseconds. The present avoids
float32 narrowing, writes rates and coordinates to six decimal places, and
rounds UTC to six fractional digits with decimal ties to even. Precision in
the representation does not establish measurement accuracy. Empty CSV cells
replace old `nan` missing markers; a known blank waveform location is exactly
two ASCII spaces, distinct from a missing identity and from `00`.

Current validation checks row-specific required/applicable fields, finite
numbers, coordinate ranges, positive rates/counts, pressure constraints and one
network/station per file. Non-finite required values raise. Pressure observations
can be signed; waveform and crossing pressures must be nonnegative.

Sources: [present writer](../scripts/geocsv.py),
[rc2 schema](../../mermaid-geocsv/docs/format-spec.md), and baseline
`git show v4.3.2:scripts/geocsv.py`.

### Modeled pressure positions and waveform consistency

v4.3.2 pressure rows had no positions. The present can attach estimated
coordinates at an uncorrected pressure measurement time using the existing
surface, submerged and ascent trajectory segments. Both the physical phase
and retained anchor epochs must bracket that measurement. If the helper cannot
provide a position at the requested epoch, both coordinates remain empty.
Init and IcCycle pressure rows remain measurements without these estimates.
The underlying pressure series is still the cycle's LOG pressure observations;
SBE/RBR CTD profile samples are not inserted into these GeoCSV rows.

For waveform rows, the present checks that the source Stats start matches the
corrected event start and that the serialized coordinates match the trajectory
at that instant. If no bounded at-time estimate exists, it checks the original
event anchor pair, preserving the stability fallback. It raises on disagreement
instead of silently changing the waveform position.

One unresolved consequence is that the event calculation uses the submerged
anchor pair for every recording in a two-layer dive, while the GeoCSV trajectory
check uses phase-specific segments. A synthetic shallow recording produced a
conflict and stopped GeoCSV generation after waveform writing. Its prevalence
in real data remains unverified.

### Product scope and time windows

Both endpoints write combined DET/REQ and separate DET and REQ files, each
including measurement context. v4.3.2 collected measurement rows from every
supplied cycle and skipped preliminary event positions. Only pressure rows
were clipped to times **strictly inside** the first/last GPS epochs; without
GPS, its `IndexError` handling left that pressure filtering unapplied.

The present retains measurement collection from every cycle but explicitly
excludes derived rows from cycle names containing `Init` or `IcCycle`,
case-insensitively. Waveform collection also excludes those substrings in
processed filenames. It then applies these independent writing constraints:

1. The resolved deployment window is inclusive at its beginning and exclusive
   at its end: `begin <= row_time < end`.
2. GPS rows retained in that window define an inclusive first/last GPS span.
   **Every** normal output row must lie inside it, using its populated time
   column. Pressure measurements exactly at the GPS endpoints can now remain.
3. Formatted rows outside either window go to
   `outside_filterDate_gps.geocsv`. With no retained GPS, normal files are
   recordless and all collected rows go to that local audit file. Init/IcCycle
   derived rows were never collected, so do not appear there either.

These are GeoCSV writing rules. They do not change LOG event-selection
intervals or independently impose the same time window on waveform exports.
GPS observations with failed clock-anchor checks can still be retained as
measurement evidence; the calculation gate does not delete them.
`main.py` passes its `filterDate` bounds to the writer. Saved-cycle callers
can omit both deployment bounds to apply only GPS bracketing; supplying just
one bound or a non-increasing window raises.

### Deduplication and exclusion evidence

The old event writer suppressed adjacent identical rendered rows without
comparing raw source events. The present groups by rendered row and compares
raw EVENT headers and payload bytes within each group. Identical variants
collapse; distinct variants that render to one row retain the first CSV row
and produce clash evidence. Each GeoCSV variant is deduplicated independently.
This does not establish decoded-sample equivalence or reconcile conflicting
acquisition metadata. Adjacent duplicate pressure-message suppression remains.

The present adds a SHA-256-bound `geocsv-clash.json` for the combined payload,
with source row/line references, associated MiniSEED basenames, header differences
and a payload-equality flag. Human-readable clash files are also written when needed.
`gps-validation.jsonl` records cycle eligibility and rejected original clock
anchors. `excluded-waveforms.jsonl` records source-event hashes, available
times, acquisition/log provenance, pressure and exclusion reasons. These
decision sidecars are local evidence outside the rc2 payload.

An explicit zero DET source pressure now triggers the temporary
`zero_receiver_depth_pending_review` exclusion. Fresh MiniSEED/SAC outputs,
waveform plots, waveform metadata tables and all GeoCSV waveform variants omit
that recording. The raw event is preserved, and missing REQ pressure remains
permitted. The firmware meaning of zero remains unresolved; zero is not silently
replaced by an assumed depth. Existing output files are not purged by this guard.

Source: [producer rules and exclusions](../docs/geocsv.md) and
[event export guards and reports](../scripts/events.py).

## BIN LOG and MER source handling

BIN, LOG and MER already had distinct responsibilities in v4.3.2:

- BIN contains encoded log records decoded using model/firmware database cards.
  The code calls this “decrypt,” but these routines interpret record formats.
- LOG provides dive chronology, pressure, GPS and acquisition associations.
  LOGs are assembled into cycle histories, including histories spanning files.
- MER contains environment metadata and binary recording/PSD EVENT blocks.
  A transmission can contain recordings acquired during earlier dives.

Both endpoints concatenate working fragments, decode BIN to same-stem LOG,
parse MER EVENT blocks, and select recordings by their uncorrected `INFO DATE`
inside LOG intervals. The acquisition LOG's environment supplies
`TRUE_SAMPLE_FREQ FS_Hz`, which is adjusted for transmitted wavelet scales.
The later transmission's EVENT `TRUE_FS` is not the selected authority. If the
LOG has no environment, the existing fallback uses the first selected event's
transmission environment. The [P0006 source comparison](p0006-historical-sample-frequencies/README.md)
shows disagreements between historical EVENT and acquisition-environment rates;
the present does not resolve their cause or change this precedence.

The present makes provenance more accessible: per-instrument `MER/`, `LOG/`
and `BIN/` directories retain copies and relevant numbered fragments before
flat working files are cleaned up. Successful decoded LOGs are copied into
`LOG/`, superseding a same-stem server LOG there as well as in the working
directory. Thus `LOG/` is not necessarily a verbatim archive of every original
server LOG; the protected server remains the reference for those bytes.
Output/server overlap checks and before/after server fingerprints protect the
source tree. Cycle objects are also saved in per-instrument pickle files.

LOG parsing now accepts GPS coordinates under broader state labels, optional
`P`/signed pressure forms, and a less restrictive cycle-boundary bypass message.
These changes support newer float logs and can change which observations and
cycles are recognized. BIN decode cards are initialized per file; blank-format
records and embedded timestamps receive revised formatting.

Several inherited source-selection limitations remain: EVENT objects are shared
across overlapping LOG selections; a missing MER environment match can retain
the preceding file's local environment; DET parsing requires six fractional
digits; REQ `INFO DATE` loses fractional seconds before LOG association; and
the early-LOG-timestamp replacement branch discards `str.replace()`'s result.
Reset-era dates, incomplete EVENT framing and payload-length failures can be
discarded before the new exclusion reports apply. Those reports are therefore
not a complete inventory of every raw recording rejected by the pipeline.

Sources: [processing orchestration](../scripts/main.py),
[preprocessing](../scripts/preprocess.py), [LOG assignment](../scripts/cycles.py),
and [documented source-selection limitations](../docs/scientific-release-review.md).

## Waveforms identifiers and other scientific products

**First-sample reconstruction and waveform transforms are retained.** DET
starts use `INFO DATE - TRIG / decimated_fs`, with a zero-based trigger index.
REQ starts use acquisition-file `FNAME + SMP_OFFSET / measured_fs`. Wavelet
reconstruction and raw int32 decoding have no new algorithm in the endpoint
diff; the C transform sources are unchanged. Requested RAW data remain within
the REQ model; a separate recovered continuous-buffer product is still deferred.

**DET Q and REQ D already exist in v4.3.2.** They are retained at HEAD, as are
the `?DH` channel suffix and sampling-rate band selection. The new identity
change is the Location mapping: v4.3.2 assigned `00` universally; current
metadata distinguish nominal rates/transmitted scales as follows:

| Product | Nominal rate | Location |
| --- | --- | --- |
| RAW, `STAGES=-1` | 40 Hz | `10` |
| WLT5 | 20 Hz | `00` |
| WLT4 | 10 Hz | `20` |
| WLT3 | 5 Hz | `30` |
| WLT2 | 2.5 Hz | `40` |
| WLT1 | 1.25 Hz | `50` |

The helper requires measured acquisition frequency to round to 40 Hz and rejects
unexpected scale values. This changes SNCL identity without resampling the data.
Current filename classification also uses `is_requested`; a present `TRIG=0`
is correctly named DET, whereas the old truth test named it REQ despite its
DET classification elsewhere.

**MiniSEED serialization is more explicit.** Both endpoints already write
corrected starts, set the applied bit and iterate over record headers. Current
code replaces float-to-int truncation with nearest 0.0001 s correction ticks,
using decimal ties to even and finite/signed-32-bit checks before mutation.
It independently reads every record back to verify the applied bit and integer
correction, including zero. This changes correction-history serialization, not
the clock model or waveform start. Support remains limited to the producer's
normal big-endian, uniform-record-length output; the flag setter still has
other-flag implications. See the [clock matrix](../docs/clock-timing-matrix.md)
and its primary [SEED 2.4 reference](https://www.fdsn.org/pdf/SEEDManual_V2.4.pdf).

**SAC storage and calibration assumptions remain.** SAC holds float32 samples
and approximate receiver depth, while MiniSEED retains integer samples. The
existing sensitivity/SAC SCALE convention is not revised here; independent
raw-count comparisons use `apply_calib=False`. Agreement between local formats
does not validate the instrument response or downstream EarthScope processing.

**CTD support expands.** v4.3.2 handled SBE41/SBE61 profiles. The present adds
RBR fragment assembly, channel-based datasets, park/ascent profiles, CSV and
plots. SBE outputs also gain temporary `.ctd` sidecars carrying the earliest
available same-cycle GPS fix after the profile timestamp, or explicit
unavailability. That fix is not an interpolated profile trajectory or a
demonstration of profile timing/location accuracy. CTD pressure datum, timing,
quality control and Argo qualification remain open. Stanford percentile PSDs
remain separate from waveform rows; the hard-coded 40 Hz axis, int8 offset
arithmetic and reader compatibility issues are not resolved by this comparison.

Sources: [event timing and export](../scripts/events.py),
[identity and serialization helpers](../scripts/utils.py),
[RBR reader](../scripts/rbr.py), [CTD formats](../docs/CTD_file_formats.md), and
[scientific release review](../docs/scientific-release-review.md).

## Verification publication and remaining limits

The present adds flat waveform/metadata symlink mirrors and makes completed
processed trees read-only. Mirrors exclude `IcCycle` directories, while GeoCSV
derived-row exclusion and publisher inventory exclusion have their own scopes;
these mechanisms should not be treated as one universal eligibility gate.
Both endpoints reuse some existing waveform/plot files based on filename
existence. A code update or metadata-only regeneration therefore does not prove
that existing waveform files implement the present decisions. Fresh output
directories are required for an interpretable release comparison.

The adjacent ecosystem now separates scientific generation from consumer
parsing/association, publisher validation and read-only hosting. The inspected
consumer is 0.30.0; publisher documentation specifies 0.9.0 and report schema 6.
The consumer implements rc2, the publisher independently checks GPS bounds and
original MiniSEED/SAC associations, and the Worker serves bytes without
performing producer calculations. Their contracts agree on rc2 and testing-only
publication. Several compatibility passages still name producer 4.11.2; those
passages do not establish acceptance of HEAD's scientific changes.

For this comparison, the existing focused suite ran in conda `pymaid3.10`:

```sh
PYTHONDONTWRITEBYTECODE=1 MPLBACKEND=Agg MERMAID_BACKEND=Agg \
  conda run -n pymaid3.10 python -B -m unittest discover \
  -s tests_and_verifications -p test_scientific_eligibility.py -v
```

All **13 tests passed**, covering both signs and exact ten-second boundaries,
invalid-anchor preservation, non-anchor position inputs, the original count
gate, stale-state clearing, source-object preservation, zero-pressure exclusion,
REQ missing pressure, `TRIG=0`, longitude/stability behavior and independent
MiniSEED/SAC serialization read-back. These are focused synthetic checks of
the present source, not a v4.3.2-versus-HEAD full-corpus comparison.
Source comparison also confirmed unchanged executable bodies for sampling-rate
selection, first-sample reconstruction, sample decoding, clock correction and
event-position interpolation; all 29 local document links and the stated column
order were checked.

The retained 112-instrument GeoCSV comparison in the
[release review](../docs/scientific-release-review.md) used an earlier symmetric
**five-second** candidate. Its counts and acceptance cannot be transferred to
the present ten-second policy. No full-corpus rebuild or publication was
performed for this note. The publisher's [evidence index](../../mermaid-publisher/docs/geocsv/evidence.md)
still calls for fresh rc2 corpus evidence after a completed rebuild.

Final cross-repository inspection covered the current implementations and
relevant contracts at consumer `fb1489aee434d8c257ba0a95fe943a5481e88f22`,
publisher `0d6cc0a6968e9b712fc5a71bc029164625581d96`, and site
`16a8e343852c309b2f84dafd1c1337c5146dbc73`. These repositories were read-only
references for this comparison. Relevant references are the
[consumer schema](../../mermaid-geocsv/docs/format-spec.md),
[publisher contract](../../mermaid-publisher/docs/geocsv/contract.md) and
[site hosting status](../../bathymetrix-site/docs/geocsv-hosting.md).

The remaining scientific questions concern the appropriate clock bound and
reset model, whether failed acquisition-clock metadata invalidates GPS position
or epoch, observation identity for repeated GPS entries, shallow-recording
trajectory consistency, acquisition-rate precedence, transform/trigger phase,
CTD qualification and calibration. Better field separation and stronger
verification expose these questions; they do not settle them.

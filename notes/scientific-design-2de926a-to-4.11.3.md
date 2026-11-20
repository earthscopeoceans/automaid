> **AI-written documentation — non-authoritative.** This comparison combines source inspection and synthetic checks. Confirm instrument-specific interpretations against firmware documentation, original observations and authoritative calibration evidence before changing scientific behavior.

# Relevance: last Sebastien version before Joel started working on it.

# Scientific design comparison from 2de926a to v4.11.3

Comparison date: 2026-11-20.

The first-sample timing equations, measured-rate decimation, linear accumulated
clock correction, configured 50 m layer boundary and inverse wavelet kernels
already exist at `2de926a`. Present processing substantially changes the
selection and provenance of their inputs, the meaning of interpolation fallback
epochs, scientific metadata and product eligibility. GeoCSV, BIN decoding and
CTD/PSD products are later additions.

The most concrete current concerns are an inconsistency between SAC calibration
metadata and the producer's pressure conversion, duplicate source representations
passing the position-count gate, and a waveform/GeoCSV trajectory disagreement.
Acquisition-environment fallback,
changed interpolation epochs, emergency handling and exclusion policies also
need scientific qualification. A demonstrated source-level problem does not
establish its prevalence in the archive; those distinctions are maintained below.

## Endpoints and evidence scope

| Endpoint | Source identity | Scope |
| --- | --- | --- |
| Historical baseline | `2de926a84f2b04d5c6bf8a61b38e46105b3eb22d`, dated 2019-12-19 | Python 2.7 source, principally `dives.py`, `events.py`, `gps.py`, `utils.py` and `main.py` |
| Present | `5bfb14275056d913da3e26074ae608ed47ecddea`, dated 2026-11-20 | Python 3 source; `setup.get_version()` returns `v4.11.3` |

The historical commit is an ancestor of present HEAD. The `v4.11.3` tag itself
points to `b86ea6745db5453beff0cb2dc983f842b0f44cb4`, before the subsequent
eligibility/exclusion changes in `564a0c9`. The present commit, rather than the
version string alone, defines the current behavior in this comparison.
The present source code is unchanged from `fbdb291`, the review's starting
revision; the intervening commit adds the earlier comparison note.

The earlier [v4.3.2 comparison](scientific-design-v4.3.2-to-4.11.3.md) covers a
more recent baseline. This note independently compares the 2019 source and gives
additional attention to changes that could compromise scientific interpretation.
Existing notes and canonical products were preserved. No production pipeline,
source-server refresh, corpus rebuild or publication was run.

## Design differences at a glance

| Concern | Historical baseline | Present |
| --- | --- | --- |
| Processing unit | One Dive per assembled LOG; next Dive supplies additional post-surface positions | Preprocessed cycles combine LOG histories and assign pre/post-dive GPS candidates |
| Source acquisition | LOG/MER and numbered LOG fragments; source-file dates filtered before parsing | BIN decoding, broader fragment handling, retained source copies and server integrity checks |
| Acquisition environment | LOG-named MER environment supplies rate and transform parameters; missing named files can stop processing | Same normal precedence, plus fallback to the first selected event's transmission environment |
| Event timing state | One mutable `date` moves from INFO time to first sample to corrected first sample | Separate `info_date`, `uncorrected_starttime` and `corrected_starttime` |
| Clock anchors | Final two entries in the reconciled Dive GPS list, interpreted as pre/post-dive | Last pre-dive and first post-dive synchronization selected by phase |
| Clock eligibility | Complete-dive/GPS checks and positive anchor frequencies; no magnitude bound | Finite anchor frequencies in 3–4 MHz and finite absolute drift below 10 s |
| Position eligibility | Complete Dive, enough current/next GPS entries and a complete GPS list | Clock eligibility plus two synchronization entries strictly within 5,400 s on each side |
| GPS reconciliation | Substitute MER fixes for LOG fixes within a strict ±60 s window; unmatched LOG fixes retained | Concatenate and sort LOG and MER entries, retaining both representations |
| Sub-20 m fallback | Return reference coordinates at the requested epoch | Return reference coordinates at the reference anchor's epoch |
| Longitude | Direct subtraction across ±180° | Shortest signed longitude difference with wrapping |
| Two-layer model | Configured 50 m crossing; all recordings use submerged anchors when threshold reached | Same basic model; emergency-trigger cycles use surface departure/arrival anchors |
| Calibration | Positive scalar conversions, with different utility and PNG formulas; no explicit SAC SCALE | Nominal conversion divides by −149400; SAC SCALE stores −149400 |
| Scientific identity | Network MH, numeric station suffix; no explicit channel/Location assignment in the writer | Padded station identity, `?DH` channels and scale-based Location codes; DET Q and REQ D |
| Metadata products | SAC, optional MiniSEED, plots, KML, vitals and a saved Dive collection | Adds rc2 GeoCSV, measurement/decision/clash evidence, mirrors, CTD and Stanford PSD products |

## Current behavior that warrants scientific review

The findings distinguish **demonstrated inconsistencies**, **demonstrated
mechanisms with unmeasured archive impact**, and **model or policy changes whose
scientific validity remains unresolved**. They do not treat historical output
as a physical truth standard.

### 1 SAC calibration metadata conflicts with the pressure conversion

**Assessment: demonstrated inconsistency introduced after the baseline.**

The present stores waveform samples as counts and writes
`stats.sac['scale'] = -149400`. Its plotting conversion instead computes
`counts / -149400`, with the result labeled pascals. ObsPy maps SAC SCALE into
`stats.calib`, and its `apply_calib=True` path multiplies samples by that value.
Those two operations are incompatible interpretations of the same calibration.
The mappings are explicit in the primary
[ObsPy SAC conversion source](https://docs.obspy.org/_modules/obspy/io/sac/util.html)
and [waveform reading source](https://docs.obspy.org/_modules/obspy/core/stream.html).

This finding concerns the ObsPy calibration contract. The current
[SAC format manual](https://ds.iris.edu/files/sac-manual/manual/file_format.html)
labels the fourth float header word, zero-based word 3, `UNUSED`, without a
SCALE declaration. ObsPy's [header table](../../obspy/obspy/io/sac/header.py)
still names that slot `scale` and describes a multiplying scale factor.
The present mismatch therefore does not establish that current SAC itself
requires a counts-to-pascals factor in this slot.

If −149400 is adopted as a scalar sensitivity in counts/Pa, the corresponding
ObsPy multiplicative conversion is its reciprocal,
`1 / -149400 = -6.693440428380187e-6 Pa/count`. Establishing that reader
convention does not establish that this empirical pole-zero constant is the
appropriate scalar sensitivity for every instrument and epoch.

A scratch serialization/read-back check with installed ObsPy 1.4.1 gave:

| Quantity | Result |
| --- | --- |
| Original synthetic counts | `[1, 2, -3]` |
| Historical-writer SAC, `apply_calib=False` | `[1, 2, -3]`; reader calibration factor 1 |
| Present SAC, `apply_calib=False` | `[1, 2, -3]`; reader calibration factor −149400 |
| Present SAC, `apply_calib=True` | `[-149400, -298800, 448200]` |
| Present plotting conversion for one count | `−0.000006693440428380187 Pa` |

For the first sample, the calibrated-reader result is 22,320,360,000 times the
producer's nominal pressure conversion. This demonstrates a reader/header
contract problem. It does **not** show that raw waveform samples were scaled
incorrectly on export, nor that the default ObsPy read applies calibration;
`apply_calib` defaults to false. The mismatch becomes consequential when a
consumer requests or otherwise uses the calibration factor.

The history also contains a real amplitude/polarity change:

| Scalar used as a divisor | Numerical value |
| --- | ---: |
| Historical `utils.counts2pascal()` formula | +134986.35692722283 |
| Historical default PNG conversion formula | +170176.61073183763 |
| Present plotting conversion | −149400 |

Thus the historical implementation itself did not have one consistent scalar
conversion. Present plotting reverses polarity and changes amplitude relative
to either historical expression. The negative value was introduced as an
empirical pole-zero constant in `edc431f` on 2021-07-28. Whether that constant
is the appropriate scalar sensitivity for each instrument, epoch and passband
requires the response model and calibration evidence. A pole-zero constant's
name alone does not establish that interpretation. Neither endpoint performs
full frequency-dependent response removal in these plotting conversions.

The [response source-status policy](../../mermaid-response/SOURCE_STATUS.md)
explicitly treats supplied response models as provisional. It would be
scientifically unjustified to declare either historical scalar universally
correct, apply the newer scalar to every hardware generation without checking,
or describe matching raw MiniSEED/SAC samples as validation of calibration.
Resolve the intended units and reader behavior before changing metadata or
pressure conversions.

Sources: current [conversion helpers](../scripts/utils.py),
[SAC Stats and plotting](../scripts/events.py); historical `events.py`
`plot_png()` and `get_stream()`, and `utils.py` `counts2pascal()`.

### 2 Transmission environment fallback requires an acquisition association

**Assessment: demonstrated new substitution path; incorrect production
assignments have not been established.**

`<ENVIRONMENT>` blocks belong to MER files. LOG files do not contain them.
The Python `Log.mer_environment` attribute holds a MER environment obtained by
following the MER reference recorded in a LOG. Failure to obtain that block can
mean an absent or unrecognized reference, a missing/empty MER, or an absent
environment block in that MER.

Grouping multiple LOGs into a cycle supports reconstruction of fragmented,
interrupted or incomplete dive histories. This is a useful recovery design.
The normal source rule is to obtain the environment describing acquisition,
using the LOG/MER associations as evidence. That environment supplies measured
sampling frequency and wavelet normalization/edge-correction parameters.

The present `Log` constructor also selects events when the LOG-associated MER
environment could not be obtained, then uses
`self.events[0].default_mer_environment`. That is the environment carried by
the first selected event's transmission MER. It is applied to every selected
event in the LOG. The baseline's event assignment was inside the LOG-named-MER
branch and had no equivalent substitution path.

This fallback can be correct when the selected transmission MER environment
describes the same acquisition cycle. Membership of the recording in a cycle
does not alone establish that relationship: events are selected by their INFO
timestamps within LOG intervals, independently of the containing transmission
MER. For example, a recording acquired in cycle A can be transmitted in a MER
whose environment describes cycle B. Selection by the recording's INFO time
places it in A while its transmission default still describes B. This example
illustrates the distinction; no actual erroneous fallback association has been
established here.

An independently established association of that MER environment with the
acquisition cycle would support its use. The current fallback does not search
the other cycle LOGs for that evidence: each `Log` processes its selected events
while the cycle's LOG objects are being constructed.

The fallback entered the cycle implementation in `c320ee2` on 2024-09-06.
It replaced a guard that processed selected events only when the LOG-associated
MER environment was available with an assignment from the first event's transmission environment,
followed by an unconditional processing loop.

A synthetic LOG with no resolvable MER environment led to a measured rate of
40.02 Hz from this fallback while `event.mer_environment_name` remained `None`.
This demonstrates assignment without an identified acquisition MER filename;
it does not demonstrate that the selected parameters were wrong. A transmission
can occur after acquisition, and an incorrect environment association could
alter first-sample time, sample rate and sample reconstruction parameters.

The [P0006 source evidence](p0006-historical-sample-frequencies/README.md)
establishes actual disagreements between historical EVENT `TRUE_FS` values
and acquisition-environment rates. For scale, a sample offset of 9,618,902 gives
a 0.072090928 s difference between reconstruction at 40.014095 and 40.014107 Hz.
This is an illustrative calculation using the documented values, not evidence
that this specific recording used the fallback. The normal environment-rate
precedence was already present in 2019 and is not itself a new regression.

The present MER-reading loop also leaves its environment local unchanged when
an environment match fails. A following file can therefore inherit the
preceding file's environment, or fail if none has been assigned. This mechanism
was absent from the baseline global EVENT reader. The incidence and effects of
either mechanism require tracing actual acquisition assignments, not selecting
an apparently plausible rate or copying parameters between recordings.
The per-file environment/default-environment path entered in `10d30a8` on
2024-09-04. If file A supplies an environment and file B does not, the local
variable can still hold A's environment when B's Event objects are constructed.
Normal assignment from a valid LOG-associated acquisition MER environment supersedes that
default; a stale transmission default therefore does not by itself prove that
a final waveform was processed with the wrong environment.
The 2019 Dive constructor instead required the LOG-named MER environment and
could stop when it was missing. These specific substitution paths are later
changes; shared Event references and broader association ambiguities have an
inherited basis.

Sources: [Log assignment](../scripts/cycles.py), [MER reading and rate selection](../scripts/events.py),
and [retained source-selection questions](../docs/scientific-release-review.md).

### 3 Preserving both GPS representations weakens the meaning of a two-fix gate

**Assessment: demonstrated count-gate weakness associated with changed
reconciliation; physical observation identity remains unresolved.**

The historical merger iterated over LOG fixes. A MER fix strictly within
±60 s replaced its corresponding LOG fix; otherwise the LOG fix remained.
The present merger simply concatenates both lists and sorts them. Retaining
both source representations improves provenance, but it does not establish
two independent positions or synchronizations.

There are three distinct implementations in this history:

| Period | Reconciliation behavior |
| --- | --- |
| 2019 endpoint | Prefer the complete nearby MER fix over the LOG fix; no hybrid time/location object |
| 2021 through the pre-cycle implementation | Merge matching representations into a unique fix with MER time/drift/frequency and LOG position/HDOP/VDOP, retaining separate source provenance |
| September 2024 cycle rewrite onward | Concatenate and sort the original representations; the hybrid object and unique-fix merger are removed |

The hybrid merger was introduced through `25d4943` on 2021-04-02 and
`387501c` on 2021-04-06. Its pairing predicate used less than 60 s time
separation and less than one microsecond clock-drift difference. Commit
`ff943e7` on 2024-09-09 replaced the active `gps.py` implementation with the
current concatenating merger and removed `GPS_unique`, `GPS_nonUnique` and
the `mer_time_log_loc()` source check. Thus the hybrid-merger removal is a
separate later change from the simpler reconciliation at the 2019 endpoint.

In a synthetic case representing one observation in both sources, the historical
merger returned one entry and the present merger returned two. With one such
pair before the dive and one after, the present default location gate passed.
All clock fields were valid, and both members on each side had identical times
and coordinates. The nominal two-entry requirement therefore did not establish
two distinct observations or a measured surface velocity.

The interpolation helper may then fall back to a retained point, or choose a
different pair among nearby representations. That is scientifically different
from a trajectory supported by independent, separated fixes. Clock checks on
the selected anchors do not repair observation counting. The proximity gate
also counts synchronization entries, not all available positions: two genuine
position-only observations can be insufficient while repeated synchronization
representations can pass.

Neither endpoint enforces a 15-minute acquisition interval or requests a new
GPS measurement. Both interpolation helpers try to select fixes at least
10 minutes apart for surface extrapolation, but that search is best effort:
it can run out of candidates and use the stability fallback. Reconciliation
normally prevents a matched LOG/MER pair from supplying both members of a
two-entry list; the present count gate does not provide that distinction.
The 2019 post-dive position list also included fixes from the next Dive.
These mechanisms improve access to a separate observation when one exists,
but do not prove a hard minimum separation or guarantee that a second
independent observation was obtained.

The historical ±60 s rule was not a general identity solution: several MER
fixes could match a LOG fix, and MER-only fixes were omitted. Restoring that
rule without source evidence would introduce its own assumptions. Retain the
observations and distinguish raw representation count from independent-fix
support before changing calculation eligibility.

Sources: current [GPS merger](../scripts/gps.py) and
[cycle count gate](../scripts/cycles.py); historical `gps.get_gps_list()`.

### 4 Waveform and GeoCSV trajectories disagree for a shallow recording

**Assessment: demonstrated present product inconsistency; the all-recordings
submerged-anchor assumption is inherited.**

When a dive exceeds the configured boundary, both endpoints calculate positions
for every recording using the submerged anchor pair, even for a recording
during the shallow descent or ascent. The present GeoCSV writer introduces a
piecewise surface/submerged/ascent trajectory for pressure positions and checks
waveform coordinates against it at corrected first-sample time.

A synthetic eligible dive used pressure observations of 1,000 mbar at 10 s,
9,000 mbar at 100 s and 900 s, and 1,000 mbar at 990 s; the configured boundary
was 5,000 mbar. A shallow DET recording had an uncorrected start of 20 s.
Present calculation and waveform writing succeeded, but GeoCSV raised
`Waveform location differs from dive interpolation`. Both the MiniSEED and SAC
files already existed in the scratch directory when that error occurred.

The new check usefully exposes a disagreement; removing it would not resolve
the scientific ambiguity. Define which trajectory applies to recordings in
each physical phase, including those spanning phases, and make the resulting
products agree. The check validates a position at the first sample, not an
average position over the waveform. No archive-wide count of affected real
recordings was established here.

Sources: [cycle trajectory](../scripts/cycles.py) and
[GeoCSV trajectory comparison](../scripts/geocsv.py).

### 5 Retaining a fallback anchor epoch changes downstream modeled positions

**Assessment: intentional model change with demonstrated numerical effects;
not established as physically wrong.**

In the 2019 GPS helper, a selected pair less than 20 m apart caused reference
coordinates to be returned **at the requested epoch**. Present code returns
those coordinates **at the reference observation's epoch**. Commit `1ee1ca2`
on 2020-11-20 made this distinction explicit to avoid assigning a distant
requested time to a position for which interpolation was not performed.

This is a change in the inputs to the subsequent trajectory, not merely more
complete provenance. A synthetic example at latitude −10° used:

- Surface fixes at −600 s/−151° and −100 s/−150.99999° longitude.
- A requested descent-crossing epoch of +50 s.
- A second submerged anchor at +950 s/−150.99° longitude.
- A recording position requested at +400 s.

Both helpers returned the same fallback coordinates for the descent anchor.
The historical helper returned its epoch as +50 s; present returned −100 s.
Subsequent recording longitudes were −150.996105° and −150.995232857143°,
respectively, a difference of approximately 95.62 m. These are constructed
values illustrating the mechanism, not observed archive errors.

The current behavior is scientifically defensible as an explicit statement
that no at-time position was obtained. The concern is how downstream code uses
that statement: a retained surface observation becomes an anchor of the
submerged trajectory. Current GeoCSV also labels such retained anchor epochs
as `downcrossing` or `upcrossing` derived times, even though they need not be
the physical boundary-crossing times. The producer documentation discloses this,
but the row type alone can be misinterpreted.

Whether the desired model should preserve an observation epoch, hold a position
constant to the physical crossing, or leave the crossing unavailable is a
scientific design decision. Preserve the existing intentional fallback during
this audit; do not silently retime it or treat the older choice as automatically
more correct.

Sources: [GPS fallback](../scripts/gps.py), [trajectory construction](../scripts/cycles.py),
and [documented crossing semantics](../docs/geocsv.md).

### 6 Numeric SAC elevation is asserted without a measured elevation source

**Assessment: new metadata assumption requiring qualification.**

The baseline did not explicitly populate SAC STEL. Present output assigns
`STEL=0` with a sea-level-reference comment, independently of receiver pressure
and depth. The [SAC format reference](https://ds.iris.edu/files/sac-manual/manual/file_format.html)
defines STEL as station elevation above sea level, and STDP as station depth
below surface. A reference datum and an observed submerged sensor elevation
are different quantities. A consumer treating STEL as receiver altitude can
therefore receive a misleading number.

This does not justify automatically replacing zero with negative pressure-derived
depth: that would introduce another unverified coordinate/datum convention.
The current rc2 schema omits elevation, and consumer-generated SAC leaves STEL
undefined. Publisher verification explicitly permits that absence alongside
the original producer SAC zero. Consequently, successful cross-format checks
do not establish one shared elevation interpretation. The added fixed
orientation headers likewise express conventions rather than measurements
of an instrument's orientation; a hydrophone pressure channel is scalar.

Sources: [producer SAC headers](../scripts/events.py),
[rc2 schema](../../mermaid-geocsv/docs/format-spec.md), and
[publisher SAC verification](../../mermaid-publisher/docs/geocsv/sac-verification.md).

### 7 BIN database version selection can violate its declared maximum

**Assessment: demonstrated latent defect in a new source-decoding path;
production relevance is unestablished.**

The baseline has no BIN decoder. Present `decrypt_get_database()` selects a
database using model and declared minimum/maximum firmware versions. One branch
accepts a version whose major is greater than the minimum and minor is less
than the maximum minor, without bounding the major by the maximum major.

With an isolated synthetic model-3 database declaring versions 3.0 through 3.9,
the function selected that database for firmware 4.0. That is outside the
declared interval. This demonstrates a range-selection defect, not that any
actual instrument has firmware 4.0 or that a production BIN was misdecoded.
An inappropriate decode table can alter scientific LOG content, so version
range semantics matter even though this example is hypothetical.

The exact decoding database is also part of scientific provenance. Retaining
BIN bytes, decoded LOGs and an automaid version does not by itself identify the
database bytes used to produce those LOGs. A reproducible BIN-based release
comparison should retain that input alongside model/firmware identity.

Source: [database selector and BIN decoder](../scripts/preprocess.py).

## Changed scientific policies with unresolved justification

### Clock and position acceptance

The baseline clock path required a complete Dive and GPS list and checked
positive frequencies on its final two GPS entries. It neither enforced the
3–4 MHz range nor bounded clock drift. The final-two-entry assumption could
also select the wrong phase when lists contained additional fixes.

Present code selects anchors explicitly by phase, requires finite frequency
in the inclusive 3–4 MHz range, and requires finite `abs(clockdrift) < 10 s`.
It then couples normal position eligibility to those clock checks and the
two-entry/5,400 s count gate. Invalid anchors are not replaced. Other position
inputs are retained even if their clock metadata are missing or invalid.

The stronger clock guard is an improvement over accepting arbitrary positive
frequencies or reset-scale drifts. However, ten seconds is an arbitrary,
documented screening cutoff, not an instrument-derived accuracy guarantee.
The 5,400 s window, coupling of position availability to clock eligibility,
and treatment of failed-clock GPS positions are also scientific acceptance
choices. They can remove usable data or retain insufficiently characterized
positions; their meaning cannot be established by a test that merely confirms
the chosen inequality. No HDOP/VDOP threshold, velocity acceptance limit,
extrapolation-duration acceptance limit or position uncertainty is supplied.

A useful improvement was reproduced: in the baseline, rejecting clock
correction did not necessarily prevent subsequent position calculation and SAC
export. With a zero-frequency pre-dive anchor, an otherwise complete synthetic
Dive still produced a positioned SAC waveform with its uncorrected start.
Present default eligibility blocks that normal calculation/export path.

### Emergency and surfacing definitions

The historical two-layer branch depended on maximum pressure reaching the
50 m proxy. Present code requires pressure to exceed it and no emergency
triggers; otherwise it uses the departure/surfacing pair. This deliberately
changes the trajectory for emergency dives. Avoiding ordinary crossing logic
for abnormal histories may be appropriate, but an emergency flag does not by
itself demonstrate a single-layer horizontal trajectory.

The surface-arrival marker also changes: the baseline used the last bladder
inflation message in a LOG; current code uses the first such message after
the identified ascent start within the cycle. This can alter GPS phase
membership and extrapolation epochs. Which message best represents physical
surfacing requires the particular firmware/log sequence. The shift from LOGs
to assembled cycles means the two message searches do not always cover the
same source interval.

### Zero-pressure exclusions and data-quality precedence

The baseline had no dedicated zero-pressure DET exclusion. Present code
temporarily withholds those recordings from newly generated waveform files,
waveform plots/tables and GeoCSV waveform rows, with raw source and decision
evidence retained. Missing REQ pressure is still permitted. The current review
records 65 such DET rows across seven instruments in an earlier corpus audit;
that count is not a new measurement from this comparison.

The precaution prevents an unqualified zero receiver depth from entering those
products, but the firmware meaning of zero remains open. If some are legitimate
near-surface observations, the policy removes scientifically useful recordings.
It is an explicit temporary exclusion, not proof the signal itself is invalid.
An existing excluded waveform is not automatically removed from an old output
tree, so fresh-output and metadata-only runs can have different inventories.

The baseline writer did not explicitly distinguish MiniSEED quality by DET/REQ.
Present output assigns DET Q and REQ D to give DET precedence in downstream
overlap handling. Source class and intended archive preference do not alone
establish that every DET has more accurate timing, position or samples than
every REQ. Preserve this lineage distinction while independently qualifying
quality claims and verifying what downstream ingest/delivery retains.

## Retained models and substantive improvements

### Recording time and sampling

Both endpoints use measured acquisition-environment frequency rather than
nominal 40 Hz for first-sample reconstruction:

```text
output_rate = measured_fs / 2**(6 - transmitted_scales)
DET first sample = INFO_DATE - TRIG / output_rate
REQ first sample = acquisition FNAME epoch + SMP_OFFSET / measured_fs
```

Raw `STAGES=-1` uses the native rate. DET trigger indexing remains zero-based.
REQ INFO-time fractional truncation and strict six-digit DET parsing are
already present in the baseline; they are not newly introduced first-sample
equation errors. Current INFO-time rejection/retention mechanisms differ, and
association effects at LOG boundaries still require inspection.

Separate original/uncorrected/corrected fields improve verifiability over the
baseline's in-place mutation of `date`, especially when later LOG selections
inspect shared events. Shared Event references across overlapping LOG selections
still permit environment/rate overwrites. That risk has an inherited basis,
even though current source-assignment paths differ.

### Product identity

The historical writer used network MH and the numeric suffix of the instrument
serial as Station, without explicitly assigning Channel or Location. Present
output uses the padded station identity, a hydrophone `?DH` channel and these
Location codes. Supported source scales are 1 through 5, with −1 denoting raw
values.

| Source scales | Nominal rate | Present Location | Present Channel |
| --- | --- | --- | --- |
| `-1`, RAW | 40 Hz | `10` | `BDH` |
| `5` | 20 Hz | `00` | `BDH` |
| `4` | 10 Hz | `20` | `BDH` |
| `3` | 5 Hz | `30` | `MDH` |
| `2` | 2.5 Hz | `40` | `MDH` |
| `1` | 1.25 Hz | `50` | `MDH` |

These identities distinguish product types without resampling them. Actual
rates remain measured rather than nominal. The current Location helper requires
the acquisition frequency to round to 40 Hz; this is an explicit hardware
assumption absent from the historical rate calculation. Identity changes are
an archive/association compatibility change, separate from whether sample values
and timestamps agree.

### Clock model

For an uncorrected first-sample epoch `t_u`, pre/post GPS epochs `t_b` and `t_a`,
and post-dive GPS-minus-instrument drift `d_a`, both endpoints calculate:

```text
correction = d_a * (t_u - t_b) / (t_a - t_b)
corrected_start = t_u + correction
```

Both assume a successful pre-dive reset and clock continuity over the interval.
Neither uses the measured pre-dive drift as an intercept. A nonzero residual
therefore challenges an inherited model assumption, not a new sign change.
Current naming and the [clock matrix](../docs/clock-timing-matrix.md) make the
signs explicit: GPS `clock_offset` is instrument minus GPS, while waveform
`time_correction_applied` is the estimated amount already added to the original
recording start. Those values concern different epochs.

Current MiniSEED adds applied-bit/correction history, nearest-0.0001 s tick
rounding with decimal ties to even, finite/range validation and every-record
read-back. These improve correction-history serialization. They do not validate
the assumed clock history or establish support for arbitrary byte orders and
mixed record lengths. GPS, LOG pressure and crossing epochs are not corrected
with the recording correction.

### Position pressure and decoded samples

The two-layer approximation and `1 dbar ≈ 1 m` depth convention are inherited.
`1 dbar = 100 mbar` is an exact unit conversion; current shared helpers make
the depth approximation explicit without adding density/gravity, atmospheric,
tide or geoid corrections. Neither implementation measures a thermocline from
CTD profiles. Historical code already interpolated latitude/longitude linearly;
the present remains an angular-coordinate model without uncertainty propagation.

Longitude wrapping is a clear correction relative to this baseline. For a
midpoint between 179.8° and −179.8°, the historical helper returned 0° and
present returned −180°. Both returned 0° for the midpoint from −1° to +1°.
The prime-meridian problem of an intermediate `[0, 360)` implementation is not
a defect of the 2019 endpoint and is absent at present.

The ordinary and edge-corrected inverse CDF24 kernel files are byte-identical
between their historical and present paths. Binary-safe Python I/O, complete
EVENT/payload checks and cleanup of temporary transform files improve sample
handling. This comparison found no new transform-kernel change. Native int32
assumptions and waveform reconstruction phase still need instrument/platform
qualification; identical kernels alone do not validate every input or compiled
binary. SAC float32 storage can alter large integer counts at either endpoint.

## GeoCSV source retention and new product scope

There was no GeoCSV writer at the historical endpoint. Present output is solely
MERMAID GeoCSV 1.0.0-rc2 in dataset-first GeoCSV 2.0, with five explicit row
types, 18 fields, microsecond timestamp formatting and separate measured and
derived quantities. These are new scientific interfaces relative to 2019,
not a format migration from an existing baseline CSV.

Measured GPS/pressure rows survive calculation failures where applicable.
Pressure positions are optional trajectory estimates. Waveform rows describe
corrected first samples and carry estimated receiver positions, not earthquake
source coordinates. Signed gauge pressure is preserved; missing pressure is
not filled with zero. Derived rows exclude Init/IcCycle namespaces and
preliminary events. Every normal row is bounded by retained GPS times and, when
supplied, the inclusive-begin/exclusive-end deployment window. Outside rows have
a local audit file. These output constraints are not independent physical
validation of source epochs or the trajectory.

Raw-event comparison, hash-bound clash reports and source/exclusion sidecars
improve traceability. Distinct raw events that render one identical waveform
row still result in one CSV row plus clash evidence; they are not established
as scientifically equivalent signals. Existing upstream framing/date rejections
are not all represented in the newer exclusion reports.

The historical workflow filtered source files by filename time before reading
events. Present processing retains a broader source set before association,
which better preserves delayed transmissions of earlier acquisitions. Retained
MER/LOG/BIN directories and fragments, server fingerprints and read-only final
products also strengthen provenance. A successfully decoded LOG supersedes a
same-stem server LOG in the retained LOG directory; that directory is not a
verbatim archive of every original LOG. Consult the protected source server
for original bytes and preserve exact decode-database provenance.

New SBE/RBR CTD and Stanford PSD outputs need their own scientific verification.
SBE `.ctd` metadata use a later same-cycle GPS fix, not a measured per-level
trajectory. Timing, pressure datum and QC remain incompletely qualified. The
Stanford path's hard-coded 40 Hz frequency axis, int8 offset arithmetic and
reader compatibility are documented concerns in a product absent in 2019.
These additions should not inherit scientific acceptance from ordinary waveform
checks. See [CTD open questions](../docs/CTD_open_questions.md) and the
[release review](../docs/scientific-release-review.md).

## Verification and limits

The existing 13-test scientific-eligibility suite passed in conda `pymaid3.10`
against the present source. Additional temporary diagnostics reproduced the
calibration inconsistency, changed fallback epochs and downstream positions,
duplicate count acceptance, shallow trajectory failure after waveform writing,
acquisition-environment substitution, out-of-range
BIN database selection and historical export after failed clock correction.
They also checked longitude behavior and the numerical calibration/rate examples.

Historical routines were extracted from the pinned Git source. Only Python 2
print syntax was adapted to execute the selected routines with the same modern
ObsPy 1.4.1 environment. Synthetic objects supplied the scientific inputs;
waveform serialization and all temporary files stayed in scratch directories.
This isolates selected source behavior. It is not a reconstruction of the
original Python 2.7/ObsPy environment or an end-to-end reprocessing of 2019 data.
The independent local ObsPy source reference inspected was commit
`50033e1daf95233cd4f30e95a49c37fd50be2ccd`; installed-version behavior was
checked separately by actual serialization/read-back.

Passing focused checks does not contradict the findings: the existing tests
verify selected intended behavior and do not establish scientific acceptance
of every supported product. The temporary diagnostics deliberately expose
counterexamples and conditional defects; they do not estimate archive impact.

The retained 112-instrument candidate comparison in the release review used an
earlier symmetric five-second bound. Its acceptance and counts do not validate
present HEAD's ten-second policy. No full historical-versus-present corpus
comparison or current rebuilt-corpus acceptance is claimed here.

Cross-repository inspection covered consumer
`fb1489aee434d8c257ba0a95fe943a5481e88f22`, publisher
`0d6cc0a6968e9b712fc5a71bc029164625581d96`, and site
`16a8e343852c309b2f84dafd1c1337c5146dbc73`. The rc2 consumer, publisher's
GPS/association checks and read-only Worker have distinct responsibilities.
Their contracts agree on rc2 and testing-only publication, but that agreement
does not validate producer calibration, firmware interpretation or trajectory
assumptions. The [publisher evidence index](../../mermaid-publisher/docs/geocsv/evidence.md)
still calls for fresh rebuilt-corpus evidence. All three repositories remained
read-only references for this note.

## Source map

Historical sources are reproducible with `git show 2de926a:<path>`:

| Historical source | Relevant behavior | Present source |
| --- | --- | --- |
| `scripts/main.py` | Source-date filtering, processing order and next-Dive position support | [main.py](../scripts/main.py), [preprocess.py](../scripts/preprocess.py) |
| `scripts/dives.py` | Environment selection, clock guards, pressure crossings, surface markers and event positions | [cycles.py](../scripts/cycles.py) |
| `scripts/events.py` | First-sample equations, clock formula, decoding, calibration plots and SAC construction | [events.py](../scripts/events.py) |
| `scripts/gps.py` | ±60 s reconciliation, coordinate interpolation and fallback epochs | [gps.py](../scripts/gps.py) |
| `scripts/utils.py` | Pressure plotting convention and utility calibration | [utils.py](../scripts/utils.py) |
| `scripts/bin/V103_Sources/icdf24.c` | Ordinary inverse transform kernel | [V103 kernel](../scripts/src/V103/icdf24.c) |
| `scripts/bin/V103EC_Sources/icdf24.c` | Edge-corrected inverse transform kernel | [V103EC kernel](../scripts/src/V103EC/icdf24.c) |

Current [producer rules](../docs/geocsv.md),
[consumer schema](../../mermaid-geocsv/docs/format-spec.md),
[publication contract](../../mermaid-publisher/docs/geocsv/contract.md) and
[hosting status](../../bathymetrix-site/docs/geocsv-hosting.md) define the current
workflow. They describe implemented contracts and remaining questions; their
presence is not independent confirmation of physical correctness.

## Improvements in the present implementation

### Preventing stale waveform substitution after a failed inverse transform

This is a major scientific-integrity improvement. The historical wrapper reused
shared filenames such as `bin/wtcoeffs` and `bin/wtcoeffs.icdf24_5` across
recordings without removing the previous reconstructed output. After invoking
the subprocess, it read that output path without establishing that the current
invocation had produced it.

The C driver can report an invalid transform size without writing a new output,
then exit with `EXIT_SUCCESS`. Consequently, `subprocess.check_output()` does
not raise for that failure. An earlier recording's output at the same wavelet
scale can remain available, be loaded as the current recording's samples, and
subsequently be exported with the current recording's filename and metadata.
This can substitute an unrelated waveform into an apparently usable SAC or
MiniSEED product. A nonzero subprocess exit already raised in the historical
wrapper; the demonstrated gap is failure without a nonzero exit status or a
fresh output.

Present code removes old coefficient and reconstructed-output files before
invocation, checks that an output was produced before loading samples, and
removes the scratch files after a successful read. Commit `18ee178` on
2020-10-13 introduced the cleanup and input-length protections. The prevention
comes from the wrapper's output handling; the underlying transform kernel is
unchanged.

A scratch check compiled the ordinary C driver and supplied three int32 input
values at scale 5, an invalid transform size. With an existing output containing
`[101, 202, 303]`, the subprocess returned zero and the subsequent historical
style of read loaded those unchanged old samples. After deleting the old output
and repeating the invocation, the subprocess again returned zero but no output
file existed. This reproduces the stale-data mechanism and the protection
provided by removal before invocation. It does not identify affected historical
archive files or reproduce a complete production export.

Sources: historical `Event.invert_transform()`, present
[sample reconstruction](../scripts/events.py), and the
[ordinary](../scripts/src/V103/icdf24_test.c) and
[edge-corrected](../scripts/src/V103EC/icdf24_test.c) C drivers.

### Correct longitude interpolation across the antimeridian

The historical helper could interpolate between 179.8° and −179.8° through 0°.
The present shortest signed longitude difference correctly puts the midpoint
at ±180°. This is a demonstrated geographic correctness fix, while the wider
trajectory remains the existing angular-coordinate approximation.

### Blocking some exports after failed clock correction

Historical position calculation and waveform export could proceed after clock
correction was rejected. A synthetic zero-frequency anchor reproduced a
positioned SAC export with an uncorrected start. Present normal eligibility
blocks that path and explicitly checks finite frequency and drift at selected
anchors. The benefit is stronger control over uncorrected exports; the numerical
screening cutoffs still require scientific qualification.

### Reconstructing a physical cycle from multiple LOG histories

Cycle assembly can combine chronology, pressure, GPS and recordings across file
switches, interrupted histories and partial LOGs. This supports recovery when
one assembled LOG is insufficient to describe the physical dive. The additional
evidence helps establish acquisition history, while the association of any
particular MER environment still needs to be supported as described in finding 2.

### Keeping original and corrected timing states separate

Separate `info_date`, `uncorrected_starttime` and `corrected_starttime` preserve
the intermediate timing quantities that the historical implementation stored
by repeatedly modifying one `date`. This improves verification and reduces
opportunities for later selection or repeated calculation to use an already
modified timestamp. It does not eliminate shared Event ownership issues.

### Checking sample input integrity and using explicit binary input and output

Complete EVENT framing and expected payload-length checks reject incomplete
input before reconstruction. Explicit binary file handling preserves the
intended coefficient bytes. Together with the stale-output protections, these
changes strengthen confidence that the loaded samples belong to the supplied
recording, without changing the inverse wavelet equations.

### Recording and verifying MiniSEED clock correction history

Present MiniSEED serialization records the applied correction and applied bit,
rounds correction history to 0.0001 s ticks with defined ties-to-even behavior,
checks finite values and integer range, and independently verifies every record
after writing. This makes the already corrected waveform start and its
processing history inspectable. Those checks establish serialization agreement,
not the physical accuracy of the assumed clock model.

### Separating scientific quantities and preserving processing evidence

GeoCSV distinguishes measured observations from derived times, estimated receiver
positions and configured boundary-pressure proxies. Shared conversion helpers
expose the exact pressure-unit relation and approximate pressure-to-depth rule.
Retained source files, hashes, clash reports and exclusion reports make source
choices and withheld products traceable. These are substantial gains in
verifiability and reproducibility, subject to the source-association, calibration
and rebuilt-corpus limitations documented above.

> **AI-written documentation — non-authoritative.** This review records source inspection, synthetic checks and local corpus observations from November 2026. Confirm instrument semantics against firmware documentation and original observations before changing scientific behavior.

# Scientific release review

Version v4.11.3 implements a symmetric absolute clock-drift limit below ten
seconds and the fixes listed below. Exactly ten seconds fails. This is an
arbitrary, deliberately loose screening cutoff; a scientifically appropriate
maximum remains an open question. The retained GeoCSV distributions provide
context for that decision.

## Implemented in v4.11.3

- Waveform filenames use `event.is_requested`. A present `TRIG=0` is DET.
  The prior truth test gave it a REQ filename. This was reproduced
  synthetically. The source-header scan found no real
  `TRIG=0` case. [Parser and filename construction](../scripts/events.py).
- Missing GPS clock drift, frequency, HDOP and VDOP are formatted with new local
  variables in `write_gps()`. Source GPS objects retain their original missing
  state. [GPS writer](../scripts/gps.py).
- DET waveforms whose source event pressure is explicitly zero are temporarily
  withheld from MiniSEED, SAC and waveform rows in every GeoCSV variant,
  including generation from saved cycles. The exclusion sidecar records each source
  event, available timing and acquisition provenance, intended output paths,
  literal pressure and reason in an exclusion sidecar. Missing REQ pressure
  remains permitted. The audited corpus contained 65 zero-pressure DET rows
  across seven instruments. The firmware meaning of zero remains open.
- The original last pre-dive and first post-dive clock anchors require valid
  frequency and finite `abs(clockdrift) < 10`. An invalid anchor is not replaced
  by another synchronization or a neighboring cycle. Position inputs retain
  the original per-cycle lists without applying these clock checks to every
  fix. The previous synchronization-entry proximity/count gate is preserved.

## Full GeoCSV comparison

The retained comparison and numerical results below used the earlier
`abs(clockdrift) < 5` policy. They do not verify the current ten-second bound.
The corpus has not been regenerated for this threshold revision. A larger
symmetric bound can both restore rejected cycles and admit cycles rejected by
the canonical signed-only guard.

The earlier v4.11.3 candidate at
[`~/mermaid/processed_4.11.3`](/Users/jdsimon/mermaid/processed_4.11.3)
contains all three GeoCSV variants for 112 instruments. The original per-cycle
position lists and synchronization-entry count gate are restored. The earlier
position-filter diagnostic and its full corpus are preserved separately under
`_comparison/superseded-position-filter/`.

Each canonical saved cycle set reproduced all three original payloads exactly
before revalidation. Reprocessing reused the saved acquisition assignments and
decoded samples; it recalculated clock eligibility, clock corrections,
positions and waveform Stats, then wrote GeoCSV and review sidecars only.
The comparison rechecked SHA-256, size and modification time for all 448
canonical input files.

All retained waveform, pressure and crossing positions match their canonical
values. Retained waveform timestamps, clock corrections, sample rates and
sample counts are unchanged. No retained crossing changes epoch. All 212,865
GPS rows and 3,808,238 pressure measurements are retained. Waveform rows
decrease from 43,359 to 43,294: all 65 removals have explicit zero DET source
pressure.

Four cycles lose eligibility because their original post-dive anchors have
drifts from -5.065551 to -7.073822 seconds. This withholds six crossing rows
and clears 207 pressure-position estimates. It causes no additional waveform
row loss beyond the zero-pressure rule. The 741 moved waveform positions and
34 retimed crossings reported in the superseded diagnostic do not occur under
the restored position-input policy. Existing raw GPS jumps and extrapolations
still require scientific interpretation.

Thirteen focused checks for that snapshot covered both drift signs, exact
five-second boundaries, position-only fixes with zero or missing clock fields,
the original count gate,
cycle isolation, stale derived state, source mutation, exclusions,
antimeridian behavior and actual MiniSEED/SAC serialization. The waveform
check uses ObsPy read-back and independent fixed-header inspection for every
MiniSEED record. The independent `mermaid.geocsv` consumer also checks all
336 candidate payloads; the retained report records its completed outcome.

The [comparison report](/Users/jdsimon/mermaid/processed_4.11.3/_comparison/README.md)
contains the per-row changes, source fingerprints, exclusion reasons and
pinned code excerpts. This metadata-only candidate contains no new MiniSEED
or SAC files. Canonical products remain read-only.

## Independent reading of waveform exports

Read a pair with ObsPy in the existing conda environment, without importing
Automaid. `apply_calib=False` preserves the stored sample values. This is a
reader instruction; the SAC writer's calibration convention remains deferred.

```python
from pathlib import Path

import numpy as np
from obspy import read
from obspy.io.sac import SACTrace

mini_path = Path("/absolute/path/to/waveform.mseed")
sac_path = mini_path.with_suffix(".sac")
mini, = read(str(mini_path), format="MSEED", apply_calib=False)
sac, = read(str(sac_path), format="SAC", apply_calib=False)
header = SACTrace.read(str(sac_path))

np.testing.assert_array_equal(sac.data, mini.data.astype(np.float32))
print(mini.stats.starttime, sac.stats.starttime)
print(mini.stats.sampling_rate, sac.stats.sampling_rate)
print(header.stla, header.stlo, header.stdp, header.scale)
```

SAC float32 samples can differ from the original integer counts. SAC `stdp`
is receiver depth in metres, using the producer's pressure-to-depth
approximation. MiniSEED has no corresponding station-coordinate headers.
The stored waveform start already includes its clock correction: do not add
GeoCSV `time_correction_applied` again. See the [clock matrix](clock-timing-matrix.md)
for the source definitions and applied-bit convention. The focused
[serialization check](../tests_and_verifications/test_scientific_eligibility.py)
also inspects MiniSEED fixed headers with Python `struct`, independently of
the producer's correction helper.

## Planned output handling

- Replace filename existence as the sole criterion for output reuse and record
  every skipped output with its path and reason. Until this is implemented,
  generate release candidates in fresh output directories. See the
  [README output-reuse note](../README.md).

## Known issues and limitations

- Shallow waveform positions use the deep-water anchor pair for the entire
  cycle. GeoCSV pressure positions use phase-specific trajectory segments.
  A synthetic shallow recording produced conflicting positions and raised
  during GeoCSV generation, after the waveform-writing stage. The number of
  affected real recordings remains unverified. Preserve the intentional
  interpolation stability fallback and its retained anchor epoch.
  [Trajectory construction](../scripts/cycles.py) and
  [GeoCSV trajectory comparison](../scripts/geocsv.py).
- The two-fix gate counts synchronization-list entries. Repeated representations of one
  observation can satisfy that count. The interpolation helper also sorts the
  caller's GPS list in place; the revalidated cycle calculations now pass
  copies to preserve the original candidate lists. Establish observation identity from source
  evidence before changing duplicate handling. [GPS merge and interpolation](../scripts/gps.py).
- LOG selections return shared Event objects. Overlapping selections can
  overwrite an earlier selection's environment, sampling rate and derived
  values. A synthetic test demonstrated this mechanism. Conflicting production
  assignments have not been established. A missing acquisition environment
  also triggers fallback to the first selected event's transmission environment.
  The per-MER environment local can retain the preceding file's value when the
  environment match fails. Investigation and implementation are deferred.
  [Event selection](../scripts/events.py) and [LOG assignment](../scripts/cycles.py).
- DET timestamps without six fractional digits are discarded. Two such raw
  headers were found. REQ `INFO DATE` parsing drops fractional seconds, although
  first-sample reconstruction later uses `FNAME` and `SMP_OFFSET`. The source
  scan found 2,550 REQ headers containing fractional seconds. Effects on LOG
  assignment at boundaries remain unverified. [Event parsing](../scripts/events.py).
- The LOG timestamp replacement branch discards the return value of
  `line.replace()`. Its intended replacement therefore leaves the original
  line intact. The scientific meaning of those early timestamps needs review
  before changing the branch. [Cycle preprocessing](../scripts/preprocess.py).
- Original SAC files store `SCALE=-149400`, while the plotting helper divides
  counts by that sensitivity to obtain nominal flat-band pascals. ObsPy maps
  SCALE to `stats.calib` and multiplies when `apply_calib=True`. Reader-option
  changes and the writer calibration convention are deferred.
  [Sensitivity and plotting conversion](../scripts/utils.py),
  [SAC writer](../scripts/events.py) and
  [ObsPy calibration behavior](https://github.com/obspy/obspy/blob/1.4.1/obspy/core/stream.py).
- SAC float32 storage changes some integer sample values. In the audited
  43,376 pairs, 8,345 pairs lost integer precision, with a maximum observed
  absolute difference of 22 counts. All SAC arrays equaled the paired MiniSEED
  arrays cast to float32. Exact integer comparisons require MiniSEED.
- The Stanford PSD reader raises a bytes-versus-text TypeError on its
  checked-in fixture under Python 3.10. The producer uses a hard-coded 40 Hz
  frequency axis and int8 arithmetic for decibel-offset subtraction. The
  scientific bin, offset and overflow implications need source verification.
  [PSD reader](../scripts/mermaidpsd.py) and [PSD production](../scripts/events.py).
- CTD profile timing, location, pressure datum, signed encodings and quality
  control are incompletely qualified. Existing CTD outputs require separate
  instrument-specific verification. See [CTD open questions](CTD_open_questions.md)
  and [current CTD formats](CTD_file_formats.md).
- The MiniSEED correction helper supports the producer's normal big-endian,
  uniform-record-length output. Little-endian input and mixed record lengths
  require separate qualification. See the [clock timing matrix](clock-timing-matrix.md).

## Open scientific questions

- What maximum absolute clock drift should be allowed at each clock anchor?
  The current ten-second screening cutoff is arbitrary; its scientific
  justification and the appropriate maximum remain open. Changing the bound
  can both restore rejected cycles and admit previously excluded cycles;
  assess both effects rather than assuming agreement with canonical products.
  Separate pre-dive and post-dive bounds also remain an open question. Large
  offsets need differentiation between ordinary accumulated drift
  and resets or loss of clock continuity. GeoCSV contains GPS offsets and applied
  waveform corrections at different epochs. The waveform timestamps already
  include the correction. [Clock definitions](clock-timing-matrix.md).
- Does zero or unavailable acquisition-clock frequency invalidate the associated
  GPS position or epoch, or only qualify the clock synchronization? Manual
  Ref. 452.000.852 v00, printed pp. 16 and 32, identifies `GPSOFF`/`CLOCK Hz`
  as the acquisition-board clock frequency and gives the 3–4 MHz test range;
  those sections do not define zero or a corresponding position-rejection rule.
  In P0016 on 2022-02-08, the zero-frequency MER fix has clock drift -1.407562 s.
  The LOG records `no GPSOFF after 30s (3)` and gives coordinates 443 seconds
  after the MER GPS epoch, with a large geographic discrepancy. The failure
  semantics and time/position association need firmware verification. Across
  the 112 canonical `gps.csv` files, 56 of 59 zero-frequency representations
  have absolute clock drift below five seconds; this does not establish their
  position quality. Position inputs currently retain the previous handling;
  clock-anchor frequency checks remain mandatory. See the
  [manual](/Users/jdsimon/mermaid/manauls/452.000.852_v00.pdf),
  [original LOG](/Users/jdsimon/mermaid/processed/452.020-P-16/LOG/16_6202E92F.LOG:28)
  and [retained observations and hashes](/Users/jdsimon/.codex/visualizations/2026/11/17/01a1e703-ebf3-79d0-a1cc-b3e56f0a3474/clock-drift-audit-2026-11-18/zero-frequency-gps-review.json).
- How should GPS jumps and long surface extrapolations be interpreted?
  Velocity and extrapolation-duration diagnostics remain available for end-user
  assessment. Acceptance limits belong to end users. The reviewed P0016 cycle
  had a 6.6 km jump over 639 seconds and a 14.7 km extrapolation of the descent
  crossing. A P0012 ascent leg extrapolated approximately 9.8 km over 8.6 hours.
- What are the firmware-specific synchronization epoch, reset sequence,
  residual pre-dive offset and behavior during reboots? The current recording
  model assumes continuity between its selected GPS anchors and a successful
  pre-dive reset. Year/month drift components use approximate durations.
- Which source sampling frequency describes acquisition for historical REQ
  recordings? The P0006 event-header and acquisition-environment values differ.
  Verify sample-offset indexing, zero-based DET trigger indexing, wavelet
  decimation phase and filter delays across hardware and firmware generations.
  [P0006 evidence](../notes/p0006-historical-sample-frequencies/README.md).
- Why did one P0011 overlapping RAW/WLT5 comparison peak at a one-sample
  offset, approximately 50 ms? This was one of 14 tested overlaps. Establish
  the cause from source timing and signal processing before inferring a
  systematic delay.
- Is every excluded raw recording accounted for? The source scan counted 401
  headers dated in 1970 and 19 payload-length mismatches, including possible
  retransmissions. Reset-era events are excluded by the current date-based
  workflow. Preserve their exclusion reasons without inferring recoverable UTC.
- Which calibration is authoritative for each instrument, epoch and waveform
  product? The cited third-generation sensitivity does not establish all
  instrument responses. [Response source status](../../mermaid-response/SOURCE_STATUS.md).
- What timing, identity, flags, quality precedence and overlap handling survive
  EarthScope ingest and delivery? Local cross-format agreement does not verify
  downloaded products. The 2026-11-16 local audit found consistent correction
  history and applied bits in all 240,456 MiniSEED records checked.

## Retained clock distributions

The 2026-11-18 analysis reads every `geo_DET_REQ.csv` beneath
`$MERMAID/processed`. It preserves GPS and waveform rows with source-record
indices and physical line numbers, together with source-file SHA-256 hashes.
Repeated rows retain their source weighting. Empty GPS offsets remain missing.
GPS clock drift is derived as the negative of the literal `clock_offset`.

Offsets with magnitude at least 100,000,000 seconds are excluded from the
histogram and retained with an explicit flag. This removes 1,634 offsets
consistent with 1970 resets and one additional gross positive offset of about
618.5 million seconds. This analysis cutoff is independent of production
eligibility and the adopted ten-second calculation bound.

The retained [analysis README](</Users/jdsimon/.codex/visualizations/2026/11/17/01a1e703-ebf3-79d0-a1cc-b3e56f0a3474/clock-drift-audit-2026-11-18/README.md>)
describes the values, histogram and source manifest. These files
support subsequent statistics on the same source bytes.

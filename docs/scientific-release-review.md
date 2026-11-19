> **AI-written documentation — non-authoritative.** This review records source inspection, synthetic checks and local corpus observations from November 2026. Confirm instrument semantics against firmware documentation and original observations before changing scientific behavior.

# Scientific release review

The queued changes below are planned work. The numerical clock-drift limit is
under review using the retained GeoCSV distributions. The current implementation
checks signed `clockdrift < 5` for the selected pre-dive and post-dive anchors.

## Queued fixes

- Classify waveform filenames using `event.is_requested`. A present `TRIG=0`
  is parsed as DET, but `if not self.trig` currently gives it a REQ filename.
  This was reproduced synthetically. The source-header scan found no real
  `TRIG=0` case. [Parser and filename construction](../scripts/events.py).
- Format missing GPS clock drift, frequency, HDOP and VDOP with new local
  variables in `write_gps()`. The current writer changes missing attributes on
  the original objects from `None` to NaN. The cached clock offset retains its
  original missing state. [GPS writer](../scripts/gps.py).
- Temporarily withhold DET waveforms whose source event pressure is explicitly
  zero. Apply the same exclusion to MiniSEED, SAC and waveform rows in every
  GeoCSV variant, including generation from saved cycles. Record each source
  event, available timing and acquisition provenance, intended output paths,
  literal pressure and reason in an exclusion sidecar. Missing REQ pressure
  remains permitted. The audited corpus contained 65 zero-pressure DET rows
  across seven instruments. The firmware meaning of zero remains open.
- Validate every candidate GPS fix before its use in a scientific calculation.
  Keep the existing cycle and pre-dive/post-dive assignments. Derive eligible
  lists from candidates already assigned to that cycle. Insufficient eligible
  fixes make the affected cycle ineligible, with a recorded reason. Clock
  correction requires its actual last pre-dive and first post-dive
  synchronization to pass. Handling missing clock metadata for position-only
  observations and the final symmetric drift limit remain open questions.
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
- The two-fix gate counts GPS entries. Repeated representations of one
  observation can satisfy that count. The interpolation helper also sorts the
  caller's GPS list in place. Establish observation identity from source
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

- What symmetric drift bound is appropriate, and should pre-dive and post-dive
  bounds differ? A one-second bound was proposed, then reopened for distribution
  review. Large offsets need differentiation between ordinary accumulated drift
  and resets or loss of clock continuity. GeoCSV contains GPS offsets and applied
  waveform corrections at different epochs. The waveform timestamps already
  include the correction. [Clock definitions](clock-timing-matrix.md).
- How should missing clock metadata affect use of a GPS observation for
  position? The proposed conservative filter requires complete clock evidence
  for each modeled-position input. Some LOG fixes lack that evidence. Assess
  exclusions within each cycle before adopting this extension.
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
eligibility and the pending scientific threshold decision.

The retained [analysis README](</Users/jdsimon/.codex/visualizations/2026/11/17/01a1e703-ebf3-79d0-a1cc-b3e56f0a3474/clock-drift-audit-2026-11-18/README.md>)
describes the values, histogram and source manifest. These files
support subsequent statistics on the same source bytes.

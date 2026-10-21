> **AI-written documentation — non-authoritative.** The Argo User's Manual and ADMT documentation define the Argo formats. The automaid section below describes code inspected on 2026-10-09 and may become stale as the code changes.

# What the file formats are

## Standard Argo CTD profile

The standard Argo exchange and distribution format is **NetCDF**, following
the Argo conventions in the [Argo User's Manual](https://oneargo.github.io/argo-format-user-manual/)
([DOI](https://doi.org/10.13155/29825)). A core profile represents CTD data,
including pressure (`PRES`), temperature (`TEMP`), and practical salinity
(`PSAL`), with corresponding quality-control information and, when available,
adjusted values and adjustment metadata. NetCDF attributes describe variables,
units, platform, cycle, time, position, and data mode.

Argo distributes profile, trajectory, metadata, and technical files. Profile
file names encode the real-time or delayed-mode state, float WMO identifier,
cycle, and sometimes profile direction. Current V3 files can contain multiple
profiles in one cycle; inspect `N_PROF` and the file's metadata rather than
assuming there is always one profile. Start with the User's Manual's **Argo
profile files** and **Naming convention for profile files** sections and check
the current format version and QC guidance before preparing data for submission.

### Filename examples

These are illustrative names using the Argo profile naming convention:

```text
R5900400_001.nc    # real-time core profile, WMO 5900400, cycle 1
D5900400_001.nc    # delayed-mode core profile, same float and cycle
BR5904179_001.nc   # real-time B-profile for a BGC float
SR5904179_001.nc   # GDAC synthetic profile combining CTD and ocean-state data
```

The `.nc` suffix is the ordinary NetCDF suffix; Argo is identified by its
filename convention and file contents, not by a special `.argo` suffix.

### Simplified data example

An Argo profile NetCDF stores the parameters in named variables with metadata
and QC fields. Conceptually, one profile might have:

| PRES (dbar) | TEMP (°C) | PSAL (unitless) |
| ---: | ---: | ---: |
| 10 | 18.42 | 34.91 |
| 20 | 18.37 | 34.92 |

This table is only a schematic view of three variables. It is not the complete
Argo NetCDF schema or a file ready for submission.

## Location in Argo data

Argo profile NetCDF files provide latitude and longitude as profile-level
metadata associated with each profile, not as a separate position for every
vertical CTD sample. Trajectory files record float position and timing through
the mission. Profile position should therefore be interpreted with the
profile's time and the applicable Argo conventions; it is not the float's
continuously known subsurface position.

## What automaid currently writes

Code inspection found the following profile outputs:

- `main.py` has a CSV output switch set to `True` and calls the profile CSV
  writers.
- The SBE41, SBE61, and RBR profile writers write a semicolon-separated CSV
  containing pressure, temperature, and salinity values. The existing `.csv`
  outputs remain unchanged and have no header row or location fields.
- SBE41 and SBE61 profiles also write a temporary `.ctd` companion. It retains
  the same semicolon-separated data rows and adds commented headers for the
  timestamp, latitude, and longitude of the first GPS fix after the profile.
  If no usable post-profile fix is available, those values say `unavailable`.
  This is a project-specific interim format, not an exact implementation of
  Argo `JULD`/`JULD_LOCATION` or a submission-ready Argo product.
- These profile CSVs are **not Argo core-profile files** and are not an Argo
  submission format. They also are not separate SAL and TEMP CSV files.
- The per-parameter SAL and TEMP outputs found in the code are HTML plots.
- automaid also writes GeoCSV metadata (`geo.csv` variants) for MERMAID GPS,
  pressure, event, and thermocline metadata. That GeoCSV output is not a CTD
  profile export and is not an alternate Argo NetCDF product.
  The legacy writer accepts Python `float` and NumPy `float64` inputs, including
  NaNs, and rejects other NumPy floating types before conversion or formatting.
  Integer values and pressure strings from the logs remain accepted. Numeric
  formatting uses `float64`, with six decimal places for coordinates, sample
  rates, and timing offsets, and zero decimal places for measured pressures.
  Thermocline pressure is written as mixed-layer depth in meters times 100,
  without fixed decimal formatting. These checks cannot detect precision lost
  before a value was converted to Python `float` or NumPy `float64`.

For example, the existing SBE `.csv` contains rows shaped like this, with no
header or location fields:

```text
10.0;18.42;34.91
20.0;18.37;34.92
```

Columns are pressure, temperature, and salinity, respectively. Values above
are illustrative, not copied from an actual MERMAID profile.

The temporary `.ctd` companion keeps those same data rows, preceded by
commented metadata such as:

```text
# TEMPORARY CTD format: adds location/time metadata; not an exact Argo JULD implementation
# gps_fix_time_utc: 2026-09-24T00:57:06Z
# latitude_deg_north: 12.345
# longitude_deg_east: -67.890
# gps_fix_selection: first GPS fix after CTD profile
```

The example metadata above is illustrative. The timestamp and coordinates come
from the same GPS fix. `gps_fix_time_utc` is deliberately named as the GPS-fix
time; it is not asserted to be the profile time or Argo `JULD`.

Relevant implementation: [`main.py`](../scripts/main.py),
[`cycles.py`](../scripts/cycles.py), [`sbe41.py`](../scripts/sbe41.py),
[`sbe61.py`](../scripts/sbe61.py), [`rbr.py`](../scripts/rbr.py), and
[`geocsv.py`](../scripts/geocsv.py).

## Does automaid attach location to salinity and temperature?

Not in its profile CSV. Each output row contains pressure, temperature, and
salinity values only; it has no latitude or longitude columns. GeoCSV separately
records GPS-fix locations and event or thermocline locations, but those are
not joined to individual CTD profile rows. For standard Argo representation,
location belongs in the profile metadata in NetCDF; trajectory locations belong
in trajectory data.

## Auxiliary CSVs are a different case

The GDAC `aux/` area accepts some auxiliary sensor files in CSV, text, or
NetCDF, under a prescribed naming convention. It is intended for experimental
or supplementary sensor data and is distributed without GDAC curation. This
does not make a semicolon-separated automaid CTD profile CSV compliant with the
core Argo profile specification. See the [Argo auxiliary directory guidance](https://argo.ucsd.edu/data/auxiliary-directory/)
and consult the responsible DAC before using that route.

## OneArgo GitHub tools checked for a writer

Repository review on 2026-10-09 found no general-purpose writer in the public
[OneArgo GitHub organization](https://github.com/OneArgo) that takes new
pressure, temperature, and salinity observations and creates a standard Argo
core-profile NetCDF file.

One similarly named tool is the [EasyOneArgo repository](https://github.com/OneArgo/EasyOneArgo).
Its `generate_easy_one_argo_core` MATLAB function reads existing GDAC profile
NetCDF files and produces the simplified EasyOneArgo data products (CSV, with
optional MAT output); it does not write Argo profile NetCDF. The
[ArgoFormatChecker](https://github.com/OneArgo/ArgoFormatChecker) validates
files; it is not a profile writer. The other visible organization repositories
are for documentation, vocabularies, indexes, or Argo team activities.

The ADMT does point to a Coriolis real-time processing chain for file creation
and to `pysprof` for synthetic BGC S-profile generation. These are
DAC/processing workflows or specialized S-profile tooling, not a small generic
core-profile writer. See [ADMT tools for DACs](https://www.argodatamgt.org/DACs.html).

## References

- [Argo User's Manual, online edition](https://oneargo.github.io/argo-format-user-manual/)
- [Argo User's Manual DOI](https://doi.org/10.13155/29825)
- [Argo profile-file guide](https://argo.ucsd.edu/data/how-to-use-argo-files/)
- [Argo auxiliary directory](https://argo.ucsd.edu/data/auxiliary-directory/)

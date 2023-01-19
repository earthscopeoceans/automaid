__automaid__, a Python package to process MERMAID files.

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.5057096.svg)](https://doi.org/10.5281/zenodo.5057096)

This program converts raw data transmitted by MERMAID instruments to classify
their data, correct clock drifts, interpolate float positions, generate seismic
SAC and miniSEED files, plot seismic events and dives, and generate KML files.

Continually developed by @joelsimon (jdsimon@princeton.edu).  Originally written
by @sebastienbx .  Many v3.6+ additions for generation 3+ MERMAID floats (.BIN
decryption, CTD profiling, etc.) coded by @oseanfro.

### 1. INSTALLATION

This installation procedure has been tested with MacOS. For Linux the
procedure is valid but one could prefer to use a package manager.
For Windows the installation of Python 2.7 is valid but the
compilation of the wavelet inversion program with "make" could be
problematic.

An easy installation procedure is described here:

* Install [Miniconda](https://conda.io/miniconda.html) or
  [Anaconda](https://www.anaconda.com/download/) (which requires more
  disk space). (You may already have it, you might have to do `module
  load anaconda/5.2.0` to specify the precise version).
* Restart your terminal to load the new PATH variables.
* Add the conda-forge channel:
  `conda config --add channels conda-forge`
* Create a virtual environment called "pymaid":
  `conda create -n pymaid python=2.7`

* Make sure you are in the `bash` shell!

* Activate the environment:
  `source activate pymaid`
* Install obspy:
  `conda install obspy`
  (or try these following if the above fails/stalls)<br>
  `conda install --channel https://conda.anaconda.org/obspy obspy`<br>
  `conda install obspy=1.2.2` # WARNING<sup>1</sup> (see note at bottom)
* Install plotly 2.7.0:
  `conda install plotly=2.7.0`
* Quit the virtual environment:
  `source deactivate`

In addition to the Python 2.7 installation it is necessary to compile,
using `make` the wavelet inversion programs located in
`scripts/src/V103/` and `scripts/src/V103EC/`. The compiled binaries
must be in the "bin" directory and must be named `icdf24_v103_test` and
`icdf24_v103ec_test`.

Finally, ensure the environmental variable, `MERMAID`, is set as a directory
containing "server/" and "processed/" subdirectories.  These defaults may be
overridden at execution using the `--server` and `--processed` arguments.

### 2. USAGE

To use the application:

* Copy files from your MERMAID server into the "$MERMAID/server" directory:
  `scp username@host:\{"*.LOG","*.MER","*.vit"\} server`
* Activate the virtual environment:
  `source activate pymaid` or `conda activate pymaid` or (if "conda" not found)
  e.g., `source /Users/joelsimon/anaconda3/etc/profile.d/conda.sh ; conda  activate pymaid`
* Run the main.py file:
  `python $AUTOMAID/scripts/main.py`
* Quit the virtual environment:
  `source deactivate`

You will be getting the processed files into the directory `$MERMAID/processed`.
You may have to remove some error-prone log files and create some directories -
we will be editing the script for increased versatility as we go along.

The "main.py" file can be edited to select some options:

* A date range between which to process the data can be chosen with
the `begin` and `end` variables.
* A "redo" flag can be set to True in order to restart the processing
of data for each launch of the script. This flag force the deletion
of the content of the content of the `processed` directory.
* A `events_plotly` flag allow the user to plot interactive figures
of events in a html page. This kind of plot can be disabled to save
disk space.

### 3. CITATION

Joel D. Simon, Sébastien Bonnieux, Frederik J. Simons & The EarthScope-Oceans
Consortium. (2021). earthscopeoceans/automaid: v3.5.0
(v3.5.0). Zenodo. https://doi.org/10.5281/zenodo.5514229

<sup>1</sup>Joel could not get `conda install` to work without specifying a version...
he choose the seemingly most recent Python 2.7 version, though this needs to validated.

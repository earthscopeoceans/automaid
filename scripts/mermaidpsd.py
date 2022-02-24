# -*- coding: utf-8 -*-
#
# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v2.7)
#
# Developer: Joel D. Simon (JDS)
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified by JDS: 24-Feb-2022
# Last tested: Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit

# Todo:
#
# *Docstrings
# *Specify header-string lengths? (e.g., lat/lon)?
# *`float64` vs `float32` for psd['freq']?
# *Formatspec for `read()` (currently all returned as str)

import re
import sys
import pytz
import datetime
import numpy as np
from collections import OrderedDict

import utils
import setup

# !! Version really should be cross-referenced with version in file... !!
version = "v0.1.0"

class MermaidPSD:
    def __init__(self, filename, hdr, psd):
        self.filename = filename
        self.hdr = hdr
        self.psd = psd
        self.__version__ = version

def read(filename):
    def _parse_datablock_line(line):
        desc = re.search("\[(.*)\]", line).group(1).lower()
        stat = line.split("->")[1].strip().split(" ")
        size = int(stat[0])
        precision = stat[1]
        byteorder = stat[2]

        # Translate "little" or "big" byteorder for "<" or ">" shorthand
        # Annoyance -> "TypeError: data type "<float64" not understood"
        # Instead of, e.g.,  "<float64" must be "<f8" (or the numpy "f8" equivalent, "d")
        # https://numpy.org/doc/stable/reference/generated/numpy.dtype.char.html
        if byteorder  == "little":
            byteorder = "<"
        elif byteorder == "big":
            byteorder = ">"
        elif byteorder == "n/a":
            byteorder = ""
        else:
            raise TypeError("byte order {} not understood".format(byteorder))

        dtype = np.dtype(byteorder + np.dtype(precision).char)

        dbdict = {
            "desc": desc,
            "size": size,
            "precision": precision,
            "byteorder": byteorder,
            "dtype": dtype
        }
        return dbdict

    psd = {}
    with open(filename, "rb") as f:
        hdr = OrderedDict()
        line = f.readline()
        while "Datablock" not in line:
            key, val = line.strip().split(": ", 1)
            hdr[key] = val
            line = f.readline()

        while "Datablock" in line:
            dbdict = _parse_datablock_line(line)
            desc = dbdict["desc"]
            dtype = dbdict["dtype"]
            size = dbdict["size"]

            data = np.fromfile(f, dtype, size)
            psd[desc] = data

            line = f.readline()
            while line == "\n":
                line = f.readline()

        if "<<EOF>>" not in line:
            raise IOError("file incomplete - expected terminal '<<EOF>>' not found\n{}"
                          .format(filename))

    mhpsd = MermaidPSD(filename, hdr, psd)
    return mhpsd

def write(filename, event, psd_data, psd_desc, hdr_date=None):
    def _format_datablock_line(psd_desc, psd_data):
        """Format data description line preceding data block with size, precision, and
        endianness, e.g.

        #Datablock [FREQ] -> 256 float64 little

        """

        stat = utils.ndarray_stat(psd_data)
        dbline = "#Datablock [{}] -> {} {} {}\n" \
                 .format(psd_desc, stat["size"], stat["precision"], stat["byteorder"])
        return dbline

    if event.processed_file_name not in filename:
        raise ValueError("event filename does not match instance filename")

    if len(psd_data) != len(psd_desc):
        raise ValueError("unmatched data and descriptor lists")

    psd_val = list(sorted(psd_desc)) # careful:`list()` copy is required here
    psd_val.remove('freq')
    dataset = ",".join(psd_val)

    if hdr_date is None:
        hdr_date = datetime.datetime.now(pytz.UTC).isoformat().split(".")[0] + "Z"

    hdr = OrderedDict([
        ("Dataset", "MERMAID Hydrophone {}% PSD (.mhpsd) {}".format(dataset, version)),
        ("Created", hdr_date),
        ("Automaid",  "{} ({})".format(setup.get_version(), setup.get_url())),
        ("Network", utils.network()),
        ("Station", event.kstnm),
        ("Location", "00"),
        ("Channel", event.kcmpnm),
        ("StartTime", event.corrected_starttime),
        ("Latitude", event.station_loc.latitude),
        ("Longitude", event.station_loc.longitude),
        ("Elevation", 0),
        ("AbsolutePressure", "<?get_pressure_from_log?>"),
        ("SensorDescription", "MERMAIDHydrophone({})".format(event.kinst)),
        ("SampleRate", event.decimated_fs),
        ("TimeCorrection", event.mseed_time_correction),
        #("Duration", event.stanford_duration),
        ("AnalysisPeriod", event.stanford_period),
        ("WindowType", event.stanford_win_type),
        ("WindowLength", event.stanford_win_len),
        ("WindowOverlap", event.stanford_overlap),
        ("WindowCount", event.stanford_rounds),
        ("DecibelOffset", event.stanford_db_offset)
    ])

    psd = {}
    for desc, data in zip(psd_desc, psd_data):
        psd[desc] = data

    hdr_lines = ["{}: {}\n".format(key, val) for key, val in hdr.items()]
    with open(filename, "wb") as f:
        f.writelines(hdr_lines)

        for desc in sorted(psd):
            f.write(_format_datablock_line(desc, psd[desc]))
            f.write(psd[desc])
            f.write("\n")

        f.write("<<EOF>>\n")

    print("Wrote " + filename)

    mhpsd = MermaidPSD(filename, hdr, psd)
    return mhpsd

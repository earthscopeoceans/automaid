# -*- coding: utf-8 -*-
# @Author: fro
# @Date:   2024-09-13 16:14:34
# @Last Modified by:   fro
# @Last Modified time: 2025-02-13 11:45:48
# -*- coding: utf-8 -*-
#
# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v3.10)
#
# Developer: Frédéric rocca <FRO>
# Contact:  frederic.rocca@osean.fr
# Last modified by FRO: 09-Sep-2024
# Last tested: Python 3.10.13, 22.04.3-Ubuntu


import sys
import os
import re
import glob
import subprocess
import numpy as np
import matplotlib
# if os.environ.get('DISPLAY','') == '':
#     print "no display found. Using non-interactive Agg backend"#
#     matplotlib.use('agg',warn=False, force=True)
matplotlib.use('tkagg')   # Joel's edit on MacOS, Big Sur 11.6 (otherwise `plt.show()` throws seg fault)
import matplotlib.pyplot as plt
import plotly.offline as plotly
import plotly.graph_objs as graph

from obspy import UTCDateTime
from obspy.core.trace import Trace
from obspy.core.trace import Stats
from obspy.core.stream import Stream

import gps
import sys
import setup
import utils
import mermaidpsd
import time

# Get current version number.
version = setup.get_version()

class Events:
    '''The Events (plural) class references a SINGLE .MER file, and all events that
     live within it, which may be associated with the environments of multiple
     other .MER files

     Multiple events (event binary blocks) may exist in a single Events.mer_name

    '''

    def __init__(self, base_path=None, mer_name=None):
        self.mer_name = mer_name
        self.base_path = base_path
        self.events = []
        self.gps_info = []
        self.__version__ = version

        # If just a base path to (e.g., a server directory) is passed, load all
        # .MER files contained there; otherwise read a single input file
        if self.mer_name is None:
            mer_files = glob.glob(os.path.join(self.base_path, "*.MER"))
        else:
            mer_files = glob.glob(os.path.join(self.base_path, self.mer_name))

        for mer_file in mer_files:
            # This .MER file name
            mer_binary_name = mer_file.split("/")[-1]

            # The </EVENT> binary blocks contained in this .MER file
            with open(mer_file, "rb") as f:
                content = f.read()

            catch = re.findall(b"<ENVIRONMENT>.+</PARAMETERS>", content, re.DOTALL)
            if catch :
                mer_environment = catch[0].decode("utf-8","replace")
                self.gps_info += gps.get_gps_from_mer_environment(mer_binary_name,mer_environment)

            events = content.split(b'</PARAMETERS>')[-1].split(b'<EVENT>')[1:]
            for event in events:
                # Ensure every event block is complete(ly transmitted)
                if event[0:14] != b"\n\r\t<INFO DATE=" or event[-22:] != b"\n\r\t</DATA>\n\r</EVENT>\n\r":
                    continue
                # The header of this specific </EVENT> block (NOT the </ENVIRONMENT> of
                # the same .MER file, which may be unrelated (different time))
                mer_binary_header = event.split(b"<DATA>\x0A\x0D")[0]

                # The actual binary data contained in this </EVENT> block (the seismogram)
                # N.B:
                # "\x0A" is "\n": True
                # "\x0D" is "\r": True
                # "\x09" is "\t": True
                # https://docs.python.org/2/reference/lexical_analysis.html#string-and-bytes-literals
                mer_binary_binary = event.split(b"<DATA>\x0A\x0D")[1].split(b"\x0A\x0D\x09</DATA>")[0]

                # The double split above is not foolproof; if the final data
                # block in the .MER file ends without </DATA> (i.e., the file
                # was not completely transmitted), the object 'binary' will just
                # return everything to the end of the file -- verify that the we
                # actually have the expected number of bytes (apparently len()
                # returns the byte-length of a string, though I am not super
                # happy with this solution because I would prefer to know the
                # specific encoding used for event binary...)
                if b" ROUNDS=" not in mer_binary_header:
                    actual_binary_length = len(mer_binary_binary)
                    bytes_per_sample = int(re.search(b'BYTES_PER_SAMPLE=(\d+)', mer_binary_header).group(1))
                    num_samples = int(re.search(b'LENGTH=(\d+)', mer_binary_header).group(1))
                    expected_binary_length = bytes_per_sample * num_samples
                    if actual_binary_length != expected_binary_length:
                        continue

                evt = Event(mer_binary_name, mer_binary_header, mer_binary_binary,mer_environment)

                # Use weak catchall for obj init issues (e.g., formatting
                # abnormalities in the .MER file)
                if evt.info_date:
                    self.events.append(evt)

        # Sort by events by reported "INFO DATE", which may be 1970 if the clock
        # was reset (the info date has not been corrected for clockdrift)
        self.events.sort(key=lambda x: x.info_date)

    def get_events_between(self, begin, end):
        # The dates are not yet corrected for clockdrift, which can be years if
        # the float reset to UNIX time 0 (01-Jan-1970).  So this def actually
        # kicks out potential events, but that is okay with me because timing
        # seems like it would be iffy at best for, e.g., the following event in
        # 08_5EAD0DD4.MER --
        #
        # "
        #   <ENVIRONMENT>
        #   ...
        #   <GPSINFO DATE=2020-05-02T06:05:46 LAT=-1332.5810 LON=-17857.8430 />
        #   <DRIFT YEAR=50 MONTH=4 DAY=-1 HOUR=-9 MIN=-47 SEC=19 USEC=-578796 />
        #   ...
        #   </PARAMETERS><EVENT>
        #   <INFO DATE=1970-01-03T10:18:13.513763 ... />
        # "
        catched_events = []
        for event in self.events:
            if begin < event.info_date < end:
                catched_events.append(event)
        return sorted(catched_events, key=lambda x: x.info_date)

    def get_gps_between(self, begin, end):
        catched_gps = []
        for gps in self.gps_info:
            if begin < gps.date < end:
                catched_gps.append(gps)
        return sorted(catched_gps, key=lambda x: x.date)
    # def __repr__(self):
    #     return "Events('{}', '{}')".format(self.base_path, self.mer_name)


class Event:
    '''The Event (singular) class references TWO .MER files, which may be the same,
    through Event.mer_binary_name (.MER file containing the </EVENT> binary
    data), and Event.mer_environment_name (.MER file containing the
    </ENVIRONMENT> metadata [e.g., GPS, clock drift, sampling freq. etc.]
    associated with that event)

    Only a SINGLE event (event binary block) is referenced by
    Event.mer_binary_name and Event.mer_environment_name

    '''

    def __init__(self, mer_binary_name=None, mer_binary_header=None, mer_binary_binary=None, default_mer_environment=None):
        self.mer_binary_name = mer_binary_name
        self.mer_binary_header = mer_binary_header
        self.mer_binary_binary = mer_binary_binary
        self.default_mer_environment = default_mer_environment
        self.__version__ = version

        self.kstnm = None
        self.kinst = None
        self.kcmpnm = None
        self.mer_environment_name = None
        self.mer_environment = None

        self.processed_data = None
        self.measured_fs = None
        self.decimated_fs = None
        self.trig = None
        self.pressure_mbar = None
        self.pressure_dbar = None
        self.depth = None
        self.temperature = None
        self.criterion = None
        self.snr = None
        self.scales = None
        self.normalized = None
        self.edges_correction = None

        self.info_date = None
        self.uncorrected_starttime = None
        self.corrected_starttime = None
        self.station_loc = None
        self.station_loc_is_preliminary = None
        self.clockdrift_correction = None
        self.mseed_time_correction = None
        self.obspy_trace_stats = None
        self.processed_file_name = None
        self.uncorrected_processed_file_name = None

        self.is_requested = None

        self.is_stanford_event = None
        self.stanford_rounds = None
        self.stanford_duration = None
        self.stanford_period = None
        self.stanford_win_len = None
        self.stanford_win_type = None
        self.stanford_overlap = None
        self.stanford_db_offset = None
        self.stanford_psd_freqs = None
        self.stanford_psd_perc50 = None
        self.stanford_psd_perc95 = None

        print("{} (binary)".format(self.mer_binary_name))

        if len(re.findall(b" ROUNDS=(-?\d+)", self.mer_binary_header)) > 0 :
            self.is_stanford_event = True
            self.stanford_rounds = re.findall(b" ROUNDS=(-?\d+)", self.mer_binary_header)[0]
            date = re.findall(b" DATE=(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6})", mer_binary_header, re.DOTALL)
            self.info_date = UTCDateTime.strptime(date[0].decode("utf-8","replace"), "%Y-%m-%dT%H:%M:%S.%f")
            self.is_requested = False
            #if len(re.findall("FNAME=(\d{4}-\d{2}-\d{2}T\d{2}_\d{2}_\d{2}\.\d{6})", self.header))  0 :
            #self.requested = True

        else:
            self.is_stanford_event = False
            self.scales = re.findall(b" STAGES=(-?\d+)", self.mer_binary_header)[0].decode("utf-8","replace")
            catch_trig = re.findall(b" TRIG=(\d+)", self.mer_binary_header)
            if len(catch_trig) > 0:
                # Event detected with STA/LTA algorithm
                self.is_requested = False
                self.trig = int(catch_trig[0])

                # Sometimes "INFO DATE" is transferred with the incorrect precision,
                # e.g., in 0039_5E71459C.MER, which is missing fractional seconds
                # ("INFO DATE=2020-03-16T01:06:42")
                date = re.findall(b" DATE=(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6})", mer_binary_header, re.DOTALL)
                if not date:
                    return

                # Potentially something like this, if we want to allow
                # non-fractional seconds...
                # date = re.findall(" DATE=(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6})", header, re.DOTALL)
                # try:
                #     self.date = UTCDateTime.strptime(date[0], "%Y-%m-%dT%H:%M:%S.%f")
                # except IndexError as e:
                #     date = re.findall(" DATE=(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})", header, re.DOTALL)
                #     self.date = UTCDateTime.strptime(date[0], "%Y-%m-%dT%H:%M:%S")

                # The "depth" of an event is actually units of dbar in both .LOG and .MER
                # (not mbar, like other pressures in the .LOG)
                # We assume 1 dbar = 1 m = 100 mbar
                # (NOT 1 m = 101 mbar as stated in MERMAID manual Réf : 452.000.852 Version 00)
                self.pressure_dbar = int(re.findall(b" PRESSURE=(-?\d+)", self.mer_binary_header)[0])
                self.pressure_mbar = self.pressure_dbar * 100
                self.info_date = UTCDateTime.strptime(date[0].decode("utf-8","replace"), "%Y-%m-%dT%H:%M:%S.%f")
                self.depth = self.pressure_dbar # ~= meters
                self.temperature = int(re.findall(b" TEMPERATURE=(-?\d+)", self.mer_binary_header)[0])
                self.criterion = float(re.findall(b" CRITERION=(\d+\.\d+)", self.mer_binary_header)[0])
                self.snr = float(re.findall(b" SNR=(\d+\.\d+)", self.mer_binary_header)[0])

            else:
                # Event requested by user
                self.is_requested = True
                date = re.findall(b" DATE=(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})", mer_binary_header, re.DOTALL)
                self.info_date = UTCDateTime.strptime(date[0].decode("utf-8","replace"), "%Y-%m-%dT%H:%M:%S")

    def set_kstnm_kinst(self, kstnm=None, kinst=None):
        '''Sets `kstnm` and `kinst` attrs using those station and instrument names
        previously derived with `dives.Dive.set_kstnm_kinst()`; see there for details

        '''

        self.kstnm = kstnm
        self.kinst = kinst

    def set_environment(self, mer_environment_name, mer_environment):
        self.mer_environment_name = mer_environment_name
        self.mer_environment = mer_environment

        # Shouldn't these attrs remain `None` instead of `""` if not a
        # Stanford float?
        duration = re.findall("DURATION_h=(\d+)", self.mer_environment)
        if len(duration) > 0:
            self.stanford_duration = duration[0]
        else :
            self.stanford_duration = ""

        period = re.findall("PROCESS_PERIOD_h=(\d+)", self.mer_environment)
        if len(duration) > 0:
            self.stanford_period = period[0]
        else :
            self.stanford_period = ""

        win_len = re.findall("WINDOW_LEN=(\d+)", self.mer_environment)
        if len(duration) > 0:
            self.stanford_win_len = win_len[0]
        else :
            self.stanford_win_len = ""

        win_type = re.findall("WINDOW_TYPE=(\w+)", self.mer_environment)
        if len(duration) > 0:
            self.stanford_win_type = win_type[0]
        else :
            self.stanford_win_type = ""

        overlap = re.findall("OVERLAP_PERCENT=(\d+)", self.mer_environment)
        if len(duration) > 0:
            self.stanford_overlap = overlap[0]
        else :
            self.stanford_overlap = ""

        db_offset = re.findall("dB_OFFSET=(\d+)", self.mer_environment)
        if len(duration) > 0:
            self.stanford_db_offset = db_offset[0]
        else :
            self.stanford_db_offset = ""

    def find_measured_sampling_frequency(self):
        # Get the frequency recorded in the .MER environment header
        fs_catch = re.findall("TRUE_SAMPLE_FREQ FS_Hz=(\d+\.\d+)", self.mer_environment)
        if fs_catch:
            self.measured_fs = float(fs_catch[0])
        else:
            return

        # Divide frequency by number of scales
        if not self.is_stanford_event and self.scales != "-1":
                self.decimated_fs = self.measured_fs / (2. ** (6 - int(self.scales)))
        else:
            # Sampled at ~40Hz
            # Either: Stanford PSD float or seismic float with `scales = -1` (raw data)
            self.decimated_fs = self.measured_fs

        self.kcmpnm = utils.channel(self.decimated_fs)

    def set_uncorrected_starttime(self):
        '''Compute the starttime of the event (uncorrected for GPS clockdrift) from the
        event header preceding the .MER binary

        '''

        if not self.measured_fs:
            print("=> measured_fs not found  !!!!!!")
            self.uncorrected_starttime = self.info_date
            return

        if self.is_stanford_event:
            self.uncorrected_starttime = self.info_date
            return

        if self.is_requested:
            # Quoted verbatim from SB email, "Re: Future update for automated,"
            # 23 January 2019 --
            #
            # "The data are recorded in the SD card. Each time an acquisition
            # start a new file is created and the date of the first sample is
            # recorded. When you request data, the acquisition board count the
            # number of samples from the file beginning until to reach the
            # requested date (the date of the beginning of the file, plus the
            # number of samples dived by the sampling frequency of the
            # hydrophone must be equal to the requested date). But this search
            # doesn’t have access to the sampling frequency of the recorded file
            # and use instead the measurement of the sampling frequency, since a
            # long time can happen between the recording of a file and the
            # request of a signal, the sampling frequency can change. It is then
            # necessary to consider the sampling frequency during the recording
            # of a signal to have an accurate estimation of the requested
            # signal. Without this consideration an error of several hundred
            # milliseconds could be introduced in the date of the requested
            # signal (and the error would be of several tenths of seconds by
            # considering the sampling frequency exactly equal to 40Hz)."
            rec_file_date = re.findall(b"FNAME=(\d{4}-\d{2}-\d{2}T\d{2}_\d{2}_\d{2})", self.mer_binary_header)
            if rec_file_date:
                rec_file_date = UTCDateTime.strptime(rec_file_date[0].decode("utf-8","replace"), "%Y-%m-%dT%H_%M_%S")
                rec_file_ms = re.findall(b"FNAME=\d{4}-\d{2}-\d{2}T\d{2}_\d{2}_\d{2}\.?(\d{6}?)", self.mer_binary_header)
                if len(rec_file_ms) > 0:
                    rec_file_date += float("0." + rec_file_ms[0].decode("utf-8","replace"))

                sample_offset = re.findall(b"SMP_OFFSET=(\d+)", self.mer_binary_header)
                sample_offset = float(sample_offset[0])
                self.uncorrected_starttime = rec_file_date + sample_offset / self.measured_fs
            else :
                self.uncorrected_starttime = self.info_date
        else:
            # For a detected event the INFO DATE is timestamp of the STA/LTA trigger
            #
            # NB, the manual (Réf : 452.000.852 Version 00) incorrectly states
            # on pg. 33 --
            #
            # "The time given in the date is not the time of the first sample of
            # the signal, but the time of the TRIG sample number. In the example
            # above TRIG=250 so the date given corresponds to the timestamp of the
            # 250th sample."
            #
            # It should say, "...timestamp of the 251th sample."  Indexing
            # starts at 0 in this case, hence `float(self.trig)` and not
            # `float(self.trig)-1` below.  JDS verified with SB in email "Re:
            # Bumps and other matters," 28 Mar 2021.
            self.uncorrected_starttime = self.info_date - float(self.trig) / self.decimated_fs

    def set_processed_data(self):
        '''Convert raw .MER binary data to processed MERMAID traces or Stanford PSD
        50-95% arrays.  The former's binary are generally inverted via a
        CDF(2,4) wavelet transform for "WLT?" data (or through casting to int32
        in the case of "RAW" [STAGES=-1] data), while the latter's are simply
        cast to int8 and...

        Sets attrs:
        `processed_data`          (for V1 floats and V2 Stanford PSD floats)
        `data_max`                (for V1 floats and V2 Stanford PSD floats)
        `data_min`                (for V1 floats and V2 Stanford PSD floats)
        `normalized`              (only for V1 floats)
        `edges_correction`        (only for V1 floats)

        '''

        if self.is_stanford_event:
            self.processed_data = np.frombuffer(self.mer_binary_binary, np.int8) - np.int8(self.stanford_db_offset)
            x_split = np.array_split(self.processed_data, 2)
            self.stanford_psd_perc50 = x_split[0]
            self.stanford_psd_perc95 = x_split[1]
            freq_max = float(self.stanford_psd_perc50.size * 40 / int(self.stanford_win_len))

            dt = '<f8'  # little-endian float64 (native Python "float" on JDS' Mac)
            #dt = '>f4' # big-endian float32
            self.stanford_psd_freqs = np.arange(0., freq_max, freq_max/self.stanford_psd_perc50.size,
                                                dtype=dt)

            # Endianness notes to be moved out of here...
            # l = np.float64(90.7)
            # b = l.byteswap()
            # WRONG: b.dtype.byteorder still says "=" for native little!
            # WRONG: still wrong, even after call to  b.dtype.newbyteorder('>')
            # I don't get it...see
            # "byteswap() doesn't change byteorder attribute #10372"
            # https://github.com/numpy/numpy/issues/10372
            # ...perhaps addressed in newer Python.  I think this is an issue
            # with the "view" of the array vs. the array representation in
            # memory. The only way I could reliably get b.dtype.byteorder to be
            # ">" was to initialize it as such; doesn't seem I can alter later
            #
            # DOES NOT WORK: b = np.float64(90.7, dtype='>f8') (endianness ignored)
            # DOES WORK: b = np.arange(90.7, dtype='>f8')


        else:
            # Get additional information on flavor of invert wavelet transform
            # Must do this before the `return` statement, in the case of RAW files
            self.normalized = re.findall(" NORMALIZED=(\d+)", self.mer_environment)[0]
            self.edges_correction = re.findall(" EDGES_CORRECTION=(\d+)", self.mer_environment)[0]

            # If scales == -1 this is a raw signal, just convert binary data to np array of int32
            if self.scales != "-1":
                # Change to bin/ directory because the executable C inversion
                # program called below can fail with full paths :(
                os.chdir("bin")

                # The following scripts READ wavelet coefficients (what MERMAID
                # generally sends) from a file named "wtcoeffs" and WRITE the inverted
                # data to a file name, e.g., "wtcoeffs.icdf24_5"
                wtcoeffs_data_file_name = "wtcoeffs"
                inverted_data_file_name = "wtcoeffs.icdf24_" + self.scales

                # Delete any previously-inverted data just to be absolutely sure we are
                # working with this event's data only (an interruption before the second
                # call to delete these files could result in their persistence)
                if os.path.exists(wtcoeffs_data_file_name):
                    os.remove(wtcoeffs_data_file_name)

                if os.path.exists(inverted_data_file_name):
                    os.remove(inverted_data_file_name)

                # Write cdf24 data to file named "wtcoeffs" in local directory
                with open(wtcoeffs_data_file_name, 'wb') as f:
                    f.write(self.mer_binary_binary)

                # The inverse wavelet transform C code (`icdf24_v103(ec)_test`) is
                # called below in a shell subprocess and its output is verified;
                # determine if edge correction needs to be accounted for and set the
                # first argument (the executable) in the full command (note that "./" is
                # required before script on JDS' Linux machine, but not JDS' Mac...)
                icdf24_shell_command = []
                if self.edges_correction == "1":
                    icdf24_shell_command.append("./icdf24_v103ec_test")

                else:
                    icdf24_shell_command.append("./icdf24_v103_test")

                # Append the argument list to feed inversion script, e.g., "5 1 wtcoeffs"
                icdf24_shell_command.extend([self.scales, self.normalized, wtcoeffs_data_file_name])

                # Perform inverse wavelet transform, e.g., running in background shell --
                # $ ./icdf24_v103ec_test 5 1 wtcoeffs
                # NB, `subprocess` is analogous to `system` in MATLAB
                stdout = subprocess.check_output(icdf24_shell_command)

                # Ensure the inverse wavelet transform worked as expected, meaning that
                # it generated an output file of int32 data
                if not os.path.exists(inverted_data_file_name):
                    cmd = ' '.join(map(str, icdf24_shell_command))
                    err_mess = "\nFailed: inverse wavelet transformation\n"
                    err_mess += "In directory: {:s}\n".format(bin_path)
                    err_mess += "Attempted command: {:s}\n".format(cmd)
                    err_mess += "Using: event around {:s} in {:s}\n\n".format(self.info_date, self.mer_binary_name)
                    err_mess += "Command printout:\n'{:s}'".format(stdout)

                    # This output message is more helpful than the program crashing on
                    # the next line
                    sys.exit(err_mess)

                # Read the inverted data
                self.processed_data = np.fromfile(inverted_data_file_name, np.int32)

                # Delete the files of coefficient and inverted data, otherwise a latter
                # .MER with an incomplete binary event block can come along and use the
                # same data
                os.remove(wtcoeffs_data_file_name)
                os.remove(inverted_data_file_name)

                # Move up one level back into the scripts/ directory
                os.chdir("..")

            else:
                self.processed_data = np.frombuffer(self.mer_binary_binary, np.int32)

        self.processed_data_max = np.amax(self.processed_data)
        self.processed_data_min = np.amin(self.processed_data)

    def correct_clockdrift(self, gps_descent, gps_ascent):
        '''Estimate and correct GPS clockdrift for this event.

        Sets attrs:

        `clockdrift_correction`
        `mseed_time_correction
        `corrected_starttime`

        '''

        # Correct the clock drift of the Mermaid board with GPS measurement
        pct = (self.uncorrected_starttime - gps_descent.date) / (gps_ascent.date - gps_descent.date)
        self.clockdrift_correction = gps_ascent.clockdrift * pct

        # The miniSEED convention of a time correction is of the same sign of
        # the `clockdrift` (or the `clockdrift_correction') of this program
        #
        # positive clockdrift => uncorrected MER time early (onboard clock is slow) w.r.t GPS
        # negative clockdrift => uncorrected MER time late (oboard clock is fast) w.r.t GPS
        self.mseed_time_correction = self.clockdrift_correction

        # Apply correction
        self.corrected_starttime = self.uncorrected_starttime + self.clockdrift_correction

    def compute_station_location(self, drift_begin_gps, drift_end_gps, station_loc_is_preliminary=False):
        '''Fills attr `station_loc`, the interpolated location of MERMAID when it
        recorded an event

        '''

        self.station_loc = gps.linear_interpolation([drift_begin_gps,
                                                     drift_end_gps],
                                                    self.corrected_starttime)
        self.station_loc_is_preliminary = station_loc_is_preliminary

    def set_processed_file_name(self):
        '''Note that setting of attr `processed_file_name` does not imply that the event
        may be written to output .sac and .mseed files; that is determined by
        the setting of `station_loc`

        Filename uses attr `corrected_starttime`, so be sure to apply all date
        adjustments and corrections before setting the file name

        '''

        if not self.corrected_starttime:
            return

        processed_file_name = UTCDateTime.strftime(UTCDateTime(self.corrected_starttime),\
                                                   "%Y%m%dT%H%M%S") + "." + self.mer_binary_name

        if self.is_stanford_event:
            processed_file_name += ".STD"

        else:
            if not self.trig:
                processed_file_name += ".REQ"
            else:
                processed_file_name += ".DET"

            if self.scales == "-1":
                processed_file_name += ".RAW"
            else:
                processed_file_name += ".WLT" + self.scales

        if self.station_loc_is_preliminary:
            processed_file_name += '.prelim'

        self.processed_file_name = processed_file_name

    def set_uncorrected_processed_file_name(self):
        if not self.uncorrected_starttime:
            self.uncorrected_starttime = self.info_date

        processed_file_name = UTCDateTime.strftime(UTCDateTime(self.uncorrected_starttime),\
                                                   "%Y%m%dT%H%M%S") + "." + self.mer_binary_name

        if self.is_stanford_event:
            processed_file_name += ".STD"

        else:
            if not self.trig:
                processed_file_name += ".REQ"
            else:
                processed_file_name += ".DET"

            if self.scales == "-1":
                processed_file_name += ".RAW"
            else:
                processed_file_name += ".WLT" + self.scales

        processed_file_name += '.unloc'
        self.uncorrected_processed_file_name = processed_file_name


    def statistics(self):
        if not self.is_stanford_event:
            stat_date = self.corrected_starttime

        else:
            stat_date = self.info_date

        return [UTCDateTime.strftime(UTCDateTime(stat_date), "%Y%m%dT%H%M%S"),self.processed_data_max, self.processed_data_min]

    def __get_figure_title(self):
        if self.corrected_starttime :
            title = "<Unlocalized> " + self.corrected_starttime.isoformat() \
                    + "     Fs = " + str(self.decimated_fs) + "Hz\n" \
                    + "     Depth: " + str(self.depth) + " m\n" \
                    + "     Temperature: " + str(self.temperature) + " degC\n" \
                    + "     Criterion = " + str(self.criterion) \
                    + "     SNR = " + str(self.snr)
        else :
            title = "" + self.uncorrected_starttime.isoformat() \
                    + "     Fs = " + str(self.decimated_fs) + "Hz\n" \
                    + "     Depth: " + str(self.depth) + " m\n" \
                    + "     Temperature: " + str(self.temperature) + " degC\n" \
                    + "     Criterion = " + str(self.criterion) \
                    + "     SNR = " + str(self.snr)
        return title

    def __get_figure_title_stanford_html(self):
        title = "" + self.info_date.isoformat() \
                + "<br Fs = " + str(self.decimated_fs) + "Hz" \
                + "     DURATION = " + str(self.stanford_duration) + "h" \
                + "     PROCESS_PERIOD = " + str(self.stanford_period) + "h" \
                + "     WINDOW_LEN = " + str(self.stanford_win_len) \
                + "<br WINDOW_TYPE = " + str(self.stanford_win_type) \
                + "     OVERLAP_PERCENT = " + str(self.stanford_overlap) \
                + "     dB_OFFSET = " + str(self.stanford_db_offset) + "db"
        return title

    def __get_figure_title_stanford(self):
        title = "" + self.info_date.isoformat() \
                + "\n Fs = " + str(self.decimated_fs) + "Hz" \
                + "     DURATION = " + str(self.stanford_duration) + "h" \
                + "     PROCESS_PERIOD = " + str(self.stanford_period) + "h" \
                + "     WINDOW_LEN = " + str(self.stanford_win_len) \
                + "\n WINDOW_TYPE = " + str(self.stanford_win_type) \
                + "     OVERLAP_PERCENT = " + str(self.stanford_overlap) \
                + "     dB_OFFSET = " + str(self.stanford_db_offset) + "db"
        return title

    def plot_html(self, processed_path, optimize=False, include_plotly=True):
        processed_file_name = self.processed_file_name
        starttime = self.corrected_starttime

        if processed_file_name is None:
            processed_file_name = self.uncorrected_processed_file_name
            starttime = self.uncorrected_starttime
            if processed_file_name is None:
                return

        # Check if file exist
        processed_path_html = processed_path + processed_file_name + ".html"
        if os.path.exists(processed_path_html):
            return

        print("plot {}".format(processed_file_name + ".html"))
        # Plotly you can implement WebGL with Scattergl() in place of Scatter()
        # for increased speed, improved interactivity, and the ability to plot even more data.
        Scatter = graph.Scatter
        if optimize :
            Scatter = graph.Scattergl
        # Add acoustic values to the graph
        pascals = [utils.counts2pascal(d) for d in self.processed_data]

        data_line = Scatter(x=utils.get_date_array(starttime, len(pascals), 1./self.decimated_fs),
                                  y=pascals,
                                  name="pascals",
                                  line=dict(color='blue',width=2),
                                  mode='lines')

        data = [data_line]

        layout = graph.Layout(title=self.__get_figure_title(),
                              xaxis=dict(title='Coordinated Universal Time (UTC)', titlefont=dict(size=18)),
                              yaxis=dict(title='Pascals', titlefont=dict(size=18)),
                              hovermode='closest')
        figure = graph.Figure(data=data, layout=layout)

        # Include plotly into any html files ?
        # If false user need connexion to open html files
        if include_plotly :
            figure.write_html(file=processed_path_html, include_plotlyjs=True)
        else :
            figure.write_html(file=processed_path_html,
                              include_plotlyjs='cdn', full_html=False)

    def plot_html_stanford(self, processed_path, optimize=False, include_plotly=True):
        # Check if file exist
        processed_file_name = self.processed_file_name
        if processed_file_name is None:
            processed_file_name = self.uncorrected_processed_file_name
            if processed_file_name is None:
                return

        processed_path_html = processed_path + processed_file_name+ ".html"
        print(processed_path_html)
        if os.path.exists(processed_path_html):
            return
        win_sz = re.findall("WINDOW_LEN=(\d+)", self.mer_environment, re.DOTALL)
        dt = np.dtype([('perc50', np.int8)])
        x_split = np.array_split(self.processed_data,2)
        x0=x_split[0]
        x1=x_split[1]
        freq_max=(float)((x0.size*40)/int(win_sz[0]))
        freq = np.arange(0.,freq_max,freq_max/x0.size)


        # Plotly you can implement WebGL with Scattergl() in place of Scatter()
        # for increased speed, improved interactivity, and the ability to plot even more data.
        Scatter = graph.Scatter
        if optimize :
            Scatter = graph.Scattergl

        # Add acoustic values to the graph
        x0_line = Scatter(x=freq,
                                  y=x0,
                                  name="Percentile 50",
                                  line=dict(color='blue',
                                            width=2),
                                  mode='lines')
        x1_line = Scatter(x=freq,
                                  y=x1,
                                  name="Percentile 95",
                                  line=dict(color='red',
                                            width=2),
                                  mode='lines')

        data = [x0_line,x1_line]
        layout = graph.Layout(title=self.__get_figure_title_stanford_html(),
                              xaxis=dict(title='Freq (Hz)', titlefont=dict(size=18), type='log'),
                              yaxis=dict(title='dBfs^2/Hz', titlefont=dict(size=18)),
                              hovermode='closest'
                              )
        figure = graph.Figure(data=data, layout=layout)

        # Include plotly into any html files ?
        # If false user need connexion to open html files
        if include_plotly :
            figure.write_html(file=processed_path_html, include_plotlyjs=True)
        else :
            figure.write_html(file=processed_path_html,
                              include_plotlyjs='cdn', full_html=False)

    def plot_png(self, processed_path, force_redo=False):
        processed_file_name = self.processed_file_name
        if processed_file_name is None:
            processed_file_name = self.uncorrected_processed_file_name

        # Check if file exist
        processed_path_png = processed_path + processed_file_name + ".png"
        if not force_redo and os.path.exists(processed_path_png):
            return

        pascals = [utils.counts2pascal(d) for d in self.processed_data]

        # Plot frequency image
        plt.figure(figsize=(9, 4))
        plt.title(self.__get_figure_title(), fontsize=12)
        plt.plot(utils.get_time_array(len(pascals), 1./self.decimated_fs),
                 pascals,
                 color='b')
        plt.xlabel("Time (s)", fontsize=12)
        plt.ylabel("Pascal", fontsize=12)
        plt.tight_layout()
        plt.grid()
        plt.savefig(processed_path_png)
        plt.clf()
        plt.close()

    def plot_png_stanford(self, processed_path):

        # Check if file exist
        processed_path_png = processed_path + self.processed_file_name + ".png"
        print(processed_path_png)
        if os.path.exists(processed_path_png):
            return
        win_sz = re.findall("WINDOW_LEN=(\d+)", self.mer_environment, re.DOTALL)
        dt = np.dtype([('perc50', np.int8)])
        x_split = np.array_split(self.processed_data,2)
        x0=x_split[0]
        x1=x_split[1]
        freq_max=(float)((x0.size*40)/int(win_sz[0]))
        freq = np.arange(0.,freq_max,(freq_max/x0.size))

        # Plot frequency image
        plt.figure(figsize=(9, 4))
        plt.title(self.__get_figure_title_stanford(), fontsize=12)
        plt.plot(freq,x0,color='b')
        plt.plot(freq,x1,color='r')
        plt.xlabel("Freq (Hz)", fontsize=12)
        plt.ylabel("dBfs^2/Hz", fontsize=12)
        plt.xscale("log")
        plt.tight_layout()
        plt.grid()
        plt.savefig(processed_path_png)
        plt.clf()
        plt.close()

        # This *_2.png left here to compare JDS' rewrite using .stanford attrs
        # with Rocca's original code (e.g., x0, x1)...later to be removed after
        processed_path_png2 = processed_path + self.processed_file_name + "_2.png"
        print(processed_path_png2)
        plt.figure(figsize=(9, 4))
        plt.title(self.__get_figure_title_stanford(), fontsize=12)
        plt.plot(self.stanford_psd_freqs, self.stanford_psd_perc50, color='b')
        plt.plot(self.stanford_psd_freqs, self.stanford_psd_perc95, color='r')
        plt.xlabel("Freq (Hz)", fontsize=12)
        plt.ylabel("dBfs^2/Hz", fontsize=12)
        plt.xscale("log")
        plt.tight_layout()
        plt.grid()
        plt.savefig(processed_path_png2)
        plt.clf()
        plt.close()

    def set_obspy_trace_stats(self, force_without_loc=False):
        '''Sets attr `obspy_trace_stats`, an obspy.core.trace.Stats instance

        obspy_trace_stats holds metadata common to both miniSEED and SAC formats.
        obspy_trace_stats.sac holds extra metadata only found in the SAC format.

        Floats are NOT converted to np.float32() in either case.

        NB: the SAC header value shown to the world (e.g., "sac.delta"), and the private SAC header
        written to disk (e.g., "sac._hf[0]"), differ in type.  The relevant float header values that
        actually get written to disk with sac.write are stored in the private "._hf" attribute,
        which is not generated with initialization of the raw Stats() container. Therefore, if
        printing those values to, e.g. a text file, ensure the relevant F (float) fields are cast to
        np.float32 first.

        For example:
        >> from obspy.core.trace import Trace
        >> from obspy.io.sac.sactrace import SACTrace
        >> trace = Trace()
        >> sac = SACTrace.from_obspy_trace(trace)  <-- this gets called by sac.write (within stream.write)
        >> sac.delta = 1/20
        >> isinstance(sac.delta, float)            <-- True: this is the public attr shown to the world
        >> isinstance(sac.delta, np.float32)       <-- False
        >> isinstance(sac._hf[0], float)           <-- False
        >> isinstance(sac._hf[0], np.float32)      <-- True: this is the private attr written to disk

        For more detail see: http://www.adc1.iris.edu/files/sac-manual/manual/file_format.html

        Update function `events.write_obspy_trace_stats` if the fields in this method are changed.

        '''

        # Do not try to hack SAC header vars to fit Stanford data...
        # Trust me (JDS), it's not worth it
        # (e.g., how to handle `npts`, 'delta`, and their effect on `start\endtime`?)
        if self.is_stanford_event:
            return

        # Fill metadata common to SAC and miniSEED formats
        stats = Stats()
        stats.network = utils.network()
        stats.station = self.kstnm
        stats.location = "00"
        stats.channel = self.kcmpnm
        if not force_without_loc:
            stats.starttime = self.corrected_starttime
        else :
            stats.starttime = self.uncorrected_starttime
        stats.sampling_rate = self.decimated_fs
        stats.npts = len(self.processed_data)

        # Extra metadata, some of which is only written to SAC files
        keys = ['stla',
                'stlo',
                'stel',
                'stdp',
                'scale',
                'cmpaz',
                'cmpinc',
                'user0',
                'user1',
                'user2',
                'user3',
                'kinst',
                'kuser0',
                'kuser1',
                'kuser2']
        def_float = -12345.

        # Default SAC header (we may not will not fill all of these keys)
        stats.sac = dict.fromkeys(keys, def_float)

        # Fill station-location header fields.
        if not force_without_loc:
            stats.sac["stla"] = self.station_loc.latitude;
            stats.sac["stlo"] = self.station_loc.longitude;

        # Elevation is 0 (our reference is truly sea level)
        stats.sac["stel"] = 0

        # Add scaling factor to convert digital counts to Pa
        stats.sac["scale"] = utils.sacpz_const()

        # Add dip (CMPINC; "component incidence") in SAC dip convention, using as guide:
        # https://github.com/iris-edu/mseed2sac/blob/master/doc/mseed2sac.md
        #
        # SAC dip convention: "degrees down from vertical up/outward",
        # i.e., BHN, BHE = 90, BHZ = 0
        #
        # SEED dip convection: "degrees down from horizontal"
        # i.e., BHN, BHE = 0, BHZ = -90
        stats.sac["cmpinc"] = 0 # SAC dip

        # Add azimuth: horizontal projection of component vector measured clockwise from north
        # It is 0 for vertical components. Theoretically, BHN, BHZ = 90, BHE = 90
        stats.sac["cmpaz"] = 0

        # NB: I checked how IRIS serves up hydrophone data (in MATLAB):
        # >> s = irisFetch.Stations('channel', '*', '*', '*', '?DH')
        #
        # For all 3233 channels from 2147 stations that were returned:
        # dip = -90, 0, or 90
        # azimuth = 0 or 360
        #
        # For dip = -90, I assume that is the SEED dip convention
        # For dip = +90, I do not know; I thought perhaps it might be some(thing like a?)
        # right-hand-rule convention, but not all +90 dips are associated with 360 azimuth

        # REQ events do not record their depth at the time of acquisition, and because the onboard
        # detection algorithm was not triggered there are no trigger parameters to report
        if not self.is_requested:
            stats.sac["stdp"] = self.depth # dbar ~= meters (from external pressure sensor; down is positive)
            stats.sac["user0"] = self.snr
            stats.sac["user1"] = self.criterion
            stats.sac["user2"] = self.trig # sample index

        # Clock drift correction, which is the 'Time correction' applied in the 48-byte
        # fixed header in utils.set_mseed_time_correction()
        stats.sac["user3"] = self.clockdrift_correction # = self.mseed_time_correction

        # Generic instrument (e.g., '452.020')
        stats.sac['kinst'] = self.kinst

        # automaid version number
        stats.sac["kuser0"] = self.__version__

        # String describing detection/request status, and number of wavelet scales transmitted
        # (e.g., 'DET.WLT5')
        if self.processed_file_name :
            reqdet_scales = self.processed_file_name.split('.')[-2:]
        else :
            reqdet_scales = self.uncorrected_processed_file_name.split('.')[-2:]
        stats.sac['kuser1'] = '.'.join(reqdet_scales)

        # String detailing the type of (i)CDF24 transform: edge correction and
        # normalization
        stats.sac['kuser2'] = 'ec' + self.edges_correction + 'norm' + self.normalized

        # Attach Stats to events object
        self.obspy_trace_stats = stats

    def write_mseed(self, processed_path, force_without_loc=False,
                 force_redo=False, force_without_time_correction=False):
        # NB, mseed2sac writes, e.g., "MH.P0025..BDH.D.2018.259.211355.SAC",
        # where "D" is the quality indicator, "D -- The state of quality control
        # of the data is indeterminate" (SEED v2.4 manual pg. 108)

        if self.is_stanford_event:
            return

        # Check if the station location has been calculated
        if self.station_loc is None and not force_without_loc:
            #print self.processed_file_name + ": Skip mseed generation, wait the next ascent to compute location"
            return

        # Format the metadata into miniSEED and SAC header formats
        if not self.obspy_trace_stats:
            self.set_obspy_trace_stats(force_without_loc)

        # Check if file exists
        mseed_filename = processed_path + self.processed_file_name + ".mseed"
        if not force_redo and os.path.exists(mseed_filename):
            return

        # Get stream object
        stream = self.get_stream(processed_path, force_without_loc)

        # Save stream object with the time correction applied but without 'Time
        # correction applied' flag or 'Time correction' value being set in the
        # 48-byte fixed header
        stream.write(mseed_filename, format='MSEED')

        # Update (open and rewrite bits of each 48-byte fixed header that
        # precedes each record) the mseed file with time-correction metadata
        if not force_without_time_correction and not self.station_loc_is_preliminary:
            utils.set_mseed_time_correction(mseed_filename, self.mseed_time_correction)

    def write_sac(self, processed_path, force_without_loc=False, force_redo=False):
        '''
        A note about starttime and .sac, and the headers NZMSEC and B, if
        str(event.obspy_trace_stats["starttime"]) == '2018-09-28T10:14:34.251926Z',
        then in the .sac header "NZMSEC" would be 251 and "B" would be 926.

        '''

        if self.is_stanford_event:
            return

        # Check if the station location has been calculated
        if self.station_loc is None and not force_without_loc:
            #print self.processed_file_name + ": Skip sac generation, wait the next ascent to compute location"
            return

        # Format the metadata into miniSEED and SAC header formats
        if not self.obspy_trace_stats:
            self.set_obspy_trace_stats(force_without_loc)

        # Check if file exists
        sac_filename = processed_path + self.processed_file_name + ".sac"
        if not force_redo and os.path.exists(sac_filename):
            return

        # Get stream object
        stream = self.get_stream(processed_path, force_without_loc)

        # Save stream object
        stream.write(sac_filename, format='SAC')

    def write_wav(self, processed_path, force_without_loc=True, force_redo=False):
        if self.is_stanford_event:
            return

        processed_file_name = self.processed_file_name
        if self.station_loc is None :
            processed_file_name = self.uncorrected_processed_file_name
            # Format the metadata into wav 
            if not self.obspy_trace_stats:
                self.set_obspy_trace_stats(force_without_loc)
        # Check if file exists
        wav_filename = processed_path + processed_file_name + ".wav"
        if not force_redo and os.path.exists(wav_filename):
            return

        # Get stream object
        stream = self.get_stream(processed_path, force_without_loc)   
        # Save stream object
        stream.write(wav_filename, format='WAV', framerate=self.decimated_fs)                    

    def write_mhpsd(self, processed_path, creation_datestr, force_redo=False):
        if not self.is_stanford_event or self.station_loc is None:
            return

        # Check if the file exists
        mhpsd_filename = processed_path + self.processed_file_name + ".mhpsd"
        if not force_redo and os.path.exists(mhpsd_filename):
            return

        # Stanford PSD percentiles, hardcoded for now (forever?)
        mhpsd_desc = ["freq", "perc50", "perc95"]
        mhpsd_data = [self.stanford_psd_freqs, self.stanford_psd_perc50, self.stanford_psd_perc95]

        # Write .mhpsd file
        mhpsd = mermaidpsd.write(mhpsd_filename, self, mhpsd_data, mhpsd_desc, creation_datestr)

    def get_stream(self, processed_path, force_without_loc=False):
        # Check if an interpolated station location exists
        if self.station_loc is None and not force_without_loc:
            return

        # Save data into a Stream object
        trace = Trace()
        trace.stats = self.obspy_trace_stats
        trace.data = self.processed_data

        stream = Stream(traces=[trace])

        return stream

    # def __repr__(self):
    #     # Hacked repr dunder because I can't print binary...
    #     if self.mer_binary_binary:
    #         bin_str = '<int32 binary>'
    #     else:
    #         bin_str = self.mer_binary_binary

    #     return "Event('{}', '{}', {})".format(self.mer_binary_name, self.mer_binary_header, bin_str)


def write_traces_txt(cycles, creation_datestr, processed_path, mfloat_path):
    event_cycle_tup = ((event, cycle) for cycle in cycles for event in cycle.events if event.station_loc and not event.station_loc_is_preliminary)

    traces_file = os.path.join(processed_path, mfloat_path, "traces.txt")
    fmt_spec = '{:>42s}    {:>17s}    {:>23s}    {:>32s}\n'

    version_line = "#automaid {} ({})\n".format(setup.get_version(), setup.get_url())
    created_line = "#created {}\n".format(creation_datestr)
    header_line = "#                                 filename              bin_mer                 cycle_name                             log_files\n"

    with open(traces_file, "w+") as f:
        f.write(version_line)
        f.write(created_line)
        f.write(header_line)
        for e, c in sorted(event_cycle_tup, key=lambda x: x[0].corrected_starttime):
            log_files = ""
            for log in c.logs :
                log_files += "{:>17s} ".format(log.log_name)
            f.write(fmt_spec.format(e.processed_file_name,
                                    e.mer_binary_name,
                                    c.cycle_name,
                                    log_files))

def write_loc_txt(complete_dives, creation_datestr, processed_path, mfloat_path):
    '''Writes interpolated station locations at the time of event recording for all events for each
    individual float

    '''

    event_list = [event for dive in complete_dives for event in dive.events if event.station_loc and not event.station_loc_is_preliminary]

    loc_file = os.path.join(processed_path, mfloat_path, "loc.txt")
    fmt_spec = "{:>42s}    {:>10.6f}    {:>11.6f}    {:>6.0f}\n"

    version_line = "#automaid {} ({})\n".format(setup.get_version(), setup.get_url())
    created_line = "#created {}\n".format(creation_datestr)
    header_line = "#                                 filename   interp_STLA    interp_STLO      STDP\n"

    with open(loc_file, "w+") as f:
        f.write(version_line)
        f.write(created_line)
        f.write(header_line)

        for e in sorted(event_list, key=lambda x: x.corrected_starttime):
            if e.is_stanford_event:
                # Revist this...
                continue

            f.write(fmt_spec.format(e.processed_file_name,
                                    np.float32(e.obspy_trace_stats.sac["stla"]),
                                    np.float32(e.obspy_trace_stats.sac["stlo"]),
                                    np.float32(e.obspy_trace_stats.sac["stdp"])))


def write_obspy_trace_stats(complete_dives, creation_datestr, processed_path, mfloat_path):
    '''Write mseed2sac metadata and automaid metadata files.

    Update this function if the fields in method
    `events.set_obspy_trace_stats` are changed.

    In total six files are written:

    mseed2sac_metadata_DET_REQ.csv (DET and REQ files, used by mseed2sac)
    mseed2sac_metadata_DET.csv (DET files only)
    mseed2sac_metadata_REQ.csv (REQ files only)

    automaid_metadata_DET_REQ.csv (DET and REQ files, ALL and ONLY SAC info defined in automaid)
    automaid_metadata_DET.csv (DET files only)
    automaid_metadata_REQ.csv (REQ files only)

    msee2sac_metadata*.csv:

        Usage: mseed2sac -m mseed2sac_metadata.csv *mseed

        From: https://github.com/iris-edu/mseed2sac/blob/master/doc/mseed2sac.md

        (01) Network (KNETWK)
        (02) Station (KSTNM)
        (03) Location (KHOLE)
        (04) Channel (KCMPNM)
        (05) Latitude (STLA)
        (06) Longitude (STLO)
        (07) Elevation (STEL), in meters [not currently used by SAC]
        (08) Depth (STDP), in meters [not currently used by SAC]
        (09) Component Azimuth (CMPAZ), degrees clockwise from north
        (10) Component Incident Angle (CMPINC), degrees from vertical
        (11) Instrument Name (KINST), up to 8 characters
        (12) Scale Factor (SCALE)
        (13) Scale Frequency, unused
        (14) Scale Units, unused
        (15) Sampling rate, unused
        (16) Start time, used for matching
        (17) End time, used for matching

    automaid_metadata*.csv:

        Prints ALL and ONLY the non-default SAC headers filled by automaid:

        (01) file name (from automaid; not a SAC header field)
        (02) KNETWK
        (03) KSTNM
        (04) KHOLE
        (05) KCMPNM
        (06) STLA
        (07) STLO
        (08) STEL
        (09) STDP
        (10) CMPAZ
        (11) CMPINC
        (12) KINST
        (13) SCALE
        (14) USER0 (SNR)
        (15) USER1 (criterion)
        (16) USER2 (trig)
        (17) USER3 (clockdrift correction)
        (18) KUSER0 (automaid version)
        (19) KUSER1 (REQ or DET and scales)
        (20) KUSER2 (CDF24 edge correction and normalization)
        (21) samplerate (not a SAC header field)
        (22) start (not a SAC header field)
        (23) end (not a SAC header field)

    '''

    ## NB, concerning filename abbreviations:
    ## m2s_* == mseed2sac
    ## atm_* == automaid*
    ##
    ## Previous versions wrote formatted text files for easy human readability.
    ## Those have since been nixed because it turned out that mseed2sac would
    ## actually generate convert miniSEED and generate SAC files with those
    ## metadata*.txt files, without warning that it only partially filled the
    ## header (e.g., skipping STLA/STLO because the .txt was not formatted in
    ## the expected .csv style).  The code to generate those is left here...

    # Version and creation-date lines are the same for both
    version_line = "#automaid {} ({})\n".format(setup.get_version(), setup.get_url())
    created_line = "#created {}\n".format(creation_datestr)

    # Generate header lines for all four files: generate .csv by replacing
    # spaces with commas in text format
    m2s_header_line_txt = "#net    sta   loc   chan           lat            lon      elev     depth   azimuth    SACdip  instrument     scale  scalefreq scaleunits samplerate                  start                    end\n"
    m2s_header_line_csv = ','.join(m2s_header_line_txt.split())  + '\n'

    # (add pound after comma substitution)
    atm_header_line_txt = "                               filename KNETWK    KSTNM KHOLE KCMPNM          STLA           STLO STEL      STDP CMPAZ CMPINC      KINST     SCALE            USER0            USER1     USER2            USER3      KUSER0      KUSER1      KUSER2 samplerate                  start                    end\n"
    atm_header_line_csv = '#' + ','.join(atm_header_line_txt.split()) + '\n'
    #atm_header_line_txt = '#' + atm_header_line_txt

    # Field specifiers for mseed2sac_metadata.csv and mseed2sac_metadata.txt
    m2s_fmt = ['{:>2s}',    # Network (KNETWK)
               '{:>5s}',    # Station (KSTNM)
               '{:>2s}',    # Location (KHOLE)
               '{:>3s}',    # Channel (KCMPNM)
               '{:>10.6f}', # Latitude (STLA)
               '{:>11.6f}', # Longitude (STLO)
               '{:>6.0f}',  # Elevation (STEL), in meters [not currently used by SAC]
               '{:>6.0f}',  # Depth (STDP), in meters [not currently used by SAC]
               '{:>6.0f}',  # Component Azimuth (CMPAZ), degrees clockwise from north
               '{:>6.0f}',  # Component Incident Angle (CMPINC), degrees from vertical
               '{:>8s}',    # Instrument Name (KINST), up to 8 characters
               '{:6.0f}',   # Scale Factor (SCALE)
               '{:>7.1f}',  # Scale Frequency, unused
               '{:>7s}',    # Scale Units, unused
               '{:>7.0f}',  # Sampling rate, unused
               '{:>19s}',   # Start time, used for matching
               '{:>19s}\n'] # End time, used for matching

    # Add four spaces between each field to format the text file
    #m2s_fmt_txt  = '    '.join(m2s_fmt)

    # Add comma between each field and remove field width (non-decimal) to format the csv
    m2s_fmt_csv  = ','.join(m2s_fmt)
    m2s_fmt_csv  = re.sub(':>\d*', ':', m2s_fmt_csv)

    # Field specifiers for automaid_metadata.csv and automaid_metadata.txt format
    atm_fmt = ['{:>40s}',   # file name (from automaid; not a SAC header field)
               '{:>3s}',    # KNETWK
               '{:>5s}',    # KSTNM
               '{:>2s}',    # KHOLE
               '{:>3s}',    # KCMPNM
               '{:>10.6F}', # STLA
               '{:>11.6f}', # STLO
               '{:>1.0F}',  # STEL
               '{:>6.0f}',  # STDP
               '{:>2.0F}',  # CMPAZ
               '{:>3.0f}',  # CMPINC
               '{:s}',      # KINST
               '{:>.0f}',   # SCALE
               '{:>13.6f}', # USER0 (detection SNR)
               '{:>13.6f}', # USER1 (detection criterion)
               '{:>6.0f}',  # USER2 (detection trigger sample index)
               '{:>13.6f}', # USER3 (clockdrift correction)
               '{:>8s}',    # KUSER0 (automaid version)
               '{:>8s}',    # KUSER1 (REQ or DET and scales)
               '{:>8s}',    # KUSER2 (CDF24 edge correction and normalization)
               '{:>7.0f}',  # samplerate (not a SAC header field)
               '{:>19s}',   # start (not a SAC header field)
               '{:>19s}\n'] # end (not a SAC header field)

    # Add four spaces between each field to format the text file
    #atm_fmt_txt  = '    '.join(atm_fmt)

    # Add comma between each field and remove field width (non-decimal) to format the csv
    atm_fmt_csv  = ','.join(atm_fmt)
    atm_fmt_csv  = re.sub(':>\d*', ':', atm_fmt_csv)

    # The base path (the folder) is the same for all four files
    base_path = os.path.join(processed_path, mfloat_path)
    m2s_path =  os.path.join(base_path, 'mseed2sac_metadata')
    atm_path =  os.path.join(base_path, 'automaid_metadata')

    # These are mseed2sac_metadata values that do not differ(yet?) between MERMAIDs
    scalefreq = np.float32(1.)
    scaleunits = 'Pa'

    # Open all files
    with open(m2s_path+"_DET_REQ.csv", "w+") as m2s_dr_csv, \
         open(m2s_path+"_DET.csv", "w+") as m2s_d_csv, \
         open(m2s_path+"_REQ.csv", "w+") as m2s_r_csv, \
         open(atm_path+'_DET_REQ.csv', "w+") as atm_dr_csv, \
         open(atm_path+'_DET.csv', "w+") as atm_d_csv, \
         open(atm_path+'_REQ.csv', "w+") as atm_r_csv:

         # open(m2s_path+".txt", "w+") as m2s_f_txt, \
         # open(atm_path+'.txt', "w+") as atm_f_txt, \

        ## Write version line and header line to all four files

        m2s_dr_csv.write(version_line)
        m2s_dr_csv.write(created_line)
        m2s_dr_csv.write(m2s_header_line_csv)

        m2s_d_csv.write(version_line)
        m2s_d_csv.write(created_line)
        m2s_d_csv.write(m2s_header_line_csv)

        m2s_r_csv.write(version_line)
        m2s_r_csv.write(created_line)
        m2s_r_csv.write(m2s_header_line_csv)

        # m2s_f_txt.write(version_line)
        # m2s_f_txt.write(created_line)
        # m2s_f_txt.write(m2s_header_line_txt)

        atm_dr_csv.write(version_line)
        atm_dr_csv.write(created_line)
        atm_dr_csv.write(atm_header_line_csv)

        atm_d_csv.write(version_line)
        atm_d_csv.write(created_line)
        atm_d_csv.write(atm_header_line_csv)

        atm_r_csv.write(version_line)
        atm_r_csv.write(created_line)
        atm_r_csv.write(atm_header_line_csv)

        # atm_f_txt.write(version_line)
        # atm_f_txt.write(created_line)
        # atm_f_txt.write(atm_header_line_txt)

        # Loop over all events for which a station location was computed
        event_list = [event for dive in complete_dives for event in dive.events if event.station_loc and not event.station_loc_is_preliminary]
        for e in sorted(event_list, key=lambda x: x.corrected_starttime):
            if e.is_stanford_event:
                # Revist this...
                continue

            ## Collect metadata and convert to np.float32()

            # For mseed2sac_metadata*.csv:
            net = e.obspy_trace_stats["network"]
            sta = e.obspy_trace_stats["station"]
            loc = e.obspy_trace_stats["location"]
            chan = e.obspy_trace_stats["channel"]
            lat = np.float32(e.obspy_trace_stats.sac["stla"])
            lon = np.float32(e.obspy_trace_stats.sac["stlo"])
            elev = np.float32(e.obspy_trace_stats.sac["stel"])
            depth = np.float32(e.obspy_trace_stats.sac["stdp"])
            azimuth = np.float32(e.obspy_trace_stats.sac["cmpaz"])
            SACdip = np.float32(e.obspy_trace_stats.sac["cmpinc"])
            instrument = e.obspy_trace_stats.sac["kinst"]
            scale = np.float32(e.obspy_trace_stats.sac["scale"])
            # scalefreq (local defined above)
            # scaleunits (local defined above)
            samplerate = np.float32(e.obspy_trace_stats["sampling_rate"])
            start = str(e.obspy_trace_stats["starttime"])[:19]
            end = str(e.obspy_trace_stats["endtime"])[:19]

            # Fields unique to automaid_metadata that are not in mseed2sac_metadata*.csv
            # (commented fields are defined in both files)
            filename = e.processed_file_name
            # KNETWK = net  (LHS are SAC names; RHS are their mseed2sac equivalents)
            # KSTNM = sta
            # KHOLE = loc
            # KCMPNM = chan
            # STLA = lat
            # STLO = lon
            # ELEV = elev
            # STDP = depth
            # CMPAZ = azimuth
            # CMPINC = SACdip
            # KINST = instrument
            # SCALE = scale
            USER0 = np.float32(e.obspy_trace_stats.sac["user0"])
            USER1 = np.float32(e.obspy_trace_stats.sac["user1"])
            USER2 = np.float32(e.obspy_trace_stats.sac["user2"])
            USER3 = np.float32(e.obspy_trace_stats.sac["user3"])
            KUSER0 = e.obspy_trace_stats.sac["kuser0"]
            KUSER1 = e.obspy_trace_stats.sac["kuser1"]
            KUSER2 = e.obspy_trace_stats.sac["kuser2"]
            # samplerate
            # start
            # end

            ## Group into correct order

            # mseed2sac_metadata.csv fields
            m2s_meta = [net,
                        sta,
                        loc,
                        chan,
                        lat,
                        lon,
                        elev,
                        depth,
                        azimuth,
                        SACdip,
                        instrument,
                        scale,
                        scalefreq,
                        scaleunits,
                        samplerate,
                        start,
                        end]

            # automaid_metadata.csv fields, with SAC names commented
            atm_meta = [filename,
                        net,
                        sta,
                        loc,
                        chan,
                        lat,
                        lon,
                        elev,
                        depth,
                        azimuth,
                        SACdip,
                        instrument,
                        scale,
                        USER0,
                        USER1,
                        USER2,
                        USER3,
                        KUSER0,
                        KUSER1,
                        KUSER2,
                        samplerate,
                        start,
                        end]

            ## Write DET and REQ info to both
            # m2s_f_txt.write(m2s_fmt_txt.format(*m2s_meta))
            m2s_dr_csv.write(m2s_fmt_csv.format(*m2s_meta))

            #atm_f_txt.write(atm_fmt_txt.format(*atm_meta))
            atm_dr_csv.write(atm_fmt_csv.format(*atm_meta))

            if not e.is_requested:
                m2s_d_csv.write(m2s_fmt_csv.format(*m2s_meta))
                atm_d_csv.write(atm_fmt_csv.format(*atm_meta))

            else:
                m2s_r_csv.write(m2s_fmt_csv.format(*m2s_meta))
                atm_r_csv.write(atm_fmt_csv.format(*atm_meta))

# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v2.7)
#
# Original author: Sebastien Bonnieux
# Current maintainer: Joel D. Simon (JDS)
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified by JDS: 09-Nov-2020, Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit

import os
import glob
import re
import subprocess
import numpy
from obspy import UTCDateTime
from obspy.core.stream import Stream
from obspy.core.trace import Trace
from obspy.core.trace import Stats
import plotly.graph_objs as graph
import plotly.offline as plotly
import matplotlib.pyplot as plt
import utils
import gps
import sys
import setup
from pdb import set_trace as keyboard

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
        self.events = list()
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
            with open(mer_file, "r") as f:
                content = f.read()
            events = content.split("</PARAMETERS>")[-1].split("<EVENT>")[1:]

            for event in events:
                # The header of this specific </EVENT> block (NOT the </ENVIRONMENT> of
                # the same .MER file, which may be unrelated (different time))
                mer_binary_header = event.split("<DATA>\x0A\x0D")[0]

                # The actual binary data contained in this </EVENT> block (the seismogram)
                mer_binary_binary = event.split("<DATA>\x0A\x0D")[1].split("\x0A\x0D\x09</DATA>")[0]

                # N.B:
                # "\x0A" is "\n": True
                # "\x0D" is "\r": True
                # "\x09" is "\t": True
                # https://docs.python.org/2/reference/lexical_analysis.html#string-and-bytes-literals
                # I don't know why Seb choose to represent the separators as
                # hex, I believe a valid split would be "...split('\n\r\t</DATA>')..."

                # The double split above is not foolproof; if the final data
                # block in the .MER file ends without </DATA> (i.e., the file
                # was not completely transmitted), the object 'binary' will just
                # return everything to the end of the file -- verify that the we
                # actually have the expected number of bytes (apparently len()
                # returns the byte-length of a string, though I am not super
                # happy with this solution because I would prefer to know the
                # specific encoding used for event binary...)
                actual_binary_length = len(mer_binary_binary)
                bytes_per_sample = int(re.search('BYTES_PER_SAMPLE=(\d+)', mer_binary_header).group(1))
                num_samples = int(re.search('LENGTH=(\d+)', mer_binary_header).group(1))
                expected_binary_length = bytes_per_sample * num_samples

                if actual_binary_length == expected_binary_length:
                    self.events.append(Event(mer_binary_name, mer_binary_header, mer_binary_binary))

            # Sort by date the list of events contained in this .MER file
            self.events.sort(key=lambda x: x.date)


    def __repr__(self):
        return "Events('{}', '{}')".format(self.base_path, self.mer_name)


    def get_events_between(self, begin, end):
        catched_events = list()
        for event in self.events:
            if begin < event.date < end:
                catched_events.append(event)
        return catched_events


class Event:
    '''The Event (singular) class references TWO .MER files, which may be the same,
    through Event.mer_binary_name (.MER file containing the </EVENT> binary
    data), and Event.mer_environment_name (.MER file containing the
    </ENVIRONMENT> metadata (e.g., GPS, clock drift, sampling freq. etc.)
    associated with that event)

    Only a SINGLE event (event binary block) is referenced by
    Event.mer_binary_name and Event.mer_environment_name

    '''

    def __init__(self, mer_binary_name=None, mer_binary_header=None, mer_binary_binary=None):
        self.mer_binary_name = mer_binary_name
        self.mer_binary_header = mer_binary_header
        self.mer_binary_binary = mer_binary_binary
        self.__version__ = version

        # Defaults
        self.mer_environment_name = None
        self.mer_environment = None

        self.data = None
        self.measured_fs = None
        self.decimated_fs = None
        self.trig = None
        self.depth = None
        self.temperature = None
        self.criterion = None
        self.snr = None
        self.scales = None

        self.date = None
        self.station_loc = None
        self.clockdrift_correction = None

        self.is_complete_mer_file = False
        self.is_requested = False

        self.scales = re.findall(" STAGES=(-?\d+)", self.mer_binary_header)[0]
        catch_trig = re.findall(" TRIG=(\d+)", self.mer_binary_header)
        if len(catch_trig) > 0:
            # Event detected with STA/LTA algorithm
            self.trig = int(catch_trig[0])
            date = re.findall(" DATE=(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6})", mer_binary_header, re.DOTALL)
            self.date = UTCDateTime.strptime(date[0], "%Y-%m-%dT%H:%M:%S.%f")
            self.depth = int(re.findall(" PRESSURE=(-?\d+)", self.mer_binary_header)[0])
            self.temperature = int(re.findall(" TEMPERATURE=(-?\d+)", self.mer_binary_header)[0])
            self.criterion = float(re.findall(" CRITERION=(\d+\.\d+)", self.mer_binary_header)[0])
            self.snr = float(re.findall(" SNR=(\d+\.\d+)", self.mer_binary_header)[0])
        else:
            # Event requested by user
            self.is_requested = True
            date = re.findall(" DATE=(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})", mer_binary_header, re.DOTALL)
            self.date = UTCDateTime.strptime(date[0], "%Y-%m-%dT%H:%M:%S")

    def __repr__(self):
        # Hacked repr dunder because I can't print binary...
        if self.mer_binary_binary:
            bin_str = '<int32 binary>'
        else:
            bin_str = self.mer_binary_binary

        return "Event('{}', '{}', {})".format(self.mer_binary_name, self.mer_binary_header, bin_str)

    def set_environment(self, mer_environment_name, mer_environment):
        self.mer_environment_name = mer_environment_name
        self.mer_environment = mer_environment

    def find_measured_sampling_frequency(self):
        # Get the frequency recorded in the .MER environment header
        fs_catch = re.findall("TRUE_SAMPLE_FREQ FS_Hz=(\d+\.\d+)", self.mer_environment)
        self.measured_fs = float(fs_catch[0])
        #self.measured_fs = 40

        # Divide frequency by number of scales
        int_scl = int(self.scales)
        if int_scl >= 0:
            self.decimated_fs = self.measured_fs / (2. ** (6 - int_scl))
        else:
            # This is raw data sampled at 40Hz
            self.decimated_fs = self.measured_fs

    def correct_date(self):
        # Calculate the date of the first sample
        if self.is_requested:
            # For a requested event
            rec_file_date = re.findall("FNAME=(\d{4}-\d{2}-\d{2}T\d{2}_\d{2}_\d{2})", self.mer_binary_header)
            rec_file_date = UTCDateTime.strptime(rec_file_date[0], "%Y-%m-%dT%H_%M_%S")

            rec_file_ms = re.findall("FNAME=\d{4}-\d{2}-\d{2}T\d{2}_\d{2}_\d{2}\.?(\d{6}?)", self.mer_binary_header)
            if len(rec_file_ms) > 0:
                rec_file_date += float("0." + rec_file_ms[0])

            sample_offset = re.findall("SMP_OFFSET=(\d+)", self.mer_binary_header)
            sample_offset = float(sample_offset[0])
            self.date = rec_file_date + sample_offset/self.measured_fs
        else:
            # For a detected event
            # The recorded date is the STA/LTA trigger date, subtract the time before the trigger.
            self.date = self.date - float(self.trig) / self.decimated_fs

    def correct_clockdrift(self, gps_descent, gps_ascent):
        # Correct the clock drift of the Mermaid board with GPS measurement
        pct = (self.date - gps_descent.date) / (gps_ascent.date - gps_descent.date)
        self.clockdrift_correction = gps_ascent.clockdrift * pct
        # Apply correction
        self.date = self.date + self.clockdrift_correction

    def compute_station_location(self, drift_begin_gps, drift_end_gps):
        '''Fills attribute self.station_loc, the interpolated location of MERMAID when
        it recorded an event

        '''
        self.station_loc = gps.linear_interpolation([drift_begin_gps, drift_end_gps], self.date)

    def invert_transform(self, bin_path=os.path.join(os.environ["AUTOMAID"], "scripts", "bin")):
        # If scales == -1 this is a raw signal, just convert binary data to numpy array of int32
        if self.scales == "-1":
            self.data = numpy.frombuffer(self.mer_binary_binary, numpy.int32)
            return

        # Get additional information on flavor of invert wavelet transform
        normalized = re.findall(" NORMALIZED=(\d+)", self.mer_environment)[0]
        edge_correction = re.findall(" EDGES_CORRECTION=(\d+)", self.mer_environment)[0]

        # Change to binary directory because these scripts can fail with full paths
        start_dir = os.getcwd();
        os.chdir(bin_path)

        # The following scripts READ wavelet coefficients (what MERMAID
        # generally sends) from a file named "wtcoeffs" and WRITE the inverted
        # data to a file name, e.g., "wtcoeffs.icdf24_5"
        wtcoeffs_data_file_name = "wtcoeffs"
        inverted_data_file_name = "wtcoeffs.icdf24_" + self.scales

        # Delete any previously-inverted data just to be absolutely sure we are
        # working with this events' data only (an interruption before the second
        # call to delete these files could result in their persistence)
        if os.path.exists(wtcoeffs_data_file_name):
            os.remove(wtcoeffs_data_file_name)

        if os.path.exists(inverted_data_file_name):
            os.remove(inverted_data_file_name)

        # Write cdf24 data
        with open(wtcoeffs_data_file_name, 'w') as f:
            f.write(self.mer_binary_binary)

        # The inverse wavelet transform C code (icdf24_v103(ec)_test) is called
        # below in a subprocess and its output is verified; determine if edge
        # correction needs to be accounted for
        icdf24_arg_list = list()
        if edge_correction == "1":
            icdf24_arg_list.append("icdf24_v103ec_test")

        else:
            icdf24_arg_list.append("icdf24_v103_test")


        # Extend the icdf24_v103(ec)_test argument list with other data values
        icdf24_arg_list.extend([self.scales, normalized, wtcoeffs_data_file_name])

        # Perform inverse wavelet transform
        stdout = subprocess.check_output(icdf24_arg_list)

        # Ensure the inverse wavelet transform worked as expected, meaning that
        # it generated an output file of int32 data
        if not os.path.exists(inverted_data_file_name):
            cmd  = ' '.join(map(str, icdf24_arg_list)) # prints python list as comma-separated string
            err_mess = "\nFailed: inverse wavelet transformation\n"
            err_mess += "In directory: {:s}\n".format(bin_path)
            err_mess += "Attempted command: {:s}\n".format(cmd)
            err_mess += "Using: event around {:s} in {:s}\n\n".format(self.date, self.mer_binary_name)
            err_mess += "Command printout:\n'{:s}'".format(stdout)

            # This output message is more helpful than the program crashing on
            # the next line
            sys.exit(err_mess)

        # Read the inverted data
        self.data = numpy.fromfile(inverted_data_file_name, numpy.int32)

        # Delete the files of coefficient and inverted data, otherwise a latter
        # .MER with an incomplete binary event block can come along and use the
        # same data
        os.remove(wtcoeffs_data_file_name)
        os.remove(inverted_data_file_name)

        # Return to start directory.
        os.chdir(start_dir)

    def get_export_file_name(self):
        export_file_name = UTCDateTime.strftime(UTCDateTime(self.date), "%Y%m%dT%H%M%S") + "." + self.mer_binary_name
        if not self.trig:
            export_file_name = export_file_name + ".REQ"
        else:
            export_file_name = export_file_name + ".DET"
        if self.scales == "-1":
            export_file_name = export_file_name + ".RAW"
        else:
            export_file_name = export_file_name + ".WLT" + self.scales
        return export_file_name

    def __get_figure_title(self):
        title = "" + self.date.isoformat() \
                + "     Fs = " + str(self.decimated_fs) + "Hz\n" \
                + "     Depth: " + str(self.depth) + " m" \
                + "     Temperature: " + str(self.temperature) + " degC" \
                + "     Criterion = " + str(self.criterion) \
                + "     SNR = " + str(self.snr)
        return title

    def plotly(self, export_path, force_redo=False):
        # Check if file exist
        export_path_html = export_path + self.get_export_file_name() + ".html"
        if not force_redo and os.path.exists(export_path_html):
            return

        # Add acoustic values to the graph
        data_line = graph.Scatter(x=utils.get_date_array(self.date, len(self.data), 1./self.decimated_fs),
                                  y=self.data,
                                  name="counts",
                                  line=dict(color='blue',
                                            width=2),
                                  mode='lines')

        data = [data_line]

        layout = graph.Layout(title=self.__get_figure_title(),
                              xaxis=dict(title='Coordinated Universal Time (UTC)', titlefont=dict(size=18)),
                              yaxis=dict(title='Counts', titlefont=dict(size=18)),
                              hovermode='closest'
                              )

        plotly.plot({'data': data, 'layout': layout},
                    filename=export_path_html,
                    auto_open=False)

    def plot_png(self, export_path, force_redo=False):
        # Check if file exist
        export_path_png = export_path + self.get_export_file_name() + ".png"
        if not force_redo and os.path.exists(export_path_png):
            return

        data = [d/(10**((-201.+25.)/20.) * 2 * 2**28/5. * 1000000) for d in self.data]

        # Plot frequency image
        plt.figure(figsize=(9, 4))
        plt.title(self.__get_figure_title(), fontsize=12)
        plt.plot(utils.get_time_array(len(self.data), 1./self.decimated_fs),
                 data,
                 color='b')
        plt.xlabel("Time (s)", fontsize=12)
        plt.ylabel("Pascal", fontsize=12)
        plt.tight_layout()
        plt.grid()
        plt.savefig(export_path_png)
        plt.clf()
        plt.close()

    def to_mseed(self, export_path, station_number, force_without_loc=False, force_redo=False):
        # Check if the station location has been calculated
        if self.station_loc is None and not force_without_loc:
            #print self.get_export_file_name() + ": Skip mseed generation, wait the next ascent to compute location"
            return

        # Check if file exist
        export_path_msd = export_path + self.get_export_file_name() + ".mseed"
        if not force_redo and os.path.exists(export_path_msd):
            return

        # Get stream object
        stream = self.get_stream(export_path, station_number, force_without_loc)

        # Save stream object
        stream.write(export_path_msd, format='MSEED')

    def to_sac(self, export_path, station_number, force_without_loc=False, force_redo=False):
        # Check if the station location has been calculated
        if self.station_loc is None and not force_without_loc:
            #print self.get_export_file_name() + ": Skip sac generation, wait the next ascent to compute location"
            return

        # Check if file exist
        export_path_sac = export_path + self.get_export_file_name() + ".sac"
        if not force_redo and os.path.exists(export_path_sac):
            return

        # Get stream object
        stream = self.get_stream(export_path, station_number, force_without_loc)

        # Save stream object
        stream.write(export_path_sac, format='SAC')

    def get_stream(self, export_path, station_number, force_without_loc=False):
       # Check if an interpolated station location exists
        if self.station_loc is None and not force_without_loc:
            return

        # Fill SAC header info
        stats = Stats()
        stats.sampling_rate = self.decimated_fs
        stats.network = "MH"
        stats.station = station_number
        stats.starttime = self.date
        stats.sac = dict()
        if not force_without_loc:
            stats.sac["stla"] = self.station_loc.latitude
            stats.sac["stlo"] = self.station_loc.longitude
        stats.sac["stdp"] = self.depth
        stats.sac["user0"] = self.snr
        stats.sac["user1"] = self.criterion
        stats.sac["user2"] = self.trig # samples
        stats.sac["user3"] = self.clockdrift_correction # seconds
        stats.sac["kuser0"] = self.__version__
        stats.sac["iztype"] = 9  # 9 == IB in sac format

        # Save data into a Stream object
        trace = Trace()
        trace.stats = stats
        trace.data = self.data
        stream = Stream(traces=[trace])

        return stream


def write_traces_txt(mdives, processed_path, mfloat_path):
    traces_file = os.path.join(processed_path, mfloat_path, "traces.txt")
    event_dive_tup = ((event, dive) for dive in mdives for event in dive.events if event.station_loc)

    fmt_spec = '{:>40s}    {:>15s}    {:>15s}    {:>15s}    {:>15s}    {:>15s}    {:>15s}    {:>15s}\n'
    with open(traces_file, "w+") as f:
        f.write("automaid {} ({})\n\n".format(setup.get_version(), setup.get_url()))
        f.write("                               FILE_NAME            BIN_MER      PREV_DIVE_LOG  PREV_DIVE_ENV_MER      THIS_DIVE_LOG  THIS_DIVE_ENV_MER      NEXT_DIVE_LOG  NEXT_DIVE_ENV_MER\n".format())

        for e, d in sorted(event_dive_tup, key=lambda x: x[0].date):
            f.write(fmt_spec.format(e.get_export_file_name(),
                                    e.mer_binary_name,
                                    d.prev_dive_log_name,
                                    d.prev_dive_mer_environment_name,
                                    d.log_name,
                                    d.mer_environment_name,
                                    d.next_dive_log_name,
                                    d.next_dive_mer_environment_name))


def write_loc_txt(mdives, processed_path, mfloat_path):
    '''Writes interpolated station locations at the time of event recording for all events for each
    individual float

    '''

    loc_file = os.path.join(processed_path, mfloat_path, "loc.txt")

    event_dive_tup = ((event, dive) for dive in mdives for event in dive.events if event.station_loc)

    fmt_spec = "{:>40s}    {:>10.6f}    {:>11.6f}    {:>4.0f}\n"
    version_line = "automaid {} ({})\n\n".format(setup.get_version(), setup.get_url())
    header_line = "                               FILE_NAME   INTERP_STLA    INTERP_STLO    STDP\n"

    with open(loc_file, "w+") as f:
        f.write(version_line)
        f.write(header_line)
        for e, d in sorted(event_dive_tup, key=lambda x: x[0].date):
            trace_name = e.get_export_file_name()
            STDP = e.depth if e.depth else float("nan")
            f.write(fmt_spec.format(trace_name,
                                    e.station_loc.latitude,
                                    e.station_loc.longitude,
                                    STDP))

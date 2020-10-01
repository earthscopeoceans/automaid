# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v2.7)
#
# Original author: Sebastien Bonnieux
#
# Current maintainer: Dr. Joel D. Simon (JDS)
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified by JDS: 01-Oct-2020, Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit

import setup
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
from pdb import set_trace as keyboard

# Get current version number.
version = setup.get_version()

class Events:
    events = None

    def __init__(self, base_path=None, mmd_name=None):
        # Initialize event list (if list is declared above, then elements of the
        # previous instance are kept in memory)
        self.__version__ = version
        self.events = list()

        # If just a base path to (e.g., a server directory) is passed, load all
        # .MER files contained there; otherwise read a single input file
        if mmd_name is None:
            mmd_files = glob.glob(os.path.join(base_path, "*.MER"))
        else:
            mmd_files = glob.glob(os.path.join(base_path, mmd_name))

        for mmd_file in mmd_files:
            mmd_data_name = mmd_file.split("/")[-1]
            with open(mmd_file, "r") as f:
                content = f.read()
            events = content.split("</PARAMETERS>")[-1].split("<EVENT>")[1:]
            for event in events:
                # Divide header and binary
                header = event.split("<DATA>\x0A\x0D")[0]
                binary = event.split("<DATA>\x0A\x0D")[1].split("\x0A\x0D\x09</DATA>")[0]
                self.events.append(Event(mmd_data_name, header, binary))

    def get_events_between(self, begin, end):
        catched_events = list()
        for event in self.events:
            if begin < event.date < end:
                catched_events.append(event)
        return catched_events


class Event:
    mmd_data_name = None
    mmd_file_is_complete = None
    environment = None
    header = None
    binary = None
    data = None
    date = None
    measured_fs = None   # Measured sampling frequency
    decimated_fs = None  # Sampling frequency of the received data
    trig = None
    depth = None
    temperature = None
    criterion = None
    snr = None
    requested = None
    station_loc = None
    drift_correction = None

    def __init__(self, mmd_data_name, header, binary):
        self.mmd_data_name = mmd_data_name
        self.header = header
        self.binary = binary
        self.__version__ = version

        self.scales = re.findall(" STAGES=(-?\d+)", self.header)[0]
        catch_trig = re.findall(" TRIG=(\d+)", self.header)
        if len(catch_trig) > 0:
            # Event detected with STA/LTA algorithm
            self.requested = False
            self.trig = int(catch_trig[0])
            date = re.findall(" DATE=(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6})", header, re.DOTALL)
            self.date = UTCDateTime.strptime(date[0], "%Y-%m-%dT%H:%M:%S.%f")
            self.depth = int(re.findall(" PRESSURE=(-?\d+)", self.header)[0])
            self.temperature = int(re.findall(" TEMPERATURE=(-?\d+)", self.header)[0])
            self.criterion = float(re.findall(" CRITERION=(\d+\.\d+)", self.header)[0])
            self.snr = float(re.findall(" SNR=(\d+\.\d+)", self.header)[0])
        else:
            # Event requested by user
            self.requested = True
            date = re.findall(" DATE=(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})", header, re.DOTALL)
            self.date = UTCDateTime.strptime(date[0], "%Y-%m-%dT%H:%M:%S")

    def set_environment(self, environment):
        self.environment = environment

    def find_measured_sampling_frequency(self):
        # Get the frequency recorded in the .MER environment header
        fs_catch = re.findall("TRUE_SAMPLE_FREQ FS_Hz=(\d+\.\d+)", self.environment)
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
        if self.requested:
            # For a requested event
            rec_file_date = re.findall("FNAME=(\d{4}-\d{2}-\d{2}T\d{2}_\d{2}_\d{2})", self.header)
            rec_file_date = UTCDateTime.strptime(rec_file_date[0], "%Y-%m-%dT%H_%M_%S")

            rec_file_ms = re.findall("FNAME=\d{4}-\d{2}-\d{2}T\d{2}_\d{2}_\d{2}\.?(\d{6}?)", self.header)
            if len(rec_file_ms) > 0:
                rec_file_date += float("0." + rec_file_ms[0])

            sample_offset = re.findall("SMP_OFFSET=(\d+)", self.header)
            sample_offset = float(sample_offset[0])
            self.date = rec_file_date + sample_offset/self.measured_fs
        else:
            # For a detected event
            # The recorded date is the STA/LTA trigger date, subtract the time before the trigger.
            self.date = self.date - float(self.trig) / self.decimated_fs

    def correct_clock_drift(self, gps_descent, gps_ascent):
        # Correct the clock drift of the Mermaid board with GPS measurement
        pct = (self.date - gps_descent.date) / (gps_ascent.date - gps_descent.date)
        self.drift_correction = gps_ascent.clockdrift * pct
        # Apply correction
        self.date = self.date + self.drift_correction

    def compute_station_location(self, drift_begin_gps, drift_end_gps):
        self.station_loc = gps.linear_interpolation([drift_begin_gps, drift_end_gps], self.date)

    def invert_transform(self, bin_path=os.path.join(os.environ["AUTOMAID"], "scripts", "bin")):
        # If scales == -1 this is a raw signal, just convert binary data to numpy array of int32
        if self.scales == "-1":
            self.data = numpy.frombuffer(self.binary, numpy.int32)
            return
        # Get additional information to invert wavelet
        normalized = re.findall(" NORMALIZED=(\d+)", self.environment)[0]
        edge_correction = re.findall(" EDGES_CORRECTION=(\d+)", self.environment)[0]

        # Change to binary directory. These scripts can fail with full paths.
        start_dir = os.getcwd();
        os.chdir(bin_path)

        # Write cdf24 data
        with open("wtcoeffs", 'w') as f:
            f.write(self.binary)

        # Do icd24
        if edge_correction == "1":
            #print "icdf24_v103ec_test"
            subprocess.check_output(["icdf24_v103ec_test",
                                     self.scales,
                                     normalized,
                                     "wtcoeffs"])
        else:
            #print "icdf24_v103_test"
            subprocess.check_output(["icdf24_v103_test",
                                    self.scales,
                                    normalized,
                                    "wtcoeffs"])
        # Read icd24 data
        self.data = numpy.fromfile("wtcoeffs.icdf24_" + self.scales, numpy.int32)

        # Return to start directory.
        os.chdir(start_dir)

    def get_export_file_name(self):
        export_file_name = UTCDateTime.strftime(UTCDateTime(self.date), "%Y%m%dT%H%M%S") + "." + self.mmd_data_name
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

    def plotly(self, export_path, force_with_incomplete_mmd=False):
        # Check if file exist
        export_path = export_path + self.get_export_file_name() + ".html"
        if os.path.exists(export_path):
            return

        # Return in the .MER file is incomplete (tranmission failure)
        if not self.mmd_file_is_complete and not force_with_incomplete_mmd:
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
                    filename=export_path,
                    auto_open=False)

    def plot_png(self, export_path, force_with_incomplete_mmd=False):
        # Check if file exist
        export_path = export_path + self.get_export_file_name() + ".png"
        if os.path.exists(export_path):
            return
        data = [d/(10**((-201.+25.)/20.) * 2 * 2**28/5. * 1000000) for d in self.data]

        # Return in the .MER file is incomplete (tranmission failure)
        if not self.mmd_file_is_complete and not force_with_incomplete_mmd:
            return

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
        plt.savefig(export_path)
        plt.clf()
        plt.close()

    def to_mseed(self, export_path, station_number, force_without_loc=False, force_with_incomplete_mmd=False):
        # Check if file exist
        export_path_msd = export_path + self.get_export_file_name() + ".mseed"
        if os.path.exists(export_path_msd):
            return

        # Return in the .MER file is incomplete (tranmission failure)
        if not self.mmd_file_is_complete and not force_with_incomplete_mmd:
            return

        # Check if the station location has been calculated
        if self.station_loc is None and not force_without_loc:
            #print self.get_export_file_name() + ": Skip mseed generation, wait the next ascent to compute location"
            return

        # Get stream object
        stream = self.get_stream(export_path, station_number, force_without_loc)

        # Save stream object
        stream.write(export_path_msd, format='MSEED')

    def to_sac(self, export_path, station_number, force_without_loc=False, force_with_incomplete_mmd=False):
        # Check if file exist
        export_path_sac = export_path + self.get_export_file_name() + ".sac"
        if os.path.exists(export_path_sac):
            return

        # Return in the .MER file is incomplete (tranmission failure)
        if not self.mmd_file_is_complete and not force_with_incomplete_mmd:
            return

        # Check if the station location has been calculated
        if self.station_loc is None and not force_without_loc:
            print self.get_export_file_name() + ": Skip sac generation, wait the next ascent to compute location"
            return

        # Get stream object
        stream = self.get_stream(export_path, station_number, force_without_loc)

        # Save stream object
        stream.write(export_path_sac, format='SAC')

    def get_stream(self, export_path, station_number, force_without_loc=False):
        # Check if file exist
        export_path_sac = export_path + self.get_export_file_name() + ".sac"
        export_path_msd = export_path + self.get_export_file_name() + ".mseed"
        if os.path.exists(export_path_sac) and os.path.exists(export_path_msd):
            return

        # Check if the station location have been calculated
        if self.station_loc is None and not force_without_loc:
            print self.get_export_file_name() + ": Skip sac/mseed generation, wait the next ascent to compute location"
            return

        # Fill header info
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
        if self.drift_correction is not None:
            stats.sac["user3"] = self.drift_correction # seconds
        else:
            stats.sac["user3"] = -12345.0 # undefined default
        stats.sac["kuser0"] = self.__version__
        stats.sac["iztype"] = 9  # 9 == IB in sac format

        # Save data into a Stream object
        trace = Trace()
        trace.stats = stats
        trace.data = self.data
        stream = Stream(traces=[trace])

        return stream

# Written by Sebastien Bonnieux.
# Last modified by jdsimon@princeton.edu,  20-Aug-2018.

# Change log -
#
# 20-Aug-2018: Added stats.sac["user2"] = self.trig

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


class Events:
    events = None

    def __init__(self, base_path=None):
        # Initialize event list (if list is declared above, then elements of the previous instance are kept in memory)
        self.events = list()
        # Read all Mermaid files and find events associated to the dive
        mer_files = glob.glob(base_path + "*.MER")
        for mer_file in mer_files:
            file_name = mer_file.split("/")[-1]
            with open(mer_file, "r") as f:
                content = f.read()
            events = content.split("</PARAMETERS>")[-1].split("<EVENT>")[1:]
            for event in events:
                # Divide header and binary
                header = event.split("<DATA>\x0A\x0D")[0]
                binary = event.split("<DATA>\x0A\x0D")[1].split("\x0A\x0D\x09</DATA>")[0]
                self.events.append(Event(file_name, header, binary))

    def get_events_between(self, begin, end):
        catched_events = list()
        for event in self.events:
            if begin < event.date < end:
                catched_events.append(event)
        return catched_events


class Event:
    file_name = None
    environment = None
    header = None
    binary = None
    data = None
    date = None
    fs = None
    trig = None
    depth = None
    temperature = None
    criterion = None
    snr = None
    requested = None
    station_loc = None
    drift_correction = None

    def __init__(self, file_name, header, binary):
        self.file_name = file_name
        self.header = header
        self.binary = binary
        self.scales = re.findall(" STAGES=(-?\d+)", self.header)[0]
        catch_trig = re.findall(" TRIG=(\d+)", self.header)
        if len(catch_trig) > 0:
            # Event detected with STA/LTA algorithm
            self.requested = False
            self.trig = int(catch_trig[0])
            date = re.findall(" DATE=(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6})", header, re.DOTALL)
            self.date = UTCDateTime.strptime(date[0], "%Y-%m-%dT%H:%M:%S.%f")
            self.depth = int(re.findall(" PRESSURE=(\d+)", self.header)[0])
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
        # Get true frequency measured on board
        fs_catch = re.findall("TRUE_SAMPLE_FREQ FS_Hz=(\d+\.\d+)", self.environment)
        if len(fs_catch) > 0:
            self.fs = float(fs_catch[0])
            # Divide frequency by number of scales
            int_scl = int(self.scales)
            if int_scl >= 0:
                self.fs = self.fs / (2.**(6-int_scl))
            else:
                # This is raw data sampled at 40Hz
                pass
        else:
            # Backward compatibility
            fs_catch = re.findall(" SAMPLING_RATE=(\d+\.\d+)", self.header)
            self.fs = float(fs_catch[0])

    def correct_date(self):
        if not self.requested:
            # Detected event: compute date of the first sample (recorded date is the trig date)
            self.date = self.date - float(self.trig) / self.fs

    def invert_transform(self):
        # If scales == -1 this is a raw signal, just convert binary data to numpy array of int32
        if self.scales == "-1":
            self.data = numpy.frombuffer(self.binary, numpy.int32)
            return
        # Get additional information to invert wavelet
        normalized = re.findall(" NORMALIZED=(\d+)", self.environment)[0]
        edge_correction = re.findall(" EDGES_CORRECTION=(\d+)", self.environment)[0]
        # Write cdf24 data
        with open("bin/wtcoeffs", 'w') as f:
            f.write(self.binary)
        # Do icd24
        if edge_correction == "1":
            subprocess.check_output(["bin/icdf24_v103ec_test",
                                     self.scales,
                                     normalized,
                                     "bin/wtcoeffs"])
        else:
            subprocess.check_output(["bin/icdf24_v103_test",
                                    self.scales,
                                    normalized,
                                    "bin/wtcoeffs"])
        # Read icd24 data
        self.data = numpy.fromfile("bin/wtcoeffs.icdf24_" + self.scales, numpy.int32)

    def correct_clock_drift(self, gps_descent, gps_ascent):
        pct = (self.date - gps_descent.date) / (gps_ascent.date - gps_descent.date)
        self.drift_correction = gps_ascent.clockdrift * pct
        # Apply correction
        self.date = self.date + self.drift_correction

    def compute_station_location(self, drift_begin_gps, drift_end_gps):
        self.station_loc = gps.linear_interpolation([drift_begin_gps, drift_end_gps], self.date)

    def get_export_file_name(self):
        export_file_name = UTCDateTime.strftime(UTCDateTime(self.date), "%Y%m%dT%H%M%S") + "." + self.file_name
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
                + "     Fs = " + str(self.fs) + "Hz\n" \
                + "     Depth: " + str(self.depth) + " m" \
                + "     Temperature: " + str(self.temperature) + " degC" \
                + "     Criterion = " + str(self.criterion) \
                + "     SNR = " + str(self.snr)
        return title

    def plotly(self, export_path):
        # Check if file exist
        export_path = export_path + self.get_export_file_name() + ".html"
        if os.path.exists(export_path):
            return
        # Add acoustic values to the graph
        data_line = graph.Scatter(x=utils.get_date_array(self.date, len(self.data), 1./self.fs),
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

    def plot(self, export_path):
        # Check if file exist
        export_path = export_path + self.get_export_file_name() + ".png"
        if os.path.exists(export_path):
            return
        # Plot frequency image
        plt.figure(figsize=(9, 4))
        plt.title(self.__get_figure_title(), fontsize=12)
        plt.plot(utils.get_time_array(len(self.data), 1./self.fs),
                 self.data,
                 color='b')
        plt.xlabel("Time (s)", fontsize=12)
        plt.ylabel("Counts", fontsize=12)
        plt.tight_layout()
        plt.grid()
        plt.savefig(export_path)
        plt.clf()
        plt.close()

    def to_sac_and_mseed(self, export_path, station_number, force_without_loc):
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
        stats.sampling_rate = self.fs
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
        stats.sac["user2"] = self.trig
        stats.sac["iztype"] = 9  # 9 == IB in sac format

        # Save data into a Stream object
        trace = Trace()
        trace.stats = stats
        trace.data = self.data
        stream = Stream(traces=[trace])

        # Save stream object
        stream.write(export_path_sac, format='SAC')
        stream.write(export_path_msd, format='MSEED')

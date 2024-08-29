# -*- coding: utf-8 -*-

import os
import sys
import csv
import glob
import re
import utils
import numpy
from obspy import UTCDateTime
import plotly.graph_objs as graph
import plotly.offline as plotly

import matplotlib as mpl
# if os.environ.get('DISPLAY','') == '':
#     print "no display found. Using non-interactive Agg backend"
#     mpl.use('agg',warn=False, force=True)
mpl.use('tkagg')
import matplotlib.pyplot as plt

class Profiles:
    events = None
    def __init__(self, base_path=None):
        # Initialize event list (if list is declared above, then elements of the previous instance are kept in memory)
        self.profiles = list()
        # Read all S41 files and find profiles associated to the dive
        profile_files = glob.glob(base_path + "*.S41")
        for profile_file in profile_files:
            file_name = profile_file.split("/")[-1]
            with open(profile_file, "r") as f:
                content = f.read()
            header = content.split("</PILOTS>\r\n")[0]
            if len(content.split("</PILOTS>\r\n")) > 1 :
                binary = content.split("</PILOTS>\r\n")[1]
                self.profiles.append(Profile(file_name,header,binary))
    def get_profiles_between(self, begin, end):
        catched_profiles = list()
        for profile in self.profiles:
            if begin < profile.date < end:
                catched_profiles.append(profile)
        return catched_profiles

class Profile:
    def __init__(self, file_name, header, binary):
        self.date = None
        self.old_version = None
        self.file_name = None
        self.header = None
        self.binary = None
        self.data = None
        self.data_pressure = None
        self.data_temperature = None
        self.data_salinity = None
        self.pcutoff = None
        self.samplerate = None
        self.top_bin_interval = None
        self.top_bin_size = None
        self.top_bin_max = None
        self.middle_bin_interval = None
        self.middle_bin_size = None
        self.middle_bin_max = None
        self.bottom_bin_interval = None
        self.bottom_bin_size = None
        self.include_transition_bin = None
        self.include_nbin = None
        self.continiousprofile = None
        self.speeddetection = None
        self.hexoutput = None
        self.binaverageoutput = None
        self.manualprofilerate = None
        self.runningpumpbeforeprofile = None
        self.speedstart = None

        self.file_name = file_name
        print("SBE41 file name : " + self.file_name)
        self.date = utils.get_date_from_file_name(file_name)
        self.header = header
        self.binary = binary
        self.pcutoff = re.findall("pcutoff=(-?\d+)", self.header)[0]
        self.old_version = True
        try:
            self.samplerate = re.findall("samplerate=(\d+)", self.header)[0]
        except IndexError:
            self.old_version = False
            self.samplerate = re.findall("samplerate=(\w+)", self.header)[0]
        self.top_bin_interval = re.findall("top_bin_interval=(\d+)", self.header)[0]
        self.top_bin_size = re.findall("top_bin_size=(\d+)", self.header)[0]
        self.top_bin_max = re.findall("top_bin_max=(\d+)", self.header)[0]
        self.middle_bin_interval = re.findall("middle_bin_interval=(\d+)", self.header)[0]
        self.middle_bin_size = re.findall("middle_bin_size=(\d+)", self.header)[0]
        self.middle_bin_max = re.findall("middle_bin_max=(\d+)", self.header)[0]
        self.bottom_bin_interval = re.findall("bottom_bin_interval=(\d+)", self.header)[0]
        self.bottom_bin_size = re.findall("bottom_bin_size=(\d+)", self.header)[0]
        self.include_transition_bin = re.findall("include_transition_bin=(\d+)", self.header)[0]
        self.include_nbin = re.findall("include_nbin=(\d+)", self.header)[0]
        self.continiousprofile = re.findall("continiousprofile=(\d+)", self.header)[0]
        self.speeddetection = re.findall("speeddetection=(\d+)", self.header)[0]
        self.hexoutput = re.findall("hexoutput=(\d+)", self.header)[0]
        self.binaverageoutput = re.findall("binaverageoutput=(\d+)", self.header)[0]
        self.manualprofilerate = re.findall("manualprofilerate=(\d+)", self.header)[0]
        self.runningpumpbeforeprofile = re.findall("runningpumpbeforeprofile=(\d+)", self.header)[0]
        self.speedstart = re.findall("speedstart=(\d+)", self.header)[0]
        try:
            if self.old_version:
                self.data = numpy.frombuffer(self.binary, numpy.int32)
            else:
                self.data = list()
                for index in range(0, len(self.binary), 3):
                    value = (ord(self.binary[index + 2]) << 16) +\
                            (ord(self.binary[index + 1]) << 8) +\
                            ord(self.binary[index])
                    self.data.append(value)
        except:
            print("error")
            self.data = None
        else:
            self.data_pressure = list()
            self.data_temperature = list()
            self.data_salinity = list()

            if self.hexoutput == '1':
                for index in range(0, len(self.data), 3):
                    if self.data[index] == 0x00000:
                        self.data_pressure.append(-10.0)
                    elif self.data[index] < 0xFFFFF:
                        self.data_pressure.append(float(self.data[index]) / 100.0 - 10.0)
                    else:
                        self.data_pressure.append(3000.0)

                    if self.data[index + 1] == 0x00000:
                        self.data_temperature.append(-5.0)
                    elif self.data[index + 1] < 0xFFFFF:
                        self.data_temperature.append(float(self.data[index + 1]) / 10000.0 - 5.0)
                    else:
                        self.data_temperature.append(35.0)

                    if self.data[index + 2] == 0x00000:
                        self.data_salinity.append(-1.0)
                    elif self.data[index + 2] < 0xFFFFF:
                        self.data_salinity.append(float(self.data[index + 2]) / 10000.0 - 1.0)
                    else:
                        self.data_salinity.append(45.0)


    def plot_temperature_html(self, processed_path, csv_file):
        if list(self.data):
            # Check if file exist
            export_name = UTCDateTime.strftime(UTCDateTime(self.date), "%Y%m%dT%H%M%S") + \
            "." + self.file_name + ".TEMP" + ".html"
            processed_path = processed_path + export_name
            if csv_file:
                csv_path = processed_path.replace(".TEMP.html",".csv")
                rows = zip(self.data_pressure,self.data_temperature,self.data_salinity)
                with open(csv_path, mode='w') as csv_file:
                    csv_file = csv.writer(csv_file, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                    for row in rows:
                        csv_file.writerow(row)
            if os.path.exists(processed_path):
                print(processed_path + "already exist")
                return
            print(export_name)
            # Add acoustic values to the graph
            data_line = graph.Scatter(x=self.data_temperature,
                                      y=self.data_pressure,
                                      marker=dict(size=6,
                                                  cmax=30,
                                                  cmin=-2,
                                                  color=self.data_temperature,
                                                  colorbar=dict(title="Temperatures (Deg C)"),
                                                  colorscale="Bluered"),
                                      mode="markers",
                                      name="Temperatures (Deg C)")

            data = [data_line]
            layout = graph.Layout(title="CTD Profile with SBE41 [Temperature = f(Pressures)] ",
                                  xaxis=dict(title='Temperatures (Deg C)', titlefont=dict(size=18)),
                                  yaxis=dict(title='Pressures (dbar)', titlefont=dict(
                                      size=18), autorange="reversed"),
                                  hovermode='closest'
                                  )

            plotly.plot({'data': data, 'layout': layout},
                        filename=processed_path,
                        auto_open=False)
        else:
            print(processed_path + " can't be exploited for temperature profile")

    def plot_salinity_html(self, processed_path):
        if list(self.data):
            # Check if file exist
            processed_path = processed_path + \
                UTCDateTime.strftime(UTCDateTime(self.date), "%Y%m%dT%H%M%S") + \
                "." + self.file_name + ".SAL" + ".html"
            if os.path.exists(processed_path):
                print(processed_path + "already exist")
                return
            # Add acoustic values to the graph
            data_line = graph.Scatter(x=self.data_salinity,
                                      y=self.data_pressure,
                                      marker=dict(size=9,
                                                  cmax=39,
                                                  cmin=31,
                                                  color=self.data_salinity,
                                                  colorbar=dict(title="Salinity (PSU)"),
                                                  colorscale="aggrnyl"),
                                      mode="markers",
                                      name="Salinity (PSU)")

            data = [data_line]

            layout = graph.Layout(title="CTD Profile with SBE41 [Salinity = f(Pressures)]",
                                  xaxis=dict(title='Salinity (PSU)', titlefont=dict(size=18)),
                                  yaxis=dict(title='Pressures (dbar)', titlefont=dict(
                                      size=18), autorange="reversed"),
                                  hovermode='closest'
                                  )

            plotly.plot({'data': data, 'layout': layout},
                        filename=processed_path,
                        auto_open=False)
        else:
            print(processed_path + " can't be exploited for salinity profile")

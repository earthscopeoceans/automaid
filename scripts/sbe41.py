# -*- coding: utf-8 -*-
#
# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v3.10)
#
# Developer: Frédéric rocca <FRO>
# Contact:  frederic.rocca@osean.fr
# Last modified by FRO: 09-Sep-2024
# Last tested: Python 3.10.13, 22.04.3-Ubuntu

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
import struct
import traceback
import matplotlib as mpl

if os.environ.get('DISPLAY', '') == '':
    print("no display found. Using non-interactive Agg backend")
    mpl.use('agg', force=True)

import matplotlib.pyplot as plt

class Profiles:
    profiles = None
    params = None

    def __init__(self, base_path=None):
        # Initialize event list (if list is declared above, then elements of the previous instance are kept in memory)
        self.profiles = list()
        if not base_path:
            return
        # Read all S41 files and find profiles associated to the dive
        profile_files = glob.glob(base_path + "*.S41")
        for profile_file in profile_files:
            file_name = profile_file.split("/")[-1]
            with open(profile_file, "rb") as f:
                content = f.read()
            splitted = content.split(b'</PARAMETERS>\r\n')
            header = splitted[0].decode('latin1')
            if len(splitted) > 1:
                binary = splitted[1]
                self.profiles.append(Profile(file_name, header, binary))

    def get_profiles_between(self, begin, end):
        catched_profiles = list()
        for profile in self.profiles:
            if begin < profile.date < end:
                catched_profiles.append(profile)
        return catched_profiles


class Profile:
    file_name = None
    header = None
    data = None
    data_pressure = None
    data_temperature = None
    data_salinity = None
    data_nbin = None

    binary = None
    fast_sample = None
    date = None
    version = None
    output_pressure = None
    echo_cmd = None
    auto_bin_avg = None
    include_nbin = None
    include_transition_bin = None
    ts_wait_s = None
    p_cut_off_dbar = None
    top_bin_interval_dbar = None
    top_bin_size_dbar = None
    top_bin_max_dbar = None
    middle_bin_interval_dbar = None
    middle_bin_size_dbar = None
    middle_bin_max_dbar = None
    bottom_bin_interval_dbar = None
    bottom_bin_size_dbar = None
    manual_profil = None
    speed_detection = None
    bin_average_output = None
    load_test_sample = None
    manual_profil_rate_h = None
    running_pump_before_profile_s = None
    speed_start_mbar_per_s = None
    speed_control_mbar_per_s = None

    def __init__(self, file_name, header, binary):
        self.file_name = file_name
        print(("SBE41 file name : " + self.file_name))
        self.date = utils.get_date_from_file_name(file_name)
        self.header = header
        self.binary = binary

        header_split = self.header.replace("<PARAMETERS>\r\n", "").split(";")
        self.version = int(header_split[0], 16)
        start_index = 1
        if self.version == 0x7E:
            self.fast_sample = int(header_split[1], 16)
            start_index = 2
        else :
            self.fast_sample = 0
        self.output_pressure = int(header_split[start_index], 16)
        self.echo_cmd = int(header_split[start_index+1], 16)
        self.auto_bin_avg = int(header_split[start_index+2], 16)
        self.include_nbin = int(header_split[start_index+3], 16)
        self.include_transition_bin = int(header_split[start_index+4], 16)
        self.ts_wait_s = int(header_split[start_index+5], 16)
        self.p_cut_off_dbar = int(header_split[start_index+6], 16)
        self.top_bin_interval_dbar = int(header_split[start_index+7], 16)
        self.top_bin_size_dbar = int(header_split[start_index+8], 16)
        self.top_bin_max_dbar = int(header_split[start_index+9], 16)
        self.middle_bin_interval_dbar = int(header_split[start_index+10], 16)
        self.middle_bin_size_dbar = int(header_split[start_index+11], 16)
        self.middle_bin_max_dbar = int(header_split[start_index+12], 16)
        self.bottom_bin_interval_dbar = int(header_split[start_index+13], 16)
        self.bottom_bin_size_dbar = int(header_split[start_index+14], 16)
        self.manual_profil = int(header_split[start_index+15], 16)
        self.speed_detection = int(header_split[start_index+16], 16)
        self.bin_average_output = int(header_split[start_index+17], 16)
        self.load_test_sample = int(header_split[start_index+18], 16)
        self.manual_profil_rate_h = int(header_split[start_index+19], 16)
        self.running_pump_before_profile_s = int(header_split[start_index+20], 16)
        self.speed_start_mbar_per_s = int(header_split[start_index+21], 16)
        self.speed_control_mbar_per_s = int(header_split[start_index+22], 16)
        try:
            if self.include_nbin > 0:
                self.data = numpy.frombuffer(self.binary, numpy.dtype(
                    [('pressLSB', 'u1'),('pressMID', 'u1'),('pressMSB', 'u1'),
                    ('tempLSB', 'u1'),('tempMID', 'u1'),('tempMSB', 'u1'),
                    ('salLSB', 'u1'),('salMID', 'u1'),('salMSB', 'u1')
                    ,('nbin', 'u1')]))
            else:
                self.data = numpy.frombuffer(self.binary, numpy.dtype(
                    [('pressLSB', 'u1'),('pressMID', 'u1'),('pressMSB', 'u1'),
                    ('tempLSB', 'u1'),('tempMID', 'u1'),('tempMSB', 'u1'),
                    ('salLSB', 'u1'),('salMID', 'u1'),('salMSB', 'u1')]))
        except:
            traceback.print_exc()
            self.data = None
        else:
            self.data_pressure = list()
            self.data_temperature = list()
            self.data_salinity = list()
            self.data_nbin = list()

            rangeIndex = None
            if self.bin_average_output > 0:
                rangeIndex = range(0, len(self.data), 1)
            else :
                # reverse array when data are discrete
                rangeIndex = range(len(self.data)-1, -1, -1)
            for index in rangeIndex :
                press = (self.data[index]['pressMSB'] << 16) |(self.data[index]['pressMID'] << 8) |self.data[index]['pressLSB']
                temp = (self.data[index]['tempMSB'] << 16) |(self.data[index]['tempMID'] << 8) |self.data[index]['tempLSB']
                sal = (self.data[index]['salMSB'] << 16) |(self.data[index]['salMID'] << 8) |self.data[index]['salLSB']
                if not (press == 0 and temp == 0 and sal == 0):
                    self.data_pressure.append((float(press) / 100.0) - 10.0)
                    self.data_temperature.append((float(temp) / 10000.0) - 5)
                    self.data_salinity.append((float(sal) / 10000.0) - 1)
                    if self.include_nbin > 0:
                        self.data_nbin.append(self.data[index]['nbin'])

    def parameters_header(self):
        header = " <output_pressure>"+str(self.output_pressure)+"</output_pressure>\r\n"
        header += " <fast_sample>"+str(self.fast_sample)+"</fast_sample>\r\n"
        header += " <echo_cmd>"+str(self.echo_cmd)+"</echo_cmd>\r\n"
        header += " <auto_bin_avg>"+str(self.auto_bin_avg)+"</auto_bin_avg>\r\n"
        header += " <include_nbin>"+str(self.include_nbin)+"</include_nbin>\r\n"
        header += " <include_transition_bin>"+str(self.include_transition_bin)+"</include_transition_bin>\r\n"
        header += " <ts_wait_s>"+str(self.ts_wait_s)+"</ts_wait_s>\r\n"
        header += " <p_cut_off_dbar>"+str(self.p_cut_off_dbar)+"</p_cut_off_dbar>\r\n"
        header += " <top_bin_interval_dbar>"+str(self.top_bin_interval_dbar)+"</top_bin_interval_dbar>\r\n"
        header += " <top_bin_size_dbar>"+str(self.top_bin_size_dbar)+"</top_bin_size_dbar>\r\n"
        header += " <top_bin_max_dbar>"+str(self.top_bin_max_dbar)+"</top_bin_max_dbar>\r\n"
        header += " <middle_bin_interval_dbar>"+str(self.middle_bin_interval_dbar)+"</middle_bin_interval_dbar>\r\n"
        header += " <middle_bin_size_dbar>"+str(self.middle_bin_size_dbar)+"</middle_bin_size_dbar>\r\n"
        header += " <middle_bin_max_dbar>"+str(self.middle_bin_max_dbar)+"</middle_bin_max_dbar>\r\n"
        header += " <bottom_bin_interval_dbar>"+str(self.bottom_bin_interval_dbar)+"</bottom_bin_interval_dbar>\r\n"
        header += " <bottom_bin_size_dbar>"+str(self.bottom_bin_size_dbar)+"</bottom_bin_size_dbar>\r\n"
        header += " <manual_profil>"+str(self.manual_profil)+"</manual_profil>\r\n"
        header += " <speed_detection>"+str(self.speed_detection)+"</speed_detection>\r\n"
        header += " <bin_average_output>"+str(self.bin_average_output)+"</bin_average_output>\r\n"
        header += " <load_test_sample>"+str(self.load_test_sample)+"</load_test_sample>\r\n"
        header += " <manual_profil_rate_h>"+str(self.manual_profil_rate_h)+"</manual_profil_rate_h>\r\n"
        header += " <running_pump_before_profile_s>"+str(self.running_pump_before_profile_s)+"</running_pump_before_profile_s>\r\n"
        header += " <speed_start_mbar_per_s>"+str(self.speed_start_mbar_per_s)+"</speed_start_mbar_per_s>\r\n"
        header += " <speed_control_mbar_per_s>"+str(self.speed_control_mbar_per_s)+"</speed_control_mbar_per_s>\r\n"
        return header

    def write_csv(self, export_path) :
        if list(self.data):
            export_name = UTCDateTime.strftime(UTCDateTime(self.date), "%Y%m%dT%H%M%S") + \
                "." + self.file_name + ".csv"
            export_path = export_path + export_name
            rows = list(zip(self.data_pressure, self.data_temperature, self.data_salinity))
            with open(export_path, mode='w') as csv_file:
                csv_file = csv.writer(
                    csv_file, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                for row in rows:
                    csv_file.writerow(row)
        else:
            print((export_path + " can't be exploited for csv data"))

    def write_temperature_html(self, export_path, optimize=False, include_plotly=True):
        if list(self.data):
            # Check if file exist
            export_name = UTCDateTime.strftime(UTCDateTime(self.date), "%Y%m%dT%H%M%S") + \
                "." + self.file_name + ".TEMP" + ".html"
            export_path = export_path + export_name
            if os.path.exists(export_path):
                print((export_path + "already exist"))
                return

            print(export_name)
            # Plotly you can implement WebGL with Scattergl() in place of Scatter()
            # for increased speed, improved interactivity, and the ability to plot even more data.
            Scatter = graph.Scatter
            if optimize :
                Scatter = graph.Scattergl
            data_line = Scatter(x=self.data_temperature,
                                y=self.data_pressure,
                                marker=dict(size=6,
                                            cmax=30,
                                            cmin=-2,
                                            color=self.data_temperature,
                                            colorbar=dict(
                                                title="Temperatures (Deg C)"),
                                            colorscale="Bluered"),
                                mode="markers",
                                name="Temperatures (Deg C)")

            data = [data_line]
            layout = graph.Layout(title="CTD Profile with SBE41 [Temperature = f(Pressures)] ",
                                  xaxis=dict(
                                      title='Temperatures (Deg C)', titlefont=dict(size=18)),
                                  yaxis=dict(title='Pressures (dbar)', titlefont=dict(
                                      size=18), autorange="reversed"),
                                  hovermode='closest'
                                  )
            figure = graph.Figure(data=data, layout=layout)
            # Include plotly into any html files ?
            # If false user need connexion to open html files
            if include_plotly :
                figure.write_html(file=export_path, include_plotlyjs=True)
            else :
                figure.write_html(file=export_path,
                                  include_plotlyjs='cdn', full_html=False)
        else:
            print((export_path + " can't be exploited for temperature profile"))

    def write_salinity_html(self, export_path, optimize=False, include_plotly=True):
        if list(self.data):
            # Check if file exist
            export_path = export_path + \
                UTCDateTime.strftime(UTCDateTime(self.date), "%Y%m%dT%H%M%S") + \
                "." + self.file_name + ".SAL" + ".html"
            if os.path.exists(export_path):
                print((export_path + "already exist"))
                return
            # Add acoustic values to the graph
            data_line = Scatter(x=self.data_salinity,
                                y=self.data_pressure,
                                marker=dict(size=9,
                                            cmax=39,
                                            cmin=31,
                                            color=self.data_salinity,
                                            colorbar=dict(
                                                title="Salinity (PSU)"),
                                            colorscale="aggrnyl"),
                                mode="markers",
                                name="Salinity (PSU)")

            data = [data_line]
            layout = graph.Layout(title="CTD Profile with SBE41 [Salinity = f(Pressures)]",
                                  xaxis=dict(title='Salinity (PSU)',
                                             titlefont=dict(size=18)),
                                  yaxis=dict(title='Pressures (dbar)', titlefont=dict(
                                      size=18), autorange="reversed"),
                                  hovermode='closest'
                                  )
            figure = graph.Figure(data=data, layout=layout)
            # Include plotly into any html files ?
            # If false user need connexion to open html files
            if include_plotly :
                figure.write_html(file=export_path, include_plotlyjs=True)
            else :
                figure.write_html(file=export_path,
                                  include_plotlyjs='cdn', full_html=False)
        else:
            print((export_path + " can't be exploited for salinity profile"))

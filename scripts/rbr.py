# -*- coding: utf-8 -*-
#
# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v3.10)
#
# Developer: Frédéric rocca <FRO>
# Contact:  frederic.rocca@osean.fr
# Last modified by FRO: 08-Sep-2025
# Last tested: 


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
from plotly.subplots import make_subplots
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
        # Read all S61 files and find profiles associated to the dive
        profile_files = glob.glob(base_path + "*.RBR")
        for profile_file in profile_files:
            file_name = profile_file.split("/")[-1]
            with open(profile_file, "rb") as f:
                content = f.read()
            splitted = content.split(b'</PARAMETERS>\r\n')
            header = splitted[0].decode('latin1')
            if len(splitted) > 1:
                binary = splitted[1]
                profil = Profile(file_name, header, binary)
                print(profil)
                self.profiles.append(profil)

    def get_profiles_between(self, begin, end):
        catched_profiles = list()
        for profile in self.profiles:
            if begin < profile.date < end:
                catched_profiles.append(profile)
        return catched_profiles

class Dataset:
    name: None
    header: None
    data: None
    chanellist:None
    channel_description: None
    dtype:None
    data_array:None
    def __init__(self, name, binary):
        self.name = name
        self.channel_description = {
            "pressure_00": "Absolute pressure (dbar)",
            "seapressure_00": "Hydrostatic pressure (dbar)",
            "temperature_00": "Marine temperature (°C)",
            "conductivity_00": "Conductivity (mS/cm)",
            "salinity_00": "Salinity (PSU)",
            "salinitydyncorr_00": "Salinity <with correction> (PSU)",
            "conductivitycelltemperature_00": "Conductivity cell temperature (°C)",
            "temperaturedyncorr_00": "Marine temperature <with correction> (°C)",
            "count_00": "Counts",
            "depth_00": "Depth in meter",
        }
        data = binary.split(b">\r\n", 1)
        if len(data) > 1 :
            self.header = data[0]
            self.data = data[1]
        if self.header :
            chanellist = re.findall(b" CHANNELLIST=(.+)", self.header)
            if len(chanellist) > 0 :
                self.chanellist = ["timestamp"]
                self.dtype = [('timestamp','<u8')]
                chanellist = chanellist[0].split(b"|")
                for channel in chanellist:
                    channel_name = channel.decode('latin1')
                    self.chanellist.append(channel_name)
                    self.dtype += [(channel_name,'<f4')]
                self.data_array = numpy.frombuffer(self.data, numpy.dtype(self.dtype))

class Profile:
    file_name = None
    header = None
    #PARK
    park_period_s = -1
    #ASCENT
    ascent_cut_off_dbar = -1
    #regime 1
    ascent_bottom_max_dbar = -1 
    ascent_bottom_size_dbar = -1
    ascent_bottom_period_ms = -1
    #regime 2
    ascent_middle_max_dbar = -1 
    ascent_middle_size_dbar = -1
    ascent_middle_period_ms = -1
    #regime 3
    ascent_top_max_dbar = -1 
    ascent_top_size_dbar = -1
    ascent_top_period_ms = -1
    datasets = None
    data = None
    data_pressure = None
    data_temperature = None
    data_salinity = None
    data_nbin = None
    binary = None
    def __init__(self, file_name, header, binary):
        self.file_name = file_name
        print(("RBR file name : " + self.file_name))
        self.date = utils.get_date_from_file_name(file_name)
        self.header = header
        self.binary = binary
        park_period = re.findall("<PARK PERIOD=(\d+)>", self.header)
        if len(park_period) > 0:
            self.park_period_s = park_period[0]
        bottom = re.findall("BOTTOM=(\d+):(\d+):(\d+)", self.header)
        if len(bottom) > 0:
            self.ascent_bottom_max_dbar = bottom[0][0]
            self.ascent_bottom_size_dbar = bottom[0][1]
            self.ascent_bottom_period_ms = bottom[0][2]
        middle = re.findall("MIDDLE=(\d+):(\d+):(\d+)", self.header)
        if len(middle) > 0:
            self.ascent_middle_max_dbar = middle[0][0]
            self.ascent_middle_size_dbar = middle[0][1]
            self.ascent_middle_period_ms = middle[0][2]            
        top = re.findall("TOP=(\d+):(\d+):(\d+)", self.header)
        if len(top) > 0 :
            self.ascent_top_max_dbar = top[0][0]
            self.ascent_top_size_dbar = top[0][1]
            self.ascent_top_period_ms = top[0][2]
        final_cutoff = re.findall("FINAL=(\d+)", self.header)
        if len(final_cutoff) > 0 :
            self.ascent_cut_off_dbar = final_cutoff[0]
        self.datasets = []
        datasets = self.binary.split(b'</DATA>\x0D\x0A')
        for dataset in datasets:
            name = re.findall(b" CONFIG=(\w+) ", dataset)
            if len(name) > 0 :
                self.datasets.append(Dataset(name[0].decode('latin1'),dataset))

    def write_csv(self, export_path) :
        if len(self.datasets) > 0:
            index = -1
            export_name = UTCDateTime.strftime(UTCDateTime(self.date), "%Y%m%dT%H%M%S") + "." + self.file_name
            export_path = export_path + export_name
            for dataset in self.datasets:
                index = index + 1
                dataset_name = dataset.name + str(index)
                dataset_path =  export_path + "_" + dataset_name + ".csv"  
                rows = dataset.data_array.tolist()
                with open(dataset_path, mode='w') as csv_file:
                    csv_file = csv.writer(
                        csv_file, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                    csv_file.writerow(dataset.chanellist)
                    for row in rows:
                        x = list(row)
                        x[0] = UTCDateTime(x[0]/1000)
                        row = tuple(x)
                        csv_file.writerow(row)
        else:
            print((export_path + " can't be exploited for csv data"))

    def write_park_html(self, export_path, optimize=False, include_plotly=True):
        if len(self.datasets) > 0:
            index = -1
            for dataset in self.datasets:
                index = index + 1
                if not dataset.name == "PARK":
                    continue
                # Check if file exist
                export_name = UTCDateTime.strftime(UTCDateTime(self.date), "%Y%m%dT%H%M%S") + \
                    "." + self.file_name + ".PARK" + str(index) + ".html"
                export_path = export_path + export_name
                if os.path.exists(export_path):
                    print((export_path + " already exist"))
                    continue
                print(export_name)
                #Plotly you can implement WebGL with Scattergl() in place of Scatter()
                # for increased speed, improved interactivity, and the ability to plot even more data.
                Scatter = graph.Scatter
                if optimize :
                    Scatter = graph.Scattergl

                rows_nb = len(dataset.chanellist)-1
                timestamp = [UTCDateTime(t/1000) for t in dataset.data_array["timestamp"]]
                figure = make_subplots(rows=rows_nb, cols=1,shared_xaxes=True,vertical_spacing=0.02)
                for channel in dataset.chanellist[1:]:
                    channel_name = channel + " (" + dataset.channel_description[channel] + ")"
                    trace = Scatter(x=timestamp,y=dataset.data_array[channel],mode="lines+markers",name=channel_name)
                    figure.add_trace(trace,row=rows_nb, col=1)
                    #figure.update_yaxes(title_text=dataset.channel_description[channel], row=rows_nb, col=1)
                    rows_nb = rows_nb - 1;

                figure.update_layout(title_text="Measurements performed in park mode")
                if include_plotly :
                    figure.write_html(file=export_path, include_plotlyjs=True)
                else :
                    figure.write_html(file=export_path,include_plotlyjs='cdn', full_html=False)                
           

    def write_temperature_html(self, export_path, optimize=False, include_plotly=True):
        if len(self.datasets) > 0:
            ascent_dataset = None
            for dataset in self.datasets:
                if dataset.name == "ASCENT":
                    ascent_dataset = dataset
                    if not "pressure_00" in ascent_dataset.chanellist :
                        print((export_path + " no pressure_00 channel"))
                        return 
                    if not "temperature_00" in ascent_dataset.chanellist :
                        print((export_path + " no temperature_00 channel"))
                        return 
            if not ascent_dataset:
                print((export_path + " no ascent dataset"))
                return

            # Check if file exist
            export_name = UTCDateTime.strftime(UTCDateTime(self.date), "%Y%m%dT%H%M%S") + \
                "." + self.file_name + ".TEMP" + ".html"
            export_path = export_path + export_name
            if os.path.exists(export_path):
                print((export_path + "already exist"))
                return

            print(export_name)
            #Plotly you can implement WebGL with Scattergl() in place of Scatter()
            # for increased speed, improved interactivity, and the ability to plot even more data.
            Scatter = graph.Scatter
            if optimize :
                Scatter = graph.Scattergl

            data_line = Scatter(x=ascent_dataset.data_array["temperature_00"],
                                y=ascent_dataset.data_array["pressure_00"],
                                marker=dict(size=6,cmax=30,cmin=-2,color=ascent_dataset.data_array["temperature_00"],
                                            colorbar=dict(title="Marine temperature (°C)"),
                                            colorscale="Bluered"),
                                mode="markers",
                                name="Marine temperature (°C)")

            data = [data_line]
            layout = graph.Layout(title="CTD Profile with RBR [Temperature = f(Pressures)] ",
                                  xaxis=dict(title='Marine temperature (°C)', titlefont=dict(size=18)),
                                  yaxis=dict(title='Absolute pressure (dbar) (at surface will read around 10 dbar)', titlefont=dict(size=18), autorange="reversed"),
                                  hovermode='closest')
            figure = graph.Figure(data=data, layout=layout)
            #Include plotly into any html files ?
            #If false user need connexion to open html files
            if include_plotly :
                figure.write_html(file=export_path, include_plotlyjs=True)
            else :
                figure.write_html(file=export_path,include_plotlyjs='cdn', full_html=False)
        else:
            print((export_path + " can't be exploited for temperature profile"))

    def write_salinity_html(self, export_path, optimize=False, include_plotly=True):
        if len(self.datasets) > 0:
            ascent_dataset = None
            for dataset in self.datasets:
                if dataset.name == "ASCENT":
                    ascent_dataset = dataset
                    if not "pressure_00" in ascent_dataset.chanellist :
                        print((export_path + " no pressure_00 channel"))
                        return 
                    if not "salinity_00" in ascent_dataset.chanellist :
                        print((export_path + " no salinity_00 channel"))
                        return 
            if not ascent_dataset:
                print((export_path + " no ascent dataset"))
                return

            # Check if file exist
            export_name = UTCDateTime.strftime(UTCDateTime(self.date), "%Y%m%dT%H%M%S") + \
                "." + self.file_name + ".SAL" + ".html"
            export_path = export_path + export_name
            if os.path.exists(export_path):
                print((export_path + "already exist"))
                return

            print(export_name)
            #Plotly you can implement WebGL with Scattergl() in place of Scatter()
            # for increased speed, improved interactivity, and the ability to plot even more data.
            Scatter = graph.Scatter
            if optimize :
                Scatter = graph.Scattergl

            data_line = Scatter(x=ascent_dataset.data_array["salinity_00"],
                                y=ascent_dataset.data_array["pressure_00"],
                                marker=dict(size=9,cmax=39,cmin=31,color=ascent_dataset.data_array["salinity_00"],
                                            colorbar=dict(title="Salinity without dynamic correction applied (PSU)"),colorscale="aggrnyl"),
                                mode="markers",
                                name="Salinity (PSU)")

            data = [data_line]
            layout = graph.Layout(title="CTD Profile with RBR [Salinity = f(Pressures)] ",
                                  xaxis=dict(title='Salinity without dynamic correction applied (PSU)', titlefont=dict(size=18)),
                                  yaxis=dict(title='Absolute pressure (dbar) (at surface will read around 10 dbar)', titlefont=dict(size=18), autorange="reversed"),
                                  hovermode='closest')
            figure = graph.Figure(data=data, layout=layout)
            #Include plotly into any html files ?
            #If false user need connexion to open html files
            if include_plotly :
                figure.write_html(file=export_path, include_plotlyjs=True)
            else :
                figure.write_html(file=export_path,include_plotlyjs='cdn', full_html=False)
        else:
            print((export_path + " can't be exploited for temperature profile"))

    def __str__(self):
        string = "<PARK CONFIGURATION>\n"
        string += "park_period_s={}\n".format(self.park_period_s)
        string += "<ASCENT CONFIGURATION>\n"
        string += "ascent_cut_off_dbar={}\n".format(self.ascent_cut_off_dbar)
        string += "ascent_bottom_max_dbar={}\n".format(self.ascent_bottom_max_dbar)
        string += "ascent_bottom_size_dbar={}\n".format(self.ascent_bottom_size_dbar)
        string += "ascent_bottom_period_ms={}\n".format(self.ascent_bottom_period_ms)
        string += "ascent_middle_max_dbar={}\n".format(self.ascent_middle_max_dbar)
        string += "ascent_middle_size_dbar={}\n".format(self.ascent_middle_size_dbar)
        string += "ascent_middle_period_ms={}\n".format(self.ascent_middle_period_ms)
        string += "ascent_top_max_dbar={}\n".format(self.ascent_top_max_dbar)
        string += "ascent_top_size_dbar={}\n".format(self.ascent_top_size_dbar)
        string += "ascent_top_period_ms={}\n".format(self.ascent_top_period_ms)
        string += "ascent_cut_off_dbar={}\n".format(self.ascent_cut_off_dbar)
        string += "<DATASET>\n"
        for dataset in self.datasets:
            string += "{}:{} {}\n".format(dataset.name,dataset.chanellist, dataset.dtype)
            string += "{}\n".format(dataset.data_array)
        return string

            

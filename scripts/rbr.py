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
    schedule:None
    data: None
    def __init__(self, name, binary):
        self.name = name
        schedule = re.findall(b" SCHEDULE=(.+)", binary)
        if len(schedule) > 0 :
            self.schedule = schedule


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
        regime1 = re.findall("REGIME1=(\d+):(\d+):(\d+)", self.header)
        if len(regime1) > 0:
            self.ascent_bottom_max_dbar = regime1[0][0]
            self.ascent_bottom_size_dbar = regime1[0][1]
            self.ascent_bottom_period_ms = regime1[0][2]
        regime2 = re.findall("REGIME2=(\d+):(\d+):(\d+)", self.header)
        if len(regime2) > 0:
            self.ascent_middle_max_dbar = regime2[0][0]
            self.ascent_middle_size_dbar = regime2[0][1]
            self.ascent_middle_period_ms = regime2[0][2]            
        regime3 = re.findall("REGIME3=(\d+):(\d+):(\d+)", self.header)
        if len(regime3) > 0 :
            self.ascent_top_max_dbar = regime3[0][0]
            self.ascent_top_size_dbar = regime3[0][1]
            self.ascent_top_period_ms = regime3[0][2]
        cutoff = re.findall("CUTOFF=(\d+)", self.header)
        if len(cutoff) > 0 :
            self.ascent_cut_off_dbar = cutoff[0]
        self.datasets = []
        datasets = self.binary.split(b'</DATA>\x0D\x0A')
        for dataset in datasets:
            name = re.findall(b" DATASET=(.+)", dataset)
            if len(name) > 0 :
                self.datasets.append(Dataset(name[0],dataset))

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
            string += "{}:{}\n".format(dataset.name,dataset.schedule)
        return string

            

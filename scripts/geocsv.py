# -*- coding: utf-8 -*-
#
# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v2.7)
#
# Author: Joel. D Simon
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified: 15-Dec-2020, Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit

import csv
import pickle

class GeoCSV:
    """Organize MERMAID metadata and write them to GeoCSV format

    Args:
        dives (list): List of dives.Dive instances

    Attributes:
        dives (list): List of dives.Dive instances

    """

    def __init__(self, dives=None):
        self.dives = dives


if __name__ == "__main__":
    dive_list = pickle.load( open('mdives.p', 'rb'))
    geocsv = GeoCSV(dive_list)

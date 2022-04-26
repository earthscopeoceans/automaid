# -*- coding: utf-8 -*-
#
# Read and display contents of an .mhpsd file in Python.
#
# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v2.7)
#
# Developer: Joel D. Simon (JDS)
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified by JDS: 26-Apr-2022
# Last tested: Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit

# This block is just `addpath` since I'm not working locally in automaid
import os
import sys
sys.path.insert(1, os.path.join(os.getenv('AUTOMAID'), 'scripts'))

# Read and display the example .mhpsd file
from pprint import pprint
import mermaidpsd

filename = '20211116T125142.0002_6194A40E.MER.STD.mhpsd'
mhpsd = mermaidpsd.read(filename)

pprint(mhpsd.hdr)
pprint(mhpsd.psd['perc50'])
pprint(mhpsd.psd['perc95'])

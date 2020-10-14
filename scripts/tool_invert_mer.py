# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v2.7)
#
# Usage: python tool_invert_mer.py [.MER file]
#
# Converts a single .MER file without location interpolation, and places the SAC
# and miniSEED outputs into the same directory as the input .MER file.
#
# Warning:
# * does not correct for MERMAID clock drift, but that does not explain
#   the entire time difference between using this tool and main.py...
#
# Original author: Sebastien Bonnieux
# Current maintainer: Dr. Joel D. Simon (JDS)
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified by JDS: 13-Oct-2020, Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit

import setup
import events
import re
import sys
import os
from pdb import set_trace as keyboard

# Get current version number.
version = setup.get_version()

fullpath_file_name = os.path.abspath(sys.argv[1])
mmd_file_name = os.path.basename(fullpath_file_name)
mmd_file_path = os.path.join(os.path.dirname(fullpath_file_name), "")

def invert_main():
    mevents = events.Events(mmd_file_path, mmd_file_name)
    for event in mevents.events:
        with open(os.path.join(mmd_file_path, event.mmd_data_name), 'r') as f:
            content = f.read()
        environment = re.findall("<ENVIRONMENT>.+</PARAMETERS>", content, re.DOTALL)[0]
        event.set_environment(environment)
        event.find_measured_sampling_frequency()
        event.correct_date()
        event.invert_transform()
        event.to_sac(mmd_file_path, station_number="00", force_without_loc=True)
        event.to_mseed(mmd_file_path, station_number="00", force_without_loc=True)
        event.plotly(mmd_file_path)
        event.plot_png(mmd_file_path)

if __name__ == "__main__":
    invert_main()

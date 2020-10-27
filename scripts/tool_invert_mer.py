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
# Last modified by JDS: 23-Oct-2020, Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit

import events
import re
import sys
import os
import gps
import setup
from pdb import set_trace as keyboard

# Get current version number.
version = setup.get_version()

# Parse input
fullpath_file_name = os.path.abspath(sys.argv[1])
mer_file_name = os.path.basename(fullpath_file_name)
mer_file_path = os.path.join(os.path.dirname(fullpath_file_name), "")

def invert_main():
    # Pull all events from this .MER file
    mevents = events.Events(mer_file_path, mer_file_name)
    fullpath_mer_name = os.path.join(mer_file_path, mer_file_name)

    # Get station number
    station_number = mer_file_name.split('_')[0]

    # Collect header block from this .MER file
    with open(fullpath_mer_name, 'r') as f:
        content = f.read()
        environment = re.findall("<ENVIRONMENT>.+</PARAMETERS>", content, re.DOTALL)[0]

    # Collect GPS list from the header -- the subsequent events we loop through
    # must be contained within these GPS times otherwise this .MER environment
    # is not references by the .MER events contained therein
    gpsl = gps.get_gps_from_mer_environment(mer_file_name, environment)

    for event in mevents.events:
        if not gpsl[0].date < event.date < gpsl[-1].date:
            print("Event at {:s} is not associated (date out of range) with {:s} " \
                  "environment...skipping".format(event.date, mer_file_name))
            continue

        event.set_environment(mer_file_name, environment)
        event.find_measured_sampling_frequency()
        event.correct_date()
        event.invert_transform()
        event.to_sac(mer_file_path, station_number, force_without_loc=True, force_redo=True)
        event.to_mseed(mer_file_path, station_number, force_without_loc=True, force_redo=True)
        event.plotly(mer_file_path, force_redo=True)
        event.plot_png(mer_file_path, force_redo=True)

if __name__ == "__main__":
    invert_main()

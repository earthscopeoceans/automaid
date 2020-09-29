# automaid v1.1.0
# pymaid environment (Python v2.7)
#
# Usage: python tool_invert_mer.py [.MER file]
#
# Converts a single .MER file without location interpolation, and places the SAC
# and miniSEED outputs into the same directory as the input .MER file.
#
# Warning: does not correct for MERMAID clock drift, but that does not explain
#          the entire time difference between using this tool and main.py...
#
# Original author: Sebastien Bonnieux
#
# Current maintainer: Dr. Joel D. Simon (JDS)
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified by JDS: 17-Sep-2020, Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit

import setup
import events
import re
import sys
import os
from pdb import set_trace as keyboard

# Get current version number.
version = setup.get_version()

mer_file_name = sys.argv[1];
mer_file_path = os.path.join(os.path.split(mer_file_name)[0], "")

def invert_main():
    mevents = events.Events(mer_file_path, mer_file_name)
    for event in mevents.events:
        with open(os.path.join(mer_file_path, event.file_name), 'r') as f:
            content = f.read()
        environment = re.findall("<ENVIRONMENT>.+</PARAMETERS>", content, re.DOTALL)[0]
        event.set_environment(environment)
        event.find_measured_sampling_frequency()
        event.correct_date()
        event.invert_transform()
        event.plotly(mer_file_path)
        event.plot_png(mer_file_path)
        event.to_sac(mer_file_path, station_number="00", force_without_loc=True)
        event.to_mseed(mer_file_path, station_number="00", force_without_loc=True)

if __name__ == "__main__":
    invert_main()

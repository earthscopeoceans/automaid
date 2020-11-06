# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v2.7)
#
# Original author: Sebastien Bonnieux
# Current maintainer: Joel D. Simon (JDS)
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified by JDS: 05-Nov-2020, Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit

import os
import argparse
import shutil
import glob
import datetime
import dives
import events
import vitals
import kml
import gps
import setup
import re
import utils
from pprint import pprint
from pdb import set_trace as keyboard

# Get current version number.
version = setup.get_version()

# Set depth of mixed layer (in meters) for drift interpolation
mixed_layer_depth_m = 50

# Set default paths
automaid_path = os.environ["AUTOMAID"]
def_mermaid_path = os.environ["MERMAID"]
def_server_path = os.path.join(def_mermaid_path, "server")
def_processed_path = os.path.join(def_mermaid_path, "processed")

# Parse (optional) command line inputs to override default paths
parser = argparse.ArgumentParser()
# problem: metavar=''   prints: "-s , --server"
# problem: metavar='\b' prints: "-s, --server", but misaligns the help statement...
parser.add_argument('-s',
                    '--server',
                    default=def_server_path,
                    dest='server',
                    #metavar='\b',
                    help="server directory (default: {:s})".format(def_server_path))
parser.add_argument('-p',
                    '--processed',
                    default=def_processed_path,
                    dest='processed',
                    #metavar='',
                    help="processed directory (default: {:s})".format(def_processed_path))
args = parser.parse_args()
server_path = os.path.abspath(args.server)
processed_path = os.path.abspath(args.processed)

# Set a time range of analysis for a specific float
filterDate = {
    "452.112-N-01": (datetime.datetime(2018, 12, 27), datetime.datetime(2100, 1, 1)),
    "452.112-N-02": (datetime.datetime(2018, 12, 28), datetime.datetime(2100, 1, 1)),
    "452.112-N-03": (datetime.datetime(2018, 4, 9), datetime.datetime(2100, 1, 1)),
    "452.112-N-04": (datetime.datetime(2019, 1, 3), datetime.datetime(2100, 1, 1)),
    "452.112-N-05": (datetime.datetime(2019, 1, 3), datetime.datetime(2100, 1, 1)),
    "452.020-P-06": (datetime.datetime(2018, 6, 26), datetime.datetime(2100, 1, 1)),
    "452.020-P-07": (datetime.datetime(2018, 6, 27), datetime.datetime(2100, 1, 1)),
    "452.020-P-08": (datetime.datetime(2018, 1, 1), datetime.datetime(2100, 1, 1)),
    "452.020-P-09": (datetime.datetime(2018, 1, 1), datetime.datetime(2100, 1, 1)),
    "452.020-P-10": (datetime.datetime(2018, 1, 1), datetime.datetime(2100, 1, 1)),
    "452.020-P-11": (datetime.datetime(2018, 1, 1), datetime.datetime(2100, 1, 1)),
    "452.020-P-12": (datetime.datetime(2018, 1, 1), datetime.datetime(2100, 1, 1)),
    "452.020-P-13": (datetime.datetime(2018, 1, 1), datetime.datetime(2100, 1, 1)),
    "452.020-P-16": (datetime.datetime(2018, 1, 1), datetime.datetime(2100, 1, 1)),
    "452.020-P-17": (datetime.datetime(2018, 1, 1), datetime.datetime(2100, 1, 1)),
    "452.020-P-18": (datetime.datetime(2018, 1, 1), datetime.datetime(2100, 1, 1)),
    "452.020-P-19": (datetime.datetime(2018, 1, 1), datetime.datetime(2100, 1, 1)),
    "452.020-P-20": (datetime.datetime(2018, 1, 1), datetime.datetime(2100, 1, 1)),
    "452.020-P-21": (datetime.datetime(2018, 1, 1), datetime.datetime(2100, 1, 1)),
    "452.020-P-22": (datetime.datetime(2018, 1, 1), datetime.datetime(2100, 1, 1)),
    "452.020-P-23": (datetime.datetime(2018, 1, 1), datetime.datetime(2100, 1, 1)),
    "452.020-P-24": (datetime.datetime(2018, 1, 1), datetime.datetime(2100, 1, 1)),
    "452.020-P-25": (datetime.datetime(2018, 1, 1), datetime.datetime(2100, 1, 1)),
    "452.020-P-0050": (datetime.datetime(2019, 8, 11), datetime.datetime(2100, 1, 1)),
    "452.020-P-0051": (datetime.datetime(2019, 7, 1), datetime.datetime(2100, 1, 1)),
    "452.020-P-0052": (datetime.datetime(2019, 7, 1), datetime.datetime(2100, 1, 1)),
    "452.020-P-0053": (datetime.datetime(2019, 7, 1), datetime.datetime(2100, 1, 1)),
    "452.020-P-0054": (datetime.datetime(2019, 7, 1), datetime.datetime(2100, 1, 1))
}

# Boolean set to true in order to delete every processed data and redo everything
redo = False

# Plot interactive figures in HTML format for acoustic events
# WARNING: Plotly files takes a lot of memory so commented by default
events_plotly = False
events_mseed = True
events_sac = True
events_png = False

# Dictionary to save data in a file
dives_dict = dict()

def main():
    # Set working directory in "scripts"
    os.chdir(os.path.join(automaid_path, "scripts", ""))

    # Create processed directory if it doesn't exist
    if not os.path.exists(processed_path):
        os.mkdir(processed_path)

    # Search Mermaid floats
    vitfile_path = os.path.join(server_path, "*.vit")
    mfloats = [p.split("/")[-1][:-4] for p in glob.glob(vitfile_path)]

    # Initialize empty dict to hold the instance of every last complete dive for
    # every MERMAID
    lastdive = dict()

    # For each Mermaid float
    for mfloat in mfloats:
        mfloat_serial = mfloat[-4:]
        print("Processing {:s} .LOG & .MER files...".format(mfloat_serial))

        # Set the path for the float
        mfloat_path = os.path.join(processed_path, mfloat, "")

        # Get float number
        mfloat_nb = re.findall("(\d+)$", mfloat)[0]

        # Delete the directory if the redo flag is true
        if redo and os.path.exists(mfloat_path):
            shutil.rmtree(mfloat_path)

        # Create directory for the float
        if not os.path.exists(mfloat_path):
            os.mkdir(mfloat_path)

        # Remove existing files in the processed directory (the script may have been previously
        # executed, copied the files, then failed)
        for f in glob.glob(mfloat_path + "*.*"):
            os.remove(f)

        # Copy appropriate files in the directory and remove files outside of the time range
        files_to_copy = list()
        extensions = ["000", "001", "002", "003", "004", "005", "LOG", "MER"]
        for extension in extensions:
            files_to_copy += glob.glob(os.path.join(server_path, mfloat_nb +  "*." + extension))
        if mfloat in filterDate.keys():
            begin = filterDate[mfloat][0]
            end = filterDate[mfloat][1]
            files_to_copy = [f for f in files_to_copy if begin <= utils.get_date_from_file_name(f) <= end]
        else:
            # keep all files
            begin = datetime.datetime(1000, 1, 1)
            end = datetime.datetime(3000, 1, 1)

        # Add .vit and .out files
        files_to_copy += glob.glob(os.path.join(server_path, mfloat + "*"))

        # Copy files
        for f in files_to_copy:
            shutil.copy(f, mfloat_path)


        # Build list of all mermaid events recorded by the float
        print(" ...compiling a list of events from {:s} .MER files (GPS & seismic data)..." \
              .format(mfloat_serial))
        mevents = events.Events(mfloat_path)

        # Correlate the list of events with each dive.
        print(" ...matching those events to {:s} .LOG ('dive') files (GPS & dive metadata)..." \
              .format(mfloat_serial))

        # Really: collect all the .LOG files in order (1 .LOG == 1 Dive)
        mdives = dives.get_dives(mfloat_path, mevents)

        # Compute files for each dive
        for dive in mdives:
            # Create the directory
            if not os.path.exists(dive.export_path):
                os.mkdir(dive.export_path)
            # Generate log
            dive.generate_datetime_log()
            # Generate mermaid environment file
            dive.generate_mermaid_environment_file()
            # Generate dive plot
            dive.generate_dive_plotly()

        # Compute clock drift correction for each event, and build list of GPS locations
        for dive in mdives:
            dive.correct_events_clockdrift()

        # Interpolate for the locations that MERMAID passed out of/in to the surface and mixed
        # layers, and where it was when it recorded any events associated with the dive
        mdives[0].compute_station_locations(None, mdives[1], mixed_layer_depth_m)
        i = 1
        while i < len(mdives)-1:
            mdives[i].compute_station_locations(mdives[i-1], mdives[i+1], mixed_layer_depth_m)
            i += 1

        # We skipped event computation for the last dive (awaiting the next dive's GPS) which also
        # adds a reference to the previous dive; correct that here for the last Dive instance
        if len(mdives) > 1:
            mdives[-1].prev_dive_log_name = mdives[-2].log_name
            mdives[-1].prev_dive_mer_environment_name = mdives[-2].mer_environment_name

        # Generate plots, SAC, and miniSEED files
        print(" ...writing {:s} sac/mseed/png/html output files...".format(mfloat_serial))
        for dive in mdives:
            if events_png:
                dive.generate_events_png()
            if events_plotly:
                dive.generate_events_plotly()
            if events_sac:
                dive.generate_events_sac()
            if events_mseed:
                dive.generate_events_mseed()

        # Plot vital data
        kml.generate(mfloat_path, mfloat, mdives)
        vitals.plot_battery_voltage(mfloat_path, mfloat + ".vit", begin, end)
        vitals.plot_internal_pressure(mfloat_path, mfloat + ".vit", begin, end)
        vitals.plot_pressure_offset(mfloat_path, mfloat + ".vit", begin, end)
        if len(mdives) > 1:
            vitals.plot_corrected_pressure_offset(mfloat_path, mdives, begin, end)

        # Write text file containing all GPS fixes from .LOG and .MER
        gps.write_gps_txt(mdives, processed_path, mfloat_path, mfloat)

        # Write text file detailing event-station location interpolation parameters
        gps.write_gps_interpolation_txt(mdives, processed_path, mfloat_path, mfloat)

        # Write helpful printout detailing every dive, and how .LOG and .MER
        # files connect
        dives.generate_printout(mdives, mfloat_serial)

        # Write the same info just printout do stdout to text file
        dives.write_dives_txt(mdives, processed_path, mfloat_path, mfloat)

        # Write a text file relating all SAC and mSEED to their associated .LOG
        # and .MER files
        events.write_traces_txt(mdives, processed_path, mfloat_path, mfloat)

        # Clean directories
        for f in glob.glob(mfloat_path + "/" + mfloat_nb + "_*.LOG"):
            os.remove(f)
        for f in glob.glob(mfloat_path + "/" + mfloat_nb + "_*.MER"):
            os.remove(f)

        # Add dives to growing dict
        dives_dict[mfloat] = mdives


    # Done looping through all dives for each float
    #______________________________________________________________________________________#

    # Print a text file of corrected external pressures measured on the final
    # dive, and warn if any are approaching the limit of 300 mbar (at which
    # point adjustment is required)
    vitals.write_corrected_pressure_offset(dives_dict, processed_path)

if __name__ == "__main__":
    main()

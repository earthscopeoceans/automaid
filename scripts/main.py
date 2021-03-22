# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v2.7)
#
# Usage: python main.py [-p processed] [-s server]
#
# Developer: Joel D. Simon (JDS)
# Original author: Sebastien Bonnieux
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified by JDS: 05-Mar-2021
# Last tested: Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit


import os
import re
import glob
import shutil
import argparse
import datetime

import kml
import gps
import setup
import dives
import utils
import events
import vitals
import geocsv

# Get current version number.
version = setup.get_version()

# Set depth of mixed layer (in meters) for drift interpolation
mixed_layer_depth_m = 50

# Toggle preliminary (rapid) location estimates on and off
preliminary_location_ok = False

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

# Set an inclusive time range of analysis for a specific float
filterDate = {
    "452.112-N-01": (datetime.datetime(2018, 12, 27), datetime.datetime(2100, 1, 1)),
    "452.112-N-02": (datetime.datetime(2018, 12, 28), datetime.datetime(2100, 1, 1)),
    "452.112-N-03": (datetime.datetime(2018, 4, 9), datetime.datetime(2100, 1, 1)),
    "452.112-N-04": (datetime.datetime(2019, 1, 3), datetime.datetime(2100, 1, 1)),
    "452.112-N-05": (datetime.datetime(2019, 1, 3), datetime.datetime(2100, 1, 1)),
    "452.020-P-06": (datetime.datetime(2018, 6, 26), datetime.datetime(2100, 1, 1)),
    "452.020-P-07": (datetime.datetime(2018, 6, 27), datetime.datetime(2100, 1, 1)),
    # *
    "452.020-P-08": (datetime.datetime(2018, 8,  5, 13, 23, 14), datetime.datetime(2100, 1, 1)),
    "452.020-P-09": (datetime.datetime(2018, 8,  6, 15, 21, 26), datetime.datetime(2100, 1, 1)),
    "452.020-P-10": (datetime.datetime(2018, 8,  7, 12, 53, 42), datetime.datetime(2100, 1, 1)),
    "452.020-P-11": (datetime.datetime(2018, 8,  9, 11,  2,  6), datetime.datetime(2100, 1, 1)),
    "452.020-P-12": (datetime.datetime(2018, 8, 10, 19, 51, 31), datetime.datetime(2100, 1, 1)),
    "452.020-P-13": (datetime.datetime(2018, 8, 31, 16, 50, 23), datetime.datetime(2100, 1, 1)),
    "452.020-P-16": (datetime.datetime(2018, 9,  4,  7, 12, 15), datetime.datetime(2100, 1, 1)),
    "452.020-P-17": (datetime.datetime(2018, 9,  4, 11,  2, 54), datetime.datetime(2100, 1, 1)),
    "452.020-P-18": (datetime.datetime(2018, 9,  5, 17, 38, 32), datetime.datetime(2100, 1, 1)),
    "452.020-P-19": (datetime.datetime(2018, 9,  6, 20,  7, 30), datetime.datetime(2100, 1, 1)),
    "452.020-P-20": (datetime.datetime(2018, 9,  8, 10, 32,  8), datetime.datetime(2100, 1, 1)),
    "452.020-P-21": (datetime.datetime(2018, 9,  9, 17, 42, 36), datetime.datetime(2100, 1, 1)),
    "452.020-P-22": (datetime.datetime(2018, 9, 10, 19,  7, 21), datetime.datetime(2100, 1, 1)),
    "452.020-P-23": (datetime.datetime(2018, 9, 12,  2,  4, 14), datetime.datetime(2100, 1, 1)),
    "452.020-P-24": (datetime.datetime(2018, 9, 13,  8, 52, 18), datetime.datetime(2100, 1, 1)),
    "452.020-P-25": (datetime.datetime(2018, 9, 14, 11, 57, 12), datetime.datetime(2100, 1, 1)),
    # *
    "452.020-P-0050": (datetime.datetime(2019, 8, 11), datetime.datetime(2100, 1, 1)),
    "452.020-P-0051": (datetime.datetime(2019, 7, 1), datetime.datetime(2100, 1, 1)),
    "452.020-P-0052": (datetime.datetime(2019, 7, 1), datetime.datetime(2100, 1, 1)),
    "452.020-P-0053": (datetime.datetime(2019, 7, 1), datetime.datetime(2100, 1, 1)),
    "452.020-P-0054": (datetime.datetime(2019, 7, 1), datetime.datetime(2100, 1, 1))
}
# *I found dates in the same range (~minutes before) as misalo.txt and set these filterDates to the
# actual corresponding date in the LOG; if the date did not match exactly I looked for the first
# date where the clock drift reset and the associated LOG recorded an actual dive

# Boolean set to true in order to delete every processed data and redo everything
redo = False

# Figures commented by default (take heaps of memory)
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

        # Add .cmd, .out, and .vit files
        files_to_copy += glob.glob(os.path.join(server_path, mfloat + "*"))

        # Copy files
        for f in files_to_copy:
            shutil.copy(f, mfloat_path)

        # Really: collect all the .MER files (next we correlate their environments to .LOG files)
        print(" ...compiling a list of events from {:s} .MER files (GPS & seismic data)..." \
              .format(mfloat_serial))
        mevents = events.Events(mfloat_path)

        # Determine the time range of analysis (generally; birth to death of a MERMAID)
        if mfloat in filterDate.keys():
            begin = filterDate[mfloat][0]
            end = filterDate[mfloat][1]
        else:
            begin = datetime.datetime(1000, 1, 1)
            end = datetime.datetime(3000, 1, 1)

        # Really: collect all the .LOG files in order (1 .LOG == 1 Dive)
        print(" ...matching those events to {:s} .LOG ('dive') files (GPS & dive metadata)..." \
              .format(mfloat_serial))
        mdives = dives.get_dives(mfloat_path, mevents, begin, end)

        # Generate logs and plots for each dive
        for dive in mdives:
            # Create the directory
            if not os.path.exists(dive.export_path):
                os.mkdir(dive.export_path)
            # Generate log
            dive.generate_datetime_log()
            # Generate mermaid environment file
            dive.generate_mermaid_environment_file()
            # Generate dive plot
            dive.generate_dive_plotly() # <-- timestamps not corrected for clockdrift

        # Lengthen pre/post-dive GPS list by (pre)/(ap)pending the relevant GPS
        # recorded in the previous/next .LOG and .MER files
        mdives[0].set_incl_prev_next_dive_gps(None, mdives[1])

        # Use those pre/post-dive GPS lists to correct MERMAID timestamps and
        # interpolate for MERMAID location at the time of recording
        mdives[0].correct_events_clockdrift()
        mdives[0].compute_station_locations(mixed_layer_depth_m, preliminary_location_ok)

        # Repeat for all other dives after intialization at mdives[0] (loop
        # requires reference to previous dive)
        i = 1
        while i < len(mdives) - 1:
            mdives[i].set_incl_prev_next_dive_gps(mdives[i-1], mdives[i+1])
            mdives[i].correct_events_clockdrift()
            mdives[i].compute_station_locations(mixed_layer_depth_m, preliminary_location_ok)
            i += 1

        # Because the last dive was skipped above its GPS lists were not extended;
        # add filenames for printout
        mdives[-1].prev_dive_log_name = mdives[-2].log_name
        mdives[-1].prev_dive_mer_environment_name = mdives[-2].mer_environment_name

        # Generate plots, SAC, and miniSEED files for each event
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

        # Write csv and txt files containing all GPS fixes from .LOG and .MER
        gps.write_gps(mdives, processed_path, mfloat_path)

        # Write text file detailing event-station location interpolation parameters
        gps.write_gps_interpolation_txt(mdives, processed_path, mfloat_path)

        # Write helpful printout detailing every dive, and how .LOG and .MER
        # files connect
        dives.generate_printout(mdives, mfloat_serial)

        # Write text file detailing how .LOG and .MER files connect
        dives.write_dives_txt(mdives, processed_path, mfloat_path)

        # Write a text file relating all SAC and mSEED to their associated .LOG
        # and .MER files
        events.write_traces_txt(mdives, processed_path, mfloat_path)

        # Write a text file with our best-guess at the location of MERMAID at
        # the time of recording
        events.write_loc_txt(mdives, processed_path, mfloat_path)

        # Write mseed2sac and automaid metadata csv and text files
        events.write_metadata(mdives, processed_path, mfloat_path)

        # Write GeoCSV files
        geocsv_meta = geocsv.GeoCSV(mdives)
        geocsv_meta.write(os.path.join(processed_path, mfloat_path, 'geo.csv'))

        # Finally, try for rapid location estimates of the final dive, if requested.
        mdives[-1].compute_station_locations(mixed_layer_depth_m, preliminary_location_ok)
        if events_sac:
            mdives[-1].generate_events_sac()
        if events_mseed:
            mdives[-1].generate_events_mseed()

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

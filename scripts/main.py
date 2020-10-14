# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v2.7)
#
# Original author: Sebastien Bonnieux
# Current maintainer: Dr. Joel D. Simon (JDS)
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified by JDS: 14-Oct-2020, Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit

import setup
import os
import argparse
import shutil
import glob
import datetime
import dives
import events
import vitals
import kml
import re
import utils
import pickle
from pdb import set_trace as keyboard

# Set default paths
automaid_path = os.environ["AUTOMAID"]
def_mermaid_path = os.environ["MERMAID"]
def_server_path = os.path.join(def_mermaid_path, "server")
def_processed_path = os.path.join(def_mermaid_path, "processed")

# Parse (optional) command line inputs to override default paths
parser = argparse.ArgumentParser()
parser.add_argument('--server', default=def_server_path,
                    help="path to server directory (default: {:s})".format(def_server_path))
parser.add_argument('--processed', default=def_processed_path,
                    help="path to processed directory (default: {:s})".format(def_processed_path))
args = parser.parse_args()
server_path = os.path.abspath(args.server)
processed_path = os.path.abspath(args.processed)

# Get current version number.
version = setup.get_version()

# Set a time range of analysis for a specific float
filterDate = {
    "452.112-N-01": (datetime.datetime(2018, 12, 27), datetime.datetime(2100, 1, 1)),
    "452.112-N-02": (datetime.datetime(2018, 12, 28), datetime.datetime(2100, 1, 1)),
    "452.112-N-03": (datetime.datetime(2018, 4, 9), datetime.datetime(2100, 1, 1)),
    "452.112-N-04": (datetime.datetime(2019, 1, 3), datetime.datetime(2100, 1, 1)),
    "452.112-N-05": (datetime.datetime(2019, 1, 3), datetime.datetime(2100, 1, 1)),
    "452.020-P-06": (datetime.datetime(2018, 6, 26), datetime.datetime(2100, 1, 1)),
    "452.020-P-07": (datetime.datetime(2018, 6, 27), datetime.datetime(2100, 1, 1)),
    "452.020-P-08": (datetime.datetime(2018, 8, 5), datetime.datetime(2100, 1, 1)),
    "452.020-P-09": (datetime.datetime(2018, 8, 6), datetime.datetime(2100, 1, 1)),
    "452.020-P-10": (datetime.datetime(2018, 8, 7), datetime.datetime(2100, 1, 1)),
    "452.020-P-11": (datetime.datetime(2018, 8, 9), datetime.datetime(2100, 1, 1)),
    "452.020-P-12": (datetime.datetime(2018, 8, 10), datetime.datetime(2100, 1, 1)),
    "452.020-P-13": (datetime.datetime(2018, 8, 31), datetime.datetime(2100, 1, 1)),
    "452.020-P-16": (datetime.datetime(2018, 9, 3), datetime.datetime(2100, 1, 1)),
    "452.020-P-17": (datetime.datetime(2018, 9, 4), datetime.datetime(2100, 1, 1)),
    "452.020-P-18": (datetime.datetime(2018, 9, 5), datetime.datetime(2100, 1, 1)),
    "452.020-P-19": (datetime.datetime(2018, 9, 6), datetime.datetime(2100, 1, 1)),
    "452.020-P-20": (datetime.datetime(2018, 9, 8), datetime.datetime(2100, 1, 1)),
    "452.020-P-21": (datetime.datetime(2018, 9, 9), datetime.datetime(2100, 1, 1)),
    "452.020-P-22": (datetime.datetime(2018, 9, 10), datetime.datetime(2100, 1, 1)),
    "452.020-P-23": (datetime.datetime(2018, 9, 12), datetime.datetime(2100, 1, 1)),
    "452.020-P-24": (datetime.datetime(2018, 9, 13), datetime.datetime(2100, 1, 1)),
    "452.020-P-25": (datetime.datetime(2018, 9, 14), datetime.datetime(2100, 1, 1)),
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
datasave = dict()

def main():
    # Set working directory in "scripts"
    os.chdir(os.path.join(automaid_path, "scripts", ""))

    # Create processed directory if it doesn't exist
    if not os.path.exists(processed_path):
        os.mkdir(processed_path)

    # Search Mermaid floats
    vitfile_path = os.path.join(server_path, "*.vit")
    mfloats = [p.split("/")[-1][:-4] for p in glob.glob(vitfile_path)]

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

        # Remove existing files in the processed directory (if the script have been interrupted the time before)
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

        # Compute clock drift correction for each event, and build list of GPS locations.
        for dive in mdives:
            dive.correct_events_clock_drift()

        # Compute location of mermaid float for each event (because the station is moving)
        # the algorithm use gps information in the next dive to estimate surface drift
        i = 0
        while i < len(mdives)-1:
            mdives[i].compute_events_station_location(mdives[i+1])
            i += 1

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


        # Collect, sort, and write to all GPS points recorded in both the .LOG
        # and .MER files (flatten function posted by Alex Martelli on stack
        # overflow, "How to make a flat list out of list of lists?")
        flatten = lambda l: [item for sublist in l for item in sublist]
        gps_list_from_log = flatten([dive.gps_from_log for dive in mdives])
        gps_list_from_mmd_env = flatten([dive.gps_from_mmd_env for dive in mdives])

        # Concatenate lists from both sources (resulting in unsorted list)
        gps_list_full = gps_list_from_log +  gps_list_from_mmd_env

        # Sort the full GPS list using their date attributes
        gps_list_full.sort(key=lambda x: x.date)

        # Write GPS text file
        fmt_spec = "{:>27s}    {:>10.6f}    {:>11.6f}    {:>6.3f}    {:>6.3f}    {:>17.6f}    {:>15s}\n"
        gps_f = os.path.join(processed_path, mfloat_path, mfloat+"_GPS.txt")
        with open(gps_f, "w+") as f:
            for g in gps_list_full:
                # Replace missing hdop/vdop (not printed in .MER files) values
                # with NaNs for printing purposes (those attributes will remain
                # None in their associated GPS instances; this is just for the
                # purposes of this final flat list)
                if g.hdop is None:
                    g.hdop = float("NaN")
                if g.vdop is None:
                    g.vdop = float("NaN")

                f.write(fmt_spec.format(g.date, g.latitude, g.longitude, g.hdop, g.vdop, g.clockdrift, g.source))

        # Generate printout detailing how everything connects
        print ""
        i = 0
        for d in mdives:
            # For every dive...
            if d.is_dive:
                print("  .DIVE. {:s}".format(mfloat_serial))
            else:
                print("  .NO DIVE. {:s}".format(mfloat_serial))
            d.print_dive_length()
            d.print_dive_gps(mdives[i+1])
            d.print_dive_events()
            print ""

        print("    {:s} total: {:d} SAC files\n" \
              .format(mfloat_serial, sum(dive.sac_count for dive in mdives)))

        # Clean directories
        for f in glob.glob(mfloat_path + "/" + mfloat_nb + "_*.LOG"):
            os.remove(f)
        for f in glob.glob(mfloat_path + "/" + mfloat_nb + "_*.MER"):
            os.remove(f)

        # Put dive in a variable that will be saved in a file
        datasave[mfloat] = mdives

    with open(os.path.join(processed_path, "MerDives.pydata"), 'wb') as f:
        pickle.dump(datasave, f)

        # for dive in mdives[:-1]: # on ne regarde pas la derniere plongee qui n'a pas ete interpolee
        #    if dive.is_complete_dive: # on ne regarde que les vraies plongees (pas les tests faits a terre)
        #        print dive.log_name
        #        for gps in dive.gps_list[0:-1]: # point GPS avant de descendre
        #            print gps.date
        #        print dive.surface_leave_loc.date
        #        print dive.great_depth_reach_loc.date
        #        print dive.great_depth_leave_loc.date
        #        print dive.gps_list[-1].date # point GPS en arrivant en surface

if __name__ == "__main__":
    main()

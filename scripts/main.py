# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v2.7)
#
# Usage: python main.py [-p processed] [-s server]
#
# Developer: Joel D. Simon (JDS)
# Original author: Sebastien Bonnieux
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified by JDS: 17-May-2021
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

from pprint import pprint

# Get current version number.
version = setup.get_version()

# Set depth of mixed layer (in meters) for drift interpolation
mixed_layer_depth_m = 50

# Mininum number unique GPS fixes before/after each dive required for
# interpolation
min_gps_fix = 2

# Maximum-allowed time in seconds before(after) diving(surfacing) to record the
# minimum-required number of unique GPS fixes
max_gps_time = 3600

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
events_png = False
events_plotly = False
events_sac = True
events_mseed = True

# Dictionary  save data in a file
dives_dict = dict()

def main():
    # Set working directory in "scripts"
    os.chdir(os.path.join(automaid_path, "scripts", ""))

    # Create processed directory if it doesn't exist
    if not os.path.exists(processed_path):
        os.mkdir(processed_path)

    # Search MERMAID floats
    vitfile_path = os.path.join(server_path, "*.vit")
    mfloats = [p.split("/")[-1][:-4] for p in glob.glob(vitfile_path)]

    # Initialize empty dict to hold the instance of every last complete dive for
    # every MERMAID
    lastdive = dict()

    # For each MERMAID float
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

        # Collect all the .LOG files in order (generally 1 .LOG == 1 Dive)
        # Later we will combine multiple .LOG files in cases when they are fragmented
        # .LOG files can fragment due to ERR, EMERGENCY, REBOOT etc.
        # A fragmented .LOG is one that does not include a complete dive
        # A single-.LOG complete dive starts with '[DIVING]' and ends with '[SURFIN]'
        # A multiple-.LOG complete dive is a concatenation of fragmented dives
        # (i.e., a multi-.LOG complete dive may not actually contain a dive at all)
        # Therefore, concatenate all fragmented .LOG in-between single-LOG complete dives
        print(" ...matching those events to {:s} .LOG ('dive') files (GPS & dive metadata)..." \
              .format(mfloat_serial))
        dive_logs = dives.get_dives(mfloat_path, mevents, begin, end)

        fragmented_dive = list()
        complete_dives = list()
        for i, dive_log in enumerate(dive_logs):

            # Create the directory
            if not os.path.exists(dive_log.export_path):
                os.mkdir(dive_log.export_path)

            # Reformat and write .LOG in individual dive directory
            dive_log.generate_datetime_log()

            # Write .MER environement in individual directories
            dive_log.generate_mermaid_environment_file()

            # Generate dive plot
            dive_log.generate_dive_plotly() # <-- timestamps not corrected for clockdrift

            # The GPS list is None outside of requested begin/end dates, within
            # which it defaults to an empty list if it is truly empty
            if dive_log.gps_list is None:
                continue

            # Often a single .LOG defines a complete dive: '[DIVING]' --> '[SURFIN]'
            # Use those "known" complete dives to compile list of in-between fragmented dives
            if dive_log.is_complete_dive:
                complete_dives.append(dives.Complete_Dive([dive_log]))

            else:
                fragmented_dive.append(dive_log)

                # If the next .LOG is a complete dive then this log is the last
                # fragmented/filler .LOG file in-between complete dives
                # Define the concatenation of all fragmented dives to be one complete dive
                # Note that this type of complete dive may not define a dive at all
                # However, we want to group these data so their (possibly legit)
                # GPS may be used to interpolate previous/succeeding dives
                if i < len(dive_logs)-1 and dive_logs[i+1].is_complete_dive:
                    complete_dives.append(dives.Complete_Dive(fragmented_dive))
                    fragmented_dive = list()

        # Plot vital data
        kml.generate(mfloat_path, mfloat, complete_dives)
        vitals.plot_battery_voltage(mfloat_path, mfloat + ".vit", begin, end)
        vitals.plot_internal_pressure(mfloat_path, mfloat + ".vit", begin, end)
        vitals.plot_pressure_offset(mfloat_path, mfloat + ".vit", begin, end)
        if len(dive_logs) > 1:
            vitals.plot_corrected_pressure_offset(mfloat_path, complete_dives, begin, end)

        # Use completed (stitched together) dives to generate event metadata
        for i, complete_dive in enumerate(complete_dives):

            # Extend dive's GPS list by searching previous/next dive's GPS list
            prev_dive = complete_dives[i-1] if i > 0 else None
            next_dive = complete_dives[i+1] if i < len(complete_dives)-1 else None
            complete_dive.set_incl_prev_next_dive_gps(prev_dive, next_dive)

            # Validate that the GPS may be used to correct various MERMAID
            # timestamps, including diving/surfacing and event starttimes
            complete_dive.validate_gps(min_gps_fix, max_gps_time)

            # Apply those clock corrections
            complete_dive.correct_clockdrift()

            # Interpolate station locations at various points in the dive
            complete_dive.compute_station_locations(mixed_layer_depth_m, preliminary_location_ok)

            # Format station-location metadata for ObsPy and attach to complete dive object
            complete_dive.attach_events_metadata()

            # Write requested output files
            if not os.path.exists(complete_dive.export_path):
                os.mkdir(complete_dive.export_path)

            if events_png:
                complete_dive.generate_events_png()

            if events_plotly:
                complete_dive.generate_events_plotly()

            if events_sac:
                complete_dive.generate_events_sac()

            if events_mseed:
                complete_dive.generate_events_mseed()

        # Write text file detailing event-station location interpolation parameters
        gps.write_gps_interpolation_txt(complete_dives, processed_path, mfloat_path)

        # Write text file detailing which SINGLE .LOG and .MER files define
        # (possibly incomplete) dives
        dives.write_dives_txt(dive_logs, processed_path, mfloat_path)

        # Write text file and printout detailing which (and potentially
        # MULTIPLE) .LOG and .MER files define complete dives
        dives.write_complete_dives_txt(complete_dives, processed_path, mfloat_path, mfloat_serial)


        # # Write a text file relating all SAC and mSEED to their associated .LOG
        # # and .MER files
        # events.write_traces_txt(dive_logs, processed_path, mfloat_path)

        # # Write a text file with our best-guess at the location of MERMAID at
        # # the time of recording
        # events.write_loc_txt(dive_logs, processed_path, mfloat_path)

        # Write mseed2sac and automaid metadata csv and text files
        events.write_metadata(complete_dives, processed_path, mfloat_path)

        # Write GeoCSV files
        geocsv_meta = geocsv.GeoCSV(complete_dives)
        geocsv_meta.write(os.path.join(processed_path, mfloat_path, 'geo.csv'))

        # # Finally, try for rapid location estimates of the final dive, if requested.
        # dive_logs[-1].compute_station_locations(mixed_layer_depth_m, preliminary_location_ok)
        # if events_sac:
        #     dive_logs[-1].generate_events_sac()
        # if events_mseed:
        #     dive_logs[-1].generate_events_mseed()

        # Clean directories
        for f in glob.glob(mfloat_path + "/" + mfloat_nb + "_*.LOG"):
            os.remove(f)
        for f in glob.glob(mfloat_path + "/" + mfloat_nb + "_*.MER"):
            os.remove(f)

        # Add dives to growing dict
        dives_dict[mfloat] = dive_logs

    # Done looping through all dives for each float
    #______________________________________________________________________________________#

    # Print a text file of corrected external pressures measured on the final
    # dive, and warn if any are approaching the limit of 300 mbar (at which
    # point adjustment is required)
    vitals.write_corrected_pressure_offset(dives_dict, processed_path)

if __name__ == "__main__":
    main()

# automaid -- a Python package to process MERMAID files
#
# pymaid environment (Python v2.7)
#
# Original author: Sebastien Bonnieux
#
# Current maintainer: Dr. Joel D. Simon (JDS)
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified by JDS: 30-Sep-2020, Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit

import setup
import os
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
redo = True

# Plot interactive figures in HTML format for acoustic events
# WARNING: Plotly files takes a lot of memory so commented by default
events_plotly = False
events_mseed = True
events_sac = True
events_png = False

# Set paths.
automaid_path = os.environ["AUTOMAID"]
mermaid_path = os.environ["MERMAID"]
server_path = os.path.join(mermaid_path, "server")
processed_path = os.path.join(mermaid_path, "processed")

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

        # Attach a completeness metric concerning the data in the .MER file to
        # each event -- this is only possible after collecting all dives
        # (mdives) and all events separately (mevents).
        dives.attach_mmd_is_complete_to_dive_events(mdives)

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

        # Generate plots, SAC, and miniSEED files.
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

        # Build unsorted list of all GPS fixes from .LOG and .MER.
        print(" ...writing list of {:s} GPS locations...".format(mfloat_serial))
        gps_dates = list()
        gps_latitudes = list()
        gps_longitudes = list()
        gps_hdops = list()
        gps_vdops = list()
        gps_clockdrifts = list()
        gps_sources = list()

        for dive in mdives:
            # Collect all GPS data from LOG file.
            for gps_fix in dive.gps_from_log:
                gps_dates.append(gps_fix.date)
                gps_latitudes.append(gps_fix.latitude)
                gps_longitudes.append(gps_fix.longitude)
                gps_hdops.append(gps_fix.hdop)
                gps_vdops.append(gps_fix.vdop)
                gps_clockdrifts.append(gps_fix.clockdrift)
                gps_sources.append(dive.log_name)

            # Collect all GPS data from MER file.
            for gps_fix in dive.gps_from_mmd_env:
                gps_dates.append(gps_fix.date)
                gps_latitudes.append(gps_fix.latitude)
                gps_longitudes.append(gps_fix.longitude)
                gps_hdops.append(gps_fix.hdop)
                gps_vdops.append(gps_fix.vdop)
                gps_clockdrifts.append(gps_fix.clockdrift)
                gps_sources.append(dive.mmd_environment_name)

        # Concatenate all GPS data into zipped tuple and sort based on zeroth (date) index.
        complete_gps_tup = sorted(zip(gps_dates, gps_latitudes, gps_longitudes, gps_hdops,
                                       gps_vdops, gps_clockdrifts, gps_sources))

        # Write textfile.
        fmt_spec = "{:>27s}    {:>10.6f}    {:>11.6f}    {:>5.3f}    {:>5.3f}    {:>17.6f}    {:>15s}\n"
        gps_f = os.path.join(processed_path, mfloat_path, mfloat+"_GPS.txt")
        with open(gps_f, "w+") as f:
            for t in complete_gps_tup:
                l = list(t)
                if l[3] is None:
                    l[3] = float("NaN")

                if l[4] is None:
                    l[4] = float("NaN")

                f.write(fmt_spec.format(l[0], l[1], l[2], l[3], l[4], l[5], l[6]))

        # Clean directories
        for f in glob.glob(mfloat_path + "/" + mfloat_nb + "_*.LOG"):
            os.remove(f)
        for f in glob.glob(mfloat_path + "/" + mfloat_nb + "_*.MER"):
            os.remove(f)

        # Put dive in a variable that will be saved in a file
        datasave[mfloat] = mdives

        # Generate printout detailing how everything connects
        sac_count = 0
        print ""
        for d in mdives:
            # For every dive...
            if d.is_dive:
                #print("Dive ID: {:d}".format(d.dive_id))
                print("  .DIVE. {:s}".format(mfloat_serial))
                dive_len = (d.end_date-d.date) / (60*60*24)
                print("  Dates: {:s} -> {:s} ({:.1f} days; first/last line of {:s})" \
                      .format(str(d.date)[0:19], str(d.end_date)[0:19], dive_len, d.log_name))

                print("    GPS: {:s} (<ENVIRONMENT/>) & {:s}" \
                      .format(d.mmd_environment_name, d.log_name))

                # For every event written to a .MER file (but not necessarily recorded) during that dive...
                if d.events is None:
                    print("    ---> no detected or requested events")
                else:
                    for e in d.events:
                        if e.station_loc is None:
                            print("    ---> ! NOT MADE (not enough GPS fixes) {:s}.sac (<EVENT/> binary in {:s})" \
                                  .format(e.get_export_file_name(), e.mmd_data_name))
                        else:
                            if not e.mmd_file_is_complete:
                                print("    ---> ! NOT MADE (incomplete .MER file) {:s}.sac (<EVENT/> binary in {:s})" \
                                      .format(e.get_export_file_name(), e.mmd_data_name))
                            else:
                                sac_count += 1
                                print("    ---> {:s}.sac (<EVENT/> binary in {:s})" \
                                      .format(e.get_export_file_name(), e.mmd_data_name))

                print ""
        print(" Generated {:d} {:s} SAC files\n".format(sac_count, mfloat_serial))
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

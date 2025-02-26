# -*- coding: utf-8 -*-
#
# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v3.10)
#
# Developer: Frédéric rocca <FRO>
# Contact:  frederic.rocca@osean.fr
# Last modified by FRO: 09-Sep-2024
# Last tested: Python 3.10.13, 22.04.3-Ubuntu


import os
import re
import csv
import sys
import glob
import collections

from obspy import UTCDateTime
import plotly.offline as plotly
import plotly.graph_objs as graph

import gps
import utils
import setup

# Get current version number.
version = setup.get_version()

class Log:
    log_name = None
    log_content = None
    start_date = None
    end_date = None
    len_secs = None
    len_days = None
    gps_list_from_log = []
    gps_list_from_mermaid = []
    gps_list = []
    mer_environment = None
    mer_environment_name = None
    mer_environment_name_exists = False

    s41_file_name = None
    s41_file_name_exists = False
    s61_file_name = None
    s61_file_name_exists = False

    p2t_offset_param = None
    p2t_offset_measurement = None
    p2t_offset_corrected = None
    dive_id = None
    kstnm = None
    kinst = None
    is_partial = False

    def __init__(self,base_path,events,log_name,log_content,kstnm,kinst):
        self.base_path = base_path
        self.log_name = log_name
        self.log_content = log_content
        self.kstnm = kstnm
        self.kinst = kinst
        print("{} (Log)".format(self.log_name))
        # Get the date from the file name -- the hexadecimal component of the
        # .LOG file name is the same Unix Epoch time as the first line of the
        # LOG file (there in int seconds); i.e., .LOG files are named for the
        # time that their first line is written
        self.start_date = utils.get_date_from_file_name(log_name)
        # Get the last date (last line of the log file)
        last_epoch_time = utils.split_log_lines(self.log_content)[-1].split(':')[0]
        self.end_date = UTCDateTime(int(last_epoch_time))
        self.len_secs = int(self.end_date - self.start_date)
        self.len_days = self.len_secs / (60*60*24.)
        # get gps list from log file
        self.gps_list_from_log = gps.get_gps_from_log_content(self.log_name, log_content)
        # Find external pressure offset
        # Commanded as "p2t qm!offset ??? "in .cmd file
        # Reported as "...p2t37: ??x????s, offset ???mbar" in .LOG file
        offset_param = re.findall("offset (-?\d+)mbar", self.log_content)
        if offset_param:
            self.p2t_offset_param = int(offset_param[0])
        # Reported as "Pext ???mbar" in .LOG file, this does not include any
        # offset correction (self.p2t_offset_param)
        offset_measurement = re.findall("Pext (-?\d+)mbar", self.log_content)
        if offset_measurement:
            self.p2t_offset_measurement = int(offset_measurement[0])
        # Compute the corrected pressure offset
        if offset_param and offset_measurement:
            self.p2t_offset_corrected =  self.p2t_offset_measurement - self.p2t_offset_param
        # Find the .MER file whose environment (and maybe binary, but not
        # necessarily) is associated with this .LOG file
        #
        # To date I've seen these examples in .LOG files:
        # "XXXXX bytes in YYYY/ZZZZZZZZ.MER"
        # "<WRN>maybe YYYY/ZZZZZZZZ.MER is not complete"
        # "<ERR>upload "YY","YY/ZZZZZZZZ.MER"
        #
        # NB, "\w" is this is equivalent to the set "[a-zA-Z0-9_]"
        catch = re.findall("bytes in (\w+/\w+\.MER)", self.log_content)
        if not catch:
            # Ideally the .LOG notes the bytes expected in the .MER, though it
            # may instead say one of the three (or more?) possibilities
            # enumerated above.  The "<WRN>..." message seems workable because
            # (so far as I've seen) those data in the associated .MER file are
            # not redundantly printed in another .MER file.  However, we
            # definitely want to skip .MER files called out in the .LOG by
            # "<ERR>..."  because those data may be redundantly repeated in
            # another .MER file when the MERMAID attempts to re-transmit those
            # data, e.g., in the case of:
            #
            # 2018-09-15T20:11:48Z: 25_5B9D6784.LOG -> "21712 bytes in 25/5BA88AE8.MER"
            # 2018-09-24T06:58:50Z: 25_5BA88B2A.LOG -> "<ERR>upload "25","25/5BA88AE8.MER"
            catch = re.findall("<WRN>maybe (\w+/\w+\.MER) is not complete", self.log_content)

        if len(catch) > 0:
            self.mer_environment_name = catch[-1].replace("/", "_")
            print("{} (environment)".format(self.mer_environment_name))

            # Sometimes the MER .file named in the .LOG does not exist on the
            # server (e.g., '16_5F9C20FC.MER')
            mer_fullfile_name = self.base_path + self.mer_environment_name
            if os.path.exists(mer_fullfile_name):
                self.mer_environment_name_exists = True
                # If the dive wrote a .MER file then retrieve its corresponding
                # environment because those GPS fixes DO relate to start/end of the
                # dive. HOWEVER, the events (data) actually contained in that .MER
                # file may correspond to a different dive (GPS fixes from
                # DIFFERENT .LOG and .MER environment), thus we must
                # "get_events_between" to correlate the actual binary data in .MER
                # files with their proper GPS fixes (usually the dates of the binary
                # events in the .MER file correspond to the .MER file itself,
                # however if there are a lot of events to send back corresponding to
                # a single dive, it may take multiple surfacings to finally transmit
                # them all).

                # Read the Mermaid environment associated to the dive
                with open(mer_fullfile_name, "rb") as f:
                    content = f.read().decode("utf-8","replace")
                    catch = re.findall("<ENVIRONMENT>.+</PARAMETERS>", content, re.DOTALL)
                    # Sometimes the .MER file exists but it is empty (0037_605CB34D.MER)
                    if catch:
                        self.mer_environment = catch[0]
                        # Get dive ID according to .MER (this iterator can be reset)
                        # NB, a dive ID does not necessarily mean MERMAID actually dove
                        # It just means the float transmitted a .MER file(?)
                        # See, e.g., dive #97 float 25 (25_5EFEC58E.LOG, 25_5EFF43E0.MER)
                        # That log shows a REBOOT, TESTMD, and an old .MER transmission
                        dive_id = re.search("<DIVE ID=(\d+)", self.mer_environment)
                        self.dive_id = int(dive_id.group(1))

        # Get list of gps even with partial file
        self.gps_list_from_mermaid = events.get_gps_between(self.start_date, self.end_date);
        # Get list of events associated with this .MER file's environment
        # (the metadata header, which does not necessarily relate to the
        # events and their binary data below that header in the same .MER)
        self.events = events.get_events_between(self.start_date, self.end_date)
        # Set and parse info from .MER file and invert wavelet transform any binary data
        # (cannot invert the data without vital information from the .MER environment)
        if not self.mer_environment and len(self.events) > 0:
            # Mer file is not logged on LOG file but events are found during this dive
            # E.g : 12_65B5EC90.LOG / 12_65BF9636.MER
            self.mer_environment = self.events[0].default_mer_environment

        for event in self.events:
            event.set_kstnm_kinst(self.kstnm, self.kinst)
            event.set_environment(self.mer_environment_name, self.mer_environment)
            event.find_measured_sampling_frequency()
            event.set_uncorrected_starttime()
            event.set_processed_data()
        # Re-sort events based on starttime (rather than INFO DATE)
        self.events.sort(key=lambda x: x.uncorrected_starttime)
        # Merge gps list into an unique
        self.gps_list = gps.merge_gps_list(self.gps_list_from_log,self.gps_list_from_mermaid)
        # Check if CTD samples stored on S41 file
        sbe41_catch = re.findall("samples in (\w+/\w+\.S41)", self.log_content)
        if len(sbe41_catch) > 0:
            self.s41_file_name = sbe41_catch[-1].replace("/", "_")
            # Sometimes the S41 .file named in the .LOG does not exist on the server
            s41_fullfile_name = self.base_path + self.s41_file_name
            if os.path.exists(s41_fullfile_name):
                self.s41_file_name_exists = True
        # Check if CTD samples stored on S61 file
        sbe61_catch = re.findall("samples in (\w+/\w+\.S61)", self.log_content)
        if len(sbe61_catch) > 0:
            self.s61_file_name = sbe61_catch[-1].replace("/", "_")
            # Sometimes the S41 .file named in the .LOG does not exist on the server
            s61_fullfile_name = self.base_path + self.s61_file_name
            if os.path.exists(s61_fullfile_name):
                self.s61_file_name_exists = True
# Class to manipulate cycle files
class Cycle:
    '''
        The Cycle class references a single .CYCLE file.

        Cycle files are produced by automaid by merging several LOG files.
        Each cycle file corresponds to a dive followed by a complete cycle until data transfer.

        - Cycle 0 corresponds to initialization and contains no dives.

        - The last cycle is incomplete as the surface report will be transferred to the next dive.
    '''
    __version__ = None
    base_path = None
    processed_path = None
    directory_name = None
    station_name = None
    station_number = None
    soft_version = None
    kstnm = None
    kinst = None
    cycle_name = None
    cycle_content = None
    cycle_nb = None

    start_date = None
    end_date = None
    len_secs = None
    len_days = None

    start_cycle = None
    end_cycle = None

    logs = None
    complete_logs = None

    events = None
    profilesS41 = None
    profilesS61 = None

    # All gps (SYNC MERMAID + LOG)
    gps_before_dive = None
    gps_after_dive = None
    gps_list = None
    # Only synchronization mermaid position (.MER file)
    gps_sync_before_dive = None
    gps_sync_after_dive = None
    gps_sync_list = None

    # Dates
    descent_leave_surface_date = None
    ascent_start_date = None
    ascent_reach_surface_date = None

    is_init = False
    is_dive = False
    is_complete_cycle = False

    mermaid_reboots = None
    emergency_triggers = None
    pressure_mbar = None
    vitals_vbat = None
    vitals_pext = None
    vitals_pint = None


    gps_valid4clockdrift_correction = None
    gps_valid4location_interp = None

    descent_leave_surface_loc = None
    descent_leave_surface_layer_date = None
    descent_leave_surface_layer_loc = None
    descent_last_loc_before_event = None

    ascent_reach_surface_loc = None
    ascent_reach_surface_layer_date = None
    ascent_reach_surface_layer_loc = None
    ascent_first_loc_after_event = None

    p2t_offset_corrected = None
    last_p2t_offset_measurement = None
    last_p2t_offset_corrected = None
    last_p2t_offset_param = None
    last_p2t_log_name = None

    # Class attribute to hold MERMAID "MH" FDSN network code
    network = utils.network()

    def __init__(self, base_path=None, cycle_name=None, events=None, profilesS41=None ,profilesS61=None):
        self.base_path = base_path
        self.__version__ = version
        self.cycle_name = cycle_name
        print("{}".format(self.cycle_name))

        # Get the date and cycle number from the file name -- the hexadecimal component of the
        # .CYCLE file name is the same Unix Epoch time as the first line of the
        # file (there in int seconds); i.e., .CYCLE files are named for the
        # time that their first line is written
        filename_split = re.findall("(\d+)_([A-Z0-9]+)\.CYCLE", cycle_name)[0]
        self.cycle_nb = int(filename_split[0], 10)
        self.start_date = UTCDateTime(int(filename_split[1], 16))

        # Read the content of the CYCLE file
        with open(self.base_path + self.cycle_name, "rb") as f:
            self.cycle_content = f.read().decode("utf-8","replace")
            # Empty .LOG file, e.g. 0003_5FDCB1EE.LOG in testing
            # (maybe it was later transmitted?)
            if not self.cycle_content:
                return
        # Get the last date (last line of the cycle file)
        last_epoch_time = utils.split_log_lines(self.cycle_content)[-1].split(':')[0]
        self.end_date = UTCDateTime(int(last_epoch_time))
        # Get cycle duration
        self.len_secs = int(self.end_date - self.start_date)
        self.len_days = self.len_secs / (60*60*24.)
        # Get the station name
        find_name = None
        find_soft = None
        lines = utils.split_log_lines(self.cycle_content)
        for line in lines :
            match_board = re.findall("board (.+)", line)
            match_buoy = re.findall("buoy (.+)", line)
            match_soft_v1 = re.findall("soft (.+)", line)
            match_soft_v2 = re.findall("soft pilotage (.+)", line)
            if match_board :
                find_name = match_board[0]
            if match_buoy :
                find_name = match_buoy[0]
            if match_soft_v1 :
                find_soft = match_soft_v1[0]
            if match_soft_v2 :
                find_soft = match_soft_v2[0]
            if find_name and find_soft:
                self.station_name = find_name
                self.station_number = self.station_name.split("-")[-1]
                self.soft_version = find_soft
                # Zero-pad the (unique part) of the station name so that it is five characters long
                self.set_kstnm_kinst()
                break;

        # Retreive log source informations into a cycle
        self.logs = []
        logs_content = self.cycle_content.split("[PREPROCESS]")[1:]
        for log_content in logs_content:
            log_name = re.findall("Create (\d+_[A-Z0-9]+\.LOG)", log_content)
            if log_name :
                lobject = Log(base_path,events,log_name[0],log_content,self.kstnm,self.kinst)
                self.logs.append(lobject)
            end_of_cycle = re.findall("End of cycle", log_content)
            if end_of_cycle :
                # Last part of cycle content is an incomplete log file content
                self.logs[-1].is_partial = True

        # Make a list of complete log file
        self.complete_logs = [log for log in self.logs if not log.is_partial]
        # List all events into a cycle
        self.events = [event for log in self.logs for event in log.events]
        # List all offset correction
        self.p2t_offset_corrected = [log.p2t_offset_corrected for log in self.logs]
        # Retain most recent external pressure measurement
        for log in reversed(self.logs):
            if log.p2t_offset_corrected is not None:
                self.last_p2t_offset_measurement = log.p2t_offset_measurement
                self.last_p2t_offset_corrected = log.p2t_offset_corrected
                self.last_p2t_offset_param = log.p2t_offset_param
                self.last_p2t_log_name = log.log_name
                break

        # Compile all water presure (100 mbar = 1 dbar = 1 m)
        # Run some verifications like we do for GPS to check for redudancies?
        # I do not know if pressure values are repeated over fragmented LOGs...
        # DO NOT DO: `('\[PRESS ,\s*\d+\]P\s*(\+?\-?\d+)mbar', self.cycle_content)`
        # because "P.*mbar" is a valid pressure, even if prefixed with "[SURFIN, ..."
        # Add \] before P to delete log when battery measurement are done (for new buoys)
        self.pressure_mbar = utils.find_timestamped_values("\]P\s*(\+?\-?\d+)mbar", self.cycle_content)

        # Check if the .CYCLE corresponds to float initialization
        if self.cycle_nb == 0 :
            self.is_init = True
            self.start_cycle = self.start_date
        else :
            # Find Leave surface date
            diving = utils.find_timestamped_values("\[DIVING, *\d+\] *(\d+)mbar reached", self.cycle_content)
            if diving:
                # Cycle start when buoy leave surface
                self.is_dive = True
                self.descent_leave_surface_date = diving[0][1]
                self.start_cycle = self.descent_leave_surface_date
        # Check if the .CYCLE is completed
        complete = utils.find_timestamped_values(":\[PREPROCESS\]End of cycle", self.cycle_content)
        if complete :
            self.is_complete_cycle = True
            self.end_cycle = complete[0][1]

        # Find start of surfacing date
        # Start of surfacing can be triggered by start of last stage (CTD profile)
        surfacing_stage = utils.find_timestamped_values("\]Stage \[(\d+)\] surfacing", self.cycle_content)
        if surfacing_stage:
            # Surfacing stage
            stage_nb = surfacing_stage[0][0]
            regex_stage_begin = "\[MAIN  *, *\d+\]stage\[" + stage_nb + "\]"
            stage_begin = utils.find_timestamped_values(regex_stage_begin, self.cycle_content)
            if stage_begin :
                self.ascent_start_date = stage_begin[0][1]
        # By default surfacing is triggered when all stage are finished
        if self.descent_leave_surface_date and not self.ascent_start_date :
            surfacing = utils.find_timestamped_values("\[MAIN *, *\d+\]surfacing", self.cycle_content)
            if surfacing :
                # Get first surfacing after leave surface
                for surfin in surfacing :
                    if surfin[1] > self.descent_leave_surface_date :
                        self.ascent_start_date = surfin[1]
                        break

        # Find Reach surface date
        # It's possible that MERMAID physically dive and returned to the surface but there was
        # an error with the .LOG, so that information was not recorded (ex. 25_5B9CF6CF.LOG)
        # Log files may record several bladder fillings during a mission
        fillb_list = utils.find_timestamped_values("\[SURFIN, *\d+\]filling external bladder", self.cycle_content)
        for fillb in fillb_list :
            if fillb[1] > self.ascent_start_date :
                # find first fill after surfacing start
                self.ascent_reach_surface_date = fillb[1]
                break

        # Find if emergency triggered
        self.emergency_triggers = utils.find_timestamped_values("\]<ERR>TRIGGERED BY (.*)",self.cycle_content)
        # Find if mermaid reboot occurs
        self.mermaid_reboots = utils.find_timestamped_values("\]\$BOARD",self.cycle_content)
        # Find vitals for cycle
        self.vitals_vbat = utils.find_timestamped_values("Vbat (\d+)mV \(min (\d+)mV\)",self.cycle_content)
        self.vitals_pext = utils.find_timestamped_values("Pext (-?\d+)mbar \(rng (-?\d+)mbar\)",self.cycle_content)
        self.vitals_pint = utils.find_timestamped_values("internal pressure (\d+)Pa",self.cycle_content)
        # Generate the directory name (CycleNB_Date)
        self.directory_name = filename_split[0] + "_" + self.start_date.strftime("%Y%m%d-%Hh%Mm%Ss")
        if self.is_init:
            self.directory_name += "Init"
        elif not self.is_complete_cycle:
            self.directory_name += "IcCycle"

        self.processed_path = self.base_path + self.directory_name + "/"
        # Find the S41 profiles if any
        self.profilesS41 = profilesS41.get_profiles_between(self.start_date, self.end_date)
        # Find the S61 profiles if any
        self.profilesS61 = profilesS61.get_profiles_between(self.start_date, self.end_date)
        # Constitute lists of gps
        self.gps_before_dive = []
        self.gps_after_dive = []
        self.gps_list = []
        self.gps_sync_before_dive = []
        self.gps_sync_after_dive = []
        self.gps_sync_list = []

        for log in self.logs :
            for gps in log.gps_list :
                # All gps before leave surface (last cycle positions)
                if self.descent_leave_surface_date and gps.date < self.descent_leave_surface_date :
                    self.gps_before_dive.append(gps)
                    if gps.clockdrift is not None and gps.clockfreq is not None:
                        self.gps_sync_before_dive.append(gps)
                # All gps after leave surface (cycle positions when dive)
                if self.ascent_reach_surface_date and gps.date > self.ascent_reach_surface_date :
                    self.gps_after_dive.append(gps)
                    if gps.clockdrift is not None and gps.clockfreq is not None:
                        self.gps_sync_after_dive.append(gps)
                # All gps of this cycle (unique for a cycle)
                if gps.date > self.start_cycle :
                    self.gps_list.append(gps)
                    if gps.clockdrift is not None and gps.clockfreq is not None:
                        self.gps_sync_list.append(gps)
    def __len__(self):
        return 1

    def write_datetime_cycle(self):
        # Check if file exist
        processed_path = self.processed_path + self.cycle_name + ".h"
        if os.path.exists(processed_path):
            return
        # Generate log with formatted date
        formatted_log = utils.format_log(self.cycle_content)
        # Write file
        with open(processed_path, "w") as f:
            f.write(formatted_log)

    def write_mermaid_environment_files(self):
        # Write all mermaid environement in one cycle
        for log in self.logs :
            # The .MER file can be listed in the .LOG but not actually exist on the server
            if log.mer_environment_name is None or not log.mer_environment_name_exists:
                continue

            # Check if the output file already exists
            processed_path = self.processed_path + log.log_name + "." + log.mer_environment_name + ".env"
            if os.path.exists(processed_path):
                return

            # Write file
            with open(processed_path, "w") as f:
                if log.mer_environment:
                    f.write(log.mer_environment)

    def write_s41_environment_file(self):
        # Check if there is a s41 profile
        if len(self.profilesS41) == 0:
            return
        # Get environnement for all profiles
        environment = ""
        for profile in self.profilesS41:
            environment += "<PARAMETERS file=" + profile.file_name + ">\r\n"
            environment += profile.parameters_header()
            environment += "<\PARAMETERS>\r\n"

        # Check if file exist
        processed_path = self.processed_path + self.cycle_name + ".S41.params"
        if os.path.exists(processed_path):
            return

        # Write file
        with open(processed_path, "w") as f:
            f.write(environment)

    def write_s61_environment_file(self):
        # Check if there is a s41 profile
        if len(self.profilesS61) == 0:
            return
        # Get environnement for all profiles
        environment = ""
        for profile in self.profilesS61:
            environment += "<PARAMETERS file=" + profile.file_name + ">\r\n"
            environment += profile.parameters_header()
            environment += "<\PARAMETERS>\r\n"

        # Check if file exist
        processed_path = self.processed_path + self.cycle_name + ".S61.params"
        if os.path.exists(processed_path):
            return

        # Write file
        with open(processed_path, "w") as f:
            f.write(environment)

    def write_cycle_html(self, csv_file, optimize=False, include_plotly=True):
        '''
            Generates a dive plot for a complete cycle
        '''

        # Check if file exist
        processed_path = self.processed_path + self.cycle_name[:-4] + '.html'
        if os.path.exists(processed_path):
            return

        # If the float is not diving don't plot anything
        if not self.is_dive:
            return

        # Search pressure values
        # DO NOT DO: `('\[PRESS ,\s*\d+\]P\s*(\+?\-?\d+)mbar', self.cycle_content)`
        # because "P.*mbar" is a valid pressure, even if prefixed with "[SURFIN, ..."
        pressure = utils.find_timestamped_values("P\s*(\+?\-?\d+)mbar", self.cycle_content)
        bypass = utils.find_timestamped_values(":\[BYPASS", self.cycle_content)
        valve = utils.find_timestamped_values(":\[VALVE", self.cycle_content)
        pump = utils.find_timestamped_values(":\[PUMP", self.cycle_content)
        mermaid_events = utils.find_timestamped_values("\[MRMAID,\d+\] *\d+dbar, *-?\d+degC", self.cycle_content)

        # Return if there is no data to plot
        if len(pressure) < 1:
            return

        # Add pressure values to the graph
        p_val = [-int(p[0])/100. for p in pressure]
        p_date = [p[1] for p in pressure]

        # Plotly you can implement WebGL with Scattergl() in place of Scatter()
        # for increased speed, improved interactivity, and the ability to plot even more data.
        Scatter = graph.Scatter
        if optimize :
            Scatter = graph.Scattergl

        depth_line = graph.Scatter(x=p_date,
                                   y=p_val,
                                   name="depth",
                                   line=dict(color='#474747',
                                             width=2),
                                   mode='lines+markers')

        if csv_file:
            p_date_format = [UTCDateTime.strftime(UTCDateTime(date), "%Y%m%dT%H%M%S") for date in p_date]
            csv_path = processed_path.replace(".html",".csv")
            rows = zip(p_date_format,p_val)
            with open(csv_path, mode='w') as csv_file:
                csv_file = csv.writer(csv_file, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                for row in rows:
                    csv_file.writerow(row)

        # Add vertical lines
        # Find minimum and maximum for Y axis of vertical lines
        minimum = min(p_val) + 0.05*min(p_val)
        maximum = 0

        # Add bypass lines
        bypass = [bp[1] for bp in bypass]
        bypass_line = utils.plotly_vertical_shape(bypass,
                                                  ymin=minimum,
                                                  ymax=maximum,
                                                  name="bypass",
                                                  color="blue")
        # Add valve lines
        valve = [vv[1] for vv in valve]
        valve_line = utils.plotly_vertical_shape(valve,
                                                 ymin=minimum,
                                                 ymax=maximum,
                                                 name="valve",
                                                 color="green")
        # Add pump lines
        pump = [pp[1] for pp in pump]
        pump_line = utils.plotly_vertical_shape(pump,
                                                ymin=minimum,
                                                ymax=maximum,
                                                name="pump",
                                                color="orange")

        # Add mermaid events lines
        mermaid_events = [pp[1] for pp in mermaid_events]
        mermaid_events_line = utils.plotly_vertical_shape(mermaid_events,
                                                          ymin=minimum,
                                                          ymax=maximum,
                                                          name="MERMAID events",
                                                          color="purple")
        # Add emergency if any
        emergency_triggers = [pp[1] for pp in self.emergency_triggers]
        emergency_triggers_line = utils.plotly_vertical_shape(emergency_triggers,
                                                                  ymin=minimum,
                                                                  ymax=maximum,
                                                                  name="Emergency",
                                                                  color="black",
                                                                  width=2.0)
        # Add mermaid reboot if any
        mermaid_reboots = [pp[1] for pp in self.mermaid_reboots]
        mermaid_reboots_line = utils.plotly_vertical_shape(mermaid_reboots,
                                                                  ymin=minimum,
                                                                  ymax=maximum,
                                                                  name="MERMAID reboot",
                                                                  color="red",
                                                                  width=2.0)


        data = [bypass_line, valve_line, pump_line, mermaid_events_line, depth_line, emergency_triggers_line, mermaid_reboots_line]

        layout = graph.Layout(title=self.directory_name + '/' + self.cycle_name,
                              xaxis=dict(title='Coordinated Universal Time (UTC)', titlefont=dict(size=18)),
                              yaxis=dict(title='Depth (meters)', titlefont=dict(size=18)),
                              hovermode='closest'
                              )
        figure = graph.Figure(data=data, layout=layout)

        # Include plotly into any html files ?
        # If false user need connexion to open html files
        if include_plotly :
            figure.write_html(file=processed_path, include_plotlyjs=True)
        else :
            figure.write_html(file=processed_path,
                              include_plotlyjs='cdn', full_html=False)

    def set_kstnm_kinst(self):
        '''Sets attrs for five-character station name (KSTNM), zero-padded between the
        letter and number defining the unique MERMAID (if required), and the
        "generic name of recording instrument" (KINST), defined as the string
        which precedes the first hyphen in the Osean-defined names


        452.112-N-01:   kinst, kstnm = '452.112', 'N0001'
        452.020-P-08:   kinst, kstnm = '452.020', 'P0008'
        452.020-P-0050: kinst, kstnm = '452.020', 'P0050'

        Station names may be a max of five characters:
        https://ds.iris.edu/ds/newsletter/vol1/no1/1/specification-of-seismograms-the-location-identifier/

        '''

        # Split at hyphens to separate kinst, kstnm and pad the middle of the latter
        self.kinst, kstnm_char, kstnm_num = self.station_name.split('-')

        num_zeros = 5 - len(kstnm_char + kstnm_num)
        self.kstnm = kstnm_char + '0'*num_zeros + kstnm_num

    def validate_gps(self, num_gps=2, max_time=5400):
        """

        Returns true if valid GPS fixes exist to interpolate clock drifts and
        station locations at the time of recording events.

        Args:
        num_gps (int): Min. # GPS fixes before(after) diving(surfacing) (def=2)
        max_time (int): Max. time (s) before(after) diving(surfacing) within
                        which `num_gps` must be  recorded (def=5400)

        Sets attrs:
        `gps_valid4clockdrift_correction`: True is good synchronization pre/post dive
        `gps_valid4location_interp`: True is GPS within requested inputs

        Note that the former may be True when the latter is not: the former is a
        softer requirement that only the last(first) GPS fix before(after)
        diving contain a good onboard clock synchronization.

        If max_time is ignored if num_gps=1.

        Allows at most 5 s of clockdrift (generally drifts are < 2 s) to skip
        cases when clock resets occurred immediately before/after dive (MERMAID's
        onboard clock resets to UNIX time 0 -- Thu Jan 1 00:00:00 UTC 1970 --
        which results in a reported clockdrift of ~50 yr; these should already
        be excluded by `get_events_between`, but you can never be too careful).

        """

        self.gps_valid4clockdrift_correction = False
        self.gps_valid4location_interp = False

        # Only gps synchronization save one .MER file give clockfreq and clockdift
        if self.gps_sync_before_dive:
            gps_before = self.gps_sync_before_dive
        else:
            print("Cycle {} : no gps sync before dive ({})".format(self.cycle_nb,self.ascent_reach_surface_date))
            return

        if self.gps_sync_after_dive:
            gps_after = self.gps_sync_after_dive
        else:
            print("Cycle {} : no gps sync after dive ({})".format(self.cycle_nb,self.ascent_reach_surface_date))
            return

        # Ensure MERMAID clock synchronized with last(first) GPS before(after) diving(surfacing)
        # (this also handles the case of verifying `gps.mer_time_log_loc` if `num_gps=1`)
        if gps.valid_clockfreq(gps_before[-1]) \
           and gps_before[-1].clockdrift < 5 \
           and gps.valid_clockfreq(gps_after[0]) \
           and gps_after[0].clockdrift < 5:
           self.gps_valid4clockdrift_correction = True
        else:
            print("Cycle {} : clockdrift or clockfreq not valid".format(self.cycle_nb))
            print("******** : before drift {} freq {}".format(gps_before[-1].clockdrift,gps_before[-1].clockfreq))
            print("******** : after drift {} freq {}".format(gps_after[0].clockdrift,gps_after[0].clockfreq))
            return

        # We only require that `gps.mer_time_log_loc()` be true for the
        # last(first) GPS fix before(after) diving(surfacing) because we those
        # are the two that are used to correct MERMAID's onboard clock and we
        # are (1) not as concerned with timing for GPS fixes that are only used
        # for location interpolation (which, already, has uncertainty), and (2)
        # more importantly we know that clock drifts while at the surface are
        # small because the onboard clock is constantly being resynced.

        if num_gps > 1:
            # Ensure the required number of valid GPS exist within the required
            # time before diving
            count = 0
            for gb in reversed(gps_before):
                tdiff = self.descent_leave_surface_date - gb.date
                if tdiff < max_time:
                    count += 1

            if count < num_gps:
                print("Cycle {} : not enough positions before leave surface ({})".format(self.cycle_nb,self.descent_leave_surface_date))
                return

            # Ensure the required number of valid GPS exist within the required
            # time after surfacing
            count = 0
            for ga in gps_after:
                tdiff = ga.date - self.ascent_reach_surface_date
                if tdiff < max_time:
                    count += 1

            if count < num_gps:
                print("Cycle {} : not enough positions after ascent ({})".format(self.cycle_nb,self.ascent_reach_surface_date))
                return

        # If here, all tests passed
        self.gps_valid4location_interp = True
        return

    def correct_clockdrifts(self):
        '''Estimate and correct GPS clockdrifts for each event associated with this
        complete dive.

        '''

        if not self.gps_valid4clockdrift_correction:
            return

        # Correct clock drift
        for event in self.events:
            event.correct_clockdrift(self.gps_sync_before_dive[-1],
                                     self.gps_sync_after_dive[0])

    def set_processed_file_names(self):
        '''Sets `processed_file_name` attr for each event attached to this complete
        dive.

        Removes redundant events, e.g.,
        20180728T225619.07_5B7739F0.MER.REQ.WLT5, whose data appears twice in
        07_5B7739F0.MER.

        Appends '1' to 'MER' in redundant file names whose data actually differ,
        e.g., in the case of '20180728T225619.06_5B773AE6.MER.REQ.WLT5' and
        '20180728T225619.06_5B773AE6.MER1.REQ.WLT5', whose data are both
        contained in 06_5B773AE6.MER and do in fact differ, but whose processed
        filenames are identical because those only display seconds precision
        (and the timing differences between the event dates are on the order of
        fractional seconds).

        This check for redundancy only considers a single redundant file name
        appearing twice in any give cycle; if multiple filenames appear
        twice and/or any one appears three or more times this will error (the
        fix complicates the code a lot and I've yet to see the need for it...).

        Note that setting of attr `processed_file_name` does not imply that valid
        GPS fixes are associated with the events and they therefore may be
        written to output .sac and .mseed files; that is determined by the
        setting of attr `station_loc`.

        '''

        names = []
        for event in self.events:
            event.set_processed_file_name()
            names.append(event.processed_file_name)

        # It is acceptable to check for processed filename redundancies on a
        # per-dive basis, as opposed to considering the entire `event.Events`
        # list, because the same data (meaning that `event.mer_binary_binary`
        # and `event.mer_binary_header` are equal) requested at a later date
        # will be transmitted in a different .MER file, e.g., the
        # `event.mer_binary_name` will be different from the current dive and
        # thus the `event.processed_file_name` resulting in no name conflict

        redundant_names = [name for name,count in collections.Counter(names).items() if count > 1 and name is not None]

        if not redundant_names:
            return

        if len(redundant_names) > 1:
            raise ValueError('Must edit def to handle multiple redundant file names')

        redundant_index = []
        for index,name in enumerate(names):
            if name == redundant_names[0]:
                redundant_index.append(index)

        if len(redundant_index) > 2:
            raise ValueError('Must edit def to handle 3+ occurrences of a single redundant file name')

        # Same processed file name  (.sac, .mseed), different data (do not remove from list!):
        #     '20180728T225619.06_5B773AE6.MER.REQ.WLT5'
        # Rename second occurrence of redundant PROCESSED file name to:
        #     '20180728T225619.06_5B773AE6.MER1.REQ.WLT5'
        #
        # Same file name, redundant data (remove second event from list):
        #     '20180728T225619.07_5B7739F0.MER.REQ.WLT5'

        if self.events[redundant_index[0]].mer_binary_header ==  \
           self.events[redundant_index[1]].mer_binary_header and \
           self.events[redundant_index[0]].mer_binary_binary ==  \
           self.events[redundant_index[1]].mer_binary_binary:

            # Remove the redundant event from the list of events associated with
            # this cycle.  This does not delete the events.Event object
            # itself, which is still referenced elsewhere, including
            # `dive_logs`, so be careful
            del self.events[redundant_index[1]]

        else:
            # Rename the event with DIFFERENT data but a redundant processed file
            # name (e.g., because the filename only has seconds precision, and
            # the event date may be different by fractional seconds) from
            # "...MER..." to "...MER1..."
            self.events[redundant_index[1]].processed_file_name = \
            self.events[redundant_index[1]].processed_file_name.replace('MER', 'MER1')

    def compute_station_locations(self, mixed_layer_depth_m, preliminary_location_ok=False):
        '''
        Fills attributes detailing interpolated locations of MERMAID at various
        points during a Dive (i.e., when it left the surface, reached the mixed
        layer, etc.), including `self.events[*].station_loc`, which is required
        to write the out .sac and .mseed files.

        '''
        if not self.gps_valid4location_interp:
            if preliminary_location_ok:
                for event in self.events:
                    if self.gps_before_dive and self.gps_after_dive:
                        # Use last GPS before dive and first GPS after dive, ideally
                        event.compute_station_location(self.gps_before_dive[-1], \
                                                       self.gps_after_dive[0], \
                                                       station_loc_is_preliminary=True)

                    elif self.gps_after_dive:
                        # Then first after dive, assuming preliminary location for
                        # event that caused immediate surfacing
                        event.compute_station_location(self.gps_after_dive[0], \
                                                       self.gps_after_dive[0], \
                                                       station_loc_is_preliminary=True)

                    elif self.gps_before_dive:
                        # Use last before dive as last resort
                        event.compute_station_location(self.gps_before_dive[-1], \
                                                       self.gps_before_dive[-1], \
                                                       station_loc_is_preliminary=True)

            # Always exit this def, regardless of if preliminary location estimated or not
            return

        # Find when & where the float left the surface
        self.descent_leave_surface_loc = gps.linear_interpolation(self.gps_before_dive, \
                                                                  self.descent_leave_surface_date)

        # Find when & where the float reached the surface
        self.ascent_reach_surface_loc =  gps.linear_interpolation(self.gps_after_dive, \
                                                                  self.ascent_reach_surface_date)
        # Find pressure values
        pressure_date = [p[1] for p in self.pressure_mbar]

        # Convert pressure values from mbar to dbar
        # For our purposes it it fine to assume that 1 dbar = 1 m = 100 mbar
        # (NOT 1 m = 101 mbar as stated in MERMAID manual Réf : 452.000.852 Version 00)
        pressure_dbar = [int(p[0])/100. for p in self.pressure_mbar]

        # Determine if using one- or two-layer ocean.
        if max(pressure_dbar) > mixed_layer_depth_m:
            # Two-layer ocean case (surface and mixed)
            # Interpolate for location that MERMAID passed from the surface layer to the mixed layer
            # on the descent

            # Loop through pressure readings until we've exited surface layer and passed into the
            # mixed layer -- this assumes we don't bob in and out of the mixed layer, and it only
            # retains the date of the first crossing
            i = 0
            while pressure_dbar[i] < mixed_layer_depth_m and i < len(pressure_dbar):
                i += 1

            descent_date_in_mixed_layer = pressure_date[i]
            descent_depth_in_mixed_layer = pressure_dbar[i]

            if i > 0:
                descent_date_in_surface_layer = pressure_date[i-1]
                descent_depth_in_surface_layer = pressure_dbar[i-1]
            else:
                # On the descent: we have pressure readings in the mixed layer but not in the
                # surface layer -- just interpolate using the last-known (diving) location
                descent_date_in_surface_layer = self.descent_leave_surface_date
                descent_depth_in_surface_layer = 0

            # Compute when the float leaves the surface layer and reaches the mixed layer
            descent_vel = (descent_depth_in_mixed_layer - descent_depth_in_surface_layer) \
                          / (descent_date_in_mixed_layer - descent_date_in_surface_layer)
            descent_dist_to_mixed_layer = mixed_layer_depth_m - descent_depth_in_surface_layer
            descent_time_to_mixed_layer = descent_dist_to_mixed_layer / descent_vel
            self.descent_leave_surface_layer_date = descent_date_in_surface_layer + descent_time_to_mixed_layer
            self.descent_leave_surface_layer_loc = gps.linear_interpolation(self.gps_before_dive, \
                                                                            self.descent_leave_surface_layer_date)

            #______________________________________________________________________________________#

            # Interpolate for location that MERMAID passed from the mixed layer to the surface layer
            # on the ascent

            # Loop through pressure readings until we've exited mixed layer and passed into the
            # surface layer -- this assumes we don't bob in and out of the mixed layer, and it only
            # retains the date of the final crossing
            i = len(pressure_dbar)-1
            while pressure_dbar[i] < mixed_layer_depth_m and i > 0:
                i -= 1

            ascent_date_in_mixed_layer = pressure_date[i]
            ascent_depth_in_mixed_layer = pressure_dbar[i]

            if i < len(pressure_dbar)-1:
                ascent_date_in_surface_layer = pressure_date[i+1]
                ascent_depth_in_surface_layer = pressure_dbar[i+1]
            else:
                # On the ascent: we have pressure readings in the mixed layer but not the surface
                # layer -- just interpolate using next-know (surfacing) location
                ascent_date_in_surface_layer = self.ascent_reach_surface_date
                ascent_depth_in_surface_layer = 0

            # Compute when the float leaves the mixed layer and reaches the surface (flipped
            # subtraction order so that ascent velocity is positive)
            ascent_vel = (ascent_depth_in_mixed_layer - ascent_depth_in_surface_layer) \
                         / (ascent_date_in_surface_layer - ascent_date_in_mixed_layer)
            ascent_dist_to_mixed_layer = ascent_depth_in_mixed_layer - mixed_layer_depth_m
            ascent_time_to_mixed_layer = ascent_dist_to_mixed_layer / ascent_vel
            self.ascent_reach_surface_layer_date = ascent_date_in_mixed_layer + ascent_time_to_mixed_layer
            self.ascent_reach_surface_layer_loc = gps.linear_interpolation(self.gps_after_dive, \
                                                                           self.ascent_reach_surface_layer_date)

            #______________________________________________________________________________________#

            # MERMAID passed through the surface layer and into the mixed layer -- interpolate the
            # location of the recorded event assuming a multi-layer (surface and mixed) ocean
            self.descent_last_loc_before_event = self.descent_leave_surface_layer_loc
            self.ascent_first_loc_after_event = self.ascent_reach_surface_layer_loc

        else:
            # One-layer ocean case (surface only)

            # MERMAID never passed through the surface layer and into the mixed layer --
            # interpolate the location of the recorded event assuming single-layer ocean
            self.descent_last_loc_before_event = self.descent_leave_surface_loc
            self.ascent_first_loc_after_event = self.ascent_reach_surface_loc

        # Compute event locations between interpolated locations of exit and re-entry of surface waters
        for event in self.events:
            event.compute_station_location(self.descent_last_loc_before_event,
                                           self.ascent_first_loc_after_event)

    def set_events_obspy_trace_stats(self):
        for event in self.events:
            if event.station_loc is not None:
                event.set_obspy_trace_stats()

    def write_events_html(self, optimize=False, include_plotly=True):
        for event in self.events:
            if not event.is_stanford_event:
                event.plot_html(self.processed_path,optimize,include_plotly)
            else:
                event.plot_html_stanford(self.processed_path,optimize,include_plotly)

    def write_events_png(self):
        for event in self.events:
            if not event.is_stanford_event:
                event.plot_png(self.processed_path)
            else:
                event.plot_png_stanford(self.processed_path)

    def write_profile_html(self, optimize=False, include_plotly=True):
        for profile in self.profilesS41:
            profile.write_temperature_html(self.processed_path,optimize,include_plotly)
            profile.write_salinity_html(self.processed_path,optimize,include_plotly)
        for profile in self.profilesS61:
            profile.write_temperature_html(self.processed_path,optimize,include_plotly)
            profile.write_salinity_html(self.processed_path,optimize,include_plotly)

    def write_profile_csv(self):
        for profile in self.profilesS41:
            profile.write_csv(self.processed_path)
        for profile in self.profilesS61:
            profile.write_csv(self.processed_path)

    def write_events_sac(self):
        for event in self.events:
            event.write_sac(self.processed_path)

    def write_events_mseed(self):
        for event in self.events:
            event.write_mseed(self.processed_path)

    def write_events_mhpsd(self, creation_datestr=None):
        for event in self.events:
            event.write_mhpsd(self.processed_path, creation_datestr)

    def print_len(self):
        len_str  = "   Date: {:s} -> {:s} ({:.2f} days; first/last line of {:s})" \
                   .format(str(self.start_date)[0:19], str(self.end_date)[0:19],
                           self.len_days, self.cycle_name)
        print(len_str)
        return len_str + "\n"

    def print_errors(self):
        # Print emergency triggers
        errors_str = ""
        if self.emergency_triggers:
            causes = "!!!WARNING !!! Emergency : "
            for trig in self.emergency_triggers:
                causes += "{} ".format(trig[0])
            print(causes)
            errors_str += causes + "\n"
        # Print mermaid reboot events
        if self.mermaid_reboots:
            dates = "!!!WARNING !!! Mermaid reboot : "
            for reboot in self.mermaid_reboots:
                dates += "{} ".format(reboot[1])
            print(dates)
            errors_str += dates + "\n"
        return errors_str

    def print_dates(self):
        dates_str = ""
        leave_surface_str = ""
        if self.descent_leave_surface_date:
            leave_surface_str += "   Leave surface : {:s}".format(str(self.descent_leave_surface_date)[0:19])
        else :
            leave_surface_str += "   Leave surface : <none>"
        print(leave_surface_str)
        dates_str += leave_surface_str + "\n"

        ascent_start_str = ""
        if self.ascent_start_date:
            ascent_start_str += "   Ascent start  : {:s}".format(str(self.ascent_start_date)[0:19])
        else :
            ascent_start_str += "   Ascent start  : <none>"
        print(ascent_start_str)
        dates_str += ascent_start_str + "\n"

        ascent_reach_surface_str = ""
        if self.ascent_reach_surface_date:
            ascent_reach_surface_str += "   Reach surface : {:s}".format(str(self.ascent_reach_surface_date)[0:19])
        else :
            ascent_reach_surface_str += "   Reach surface : <none>"
        print(ascent_reach_surface_str)
        dates_str += ascent_reach_surface_str + "\n"
        return dates_str

    def print_logs(self):
        log_mer_str = ""
        for i,_ in enumerate(self.logs):
            start_date = str(self.logs[i].start_date)[0:19]
            end_date = str(self.logs[i].end_date)[0:19]
            if self.logs[i].is_partial :
                log_name = self.logs[i].log_name + "<partial>"
            else :
                log_name = self.logs[i].log_name + "<complete>"

            log_str  = "     #{:d}/ {:s} Date: {:s} -> {:s} ({:.2f} days)" \
                       .format(i+1,log_name,start_date,end_date,self.logs[i].len_days)

            if self.logs[i].mer_environment_name :
                mermaid_str = "{:s}.".format(self.logs[i].mer_environment_name)
            else :
                mermaid_str = ""

            if self.logs[i].s41_file_name :
                profile_str = "{:s}.".format(self.logs[i].s41_file_name)
            elif self.logs[i].s61_file_name :
                profile_str = "{:s}.".format(self.logs[i].s61_file_name)
            else :
                profile_str = ""

            if mermaid_str or profile_str :
                tmp_str = "{:s} Data files : {:s} {:s}".format(log_str,mermaid_str,profile_str)
            else :
                tmp_str = "{:s} Data files : <none>".format(log_str,mermaid_str,profile_str)
            print(tmp_str)
            log_mer_str += tmp_str + "\n"

        return log_mer_str

    def print_events(self):
        evt_str = ""
        if not self.events:
            tmp_str = "  Event: (no detected or requested events fall within the time window of this dive)"
            print(tmp_str)
            evt_str += tmp_str + "\n"
        else:
            for e in self.events:
                processed_file_name = e.processed_file_name
                if processed_file_name is None :
                    processed_file_name = "<None>"
                if e.station_loc is None:
                    tmp_str = " Event: ! NOT MADE ! (invalid and/or not enough GPS fixes) {:s} (</EVENT> binary in {:s})" \
                              .format(processed_file_name, e.mer_binary_name)
                else:
                    tmp_str = "  Event: {:s} (</EVENT> binary in {:s})" \
                              .format(processed_file_name, e.mer_binary_name)
                print(tmp_str)
                evt_str += tmp_str + "\n"
        return evt_str


# Create dives object
def get_cycles(path, events, profilesS41, profilesS61):
    # Get the list of cycle files
    cycle_names = glob.glob(path + "*.CYCLE")
    cycle_names = [os.path.basename(x) for x in cycle_names]
    cycle_names.sort()
    # Create Cycle objects
    cycles = []
    for cycle_name in cycle_names:
        c = Cycle(path, cycle_name, events, profilesS41, profilesS61)
        if c.cycle_content:
            cycles.append(c)
    return cycles

def write_cycles_txt(cycles, creation_datestr, processed_path, mfloat_path, mfloat):
    '''

    Writes cycles.txt and prints the same info to stdout

    A complete cycle is defined by two successive descents of the profiler.

    '''
    cycles_file = os.path.join(processed_path, mfloat_path, "cycles.txt")
    version_line = "#automaid {} ({})\n".format(setup.get_version(), setup.get_url())
    created_line = "#created {}\n".format(creation_datestr)

    with open(cycles_file, "w+") as f:
        f.write(version_line)
        f.write(created_line)

        for cycle in sorted(cycles, key=lambda x: x.start_date):
            print("Cycle {}\n".format(cycle.cycle_nb))
            f.write("Cycle {}\n".format(cycle.cycle_nb))
            # These methods both return, and print to stdout, the same formatted string
            f.write(cycle.print_errors())
            f.write(cycle.print_len())
            f.write(cycle.print_dates())
            f.write(cycle.print_logs())
            f.write(cycle.print_events())
            print("")
            f.write("\n")

        # Determine the total number of SAC and/or miniSEED files that COULD be
        # written (but do not necessarily exists, e.g., if `events_sac=False` in
        # main.py).
        sac_str = "    {:s} total: {:d} (non-preliminary) SAC & miniSEED files\n".format(mfloat, \
                  len([e for d in cycles for e in d.events if e.station_loc and not e.station_loc_is_preliminary]))

        print(sac_str)
        f.write(sac_str)


def write_logs_txt(cycles, creation_datestr, processed_path, mfloat_path):
    '''Writes dives.txt, which treats every .LOG as a single (possibly incomplete) dive

    Prints all data for every .LOG/.MER in the server; does not, e.g., only
    print info associated with those .LOG/.MER within datetime range of  `main.py`

    '''
    logs_file = os.path.join(processed_path, mfloat_path, "logs.txt")
    fmt_spec = "{:>9s}    {:>8s}    {:>20s}    {:>20s}    {:>10d}    {:>9.3f}    {:>17s}    {:>17s}\n"

    version_line = "#automaid {} ({})\n".format(setup.get_version(), setup.get_url())
    created_line = "#created {}\n".format(creation_datestr)
    header_line = "#cycle_nb     dive_id               log_start                 log_end      len_secs     len_days             cycle_name         mer_env_name\n".format()

    with open(logs_file, "w+") as f:
        f.write(version_line)
        f.write(created_line)
        f.write(header_line)

        # 1 .LOG == 1 dive
        for cycle in sorted(cycles, key=lambda x: x.start_date):
            for log in sorted(cycle.complete_logs, key=lambda x: x.start_date):
                f.write(fmt_spec.format(str(cycle.cycle_nb),
                                        str(log.dive_id),
                                        str(log.start_date)[:19] + 'Z',
                                        str(log.end_date)[:19] + 'Z',
                                        int(log.len_secs),
                                        log.len_days,
                                        log.log_name,
                                        str(log.mer_environment_name)))

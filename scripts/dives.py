# -*- coding: utf-8 -*-
#
# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v2.7)
#
# Developer: Joel D. Simon (JDS)
# Original author: Sebastien Bonnieux (SB)
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified by JDS: 18-Jan-2022
# Last tested: Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit

import os
import re
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

# Class to manipulate log files
class Dive:
    ''' The Dive class references a single .LOG file.

    1 .LOG file == 1 Dive instance

    Any single dive only references a single .LOG file (dive.log_name) and the
    ENVIRONMENT block of a single .MER (dive.mer_environment_name) file, though
    it may contain multiple Event instances which reference zero or more
    (possibly different) .MER files that contain the event data that was
    recorded during this dive.

    '''

    def __init__(self, base_path=None, log_name=None, events=None, begin=None, end=None):
        self.base_path = base_path
        self.log_name = log_name
        self.__version__ = version

        self.directory_name = None
        self.processed_path = None
        self.station_name = None
        self.station_number = None
        self.kstnm = None
        self.kinst = None

        self.log_content = None
        self.start_date = None
        self.end_date = None
        self.len_secs = None
        self.len_days = None

        self.mer_environment_name = None
        self.mer_environment_name_exists = False
        self.mer_environment = None

        self.gps_from_log = None
        self.gps_from_mer_environment = None
        self.gps_nonunique_list = None
        self.gps_list = None

        self.gps_before_dive = None
        self.gps_before_dive_incl_prev_dive = None
        self.gps_after_dive = None
        self.gps_after_dive_incl_next_dive = None

        self.descent_leave_surface_date = None
        self.ascent_reach_surface_date = None

        self.p2t_offset_param = None
        self.p2t_offset_measurement = None
        self.p2t_offset_corrected = None

        self.is_init = False
        self.is_dive = False
        self.is_complete_dive = False
        self.dive_id = None

        self.prev_dive_log_name = None
        self.prev_dive_mer_environment_name = None

        self.next_dive_log_name = None
        self.next_dive_mer_environment_name = None

        print("{}".format(self.log_name))

        # Get the date from the file name -- the hexadecimal component of the
        # .LOG file name is the same Unix Epoch time as the first line of the
        # LOG file (there in int seconds); i.e., .LOG files are named for the
        # time that their first line is written
        self.start_date = utils.get_date_from_file_name(log_name)

        # Read the content of the LOG
        with open(self.base_path + self.log_name, "r") as f:
            self.log_content = f.read()

        # Get the last date (last line of the log file)
        #
        # Unfortunately, .LOG files can also suffer from incomplete transmission
        # and I do not yet know how to get around that; if this line fails wait
        # until next surfacing to rerun automaid until a fix is found
        ed = re.findall("(\d+):", utils.split_log_lines(self.log_content)[-1])[0]
        self.end_date = UTCDateTime(int(ed))
        self.len_secs = int(self.end_date - self.start_date)
        self.len_days = self.len_secs / (60*60*24.)

        # Check if the log correspond to the float initialization
        match = re.search("\[TESTMD,\d{3}\]\"yes\"", self.log_content)
        if "Enter in test mode?" in self.log_content and not match:
            self.is_init = True

        # Check if the .LOGS corresponds to a dive
        diving = utils.find_timestamped_values("\[DIVING, *\d+\] *(\d+)mbar reached", self.log_content)
        if diving:
            self.descent_leave_surface_date = diving[0][1]
            self.is_dive = True

        # It's possible that MERMAID physically dove and returned to the surface but there was
        # an error with the .LOG, so that information was not recorded (ex. 25_5B9CF6CF.LOG)
        surfin = utils.find_timestamped_values("\[SURFIN, *\d+\]filling external bladder", self.log_content)
        if surfin:
            self.ascent_reach_surface_date = surfin[-1][-1]

        # Check if the .LOG is fragmented
        # Sometimes the .LOG will have errors and only print the dive or surfacing date
        if self.descent_leave_surface_date and self.ascent_reach_surface_date:
            self.is_complete_dive = True

        # Generate the directory name
        self.directory_name = self.start_date.strftime("%Y%m%d-%Hh%Mm%Ss")
        if self.is_init:
            self.directory_name += "Init"
        elif not self.is_dive:
            self.directory_name += "NoDive"
        elif not self.is_complete_dive:
            self.directory_name += "IcDive"

        self.processed_path = self.base_path + self.directory_name + "/"

        # Get the station name
        if self.is_dive or self.is_init:
            self.station_name = re.findall("board (.+)", utils.split_log_lines(self.log_content)[0])
            if len(self.station_name) == 0:
                self.station_name = re.findall("board (.+)", utils.split_log_lines(self.log_content)[1])
            if len(self.station_name) == 0:
                self.station_name = re.findall("buoy (.+)", utils.split_log_lines(self.log_content)[0])
            if len(self.station_name) == 0:
                self.station_name = re.findall("buoy (.+)", utils.split_log_lines(self.log_content)[1])
            self.station_name = self.station_name[0]
            self.station_number = self.station_name.split("-")[-1]

            # Zero-pad the (unique part) of the station name so that it is five characters long
            self.attach_kstnm_kinst()

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
                # file may correspond to a different dive (GPS fixes from a
                # DIFFERENT .LOG and .MER environment), thus we must
                # "get_events_between" to correlate the actual binary data in .MER
                # files with their proper GPS fixes (usually the dates of the binary
                # events in the .MER file correspond to the .MER file itself,
                # however if there are a lot of events to send back corresponding to
                # a single dive, it may take multiple surfacings to finally transmit
                # them all).

                # Read the Mermaid environment associated to the dive
                with open(mer_fullfile_name, "r") as f:
                    content = f.read()
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

        # Get list of events associated with this .MER files environment
        # (the metadata header, which does not necessarily relate to the
        # attached events and their binary data).
        self.events = events.get_events_between(self.start_date, self.end_date)

        # Set and parse info from .MER file and invert wavelet transform any binary data
        # (cannot invert the data without vital information from the .MER environment)
        if self.mer_environment:
            for event in self.events:
                event.set_environment(self.mer_environment_name, self.mer_environment)
                event.find_measured_sampling_frequency()
                event.set_uncorrected_starttime()
                event.process_binary_data()

        # Re-sort events based on starttime (rather than INFO DATE)
        self.events.sort(key=lambda x: x.uncorrected_starttime)

        # Collect all GPS fixes taken in both the .LOG  and .MER file
        self.gps_list, self.gps_nonunique_list, self.gps_from_log, self.gps_from_mer_environment \
            = gps.get_gps_lists(self.log_name, self.log_content,
                                self.mer_environment_name, self.mer_environment,
                                begin, end)

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

    def __len__(self):
        return 1

    def generate_datetime_log(self):
        # Check if file exist
        processed_path = self.processed_path + self.log_name + ".h"
        if os.path.exists(processed_path):
            return
        # Generate log with formatted date
        formatted_log = utils.format_log(self.log_content)
        # Write file
        with open(processed_path, "w") as f:
            f.write(formatted_log)

    def generate_mermaid_environment_file(self):
        # The .MER file can be listed in the .LOG but not actually exist on the server
        if self.mer_environment_name is None or not self.mer_environment_name_exists:
            return

        # Check if the output file already exists
        processed_path = self.processed_path + self.log_name + "." + self.mer_environment_name + ".env"
        if os.path.exists(processed_path):
            return

        # Write file
        with open(processed_path, "w") as f:
            if self.mer_environment:
                f.write(self.mer_environment)

    def generate_dive_plotly(self):
        '''Generates a dive plot for a SINGLE .LOG file, which usually describes a
        complete dive, but not always. I.e., this does not plot a
        `Complete_Dive` instance, but rather generates a single plot for
        whatever is written to an individual .LOG file.

        '''

        # Check if file exist
        processed_path = self.processed_path + self.log_name[:-4] + '.html'
        if os.path.exists(processed_path):
            return

        # If the float is not diving don't plot anything
        if not self.is_dive:
            return

        # Search pressure values
        # DO NOT DO: `('\[PRESS ,\s*\d+\]P\s*(\+?\-?\d+)mbar', self.log_content)`
        # because "P.*mbar" is a valid pressure, even if prefixed with "[SURFIN, ..."
        pressure = utils.find_timestamped_values("P\s*(\+?\-?\d+)mbar", self.log_content)
        bypass = utils.find_timestamped_values(":\[BYPASS", self.log_content)
        valve = utils.find_timestamped_values(":\[VALVE", self.log_content)
        pump = utils.find_timestamped_values(":\[PUMP", self.log_content)
        mermaid_events = utils.find_timestamped_values("[MRMAID,\d+] *\d+dbar, *-?\d+degC", self.log_content)

        # Return if there is no data to plot
        if len(pressure) < 1:
            return

        # Add pressure values to the graph
        p_val = [-int(p[0])/100. for p in pressure]
        p_date = [p[1] for p in pressure]
        depth_line = graph.Scatter(x=p_date,
                                   y=p_val,
                                   name="depth",
                                   line=dict(color='#474747',
                                             width=2),
                                   mode='lines+markers')

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

        data = [bypass_line, valve_line, pump_line, mermaid_events_line, depth_line]

        layout = graph.Layout(title=self.directory_name + '/' + self.log_name,
                              xaxis=dict(title='Coordinated Universal Time (UTC)', titlefont=dict(size=18)),
                              yaxis=dict(title='Depth (meters)', titlefont=dict(size=18)),
                              hovermode='closest'
                              )

        plotly.plot({'data': data, 'layout': layout},
                    filename=processed_path,
                    auto_open=False)

    def attach_kstnm_kinst(self):
        '''Attaches a five-character station name (KSTNM), zero-padded between the letter and number
        defining the unique MERMAID (if required), and the "generic name of recording instrument"
        (KINST), defined as the string which precedes the first hyphen in the Osean-defined names


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


    def attach_prev_next_dive(self, prev_dive, next_dive):
        if prev_dive:
            self.prev_dive_log_name = prev_dive.log_name
            self.prev_dive_mer_environment_name = prev_dive.mer_environment_name

        if next_dive:
            self.next_dive_log_name = next_dive.log_name
            self.next_dive_mer_environment_name = next_dive.mer_environment_name

    # def __repr__(self):
    #     return "Dive('{}', '{}', {})".format(self.base_path, self.log_name, self.events)

    # def print_dive_gps(self):
    #     # Repeat printout for the previous dive, whose data affect the GPS interpolation of the
    #     # current dive
    #     if self.prev_dive_log_name is not None:
    #         if self.prev_dive_mer_environment_name is not None:
    #             print("    GPS: {:s} (</ENVIRONMENT>) & {:s} [prev dive]" \
    #                   .format(self.prev_dive_mer_environment_name, self.prev_dive_log_name))
    #         else:
    #             print("    GPS: {:s} [prev dive]".format(self.prev_dive_log_name))
    #     else:
    #         print("    GPS: (...no previous dive...)")

    #     # By definition 1 .LOG == 1 "dive," so there is always a .log file but
    #     # not necessarily an associated .MER (e.g., test or init I think?)
    #     if self.mer_environment_name is not None:
    #         print("         {:s} (</ENVIRONMENT>) & {:s} [this dive]" \
    #               .format(self.mer_environment_name, self.log_name))
    #     else:
    #         print("         {:s} [this dive]".format(self.log_name))

    #     # Repeat printout for the following dive, whose data affect the gps
    #     # interpolation of the current dive
    #     if self.next_dive_exists:
    #         if self.next_dive_mer_environment_name is not None:
    #             print("         {:s} (</ENVIRONMENT>) & {:s} [next dive]" \
    #                   .format(self.next_dive_mer_environment_name, self.next_dive_log_name))
    #         else:
    #             print("         {:s} [next dive]".format(self.next_dive_log_name))
    #     else:
    #         print("         (...awaiting next_dive...)")

class Complete_Dive:
    '''

    '''

    # Class attribute to hold MERMAID "MH" FDSN network code
    network = utils.network()

    def __init__(self, complete_dive=None):

        self.pressure_mbar = None

        self.gps_valid4clockdrift_correction = None
        self.gps_valid4location_interp = None

        self.gps_before_dive_incl_prev_dive = None
        self.descent_leave_surface_loc = None
        self.descent_leave_surface_layer_date = None
        self.descent_leave_surface_layer_loc = None
        self.descent_last_loc_before_event = None

        self.gps_after_dive_incl_next_dive = None
        self.ascent_reach_surface_loc = None
        self.ascent_reach_surface_layer_date = None
        self.ascent_reach_surface_layer_loc = None
        self.ascent_first_loc_after_event = None

        self.log_name = [d.log_name for d in complete_dive]
        self.log_content = ''.join(d.log_content for d in complete_dive)
        self.mer_environment_name = [d.mer_environment_name for d in complete_dive]
        self.__version__ = complete_dive[-1].__version__

        self.start_date = complete_dive[0].start_date
        self.end_date = complete_dive[-1].end_date
        self.dive_id = [d.dive_id for d in complete_dive]

        if len(self.log_name) != len(self.mer_environment_name):
            raise ValueError('Expected equal-length lists: .LOG, .MER (.MER can be `None`)')

        self.len_secs = self.end_date - self.start_date
        self.len_days = self.len_secs / (60*60*24.)

        self.station_name = complete_dive[-1].station_name
        self.station_number = complete_dive[-1].station_number
        self.kstnm = complete_dive[-1].kstnm
        self.kinst = complete_dive[-1].kinst

        # Might want to rename the directories into something more useful...
        self.base_path = complete_dive[-1].base_path
        self.directory_name = complete_dive[-1].directory_name
        self.processed_path = complete_dive[-1].processed_path

        # The nonunique list may include redundant GPS fixes from fragmented .LOG
        # I.e., an error in the .LOG may result in the redundant printing of GPS
        # fixes over multiple files
        self.gps_nonunique_list = utils.flattenList([d.gps_nonunique_list for d in complete_dive])
        self.gps_nonunique_list = sorted(self.gps_nonunique_list, key=lambda x: x.date)

        # We must re-merge GPS pairs to find truly unique pairs within
        # "complete" dives due to the combination of possibly fragmented .LOG
        # and .MER files that print redundant GPS info that is unique to THAT
        # SPECIFIC file, but NOT unique to a "complete dive" constructed of
        # fragmented files
        self.gps_list = utils.flattenList([d.gps_list for d in complete_dive])
        self.gps_list = gps.merge_gps_list(self.gps_list)

        # Compile all water presure (100 mbar = 1 dbar = 1 m)
        # Run some verifications like we do for GPS to check for redudancies?
        # I do not know if pressure values are repeated over fragmented LOGs...
        # DO NOT DO: `('\[PRESS ,\s*\d+\]P\s*(\+?\-?\d+)mbar', self.log_content)`
        # because "P.*mbar" is a valid pressure, even if prefixed with "[SURFIN, ..."
        self.pressure_mbar = utils.find_timestamped_values("P\s*(\+?\-?\d+)mbar", self.log_content)

        # Retain date of (first if multiple(?)) "DIVING" (else set to None)
        for d in complete_dive:
            self.descent_leave_surface_date = d.descent_leave_surface_date
            if self.descent_leave_surface_date is not None:
                break

        self.gps_before_dive = [x for x in self.gps_list if x.date < self.descent_leave_surface_date]

        # Retain date of (last if multiple(?)) "SURFIN" (else set to None)
        for d in reversed(complete_dive):
            self.ascent_reach_surface_date = d.ascent_reach_surface_date
            if self.ascent_reach_surface_date is not None:
                break

        self.gps_after_dive = [x for x in self.gps_list if x.date > self.ascent_reach_surface_date]

        self.events = utils.flattenList([d.events for d in complete_dive])

        # Retain most recent external pressure measurement
        for d in reversed(complete_dive):
            self.p2t_offset_param = d.p2t_offset_param
            self.p2t_offset_measurement = d.p2t_offset_measurement
            self.p2t_offset_corrected = d.p2t_offset_corrected
            if d.p2t_offset_corrected is not None:
                break

    def set_incl_prev_next_dive_gps(self, prev_dive=None, next_dive=None):
        '''Expands a dive's GPS list to include GPS fixes before/after it by inspecting
        the previous/next dive's GPS list.

        '''

        # Shallow copy lists so the copy may be extended w/o also extending original
        self.gps_before_dive_incl_prev_dive = list(self.gps_before_dive)
        self.gps_after_dive_incl_next_dive = list(self.gps_after_dive)

        # Add the previous dive's GPS fixes AFTER the previous dive reached the surface
        if self.descent_leave_surface_date and prev_dive and prev_dive.gps_list:
            self.gps_before_dive_incl_prev_dive += prev_dive.gps_after_dive

        # Add the next dive's GPS fixes BEFORE the next dive left the surface
        if self.ascent_reach_surface_date and  next_dive and next_dive.gps_list:
            self.gps_after_dive_incl_next_dive += next_dive.gps_before_dive

        # Ensure sorting of the expanded GPS lists
        self.gps_before_dive_incl_prev_dive.sort(key=lambda x: x.date)
        self.gps_after_dive_incl_next_dive.sort(key=lambda x: x.date)

    def validate_gps(self, num_gps=2, max_time=5400):
        """Returns true if valid GPS fixes exist to interpolate clock drifts and
        station locations at the time of recording events.

        Args:
        num_gps (int): Min. # GPS fixes before(after) diving(surfacing) (def=2)
        max_time (int): Max. time (s) before(after) diving(surfacing) within
                        which `num_gps` must be  recorded (def=3600)

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

        if self.gps_before_dive_incl_prev_dive:
            gps_before = self.gps_before_dive_incl_prev_dive
        else:
            return

        if self.gps_after_dive_incl_next_dive:
            gps_after = self.gps_after_dive_incl_next_dive
        else:
            return

        # Ensure MERMAID clock synchronized with last(first) GPS before(after) diving(surfacing)
        # (this also handles the case of verifying `gps.mer_time_log_loc` if `num_gps=1`)
        if gps.valid_clockfreq(gps_before[-1]) \
           and gps_before[-1].mer_time_log_loc() \
           and gps_before[-1].clockdrift < 5 \
           and gps.valid_clockfreq(gps_after[0]) \
           and gps_after[0].mer_time_log_loc() \
           and gps_after[0].clockdrift < 5:

           self.gps_valid4clockdrift_correction = True

        else:
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
                return

            # Ensure the required number of valid GPS exist within the required
            # time after surfacing
            count = 0
            for ga in gps_after:
                tdiff = ga.date - self.ascent_reach_surface_date
                if tdiff < max_time:
                    count += 1

            if count < num_gps:
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
            event.correct_clockdrift(self.gps_before_dive_incl_prev_dive[-1],
                                     self.gps_after_dive_incl_next_dive[0])

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
        appearing twice in any give complete dive; if multiple filenames appear
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
            # this complete dive.  This does not delete the events.Event object
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
        '''Fills attributes detailing interpolated locations of MERMAID at various
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
        self.descent_leave_surface_loc = gps.linear_interpolation(self.gps_before_dive_incl_prev_dive, \
                                                                  self.descent_leave_surface_date)

        # Find when & where the float reached the surface
        self.ascent_reach_surface_loc =  gps.linear_interpolation(self.gps_after_dive_incl_next_dive, \
                                                                  self.ascent_reach_surface_date)
        # Find pressure values
        pressure_date = [p[1] for p in self.pressure_mbar]

        # Convert pressure values from mbar to dbar
        # For our purposes it it fine to assume that 1 dbar = 1 m = 100 mbar
        # (NOT 1 m = 101 mbar as stated in MERMAID manual Réf : 452.000.852 Version 00)
        pressure_dbar = [int(p[0])/100. for p in self.pressure_mbar]

        # Compute location of events from surface position if MERMAID does not reach mixed layer
        # Recall that we assume 1 m of water = 1 dbar of pressure
        if max(pressure_dbar) > mixed_layer_depth_m:

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

            self.descent_leave_surface_layer_loc = gps.linear_interpolation(self.gps_before_dive_incl_prev_dive, \
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

            self.ascent_reach_surface_layer_loc = gps.linear_interpolation(self.gps_after_dive_incl_next_dive, \
                                                                           self.ascent_reach_surface_layer_date)

            #______________________________________________________________________________________#

            # MERMAID passed through the surface layer and into the mixed layer -- interpolate the
            # location of the recorded event assuming a multi-layer (surface and mixed) ocean
            self.descent_last_loc_before_event = self.descent_leave_surface_layer_loc
            self.ascent_first_loc_after_event = self.ascent_reach_surface_layer_loc

        else:
            # MERMAID never passed through the surface layer and into the mixed layer -- interpolate
            # the location of the recorded event assuming a single-layer ocean
            self.descent_last_loc_before_event = self.descent_leave_surface_loc
            self.ascent_first_loc_after_event = self.ascent_reach_surface_loc

        # Compute event locations between interpolated locations of exit and re-entry of surface waters
        for event in self.events:
            event.compute_station_location(self.descent_last_loc_before_event,
                                           self.ascent_first_loc_after_event)

    def attach_events_metadata(self):
        for event in self.events:
            if event.station_loc is not None:
                event.attach_obspy_trace_stats(self.kstnm, self.kinst)

    def generate_events_plotly(self):
        for event in self.events:
            event.plotly(self.processed_path)

    def generate_events_png(self):
        for event in self.events:
            event.plot_png(self.processed_path)

    def generate_events_sac(self):
        for event in self.events:
            event.to_sac(self.processed_path, self.kstnm, self.kinst)

    def generate_events_mseed(self):
        for event in self.events:
            event.to_mseed(self.processed_path, self.kstnm, self.kinst)

    def print_len(self):
        len_str  = "   Date: {:s} -> {:s} ({:.2f} days; first/last line of {:s}/{:s})" \
                   .format(str(self.start_date)[0:19], str(self.end_date)[0:19],
                           self.len_days, self.log_name[0], self.log_name[-1])
        print(len_str)
        return len_str + "\n"

    def print_log_mer_id(self):
        log_mer_str = ""
        for i,_ in enumerate(self.log_name):
            if self.dive_id[i] is None:
                id_str = "     ID: <none>"

            else:
                id_str = "     ID: #{:>5d}".format(self.dive_id[i])

            if self.log_name[i] and self.mer_environment_name[i]:
                tmp_str = "{:s} ({:s}, {:s})".format(id_str, self.log_name[i], self.mer_environment_name[i])

            elif self.log_name[i] and not self.mer_environment_name[i]:
                # For example, 16_5F9C20FC.MER, which would have been P-16 Dive
                # #120, and which was supposedly uploaded associated with
                # 16_5F92A09C.LOG, does not/never existed on the server (no idea
                # what happened)
                tmp_str = "{:s} ({:s}, <none>)".format(id_str, self.log_name[i])

            elif self.mer_environment_name[i] and not self.log_name[i]:
                tmp_str = "{:s} (<none>, {:s})".format(id_str, self.mer_environment_name[i])

            else:
                tmp_str = "(<none>, <none>)".format()

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
                if e.station_loc is None:
                    tmp_str = " Event: ! NOT MADE ! (invalid and/or not enough GPS fixes) {:s}.sac (</EVENT> binary in {:s})" \
                              .format(e.processed_file_name, e.mer_binary_name)

                else:
                    tmp_str = "  Event: {:s}.sac (</EVENT> binary in {:s})" \
                              .format(e.processed_file_name, e.mer_binary_name)
                print(tmp_str)
                evt_str += tmp_str + "\n"

        return evt_str

# Create dives object
def get_dives(path, events, begin, end):
    # Concatenate log files that need it
    concatenate_log_files(path)
    # Get the list of log files
    log_names = glob.glob(path + "*.LOG")
    log_names = [x.split("/")[-1] for x in log_names]
    log_names.sort()
    # Create Dive objects
    dives = list()
    for log_name in log_names:
        dives.append(Dive(path, log_name, events, begin, end))
    return dives


# Concatenate .000 files .LOG files in the path
def concatenate_log_files(path):
    log_files = list()
    extensions = ["000", "001", "002", "003", "004", "005", "LOG"]
    for extension in extensions:
        log_files += glob.glob(path + "*." + extension)
    log_files = [x.split("/")[-1] for x in log_files]
    log_files.sort()

    logstring = ""
    for log_file in log_files:
        # If log extension is a digit, fill the log string
        if log_file[-3:].isdigit():
            with open(path + log_file, "r") as fl:
                # We assume that files are sorted in a correct order
                logstring += fl.read()
            os.remove(path + log_file)
        else:
            if len(logstring) > 0:
                # If log extension is not a digit and the log string is not empty
                # we need to add it at the end of the file
                with open(path + log_file, "r") as fl:
                    logstring += fl.read()
                with open(path + log_file, "w") as fl:
                    fl.write(logstring)
                logstring = ""


def write_complete_dives_txt(complete_dives, creation_datestr, processed_path, mfloat_path, mfloat):
    '''Writes complete_dives.txt and prints the same info to stdout

    A complete dive is either: (1) wholly defined in a single .LOG file, or (2)
    a concatenation of many (fragmented/error/reboot/testmd) .LOG files that lie
    in-between single-.LOG complete dives

    Prints all data for every .LOG/.MER in the server; does not, e.g., only
    print info associated with those .LOG/.MER within datetime range of `main.py`

    '''

    complete_dives_file = os.path.join(processed_path, mfloat_path, "complete_dives.txt")
    version_line = "#automaid {} ({})\n".format(setup.get_version(), setup.get_url())
    created_line = "#created {}\n".format(creation_datestr)

    with open(complete_dives_file, "w+") as f:
        f.write(version_line)
        f.write(created_line)

        for d in sorted(complete_dives, key=lambda x: x.start_date):
            print("Complete Dive")
            f.write("Complete Dive\n")

            # These methods both return, and print to stdout, the same formatted string
            f.write(d.print_len())
            f.write(d.print_log_mer_id())
            f.write(d.print_events())

            print ""
            f.write("\n")

        # Determine the total number of SAC and/or miniSEED files that COULD be
        # written (but do not necessarily exists, e.g., if `events_sac=False` in
        # main.py).
        sac_str = "    {:s} total: {:d} (non-preliminary) SAC & miniSEED files\n".format(mfloat, \
                  len([e for d in complete_dives for e in d.events if e.station_loc and not e.station_loc_is_preliminary]))

        print(sac_str)
        f.write(sac_str)

def write_dives_txt(dive_logs, creation_datestr, processed_path, mfloat_path):
    '''Writes dives.txt, which treats every .LOG as a single (possibly incomplete) dive

    Prints all data for every .LOG/.MER in the server; does not, e.g., only
    print info associated with those .LOG/.MER within datetime range of  `main.py`

    '''

    dives_file = os.path.join(processed_path, mfloat_path, "dives.txt")
    fmt_spec = "{:>8s}    {:>20s}    {:>20s}    {:>10d}    {:>9.3f}    {:>15s}    {:>15s}\n"

    version_line = "#automaid {} ({})\n".format(setup.get_version(), setup.get_url())
    created_line = "#created {}\n".format(creation_datestr)
    header_line = "#dive_id               log_start                 log_end      len_secs     len_days           log_name       mer_env_name\n".format()

    with open(dives_file, "w+") as f:
        f.write(version_line)
        f.write(created_line)
	f.write(header_line)

        # 1 .LOG == 1 dive
        for d in sorted(dive_logs, key=lambda x: x.start_date):
            f.write(fmt_spec.format(str(d.dive_id),
                                    str(d.start_date)[:19] + 'Z',
                                    str(d.end_date)[:19] + 'Z',
                                    int(d.len_secs),
                                    d.len_days,
                                    d.log_name,
                                    d.mer_environment_name))

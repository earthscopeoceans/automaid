# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v2.7)
#
# Developer: Joel D. Simon (JDS)
# Original author: Sebastien Bonnieux
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified by JDS: 18-May-2021
# Last tested: Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit

import os
import re
import sys
import glob

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
        self.export_path = None
        self.station_name = None
        self.station_number = None
        self.kstnm = None
        self.kinst = None

        self.log_content = None
        self.start_date = None
        self.end_date = None
        self.len_secs = None
        self.len_days = None

        self.mer_environment_file_exists = False
        self.mer_environment_name = None
        self.mer_environment = None
        self.mer_bytes_received = None
        self.mer_bytes_expected = None

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

        self.is_init = False
        self.is_dive = False
        self.is_complete_dive = False
        self.is_complete_mer_file = False
        self.dive_id = None

        self.prev_dive_log_name = None
        self.prev_dive_mer_environment_name = None

        self.next_dive_exists = False
        self.next_dive_log_name = None
        self.next_dive_mer_environment_name = None

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

        # Check if the .LOG is fragemented
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

        self.export_path = self.base_path + self.directory_name + "/"

        # Get the station name
        if self.is_dive or self.is_init:
            self.station_name = re.findall("board (.+)", utils.split_log_lines(self.log_content)[0])
            if len(self.station_name) == 0:
                self.station_name = re.findall("board (.+)", utils.split_log_lines(self.log_content)[1])
            self.station_name = self.station_name[0]
            self.station_number = self.station_name.split("-")[-1]

            # Zero-pad the (unique part) of the station name so that it is five characters long
            self.attach_kstnm_kinst()

        # Find the .MER file of the ascent
        catch = re.findall("bytes in (\w+/\w+\.MER)", self.log_content)
        if len(catch) > 0:
            self.mer_environment_name = catch[-1].replace("/", "_")
            mer_fullfile_name = self.base_path + self.mer_environment_name

            if os.path.exists(mer_fullfile_name):
                self.mer_environment_file_exists = True

        # If the dive wrote a .MER file then retrieve its corresponding environment because those
        # GPS fixes DO relate to start/end of the dive. HOWEVER, the events (data) actually
        # contained in that .MER file may correspond to a different dive (GPS fixes from a DIFFERENT
        # .LOG and .MER environment), thus we must "get_events_between" to correlate the actual
        # binary data in .MER files with their proper GPS fixes (usually the dates of the binary
        # events in the .MER file correspond to the .MER file itself, however if there are a lot of
        # events to send back corresponding to a single dive, it may take multiple surfacings to
        # finally transmit them all).
        if self.mer_environment_file_exists:
            # Verify that the number of bytes purported to be in the .MER file are actually in the
            # .MER file (the .LOG prints the expectation)
            bytes_expected = re.search("](\d+) bytes in " + self.mer_environment_name.replace("_", "/"), self.log_content)
            self.mer_bytes_expected = int(bytes_expected.group(1))

            self.mer_bytes_received = os.path.getsize(mer_fullfile_name)
            if self.mer_bytes_received == self.mer_bytes_expected:
                self.is_complete_mer_file = True

            # Warning if .MER transmission is incomplete
            # if not self.is_complete_mer_file:
                # print("WARNING: {:s} file transmission is incomplete" \
                #       .format(self.mer_environment_name))
                # print("         Expected {:>6d} bytes (according to {:s})\n         Received {:>6d} bytes"\
                #       .format(self.mer_bytes_expected, self.log_name, self.mer_bytes_received))

            # Read the Mermaid environment associated to the dive
            with open(mer_fullfile_name, "r") as f:
                content = f.read()
            self.mer_environment = re.findall("<ENVIRONMENT>.+</PARAMETERS>", content, re.DOTALL)[0]

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

        # For each event
        for event in self.events:
            # 1 Set the environment information
            event.set_environment(self.mer_environment_name, self.mer_environment)
            # 2 Find true sampling frequency
            event.find_measured_sampling_frequency()
            # 3 Compute starttime of event from the TRIG sample index
            event.correct_date()
            # 4 Invert wavelet transform of event
            event.invert_transform()

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

    # def __repr__(self):
    #     return "Dive('{}', '{}', {})".format(self.base_path, self.log_name, self.events)

    def generate_datetime_log(self):
        # Check if file exist
        export_path = self.export_path + self.log_name + ".h"
        if os.path.exists(export_path):
            return
        # Generate log with formatted date
        formatted_log = utils.format_log(self.log_content)
        # Write file
        with open(export_path, "w") as f:
            f.write(formatted_log)

    def generate_mermaid_environment_file(self):
        # Check if there is a Mermaid file
        if self.mer_environment_name is None or not self.mer_environment_file_exists:
            return

        # Check if file exist
        export_path = self.export_path + self.log_name + "." + self.mer_environment_name + ".env"
        if os.path.exists(export_path):
            return

        # Write file
        with open(export_path, "w") as f:
            f.write(self.mer_environment)

    def generate_dive_plotly(self):
        '''Generates a dive plot for a SINGLE .LOG file, which usually describes a
        complete dive, but not always. I.e., this does not plot a
        `Complete_Dive` instance, but rather generates a single plot for
        whatever is written to an individual .LOG file.

        '''

        # Check if file exist
        export_path = self.export_path + self.log_name[:-4] + '.html'
        if os.path.exists(export_path):
            return

        # If the float is not diving don't plot anything
        if not self.is_dive:
            return

        # Search pressure values
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
                    filename=export_path,
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

    def print_dive_gps(self):
        # Repeat printout for the previous dive, whose data affect the GPS interpolation of the
        # current dive
        if self.prev_dive_log_name is not None:
            if self.prev_dive_mer_environment_name is not None:
                print("    GPS: {:s} (</ENVIRONMENT>) & {:s} [prev dive]" \
                      .format(self.prev_dive_mer_environment_name, self.prev_dive_log_name))
            else:
                print("    GPS: {:s} [prev dive]".format(self.prev_dive_log_name))
        else:
            print("    GPS: (...no previous dive...)")

        # By definition 1 .LOG == 1 "dive," so there is always a .log file but
        # not necessarily an associated .MER (e.g., test or init I think?)
        if self.mer_environment_name is not None:
            print("         {:s} (</ENVIRONMENT>) & {:s} [this dive]" \
                  .format(self.mer_environment_name, self.log_name))
        else:
            print("         {:s} [this dive]".format(self.log_name))

        # Repeat printout for the following dive, whose data affect the gps
        # interpolation of the current dive
        if self.next_dive_exists:
            if self.next_dive_mer_environment_name is not None:
                print("         {:s} (</ENVIRONMENT>) & {:s} [next dive]" \
                      .format(self.next_dive_mer_environment_name, self.next_dive_log_name))
            else:
                print("         {:s} [next dive]".format(self.next_dive_log_name))
        else:
            print("         (...awaiting next_dive...)")

class Complete_Dive:
    '''

    '''

    # Class attribute to hold MERMAID "MH" FDSN network code
    network = utils.network()

    def __init__(self, complete_dive=None):
        flatten = lambda toplist: [item for sublist in toplist for item in sublist]

        self.log_name = [d.log_name for d in complete_dive]
        self.log_content = ''.join(d.log_content for d in complete_dive)
        self.mer_environment_name = [d.mer_environment_name for d in complete_dive]
        self.__version__ = complete_dive[-1].__version__

        self.start_date = complete_dive[0].start_date
        self.end_date = complete_dive[-1].end_date
        self.dive_id = [d.dive_id for d in complete_dive]

        if not (len(self.log_name) ==
                len(self.mer_environment_name) ==
                len(self.dive_id)):
            # This would surprise me and imply that something went wrong...
            from IPython import embed; embed()

        self.len_secs = self.end_date - self.start_date
        self.len_days = self.len_secs / (60*60*24.)

        self.station_name = complete_dive[-1].station_name
        self.station_number = complete_dive[-1].station_number
        self.kstnm = complete_dive[-1].kstnm
        self.kinst = complete_dive[-1].kinst

        # Might want to rename the directories into something more useful...
        self.base_path = complete_dive[-1].base_path
        self.directory_name = complete_dive[-1].directory_name
        self.export_path = complete_dive[-1].export_path
        # ...like this perhaps?
        self.base_path2 = complete_dive[-1].base_path
        self.directory_name2 = '{:s}_{:s}'.format(str(self.start_date)[:19], str(self.end_date)[:19])
        self.export_path2 = self.base_path2 + self.directory_name2 + "/"

        # The nonunique list may include redundant GPS fixes from fragmented .LOG
        # I.e., an error in the .LOG may result in the redundant printing of GPS
        # fixes over multiple files
        self.gps_nonunique_list = flatten([d.gps_nonunique_list for d in complete_dive])
        self.gps_nonunique_list = sorted(self.gps_nonunique_list, key=lambda x: x.date)

        # We must re-merge GPS pairs to find truly unique pairs within
        # "complete" dives due to the combination of possibly fragmented .LOG
        # and .MER files that print redundant GPS info that is unique to THAT
        # SPECIFIC file, but NOT unique to a "complete dive" constructed of
        # fragmented files
        self.gps_list = flatten([d.gps_list for d in complete_dive])
        self.gps_list = gps.merge_gps_list(self.gps_list)

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

        self.events = flatten([d.events for d in complete_dive])

        # Retain most recent external pressure measurement
        for d in reversed(complete_dive):
            self.p2t_offset_param = d.p2t_offset_param
            self.p2t_offset_measurement = d.p2t_offset_measurement
            self.p2t_offset_corrected = d.p2t_offset_corrected
            if d.p2t_offset_corrected is not None:
                break

        self.gps_valid4clockdrift_correction = None
        self.gps_valid4location_interp = None

        self.gps_before_dive_incl_prev_dive = None
        self.descent_leave_surface_loc = None
        self.descent_leave_surface_layer_date = None
        self.descent_leave_surface_layer_loc = None

        self.gps_after_dive_incl_next_dive = None
        self.ascent_reach_surface_loc = None
        self.ascent_reach_surface_layer_date = None
        self.ascent_reach_surface_layer_loc = None

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

    def validate_gps(self, num_gps=2, max_time=3600):
        """Returns true if valid GPS fixes exist to interpolate clock drifts and
        station locations at the time of recording events

        Args:
        num_gps (int): Min. # GPS fixes before/after dive (def=2)
        max_time (int): Max. time (s) before/after dive within which
                        `num_gps` are recorded (def=3600)

        Sets attrs:
        `gps_valid4clockdrift_correction`: True is good synchronization pre/post dive
        `gps_valid4location_interp`: True is GPS within requested inputs

        Note that the former may be True when the latter is not: the former is a
        softer requirement only that the last(first) before(after) diving
        contain a good onboard clock synchronization.

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

        # Ensure MERMAID clock synronized with first GPS after surfacing
        if gps.valid_clockfreq(gps_before[-1]) and gps.valid_clockfreq(gps_after[0]):
            self.gps_valid4clockdrift_correction = True
        else:
            return

        # Ensure the required number of GPS exist within the required time
        # before diving
        count = 0
        for g in reversed(gps_before):
            tdiff = self.descent_leave_surface_date - g.date
            if tdiff < max_time:
                count += 1
                if count == num_gps:
                    break
            else:
                return

        # Ensure the required number of GPS exist within the required time
        # after surfacing
        count = 0
        for g in gps_after:
            tdiff = g.date - self.ascent_reach_surface_date
            if tdiff < max_time:
                count += 1
                if count == num_gps:
                    break
            else:
                return

        # If here, all tests passed
        self.gps_valid4location_interp = True

        return

    def correct_clockdrift(self):
        if not self.gps_valid4clockdrift_correction:
            return

        # Correct clock drift
        for event in self.events:
            event.correct_clockdrift(self.gps_before_dive_incl_prev_dive[-1],
                                     self.gps_after_dive_incl_next_dive[0])

    def compute_station_locations(self, mixed_layer_depth_m, preliminary_location_ok=False):
        '''Fills attributes detailing interpolated locations of MERMAID at various
        points during a Dive (i.e., when it left the surface, reached the mixed
        layer, etc.)

        '''

        # Require at least a single GPS point before and after each dive; after all, we only have
        # two points to interpolate for mixed-layer drift, which accounts for > 90% of the total
        # drift (despite the higher drift velocities at the surface, the total the surface-drift
        # components are generally not large because comparatively so little time is spent there --
        # see *gps_interpolation.txt for percentages)

        if not self.gps_valid4location_interp:
            if preliminary_location_ok:
                for event in self.events:
                    # Do not use `_incl_[prev/next]_dive` because the final Dive
                    # has no "next" dive, yet, and hackily assigning it one with
                    # `mdives[i].set_incl_prev_next_dive_gps(mdives[i-1], None)`
                    # in main.py can set `self.valid_event_gps()` to True, when
                    # it's really false causing this entire conditional to be
                    # skipped, and generating a non-'prelim.sac', which is bad

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
        pressure = utils.find_timestamped_values("P\s*(\+?\-?\d+)mbar", self.log_content)
        pressure_date = [p[1] for p in pressure]

        # Convert pressure values from mbar to m (really, this converts to dbar,
        # but 1 bar ~= 1 m)
        pressure_val = [int(p[0])/100. for p in pressure]

        # Compute location of events from surface position if MERMAID does not reach mixed layer
        if max(pressure_val) > mixed_layer_depth_m:

            # Interpolate for location that MERMAID passed from the surface layer to the mixed layer
            # on the descent

            # Loop through pressure readings until we've exited surface layer and passed into the
            # mixed layer -- this assumes we don't bob in and out of the mixed layer, and it only
            # retains the date of the first crossing
            i = 0
            while pressure_val[i] < mixed_layer_depth_m and i < len(pressure_val):
                i += 1

            descent_date_in_mixed_layer = pressure_date[i]
            descent_depth_in_mixed_layer = pressure_val[i]

            if i > 0:
                descent_date_in_surface_layer = pressure_date[i-1]
                descent_depth_in_surface_layer = pressure_val[i-1]
            else:
                # On the descent: we have pressure readings in the mixed layer but not in the
                # surface layer -- just interpolate using the last-known (diving) location
                descent_date_in_surface_layer = self.descent_leave_surface_date
                descent_depth_in_surface_layer = 0

            # Compute when the float leaves the surface and reaches the mixed layer
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
            i = len(pressure_val)-1
            while pressure_val[i] < mixed_layer_depth_m and i > 0:
                i -= 1

            ascent_date_in_mixed_layer = pressure_date[i]
            ascent_depth_in_mixed_layer = pressure_val[i]

            if i < len(pressure_val)-1:
                ascent_date_in_surface_layer = pressure_date[i+1]
                ascent_depth_in_surface_layer = pressure_val[i+1]
            else:
                # On the ascent: we have pressure readings in the mixed layer but not the surface
                # layer -- just interpolate using next-know (surfacing) location
                ascent_date_in_surface_layer = self.ascent_reach_surface_date
                ascent_depth_in_surface_layer = 0

            # Compute when the float leaves the mixed layer and reaches the surface (flipped
            # subtraction order so that ascent is velocity is positive)
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
            last_descent_loc_before_event = self.descent_leave_surface_layer_loc
            first_ascent_loc_after_event = self.ascent_reach_surface_layer_loc
        else:
            # MERMAID never passed through the surface layer and into the mixed layer -- interpolate
            # the location of the recorded event assuming a single-layer ocean
            last_descent_loc_before_event = self.descent_leave_surface_loc
            first_ascent_loc_after_event = self.ascent_reach_surface_loc

        # Compute event locations between interpolated locations of exit and re-entry of surface waters
        for event in self.events:
            event.compute_station_location(last_descent_loc_before_event, first_ascent_loc_after_event)

    def attach_events_metadata(self):
        for event in self.events:
            if event.station_loc is not None:
                event.attach_obspy_trace_stats(self.kstnm, self.kinst)

    def generate_events_plotly(self):
        for event in self.events:
            event.plotly(self.export_path)

    def generate_events_png(self):
        for event in self.events:
            event.plot_png(self.export_path)

    def generate_events_sac(self):
        for event in self.events:
            event.to_sac(self.export_path, self.kstnm, self.kinst)

    def generate_events_mseed(self):
        for event in self.events:
            event.to_mseed(self.export_path, self.kstnm, self.kinst)

    def print_len(self):
        print("   Date: {:s} -> {:s} ({:.2f} days; first/last line of {:s}/{:s})" \
              .format(str(self.start_date)[0:19], str(self.end_date)[0:19],
                      self.len_days, self.log_name[0], self.log_name[-1]))

    def print_log_mer_id(self):
        for i,_ in enumerate(self.log_name):
            if self.dive_id[i] is None:
                id_str = "     ID: <none>"

            else:
                id_str = "     ID: #{:>5d}".format(self.dive_id[i])

            if self.log_name[i] and self.mer_environment_name[i]:
                print("{:s} ({:s}, {:s})".format(id_str, self.log_name[i], self.mer_environment_name[i]))

            elif self.log_name[i] and not self.mer_environment_name[i]:
                # For example, 16_5F9C20FC.MER, which would have been P-16 Dive
                # #120, and which was supposedly uploaded associated with
                # 16_5F92A09C.LOG, does not/never existed on the server (no idea
                # what happened)
                print("{:s} ({:s}, <none>)".format(id_str, self.log_name[i]))

            elif self.mer_environment_name[i] and not self.log_name[i]:
                print("{:s} (<none>, {:s})".format(id_str, self.mer_environment_name[i]))

            else:
                print("(<none>, <none>)\n")

    def print_events(self):
        if not self.events:
            print("  Event: (no detected or requested events fall within the time window of this dive)")
        else:
            for e in self.events:
                if e.station_loc is None:
                    print("  Event: ! NOT MADE (not enough GPS fixes) {:s}.sac (</EVENT> binary in {:s})" \
                          .format(e.get_export_file_name(), e.mer_binary_name))
                else:
                    print("  Event: {:s}.sac (</EVENT> binary in {:s})" \
                          .format(e.get_export_file_name(), e.mer_binary_name))

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


def generate_printout(complete_dives, mfloat_serial):
    print ""
    for d in sorted(complete_dives, key=lambda x: x.start_date):
        print("Complete Dive")
        d.print_len()
        d.print_log_mer_id()
        d.print_events()
        print ""

    print("    {:s} total: {:d} (non-preliminary) SAC & miniSEED files\n" \
        .format(mfloat_serial, \
        sum(bool(e.station_loc) for d in complete_dives for e in d.events if not e.station_loc_is_preliminary)))


def write_dives_txt(mdives, processed_path, mfloat_path):
    dives_file = os.path.join(processed_path, mfloat_path, "dives.txt")
    fmt_spec = "{:>7s}    {:>20s}    {:>20s}    {:>7d}    {:>6.3f}    {:>15s}    {:>15s}\n"

    version_line = "automaid {} ({})\n\n".format(setup.get_version(), setup.get_url())
    header_line = "dive_id              dive_start                dive_end   len_secs  len_days           log_name       mer_env_name\n".format()

    with open(dives_file, "w+") as f:
        f.write(version_line)
	f.write(header_line)

        # 1 .LOG == 1 dive
        for d in sorted(mdives, key=lambda x: x.start_date):
            f.write(fmt_spec.format(str(d.dive_id),
                                    str(d.start_date)[:19] + 'Z',
                                    str(d.end_date)[:19] + 'Z',
                                    int(d.len_secs),
                                    d.len_days,
                                    d.log_name,
                                    d.mer_environment_name))

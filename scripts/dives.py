import glob
import os
import re
import plotly.graph_objs as graph
import plotly.offline as plotly
import utils
from obspy import UTCDateTime
import gps


# Log class to manipulate log files
class Dive:
    log_name = None
    base_path = None
    directory_name = None
    export_path = None
    date = None
    end_date = None
    is_init = None
    is_dive = None
    is_complete_dive = None
    log_content = None
    mmd_name = None
    mmd_environment = None
    events = None
    station_name = None
    station_number = None
    gps_list = None
    gps_list_is_complete = None
    surface_leave_loc = None
    surface_reach_loc = None
    great_depth_reach_loc = None
    great_depth_leave_loc = None
    p2t_offset_param = 0
    p2t_offset_measurement = 0

    def __init__(self, base_path, log_name, events):
        self.base_path = base_path
        self.log_name = log_name
        print log_name

        # Get the date from the file name
        self.date = utils.get_date_from_file_name(log_name)

        # Read the content of the LOG
        with open(self.base_path + self.log_name, "r") as f:
            self.log_content = f.read()

        # Get the last date
        print self.log_name
        ed = re.findall("(\d+):", utils.split_log_lines(self.log_content)[-1])[0]
        self.end_date = UTCDateTime(int(ed))

        # Check if the log correspond to the float initialization
        self.is_init = False
        match = re.search("\[TESTMD,\d{3}\]\"yes\"", self.log_content)
        if "Enter in test mode?" in self.log_content and not match:
            self.is_init = True

        # Check if the log correspond to a dive
        self.is_dive = False
        if "[DIVING," in self.log_content:
            self.is_dive = True

        # Check if the log correspond to a complete dive
        self.is_complete_dive = False
        if self.is_dive:
            catch = utils.find_timestamped_values("\[MAIN *, *\d+\]surface", self.log_content)
            if len(catch) > 0:
                self.is_complete_dive = True

        # Generate the directory name
        self.directory_name = self.date.strftime("%Y%m%d-%Hh%Mm%Ss")
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

        # Find the .MER file of the ascent
        catch = re.findall("bytes in (\w+/\w+\.MER)", self.log_content)
        if len(catch) > 0:
            self.mmd_name = catch[-1].replace("/", "_")

        # If the dive contain a Mermaid file
        self.events = list()
        if self.mmd_name:
            # Read the Mermaid environment associated to the dive
            with open(self.base_path + self.mmd_name, "r") as f:
                content = f.read()
            self.mmd_environment = re.findall("<ENVIRONMENT>.+</PARAMETERS>", content, re.DOTALL)[0]

            # Get list of events associated to the dive
            self.events = events.get_events_between(self.date, self.end_date)

            # For each event
            for event in self.events:
                # 1 Set the environment information
                event.set_environment(self.mmd_environment)
                # 2 Find true sampling frequency
                event.find_measured_sampling_frequency()
                # 3 Correct events date
                event.correct_date()
                # 4 Invert wavelet transform of event
                event.invert_transform()

        # Find the position of the float
        self.gps_list = gps.get_gps_list(self.log_content, self.mmd_environment, self.mmd_name)
        self.gps_list_is_complete = False
        if self.is_complete_dive:
            # Check that the last GPS fix of the list correspond to the ascent position
            surface_date = utils.find_timestamped_values("\[MAIN *, *\d+\]surface", self.log_content)
            surface_date = UTCDateTime(surface_date[0][1])
            if len(self.gps_list) == 0:
                print "WARNING: No GPS synchronization at all for \"" \
                        + str(self.mmd_name) + "\", \"" + str(self.log_name) + "\""
            elif len(self.gps_list) > 1 and self.gps_list[-1].date > surface_date:
                self.gps_list_is_complete = True
            elif self.gps_list[-1].date > surface_date:
                print "WARNING: No GPS synchronization before diving for \"" \
                        + str(self.mmd_name) + "\", \"" + str(self.log_name) + "\""
            else:
                print "WARNING: No GPS synchronization after surfacing for \"" \
                        + str(self.mmd_name) + "\", \"" + str(self.log_name) + "\""

        # Find the pressure offset
        if self.is_complete_dive:
            catch = re.findall("offset (-?\d+)mbar", self.log_content)
            self.p2t_offset_param = int(catch[0])
            catch = re.findall("Pext (-?\d+)mbar", self.log_content)
            self.p2t_offset_measurement = int(catch[0])

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
        if self.mmd_name is None:
            return
        # Check if file exist
        export_path = self.export_path + self.log_name + "." + self.mmd_name + ".env"
        if os.path.exists(export_path):
            return
        # Write file
        with open(export_path, "w") as f:
            f.write(self.mmd_environment)

    def generate_dive_plotly(self):
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

    def correct_events_clock_drift(self):
        # Return if there is no events
        if len(self.events) == 0:
            return

        # Compute clock drift
        if not self.is_dive:
            # print "WARNING: Events are not part of a dive, don't do clock drift correction for \""\
            #       + str(self.mmd_name) + "\", \"" + str(self.log_name) + "\""
            return
        if not self.is_complete_dive:
            print "WARNING: Events are not part of a complete dive, do not correct clock drift for \""\
                  + str(self.mmd_name) + "\", \"" + str(self.log_name) + "\""
            return
        if not self.gps_list_is_complete:
            print "WARNING: GPS list is incomplete, do not correct clock drift for \""\
                  + str(self.mmd_name) + "\", \"" + str(self.log_name) + "\""
            return
        if self.gps_list[-2].clockfreq <= 0:
            print "WARNING: Error with last gps synchronization before diving, do not correct clock drift for \""\
                  + str(self.mmd_name) + "\", \"" + str(self.log_name) + "\""
            return
        if self.gps_list[-1].clockfreq <= 0:
            print "WARNING: Error with first gps synchronization after ascent, do not correct clock drift for \""\
                  + str(self.mmd_name) + "\", \"" + str(self.log_name) + "\""
            return

        # Correct clock drift
        for event in self.events:
            event.correct_clock_drift(self.gps_list[-2], self.gps_list[-1])

    def compute_events_station_location(self, next_dive):
        # Check if the dive is complete
        if not self.is_complete_dive:
            # print "WARNING: The dive is not complete, do not compute event location estimation for \""\
            #       + str(self.mmd_name) + "\", \"" + str(self.log_name) + "\""
            return

        # Check if the dive contain enough gps fix
        if len(self.gps_list) <= 1:
            print "WARNING: The current dive doesn't contain enough GPS fix,""" \
                  + " do not compute event location estimation for \"" \
                  + str(self.mmd_name) + "\", \"" + str(self.log_name) + "\""
            return

        # Check if the next dive contain gps fix
        if len(next_dive.gps_list) <= 1:
            print "WARNING: The next dive doesn't contain enough GPS fix,""" \
                  + " do not compute event location estimation for \"" \
                  + str(self.mmd_name) + "\", \"" + str(self.log_name) + "\""
            return

        # Warning GPS list is incomplete, do not compute event location
        if not self.gps_list_is_complete:
            print "WARNING: GPS list is incomplete, do not compute event location for \""\
                  + str(self.mmd_name) + "\", \"" + str(self.log_name) + "\""
            return

        # Divide gps in two list
        gps_before_dive = self.gps_list[:-1]
        gps_after_dive = [self.gps_list[-1]] + next_dive.gps_list[:-1]

        # Find location when float leave the surface
        surface_leave_date = utils.find_timestamped_values("\[DIVING, *\d+\] *(\d+)mbar reached", self.log_content)
        surface_leave_date = surface_leave_date[0][1]
        self.surface_leave_loc = gps.linear_interpolation(gps_before_dive, surface_leave_date)

        # Find location when float reach the surface
        surface_reach_date = utils.find_timestamped_values("\[SURFIN, *\d+\]filling external bladder", self.log_content)
        surface_reach_date = surface_reach_date[-1][1]
        self.surface_reach_loc = gps.linear_interpolation(gps_after_dive, surface_reach_date)

        # Location is determined when the float reach the mixed layer depth
        mixed_layer_depth_m = 50

        # Find pressure values
        pressure = utils.find_timestamped_values("P\s*(\+?\-?\d+)mbar", self.log_content)
        pressure_date = [p[1] for p in pressure]
        pressure_val = [int(p[0])/100. for p in pressure]

        # Return if there is the max value doesn't reach the mixed layer depth
        if max(pressure_val) < mixed_layer_depth_m:
            # compute location of events from surface position
            for event in self.events:
                event.compute_station_location(self.surface_leave_loc, self.surface_reach_loc)
            return

        # loop until to reach a depth greater than mixed_layer_depth
        i = 0
        while pressure_val[i] < mixed_layer_depth_m and i < len(pressure_val):
            i += 1
        d2 = pressure_date[i]
        p2 = pressure_val[i]
        if i > 0:
            d1 = pressure_date[i-1]
            p1 = pressure_val[i-1]
        else:
            d1 = surface_leave_date
            p1 = 0

        # compute when the float pass under the mixed layer
        reach_great_depth_date = d1 + (mixed_layer_depth_m - p1) * (d2 - d1) / (p2 - p1)

        # loop until to reach a depth higher than mixed_layer_depth bur for in the ascent phase
        i = len(pressure_val)-1
        while pressure_val[i] < mixed_layer_depth_m and i > 0:
            i -= 1
        d1 = pressure_date[i]
        p1 = pressure_val[i]

        if i < len(pressure_val)-1:
            d2 = pressure_date[i+1]
            p2 = pressure_val[i+1]
        else:
            d2 = surface_reach_date
            p2 = 0

        # compute when the float pass above the mixed layer
        leave_great_depth_date = d1 + (mixed_layer_depth_m - p1) * (d2 - d1) / (p2 - p1)

        # compute location with linear interpolation
        self.great_depth_reach_loc = gps.linear_interpolation(gps_before_dive, reach_great_depth_date)
        self.great_depth_leave_loc = gps.linear_interpolation(gps_after_dive, leave_great_depth_date)

        # compute location of events
        for event in self.events:
            event.compute_station_location(self.great_depth_reach_loc, self.great_depth_leave_loc)

    def generate_events_plotly(self):
        for event in self.events:
            event.plotly(self.export_path)

    def generate_events_png(self):
        for event in self.events:
            event.plot_png(self.export_path)

    def generate_events_sac(self):
        for event in self.events:
            event.to_sac(self.export_path, self.station_number, force_without_loc=False)

    def generate_events_mseed(self):
        for event in self.events:
            event.to_mseed(self.export_path, self.station_number, force_without_loc=False)


# Create dives object
def get_dives(path, events):
    # Concatenate log files that need it
    concatenate_log_files(path)
    # Get the list of log files
    log_names = glob.glob(path + "*.LOG")
    log_names = [x.split("/")[-1] for x in log_names]
    log_names.sort()
    # Create Dive objects
    dives = list()
    for log_name in log_names:
        dives.append(Dive(path, log_name, events))
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

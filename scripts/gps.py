# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v2.7)
#
# Original author: Sebastien Bonnieux
# Current maintainer: Joel D. Simon (JDS)
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified by JDS: 30-Oct-2020, Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit

import re
import setup
from obspy import UTCDateTime
from obspy.geodetics.base import gps2dist_azimuth
import os
from pprint import pprint
from pdb import set_trace as keyboard

# Get current version number.
version = setup.get_version()

class GPS:
    def __init__(self, date=None, latitude=None, longitude=None, clockdrift=None, clockfreq=None,
                 hdop=None, vdop=None, source=None, interp_dict=None):
        self.date = date
        self.latitude = latitude
        self.longitude = longitude
        self.clockdrift = clockdrift
        self.clockfreq = clockfreq
        self.hdop = hdop
        self.vdop = vdop
        self.source = source
        self.interp_dict = interp_dict
        self.__version__ = version


    def __repr__(self):
        # I don't want to print the entire (large) interpolation dict
        if self.source == 'interpolated':
            rep = "GPS({}, {}, {}, {}, {}, {}, {}, '{}', <interp_dict>)" \
                  .format(repr(self.date), self.latitude, self.longitude, self.clockdrift,
                          self.clockfreq, self.hdop, self.vdop, self.source)
        else:
            rep = "GPS({}, {}, {}, {}, {}, {}, {}, '{}')" \
                  .format(repr(self.date), self.latitude, self.longitude, self.clockdrift,
                          self.clockfreq, self.hdop, self.vdop, self.source)
        return rep

def linear_interpolation(gps_list, date):
    # Check if date is equal to a gps fix
    for gps in gps_list:
        if date == gps.date:
            return gps

    # If date is before any gps fix compute drift from the two first gps fix
    if date < gps_list[0].date:
        # In this case: gps_list[i] is the FIRST GPS fix AFTER the interpolation date
        i = 0
        j = 1
        # Try to get a minimum time between two gps fix of 10 minutes
        while abs(gps_list[j].date - gps_list[i].date) < 10*60 and j < len(gps_list)-1:
            j += 1
        # Try to get a minimum distance between two gps fix of 20 meters
        while gps2dist_azimuth(gps_list[j].latitude, gps_list[j].longitude,
                               gps_list[i].latitude, gps_list[i].longitude)[0] < 20 and j < len(gps_list)-1:
            j += 1

    # If date is after any gps fix compute drift from the two last gps fix
    elif date > gps_list[-1].date:
        # In this case gps_list[i] is the LAST GPS fix BEFORE the interpolation date
        i = -1
        j = -2
        # Try to get a minimum time between two gps fix of 10 minutes
        while abs(gps_list[j].date - gps_list[i].date) < 10 * 60 and abs(j) < len(gps_list):
            j -= 1
        # Try to get a minimum distance between two gps fix of 20 meters
        while gps2dist_azimuth(gps_list[j].latitude, gps_list[j].longitude,
                               gps_list[i].latitude, gps_list[i].longitude)[0] < 20 and abs(j) < len(gps_list):
            j -= 1

    else:
        # If date is between two gps fix find the appropriate gps fix
        i = 0
        j = 1
        while not gps_list[i].date < date < gps_list[j].date and j < len(gps_list)-1:
            i += 1
            j += 1

    # If the distance between the two GPS points retained is less than 20 m, don't interpolate just pick one
    if gps2dist_azimuth(gps_list[j].latitude, gps_list[j].longitude, gps_list[i].latitude, gps_list[i].longitude)[0] < 20:
        input_drift_dist_m = None
        input_drift_time = None
        input_drift_vel_ms = None
        input_lat_drift_dist_deg = None
        input_lat_drift_vel_degs = None
        input_lon_drift_dist_deg = None
        input_lon_drift_vel_degs = None

        interp_drift_time = None
        interp_lat_drift_dist_deg = None
        interp_lat = gps_list[i].latitude
        interp_lon_drift_dist_deg = None
        interp_lon = gps_list[i].longitude
        interp_drift_dist_m = None
        interp_drift_vel_ms = None
    else:
        input_drift_dist_m = gps2dist_azimuth(gps_list[j].latitude, gps_list[j].longitude, \
                                            gps_list[i].latitude, gps_list[i].longitude)[0]
        input_drift_time = gps_list[j].date - gps_list[i].date
        input_drift_vel_ms = input_drift_dist_m / input_drift_time

        input_lat_drift_dist_deg = gps_list[j].latitude - gps_list[i].latitude
        input_lat_drift_vel_degs = input_lat_drift_dist_deg / input_drift_time

        # This is a bit of a cheat because it assumes an longitude lines are equally spaced on the
        # sphere, which they are not
        input_lon_drift_dist_deg = gps_list[j].longitude - gps_list[i].longitude
        input_lon_drift_vel_degs = input_lon_drift_dist_deg / input_drift_time

        interp_drift_time = date - gps_list[i].date
        interp_lat_drift_dist_deg = input_lat_drift_vel_degs * interp_drift_time
        interp_lat = gps_list[i].latitude + interp_lat_drift_dist_deg
        interp_lon_drift_dist_deg = input_lon_drift_vel_degs * interp_drift_time
        interp_lon = gps_list[i].longitude + interp_lon_drift_dist_deg

        # This is a bit of flub -- the interpolated drift distance computed here is using our (ever
        # so slightly) incorrect longitude, so when projected on a sphere we get a slightly
        # different distance than in our equal-box lat/lon projection; as such, the interpolated
        # drift velocity, which in reality must equal the drift velocity computed from the input,
        # will be slightly different
        interp_drift_dist_m = gps2dist_azimuth(interp_lat, interp_lon, gps_list[i].latitude, gps_list[i].longitude)[0]
        interp_drift_vel_ms = interp_drift_dist_m / interp_drift_time

    # Throw all local variables into dictionary so that I may later reference
    # these interpolation parameters -- this is not ideal because it creates
    # redundant records...preferrably interpolation would be its own Class
    interp_dict = locals()

    # Nicety: >>> from pprint import pprint
    #         >>> pprint(interp_dict)

    return GPS(date, interp_lat, interp_lon, None, None, None, None,
               "interpolated", interp_dict)


# Find GPS fix in log files and Mermaid files
def get_gps_list(log_name, log_content, mer_environment_name, mer_environment):
    gps_from_log = get_gps_from_log_content(log_name, log_content)
    gps_from_mer_environment = get_gps_from_mer_environment(mer_environment_name, mer_environment)

    # Concatenate GPS lists
    gps_list = gps_from_log + gps_from_mer_environment

    # Order based on date
    gps_list = sorted(gps_list, key=lambda x: x.date)

    return gps_list, gps_from_log, gps_from_mer_environment


def get_gps_from_mer_environment(mer_environment_name, mer_environment):
    gps = list()

    # Mermaid environment can be empty
    if mer_environment is None:
        return gps

    # get gps information in the mermaid environment
    gps_tag_list = mer_environment.split("</ENVIRONMENT>")[0].split("<GPSINFO")[1:]
    for gps_tag in gps_tag_list:
        fixdate = re.findall(" DATE=(\d+-\d+-\d+T\d+:\d+:\d+)", gps_tag)
        if len(fixdate) > 0:
            fixdate = fixdate[0]
            fixdate = UTCDateTime(fixdate)
        else:
            fixdate = None

        latitude = re.findall(" LAT=([+,-])(\d{2})(\d+\.\d+)", gps_tag)
        if len(latitude) > 0:
            latitude = latitude[0]
            if latitude[0] == "+":
                sign = 1
            elif latitude[0] == "-":
                sign = -1
            latitude = sign*(float(latitude[1]) + float(latitude[2])/60.)
        else:
            latitude = None

        longitude = re.findall(" LON=([+,-])(\d{3})(\d+\.\d+)", gps_tag)
        if len(longitude) > 0:
            longitude = longitude[0]
            if longitude[0] == "+":
                sign = 1
            elif longitude[0] == "-":
                sign = -1
            longitude = sign*(float(longitude[1]) + float(longitude[2])/60.)
        else:
            longitude = None

        clockdrift = re.findall("<DRIFT( [^>]+) />", gps_tag)
        if len(clockdrift) > 0:
            clockdrift = clockdrift[0]
            _df = 0
            catch = re.findall(" USEC=(-?\d+)", clockdrift)
            if catch:
                _df += 10 ** (-6) * float(catch[0])
            catch = re.findall(" SEC=(-?\d+)", clockdrift)
            if catch:
                _df += float(catch[0])
            catch = re.findall(" MIN=(-?\d+)", clockdrift)
            if catch:
                _df += 60 * float(catch[0])
            catch = re.findall(" HOUR=(-?\d+)", clockdrift)
            if catch:
                _df += 60 * 60 * float(catch[0])
            catch = re.findall(" DAY=(-?\d+)", clockdrift)
            if catch:
                _df += 24 * 60 * 60 * float(catch[0])
            catch = re.findall(" MONTH=(-?\d+)", clockdrift)
            if catch:
                # An approximation of 30 days per month is sufficient this is just to see if there is something
                # wrong with the drift
                _df += 30 * 24 * 60 * 60 * float(catch[0])
            catch = re.findall(" YEAR=(-?\d+)", clockdrift)
            if catch:
                _df += 365 * 24 * 60 * 60 * float(catch[0])
            clockdrift = _df
        else:
            clockdrift = None

        clockfreq = re.findall("<CLOCK Hz=(-?\d+)", gps_tag)
        if len(clockfreq) > 0:
            clockfreq = clockfreq[0]
            clockfreq = int(clockfreq)
        else:
            clockfreq = None

        # Check if there is an error of clock synchronization
        # if clockfreq <= 0:
            # err_msg = "WARNING: Error with clock synchronization in file \"" + mer_environment_name + "\"" \
            #        + " at " + fixdate.isoformat() + ", clockfreq = " + str(clockfreq) + "Hz"
            # print err_msg

        # .MER files do not include hdop or vdop.
        hdop = None
        vdop = None

        # Add date to the list
        if fixdate is not None and latitude is not None and longitude is not None \
                and clockdrift is not None and clockfreq is not None:
            gps.append(GPS(fixdate, latitude, longitude, clockdrift, clockfreq, hdop, vdop, mer_environment_name))
        else:
            raise ValueError

    return gps


def get_gps_from_log_content(log_name, log_content):
    gps = list()

    gps_log_list = log_content.split("GPS fix...")[1:]
    for gps_log in gps_log_list:
        # get gps information of each gps fix
        fixdate = re.findall("(\d+):\[MRMAID *, *\d+\]\$GPSACK", gps_log)
        if len(fixdate) > 0:
            fixdate = fixdate[0]
            fixdate = UTCDateTime(int(fixdate))
        else:
            fixdate = None

        latitude = re.findall("([S,N])(\d+)deg(\d+.\d+)mn", gps_log)
        if len(latitude) > 0:
            latitude = latitude[0]
            if latitude[0] == "N":
                sign = 1
            elif latitude[0] == "S":
                sign = -1
            latitude = sign*(float(latitude[1]) + float(latitude[2])/60.)
        else:
            latitude = None

        longitude = re.findall("([E,W])(\d+)deg(\d+.\d+)mn", gps_log)
        if len(longitude) > 0:
            longitude = longitude[0]
            if longitude[0] == "E":
                sign = 1
            elif longitude[0] == "W":
                sign = -1
            longitude = sign*(float(longitude[1]) + float(longitude[2])/60.)
        else:
            longitude = None

        clockdrift = re.findall("GPSACK:(.\d+),(.\d+),(.\d+),(.\d+),(.\d+),(.\d+),(.\d+)?;", gps_log)
        if len(clockdrift) > 0:
            clockdrift = clockdrift[0]
            # YEAR + MONTH + DAY + HOUR + MIN + SEC + USEC
            clockdrift = 365 * 24 * 60 * 60 * float(clockdrift[0]) \
                + 30 * 24 * 60 * 60 * float(clockdrift[1]) \
                + 24 * 60 * 60 * float(clockdrift[2]) \
                + 60 * 60 * float(clockdrift[3]) \
                + 60 * float(clockdrift[4]) \
                + float(clockdrift[5]) \
                + 10 ** (-6) * float(clockdrift[6])
        else:
            clockdrift = None

        clockfreq = re.findall("GPSOFF:(-?\d+);", gps_log)
        if len(clockfreq) > 0:
            clockfreq = clockfreq[0]
            clockfreq = int(clockfreq)
        else:
            clockfreq = None

        hdop = re.findall("hdop (\d+.\d+)", gps_log)
        if len(hdop) > 0:
            hdop = hdop[0]
            hdop = float(hdop)

        else:
            hdop = None

        vdop = re.findall("vdop (\d+.\d+)", gps_log)
        if len(vdop) > 0:
            vdop = vdop[0]
            vdop = float(vdop)

        else:
            vdop = None


        if fixdate is not None and latitude is not None and longitude is not None:
            gps.append(GPS(fixdate, latitude, longitude, clockdrift, clockfreq, hdop, vdop, log_name))

    return gps


def write_gps_txt(mdives, processed_path, mfloat_path, mfloat):
    gps_genexp = (gps for dive in mdives for gps in dive.gps_list)

    gps_fmt_spec = "{:>19s}    {:>10.6f}    {:>11.6f}    {:>6.3f}    {:>6.3f}    {:>17.6f}    {:>15s}\n"
    gps_file = os.path.join(processed_path, mfloat_path, mfloat+"_gps.txt")

    with open(gps_file, "w+") as f:
        f.write("            GPS_TIME       GPS_LAT        GPS_LON  GPS_HDOP  GPS_VDOP    GPS_TIME-MER_TIME             SOURCE\n".format())

        for g in sorted(gps_genexp, key=lambda x: x.date):
            if g.hdop is None:
                g.hdop = float("NaN")
            if g.vdop is None:
                g.vdop = float("NaN")

            f.write(gps_fmt_spec.format(str(g.date)[:19] + 'Z', g.latitude, g.longitude, g.hdop, g.vdop, g.clockdrift, g.source))


def write_gps_interpolation_txt(mdives, processed_path, mfloat_path, mfloat):
    # Define function to pull interpolation parameters out of the interpolation dictionary attached to each GPS instance
    def parse_interp_params(leg):
        if leg['input_drift_time'] is not None:
            params = [int(leg['input_drift_time']),
                      leg['input_drift_time'] / 60.0,
                      int(round(leg['input_drift_dist_m'])),
                      leg['input_drift_dist_m'] /1000,
                      leg['input_drift_vel_ms'],
                      leg['input_drift_vel_ms'] * 3.6, # km/hr
                      int(leg['interp_drift_time']),
                      leg['interp_drift_time'] / 60,
                      int(round(leg['interp_drift_dist_m'])),
                      leg['input_drift_dist_m']  / 1000,
                      leg['interp_drift_vel_ms'],
                      leg['interp_drift_vel_ms'] * 3.6]
            params = map(abs, params)
        else:
            # We used a single GPS point so all interpolation parameters are "None"
            params = [None] * 12

        return params

    def format_interp_params(leg):
        if leg['input_drift_time'] is not None:
            # Format for floats and ints -- do half the list then repeat
            fmt_spec = '{:>6d}        {:>7.1f}        {:>6d}        {:>4.1f}        {:>5.2f}        {:>7.2f}\n'

        else:
            # Format for null strings
            fmt_spec = '{:>6s}        {:>7s}        {:>6s}        {:>4s}        {:>5s}        {:>7s}\n'

        # Repeat format for interp parameters
        fmt_spec += fmt_spec

        return fmt_spec

    dive_event_tup = ((dive, event) for dive in mdives for event in dive.events if event.station_loc)

    gps_interp_file = os.path.join(processed_path, mfloat_path, mfloat+"_gps_interpolation.txt")
    with open(gps_interp_file, "w+") as f:
        f.write('TIME_S       TIME_MIN        DIST_M     DIST_KM      VEL_M/S      VEL_KM/HR\n')
        for dive, event in dive_event_tup:
            descent = dive.descent_leave_surface_loc.interp_dict
            drift = event.station_loc.interp_dict
            ascent = dive.ascent_reach_surface_loc.interp_dict

            interp_params = []
            interp_fmt_spec = ''
            for leg in descent, drift, ascent:
                # Nicety: pprint(leg)
                interp_params += parse_interp_params(leg)
                interp_fmt_spec += format_interp_params(leg)

            # Add an extra line between each dive block
            interp_fmt_spec += '\n'

            f.write(interp_fmt_spec.format(*interp_params))


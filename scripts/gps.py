# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v2.7)
#
# Original author: Sebastien Bonnieux
# Current maintainer: Joel D. Simon (JDS)
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified by JDS: 09-Nov-2020, Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit

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
                 hdop=None, vdop=None, source=None, rawstr_dict=None, interp_dict=None):
        self.date = date
        self.latitude = latitude
        self.longitude = longitude
        self.clockdrift = clockdrift
        self.clockfreq = clockfreq
        self.hdop = hdop
        self.vdop = vdop
        self.source = source
        self.rawstr_dict = rawstr_dict # Raw strings from .LOG and .MER files
        self.interp_dict = interp_dict # Interpolation parameters from linear_interpolation()
        self.__version__ = version


    def __repr__(self):
        if self.source == 'interpolated':
            # I don't want to print the entire (large) interpolation dict
            rep = "GPS({}, {}, {}, {}, {}, {}, {}, '{}', None, <interp_dict>)" \
                  .format(repr(self.date), self.latitude, self.longitude, self.clockdrift,
                          self.clockfreq, self.hdop, self.vdop, self.source)
        else:
            rep = "GPS({}, {}, {}, {}, {}, {}, {}, '{}', {})" \
                  .format(repr(self.date), self.latitude, self.longitude, self.clockdrift,
                          self.clockfreq, self.hdop, self.vdop, self.source, self.rawstr_dict)
        return rep

    def __len__(self):
        # To check if a single GPS instance passed into something that expects a list
        return 1

def linear_interpolation(gps_list, date):
    '''linear_interpolation(gps_list, date)

    Attempts to interpolate for the location of MERMAID at the requested date given an input list of
    GPS instances.  If a single GPS instance is give as input, interpolation cannot be performed and
    the input is returned (the interpolation is fixed to the input).

    Only two GPS instances from the input GPS list are retained for interpolation, and, if possible
    this method retains only the first two GPS instances that are separated by more than 10 minutes.
    If the two retained locations are within 20 m of one another interpolation is not performed and
    the interpolated location is fixed to an input.

    The interpolation dictionary, ".interp_dict", attached to each instance attempts to explain the
    outcome of this method.

    '''

    # Defaults for the interpolation dictionary to be attached to this GPS instance
    i = None
    j = None

    # "input" -- difference between first and last locations retained (which may not even be actual
    # GPS fixes in the cases when the input is already an interpolated point)
    input_drift_dist_m = None
    input_drift_time = None
    input_drift_vel_ms = None
    input_lat_drift_dist_deg = None
    input_lat_drift_vel_degs = None
    input_lon_drift_dist_deg = None
    input_lon_drift_vel_degs = None

    # "interp" -- difference between nearest/reference GPS point and interpolation point
    interp_drift_dist_m = None
    interp_drift_time = None
    interp_drift_vel_ms = None
    interp_lat_drift_dist_deg = None
    interp_lat_drift_vel_degs = None
    interp_lon_drift_dist_deg = None
    interp_lon_drift_vel_degs = None

    # Return prematurely if the GPS list is not a list
    if len(gps_list) == 1:
        interp_lat = gps_list.latitude
        interp_lon = gps_list.longitude
        description = "interpolation not attempted (GPS list of length 1)"

        if date == gps_list.date:
            # Set time and drift distances to 0; leave velocities undefined
            input_drift_dist_m = 0.0
            input_drift_time = 0.0
            input_lat_drift_dist_deg = 0.0
            input_lon_drift_dist_deg = 0.0

            interp_drift_dist_m = 0.0
            interp_drift_time = 0.0
            interp_lat_drift_dist_deg = 0.0
            interp_lon_drift_dist_deg = 0.0
            description = description + "; interpolation not required (interpolation date is gps_list.date)"

        else:
            description = description + "; interpolation fixed to input gps_list"

        interp_dict = locals()

        return GPS(date, interp_lat, interp_lon, None, None, None, None, "interpolated", None, interp_dict)

    # Return prematurely if the requested date is included in the GPS list
    for gps in gps_list:
        if date == gps.date:
            interp_lat = gps.latitude
            interp_lon = gps.longitude

            # Set time and drift distances to 0; leave velocities undefined
            input_drift_dist_m = 0.0
            input_drift_time = 0.0
            input_lat_drift_dist_deg = 0.0
            input_lon_drift_dist_deg = 0.0

            interp_drift_dist_m = 0.0
            interp_drift_time = 0.0
            interp_lat_drift_dist_deg = 0.0
            interp_lon_drift_dist_deg = 0.0
            description = "interpolation not required (interpolation date in gps_list)"

            interp_dict = locals()

            return GPS(date, interp_lat, interp_lon, None, None, None, None, "interpolated", None, interp_dict)

    # Otherwise, try to interpolate...

    # Ensure input list is sorted
    gps_list.sort(key=lambda x: x.date)

    # Identify the reference GPS points (gps_list[i]):
    # * last GPS before dive (descent)
    # * last interpolated location (i.e., when it leaves surface layer and crosses into mixed layer)
    #   before deep drift (mixed-layer drift; data acquisition phase)
    # * first GPS after dive (ascent)

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

    description= "interpolation attempted using multiple GPS points"

    # If the distance between the two GPS points retained is less than 20 m, don't interpolate just
    # pick one (also, if they are the same GPS point)
    if gps2dist_azimuth(gps_list[j].latitude, gps_list[j].longitude, gps_list[i].latitude, gps_list[i].longitude)[0] < 20:
        interp_lat = gps_list[i].latitude
        interp_lon = gps_list[i].longitude
        description = description + "; retained points too close for interpolation; interpolation fixed to one of gps_list"

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
        interp_lat_drift_vel_degs = input_lat_drift_vel_degs # they must equal
        interp_lat_drift_dist_deg = interp_lat_drift_vel_degs * interp_drift_time
        interp_lat = gps_list[i].latitude + interp_lat_drift_dist_deg

        interp_lon_drift_vel_degs = input_lon_drift_vel_degs # they must equal
        interp_lon_drift_dist_deg = interp_lon_drift_vel_degs * interp_drift_time
        interp_lon = gps_list[i].longitude + interp_lon_drift_dist_deg

        # This is also a bit of flub -- the interpolated drift distance computed here is using our
        # (ever so slightly) incorrect longitude, so when projected on a sphere we get a slightly
        # different distance than in our equal-box lat/lon projection; as such, the interpolated
        # drift velocity, which in reality must equal the drift velocity computed from the input,
        # will be slightly different
        interp_drift_dist_m = gps2dist_azimuth(interp_lat, interp_lon, gps_list[i].latitude, gps_list[i].longitude)[0]
        interp_drift_vel_ms = interp_drift_dist_m / interp_drift_time
        description = description + "; executed successfully"

    interp_dict = locals()

    # Nicety: >>> from pprint import pprint
    #         >>> pprint(interp_dict)

    return GPS(date, interp_lat, interp_lon, None, None, None, None, "interpolated", None, interp_dict)


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
    gps_mer_list = mer_environment.split("</ENVIRONMENT>")[0].split("<GPSINFO")[1:]
    for gps_mer in gps_mer_list:
        rawstr_dict = {'fixdate': None, 'latitude': None, 'longitude': None, 'clockdrift': None}

        fixdate = re.findall(" DATE=(\d+-\d+-\d+T\d+:\d+:\d+)", gps_mer)
        if len(fixdate) > 0:
            rawstr_dict['fixdate'] = re.search("DATE=(.*) LAT", gps_mer).group(1)
            fixdate = fixdate[0]
            rawstr_dict['fixdate'] = fixdate
            fixdate = UTCDateTime(fixdate)
        else:
            fixdate = None

        latitude = re.findall(" LAT=([+,-])(\d{2})(\d+\.\d+)", gps_mer)
        if len(latitude) > 0:
            rawstr_dict['latitude'] = re.search("LAT=(.*) LON", gps_mer).group(1)
            latitude = latitude[0]
            if latitude[0] == "+":
                sign = 1
            elif latitude[0] == "-":
                sign = -1
            latitude = sign*(float(latitude[1]) + float(latitude[2])/60.)
        else:
            latitude = None

        longitude = re.findall(" LON=([+,-])(\d{3})(\d+\.\d+)", gps_mer)
        if len(longitude) > 0:
            rawstr_dict['longitude'] = re.search("LON=(.*) />", gps_mer).group(1)
            longitude = longitude[0]
            if longitude[0] == "+":
                sign = 1
            elif longitude[0] == "-":
                sign = -1
            longitude = sign*(float(longitude[1]) + float(longitude[2])/60.)
        else:
            longitude = None

        # .MER clockdrifts are given as e.g.,
        # "<DRIFT YEAR=48 MONTH=7 DAY=4 HOUR=12 MIN=41 SEC=20 USEC=-563354 />"
        # which describe the drift using the sign convention of "drift = gps_time - mermaid_time"
        # (manual Ref: 452.000.852, pg. 32), NB: not all (any?) fields must exist (this is a
        # variable-length string); very often only USEC=*" will exist
        clockdrift = re.findall("<DRIFT( [^>]+) />", gps_mer)
        if len(clockdrift) > 0:
            rawstr_dict['clockdrift'] = re.search("<DRIFT (.*) />", gps_mer).group(1)
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

        clockfreq = re.findall("<CLOCK Hz=(-?\d+)", gps_mer)
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
            gps.append(GPS(fixdate, latitude, longitude, clockdrift, clockfreq, hdop, vdop, mer_environment_name, rawstr_dict))
        else:
            raise ValueError

    return gps


def get_gps_from_log_content(log_name, log_content):
    gps = list()

    gps_log_list = log_content.split("GPS fix...")[1:]
    for gps_log in gps_log_list:
        rawstr_dict = {'fixdate': None, 'latitude': None, 'longitude': None, 'clockdrift': None}

        # .LOG GPS times are given as integer UNIX Epoch times
        fixdate = re.findall("(\d+):\[MRMAID *, *\d+\]\$GPSACK", gps_log)
        if len(fixdate) > 0:
            fixdate = fixdate[0]
            rawstr_dict['fixdate'] = fixdate
            fixdate = UTCDateTime(int(fixdate))
        else:
            fixdate = None

        # .LOG latitudes are given as e.g., "S22deg33.978mn" (degrees and decimal minutes)
        latitude = re.findall("([S,N])(\d+)deg(\d+.\d+)mn", gps_log)
        if len(latitude) > 0:
            rawstr_dict['latitude'] = re.search("[S,N][0-9]+deg[0-9]+\.[0-9]+mn", gps_log).group(0)
            latitude = latitude[0]
            if latitude[0] == "N":
                sign = 1
            elif latitude[0] == "S":
                sign = -1
            latitude = sign*(float(latitude[1]) + float(latitude[2])/60.)
        else:
            latitude = None

        # .LOG latitudes are given as e.g., "W141deg22.679mn" (degrees and decimal minutes)
        longitude = re.findall("([E,W])(\d+)deg(\d+.\d+)mn", gps_log)
        if len(longitude) > 0:
            rawstr_dict['longitude'] = re.search("[E,W][0-9]+deg[0-9]+\.[0-9]+mn", gps_log).group(0)
            longitude = longitude[0]
            if longitude[0] == "E":
                sign = 1
            elif longitude[0] == "W":
                sign = -1
            longitude = sign*(float(longitude[1]) + float(longitude[2])/60.)
        else:
            longitude = None

        # .LOG clockdrifts are given as e.g., "$GPSACK:+48,+7,+4,+12,+41,+20,-563354;" which
        # describe the drift in terms of "year,month,day,hour,min,sec,usec" (manual Ref:
        # 452.000.852, pg. 16) where the sign convention is "drift = gps_time - mermaid_time"
        # (pg. 32), there describing the .MER environment, but it must be the same for the .LOG
        clockdrift = re.findall("GPSACK:(.\d+),(.\d+),(.\d+),(.\d+),(.\d+),(.\d+),(.\d+)?;", gps_log)
        if len(clockdrift) > 0:
            clockdrift = clockdrift[0]
            rawstr_dict['clockdrift'] = re.search("GPSACK:(.\d+,.\d+,.\d+,.\d+,.\d+,.\d+,.\d+)?;", gps_log).group(1)
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
            gps.append(GPS(fixdate, latitude, longitude, clockdrift, clockfreq, hdop, vdop, log_name, rawstr_dict))

    return gps


def write_gps_txt(mdives, processed_path, mfloat_path):
    gps_genexp = (gps for dive in mdives for gps in dive.gps_list)

    gps_fmt_spec = "{:>19s}    {:>10.6f}    {:>11.6f}    {:>6.3f}    {:>6.3f}    {:>17.6f}  |  {:>15s}    {:>3s} {:<7s}    {:>4s} {:<7s}\n"
    gps_file = os.path.join(processed_path, mfloat_path, "gps.txt")

    with open(gps_file, "w+") as f:
        f.write("automaid {} ({})\n\n".format(setup.get_version(), setup.get_url()))
        f.write("            GPS_TIME       GPS_LAT        GPS_LON  GPS_HDOP  GPS_VDOP    GPS_TIME-MER_TIME  |           SOURCE  LAT(deg min)    LON(deg min)\n".format())

        for g in sorted(gps_genexp, key=lambda x: x.date):
            if g.hdop is None:
                g.hdop = float("NaN")
            if g.vdop is None:
                g.vdop = float("NaN")

            # Parse and format the raw strings.
            raw_lat = g.rawstr_dict['latitude']
            raw_lon = g.rawstr_dict['longitude']

            if 'LOG' in g.source:
                raw_lat_deg, raw_lat_mn = raw_lat.split('deg')
                raw_lat_deg = raw_lat_deg.replace('N','+') if 'N' in raw_lat_deg else raw_lat_deg.replace('S','-')
                raw_lat_mn = raw_lat_mn.strip('mn')

                raw_lon_deg, raw_lon_mn = raw_lon.split('deg')
                raw_lon_deg = raw_lon_deg.replace('E','+') if 'E' in raw_lon_deg else raw_lon_deg.replace('W','-')
                raw_lon_mn = raw_lon_mn.strip('mn')

            else:
                raw_lat_deg = raw_lat[:3]
                raw_lat_mn = raw_lat[3:]

                raw_lon_deg = raw_lon[:4]
                raw_lon_mn = raw_lon[4:]

            f.write(gps_fmt_spec.format(str(g.date)[:19] + 'Z',
                                        g.latitude,
                                        g.longitude,
                                        g.hdop,
                                        g.vdop,
                                        g.clockdrift,
                                        g.source,
                                        raw_lat_deg,
                                        raw_lat_mn,
                                        raw_lon_deg,
                                        raw_lon_mn))


def write_gps_interpolation_txt(mdives, processed_path, mfloat_path):
    '''Writes MERMAID GPS interpolation file, detailing GPS and interpolation parameters for the three
    main regimes of each dive: descent and drift in the surface layer, drift in the mixed layer, and
    ascent and drift in the surface layer

    '''

    # NB, the comments here assume a normal dive where all GPS fixes are obtained and MERMAID dives
    # deeper than the mix layer depth; see especially dives.compute_station_locations and
    # gps.linear_interpolation to understand of edge-cases where perhaps some GPS fixes are missing
    # and/or MERMAID didn't dive into the mixed layer.  In all cases, GPS interpolation is still
    # broken into three regimes: descent drift, "deep" drift, and ascent drift.  Descent drift uses
    # the surface-drift velocity before the dive to interpolate forward in time for the location
    # where MERMAID dove into the mixed layer (left the surface layer); ascent drift uses the
    # surface-drift velocity after the dive to interpolate backward in time for the location where
    # MERMAID ascended into the surface layer (left the mixed layer); "deep" drift uses the velocity
    # of drift between those two points to estimate where MERMAID was when it recorded events while
    # drifting in the mixed layer.

    # "input" to gps.linear_interpolation are those GPS instances that we give the algorithm
    def parse_input_params(leg):
        input_params = [leg['input_drift_time']               if leg['input_drift_time'] else float("Nan"),
                        leg['input_drift_time'] / 60.0        if leg['input_drift_time'] else float("Nan"),
                        leg['input_drift_dist_m']             if leg['input_drift_dist_m'] else float("Nan"),
                        leg['input_drift_dist_m'] / 1000      if leg['input_drift_dist_m'] else float("Nan"),
                        leg['input_drift_vel_ms']             if leg['input_drift_vel_ms'] else float("Nan"),
                        leg['input_drift_vel_ms'] * 3.6       if leg['input_drift_vel_ms'] else float("Nan"), # km/hr
                        leg['input_drift_vel_ms'] * 3.6 * 24  if leg['input_drift_vel_ms'] else float("Nan")] #km/day

        input_params = map(abs, input_params)
        input_fmt_spec = '{:>6.0f}        {:>7.1f}        {:>6.0f}        {:>4.1f}        {:>5.2f}        {:>7.2f}        {:>7.2f}'
        return (input_params, input_fmt_spec)

    # "interp" from gps.linear_interpolation are those GPS instances the algorithm computes given
    # the input
    def parse_interp_params(leg):
        interp_params = [leg['interp_drift_time']              if leg['interp_drift_time'] else float("Nan"),
                        leg['interp_drift_time'] / 60.0        if leg['interp_drift_time'] else float("Nan"),
                        leg['interp_drift_dist_m']             if leg['interp_drift_dist_m'] else float("Nan"),
                        leg['interp_drift_dist_m'] / 1000      if leg['interp_drift_dist_m'] else float("Nan"),
                        leg['interp_drift_vel_ms']             if leg['interp_drift_vel_ms'] else float("Nan"),
                        leg['interp_drift_vel_ms'] * 3.6       if leg['interp_drift_vel_ms'] else float("Nan"), # km/hr
                        leg['interp_drift_vel_ms'] * 3.6 * 24  if leg['interp_drift_vel_ms'] else float("Nan")] #km/day

        interp_params = map(abs, interp_params)
        interp_fmt_spec = '{:>6.0f}        {:>7.1f}        {:>6.0f}        {:>4.1f}        {:>5.2f}        {:>7.2f}        {:>7.2f}'

        return (interp_params, interp_fmt_spec)


    # Generate (unique) list of dives with events whose interpolated locations we are able to compute
    dive_set = set(dive for dive in mdives for event in dive.events if event.station_loc)
    dive_list = list(dive_set)
    dive_list = sorted(dive_list, key=lambda x: x.start_date)

    # Print GPS interpolation information for every dive that includes an event all three dive regimes
    gps_interp_file = os.path.join(processed_path, mfloat_path, "gps_interpolation.txt")
    with open(gps_interp_file, "w+") as f:
        for dive in dive_list:
            # Write headers to each dive block
            f.write("DIVE ID: {:>4d}\n".format(dive.dive_id))
            f.write("DATES: {:>19s} --> {:19s}\n\n".format(str(dive.start_date)[:19] + 'Z', str(dive.end_date)[:19] + 'Z'))
            f.write("DRIFT_REGIME               TIME_S       TIME_MIN        DIST_M     DIST_KM      VEL_M/S      VEL_KM/HR     VEL_KM/DAY      DIST_%                                 SAC_MSEED_TRACE\n")


            # Compute the percentage of the total interpolate distance for the three regimes:
            # (1) surface-layer drift during the descent
            #
            # (2) mixed_layer drift
            #     .station.loc['interp_dist_m'] differs for each event  (drift to event in mixed layer)
            #     .station.loc['input_dist_m'] same for all events (total mixed-layer drift)
            #
            # (3) surface-layer drift during the ascent
            leg_descent = dive.descent_leave_surface_loc
            interp_dist_descent = leg_descent.interp_dict['interp_drift_dist_m']

            # Same for all event instances ('interp' distance to event is what differs)
            input_dist_mixed =  dive.events[0].station_loc.interp_dict['input_drift_dist_m']

            leg_ascent = dive.ascent_reach_surface_loc
            interp_dist_ascent = leg_ascent.interp_dict['interp_drift_dist_m']

            if all([interp_dist_descent, input_dist_mixed, interp_dist_ascent]):
                bad_interp = False
                total_interp_dist = sum([interp_dist_descent, input_dist_mixed, interp_dist_ascent])
                interp_perc_descent = (interp_dist_descent / total_interp_dist) * 100
                input_perc_mixed = (input_dist_mixed / total_interp_dist) * 100
                interp_perc_ascent = (interp_dist_ascent / total_interp_dist) * 100

            else:
                bad_interp = True
                interp_perc_descent = float("nan")
                input_perc_mixed = float("nan")
                interp_perc_ascent = float("nan")

            # Parse the GPS ('input') components of surface drift before dive: these are actual GPS points
            gps_surface_descent, gps_fmt_spec = parse_input_params(leg_descent.interp_dict)

            gps_fmt_spec = "gps_surface                " + gps_fmt_spec + "\n"
            f.write(gps_fmt_spec.format(*gps_surface_descent))

            # Parse the interpolated components of surface drift before dive: between last GPS point
            # and crossing into mixed layer
            interp_surface_descent, interp_fmt_spec = parse_interp_params(leg_descent.interp_dict)
            interp_surface_descent.append(interp_perc_descent)

            interp_fmt_spec = "interp_surface             " + interp_fmt_spec + "        {:>4.1f}\n"
            f.write(interp_fmt_spec.format(*interp_surface_descent))

            # For every event recorded during the dive: parse the interpolated components of the
            # mixed-layer drift from leaving the surface layer (passing into the "deep" or
            # mixed-layer drift regime) and recording an event
            for event in dive.events:
                interp_drift_to_event_mixed_layer, interp_fmt_spec = parse_interp_params(event.station_loc.interp_dict)
                interp_drift_to_event_mixed_layer.append(event.get_export_file_name())

                interp_fmt_spec = " interp_mixed(to_event)    " + interp_fmt_spec + "                    {:>40s}\n"
                f.write(interp_fmt_spec.format(*interp_drift_to_event_mixed_layer))

            # The total interpolated drift in the mixed layer -- that drift that occurs between the
            # last point of the ascent and the first point of the ascent -- is the same for every
            # event; just use the last event instance
            total_drift_mixed_layer, interp_fmt_spec = parse_input_params(dive.events[0].station_loc.interp_dict)
            total_drift_mixed_layer.append(input_perc_mixed)

            interp_fmt_spec = "interp_mixed               " + interp_fmt_spec + "        {:>4.1f}\n"
            f.write(interp_fmt_spec.format(*total_drift_mixed_layer))

            # Parse the interpolated components of surface drift after dive: crossing out of mixed
            # layer and recording first GPS point
            interp_surface_ascent, interp_fmt_spec = parse_interp_params(leg_ascent.interp_dict)
            interp_surface_ascent.append(interp_perc_ascent)

            interp_fmt_spec = "interp_surface             " + interp_fmt_spec + "        {:>4.1f}\n"
            f.write(interp_fmt_spec.format(*interp_surface_ascent))

            # Parse the GPS ('input') components of surface drift after dive: these are actual GPS points
            gps_surface_ascent, gps_fmt_spec = parse_input_params(leg_ascent.interp_dict)

            gps_fmt_spec = "gps_surface                " + gps_fmt_spec + "\n"
            f.write(gps_fmt_spec.format(*gps_surface_ascent))

            # If the interpolation failed, print some helpful statements at end of block
            if bad_interp:
                f.write('\n')
                if leg_descent.interp_dict['input_drift_dist_m'] is None:
                    f.write("*Interpolation issue before dive (surface-layer drift): {:s}\n" \
                            .format(leg_descent.interp_dict['description']))

                if dive.events[0].station_loc.interp_dict['input_drift_dist_m'] is None:
                    f.write("*Interpolation issue during dive (mixed-layer drift): {:s}\n" \
                            .format(dive.events[0].station_loc.interp_dict['description']))

                if leg_ascent.interp_dict['input_drift_dist_m'] is None:
                    f.write("*Interpolation issue after dive (surface-layer drift): {:s}\n" \
                            .format(leg_ascent.interp_dict['description']))

            f.write('\n__________END__________\n\n')

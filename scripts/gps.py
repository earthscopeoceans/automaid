# automaid v0.1.0
# pymaid environment (Python v2.7)
#
# Original author: Sebastien Bonnieux
#
# Current maintainer: Dr. Joel D. Simon (JDS)
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified by JDS: 08-Sep-2020, Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit

import re
from obspy import UTCDateTime
from obspy.geodetics.base import gps2dist_azimuth


class GPS:
    date = None
    latitude = None
    longitude = None
    clockdrift = None
    clockfreq = None
    source = None

    def __init__(self, date, latitude, longitude, clockdrift, clockfreq, source):
        self.date = date
        self.latitude = latitude
        self.longitude = longitude
        self.clockdrift = clockdrift
        self.clockfreq = clockfreq
        self.source = source


def linear_interpolation(gps_list, date):
    gpsl = gps_list

    # Check if date is equal to a gps fix
    for gps in gpsl:
        if date == gps.date:
            return gps

    if date < gpsl[0].date:
        # if date is before any gps fix compute drift from the two first gps fix
        i = 0
        j = 1
        # Try to get a minimum time between two gps fix of 10 minutes
        while abs(gpsl[j].date - gpsl[i].date) < 10 * 60 and j < len(gpsl)-1:
            j += 1
        # Try to get a minimum distance between two gps fix of 20 meters
        while gps2dist_azimuth(gpsl[j].latitude, gpsl[j].longitude,
                               gpsl[i].latitude, gpsl[i].longitude)[0] < 20 and j < len(gpsl)-1:
            j += 1

    elif date > gpsl[-1].date:
        # if date is after any gps fix compute drift from the two last gps fix
        i = -1
        j = -2
        # Try to get a minimum time between two gps fix of 10 minutes
        while abs(gpsl[j].date - gpsl[i].date) < 10 * 60 and abs(j) < len(gpsl):
            j -= 1
        # Try to get a minimum distance between two gps fix of 20 meters
        while gps2dist_azimuth(gpsl[j].latitude, gpsl[j].longitude,
                               gpsl[i].latitude, gpsl[i].longitude)[0] < 20 and abs(j) < len(gpsl):
            j -= 1

    else:
        # if date is between two gps fix find the appropriate gps fix
        i = 0
        j = 1
        while not gpsl[i].date < date < gpsl[j].date and j < len(gpsl)-1:
            i += 1
            j += 1

    # If distance between two GPS points is bellow 20 meter, don't do interpolation jut use a gps point
    if gps2dist_azimuth(gpsl[j].latitude, gpsl[j].longitude, gpsl[i].latitude, gpsl[i].longitude)[0] < 20:
        latitude = gpsl[i].latitude
        longitude = gpsl[i].longitude
    else:
        latitude = gpsl[i].latitude
        latitude += (date - gpsl[i].date) * (gpsl[j].latitude - gpsl[i].latitude) / (gpsl[j].date - gpsl[i].date)
        longitude = gpsl[i].longitude
        longitude += (date - gpsl[i].date) * (gpsl[j].longitude - gpsl[i].longitude) / (gpsl[j].date - gpsl[i].date)

    return GPS(date, latitude, longitude, None, None, "interpolated")


# Find GPS fix in log files and Mermaid files
def get_gps_list(log_content, mmd_environment_content, mmd_name):

    gps_from_log = get_gps_from_log(log_content)
    gps_from_mmd_env = get_gps_from_mermaid_environment(mmd_name, mmd_environment_content)

    gpslist = list()
    for gps_log in gps_from_log:
        # Use GPS from Mermaid environment by default but if the gps doesn't
        # exist in mermaid environment use the gps from log
        cached = False
        for gps_mmd in gps_from_mmd_env:
            if gps_mmd.date - 60 < gps_log.date < gps_mmd.date + 60:
                gpslist.append(gps_mmd)
                cached = True
        if not cached:
            gpslist.append(gps_log)

    return gpslist


def get_gps_from_mermaid_environment(mmd_name, content):
    gps = list()

    # Mermaid environment can be empty
    if content is None:
        return gps

    # get gps information in the mermaid environment
    gps_tag_list = content.split("</ENVIRONMENT>")[0].split("<GPSINFO")[1:]
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
        if clockfreq <= 0:
            err_msg = "WARNING: Error with clock synchronization in file \"" + mmd_name + "\"" \
                   + " at " + fixdate.isoformat() + ", clockfreq = " + str(clockfreq) + "Hz"
            print err_msg

        # Add date to the list
        if fixdate is not None and latitude is not None and longitude is not None \
                and clockdrift is not None and clockfreq is not None:
            gps.append(GPS(fixdate, latitude, longitude, clockdrift, clockfreq, "mer"))
        else:
            raise ValueError

    return gps


def get_gps_from_log(content):
    gps = list()

    gps_log_list = content.split("GPS fix...")[1:]
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

        if fixdate is not None and latitude is not None and longitude is not None:
            gps.append(GPS(fixdate, latitude, longitude, clockdrift, clockfreq, "log"))

    return gps

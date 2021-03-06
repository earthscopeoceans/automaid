# -*-coding:Utf-8 -*
#
# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v2.7)
#
# Original author: Sebastien Bonnieux
# Current maintainer: Joel D. Simon (JDS)
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified by JDS: 17-Dec-2020, Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit

import setup
import re
import warnings
from obspy import UTCDateTime
import plotly.graph_objs as graph

# Get current version number.
version = setup.get_version()

#
# Log files utilities
#

# Split logs in several lines
def split_log_lines(content):
    splitted = []
    if "\r\n" in content:
        splitted = content.split("\r\n")
    elif "\r" in content:
        splitted = content.split("\r")
    elif "\n" in content:
        splitted = content.split("\n")
    if splitted[-1] == "":
        splitted = splitted[:-1]
    return splitted


# Search timestamps for a specific keyword
def find_timestamped_values(regexp, content):
    timestamped_values = list()
    lines = split_log_lines(content)
    for line in lines:
        value_catch = re.findall(regexp, line)
        timestamp_catch = re.findall("(\d+):", line)
        if len(value_catch) > 0:
            v = value_catch[0]
            d = UTCDateTime(int(timestamp_catch[0]))
            timestamped_values.append([v, d])
    return timestamped_values


# Format log files
def format_log(log):
    datetime_log = ""
    lines = split_log_lines(log)
    for line in lines:
        catch = re.findall("(\d+):", line)
        if len(catch) > 0:
            timestamp = catch[0]
            isodate = UTCDateTime(int(timestamp)).isoformat()
            datetime_log += line.replace(timestamp, isodate) + "\r\n"
    formatted_log = "".join(datetime_log)
    return formatted_log


# Get date from a .LOG or a .MER file name
def get_date_from_file_name(filename):
    hexdate = re.findall("(.+\d+_)?([A-Z0-9]+)\.(LOG|MER|\d{3})", filename)[0][1]
    timestamp = int(hexdate, 16)
    return UTCDateTime(timestamp)


#
# Plot utilities
#

# Plot vertical lines with plotly
def plotly_vertical_shape(position, ymin=0, ymax=1, name='name', color='blue'):
    xval = list()
    yval = list()
    for ps in position:
        xval.append(ps)
        xval.append(ps)
        xval.append(None)
        yval.append(ymin)
        yval.append(ymax)
        yval.append(None)

    lines = graph.Scatter(x=xval,
                          y=yval,
                          name=name,
                          line=dict(color=color,
                                    width=1.5),
                          hoverinfo='x',
                          mode='lines'
                          )
    return lines


# Get an array of date objects
def get_date_array(date, length, period):
    date_list = list()
    i = 0
    while i < length:
        date_list.append(date + i * period)
        i += 1
    return date_list


# Get an array of time values
def get_time_array(length, period):
    # Compute time
    time_list = list()
    i = 0.0
    while i < length:
        time_list.append(i * period)
        i += 1.
    return time_list


def sac_scale():
    '''Returns the ROUNDED multiplicative factor to convert MERMAID digital counts to pascal

    '''

    scale = round(10**((-201.+25.)/20.) * 2 * 2**28/5. * 1000000)
    return scale


def counts2pascal(data):
    '''Converts MERMAID digital counts to pascal via multiplication with scale factor: util.sac_scale

    '''
    return data/sac_scale()


def band_code(sample_rate=None):
    """ Return instrument band code given sampling frequency in Hz.

    Args:
        sample_rate (float/int): Sample rate in Hz [def: None]

    Returns:
        str: Band code (e.g., "M" for mid period) [def: None]

    """

    # Page 133 : "Appendix A: Channel Naming" (SEED  Manual Format Version 2.4)
    if 1 < sample_rate < 10:
        band_code = "M"

    elif 10 <= sample_rate < 80:
        band_code = "B"

    else:
        band_code = None
        warnings.warn("No band code defined for {} Hz sample rate".format(sample_rate))

    return band_code

def network():
    """Returns 'MH', MERMAID FDSN network name:
    https://www.fdsn.org/networks/detail/MH/

    """
    return 'MH'

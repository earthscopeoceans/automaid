# -*-coding:Utf-8 -*
#
# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v2.7)
#
# Original author: Sebastien Bonnieux
# Current maintainer: Joel D. Simon (JDS)
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified by JDS: 12-Jan-2021
# Last tested: Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit

import re
import struct
import warnings
import numpy as np
import plotly.graph_objs as graph

from obspy import UTCDateTime
from obspy.io.mseed import util as obspy_util

import setup

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

#
# Other utilities (JDS added)
#

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


def set_mseed_time_correction(mseed_filename, time_corr_secs):
    """Set 'Time correction applied' bit and 'Time correction' value in every 'Fixed
    section of Data Header' that precedes every record in an miniSEED file.

    Args:
        mseed_filename (str): miniSEED filename
        time_corr_secs (float): Time correction in seconds

    Result:
        modifies miniSEED file

    See `tests_and_verifications/mseed_fixed_section_data_header.py` for a
    discussion of the fixed header and subsequent blockettes (e.g., 1001, 1000)
    that (seem to?) precede every record an mseed file written by ObsPy v1.2.1.

    Use `$ python -m obspy.io.mseed.scripts.recordanalyzer -a <mseed_filename>`
    before and after applying this function to see the updated miniSEED header.

    """

    # miniSEED convention:
    #
    # [1] record start + time correction = corrected record start
    # [2]  (mer_time)  +  (clockdrift)   =      (gps_time)
    # (VERIFIED: POSITIVE time correction ADVANCES corrected record start)
    #
    # MERMAID convention:
    #
    # [3] clockdrift = gps_time - mer_time
    # [4] mer_time + clockdrift = gps_time = eq. [2]
    #
    # MERMAID's clock drift and SEED's time correction are of the same sign
    # SEED's time correction and time delay are of opposite sign
    # Therefore, SEED's time delay is opposite sign of MERMAID's clock drift
    #
    # positive time correction = record (MER) time EARLY w.r.t. truth (GPS)
    # ==> (+) time correction = (-) MER delay
    #
    # negative time correction = record (MER) time DELAYED w.r.t. truth (GPS)
    # ==> (-) time correction = (+) MER delay
    #
    # Toggle `time_correction` flag between True and False and use:
    #
    #     $ `libmseed/example/mseedview -p  <mseed_filename>`
    #     $ `python -m obspy.io.mseed.scripts.recordanalyzer -a <mseed_filename>`
    #
    # to convince yourself of this

    # All page numbers refer to the SEED Format Version 2.4 manual
    # http://www.fdsn.org/pdf/SEEDManual_V2.4.pdf

    # Time correction values are in units of 0.0001 (1e-4) seconds (pg. 109)
    time_corr_one_ten_thous = np.int32(time_corr_secs / 0.0001)

    # Set "Time correction applied" [Bit 1] (Note 12;  pg. 108)
    flags = {'...': {'activity_flags': {'time_correction': True}}}
    obspy_util.set_flags_in_fixed_headers(mseed_filename, flags)

    # Determine how many records (and thus fixed headers) must be updated
    # The second argument, `offset` is bytes into the mseed file (start at 0)
    record_info = obspy_util.get_record_information(mseed_filename, offset=0)
    number_of_records = record_info.get('number_of_records')

    # Open the file for reading ('r') and writing ('+') in binary ('b') mode
    mseed_file = open(mseed_filename, 'rb+')

    # Loop over every record and apply the proper bits at the proper offsets
    record_offset = 0
    for record_number in range(number_of_records):
        # Retrieve info concerning record at current offset
        record_info = obspy_util.get_record_information(mseed_filename,
                                                        offset=record_offset)

        # Format a binary string representing the time correction value
        # Type: 'LONG' (SEED manual) == 'l' (`struct` builtin)
        byte_order = record_info.get('byteorder')
        binstr_fmt = byte_order + 'l'
        time_correction_binstr = struct.pack(binstr_fmt, time_corr_one_ten_thous)

        # Set 'Time correction' value (Note 17; pg. 109)
        # Position: bytes 40-43 of the fixed header that precedes each record
        # The `record_offset` is in bytes relative to the start of the file
        time_correction_offset = record_offset + 40
        mseed_file.seek(time_correction_offset, 0)
        mseed_file.write(time_correction_binstr)

        # Find the offset of the next record relative to the start of the file
        record_offset += record_info.get('record_length')

    # Conclude
    mseed_file.close()

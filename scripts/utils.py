# -*- coding: utf-8 -*-
#
# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v2.7)
#
# Developer: Joel D. Simon (JDS)
# Original author: Sebastien Bonnieux
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified by JDS: 26-Aug-2021
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

def sacpz_const():
    '''Returns the SAC pole-zero file constant as experimentally determined by
    Nolet, Gerbaud & Rocca (2021) for the third-generation MERMAID and
    documented in "Determination of poles and zeroes for the Mermaid response."

    '''

    sacpz_const = int(-0.14940E+06)
    return sacpz_const


def counts2pascal(data):
    '''Converts MERMAID digital counts to pascal via multiplication with scale factor: util.sac_scale

    '''
    return data/sacpz_const()


def band_code(sample_rate=None):
    """Return instrument band code given sampling frequency in Hz.

    Args:
        sample_rate (float/int): Sample rate in Hz [def: None]

    Returns:
        str: Band code (e.g., "M" for mid period) [def: None]

    NB, the band code not only depends on the sampling frequency but also on the
    corner frequency of the instrument itself (10 s for third-generation
    MERMAID).  Therefore, if future generations have a lower corner frequency
    this def will need to be updated to check for both sampling rate and, e.g.,
    MERMAID generation.

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
    """Set 'Time correction applied' flag and 'Time correction' value in every
    'Fixed section of Data Header' that precedes each data record of a
    time-corrected miniSEED file.

    Args:
        mseed_filename (str): Time-corrected miniSEED filename
        time_corr_secs (float): Time correction [seconds]

    Result:
        modifies miniSEED file (see warnings and notes)

    Warnings:
    * Unsets all other 'Activity', 'I/O and clock', and 'Data Quality' flags.
    * Only adds time correction to header; does not also adjust start/end times.

    Verifications:
    [1] Verify the 'Timing correction applied' FLAG has been set for N records:

        `>> obspy.io.mseed.util.get_flags(mseed_filename)`

    [2] Verify the 'Timing correction' VALUE has been noted for N records:

        `$ python -m obspy.io.mseed.scripts.recordanalyzer -a mseed_filename`

    Notes:
    * Time correction value in [1] appears to be a bug/percentage?
    * Time correction value in [2] is in units of 0.0001 seconds.
    * In [2] it is unknown what 'Activity flags: 2'  means.

    """
    ## All page numbers refer to the SEED Format Version 2.4 manual
    ## http://www.fdsn.org/pdf/SEEDManual_V2.4.pdf

    # Time correction values are in units of 0.0001 (1e-4) seconds (pg. 109)
    time_corr_one_ten_thous = np.int32(time_corr_secs / 0.0001)

    # Set "Time correction applied" [Bit 1] (Note 12;  pg. 108)
    # Warning: this unsets any other flags that are set
    flags = {'...': {'activity_flags': {'time_correction': True}}}
    obspy_util.set_flags_in_fixed_headers(mseed_filename, flags)

    # Determine how many records (and thus fixed headers) must be updated
    # The second argument, `offset` is bytes into the mseed file (start at 0)
    record_info = obspy_util.get_record_information(mseed_filename, offset=0)
    number_of_records = record_info.get('number_of_records')

    # Loop over every record and apply the proper bits at the proper offsets
    record_offset = 0
    with open(mseed_filename, 'rb+') as mseed_file:
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


def flattenList(toplist):
    ''' Flatten/merge a two-layer-deep nested list

    '''
    return [item for sublist in toplist for item in sublist]

def get_gps_instrument_name():
    # Intake a float number and update this list as necessary
    return 'u-blox NEO-M8N'

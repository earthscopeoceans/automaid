# -*- coding: utf-8 -*-
#
# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v2.7)
#
# Developer: Joel D. Simon (JDS)
# Original author: Sebastien Bonnieux (SB)
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified by JDS: 11-Sep-2023
# Last tested: Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit

import re
import sys
import struct
import datetime
import warnings
import numpy as np
import plotly.graph_objs as graph

from obspy import UTCDateTime
from obspy.io.mseed import util as obspy_util

import setup

# Get current version number.
version = setup.get_version()

#
# LOG file utilities
#

def get_log_delimiter(content):
    if "\r\n" in content:
        delim = "\r\n"

    elif "\r" in content:
        delim = "\r"

    elif "\n" in content:
        delim = "\n"

    else:
        raise ValueError("Delimiter from list of expected delimiters not found")

    return delim

# Split logs in several lines
def split_log_lines(content):
    delim = get_log_delimiter(content)
    splits = content.split(delim)
    if splits[-1] == "":
        splits = splits[:-1]

    return splits

# Search timestamps for a specific keyword
def find_timestamped_values(regexp, content):
    timestamped_values = []
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
    xval = []
    yval = []
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
    date_list = []
    i = 0
    while i < length:
        date_list.append(date + i * period)
        i += 1
    return date_list


# Get an array of time values
def get_time_array(length, period):
    # Compute time
    time_list = []
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

def channel(sample_rate=None):
    """Return instrument channel (KCMPNM in SAC parlance), e.g., 'BDH' given
    sampling frequency in Hz

    See also: `band_code()` and SEED manual Appendix A

    """

    channel = band_code(sample_rate) + "DH"

    return channel

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

def get_gps_sensor_name():
    # Intake a float number and update this list as necessary?
    return 'u-blox NEO-M8N'

def get_absolute_pressure_sensor_name():
    # Intake a float number and update this list as necessary?
    return 'KELLER Series 6'

def ndarray_byteorder(ndarray):
    '''Return str 'little', 'big', or 'n/a' (endianess irrelevant for
    int8/ascii) indicating endianness of data within numpy array

    This def required because usually `ndarray.dtype.byteorder` returns "=", or
    native system ordering, which is not very useful

    '''
    # https://numpy.org/doc/stable/reference/generated/numpy.dtype.byteorder.html#numpy.dtype.byteorder
    byteorder = ndarray.dtype.byteorder
    if byteorder == '=':
        byteorder = sys.byteorder
    elif byteorder == '<':
        byteorder = 'little'
    elif byteorder == '>':
        byteorder = 'big'
    elif byteorder == '|':
        byteorder = 'n/a'
    else:
        # Protection for future with different(?) return values
        raise ValueError("Unknown byte order: %s'", byteorder)

    return byteorder

def ndarray_stat(ndarray):
    '''Return dict with items 'size', 'precision', and 'byteorder' (endianness;
    string either 'little or big') given an ndarray

    '''

    stat = {
        'size': ndarray.size,
        'precision': ndarray.dtype.name,
        'byteorder': ndarray_byteorder(ndarray)
    }

    return stat

def deployDate():
    '''
    Return dictionary of deployment datetimes.

    '''

    # *I found dates in the same range (~minutes before) as misalo.txt and set
    # these deployment dates to the actual corresponding date in the LOG (GPS
    # time pairs are printed in .LOG then .MER, in that order, so it is valid to
    # use the .LOG time here). If the date did not match exactly I looked for
    # the first date where the clock drift reset and the associated LOG recorded
    # an actual dive.

    date = datetime.datetime

    # Warning: leading zeros are not allowed, super annoying (means octal).
    deploy = {
        #
        # JAMSTEC
        "452.112-N-01": date(2018, 12, 27),
        "452.112-N-02": date(2018, 12, 28),
        "452.112-N-03": date(2018,  4,  9),
        "452.112-N-04": date(2019,  1,  3),
        "452.112-N-05": date(2019,  1,  3),
        #
        # GeoAzur
        "452.020-P-06": date(2018,  6, 26, 19, 13, 53),
        "452.020-P-07": date(2018,  6, 27, 18, 39, 2),
        #
        # Princeton
        "452.020-P-08": date(2018,  8,  5, 13, 23, 14),
        "452.020-P-09": date(2018,  8,  6, 15, 21, 26),
        "452.020-P-10": date(2018,  8,  7, 12, 53, 42),
        "452.020-P-11": date(2018,  8,  9, 11,  2,  6),
        "452.020-P-12": date(2018,  8, 10, 19, 51, 31),
        "452.020-P-13": date(2018,  8, 31, 16, 50, 23),
        "452.020-P-16": date(2018,  9,  4,  7, 12, 15),
        "452.020-P-17": date(2018,  9,  4, 11,  2, 54),
        "452.020-P-18": date(2018,  9,  5, 17, 38, 32),
        "452.020-P-19": date(2018,  9,  6, 20,  7, 30),
        "452.020-P-20": date(2018,  9,  8, 10, 32,  8),
        "452.020-P-21": date(2018,  9,  9, 17, 42, 36),
        "452.020-P-22": date(2018,  9, 10, 19,  7, 21),
        "452.020-P-23": date(2018,  9, 12,  2,  4, 14),
        "452.020-P-24": date(2018,  9, 13,  8, 52, 18),
        "452.020-P-25": date(2018,  9, 14, 11, 57, 12),
        #
        # SUSTech
        "452.020-P-0026": date(2019,  8,  6,  2, 50, 12),
        "452.020-P-0027": date(2019,  8,  6, 15, 52, 48),
        "452.020-P-0028": date(2019,  8,  7,  5, 23,  6),
        "452.020-P-0029": date(2019,  8,  7, 19, 32, 36),
        "452.020-P-0030": date(2021,  5, 27, 10, 39, 25), # *
        "452.020-P-0031": date(2019,  8,  8, 10, 52, 31),
        "452.020-P-0032": date(2019,  8,  9,  4, 13, 23),
        "452.020-P-0033": date(2019,  8, 10,  9, 40,  9),
        "452.020-P-0034": date(2019,  8, 12, 19, 42,  3),
        "452.020-P-0035": date(2019,  8, 13, 16, 20, 32),
        "452.020-P-0036": date(2019,  8, 14, 20, 55,  4),
        "452.020-P-0037": date(2019,  8, 16, 23, 51,  6),
        "452.020-P-0038": date(2019,  8, 17, 10, 56,  3),
        "452.020-P-0039": date(2019,  8, 17, 22,  5,  5),
        "452.020-P-0040": date(2019,  8, 18, 10, 56, 33),
        "452.020-P-0041": date(2019,  8, 19,  9, 27,  4),
        "452.020-P-0042": date(2019,  8, 19, 19, 26,  4),
        "452.020-P-0043": date(2019,  8, 20,  6, 13, 58),
        "452.020-P-0044": date(2019,  8, 21,  6, 18, 16),
        "452.020-P-0045": date(2019,  8, 21, 17, 43, 17),
        "452.020-P-0046": date(2019,  8, 22,  4, 21, 31),
        "452.020-P-0047": date(2019,  8, 22, 17, 13, 43),
        "452.020-P-0048": date(2019,  8, 24,  3,  2,  8), # *
        "452.020-P-0049": date(2019,  8, 24, 18, 46, 23),
        "452.120-R-0058": date(2021,  5, 19, 15, 55, 35),
        "452.120-R-0059": date(2021,  5, 11, 22, 41,  6),
        # 452.120-R-0060 DOA?
        "452.120-R-0061": date(2021,  5, 11,  1, 46, 41),
        "452.120-R-0062": date(2023,  7,  8, 19, 49, 30),
        "452.120-R-0063": date(2021,  5,  1, 23, 52, 39),
        # 452.120-R-0064 DOA?
        "452.120-R-0065": date(2021,  5,  1, 10,  1, 26),
        # 452.120-R-0066 DOA?
        "452.120-R-0067": date(2021,  5, 11, 10,  8,  6),
        # 452.120-R-0068 DOA?
        "452.120-R-0069": date(2021,  5,  3,  2, 23,  3),
        "452.120-R-0071": date(2021,  5,  3,  9, 12, 34),
        "452.120-R-0072": date(2021,  5,  1,  1, 22, 22),
        "452.120-R-0073": date(2021,  5, 12, 11, 33,  4),
        # 452.120-S-0070 DOA?
        # 452.120-S-0081 DOA?
        # 452.120-S-0082 DOA?
        # 452.120-S-0085 DOA?
        # 452.120-S-0086 DOA?
        # 452.120-S-0087 DOA?
        # 452.120-S-0088 DOA?
        # 452.120-S-0089 DOA?
        # 452.120-S-0090 DOA?
        # 452.120-S-0091 DOA?
        # 452.120-S-0092 DOA?
        # 452.120-S-0093 DOA?
        # 452.120-S-0094 DOA?
    }
    # (* marks unsure date)

    # Don't know about these...
    # "452.020-P-0051": date(2019,  7,  1),
    # "452.020-P-0052": date(2019,  7,  1),
    # "452.020-P-0053": date(2019,  7,  1),
    # "452.020-P-0054": date(2019,  7,  1),

    return deploy

def deploy2present():
  '''
  Returns default procesing filter dates of deployment -> present.

  '''
  now = datetime.datetime.utcnow();
  dDay = deployDate();

  fDay = {}
  for m in dDay:
      fDay[m] = [dDay[m], now]

  return fDay

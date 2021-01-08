# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v2.7)
#
# Author: Joel D. Simon (JDS)
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified by JDS: 07-Jan-2021
# Last tested: Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit

# Page numbers refer to the SEED Format Version v2.4 Manual

import struct
import numpy as np
from obspy.io.mseed import util

# python -m obspy.io.mseed.scripts.recordanalyzer -a 20201226T005647.08_5FE6DF46.MER.DET.WLT5.mseed
# blockette 1001: struct.unpack('>H',(k[48:50])+8)
# blockette 1000: struct.unpack('>H',(k[48:50])+8)

# The units of the time correction value are in 0.0001 s (1e-4 s)
time_corr_val_sec = 18.76
time_corr_val = time_corr_val_sec / 0.0001 # convert to np.int32?

def seed2struct(field=''):
    """Translate binary SEED field type to builtin `struct` (C) format.

    Args:
        field (str): SEED field type (e.g., 'UWORD') [def: '']

    Returns:
        str: builtin `sruct` (C) format (e.g., 'H') [def: None]

    """

    fmt = {
        # SEED manual v2.4 pg. 33
        # https://docs.python.org/2/library/struct.html#format-characters

        'BYTE': 'B', # unsigned char (8 bit)
        'UWORD': 'H', # unsigned short (16 bit)
        'WORD': 'h', # signed short (16 bit)
        'LONG': 'l', # signed long (32 bit)

        # ...and others I don't currently use...
    }


    return fmt.get(field)

def binstr(b_order, field, val):
    """Convert value to Python (hexadecimal) string representing binary data.

    Python returns a hex str with file.read(<binary_data>)
    BINSTR returns a hex str to write binary data with file.write(<binstr>)
    (see especially https://docs.python.org/2/search.html?q=struct.pack)

    Args:
        b_order (str): byte order (e.g., '<' for little- or '>' for big-endian)
        field (str): field type in SEED parlance (e.g., 'UWORD')
        val (int/float): value to be converted to binary (e.g., 2020 or 3.14)

    Returns:
        str: str that file.write() understands to represent binary data

    """

    # Translate SEED field name to `struct` (C) format (result: e.g., 'H')
    fmt = seed2struct(field)

    # Prepend endianness to `struct` format (result: e.g., '>H')
    fmt = b_order + fmt

    # Generate hex str representing input value in binary
    return struct.pack(fmt, val)


def readbytes(fileobj, offset, whence, b_order, f_type):
    fmt = byte_order + seed2struct(f_type)
    size = struct.calcsize(fmt)
    f.seek(offset, whence)
    binstr = f.read(size)
    val =  struct.unpack(fmt, binstr)[0]

    return val


#__________________________________

mseed_filename = 'test_data/20201226T005647.08_5FE6DF46.MER.DET.WLT5.mseed'

# Set "time correction applied" activity flag to True for all traces
flags = {'...': {'activity_flags': {'time_correction': True}}}
util.set_flags_in_fixed_headers(mseed_filename, flags)

# Get the byte ordering (big/little-endian)
record_info = util.get_record_information(mseed_filename, offset=0)
number_of_records = record_info.get('number_of_records')

# Open the file in binary mode for reading ('r') and writing ('+')
mseed_file = open(mseed_filename, 'rb+')

record_offset = 0
for record_number in range(number_of_records):
    # Retrieve info concerning record at current offset
    record_info = util.get_record_information(mseed_filename, record_offset)

    # Format a binary string recording the time correction value
    byte_order = record_info.get('byteorder')
    time_correction_binstr = binstr(byte_order, 'LONG', time_corr_val)

    # Time correction occupies bytes 40-43 of the 'Fixed Section of Data Header'
    time_correction_offset = record_offset + 40
    mseed_file.seek(time_correction_offset, 0)
    mseed_file.write(time_correction_binstr)

    # Find the offset of the next record relative to the start of the file
    record_offset += record_info.get('record_length')

mseed_file.close()

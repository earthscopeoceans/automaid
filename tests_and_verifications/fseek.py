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

        'UWORD': 'H', # unsigned short (16 bit)
        'WORD': 'h', # signed short (16 bit)
        'LONG': 'l', # signed long (32 bit)

        # ...and others I don't curently use...
    }


    return fmt.get(field)

def hexstr(b_order, field, val):
    """Convert value to Python (hexidecimal) string representing binary data.

    Python returns a hex str with file.read(<binary_data>)
    HEXSTR returns a hex str to write binary data with file.write(<hexstr>)
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


filename = 'test_data/20201226T005647.08_5FE6DF46.MER.DET.WLT5.mseed'

# Set "time correction applied" activity flag to True for all traces
flags = {'...': {'activity_flags': {'time_correction': True}}}
util.set_flags_in_fixed_headers(filename, flags)

# Get the byte ordering (big/little-endian)
rec_info = util.get_record_information(filename)
byte_order = rec_info.get('byteorder')

""" SEED Conventions

'How Binary Data Fields are Described in This Manual,' pp. 33-34

Field   #Bits    Description
UWORD      16    Unsigned quantity
LONG       32    Unsigned quantity

... and ...

'Fixed Section of Data Header (48 bytes),' pp. 108-110

Note    Length*   Start    End
   1         6        0      5
   2         1        6      6
   3         1        7      7
   4         5        8     12
   5         2       13     14
   6         3       15     17
   7         2       18     19
   8        10       20     29
   9         2       30     31 <- UWORD: Number of samples in record
  10         2       32     33
  11         2       34     35
  12         1       36     36
  13         1       37     37
  14         1       38     38
  15         1       39     39
  16         4       40     43 <- LONG: Time correction (units of 0.0001 s)
  17         2       44     45 <- UWORD: Offset to beginning of the data
  18         2       46     47 <- UWORD: Offset to first data blockette

*length in bytes

... and ...

'

"""

# Open the file in binary mode for reading ('r') and writing ('+')
f = open(filename, 'rb+')

# READ: Number of samples in record (Note 9)
f.seek(30, 0)
nsamp_fmt = byte_order + seed2struct('UWORD')
nsamp_size = struct.calcsize(nsamp_fmt)
nsamp_hexstr = f.read(nsamp_size)
nsamp =  struct.unpack(nsamp_fmt, nsamp_hexstr)[0]

# READ: Offset in bytes to the beginning of the data (Note 17)
# The first byte of the data record is byte 0
f.seek(44, 0)
offset_beg_dat_fmt = byte_order + seed2struct('UWORD')
offset_beg_dat_size = struct.calcsize(offset_beg_dat_fmt)
offset_beg_dat_hexstr = f.read(offset_beg_dat_size)
offset_beg_dat =  struct.unpack(offset_beg_dat_fmt, offset_beg_dat_hexstr)[0]

# READ: Offset in bytes to the first data blockette in this data record
# The data blockette is Blockette type - 1000 (Appendix G)
f.seek(46, 0)
offset_blkt1000_fmt = byte_order + seed2struct('UWORD')
offset_blkt1000_size = struct.calcsize(offset_blkt1000_fmt)
offset_blkt1000_hexstr = f.read(offset_blkt1000_size)
offset_blkt1000 =  struct.unpack(offset_blkt1000_fmt, offset_blkt1000_hexstr)[0]

# READ: Data blockette number (should be 1000)
f.seek(46+offset_blkt1000, 0)


#


# WRITE: Time correction value (Note 16)
# ("time correction applied" bit written with util.set_flags_in_fixed_headers)
f.seek(40,0)
hexstr_tcorr = hexstr(byte_order, 'LONG', time_corr_val)
#tcorr =  struct.unpack(tcorr_fmt, tcorr_hexstr)[0]


# Verify time_correction with util.get_record_info?






# Write the binary data at the proper location
#
f.close()



























#return '\\x%02x\\x%02x' % tuple([ ord(x) for x in struct.pack('>H', year) ])












#year = '\x07\xfc'  # hex(2044) = '0x7fc'


# f = open(filename, 'rb+')
# f.seek(20,0)
# buffer_year = np.fromfile(f, dtype=np.uint16, count=1);
# year = np.ndarray(shape=(1,),dtype='>i2', buffer=buffer_year)
# print(year)
# f.close()





# f = open(filename, 'wb')
# f.seek(20,0)
# f.write(struct.pack('>i2', 2020))
# f.close()

# f = open(filename, 'r+b')  # 'w+b' does not work, even when followed by fseek(0,0)
# f.seek(20,0)
#
# f.write(year)
# f.close()

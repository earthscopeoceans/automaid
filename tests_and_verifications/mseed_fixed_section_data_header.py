# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v2.7)
#
# This test script was abandoned but retained for explanation of mseed headers.
# It produces no output.
#
# Reason for abandonment --
# Every miniSEED file contains potentially multiple records
# Every record starts with a 48-byte fixed header (pp. 108-110, SEED manual)
# The "time correction applied" (bool) and "time correction" (LONG) reside there
# At some point after the fixed header is the mseed header (blockette 1000)
# Blockette 1000 gives the record length (how far to skip to next record)
# Every record must be updated with the time corrections
# The data within the records (between subsequent fixed headers) is compressed
# The f.seek(offset) is thus complicated
# The proper method to skip ahead is contained in clibmseed/obspy
# But that's a lot of code rewriting...
#
# So this was left at the point that I figured out how many samples were in each
# record and what compression scheme (STEIM 2 encoding) was used, which allows
# one to figure out the f.seek(offset).
#
# But I realized obspy.io.mseed.util.get_record_information() gives that info in
# a dict so I'm just using that (inelegant solution)...
#
# Author: Joel D. Simon (JDS)
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified by JDS: 07-Jan-2021
# Last tested: Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit

# Page numbers refer to the SEED Format Version v2.4 Manual

import struct
import numpy as np
from obspy.io.mseed import util

# Use in terminal:
# $ python -m obspy.io.mseed.scripts.recordanalyzer -a 20201226T005647.08_5FE6DF46.MER.DET.WLT5.mseed
# to check that every record was properly updated.

# The units of the time correction value are in 0.0001 s (1e-4 s)
time_corr_val_sec = 18.76 # fake value
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
BYTE        8    Unsigned quantity
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

# "Each data record in a SEED volume consists of a fixed header, followed by
# optional data blockettes in the variable header." (Chapter 8)
# I.e., every RECORD in an mseed starts with the fixed 48 byte header, followed
# by a variable number of data blockettes

# ObsPy seems to write for every record:
# 48 bytes: Fixed Section of Data Header (pg. 108)
#  8 bytes: [1001] Data Extension Blockette (pg. 124)
#  8 bytes: [1000] Data Only SEED Blockette (pg. 123; repeated pg. 196)

# Open the file in binary mode for reading ('r') and writing ('+')
f = open(filename, 'rb+')

# READ: Number of samples in record (Note 9)
nsamp = readbytes(f, 30, 0, byte_order, 'UWORD')

# READ: Offset in bytes to the beginning of the data (Note 17)
# The first byte of the data record is byte 0
offset_beg_dat = readbytes(f, 44, 0, byte_order, 'UWORD')

# Every Data Blockette starts with:
# Blockette type: 'UWORD' (2 bytes)
# Next blockette's byte number (offset from 0 of this record): 'UWORD' (2 bytes)

# Require Blockette 1000 -- if not the current Blockette, advance the file
# pointer two bytes to find the offset of the next Blockette
offset_blkt = readbytes(f, 46, 0, byte_order, 'UWORD')
blkt_number = readbytes(f, offset_blkt, 0, byte_order, 'UWORD')

while blkt_number != 1000:
    # Next blockette's byte offset (Note 2): +2 bytes into current Blockette
    offset_blkt = readbytes(f, offset_blkt+2, 0, byte_order, 'UWORD')
    blkt_number = readbytes(f, offset_blkt, 0, byte_order, 'UWORD')

# Encoding Format (Note 3): +4 bytes of blockette
enc_fmt = readbytes(f, offset_blkt+4, 0, byte_order, 'BYTE')


# !! Problem: I don't have a good way to translate namps * STEIM 2 encoding to
# !! determine what offset I need to jump to the next fixed header...


# WRITE: Time correction value (Note 16)
# ("time correction applied" bit written with util.set_flags_in_fixed_headers)
f.seek(40,0)
binstr_tcorr = binstr(byte_order, 'LONG', time_corr_val)
#f.write...

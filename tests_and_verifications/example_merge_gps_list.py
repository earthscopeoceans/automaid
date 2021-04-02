# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v2.7)
#
# Demonstrates how various lists of nonunique GPS fixes are merged into lists of
# unique GPS pairs using the `merge_gps_list` method.
#
# See an annotated output of this script at:
# example_merge_gps_list.pdf; 2017.2 pp. 132-133
#
# Developer: Joel D. Simon (JDS)
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified by JDS: 01-Apr-2021
# Last tested: Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit

import os
import sys
import pickle

sys.path.append(os.path.join(os.getenv('AUTOMAID'), 'scripts'))
import gps

data_file = os.path.join(os.getenv('AUTOMAID'), 'tests_and_verifications',
                         'test_data', 'gps_list.pickle')

with open(data_file) as f:
    gps_list = pickle.load(f)

ex1 = list(gps_list)
print('\nStandard list (8 GPS; 4 pairs)')
for i,x in enumerate(ex1):
    print('Non-unique GPS fix {:d}: {:s}'.format(i, str(x.date)[:19]))
    print('Date Source: ' + x.source)
    print(' Loc Source: ' + x.source + '\n')

ex1 = gps.merge_gps_list(gps_list)
for i,x in enumerate(ex1):
    print('Unique GPS fix {:d}: {:s}'.format(i, str(x.date)[:19]))
    print('Date Source: ' + x.date_source)
    print(' Loc Source: ' + x.loc_source + '\n')

## ___________________________________________________________________________ ##

ex2 = list(gps_list)
ex2.pop(0)
print('\nFirst GPS (from LOG) removed (7 GPS; 4 pairs; 0th pair all MER data)')
for i,x in enumerate(ex2):
    print('Non-unique GPS fix {:d}: {:s}'.format(i, str(x.date)[:19]))
    print('Date Source: ' + x.source)
    print(' Loc Source: ' + x.source + '\n')

ex2 = gps.merge_gps_list(ex2)
for i,x in enumerate(ex2):
    print('Unique GPS fix {:d}: {:s}'.format(i, str(x.date)[:19]))
    print('Date Source: ' + x.date_source)
    print(' Loc Source: ' + x.loc_source + '\n')

## ___________________________________________________________________________ ##

ex3 = list(gps_list)
ex3.pop(-1)
print('\nLast GPS (from MER) removed (7 GPS; 4 pairs; 3rd pair all LOG data)')
for i,x in enumerate(ex3):
    print('Non-unique GPS fix {:d}: {:s}'.format(i, str(x.date)[:19]))
    print('Date Source: ' + x.source)
    print(' Loc Source: ' + x.source + '\n')

ex3 = gps.merge_gps_list(ex3)
for i,x in enumerate(ex3):
    print('Unique GPS fix {:d}: {:s}'.format(i, str(x.date)[:19]))
    print('Date Source: ' + x.date_source)
    print(' Loc Source: ' + x.loc_source + '\n')


## ___________________________________________________________________________ ##

ex4 = list(gps_list)
ex4.pop(4)
print('\n4th GPS (from LOG) removed (7 GPS; 4 pairs; 2nd pair all MER data)')
for i,x in enumerate(ex4):
    print('Non-unique GPS fix {:d}: {:s}'.format(i, str(x.date)[:19]))
    print('Date Source: ' + x.source)
    print(' Loc Source: ' + x.source + '\n')

ex4 = gps.merge_gps_list(ex4)
for i,x in enumerate(ex4):
    print('Unique GPS fix {:d}: {:s}'.format(i, str(x.date)[:19]))
    print('Date Source: ' + x.date_source)
    print(' Loc Source: ' + x.loc_source + '\n')

# Verify v3.5.1 fix: longitude errors when MERMAID crosses antimeridian.
#
# In all examples MERMAID drifts across the antimeridian over a dive lasting one
# day and the interpolation date (i.e., time it records an event) is exactly in
# the middle (12 hours in) of the dive.
#
# See example_v3.5.1.pdf for colorful drawings of these four examples.
#
# Author: Joel D. Simon (JDS)
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified by JDS: 15-Aug-2022
# Last tested: Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit

import os
import sys
import pickle

sys.path.append(os.path.join(os.getenv('AUTOMAID'), 'scripts'))
import gps
from obspy import UTCDateTime as utc

# Load an example GPS list
data_file = os.path.join(os.getenv('AUTOMAID'), 'tests_and_verifications',
                         'test_data', 'gps_list.pickle')
with open(data_file) as f:
    gpsl = pickle.load(f)

# We only need two GPS points for these examples
# Dump indices 2+ for cleanliness
gpsl[2:] = []

# Let's make time difference 1 day with interp date in middle
gpsl[0].date = utc(1970, 01, 01, 0)
gpsl[1].date = utc(1970, 01, 02, 0)
interp_date = utc(1970, 01, 01, 12)

# Latitude is irrelevant*
# (sign does not flip at equator like it does at antimeridian)
# Set to 0 for for purposes of test
gpsl[0].latitude = 0
gpsl[1].latitude = 0

## ___________________________________________________________________________ ##

# Example 1:  Moving from east to west (to the left)
# More time spent east (to the right) of antimeridian
gpsl[0].longitude = -174
gpsl[1].longitude = +178

# Expectation: -178 (still to east; event recorded before crossing)
ex1 = gps.linear_interpolation(gpsl, interp_date)
print ex1.longitude

## ___________________________________________________________________________ ##

# Example 2: Moving from east to west (to the left)
# More time spent west (to the left) of antimeridian
gpsl[0].longitude = -178
gpsl[1].longitude = +174

# Expectation: +178 (to the west; event recorded after crossing)
ex2 = gps.linear_interpolation(gpsl, interp_date)
print ex2.longitude

## ___________________________________________________________________________ ##

# Example 3: Moving from west to east (to the right)
# More time spent east (to the right) of antimeridian
gpsl[0].longitude = +178
gpsl[1].longitude = -174

# Expectation: -178 (to the east; event recorded after crossing)
ex3 = gps.linear_interpolation(gpsl, interp_date)
print ex3.longitude

## ___________________________________________________________________________ ##

# Example 4: Moving from west to east (to the right)
# More time spent west (to the left) of antimeridian
gpsl[0].longitude = +174
gpsl[1].longitude = -178

# Expectation: +178 (still to west; event recorded before crossing)
ex4 = gps.linear_interpolation(gpsl, interp_date)
print ex4.longitude

## ___________________________________________________________________________ ##

# *Just for good measure let's repeat Example 4 while crossing equator

# Drift direction alternates: to south; to north; to south; to north
# In the first two examples more time is spent to north of equator
# In the final two examples more time is spent to south of equator
# Recall interpolation date in middle of dive
# Therefore, expectation is lat = +2 for first two and lat = -2 for second two
lat = [(+8, -4), \
       (-4, +8), \
       (+4, -8), \
       (-8, +4)]

for l in lat:
    gpsl[0].latitude = l[0]
    gpsl[1].latitude = l[1];
    ex4_lat = gps.linear_interpolation(gpsl, interp_date)
    print (ex4_lat.latitude, ex4_lat.longitude)

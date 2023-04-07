# -*- coding: utf-8 -*-
#
# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v2.7)
#
# Developer: Joel D. Simon (JDS)
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified by JDS: 04-Apr-2023
# Last tested: Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit

# Todo:
#
# *Add `read` method at module level
# *Convert most of current GeoCSV guts to `write` method at module level
# *Main GeoCSV object should organize (dict?) file columns (w/o class-level read/write methods)
# *Write (nested) function docstrings
# *Verify types and signs, e.g. for 'time correction/delay' ([+/-]np.int32)

import csv
import pytz
import datetime
import numpy as np

import dives
import setup
import utils

class GeoCSV:
    """Organize MERMAID metadata and write them to GeoCSV format

    Args:
        complete_dives (list): List of dives.Complete_Dive instances
        creation_date (str): File-creation datestr
                             (def: current UTC time ("Z" designation) in seconds precision)
        version (str): GeoCSV version (def: 'v2.2.0-0')
        delimiter (str): GeoCSV delimiter (def: ',')
        lineterminator (str): GeoCSV line terminator (def: '\n')

    """

    def __init__(self,
                 complete_dives,
                 creation_datestr=datetime.datetime.now(pytz.UTC).isoformat().split(".")[0]+"Z",
                 version='v2.2.0-1',  # Semantic versioning: v<MAJOR>.<MINOR>.<PATCH>-<PRE_RELEASE>
                 delimiter=',',
                 lineterminator='\n'):

        if not all(isinstance(complete_dive, dives.Complete_Dive) for complete_dive in complete_dives):
            raise ValueError('Input `complete_dives` must be list of `dives.Complete_Dives` instances')

        self.complete_dives = complete_dives
        self.creation_datestr = creation_datestr
        self.version = version
        self.delimiter = delimiter
        self.lineterminator = lineterminator

        self.dataset_header = ['#dataset: GeoCSV ' + self.version]
        self.created_header = ['#created: ' + self.creation_datestr]
        self.version_header = ['#automaid: {} ({})'.format(setup.get_version(), setup.get_url())]
        self.delimiter_header = ['#delimiter: ' + repr(self.delimiter)]
        self.lineterminator_header = ['#lineterminator: ' + repr(self.lineterminator)]

        self.FieldUnit_header = [
            'FieldUnit',
            'iso8601',
            'unitless',
            'unitless',
            'unitless',
            'unitless',
            'degrees_north',
            'degrees_east',
            'meters',
            'mbar',
            'unitless',
            'hertz',
            'seconds',
            'seconds'
        ]

        self.FieldType_header = [
            'FieldType',
            'datetime',
            'string',
            'string',
            'string',
            'string',
            'float',
            'float',
            'float',
            'float',
            'string',
            'float',
            'float',
            'float'
        ]

        self.MethodIdentifier_header = [
            'MethodIdentifier',
            'StartTime',
            'Network',
            'Station',
            'Location',
            'Channel',
            'Latitude',
            'Longitude',
            'Elevation',
            'AbsolutePressure',
            'SensorDescription',
            'SampleRate',
            'TimeDelay',
            'TimeCorrection'
        ]

        self.MethodIdentifier_GPS = 'Measurement:GPS:{:s}'.format(utils.get_gps_sensor_name().replace(' ', '_'))
        self.MethodIdentifier_Pressure = 'Measurement:Pressure:{:s}'.format(utils.get_absolute_pressure_sensor_name().replace(' ', '_'))
        self.MethodIdentifier_Algorithm = 'Algorithm:automaid:{:s}'.format(setup.get_version())

    def get_header_lines(self):
        header_lines = [
            self.dataset_header,
            self.created_header,
            self.version_header,
            self.delimiter_header,
            self.lineterminator_header,
            self.FieldUnit_header,
            self.FieldType_header,
            self.MethodIdentifier_header
        ]

        return header_lines

    def write(self, filename='geo.csv'):
        """Write three GeoCSV files: both 'DET' and 'REQ'; only 'DET'; and only 'REQ'

        Args:
            filename (str): root GeoCSV filename, to be appended (def: 'geo.csv')
                            'geo.csv' -> 'geo_DET_REQ.csv', 'geo_DET.csv', 'geo_DET_REQ.csv'

        """

        ## Functional prototypes for self.write()
        ## ___________________________________________________________________________ ##

        # Lambda functions to convert to float32 with specified precision
        d0 = lambda x: format(np.float32(x), '.0f')
        d1 = lambda x: format(np.float32(x), '.1f')
        d6 = lambda x: format(np.float32(x), '.6f')
        nan = np.float32('nan')

        def format_gps_rows(complete_dive):
            """Format GeoCSV rows of GPS measurements

            GPS metadata == 'Measurement'

            Args:
                complete_dive (dives.Complete_Dive instance):

            """

            # Loop over all GPS instances and write single line for each
            gps_rows = []
            for gps in sorted(complete_dive.gps_list, key=lambda x: x.date):
                gps_rows.append([
                    self.MethodIdentifier_GPS,
                    str(gps.date)[0:19]+'Z',
                    complete_dive.network,
                    complete_dive.kstnm,
                    nan,
                    nan,
                    d6(gps.latitude),
                    d6(gps.longitude),
                    d0(0),
                    d0(0),    # !!! Measured and corrected external pressure at surface? 1 atm? NaN?
                    'MERMAIDHydrophone({:s})'.format(complete_dive.kinst),
                    nan,
                    d6(gps.mseed_time_delay),
                    nan
                ])

            return gps_rows

        def format_pressure_rows(complete_dive):
            """Format GeoCSV rows of mbar absolute pressure measurements

            pressure metadata == 'Measurement'

            Args:
                complete_dive (dives.Complete_Dive instance):

            """

            # Initialize a "previous" row to check for redundancies
            # This can occur when, e.g., "[SURFIN ..." and "[PRESS ..." print same info in .LOG
            # (07_5B773AF5.LOG, lines 916 and 917)
            pressure_rows = []
            prev_pressure_row = []
            for pressure in sorted(complete_dive.pressure_mbar, key=lambda x:x[1]):
                pressure_row = [
                    self.MethodIdentifier_Pressure,
                    str(pressure[1])[0:19]+'Z',
                    complete_dive.network,
                    complete_dive.kstnm,
                    nan,
                    nan,
                    nan,
                    nan,
                    d0(0),
                    d0(pressure[0]),    # !!! External pressure at surface? Just list 1 atm?
                    'MERMAIDHydrophone({:s})'.format(complete_dive.kinst),
                    nan,
                    nan,
                    nan
                ]

                if pressure_row != prev_pressure_row:
                    pressure_rows.append(pressure_row)

                prev_pressure_row = pressure_row

            return pressure_rows

        def format_algorithm_rows(complete_dive):
            """Format GeoCSV rows of event metadata (e.g., starttime and MERMAID location)

            Event metadata == 'Algorithm'

            Args:
                complete_dive (dives.Complete_Dive instance):

            """

            # Only keep events with an interpolated station location (STLA/STLO)
            ## !! Is this condition good enough / algorithm rows match DET SAC? !!
            event_list = [event for event in complete_dive.events if event.obspy_trace_stats]

            # Initialize a "previous" row to check for redundancies
            # This can occur when, e.g., a REQ file is multiply requested
            det_algorithm_rows = []
            req_algorithm_rows = []
            prev_algorithm_row = []
            for event in sorted(event_list, key=lambda x: x.corrected_starttime):
                if event.station_loc_is_preliminary:
                    continue

                algorithm_row = [
                    self.MethodIdentifier_Algorithm,
                    str(event.obspy_trace_stats["starttime"])[:19]+'Z',
                    complete_dive.network,
                    complete_dive.kstnm,
                    event.obspy_trace_stats["location"],
                    event.obspy_trace_stats["channel"],
                    d6(event.obspy_trace_stats.sac["stla"]),
                    d6(event.obspy_trace_stats.sac["stlo"]),
                    d0(0),
                    d0(event.pressure_mbar),
                    'MERMAIDHydrophone({:s})'.format(complete_dive.kinst),
                    d1(event.obspy_trace_stats["sampling_rate"]),
                    nan,
                    d6(event.mseed_time_correction)
                ]

                if algorithm_row != prev_algorithm_row:
                    if event.is_requested:
                        req_algorithm_rows.append(algorithm_row)

                    else:
                        # Sanity checks just to make sure all "depth" units in their expected mbar
                        # The manual says 1 m = 101 mbar; automaid has always assumed 1 m = 1 dbar = 100 mbar
                        # (MERMAID manual Réf : 452.000.852 Version 00)
                        if event.pressure_dbar * 100 != event.pressure_mbar:
                            raise ValueError("Expected 100 mbar to equal 1 dbar")

                        if event.pressure_dbar is not event.obspy_trace_stats.sac["stdp"]:
                            raise ValueError("`stdp` (roughly meters) should be the dbar pressure from .MER")

                        det_algorithm_rows.append(algorithm_row)

                prev_algorithm_row = algorithm_row

            return (det_algorithm_rows, req_algorithm_rows)


        ## Script of self.write()
        ## ___________________________________________________________________________ ##

        # Build lists of formatted strings to be written to each GeoCSV
        gps_rows = []
        det_algorithm_rows = []
        req_algorithm_rows = []
        pressure_rows = []
        for complete_dive in self.complete_dives:
            # Get and extend lists of formatted "Measurement" rows
            gps_rows.extend(format_gps_rows(complete_dive))
            pressure_rows.extend(format_pressure_rows(complete_dive))

            # "Algorithm" formatted lists returned as (DET, REQ) tuple
            algorithm_rows_tup = format_algorithm_rows(complete_dive)
            det_algorithm_rows.extend(algorithm_rows_tup[0])
            req_algorithm_rows.extend(algorithm_rows_tup[1])

        # Remove pressure measurements taken before(after) first(last) GPS measurements
        # (currently: GPS dates, but not pressure dates, affected by `filterDate` in main.py)
        gps_dates = [x[1] for x in sorted(gps_rows, key=lambda x: x[1])]
        pressure_rows = [x for x in pressure_rows if x[1] > gps_dates[0] and x[1] < gps_dates[-1]]

        # The "Measurement:" rows are "GPS" and "Pressure"
        measurement_rows = gps_rows + pressure_rows

        # The complete file combines "Measurement" and "Algorithm" rows
        geocsv_det_rows = measurement_rows + det_algorithm_rows
        geocsv_req_rows = measurement_rows + req_algorithm_rows
        geocsv_det_req_rows = geocsv_det_rows + req_algorithm_rows

        # Sort the combined rows by date
        geocsv_det_req_rows.sort(key=lambda x: x[1])
        geocsv_det_rows.sort(key=lambda x: x[1])
        geocsv_req_rows.sort(key=lambda x: x[1])

        # Open as as 'wb' in Python 2 rather than 'w' with newline='' in Python 3
        # https://docs.python.org/2/library/csv.html#csv.writer
        basename = filename.strip('.csv') if filename.endswith('.csv') else filename
        with open(basename+'_DET_REQ.csv', 'wb') as csvfile_det_req, \
             open(basename+'_DET.csv', 'wb') as csvfile_det, \
             open(basename+'_REQ.csv', 'wb') as csvfile_req:

            # Define writer object for all three files
            # https://stackoverflow.com/questions/3191528/csv-in-python-adding-an-extra-carriage-return-on-windows
            csvwriter_det_req = csv.writer(csvfile_det_req, delimiter=self.delimiter, lineterminator=self.lineterminator)
            csvwriter_det = csv.writer(csvfile_det, delimiter=self.delimiter, lineterminator=self.lineterminator)
            csvwriter_req = csv.writer(csvfile_req, delimiter=self.delimiter, lineterminator=self.lineterminator)

            # Write the same header lines to all three files
            csvwriter_list = [csvwriter_det_req, csvwriter_det, csvwriter_req]
            for csvwriter in csvwriter_list:
                csvwriter.writerows(self.get_header_lines())

            # Write the combined "Measurement" and "Algorithm" rows to all three files
            csvwriter_det.writerows(geocsv_det_rows)
            csvwriter_req.writerows(geocsv_req_rows)
            csvwriter_det_req.writerows(geocsv_det_req_rows)

        print("Wrote: {}".format(csvfile_det.name))
        print("Wrote: {}".format(csvfile_req.name))
        print("Wrote: {}\n".format(csvfile_det_req.name))

        # Extra verifications: read file and check that lines are (1) sorted, and (2) unique
        with open(csvfile_det_req.name, 'r') as csvfile_det_req, \
             open(csvfile_det.name, 'r') as csvfile_det, \
             open(csvfile_req.name, 'r') as csvfile_req:

            len_header = len(self.get_header_lines())
            csvfile_list = [csvfile_det_req, csvfile_det, csvfile_req]
            for csvfile in csvfile_list:
                # Read
                csvreader = csv.reader(csvfile, delimiter=self.delimiter, lineterminator=self.lineterminator)
                rows = list(csvreader)

                # (1) Verify all dates sorted (skip header lines)
                dates = [row[1] for row in rows[len_header:]]
                if dates == sorted(dates):
                    print("Verified: {} rows sorted".format(csvfile.name))
                else:
                    raise ValueError("{} rows not sorted".format(csvfile.name))

                # (2) Verify all rows unique (include header lines)
                str_rows = [(',').join(row) for row in rows]
                if len(str_rows) == len(set(str_rows)):
                    print("Verified: {} rows unique\n".format(csvfile.name))

                else:
                    raise ValueError("{} rows not unique\n".format(csvfile.name))

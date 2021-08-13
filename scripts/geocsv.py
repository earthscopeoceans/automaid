# -*- coding: utf-8 -*-
#
# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v2.7)
#
# Developer: Joel D. Simon (JDS)
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified by JDS: 13-Aug-2021
# Last tested: Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit

# Todo:
#
# *Write (nested) function docstrings
# *Verify types and signs, e.g. for 'time correction/delay' ([+/-]np.int32)

import csv
import pytz
import warnings
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
        version (str): GeoCSV version (def: '2.0')
        delimiter (str): GeoCSV delimiter (def: ',')
        lineterminator (str): GeoCSV line terminator (def: '\n')

    """

    def __init__(self,
                 complete_dives,
                 creation_datestr=datetime.datetime.now(pytz.UTC).isoformat().split(".")[0]+"Z",
                 version='2.0',
                 delimiter=',',
                 lineterminator='\n'):

        if not all(isinstance(complete_dive, dives.Complete_Dive) for complete_dive in complete_dives):
            raise ValueError('Input `complete_dives` must be list of `dives.Complete_Dives` instances')

        self.complete_dives = complete_dives
        self.creation_datestr = creation_datestr
        self.version = version
        self.delimiter = delimiter
        self.lineterminator = lineterminator

        # Attach header lines
        self.dataset_header = ['#dataset: GeoCSV ' + self.version]
        self.created_header = ['#created: ' + self.creation_datestr]
        self.version_header = ['#automaid: {} ({})'.format(setup.get_version(), setup.get_url())]
        self.delimiter_header = ['#delimiter: ' + repr(self.delimiter)]
        self.lineterminator_header = ['#lineterminator: ' + repr(self.lineterminator)]

        self.field_unit_header = [
            '#field_unit',
            'ISO_8601',
            'unitless',
            'unitless',
            'unitless',
            'unitless',
            'degrees_north',
            'degrees_east',
            'meters',
            'meters',
            'unitless',
            'factor',
            'hertz',
            'unitless',
            'hertz',
            'seconds',
            'seconds'
        ]

        self.field_type_header = [
            '#field_type',
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
            'Depth',
            'SensorDescription',
            'Scale',
            'ScaleFrequency',
            'ScaleUnits',
            'SampleRate',
            'TimeDelay',
            'TimeCorrection'
        ]

        self.MethodIdentifier_Measurement = 'Measurement:GPS:{:s}'.format(utils.get_gps_instrument_name().replace(' ', '_'))
        self.MethodIdentifier_Algorithm = 'Algorithm:automaid:{:s}'.format(setup.get_version())

    def header_lines(self):
        return [self.dataset_header,
                self.created_header,
                self.version_header,
                self.delimiter_header,
                self.lineterminator_header,
                self.field_unit_header,
                self.field_type_header,
                self.MethodIdentifier_header]

    def write(self, filename='geo.csv'):
        """Write three GeoCSV for: all, 'DET', and 'REQ' events

        Args:
            filename (str): GeoCSV filename (def: 'geo.csv')

        """

        ## Functional prototypes for self.write()
        ## ___________________________________________________________________________ ##

        # Lambda functions to convert to float32 with specified precision
        d0 = lambda x: format(np.float32(x), '.0f')
        d1 = lambda x: format(np.float32(x), '.1f')
        d6 = lambda x: format(np.float32(x), '.6f')
        nan = np.float32('nan')

        def write_header_rows(csvwriter_list):
            """Write GeoCSV header rows

            Args:
                csvwriter_list (list):

            """
            for csvwriter in csvwriter_list:
                csvwriter.writerows(self.header_lines())

        def write_measurement_rows(csvwriter_list, complete_dive, flag):
            """Write rows of GPS measurements

            GPS metadata == 'measurement'

            Args:
                csvwriter_list (list):
                complete_dive (dives.Complete_Dive instance):
                flag (str):

            """

            # Determine what GPS fixes to write
            flag = flag.lower()
            if flag == 'all':
                gps_list = complete_dive.gps_list

            elif flag == 'before_dive':
                gps_list = complete_dive.gps_before_dive

            elif flag == 'after_dive':
                gps_list = complete_dive.gps_after_dive

            else:
                raise ValueError("flag must be one of: 'all', 'before_dive', or 'after_dive'")

            # Loop over all GPS instances and write single line for each
            for gps in sorted(gps_list, key=lambda x: x.date):
                measurement_row = [
                    self.MethodIdentifier_Measurement,
                    str(gps.date)[0:19]+'Z',
                    complete_dive.network,
                    complete_dive.kstnm,
                    '',
                    nan,
                    d6(gps.latitude),
                    d6(gps.longitude),
                    d0(0),
                    d0(0),
                    'MERMAIDHydrophone({:s})'.format(complete_dive.kinst),
                    nan,
                    nan,
                    '',
                    nan,
                    d6(gps.mseed_time_delay),
                    nan
                ]

                # Write the same GPS lines to all GeoCSV files
                for csvwriter in csvwriter_list:
                    csvwriter.writerow(measurement_row)

        def write_algorithm_rows(csvwriter, complete_dive, flag):
            """Write multiple rows of event (algorithm) values, some measured
            (e.g. "Depth", STDP), and some interpolated (e.g., "Latitude", STLA)

            Event metadata == 'algorithm'

            NB, cannot pass a list of writers here because, unlike the
            measurement rows (which are the same for all three files), this
            function must parse event lists between all, 'DET', and 'REQ' types.

            Args:
                csvwriter (writer): a single CSV writer
                complete_dive (dives.Complete_Dive instance):
                flag (str):

            """

            # Determine what events to write
            if flag == 'all':
                event_list = complete_dive.events

            elif flag == 'det':
                event_list = [event for event in complete_dive.events if not event.is_requested]

            elif flag == 'req':
                event_list = [event for event in complete_dive.events if event.is_requested]

            else:
                raise ValueError("flag must be one of: 'all', 'det', or 'req'")

            # Only keep events with an interpolated station location (STLA/STLO)
            event_list = [event for event in event_list if event.obspy_trace_stats]

            # Initialize a "previous" row to check for redundancies
            prev_algorithm_row = list()
            for event in sorted(event_list, key=lambda x: x.date):
                if event.station_loc_is_preliminary:
                    continue

                algorithm_row = [
                    self.MethodIdentifier_Algorithm,
                    str(event.obspy_trace_stats["starttime"])[:19]+'Z',
                    complete_dive.network,
                    complete_dive.kstnm,
                    '00',
                    event.obspy_trace_stats["channel"],
                    d6(event.obspy_trace_stats.sac["stla"]),
                    d6(event.obspy_trace_stats.sac["stlo"]),
                    d0(0),
                    d0(event.obspy_trace_stats.sac["stdp"]),
                    'MERMAIDHydrophone({:s})'.format(complete_dive.kinst),
                    d0(event.obspy_trace_stats.sac["scale"]),
                    d1(np.float32(1.)),
                    'Pa',
                    d1(event.obspy_trace_stats["sampling_rate"]),
                    nan,
                    d6(event.mseed_time_correction)
                ]

                # Write event ("algorithm") line to a single CSV file
                # (skipping redundant lines, e.g., for multiply-requested "REQ" files)
                if algorithm_row != prev_algorithm_row:
                    csvwriter.writerow(algorithm_row)

                # Overwrite "previous" row used to check for redundancies
                prev_algorithm_row = algorithm_row


        ## Script of self.write()
        ## ___________________________________________________________________________ ##

        # Parse basename from filename to later append "_DET.csv" and "_REQ.csv"
        basename = filename.strip('.csv') if filename.endswith('.csv') else filename

        # Open as as 'wb' in Python 2 rather than 'w' with newline='' in Python 3
        # https://docs.python.org/2/library/csv.html#csv.writer
        with open(basename+'_DET_REQ.csv', 'wb') as csvfile_all, \
             open(basename+'_DET.csv', 'wb') as csvfile_det, \
             open(basename+'_REQ.csv', 'wb') as csvfile_req:

            # Define writer object for all three files
            # https://stackoverflow.com/questions/3191528/csv-in-python-adding-an-extra-carriage-return-on-windows
            csvwriter_all = csv.writer(csvfile_all, delimiter=self.delimiter, lineterminator=self.lineterminator)
            csvwriter_det = csv.writer(csvfile_det, delimiter=self.delimiter, lineterminator=self.lineterminator)
            csvwriter_req = csv.writer(csvfile_req, delimiter=self.delimiter, lineterminator=self.lineterminator)

            # Compile list of all three files to pass into write functions
            csvwriter_list = [csvwriter_all, csvwriter_det, csvwriter_req]

            # Write headers to all three files
            write_header_rows(csvwriter_list)

            # Write metadata rows to all three files
            for complete_dive in sorted(self.complete_dives, key=lambda x: x.start_date):
                # Write ONLY this dive's GPS list --
                # Yes: `complete_dive.gps_before_dive` (or `after_dive`)
                # No: `complete_dive.gps_before_dive_incl_next_dive` (or `after_dive`)
                if complete_dive.gps_before_dive:
                    write_measurement_rows(csvwriter_list, complete_dive, 'before_dive')

                if complete_dive.events:
                    # Cannot input `csvwriter_list` because we must parse 'DET'
                    # and 'REQ' events between separate files
                    write_algorithm_rows(csvwriter_all, complete_dive, 'all')
                    write_algorithm_rows(csvwriter_det, complete_dive, 'det')
                    write_algorithm_rows(csvwriter_req, complete_dive, 'req')

                if complete_dive.gps_after_dive:
                    write_measurement_rows(csvwriter_list, complete_dive, 'after_dive')

        print("Wrote: {}".format(csvfile_all.name))
        print("Wrote: {}".format(csvfile_det.name))
        print("Wrote: {}\n".format(csvfile_req.name))

        # Extra verifications: read file and check that lines are (1) sorted, and (2) unique
        with open(csvfile_all.name, 'r') as csvfile_all, \
             open(csvfile_det.name, 'r') as csvfile_det, \
             open(csvfile_req.name, 'r') as csvfile_req:

            len_header = len(self.header_lines())
            csvfile_list = [csvfile_all, csvfile_det, csvfile_req]

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

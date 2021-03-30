# -*- coding: utf-8 -*-
#
# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v2.7)
#
# Developer: Joel D. Simon (JDS)
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified by JDS: 30-Mar-2021
# Last tested: Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit

# Todo:
#
# *Write (nested) function docstrings
# *Verify types and signs, e.g. for 'time correction/delay' ([+/-]np.int32)

import csv
import pickle
import numpy as np

import setup

class GeoCSV:
    """Organize MERMAID metadata and write them to GeoCSV format

    Args:
        dives (list): List of dives.Dive instances
        version (str): GeoCSV version (def: '2.0')
        delimiter (str): GeoCSV delimiter (def: ',')

    """

    def __init__(self, dives, version='2.0', delimiter=',', lineterminator='\n'):
        self.dives = sorted(dives, key=lambda x: x.log_name)
        self.version = version
        self.delimiter = delimiter
        self.lineterminator = lineterminator

        # Attach header lines
        self.dataset_header = ['#dataset: GeoCSV ' + self.version]
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

        def write_headers(csvwriter_list):
            """Write GeoCSV header rows

            Args:
                csvwriter_list (list):

            """
            for csvwriter in csvwriter_list:
                csvwriter.writerows([self.dataset_header,
                                     self.delimiter_header,
                                     self.lineterminator_header,
                                     self.field_unit_header,
                                     self.field_type_header,
                                     self.MethodIdentifier_header])


        def write_measurement_rows(csvwriter_list, dive, flag):
            """Write rows of GPS measurements

            GPS metadata == 'measurement'

            Args:
                csvwriter_list (list):
                dive (dives.Dive instance):
                flag (str):

            """

            # Determine what GPS fixes to write
            flag = flag.lower()
            if flag == 'all':
                gps_list = dive.gps_list

            elif flag == 'before_dive':
                gps_list = dive.gps_before_dive

            elif flag == 'after_dive':
                gps_list = dive.gps_after_dive

            else:
                raise ValueError("flag must be one of: 'all', 'before_dive', or 'after_dive'")

            # Loop over all GPS instances and write single line for each
            for gps in sorted(gps_list, key=lambda x:x.date):
                measurement_row = [
                    'Measurement:GPS:Trimble',
                    str(gps.date)[0:19]+'Z',
                    dive.network,
                    dive.kstnm,
                    '',
                    nan,
                    d6(gps.latitude),
                    d6(gps.longitude),
                    d0(0),
                    d0(0),
                    'MERMAIDHydrophone({:s})'.format(dive.kinst),
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

        def write_algorithm_rows(csvwriter, dive, flag):
            """Write multiple rows of event (algorithm) values, some measured
            (e.g. "Depth", STDP), and some interpolated (e.g., "Latitude", STLA)

            Event metadata == 'algorithm'

            NB, cannot pass a list of writers here because, unlike the
            measurement rows (which are the same for all three files), this
            function must parse event lists between all, 'DET', and 'REQ' types.

            Args:
                csvwriter (writer): a single CSV writer
                dive (dives.Dive instance):
                flag (str):

            """

            # Determine what events to write
            if flag == 'all':
                event_list = dive.events

            elif flag == 'det':
                event_list = [event for event in dive.events if not event.is_requested]

            elif flag == 'req':
                event_list = [event for event in dive.events if event.is_requested]

            else:
                raise ValueError("flag must be one of: 'all', 'det', or 'req'")

            # Only keep events with an interpolated station location (STLA/STLO)
            event_list = [event for event in event_list if event.station_loc is not None]

            for event in sorted(event_list, key=lambda x: x.station_loc.date):
                if event.station_loc_is_preliminary:
                    continue

                algorithm_row = [
                    'Algorithm:automaid:{:s}'.format(setup.get_version()),
                    str(event.obspy_trace_stats["starttime"])[:19]+'Z',
                    dive.network,
                    dive.kstnm,
                    '00',
                    event.obspy_trace_stats["channel"],
                    d6(event.obspy_trace_stats.sac["stla"]),
                    d6(event.obspy_trace_stats.sac["stlo"]),
                    d0(0),
                    d0(event.obspy_trace_stats.sac["stdp"]),
                    'MERMAIDHydrophone({:s})'.format(dive.kinst),
                    d0(event.obspy_trace_stats.sac["scale"]),
                    d1(np.float32(1.)),
                    'Pa',
                    d1(event.obspy_trace_stats["sampling_rate"]),
                    nan,
                    d6(event.mseed_time_correction)
                ]

                # Write (possibly multiple) event line(s) to a single CSV file
                csvwriter.writerow(algorithm_row)

        ## Script of self.write()
        ## ___________________________________________________________________________ ##

        # Parse basename from filename to later append "_DET.csv" and "_REQ.csv"
        basename = filename.strip('.csv') if filename.endswith('.csv') else filename

        # Open as as 'wb' in Python 2 rather than 'w' with newline='' in Python 3
        # https://docs.python.org/2/library/csv.html#csv.writer
        with open(basename+'.csv', 'wb') as csvfile_all, \
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
            write_headers(csvwriter_list)

            # Write metadata rows to all three files
            for dive in self.dives:
                if dive.is_dive:
                    # Write ONLY this dive's GPS list --
                    # Yes: `dive.gps_before_dive` (or `after_dive`)
                    # No: `dive.gps_before_dive_incl_next_dive` (or `after_dive`)
                    if dive.gps_before_dive is not None:
                        write_measurement_rows(csvwriter_list, dive, 'before_dive')

                    if dive.events is not None:
                        # Cannot input `csvwriter_list` because we must parse
                        # 'DET' and 'REQ' events to separate files
                        write_algorithm_rows(csvwriter_all, dive, 'all')
                        write_algorithm_rows(csvwriter_det, dive, 'det')
                        write_algorithm_rows(csvwriter_req, dive, 'req')

                    if dive.gps_after_dive is not None:
                        write_measurement_rows(csvwriter_list, dive, 'after_dive')

                else:
                    if dive.gps_list is not None:
                        write_measurement_rows(csvwriter_list, dive, 'all')


if __name__ == '__main__':
    dive_list = pickle.load(open('P008.p', 'rb'))
    geocsv = GeoCSV(dive_list)
    geocsv.write('test')

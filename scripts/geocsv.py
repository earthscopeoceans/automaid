# -*- coding: utf-8 -*-
#
# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v2.7)
#
# Author: Joel. D Simon
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified: 17-Dec-2020, Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit

import setup
import csv
import numpy as np
import pickle

class GeoCSV:
    """Organize MERMAID metadata and write them to GeoCSV format

    Args:
        dives (list): List of dives.Dive instances
        version (str): GeoCSV version (def: '2.0')
        delimiter (str): GeoCSV delimiter (def: ',')

    Attributes:
        dives (list): List of dives.Dive instances

    """

    def __init__(self, dives, version='2.0', delimiter=','):
        self.dives = sorted(dives, key=lambda x: x.log_name)
        self.version = version
        self.delimiter = ','

        # Define first two header lines
        self.dataset_header = ['#dataset: GeoCSV ' + self.version]
        self.delimiter_header = ['#delimiter: ' + self.delimiter]
        self.field_unit_header = ['#field_unit',
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
                                  'seconds']

        self.field_type_header = ['#field_type',
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
                                  'float']

        self.MethodIdentifier_header = ['MethodIdentifier',
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
                                        'TimeCorrection']


    def write(self, filename='geo.csv'):
        """Write (Geo)CSV file

        Args:
            filename (str): GeoCSV filename (def: 'geo.csv')

        """
        #filename.append('geocsv') if filename.split('.')[-1] != 'geocsv' else pass

        # lambdas to convert floats to numpy float32 with specified precision
        d0 = lambda x: format(np.float32(x), '.0f')
        d1 = lambda x: format(np.float32(x), '.1f')
        d6 = lambda x: format(np.float32(x), '.6f')
        nan = np.float32('nan')

        def write_headers(csvwriter):
            """Write GeoCSV header rows

            Args:
                csvwriter (writer): csv.writer object for open file

            """
            csvwriter.writerows([self.dataset_header,
                                 self.delimiter_header,
                                 self.field_unit_header,
                                 self.field_type_header,
                                 self.MethodIdentifier_header])


        def write_measurement_rows(csvwriter, dive, flag):
            """Write rows of GPS measurements (all, before, or after dive)

            Args:
                dive (dives.Dive instance):
                gps_list (list):

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
                print 'bad flag'

            # Loop over all GPS instances and write single line for each
            for gps in sorted(gps_list, key=lambda x:x.date):
                measurement_row = ['Measurement:GPS:Trimble',
                                   str(gps.date)[0:19]+'Z',
                                   dive.network,
                                   dive.kstnm,
                                   '',
                                   nan,
                                   d6(gps.latitude),
                                   d6(gps.latitude),
                                   d0(0),
                                   d0(0),
                                   'MERMAIDHydrophone({:s})'.format(dive.kinst),
                                   nan,
                                   nan,
                                   '',
                                   nan,
                                   d6(-1*gps.clockdrift), # MER delay = (-) clockdrift
                                   nan]

                csvwriter.writerow(measurement_row)

        def write_algorithm_rows(csvwriter, dive, flag):
            """Write multiple rows of event (algorithm) values, some measured
            (e.g. "Depth", STDP), and some interpolated (e.g., "Latitude", STLA)



            Args:
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
                print 'bad flag'

            # Only keep events with an interpolated station location (STLA/STLO)
            event_list = [event for event in event_list if event.station_loc is not None]

            for event in sorted(event_list, key=lambda x: x.station_loc.date):
                algorithm_row = ['Algorithm:automaid:{:s}'.format(setup.get_version()),
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
                                 d6(event.clockdrift_correction)]

                csvwriter.writerow(algorithm_row)

        # Parse basename from filename to later append "_DET.csv" and "_REQ.csv"
        basename = filename.strip('.csv') if filename.endswith('.csv') else filename

        # Open as as 'wb' in Python 2 rather than 'w' with newline='' in Python 3
        # https://docs.python.org/2/library/csv.html#csv.writer
        with open(basename+'.csv', 'wb') as csvfile_all, \
             open(basename+'_DET.csv', 'wb') as csvfile_det, \
             open(basename+'_REQ.csv', 'wb') as csvfile_req:

            # Define csv.writer object for all three files
            csvwriter_all = csv.writer(csvfile_all, delimiter=self.delimiter)
            csvwriter_det = csv.writer(csvfile_det, delimiter=self.delimiter)
            csvwriter_req = csv.writer(csvfile_req, delimiter=self.delimiter)

            # Write headers
            write_headers(csvwriter_all)
            write_headers(csvwriter_det)
            write_headers(csvwriter_req)

            # Write metadata rows
            for dive in self.dives:
                len_gps = 0;
                len_gps_before = 0;
                len_gps_after = 0;

                if dive.is_dive:
                    # Write this dive's GPS (mind prev/next dive list overlap)
                    # Yes: dive.gps_before_dive
                    # No: dive.gps_before_dive_incl_next_dive

                    len_gps = len(dive.gps_list)
                    if dive.gps_before_dive is not None:
                        write_measurement_rows(csvwriter_all, dive, 'before_dive')
                        write_measurement_rows(csvwriter_det, dive, 'before_dive')
                        write_measurement_rows(csvwriter_req, dive, 'before_dive')
                        len_gps_before = len(dive.gps_before_dive)

                    if dive.events is not None:
                        write_algorithm_rows(csvwriter_all, dive, 'all')
                        write_algorithm_rows(csvwriter_det, dive, 'det')
                        write_algorithm_rows(csvwriter_req, dive, 'req')

                    if dive.gps_after_dive is not None:
                        write_measurement_rows(csvwriter_all, dive, 'after_dive')
                        write_measurement_rows(csvwriter_det, dive, 'after_dive')
                        write_measurement_rows(csvwriter_req, dive, 'after_dive')
                        len_gps_after = len(dive.gps_after_dive)

                else:
                    if dive.gps_list is not None:
                        write_measurement_rows(csvwriter_all, dive, 'all')
                        write_measurement_rows(csvwriter_det, dive, 'all')
                        write_measurement_rows(csvwriter_req, dive, 'all')

                if len_gps != len_gps_before + len_gps_after:
                    import ipdb; ipdb.set_trace()


if __name__ == '__main__':
    dive_list = pickle.load(open('P008.p', 'rb'))
    geocsv = GeoCSV(dive_list)
    geocsv.write('test')

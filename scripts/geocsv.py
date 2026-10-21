# -*- coding: utf-8 -*-
#
# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v3.10)
#
# Developer: Joel D. Simon (JDS)
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified by JDS: 16-May-2025
# Last tested: Python 3.10.13, Darwin Kernel Version 23.6.0

# Todo:
#
# *Add `read` method at module level
# *Convert most of current GeoCSV guts to `write` method at module level
# *Main GeoCSV object should organize (dict?) file columns (w/o class-level read/write methods)
# *Write (nested) function docstrings
# *Verify types and signs, e.g. for 'time correction/delay' ([+/-]np.int32)

import csv
import hashlib
import pytz
import datetime
import numpy as np

import cycles
import setup
import utils
from collections import Counter

class GeoCSV:
    """Organize MERMAID metadata and write them to GeoCSV format

    Args:
        cycles (list): List of cycles.Cycle instances
        creation_datestr (str): File-creation datestr as "YYYY-MM-DDTHH:MM:SS.sssZ"
        mixed_layer_depth_m (float): Depth to thermocline in meters positive down (def: np.float64('nan'))
        delimiter (str): GeoCSV delimiter (def: ',')
        lineterminator (str): GeoCSV line terminator (def: '\n')

    """

    def __init__(self,
                 cycle_list,
                 creation_datestr = datetime.datetime.now(pytz.UTC).isoformat()[:23] + "Z",
                 mixed_layer_depth_m = np.float64('nan'),
                 delimiter=',',
                 lineterminator='\n'):

        if not all(isinstance(cycle, cycles.Cycle) for cycle in cycle_list):
            raise ValueError('Input `cycle_list` must be list of `cycles.Cycle` instances')

        self.cycles = cycle_list
        self.creation_datestr = creation_datestr
        self.mixed_layer_depth_m = mixed_layer_depth_m
        self.delimiter = delimiter
        self.lineterminator = lineterminator

        # Comments (multiple, some keywords required, start with # or "#)
        self.dataset_comment = ['#dataset: GeoCSV']
        self.created_comment = ['#created: ' + self.creation_datestr]
        self.description_comment = ['#description: Metadata for drifting Mobile Earthquake Recording in Marine Areas by Independent Divers (MERMAID) hydrophones, www.EarthScopeOceans.org']
        self.attribution_comment = ['#attribution: automaid {} ({})'.format(setup.get_version(), setup.get_url())]
        #self.matlab_comment = ['#matlab_reader: https://github.com/joelsimon/GeoCSV/blob/master/readGeoCSV.m']
        #self.waterpressure_comment = ['#waterpressure2depth: 100 mbar is approximately equal to the pressure of 1 meter of water']
        #self.response_comment = ["#frequency_response: http://ds.iris.edu/data/reports/MH/MH.Mermaids.Response.V3.pdf"]

        self.lineterminator_comment = ['#lineterminator: ' + repr(self.lineterminator)]
        self.delimiter_comment = ['#delimiter: ' + repr(self.delimiter)]
        self.field_unit_comment = [
            # Keyword and first value must be together so that csvwriter does
            # not put a comment between the two (i.e. "#field_unit: ,unitless")
            '#field_unit: unitless',
            'iso8601',
            'unitless',
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
            'unitless',
            'seconds',
            'seconds'
        ]
        self.field_type_comment = [
            # Keyword and first value must be together so that csvwriter does
            # not put a comment between the two (i.e. "#field_type: ,string")
            '#field_type: string',
            'datetime',
            'string',
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
            'integer',
            'float',
            'float'
        ]

        # Header line (single, first uncommented line after some comment(s))
        self.header = [
            'MethodIdentifier',
            'StartTime',
            'Network',
            'Station',
            'Location',
            'Channel',
            'DataQuality',
            'Latitude',
            'Longitude',
            'Elevation',
            'WaterPressure',
            'InstrumentDescription',
            'SampleRate',
            'SampleCount',
            'TimeDelay',
            'TimeCorrection'
        ]

        self.MethodIdentifier_GPS = 'Measurement:GPS:{:s}'.format(utils.get_gps_sensor_name().replace(' ', '_'))
        self.MethodIdentifier_Pressure = 'Measurement:Pressure:{:s}'.format(utils.get_absolute_pressure_sensor_name().replace(' ', '_'))
        self.MethodIdentifier_Algorithm_Event = 'Algorithm(event):automaid:{:s}'.format(setup.get_version())
        self.MethodIdentifier_Algorithm_Thermocline = 'Algorithm(thermocline):automaid:{:s}'.format(setup.get_version())

    def get_comment_lines(self):
        comment_lines = [
            self.dataset_comment,
            self.created_comment,
            self.description_comment,
            self.attribution_comment,
            #self.matlab_comment,
            #self.waterpressure_comment,
            #self.response_comment,
            self.lineterminator_comment,
            self.delimiter_comment,
            self.field_unit_comment,
            self.field_type_comment,
        ]
        #print(comment_lines)
        return comment_lines

    def write(self, filename='geo.csv'):
        """Write three GeoCSV files: both 'DET' and 'REQ'; only 'DET'; and only 'REQ'

        Args:
            filename (str): root GeoCSV filename, to be appended (def: 'geo.csv')
                            'geo.csv' -> 'geo_DET_REQ.csv', 'geo_DET.csv', 'geo_DET_REQ.csv'

        """

        ## Functional prototypes for self.write()
        ## ___________________________________________________________________________ ##

        def check_float64(value):
            """Accept Python float or NumPy float64 without hiding other float types."""
            if isinstance(value, np.floating) and not isinstance(value, np.float64):
                raise TypeError(
                    f"GeoCSV requires float or numpy.float64; got {type(value).__name__}: {value!r}")
            return value

        # Check floating-point inputs before conversion; integers and pressure strings are valid.
        d0 = lambda x: format(np.float64(check_float64(x)), '.0f')
        d1 = lambda x: format(np.float64(check_float64(x)), '.1f')
        d6 = lambda x: format(np.float64(check_float64(x)), '.6f')
        nan = np.float64('nan')
        check_float64(self.mixed_layer_depth_m)

        def format_gps_rows(cycle):
            """Format GeoCSV rows of GPS measurements

            GPS metadata == 'Measurement'

            Args:
                cycle (cycles.Cycle instance):

            """

            # Loop over all GPS instances and write single line for each
            gps_rows = []
            for gps in sorted(cycle.gps_list, key=lambda x: x.date):
                gps_rows.append([
                    self.MethodIdentifier_GPS,
                    str(gps.date)[:23]+'Z',
                    cycle.network,
                    cycle.kstnm,
                    nan,
                    nan,
                    nan,
                    d6(gps.latitude),
                    d6(gps.longitude),
                    nan,
                    nan,
                    'MERMAIDHydrophone({:s})'.format(cycle.kinst),
                    nan,
                    nan,
                    d6(gps.mseed_time_delay),
                    nan
                ])

            return gps_rows

        def format_press_rows(cycle):
            """Format GeoCSV rows of mbar absolute pressure measurements

            pressure metadata == 'Measurement'

            Args:
                cycle (cycles.Cycle instance):

            """

            # Initialize a "previous" row to check for redundancies
            # This can occur when, e.g., "[SURFIN ..." and "[PRESS ..." print same info in .LOG
            # (07_5B773AF5.LOG, lines 916 and 917)
            press_rows = []
            prev_pressure_row = []
            for pressure in sorted(cycle.pressure_mbar, key=lambda x:x[1]):
                pressure_row = [
                    self.MethodIdentifier_Pressure,
                    str(pressure[1])[:23]+'Z',
                    cycle.network,
                    cycle.kstnm,
                    nan,
                    nan,
                    nan,
                    nan,
                    nan,
                    nan,
                    d0(pressure[0]),
                    'MERMAIDHydrophone({:s})'.format(cycle.kinst),
                    nan,
                    nan,
                    nan,
                    nan
                ]

                if pressure_row != prev_pressure_row:
                    press_rows.append(pressure_row)

                prev_pressure_row = pressure_row

            return press_rows

        def format_algo_event_rows(cycle):
            """Format GeoCSV rows of event metadata (e.g., starttime and MERMAID location)

            Event metadata == 'Algorithm'

            Args:
                cycle (cycles.Cycle instance)

            """

            # Only keep events with an interpolated station location (STLA/STLO)
            ## !! Is this condition good enough / algorithm rows match DET SAC? !!
            event_list = [event for log in cycle.logs for event in log.events if event.obspy_trace_stats]

            det_algo_records = []
            req_algo_records = []
            for event in sorted(event_list, key=lambda x: x.corrected_starttime):
                if event.station_loc_is_preliminary:
                    continue

                algorithm_row = [
                    self.MethodIdentifier_Algorithm_Event,
                    str(event.obspy_trace_stats["starttime"])[:23]+'Z',
                    cycle.network,
                    cycle.kstnm,
                    event.obspy_trace_stats["location"],
                    event.obspy_trace_stats["channel"],
                    event.obspy_trace_stats.mseed["dataquality"],
                    d6(event.obspy_trace_stats.sac["stla"]),
                    d6(event.obspy_trace_stats.sac["stlo"]),
                    nan,
                    d0(event.pressure_mbar),
                    'MERMAIDHydrophone({:s})'.format(cycle.kinst),
                    d6(event.obspy_trace_stats["sampling_rate"]),
                    event.obspy_trace_stats["npts"],
                    nan,
                    d6(event.mseed_time_correction)
                ]

                if event.is_requested:
                    req_algo_records.append((algorithm_row, event))

                else:
                    # Sanity checks just to make sure all "depth" units in their expected mbar
                    # The manual says 1 m = 101 mbar; automaid has always assumed 1 m = 1 dbar = 100 mbar
                    # (MERMAID manual Réf : 452.000.852 Version 00)
                    if event.pressure_dbar * 100 != event.pressure_mbar:
                        raise ValueError("Expected 100 mbar to equal 1 dbar")

                    if event.pressure_dbar is not event.obspy_trace_stats.sac["stdp"]:
                        raise ValueError("`stdp` (roughly meters) should be the dbar pressure from .MER")

                    det_algo_records.append((algorithm_row, event))

            return (det_algo_records, req_algo_records)

        def deduplicate_algo_event_rows(algo_records):
            """Return unique event rows and groups with conflicting event data.

            Rows are deduplicated only when both the raw event header and raw
            payload bytes are identical.  Distinct event data that render to the
            same GeoCSV row are retained in the clash record for human review;
            only the first such row is written so that the GeoCSV remains unique.
            """

            row_variants = {}
            unique_rows = []
            for row, event in algo_records:
                # Use the values as rendered in GeoCSV, including a stable
                # representation of NaN, to find duplicate output rows.
                row_key = tuple(str(value) for value in row)
                event_data = (event.mer_binary_header, event.mer_binary_binary)
                variants = row_variants.setdefault(row_key, [])

                for variant in variants:
                    if event_data == variant['event_data']:
                        variant['mer_binary_names'].append(event.mer_binary_name)
                        break
                else:
                    variants.append({
                        'event_data': event_data,
                        'mer_binary_names': [event.mer_binary_name],
                        'row': row,
                    })
                    if len(variants) == 1:
                        unique_rows.append(row)

            clashes = [variants for variants in row_variants.values()
                       if len(variants) > 1]
            return unique_rows, clashes

        def write_clash_report(report_name, clashes):
            """Write event data that collide in a GeoCSV row for review."""

            with open(report_name, 'w') as report:
                report.write('# GeoCSV event-data clashes\n\n')
                report.write('Each group below rendered to one identical GeoCSV '
                             'row, but its event header and/or raw data payload '
                             'differed.  The first variant was retained in the '
                             'corresponding GeoCSV; all variants are listed here.\n')

                for clash_index, variants in enumerate(clashes, start=1):
                    report.write('\n## Clash {}\n\n'.format(clash_index))
                    report.write('```text\n{}\n```\n\n'.format(
                        self.delimiter.join(str(value) for value in variants[0]['row'])))
                    report.write('| Event data variant | Source MER files | Header SHA-256 | '
                                 'Payload bytes | Payload SHA-256 |\n')
                    report.write('| --- | --- | --- | ---: | --- |\n')
                    for variant_index, variant in enumerate(variants, start=1):
                        header, payload = variant['event_data']
                        report.write('| {} | `{}` | `{}` | {} | `{}` |\n'.format(
                            variant_index,
                            '`, `'.join(variant['mer_binary_names']),
                            hashlib.sha256(header).hexdigest(),
                            len(payload),
                            hashlib.sha256(payload).hexdigest()))

        def validate_required_fields(rows):
            """Ensure fields required by every GeoCSV data row are populated."""

            required_fields = [
                'MethodIdentifier',
                'StartTime',
                'Network',
                'Station',
                'InstrumentDescription',
            ]
            required_indices = [self.header.index(field) for field in required_fields]
            for row_number, row in enumerate(rows, start=1):
                for field, index in zip(required_fields, required_indices):
                    value = row[index]
                    normalized_value = '' if value is None else str(value).strip()
                    if not normalized_value or normalized_value.lower() == 'nan':
                        raise ValueError(
                            "GeoCSV required field '{}' is empty in data row {}: {}".format(
                                field, row_number,
                                self.delimiter.join(str(item) for item in row)))

        def format_algo_thermo_rows(cycle):
            """Format GeoCSV rows of interpolated dates and lat/lons of des(as)cending into(out of) the thermocline

            Passage into/out of thermocline == 'Algorithm' (interpolated)

            Args:
                cycle (cycles.Cycle instance):

            """

            thermo_algo_rows = []
            descent = cycle.descent_leave_surface_layer_loc
            ascent =  cycle.ascent_reach_surface_layer_loc
            for thermo in [descent, ascent]:
                if thermo is None:
                    continue

                thermo_algo_rows.append([
                    self.MethodIdentifier_Algorithm_Thermocline,
                    str(thermo.date)[:23]+'Z',
                    cycle.network,
                    cycle.kstnm,
                    nan,
                    nan,
                    nan,
                    d6(thermo.latitude),
                    d6(thermo.longitude),
                    nan,
                    self.mixed_layer_depth_m * 100,
                    'MERMAIDHydrophone({:s})'.format(cycle.kinst),
                    nan,
                    nan,
                    nan,
                    nan
                ])

            return thermo_algo_rows

        ## Script of self.write()
        ## ___________________________________________________________________________ ##

        # Build lists of formatted strings to be written to each GeoCSV
        gps_rows = []
        det_algo_records = []
        req_algo_records = []
        thermo_algo_rows = []
        press_rows = []
        for cycle in self.cycles:
            # Get and extend lists of formatted "Measurement" rows
            gps_rows.extend(format_gps_rows(cycle))
            press_rows.extend(format_press_rows(cycle))

            # "Algorithm" event rows, paired with their source Event instances
            algo_rows_tup = format_algo_event_rows(cycle)
            det_algo_records.extend(algo_rows_tup[0])
            req_algo_records.extend(algo_rows_tup[1])

            # "Algorithm"-thermocline formatted rows
            thermo_algo_rows.extend(format_algo_thermo_rows(cycle))

        # Remove pressure measurements taken before(after) first(last) GPS measurements
        # (currently: GPS dates, but not pressure dates, affected by `filterDate` in main.py)
        #print(gps_rows)
        gps_dates = [x[1] for x in sorted(gps_rows, key=lambda x: x[1])]
        try:
            press_rows = [x for x in press_rows if x[1] > gps_dates[0] and x[1] < gps_dates[-1]]
        except IndexError:
            pass

        # The "Measurement:" rows are "GPS" and "Pressure"
        meas_rows = gps_rows + press_rows

        # Deduplicate each GeoCSV independently: an event may occur in the
        # combined DET_REQ file without occurring in the corresponding DET or
        # REQ file.
        det_algo_rows, det_clashes = deduplicate_algo_event_rows(det_algo_records)
        req_algo_rows, req_clashes = deduplicate_algo_event_rows(req_algo_records)
        det_req_algo_rows, det_req_clashes = deduplicate_algo_event_rows(
            det_algo_records + req_algo_records)

        # The complete file combines "Measurement" and "Algorithm" rows
        geocsv_det_rows = meas_rows + det_algo_rows + thermo_algo_rows
        geocsv_req_rows = meas_rows + req_algo_rows + thermo_algo_rows
        geocsv_det_req_rows = meas_rows + det_req_algo_rows + thermo_algo_rows

        # These identifiers are required on every data row, independent of
        # measurement or algorithm type.  Validate the superset before writing
        # any of the three output variants.
        validate_required_fields(geocsv_det_req_rows)

        # Sort the combined rows by date
        geocsv_det_req_rows.sort(key=lambda x: x[1])
        geocsv_det_rows.sort(key=lambda x: x[1])
        geocsv_req_rows.sort(key=lambda x: x[1])

        # Open as as 'wb' in Python 2 rather than 'w' with newline='' in Python 3
        # https://docs.python.org/2/library/csv.html#csv.writer
        basename = filename.strip('.csv') if filename.endswith('.csv') else filename
        with open(basename+'_DET_REQ.csv', 'w', newline='') as csvfile_det_req, \
             open(basename+'_DET.csv', 'w', newline='') as csvfile_det, \
             open(basename+'_REQ.csv', 'w', newline='') as csvfile_req:

            # Define writer object for all three files
            # https://stackoverflow.com/questions/3191528/csv-in-python-adding-an-extra-carriage-return-on-windows
            csvwriter_det_req = csv.writer(csvfile_det_req, delimiter=self.delimiter, lineterminator=self.lineterminator)
            csvwriter_det = csv.writer(csvfile_det, delimiter=self.delimiter, lineterminator=self.lineterminator)
            csvwriter_req = csv.writer(csvfile_req, delimiter=self.delimiter, lineterminator=self.lineterminator)

            # Write the same comment lines and single header to all three files
            csvfile_list = [csvfile_det_req, csvfile_det, csvfile_req]
            csvwriter_list = [csvwriter_det_req, csvwriter_det, csvwriter_req]
            for csvfile, csvwriter in zip(csvfile_list, csvwriter_list):
                for comment_fields in self.get_comment_lines():
                    csvfile.write(self.delimiter.join(comment_fields) + self.lineterminator)
                csvwriter.writerow(self.header)

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

            len_comment = len(self.get_comment_lines())
            csvfile_list = [csvfile_det_req, csvfile_det, csvfile_req]
            for csvfile in csvfile_list:
                # Read
                csvreader = csv.reader(csvfile, delimiter=self.delimiter, lineterminator=self.lineterminator)
                rows = list(csvreader)

                # (1) Verify all dates sorted (skip comments and single header line)
                # NB, this assumes all comments grouped and contiguous at top of file
                dates = [row[1] for row in rows[len_comment+1:]]
                if dates == sorted(dates):
                    print("Verified: {} rows sorted".format(csvfile.name))
                else:
                    raise ValueError("{} rows not sorted".format(csvfile.name))

                # (2) Verify all rows unique (include comments and header line)
                str_rows = [(',').join(row) for row in rows]
                if len(str_rows) == len(set(str_rows)):
                    print("Verified: {} rows unique\n".format(csvfile.name))

                else:
                    nunique = [k for (k,v) in Counter(str_rows).items() if v > 1]
                    print(nunique)
                    raise ValueError("{} rows not unique\n".format(csvfile.name))

        clash_reports = [
            (basename+'_DET_REQ-CLASHES.md', det_req_clashes),
            (basename+'_DET-CLASHES.md', det_clashes),
            (basename+'_REQ-CLASHES.md', req_clashes),
        ]
        written_clash_reports = []
        for report_name, clashes in clash_reports:
            if clashes:
                write_clash_report(report_name, clashes)
                written_clash_reports.append(report_name)

        if written_clash_reports:
            print("WARNING: distinct event data rendered to duplicate GeoCSV rows; "
                  "review {}".format(', '.join(written_clash_reports)))

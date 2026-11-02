# -*- coding: utf-8 -*-
#
# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v3.10)
#
# Developer: Joel D. Simon (JDS)
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com

import csv
import hashlib
import io
import json
from pathlib import Path
import re
import pytz
import datetime
from decimal import Decimal, ROUND_HALF_EVEN
from obspy import UTCDateTime
import numpy as np

import cycles
import setup
import utils
from collections import Counter


def _format_utc(value):
    """Serialize an epoch to six UTC digits, rounding exact ties to even."""
    if isinstance(value, str):
        # The caller may supply an epoch with coarser or finer precision.
        # This formats a new file identity; it never rewrites an existing file.
        match = re.fullmatch(r"([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2})(?:\.([0-9]+))?Z", value)
        if match is None:
            raise ValueError("GeoCSV source timestamp requires explicit UTC Z")
        base = datetime.datetime.strptime(match[1], "%Y-%m-%dT%H:%M:%S")
        fraction = Decimal('0.' + match[2]) if match[2] else Decimal(0)
        micros = int((fraction * 1_000_000).to_integral_value(rounding=ROUND_HALF_EVEN))
        return (base + datetime.timedelta(microseconds=micros)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    if isinstance(value, datetime.datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("GeoCSV timestamp requires an explicit timezone")
        value = UTCDateTime(value)
    if not isinstance(value, UTCDateTime):
        raise TypeError("GeoCSV timestamp requires UTCDateTime or aware datetime")
    microseconds = int((Decimal(value.ns) / 1000).to_integral_value(rounding=ROUND_HALF_EVEN))
    seconds, fraction = divmod(microseconds, 1_000_000)
    return UTCDateTime(seconds).strftime("%Y-%m-%dT%H:%M:%S") + f".{fraction:06d}Z"


def _write_clash_json(path, clashes):
    """Bind producer clash findings to the exact combined GeoCSV output."""
    path = Path(path)
    locations = {}
    with path.open(encoding="utf-8", newline="") as stream:
        comments = 0
        while True:
            position = stream.tell()
            line = stream.readline()
            if not line.startswith("#"):
                stream.seek(position)
                break
            comments += 1
        reader = csv.reader(stream, strict=True)
        next(reader)  # Column header.
        previous_line = reader.line_num
        for index, row in enumerate(reader):
            locations[tuple(row)] = (index, comments + previous_line + 1)
            previous_line = reader.line_num
    entries = []
    for variants in clashes:
        index, line = locations[tuple(str(value) for value in variants[0]['row'])]
        sources = []
        for variant in variants:
            header, payload = variant['event_data']
            fields = {}
            for element, attributes in re.findall(r'<([\w-]+)\s+([^<>]*?)/?>', header.decode('utf-8')):
                for key, value in re.findall(r'([\w-]+)=([^\s]+)', attributes):
                    fields[f"{element}.{key}"] = value
            for name in sorted(set(variant['mseed_filenames'])):
                sources.append((name, fields, header, payload))
        sources.sort(key=lambda item: item[0])
        if len({item[0] for item in sources}) != len(sources):
            raise ValueError("distinct clash variants have the same MiniSEED basename")
        differences = []
        for key in sorted(set().union(*(item[1] for item in sources))):
            if len({(key in item[1], item[1].get(key)) for item in sources}) == 1:
                continue
            values = []
            for name, fields, _, _ in sources:
                value = {"mseed_filename": name}
                if key in fields:
                    value["value"] = fields[key]
                else:
                    value["present"] = False
                values.append(value)
            differences.append({"field": key, "values": values})
        # Preserve differences outside parsed attributes (including whitespace).
        shapes = {re.sub(r'(?<==)[^\s]+', '', item[2].decode('utf-8')) for item in sources}
        if len(shapes) > 1:
            differences.append({"field": "raw_header", "values": [
                {"mseed_filename": item[0], "value": item[2].decode('utf-8')}
                for item in sources]})
        entries.append({"source_index": index, "source_line": line,
                        "variant_count": len(variants),
                        "mseed_filenames": [item[0] for item in sources],
                        "header_differences": differences,
                        "payload_bytes_identical": len({item[3] for item in sources}) == 1})
    report = {"schema_version": 1,
              "geocsv_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
              "clashes": sorted(entries, key=lambda item: item['source_index'])}
    path.with_name('geocsv-clash.json').write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + '\n',
        encoding='utf-8')

class GeoCSV:
    """Organize MERMAID metadata and write them to GeoCSV format

    Args:
        cycles (list): List of cycles.Cycle instances
        creation_datestr (str): File-creation datestr as "YYYY-MM-DDTHH:MM:SS.ffffffZ"
        mixed_layer_depth_m (float): Configured upper mixed-layer depth in meters positive down (def: np.float64('nan'))
        delimiter (str): GeoCSV delimiter (def: ',')
        lineterminator (str): GeoCSV line terminator (def: '\n')

    """

    def __init__(self,
                 cycle_list,
                 creation_datestr = None,
                 mixed_layer_depth_m = np.float64('nan'),
                 delimiter=',',
                 lineterminator='\n'):

        if not all(isinstance(cycle, cycles.Cycle) for cycle in cycle_list):
            raise ValueError('Input `cycle_list` must be list of `cycles.Cycle` instances')

        self.cycles = cycle_list
        self.creation_datestr = _format_utc(
            datetime.datetime.now(pytz.UTC) if creation_datestr is None else creation_datestr)
        self.mixed_layer_depth_m = mixed_layer_depth_m
        if delimiter != ',' or lineterminator != '\n':
            raise ValueError("MERMAID GeoCSV requires comma delimiters and LF endings")
        self.delimiter = delimiter
        self.lineterminator = lineterminator

        # Comments (multiple, some keywords required, start with # or "#)
        self.schema_comment = ['# MERMAID GeoCSV schema: 1.0.0']
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
            'Time',
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
            'ClockOffset',
            'TimeCorrectionApplied'
        ]

        self.MethodIdentifier_GPS = 'Measurement:Position:{:s}'.format(utils.get_gps_sensor_name().replace(' ', '_'))
        self.MethodIdentifier_Pressure = 'Measurement:Pressure-Absolute:{:s}'.format(utils.get_absolute_pressure_sensor_name().replace(' ', '_'))
        self.MethodIdentifier_Algorithm_Event = 'Derivation:Recording:automaid-{:s}'.format(setup.get_version())
        self.MethodIdentifier_Crossing_Descent = 'Interpolation:Crossing-Descent:automaid-{:s}'.format(setup.get_version())
        self.MethodIdentifier_Crossing_Ascent = 'Interpolation:Crossing-Ascent:automaid-{:s}'.format(setup.get_version())

    def get_comment_lines(self):
        comment_lines = [
            self.schema_comment,
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

        def number(value, digits, *, optional=False):
            # Internal absent numeric observations are NaN/None, never the
            # nonempty string "nan". Required observations must be present.
            check_float64(value)
            if value is None or (isinstance(value, (float, np.float64)) and np.isnan(value)):
                if optional:
                    return ''
                raise ValueError("Missing required GeoCSV numeric source value")
            numeric = np.float64(value)
            if not np.isfinite(numeric):
                raise ValueError(f"Invalid GeoCSV numeric source value: {value!r}")
            return format(numeric, f'.{digits}f')

        d0 = lambda x: number(x, 0)
        d6 = lambda x: number(x, 6)
        absent = ''

        def instrument(cycle):
            if not isinstance(cycle.kinst, str) or not cycle.kinst.strip():
                raise ValueError("Missing required MERMAID model")
            return f'MERMAID_{cycle.kinst}'
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
                    _format_utc(gps.date),
                    cycle.network,
                    cycle.kstnm,
                    absent,
                    absent,
                    absent,
                    d6(gps.latitude),
                    d6(gps.longitude),
                    absent,
                    absent,
                    instrument(cycle),
                    absent,
                    absent,
                    number(gps.mseed_time_delay, 6, optional=True),
                    absent
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
                    _format_utc(pressure[1]),
                    cycle.network,
                    cycle.kstnm,
                    absent,
                    absent,
                    absent,
                    absent,
                    absent,
                    absent,
                    d0(pressure[0]),
                    instrument(cycle),
                    absent,
                    absent,
                    absent,
                    absent
                ]

                if pressure_row != prev_pressure_row:
                    press_rows.append(pressure_row)

                prev_pressure_row = pressure_row

            return press_rows

        def format_algo_event_rows(cycle):
            """Format GeoCSV rows of event metadata (e.g., starttime and MERMAID location)

            Recording rows describe original waveform segments.

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
                    _format_utc(event.obspy_trace_stats["starttime"]),
                    cycle.network,
                    cycle.kstnm,
                    ('  ' if event.obspy_trace_stats["location"] == ''
                     else event.obspy_trace_stats["location"]),
                    event.obspy_trace_stats["channel"],
                    event.obspy_trace_stats.mseed["dataquality"],
                    d6(event.obspy_trace_stats.sac["stla"]),
                    d6(event.obspy_trace_stats.sac["stlo"]),
                    '0',
                    number(event.pressure_mbar, 0, optional=event.is_requested),
                    instrument(cycle),
                    d6(event.obspy_trace_stats["sampling_rate"]),
                    event.obspy_trace_stats["npts"],
                    absent,
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

                    if event.pressure_dbar != event.obspy_trace_stats.sac["stdp"]:
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
                        variant['mseed_filenames'].append(Path(event.processed_file_name + '.mseed').name)
                        break
                else:
                    variants.append({
                        'event_data': event_data,
                        'mer_binary_names': [event.mer_binary_name],
                        'mseed_filenames': [Path(event.processed_file_name + '.mseed').name],
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
                'Time',
                'Network',
                'Station',
                'InstrumentDescription',
            ]
            for row_number, row in enumerate(rows, start=1):
                source = dict(zip(self.header, row))
                required = list(required_fields)
                subject = source['MethodIdentifier'].split(':')[1]
                if subject == 'Position':
                    required += ['Latitude', 'Longitude']
                elif subject == 'Pressure-Absolute':
                    required += ['WaterPressure']
                elif subject == 'Recording':
                    required += ['Location', 'Channel', 'DataQuality', 'Latitude', 'Longitude',
                                 'Elevation', 'SampleRate', 'SampleCount', 'TimeCorrectionApplied']
                    if source['DataQuality'] not in {'Q', 'D'}:
                        raise ValueError('Recording DataQuality must be Q or D')
                    if source['DataQuality'] == 'Q':
                        required += ['WaterPressure']
                    count = source['SampleCount']
                    if not isinstance(count, (int, np.integer)) or not 1 <= count < 2**63:
                        raise ValueError('Recording SampleCount must be a positive Int64')
                    if float(source['SampleRate']) <= 0:
                        raise ValueError('Recording SampleRate must be positive')
                else:
                    required += ['Latitude', 'Longitude', 'WaterPressure']
                for field in required:
                    value = source[field]
                    if (value is None or value == '' or
                            (isinstance(value, str) and not value.strip()
                             and not (field == 'Location' and value == '  '))):
                        raise ValueError(f"GeoCSV required field {field!r} is empty in data row {row_number}")
                for field in ['Network', 'Station', 'InstrumentDescription']:
                    if not isinstance(source[field], str):
                        raise ValueError(f'GeoCSV {field} requires a source string')
                for field, low, high in [('Latitude', -90, 90), ('Longitude', -180, 180)]:
                    if source[field] != '' and not low <= float(source[field]) <= high:
                        raise ValueError(f'GeoCSV {field} is out of range')
                if (subject != 'Pressure-Absolute' and source['WaterPressure'] != ''
                        and float(source['WaterPressure']) < 0):
                    raise ValueError('GeoCSV WaterPressure must be nonnegative')
            for field in ['Network', 'Station', 'InstrumentDescription']:
                if len({row[self.header.index(field)] for row in rows}) > 1:
                    raise ValueError(f'GeoCSV requires one {field} per file')

        def format_algo_thermo_rows(cycle):
            """Format descent/ascent crossings of the configured upper mixed-layer base.

            Preserve the GPS helper's intentional anchor position/time fallback.

            Args:
                cycle (cycles.Cycle instance):

            """

            thermo_algo_rows = []
            descent = cycle.descent_leave_surface_layer_loc
            ascent =  cycle.ascent_reach_surface_layer_loc
            for thermo, identifier in [(descent, self.MethodIdentifier_Crossing_Descent),
                                       (ascent, self.MethodIdentifier_Crossing_Ascent)]:
                if thermo is None:
                    continue

                thermo_algo_rows.append([
                    identifier,
                    _format_utc(thermo.date),
                    cycle.network,
                    cycle.kstnm,
                    absent,
                    absent,
                    absent,
                    d6(thermo.latitude),
                    d6(thermo.longitude),
                    absent,
                    d0(self.mixed_layer_depth_m * 100),
                    instrument(cycle),
                    absent,
                    absent,
                    absent,
                    absent
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

            # Recording rows, paired with their source Event instances
            algo_rows_tup = format_algo_event_rows(cycle)
            det_algo_records.extend(algo_rows_tup[0])
            req_algo_records.extend(algo_rows_tup[1])

            # Interpolated upper mixed-layer boundary rows
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

        # The complete file combines measurement, recording and crossing rows
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
        with open(basename+'_DET_REQ.csv', 'w', encoding='utf-8', newline='') as csvfile_det_req, \
             open(basename+'_DET.csv', 'w', encoding='utf-8', newline='') as csvfile_det, \
             open(basename+'_REQ.csv', 'w', encoding='utf-8', newline='') as csvfile_req:

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

            # Write the combined measurement, recording and crossing rows to all three files
            for csvfile, rows in [(csvfile_det, geocsv_det_rows),
                                  (csvfile_req, geocsv_req_rows),
                                  (csvfile_det_req, geocsv_det_req_rows)]:
                for row in rows:
                    # Keep standard CSV escaping and make the defined blank
                    # Location visible as the canonical quoted two-space cell.
                    cells = []
                    for field, value in zip(self.header, row):
                        cell = io.StringIO(newline='')
                        csv.writer(cell, lineterminator=self.lineterminator).writerow([value])
                        encoded = '' if value == '' else cell.getvalue()[:-len(self.lineterminator)]
                        cells.append('"  "' if field == 'Location' and value == '  ' else encoded)
                    csvfile.write(self.delimiter.join(cells) + self.lineterminator)

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

        _write_clash_json(basename + '_DET_REQ.csv', det_req_clashes)

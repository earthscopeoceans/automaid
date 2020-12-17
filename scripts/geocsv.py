# -*- coding: utf-8 -*-
#
# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v2.7)
#
# Author: Joel. D Simon
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified: 16-Dec-2020, Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit

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
        self.field_unit_header = ["#field_unit",
                                  "ISO_8601",
                                  "degrees_north",
                                  "degrees_east"]
        self.field_type_header = ["#field_type",
                                  "datetime",
                                  "float(32bit)",
                                  "float(32bit)"]
        self.MethodIdentifier_header = ["MethodIdentifier",
                                        "StartTime",
                                        "Latitude",
                                        "Longitude"]


    def write(self, filename='mermaid_geo.csv'):
        """Write GeoCSV file

        Args:
            filename (str): GeoCSV filename (def: mermaid_geo.csv)

        """
        #filename.append('geocsv') if filename.split('.')[-1] != 'geocsv' else pass

        def write_headers(csvwriter):
            """Write GeoCSV header rows

            Args:
                csvwriter (writer): csv.writer object for open file

            """
            csvwriter.writerows([self.dataset_header,
                                 self.delimiter_header,
                                 self.MethodIdentifier_header,
                                 self.field_unit_header,
                                 self.field_type_header])


        def write_measurement_rows(gps_list):
            """Write GeoCSV rows of GPS measurements

            Args:
               gps (list): List of gps.GPS instances of actual GPS measurements

            """

            for gps in gps_list: #sort
                csvwriter.writerow(['Measurement:GPS:Trimble',
                                    str(gps.date)[0:19]+'Z',
                                    np.float32(gps.latitude),
                                    np.float32(gps.longitude)])

        def write_algorithm_rows(event_list):
            """Write GeoCSV rows of event measurements (e.g. STDP) and interpolations
            (e.g. STLA/STLO)

            Args:
                events (list): list of events.Event instances with interpolations

            """
            for event in event_list: #sort
                csvwriter.writerow(['Algorithm:automaid:v3.3.0',
                                    str(event.station_loc.date)[0:19]+'Z',
                                    np.float32(event.station_loc.latitude),
                                    np.float32(event.station_loc.longitude)])


        # Open as as 'wb' in Python 2 rather than 'w' with newline='' in Python 3
        # https://docs.python.org/2/library/csv.html#csv.writer
        with open(filename, 'wb') as csvfile:
            csvwriter = csv.writer(csvfile, delimiter=self.delimiter)

            # Write headers
            write_headers(csvwriter)

            # Write metadata rows
            for dive in self.dives:
                if dive.gps_before_dive is not None:
                    write_measurement_rows(dive.gps_before_dive)

                if dive.events is not None:
                    write_algorithm_rows(dive.events)

                if dive.gps_after_dive is not None:
                    write_measurement_rows(dive.gps_after_dive)




if __name__ == '__main__':
    dive_list = pickle.load( open('mdives.p', 'rb') )
    geocsv = GeoCSV(dive_list)
    geocsv.write()

# automaid v0.3.0
# pymaid environment (Python v2.7)
#
# Original author: Sebastien Bonnieux
#
# Current maintainer: Dr. Joel D. Simon (JDS)
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified by JDS: 11-Sep-2020, Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit

import re
from obspy import UTCDateTime
import plotly.graph_objs as graph
import plotly.offline as plotly


def plot_battery_voltage(vital_file_path, vital_file_name, begin, end):
    # Read file
    with open(vital_file_path + vital_file_name, "r") as f:
        content = f.read()

    # Find battery values
    battery_catch = re.findall("(.+): Vbat (\d+)mV \(min (\d+)mV\)", content)
    date = [UTCDateTime(0).strptime(i[0], "%Y%m%d-%Hh%Mmn%S") for i in battery_catch]
    voltage = [float(i[1])/1000. for i in battery_catch]
    minimum_voltage = [float(i[2])/1000. for i in battery_catch]

    if len(date) < 1:
        return

    # Get values between the appropriate date
    i = 0
    while date[i] < begin and i < len(date)-1:
        i += 1
    j = 0

    while date[j] < end and j < len(date)-1:
        j += 1
    date = date[i:j+1]
    voltage = voltage[i:j+1]
    minimum_voltage = minimum_voltage[i:j+1]

    # Add battery values to the graph
    voltage_line = graph.Scatter(x=date,
                                 y=voltage,
                                 name="voltage",
                                 line=dict(color='blue',
                                           width=2),
                                 mode='lines')

    minimum_voltage_line = graph.Scatter(x=date,
                                         y=minimum_voltage,
                                         name="minimum voltage",
                                         line=dict(color='orange',
                                                   width=2),
                                         mode='lines')

    data = [voltage_line, minimum_voltage_line]

    layout = graph.Layout(title="Battery level in \"" + vital_file_name + "\"",
                          xaxis=dict(title='Coordinated Universal Time (UTC)', titlefont=dict(size=18)),
                          yaxis=dict(title='Voltage (Volts)', titlefont=dict(size=18)),
                          hovermode='closest'
                          )

    plotly.plot({'data': data, 'layout': layout},
                filename=vital_file_path + "voltage.html",
                auto_open=False)


def plot_internal_pressure(vital_file_path, vital_file_name, begin, end):
    # Read file
    with open(vital_file_path + vital_file_name, "r") as f:
        content = f.read()

    # Find battery values
    internal_pressure_catch = re.findall("(.+): Pint (-?\d+)Pa", content)
    date = [UTCDateTime(0).strptime(i[0], "%Y%m%d-%Hh%Mmn%S") for i in internal_pressure_catch]
    internal_pressure = [float(i[1])/100. for i in internal_pressure_catch]

    if len(date) < 1:
        return

    # Get values between the appropriate date
    i = 0
    while date[i] < begin and i < len(date)-1:
        i += 1
    j = 0
    while date[j] < end and j < len(date)-1:
        j += 1
    date = date[i:j+1]
    internal_pressure = internal_pressure[i:j+1]

    # Add battery values to the graph
    internal_pressure_line = graph.Scatter(x=date,
                                           y=internal_pressure,
                                           name="internal pressure",
                                           line=dict(color='blue',
                                                     width=2),
                                           mode='lines')

    data = [internal_pressure_line]

    layout = graph.Layout(title="Internal pressure in \"" + vital_file_name + "\"",
                          xaxis=dict(title='Coordinated Universal Time (UTC)', titlefont=dict(size=18)),
                          yaxis=dict(title='Internal pressure (millibars)', titlefont=dict(size=18)),
                          hovermode='closest'
                          )

    plotly.plot({'data': data, 'layout': layout},
                filename=vital_file_path + "internal_pressure.html",
                auto_open=False)


def plot_pressure_offset(vital_file_path, vital_file_name, begin, end):
    # Read file
    with open(vital_file_path + vital_file_name, "r") as f:
        content = f.read()

    # Find battery values
    pressure_offset_catch = re.findall("(.+): Pext (-?\d+)mbar \(range (-?\d+)mbar\)", content)
    date = [UTCDateTime(0).strptime(i[0], "%Y%m%d-%Hh%Mmn%S") for i in pressure_offset_catch]
    pressure_offset = [int(i[1]) for i in pressure_offset_catch]
    pressure_offset_range = [int(i[2]) for i in pressure_offset_catch]
    if len(date) < 1:
        return

    # Filter wrong values
    res = [(x, y, z) for x, y, z in zip(pressure_offset, pressure_offset_range, date) if x != -2147483648]
    pressure_offset = [x[0] for x in res]
    pressure_offset_range = [x[1] for x in res]
    date = [x[2] for x in res]
    if len(date) < 1:
        return

    # Get values between the appropriate date
    i = 0
    while date[i] < begin and i < len(date)-1:
        i += 1
    j = 0
    while date[j] < end and j < len(date)-1:
        j += 1
    date = date[i:j+1]
    date_rev = date[::-1]
    pressure_offset = pressure_offset[i:j]
    pressure_offset_range = pressure_offset_range[i:j+1]
    pressure_offset_max = [x + y for x, y in zip(pressure_offset, pressure_offset_range)]
    pressure_offset_min = [x - y for x, y in zip(pressure_offset, pressure_offset_range)]
    pressure_offset_min_rev = pressure_offset_min[::-1]

    # Add battery values to the graph
    pressure_offset_line = graph.Scatter(x=date,
                                         y=pressure_offset,
                                         name="pressure offset",
                                         line=dict(color='blue',
                                                   width=2),
                                         mode='lines')

    pressure_offset_range = graph.Scatter(x=date + date_rev,
                                          y=pressure_offset_max + pressure_offset_min_rev,
                                          fill='tozerox',
                                          fillcolor='rgba(0,0,256,0.2)',
                                          name="range",
                                          line=dict(color='rgba(0, 0, 0, 0)'),
                                          showlegend=False)

    data = [pressure_offset_line, pressure_offset_range]

    layout = graph.Layout(title="External pressure offset in \"" + vital_file_name + "\"",
                          xaxis=dict(title='Coordinated Universal Time (UTC)', titlefont=dict(size=18)),
                          yaxis=dict(title='Pressure offset (millibars)', titlefont=dict(size=18)),
                          hovermode='closest'
                          )

    plotly.plot({'data': data, 'layout': layout},
                filename=vital_file_path + "external_pressure_offset.html",
                auto_open=False)


def plot_corrected_pressure_offset(vital_file_path, mdives, begin, end):

    pressure_offset = [dive.p2t_offset_measurement - dive.p2t_offset_param for dive in mdives if dive.is_complete_dive]
    date = [dive.end_date for dive in mdives if dive.is_complete_dive]

    # Dead-float adjustment
    if len(date) < 1:
        return

    # Get values between the appropriate date
    i = 0
    while date[i] < begin and i < len(date)-1:
        i += 1
    j = 0

    while date[j] < end and j < len(date)-1:
        j += 1
    date = date[i:j+1]
    pressure_offset = pressure_offset[i:j+1]

    # Add battery values to the graph
    pressure_offset_line = graph.Scatter(x=date,
                                         y=pressure_offset,
                                         name="pressure offset",
                                         line=dict(color='blue',
                                                   width=2),
                                         mode='lines')

    data = [pressure_offset_line]

    layout = graph.Layout(title="Corrected pressure offset in LOG files",
                          xaxis=dict(title='Coordinated Universal Time (UTC)', titlefont=dict(size=18)),
                          yaxis=dict(title='Pressure offset (millibars)', titlefont=dict(size=18)),
                          hovermode='closest'
                          )

    plotly.plot({'data': data, 'layout': layout},
                filename=vital_file_path + "corrected_pressure_offset.html",
                auto_open=False)

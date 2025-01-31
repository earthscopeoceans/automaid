# -*- coding: utf-8 -*-
#
# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v2.7)
#
# Developer: Joel D. Simon (JDS)
# Original author: Sebastien Bonnieux (SB)
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified by JDS: 03-Oct-2022
# Last tested: Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit

import re
import os
import plotly.graph_objs as graph
import plotly.offline as plotly

from obspy import UTCDateTime

import setup

# Get current version number
version = setup.get_version()

def plot_battery_voltage(vital_file_path, vital_file_name, begin, end):
    # Read file
    with open(vital_file_path + vital_file_name, "rb") as f:
        content = f.read().decode("utf-8","replace")

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

    return

def plot_internal_pressure(vital_file_path, vital_file_name, begin, end):
    # Read file
    with open(vital_file_path + vital_file_name, "rb") as f:
        content = f.read().decode("utf-8","replace")

    # Find battery values
    date = []
    internal_pressure_catch = re.findall("(.+): Pint (-?\d+)Pa", content)
    for i in internal_pressure_catch:
        try:
            date.append(UTCDateTime(0).strptime(i[0], "%Y%m%d-%Hh%Mmn%S"))
        except ValueError:
            # Skip improperly-formatted datestr
            # (e.g., "ÿÿ20210703-02h11mn31: Pint 78856Pa" in 452.020-P-0041.vit)
            continue

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

    return

def plot_pressure_offset(vital_file_path, vital_file_name, begin, end):
    # Read file
    with open(vital_file_path + vital_file_name, "rb") as f:
        content = f.read().decode("utf-8","replace")

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


    return

def plot_corrected_pressure_offset(vital_file_path, cycles, begin, end):
    date  = [cycle.end_date for cycle in cycles]
    corrected_pressure_offset = [cycle.last_p2t_offset_corrected for cycle in cycles]

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
    corrected_pressure_offset = corrected_pressure_offset[i:j+1]

    # Add battery values to the graph
    corrected_pressure_offset_line = graph.Scatter(x=date,
                                                   y=corrected_pressure_offset,
                                                   name="corrected_pressure offset",
                                                   line=dict(color='blue',
                                                             width=2),
                                                   mode='lines')

    data = [corrected_pressure_offset_line]

    layout = graph.Layout(title="Corrected pressure offset in LOG files",
                          xaxis=dict(title='Coordinated Universal Time (UTC)', titlefont=dict(size=18)),
                          yaxis=dict(title='Corrected pressure offset (millibars)', titlefont=dict(size=18)),
                          hovermode='closest'
                          )

    plotly.plot({'data': data, 'layout': layout},
                filename=vital_file_path + "corrected_external_pressure_offset.html",
                auto_open=False)

    return

def write_corrected_pressure_offset(lastcycle, processed_path):
    '''Writes:

    [processed_path]/lastcycle_pressure_offset.txt

    given a dict of whose keys are float serial numbers whose single values are
    the last assocaited Complete_Dive instance

    '''

    lastcycle_fmt_spec = "{:>14s}    {:>19s}    {:>17s}      {:>3d}      {:>3d}          {:>3d}  {:3>s}\n"
    lastcycle_f = os.path.join(processed_path, "lastcycle_pressure_offset.txt")
    with open(lastcycle_f, "w+") as f:
        f.write("       MERMAID         LAST_SURFACING             LOG_NAME     PEXT   OFFSET  PEXT-OFFSET\n".format())
        for mfloat in sorted(lastcycle.keys()):
            cycle = lastcycle[mfloat]
            if cycle.last_p2t_log_name is not None:
                print("Checking final corrected external pressure reading for float {:s} [from {:s}]".format(mfloat, str(cycle.last_p2t_log_name)))
                warn_str = ''
                if cycle.last_p2t_offset_corrected > 200:
                    warn_str = '!!!'
                    print("\n!!! WARNING: {:s} corrected external pressure was {:d} mbar at last surfacing"
                          .format(mfloat, cycle.last_p2t_offset_corrected))
                    print("!!! The corrected external pressure must stay below 300 mbar")
                    print("!!! Consider adjusting {:s}.cmd using 'p2t qm!offset ...' AFTER 'buoy bypass' and BEFORE 'stage ...'\n"
                          .format(mfloat))

                f.write(lastcycle_fmt_spec.format(mfloat,
                                                 str(cycle.ascent_reach_surface_date)[0:19],
                                                 cycle.last_p2t_log_name,
                                                 cycle.last_p2t_offset_measurement,
                                                 cycle.last_p2t_offset_param,
                                                 cycle.last_p2t_offset_corrected,
                                                 warn_str))
            else:
                # Final .LOG did not record any external pressure measurements
                # (e.g. due error/reset/incomplete transmission)
                f.write("{:>14s} >> no external pressure measurements in {:s}) <<\n"\
                        .format(mfloat, cycle.cycle_name[-1]))

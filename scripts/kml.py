# -*- coding: utf-8 -*-
#
# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v2.7)
#
# Developer: Joel D. Simon (JDS)
# Original author: Sebastien Bonnieux
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified by JDS: 13-Aug-2021
# Last tested: Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit

import setup
import os
import random

# Get current version number.
version = setup.get_version()

def generate(dest_path, mfloat_name, complete_dives):
    if len(complete_dives) < 1:
        return

    kml_string = str()
    kml_string += kmlbeg()
    kml_string += docbeg(mfloat_name)
    kml_string += linestyle(mfloat_name)
    kml_string += markerstyle()

    kml_string += folderbeg("Events marker")
    kml_string += events_marker(complete_dives)
    kml_string += folderend()

    kml_string += folderbeg("GPS points")
    kml_string += gps_point_marker(complete_dives)
    kml_string += folderend()

    kml_string += folderbeg("Interpolated points")
    kml_string += interpolated_point_marker(complete_dives)
    kml_string += folderend()

    kml_string += folderbeg("Last position")
    kml_string += last_pos_marker(complete_dives)
    kml_string += folderend()

    kml_string += folderbeg("Trajectory")
    kml_string += complex_trajectory(mfloat_name, complete_dives)
    kml_string += folderend()

    # kmlfile += look_at_auto(mermaid, 0)

    kml_string += docend()
    kml_string += kmlend()
    with open(dest_path + "position.kml", 'w') as f:
        f.write(kml_string)


def kmlbeg():
    string = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"
  xmlns:gx="http://www.google.com/kml/ext/2.2">"""
    return string


def kmlend():
    string = """
</kml>"""
    return string


def docbeg(name):
    string = """
    <Document>
        <name>""" + name + """</name>
        <open>0</open>"""
    return string


def docend():
    string = """
    </Document>"""
    return string


def folderbeg(name):
    string = """
        <Folder id=\"""" + name + """\">
        <name>""" + name + """</name>"""
    return string


def folderend():
    string = """
        </Folder>"""
    return string


def linestyle(mfloat_name, width=2.5):
    def r(): return random.randint(0, 255)
    color = 'ff%02X%02X%02X' % (r(), r(), r())

    string = """
        <Style id="lineStyle1">
            <LineStyle>
                <color> ff0066ff </color>
                <width>""" + str(width) + """</width>
            </LineStyle>
        </Style>
        <Style id="lineStyle2">
            <LineStyle>
                <color>ffffffff</color>
                <width>""" + str(width) + """</width>
            </LineStyle>
        </Style>
        <Style id="lineStyle_m""" + mfloat_name[-2:] + """">
            <LineStyle>
                <color> """ + color + """ </color>
                <width>""" + str(width) + """</width>
            </LineStyle>
        </Style>"""
    return string


def markerstyle(scale=1):
    string = """
        <Style id="markerStyle1">
            <IconStyle>
                <color> ff0066ff </color>
                <scale>""" + str(scale) + """</scale>
                <Icon>
                    <href>http://maps.google.com/mapfiles/kml/paddle/wht-stars.png</href>
                </Icon>
                <hotSpot x="0.5" y="0" xunits="fraction" yunits="fraction"/>
            </IconStyle>
            <ListStyle>
                <ItemIcon>
                <href>http://maps.google.com/mapfiles/kml/paddle/wht-stars.png</href>
                </ItemIcon>
            </ListStyle>
            <LabelStyle>
                <scale>""" + str(scale) + """</scale>
            </LabelStyle>
            <BalloonStyle id="baloonstyle">
                <!-- specific to BalloonStyle -->
                <bgColor>ffffffff</bgColor>            <!-- kml:color -->
                <textColor>ff000000</textColor>        <!-- kml:color -->
                <text>$[description]</text>                       <!-- string -->
                <displayMode>default</displayMode>     <!-- kml:displayModeEnum -->
            </BalloonStyle>
        </Style>""" + """
        <Style id="markerStyle2">
            <IconStyle>
                <color> ff00A014 </color>
                <scale> 0.25 </scale>
                <Icon>
                    <href>http://maps.google.com/mapfiles/kml/shapes/road_shield3.png</href>
                </Icon>
            </IconStyle>
            <LabelStyle>
                <scale> 1 </scale>
            </LabelStyle>
        </Style>
        <Style id="markerStyle3">
            <IconStyle>
                <color> ff14F096 </color>
                <scale> 0.25 </scale>
                <Icon>
                    <href>http://maps.google.com/mapfiles/kml/shapes/road_shield3.png</href>
                </Icon>
            </IconStyle>
            <LabelStyle>
                <scale> 1 </scale>
            </LabelStyle>
        </Style>
        <Style id="markerStyle4">
            <IconStyle>
                <color> FF14B4FF </color>
                <scale> 0.6 </scale>
                <Icon>
                    <href>http://maps.google.com/mapfiles/kml/shapes/star.png</href>
                </Icon>
            </IconStyle>
            <LabelStyle>
                <scale> 1 </scale>
            </LabelStyle>
        </Style>
        <Style id="markerStyle5">
            <IconStyle>
                <color> FFF0B414 </color>
                <scale> 0.8 </scale>
                <Icon>
                    <href>http://maps.google.com/mapfiles/kml/shapes/star.png</href>
                </Icon>
            </IconStyle>
            <LabelStyle>
                <scale> 1 </scale>
            </LabelStyle>
        </Style>
        <Style id="ppoint500Style">
            <IconStyle>
                <color> ff78B4F0 </color>
                <scale> 1 </scale>
                <Icon>
                    <href>http://maps.google.com/mapfiles/kml/shapes/donut.png</href>
                </Icon>
            </IconStyle>
        </Style>
        <Style id="ppoint1000Style">
            <IconStyle>
                <color> ff786EF0 </color>
                <scale> 1 </scale>
                <Icon>
                    <href>http://maps.google.com/mapfiles/kml/shapes/donut.png</href>
                </Icon>
            </IconStyle>
        </Style>
        <Style id="ppoint2000Style">
            <IconStyle>
                <color> ff7828F0 </color>
                <scale> 1 </scale>
                <Icon>
                    <href>http://maps.google.com/mapfiles/kml/shapes/donut.png</href>
                </Icon>
            </IconStyle>
        </Style>"""
    return string


def events_marker(complete_dives):
    string = ""
    for dive in complete_dives[:-1]:
        for event in dive.events:
            if event.station_loc is None:
                continue
            pos = str(event.station_loc.longitude) + "," + str(event.station_loc.latitude) + ",0"

            string += """
                <Placemark>
                    <description><![CDATA[
    <div style="width:910x">
    <img src=\""""
            string += os.path.join(dive.directory_name, event.export_file_name + ".png")
            string += """\" style="width:675px">
          ]]>
                    </description>
                    <styleUrl> #markerStyle4 </styleUrl>
                    <Point>
                        <coordinates> """ + pos + """ </coordinates>
                    </Point>
                </Placemark>"""
    return string


def gps_point_marker(complete_dives):
    dfmt = "%d/%m/%y %H:%M"
    string = ""
    for dive in complete_dives:
        for gps in dive.gps_list:
            pos = str(gps.longitude) + "," + str(gps.latitude) + ",0"
            string += """
        <Placemark>
            <name>""" + gps.date.strftime(dfmt) + """</name>
            <visibility>1</visibility>
            <styleUrl> #markerStyle2 </styleUrl>
            <Point>
                <coordinates> """ + pos + """ </coordinates>
            </Point>
        </Placemark>"""
    return string


def interpolated_point_marker(complete_dives):
    dfmt = "%d/%m/%y %H:%M"
    string = ""
    for dive in complete_dives[1:]:
        if dive.descent_leave_surface_loc:
            pos = str(dive.descent_leave_surface_loc.longitude) + "," + str(dive.descent_leave_surface_loc.latitude) + ",0"
            posstr = dive.descent_leave_surface_loc.date.strftime(dfmt)
            string += """
            <Placemark>
                <name>""" + posstr + """</name>
                <visibility>1</visibility>
                <styleUrl> #markerStyle3 </styleUrl>
                <Point>
                    <coordinates> """ + pos + """ </coordinates>
                </Point>
            </Placemark>"""

        if dive.descent_leave_surface_layer_loc:
            pos = str(dive.descent_leave_surface_layer_loc.longitude) + "," + str(dive.descent_leave_surface_layer_loc.latitude) + ",0"
            posstr = dive.descent_leave_surface_layer_loc.date.strftime(dfmt)
            string += """
            <Placemark>
                <name>""" + posstr + """</name>
                <visibility>1</visibility>
                <styleUrl> #markerStyle3 </styleUrl>
                <Point>
                    <coordinates> """ + pos + """ </coordinates>
                </Point>
            </Placemark>"""

        if dive.ascent_reach_surface_layer_loc:
            pos = str(dive.ascent_reach_surface_layer_loc.longitude) + "," + str(dive.ascent_reach_surface_layer_loc.latitude) + ",0"
            posstr = dive.ascent_reach_surface_layer_loc.date.strftime(dfmt)
            string += """
            <Placemark>
                <name>""" + posstr + """</name>
                <visibility>1</visibility>
                <styleUrl> #markerStyle3 </styleUrl>
                <Point>
                    <coordinates> """ + pos + """ </coordinates>
                </Point>
            </Placemark>"""

        if dive.ascent_reach_surface_loc:
            pos = str(dive.ascent_reach_surface_loc.longitude) + "," + str(dive.ascent_reach_surface_loc.latitude) + ",0"
            posstr = dive.ascent_reach_surface_loc.date.strftime(dfmt)
            string += """
            <Placemark>
                <name>""" + posstr + """</name>
                <visibility>1</visibility>
                <styleUrl> #markerStyle3 </styleUrl>
                <Point>
                    <coordinates> """ + pos + """ </coordinates>
                </Point>
            </Placemark>"""

    return string


def last_pos_marker(complete_dives):
    last_dive = complete_dives[-1]
    if len(last_dive.gps_list) < 1 or not last_dive.station_name:
        return ""
    last_pos = last_dive.gps_list[-1]
    pos = str(last_pos.longitude) + "," + str(last_pos.latitude) + ",0"

    string = """
        <Placemark id=\"""" + last_dive.station_name + """_mark">
            <name>""" + last_dive.station_name + """</name>
            <styleUrl>#markerStyle1</styleUrl>
            <Point>
                <gx:drawOrder>10</gx:drawOrder>
                <coordinates>""" + pos + """</coordinates>
            </Point>
        </Placemark>"""
    return string


def complex_trajectory(mfloat_name, complete_dives):
    string = ""

    # Surface line
    pos = ""
    i = 0
    while i < len(complete_dives):
        # Use the surface drift of the end of the precedent dive
        if i > 1:
            dive = complete_dives[i-1]
            if dive.ascent_reach_surface_layer_loc is not None:
                pos += str(dive.ascent_reach_surface_layer_loc.longitude) + ","\
                       + str(dive.ascent_reach_surface_layer_loc.latitude) + ",0\n"
            if dive.ascent_reach_surface_loc is not None:
                pos += str(dive.ascent_reach_surface_loc.longitude) + "," + str(dive.ascent_reach_surface_loc.latitude) + ",0\n"
            if len(dive.gps_list) > 0:
                pos += str(dive.gps_list[-1].longitude) + "," + str(dive.gps_list[-1].latitude) + ",0\n"
        # Surface drift of the beginning of the current dive
        dive = complete_dives[i]
        for gps in dive.gps_list[:-1]:
            pos += str(gps.longitude) + "," + str(gps.latitude) + ",0\n"
        if complete_dives[i].descent_leave_surface_loc is not None:
            pos += str(dive.descent_leave_surface_loc.longitude) + "," + str(dive.descent_leave_surface_loc.latitude) + ",0\n"
        if dive.descent_leave_surface_layer_loc is not None:
            pos += str(dive.descent_leave_surface_layer_loc.longitude) + "," + str(dive.descent_leave_surface_layer_loc.latitude) + ",0\n"

        pos = pos.strip("\n")

        string += """
        <Placemark>
            <styleUrl>#lineStyle2</styleUrl>
            <LineString>
                <tessellate>1</tessellate>
                <coordinates>
""" + pos + """
                </coordinates>
            </LineString>
        </Placemark>"""

        # Keep last position
        pos = pos.split("\n")[-1] + "\n"

        # Descent position
        if dive.descent_leave_surface_layer_loc is not None:
            pos += str(dive.descent_leave_surface_layer_loc.longitude) + "," + str(dive.descent_leave_surface_layer_loc.latitude) + ",0\n"
        elif dive.descent_leave_surface_loc is not None:
            pos += str(dive.descent_leave_surface_loc.longitude) + "," + str(dive.descent_leave_surface_loc.latitude) + ",0\n"
        # Ascent position
        if dive.ascent_reach_surface_layer_loc is not None:
            pos += str(dive.ascent_reach_surface_layer_loc.longitude) + "," + str(dive.ascent_reach_surface_layer_loc.latitude) + ",0\n"
        elif dive.ascent_reach_surface_loc is not None:
            pos += str(dive.ascent_reach_surface_loc.longitude) + "," + str(dive.ascent_reach_surface_loc.latitude) + ",0\n"

        pos = pos.strip("\n")

        string += """
        <Placemark>
            <styleUrl>#lineStyle_m""" + mfloat_name[-2:] + """</styleUrl>
            <LineString>
                <tessellate>1</tessellate>
                <coordinates>
""" + pos + """
                </coordinates>
            </LineString>
        </Placemark>"""

        # Keep last position
        pos = pos.split("\n")[-1] + "\n"

        # Increment i
        i += 1

    # Add last dive surface position
    if len(complete_dives[-1].gps_list) > 0:
        pos += str(complete_dives[-1].gps_list[-1].longitude) + "," + str(complete_dives[-1].gps_list[-1].latitude) + ",0\n"
    
    line_style = "#lineStyle_m" + mfloat_name[-2:]
    string += """
            <Placemark>
                <styleUrl>""" + line_style + """</styleUrl>
                <LineString>
                    <tessellate>1</tessellate>
                    <coordinates>
""" + pos + """
                    </coordinates>
                </LineString>
            </Placemark>"""

    return string
